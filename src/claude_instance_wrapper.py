"""
Claude 实例封装模块

将子 Claude 实例封装成可调用的工具
"""

import json
from pathlib import Path
from typing import Any

from claude_agent_sdk import tool

from .error_handling import InstanceExecutionError
from .logging_config import get_logger

logger = get_logger(__name__)


def create_claude_instance_tool(
    instance_name: str,
    instance_path: Path,
    instances_root: Path
) -> callable:
    """
    创建子 Claude 实例工具

    此函数只创建工具定义，不实例化 AgentSystem。
    当工具被调用时，才会创建 AgentSystem 实例。

    注意：子实例会自动从环境变量 ANTHROPIC_API_KEY 读取 API 密钥。

    Args:
        instance_name: 实例名称
        instance_path: 实例目录路径
        instances_root: 实例根目录

    Returns:
        工具函数
    """

    # 尝试加载实例描述（用于工具说明）
    try:
        from .config_loader import AgentConfigLoader
        config_loader = AgentConfigLoader(instance_path)
        config = config_loader.load()
        description = config.get("agent", {}).get("description", f"调用 {instance_name} 子 Claude 实例")
    except Exception as e:
        logger.warning(f"加载实例 {instance_name} 配置失败，使用默认描述: {e}")
        description = f"调用 {instance_name} 子 Claude 实例"

    @tool(
        name=f"sub_claude_{instance_name}",
        description=description,
        input_schema={
            "task": {
                "type": "string",
                "description": "要执行的任务描述"
            },
            "context_files": {
                "type": "array",
                "description": "相关文件路径列表（可选）",
                "items": {"type": "string"}
            },
            "output_format": {
                "type": "string",
                "description": "输出格式：text（默认）、json、markdown",
                "enum": ["text", "json", "markdown"]
            },
            "resume_session_id": {
                "type": "string",
                "description": "要恢复的会话 ID（可选，用于继续之前的对话）"
            },
            "max_turns": {
                "type": "integer",
                "description": "最大对话轮次（可选）"
            },
            "variables": {
                "type": "object",
                "description": "变量字典，注入到提示词中（可选）"
            },
            "cwd": {
                "type": "string",
                "description": "工作目录（可选）"
            }
        }
    )
    async def execute_instance(args: dict[str, Any]) -> dict[str, Any]:
        """
        执行子 Claude 实例

        工具被调用时，动态创建 AgentSystem 实例并执行。

        Args:
            args: 工具参数

        Returns:
            工具执行结果
        """
        task = args.get("task")
        context_files = args.get("context_files", [])
        output_format = args.get("output_format", "text")
        resume_session_id = args.get("resume_session_id")
        max_turns = args.get("max_turns")
        variables = args.get("variables", {})
        # 确保 variables 是字典类型
        if isinstance(variables, str):
            # 如果传入的是字符串，尝试解析为 JSON
            try:
                import json
                variables = json.loads(variables)
            except (json.JSONDecodeError, TypeError):
                # 如果解析失败，创建一个简单的字典
                variables = {"value": variables}
        elif variables is None:
            variables = {}
        cwd = args.get("cwd")

        if not task:
            return {
                "content": [{
                    "type": "text",
                    "text": "错误：task 参数是必需的"
                }],
                "is_error": True
            }

        logger.info(f"开始执行子实例: {instance_name}")
        logger.debug(f"任务: {task}")

        try:
            # 延迟导入，避免循环依赖
            from .agent_system import AgentSystem

            # 创建子 Claude 的 AgentSystem 实例
            # API 密钥会自动从环境变量 ANTHROPIC_API_KEY 读取
            sub_agent = AgentSystem(
                instance_name=str(instance_path),
                instances_root=instances_root
            )

            # 初始化子实例
            await sub_agent.initialize()

            # 构建提示词
            prompt = _build_prompt(task, context_files, variables, output_format)

            # 执行查询（支持 resume）
            query_result = await sub_agent.query_text(
                prompt,
                record_session=True,
                resume_session_id=resume_session_id
            )

            # 构建标准 MCP 工具返回格式
            result = {
                "content": [{
                    "type": "text",
                    "text": query_result.result
                }]
            }

            # 添加会话 ID 到响应（用于父级查询）
            if query_result.session_id:
                result["_session_metadata"] = {
                    "session_id": query_result.session_id,
                    "instance_name": instance_name,
                    "resumed": bool(resume_session_id)
                }
                logger.info(f"子实例会话 ID: {query_result.session_id}" +
                          (f" (resumed from {resume_session_id})" if resume_session_id else ""))

            return result

        except Exception as e:
            logger.error(f"子实例执行失败: {e}", exc_info=True)
            return {
                "content": [{
                    "type": "text",
                    "text": f"子实例执行失败: {str(e)}"
                }],
                "is_error": True
            }

    return execute_instance


def _build_prompt(
    task: str,
    context_files: list[str],
    variables: dict[str, str],
    output_format: str
) -> str:
    """
    构建提示词

    Args:
        task: 任务描述
        context_files: 上下文文件列表
        variables: 变量字典
        output_format: 输出格式

    Returns:
        完整的提示词
    """
    sections = []

    # 添加变量部分
    if variables:
        var_lines = ["## 变量"] + [f"- {key}: {value}" for key, value in variables.items()] + [""]
        sections.append("\n".join(var_lines))

    # 添加上下文文件部分
    if context_files:
        file_lines = ["## 相关文件"] + [f"- {fp}" for fp in context_files] + [""]
        sections.append("\n".join(file_lines))

    # 添加输出格式要求
    format_instructions = {
        "json": "请以 JSON 格式返回结果。",
        "markdown": "请以 Markdown 格式返回结果。"
    }
    if output_format in format_instructions:
        sections.append(format_instructions[output_format])

    # 添加任务（始终放在最后）
    sections.append(f"## 任务\n{task}")

    return "\n\n".join(sections)


