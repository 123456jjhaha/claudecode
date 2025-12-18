"""
子实例适配器

将子 Claude 实例作为工具集成到父实例中
"""

from pathlib import Path
from typing import Dict, Any, Optional, List
from .logging_config import get_logger
from .session.utils import SessionContext

logger = get_logger(__name__)


class SubInstanceTool:
    """子实例工具类"""

    def __init__(
        self,
        instance_name: str,
        instance_path: Path,
        instances_root: Path
    ):
        """
        初始化子实例工具

        Args:
            instance_name: 子实例名称
            instance_path: 子实例路径（相对于 instances_root）
            instances_root: instances 根目录
        """
        self.instance_name = instance_name
        self.instance_path = instances_root / instance_path
        self.name = f"sub_claude_{instance_name}"

        # 从配置中读取描述
        try:
            from .config_manager import ConfigManager
            config_loader = ConfigManager(self.instance_path)
            config = config_loader.load_config()
            self._description = config.get("agent", {}).get("description", f"调用 {instance_name} 子实例")
        except Exception as e:
            logger.warning(f"加载子实例 {instance_name} 配置失败: {e}")
            self._description = f"调用 {instance_name} 子实例"

        # FastMCP 需要的属性（模拟函数对象）
        self.__name__ = self.name
        self.__doc__ = self._description

    async def __call__(
        self,
        task: str,
        context_files: Optional[List[str]] = None,
        output_format: str = "text",
        resume_session_id: Optional[str] = None,
        variables: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        调用子实例

        Args:
            task: 任务描述
            context_files: 相关文件列表
            output_format: 输出格式（text/json/markdown）
            resume_session_id: 要恢复的子会话 ID
            variables: 变量字典

        Returns:
            执行结果

        Note:
            parent_session_id 会自动从父实例的运行时上下文中获取，
            无需手动传递（通过临时文件实现进程间通信）
        """
        try:
            # 延迟导入避免循环依赖
            from .agent_system import AgentSystem

            # ✅ 自动从临时文件读取 parent_session_id
            parent_session_id = SessionContext.get_current_session()
            if parent_session_id:
                logger.info(f"[SubInstanceTool] Auto-detected parent session: {parent_session_id}")
            else:
                logger.warning(f"[SubInstanceTool] No parent session found in context")

            # 验证实例路径
            if not self.instance_path.exists():
                return {
                    "error": f"子实例路径不存在: {self.instance_path}",
                    "instance": self.instance_name
                }

            # 创建 AgentSystem
            # 🔥 传递父实例的 MessageBus 以实现实时消息传递
            from .session import MessageBus
            message_bus = MessageBus.from_config()
            connected = await message_bus.connect()
            logger.info(f"[SubInstanceTool] 子实例 {self.instance_name} MessageBus 连接状态: {connected}")

            agent = AgentSystem(str(self.instance_path), message_bus=message_bus)
            await agent.initialize()
            logger.info(f"[SubInstanceTool] 子实例 {self.instance_name} AgentSystem 初始化完成")

            try:
                # 构建提示词
                prompt_parts = [task]

                # 添加上下文文件
                if context_files:
                    file_info = "\n相关文件:\n"
                    for file_path in context_files:
                        file_info += f"- {file_path}\n"
                    prompt_parts.append(file_info)

                # 添加输出格式要求
                if output_format != "text":
                    prompt_parts.append(f"\n请以 {output_format} 格式输出结果。")

                # 添加变量
                if variables:
                    vars_info = "\n变量:\n"
                    for key, value in variables.items():
                        vars_info += f"- {key}: {value}\n"
                    prompt_parts.append(vars_info)

                # 组合提示词
                prompt = "\n".join(prompt_parts)

                # 执行查询（传递 parent_session_id）
                result = await agent.query_text(
                    prompt=prompt,
                    resume_session_id=resume_session_id,
                    parent_session_id=parent_session_id  # ✅ 传递父会话 ID
                )

                # 返回字典格式的结果
                output = result.result
                if result.session_id:
                    # 在结果末尾添加特殊标记
                    output += f"\n<!--SESSION_ID:{result.session_id}-->"

                # 返回字典格式（符合FastMCP期望）
                return {
                    "result": output,
                    "session_id": result.session_id,
                    "instance": self.instance_name
                }

            finally:
                # 清理资源
                agent.cleanup()
                await message_bus.close()

        except Exception as e:
            logger.error(f"子实例 {self.instance_name} 执行失败: {e}")
            # 返回字典格式的错误信息
            return {
                "error": str(e),
                "error_type": type(e).__name__,
                "instance": self.instance_name
            }


def create_sub_instance_tools(
    instances_config: Dict[str, str],
    instances_root: Path
) -> List[SubInstanceTool]:
    """
    创建所有子实例工具

    Args:
        instances_config: 子实例配置 {实例名: 相对路径}
        instances_root: instances 根目录

    Returns:
        子实例工具列表
    """
    tools = []

    for instance_name, relative_path in instances_config.items():
        try:
            # 验证实例路径
            instance_path = instances_root / relative_path
            if not instance_path.exists():
                logger.warning(f"子实例目录不存在: {instance_path}")
                continue

            # 创建子实例工具
            tool = SubInstanceTool(
                instance_name=instance_name,
                instance_path=Path(relative_path),
                instances_root=instances_root
            )
            tools.append(tool)

            logger.info(f"创建子实例工具: {tool.name}")

        except Exception as e:
            logger.error(f"创建子实例工具失败 {instance_name}: {e}")

    logger.info(f"共创建 {len(tools)} 个子实例工具")
    return tools