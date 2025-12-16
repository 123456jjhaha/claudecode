"""
配置管理模块

统一管理所有配置相关功能，包括：
- 加载和解析 config.yaml 配置文件
- 配置验证
- 加载和解析 .mcp.json 文件
- 环境变量替换
- 路径解析
"""

import os
import re
import yaml
import json
from pathlib import Path
from typing import Any
from functools import wraps
from dotenv import load_dotenv

from .error_handling import ConfigError, ConfigValidationError
from .logging_config import get_logger

logger = get_logger(__name__)


def require_config_loaded(func):
    """装饰器：确保配置已加载"""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if self._config is None:
            raise ConfigError("配置未加载，请先调用 load_config()")
        return func(self, *args, **kwargs)
    return wrapper


class ConfigManager:
    """统一的配置管理器"""

    # 类级别的配置定义（减少重复）
    REQUIRED_FIELDS = {
        "agent": dict,
        "model": str,
    }

    OPTIONAL_FIELDS = {
        "system_prompt_file": str,
        "cwd": str,
        "tools": dict,
        "sub_claude_instances": dict,
        "advanced": dict,
        "session_recording": dict,
    }

    # 子字段验证规则
    AGENT_FIELDS = {
        "name": (str, True),  # (类型, 是否必需)
        "description": (str, False),
    }

    TOOLS_FIELDS = {
        "allowed": (list, False),
        "disallowed": (list, False),
    }

    ADVANCED_FIELDS = {
        "permission_mode": (str, False),
        "max_turns": (int, False),
        "setting_sources": (list, False),
        "env": (dict, False),
        "add_dirs": (list, False),
    }

    SESSION_RECORDING_FIELDS = {
        "enabled": (bool, False),
        "retention_days": (int, False),
        "max_total_size_mb": (int, False),
        "auto_cleanup": (bool, False),
        "message_types": (list, False),
        "include_content": (bool, False),
        "include_metadata": (bool, False),
    }

    def __init__(self, instance_path: Path | str):
        """
        初始化配置管理器

        Args:
            instance_path: 实例目录路径
        """
        self.instance_path = Path(instance_path)
        if not self.instance_path.exists():
            raise ConfigError(f"实例目录不存在: {self.instance_path}")

        self.config_file = self.instance_path / "config.yaml"
        if not self.config_file.exists():
            raise ConfigError(f"配置文件不存在: {self.config_file}")

        # 加载 .env 文件（如果存在）
        env_file = self.instance_path / ".env"
        if env_file.exists():
            load_dotenv(env_file)

        self._config: dict[str, Any] | None = None
        self._mcp_config: dict[str, dict[str, Any]] | None = None

    def load_config(self) -> dict[str, Any]:
        """
        加载主配置文件

        Returns:
            配置字典

        Raises:
            ConfigError: 配置加载失败
        """
        logger.info(f"加载配置文件: {self.config_file}")

        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)

            if config is None:
                raise ConfigError("配置文件为空", str(self.config_file))

            # 替换环境变量
            config = self._replace_env_vars(config)

            # 验证配置
            self.validate_config(config)

            self._config = config
            logger.info("配置加载成功")
            return config

        except yaml.YAMLError as e:
            raise ConfigError(f"YAML 解析错误: {e}", str(self.config_file))
        except Exception as e:
            if isinstance(e, (ConfigError, ConfigValidationError)):
                raise
            raise ConfigError(f"配置加载失败: {e}", str(self.config_file))

    def load_mcp_config(self) -> dict[str, dict[str, Any]]:
        """
        加载 MCP 服务器配置

        Returns:
            MCP 服务器配置字典
        """
        mcp_file = self.instance_path / ".mcp.json"

        if not mcp_file.exists():
            logger.debug(f"未找到 .mcp.json 文件: {mcp_file}")
            self._mcp_config = {}
            return {}

        try:
            logger.info(f"加载 MCP 配置文件: {mcp_file}")

            with open(mcp_file, "r", encoding="utf-8") as f:
                content = f.read()

            # 解析 JSON
            data = json.loads(content)

            # 标准格式：{ "mcpServers": { "server_name": {...} } }
            if "mcpServers" not in data:
                logger.warning(f".mcp.json 格式错误：缺少 'mcpServers' 字段")
                self._mcp_config = {}
                return {}

            mcp_servers = data["mcpServers"]

            if not isinstance(mcp_servers, dict):
                logger.warning(f".mcp.json 格式错误：'mcpServers' 必须是字典")
                self._mcp_config = {}
                return {}

            # 验证和标准化配置
            validated_servers = {}
            for server_name, server_config in mcp_servers.items():
                if not isinstance(server_config, dict):
                    logger.warning(f"跳过无效的服务器配置: {server_name}")
                    continue

                # 获取服务器类型，默认为 stdio（向后兼容）
                server_type = server_config.get("type", "stdio")

                # 验证配置完整性
                if not self._validate_server_config(server_name, server_type, server_config):
                    logger.warning(f"跳过无效的服务器配置: {server_name}")
                    continue

                # 健康检查：过滤掉明显会失败的配置
                if server_type == 'stdio':
                    command = server_config.get('command', '')

                    # 跳过示例/测试配置（避免污染 MCP 系统）
                    if command.lower() in ['echo', 'test', 'example', 'demo']:
                        logger.warning(
                            f"跳过示例 MCP 服务器配置: {server_name} "
                            f"(command={command})"
                        )
                        continue

                # 通过所有检查，添加到 validated_servers
                validated_servers[server_name] = server_config
                logger.debug(f"加载 MCP 服务器: {server_name} (type={server_type})")

            logger.info(f"成功加载 {len(validated_servers)} 个 MCP 服务器")
            self._mcp_config = validated_servers
            return validated_servers

        except json.JSONDecodeError as e:
            logger.error(f"解析 .mcp.json 失败: {e}")
            self._mcp_config = {}
            return {}
        except Exception as e:
            logger.error(f"加载 .mcp.json 失败: {e}")
            self._mcp_config = {}
            return {}

    def validate_config(self, config: dict[str, Any]) -> None:
        """
        验证配置字典

        Args:
            config: 配置字典

        Raises:
            ConfigValidationError: 配置验证失败
        """
        logger.debug("开始验证配置")

        # 验证必需字段
        for field, expected_type in self.REQUIRED_FIELDS.items():
            if field not in config:
                raise ConfigValidationError(f"缺少必需字段", field=field)

        # 验证字段类型
        all_fields = {**self.REQUIRED_FIELDS, **self.OPTIONAL_FIELDS}
        for field, value in config.items():
            if field in all_fields:
                expected_type = all_fields[field]
                if not isinstance(value, expected_type):
                    raise ConfigValidationError(
                        f"类型错误，期望 {expected_type.__name__}，实际为 {type(value).__name__}",
                        field=field
                    )

        # 验证子字段
        if "agent" in config:
            self._validate_agent(config["agent"])

        if "tools" in config:
            self._validate_tools(config["tools"])

        if "advanced" in config:
            self._validate_advanced(config["advanced"])

        if "sub_claude_instances" in config:
            self._validate_sub_instances(config["sub_claude_instances"])

        if "session_recording" in config:
            self._validate_session_recording(config["session_recording"])

        # 检查提示词文件名建议
        if "system_prompt_file" in config:
            self._check_prompt_file_name(config["system_prompt_file"])

        logger.debug("配置验证通过")

    def resolve_path(self, path: str) -> Path:
        """
        解析路径（相对路径或绝对路径）

        Args:
            path: 路径字符串

        Returns:
            解析后的绝对路径

        Raises:
            ConfigError: 路径解析失败
        """
        if not path:
            raise ConfigError("路径为空")

        # 展开用户目录符号 ~
        path = os.path.expanduser(path)

        # 如果是绝对路径，直接返回
        if os.path.isabs(path):
            return Path(path)

        # 相对于实例目录的路径
        resolved = (self.instance_path / path).resolve()
        return resolved

    def load_prompt_file(self, file_path: str) -> str:
        """
        加载提示词文件

        Args:
            file_path: 提示词文件路径

        Returns:
            提示词内容

        Raises:
            ConfigError: 文件加载失败
        """
        try:
            resolved_path = self.resolve_path(file_path)

            if not resolved_path.exists():
                raise ConfigError(f"提示词文件不存在: {resolved_path}")

            with open(resolved_path, "r", encoding="utf-8") as f:
                content = f.read()

            logger.debug(f"成功加载提示词文件: {resolved_path}")
            return content

        except Exception as e:
            if isinstance(e, ConfigError):
                raise
            raise ConfigError(f"无法加载提示词文件 '{file_path}': {e}")

    @require_config_loaded
    def get_claude_options_dict(self) -> dict[str, Any]:
        """
        生成 ClaudeAgentOptions 参数字典

        Returns:
            ClaudeAgentOptions 参数字典

        Raises:
            ConfigError: 配置未加载或转换失败
        """
        try:
            options = {}

            # 基础配置
            options["model"] = self._config.get("model")

            # 系统提示词
            prompt_loaded = False
            prompt_file_names = [
                self._config.get("system_prompt_file"),
                "agent.md",
                "system_prompt.md",
                "agent_prompt.md",
            ]

            # 过滤掉 None 值
            prompt_file_names = [name for name in prompt_file_names if name]

            for prompt_file in prompt_file_names:
                if prompt_file:
                    try:
                        options["system_prompt"] = self.load_prompt_file(prompt_file)
                        prompt_loaded = True
                        logger.debug(f"成功加载系统提示词文件: {prompt_file}")
                        break
                    except Exception as e:
                        logger.debug(f"无法加载提示词文件 {prompt_file}: {e}")
                        continue

            # 如果没有找到任何提示词文件，使用默认提示词
            if not prompt_loaded:
                default_prompt = self._get_default_system_prompt()
                options["system_prompt"] = default_prompt
                logger.info("使用默认系统提示词")

            # 工作目录
            if "cwd" in self._config:
                options["cwd"] = str(self.resolve_path(self._config["cwd"]))
            else:
                options["cwd"] = str(self.instance_path)

            # 工具配置
            if "tools" in self._config:
                tools_config = self._config["tools"]
                if "allowed" in tools_config:
                    options["allowed_tools"] = tools_config["allowed"]
                if "disallowed" in tools_config:
                    options["disallowed_tools"] = tools_config["disallowed"]

            # 子实例配置
            if "sub_claude_instances" in self._config:
                options["_sub_instances_config"] = self._config["sub_claude_instances"]

            # 高级配置
            if "advanced" in self._config:
                advanced = self._config["advanced"]

                if "permission_mode" in advanced:
                    options["permission_mode"] = advanced["permission_mode"]

                if "max_turns" in advanced:
                    options["max_turns"] = advanced["max_turns"]

                if "setting_sources" in advanced:
                    options["setting_sources"] = advanced["setting_sources"]

                if "env" in advanced:
                    options["env"] = advanced["env"]

                if "add_dirs" in advanced:
                    options["add_dirs"] = [
                        str(self.resolve_path(d)) for d in advanced["add_dirs"]
                    ]

            # 会话记录配置（传递给 AgentSystem）
            if "session_recording" in self._config:
                options["_session_recording_config"] = self._config["session_recording"]

            logger.debug("成功生成 ClaudeAgentOptions 参数")
            return options

        except Exception as e:
            if isinstance(e, ConfigError):
                raise
            raise ConfigError(f"转换配置失败: {e}")

    # 属性访问器
    @property
    @require_config_loaded
    def config(self) -> dict[str, Any]:
        """获取已加载的配置"""
        return self._config

    @property
    @require_config_loaded
    def agent_name(self) -> str:
        """获取 agent 名称"""
        return self._config["agent"]["name"]

    @property
    @require_config_loaded
    def agent_description(self) -> str | None:
        """获取 agent 描述"""
        return self._config["agent"].get("description")

    @property
    def mcp_config(self) -> dict[str, dict[str, Any]]:
        """获取已加载的 MCP 配置"""
        if self._mcp_config is None:
            self.load_mcp_config()
        return self._mcp_config

    # 私有方法
    def _replace_env_vars(self, obj: Any) -> Any:
        """递归替换配置中的环境变量"""
        if isinstance(obj, dict):
            return {k: self._replace_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._replace_env_vars(item) for item in obj]
        elif isinstance(obj, str):
            return self._replace_env_var_in_string(obj)
        else:
            return obj

    def _replace_env_var_in_string(self, text: str) -> str:
        """替换字符串中的环境变量"""
        # 仅替换 ${VAR_NAME} 格式
        pattern = r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}'
        text = re.sub(
            pattern,
            lambda m: os.environ.get(m.group(1), m.group(0)),
            text
        )
        return text

    def _validate_agent(self, agent_config: dict[str, Any]) -> None:
        """验证 agent 配置"""
        for field, (expected_type, required) in self.AGENT_FIELDS.items():
            if required and field not in agent_config:
                raise ConfigValidationError(
                    f"缺少必需字段",
                    field=f"agent.{field}"
                )

            if field in agent_config:
                value = agent_config[field]
                if not isinstance(value, expected_type):
                    raise ConfigValidationError(
                        f"类型错误，期望 {expected_type.__name__}，实际为 {type(value).__name__}",
                        field=f"agent.{field}"
                    )

    def _validate_tools(self, tools_config: dict[str, Any]) -> None:
        """验证 tools 配置"""
        for field, (expected_type, _) in self.TOOLS_FIELDS.items():
            if field in tools_config:
                value = tools_config[field]
                if not isinstance(value, expected_type):
                    raise ConfigValidationError(
                        f"类型错误，期望 {expected_type.__name__}，实际为 {type(value).__name__}",
                        field=f"tools.{field}"
                    )

                # 验证列表元素都是字符串
                if isinstance(value, list):
                    for i, item in enumerate(value):
                        if not isinstance(item, str):
                            raise ConfigValidationError(
                                f"列表元素必须是字符串，实际为 {type(item).__name__}",
                                field=f"tools.{field}[{i}]"
                            )

    def _validate_advanced(self, advanced_config: dict[str, Any]) -> None:
        """验证 advanced 配置"""
        for field, (expected_type, _) in self.ADVANCED_FIELDS.items():
            if field in advanced_config:
                value = advanced_config[field]
                if not isinstance(value, expected_type):
                    raise ConfigValidationError(
                        f"类型错误，期望 {expected_type.__name__}，实际为 {type(value).__name__}",
                        field=f"advanced.{field}"
                    )

        # 验证 permission_mode 的值
        if "permission_mode" in advanced_config:
            valid_modes = ["default", "acceptEdits", "plan", "bypassPermissions"]
            if advanced_config["permission_mode"] not in valid_modes:
                raise ConfigValidationError(
                    f"无效的权限模式，有效值为: {', '.join(valid_modes)}",
                    field="advanced.permission_mode"
                )

    def _validate_sub_instances(self, instances_config: dict[str, Any]) -> None:
        """验证子实例配置"""
        if not isinstance(instances_config, dict):
            raise ConfigValidationError(
                "子实例配置必须是字典",
                field="sub_claude_instances"
            )

        for instance_name, instance_path in instances_config.items():
            if not isinstance(instance_path, str):
                raise ConfigValidationError(
                    f"子实例路径必须是字符串，实际为 {type(instance_path).__name__}",
                    field=f"sub_claude_instances.{instance_name}"
                )

    def _validate_session_recording(self, recording_config: dict[str, Any]) -> None:
        """验证会话记录配置"""
        if not isinstance(recording_config, dict):
            raise ConfigValidationError(
                "会话记录配置必须是字典",
                field="session_recording"
            )

        for field, (expected_type, _) in self.SESSION_RECORDING_FIELDS.items():
            if field in recording_config:
                value = recording_config[field]
                # message_types 可以为 None（记录所有类型）或 list
                if field == "message_types" and value is None:
                    continue
                if not isinstance(value, expected_type):
                    raise ConfigValidationError(
                        f"类型错误，期望 {expected_type.__name__}，实际为 {type(value).__name__}",
                        field=f"session_recording.{field}"
                    )

        # 验证特定字段的值范围
        if "retention_days" in recording_config and recording_config["retention_days"] < 1:
            raise ConfigValidationError(
                "retention_days 必须大于 0",
                field="session_recording.retention_days"
            )

        if "max_total_size_mb" in recording_config and recording_config["max_total_size_mb"] < 1:
            raise ConfigValidationError(
                "max_total_size_mb 必须大于 0",
                field="session_recording.max_total_size_mb"
            )

        # 验证消息类型列表（None 表示记录所有类型）
        if "message_types" in recording_config and recording_config["message_types"] is not None:
            valid_types = ["UserMessage", "AssistantMessage", "ResultMessage", "SystemMessage", "StreamEvent"]
            for msg_type in recording_config["message_types"]:
                if msg_type not in valid_types:
                    raise ConfigValidationError(
                        f"无效的消息类型: {msg_type}，有效值为: {', '.join(valid_types)} 或 None（记录所有类型）",
                        field="session_recording.message_types"
                    )

    def _validate_server_config(self, server_name: str, server_type: str, config: dict[str, Any]) -> bool:
        """验证 MCP 服务器配置的完整性"""
        # 验证类型
        valid_types = ["stdio", "http", "sse"]
        if server_type not in valid_types:
            logger.warning(
                f"服务器 '{server_name}' 的类型 '{server_type}' 无效，"
                f"有效类型: {', '.join(valid_types)}"
            )
            return False

        # 验证必需字段
        if server_type == "stdio":
            if "command" not in config:
                logger.warning(f"stdio 类型服务器 '{server_name}' 缺少 'command' 字段")
                return False
        elif server_type in ["http", "sse"]:
            if "url" not in config:
                logger.warning(f"{server_type} 类型服务器 '{server_name}' 缺少 'url' 字段")
                return False

        return True

    def _check_prompt_file_name(self, prompt_file: str) -> None:
        """检查提示词文件名并提供建议"""
        filename = os.path.basename(prompt_file).lower()

        # 检查是否使用了可能与 Claude Code 冲突的文件名
        if filename == "claude.md":
            logger.warning(
                f"警告: 使用 'CLAUDE.md' 作为系统提示词文件可能会与 Claude Code 的项目配置冲突。\n"
                f"建议使用以下文件名之一:\n"
                f"  - agent.md (推荐)\n"
                f"  - system_prompt.md\n"
                f"  - agent_prompt.md\n\n"
                f"如果您确实想使用当前文件名，请确保这是您的本意。"
            )

    def _get_default_system_prompt(self) -> str:
        """获取默认系统提示词"""
        return """# Claude Agent

你是一个基于 Claude Agent System 运行的 AI 助手。

## 你的能力

你可以使用以下工具：
- 文件操作（读取、写入、编辑）
- 代码执行（通过 Bash 命令）
- 文件搜索（Glob、Grep）
- 自定义工具（如果配置了）
- 子实例（如果配置了）

## 工作原则

1. **清晰沟通**：始终以清晰、准确的方式回答问题
2. **主动思考**：在执行任务前，先思考最佳方案
3. **谨慎操作**：在进行文件修改等操作时，先确认再执行
4. **完整响应**：确保完整回答用户的问题

## 特殊说明

- 你的对话会被自动记录，以便后续查询和分析
- 如果可以，优先使用并行执行提高效率
- 保持友好和专业的态度

请根据用户的需求，使用合适的工具来完成任务。"""


def merge_mcp_configs(
    sdk_servers: dict[str, Any],
    external_servers: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """
    合并 SDK 服务器和外部 MCP 服务器配置

    Args:
        sdk_servers: SDK 创建的服务器配置 (type="sdk")
        external_servers: 从 .mcp.json 加载的外部服务器配置

    Returns:
        合并后的服务器配置字典

    注意：
        如果有名称冲突，SDK 服务器优先（防止覆盖内部服务器）
    """
    merged = {}

    # 先添加外部服务器
    for name, config in external_servers.items():
        merged[name] = config
        logger.debug(f"添加外部 MCP 服务器: {name}")

    # 再添加 SDK 服务器（优先级更高）
    for name, config in sdk_servers.items():
        if name in merged:
            logger.warning(
                f"MCP 服务器名称冲突: '{name}' "
                f"（SDK 服务器将覆盖 .mcp.json 中的配置）"
            )
        merged[name] = config
        logger.debug(f"添加 SDK MCP 服务器: {name}")

    return merged


