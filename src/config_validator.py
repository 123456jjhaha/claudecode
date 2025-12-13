"""
配置验证模块

验证 config.yaml 文件的结构和内容
"""

from typing import Any
from .error_handling import ConfigValidationError
from .logging_config import get_logger

logger = get_logger(__name__)


class ConfigValidator:
    """配置验证器"""

    # 必需的顶级字段
    REQUIRED_FIELDS = {
        "agent": dict,
        "model": str,
    }

    # 可选的顶级字段及其类型
    OPTIONAL_FIELDS = {
        "system_prompt_file": str,
        "cwd": str,
        "tools": dict,
        "sub_claude_instances": dict,
        "advanced": dict,
        "session_recording": dict,
    }

    # agent 子字段
    AGENT_FIELDS = {
        "name": (str, True),  # (类型, 是否必需)
        "description": (str, False),
    }

    # tools 子字段
    TOOLS_FIELDS = {
        "allowed": (list, False),
        "disallowed": (list, False),
    }

    # advanced 子字段
    ADVANCED_FIELDS = {
        "permission_mode": (str, False),
        "max_turns": (int, False),
        "setting_sources": (list, False),
        "env": (dict, False),
        "add_dirs": (list, False),
    }

    # session_recording 子字段
    SESSION_RECORDING_FIELDS = {
        "enabled": (bool, False),
        "retention_days": (int, False),
        "max_total_size_mb": (int, False),
        "auto_cleanup": (bool, False),
        "message_types": (list, False),
        "include_content": (bool, False),
        "include_metadata": (bool, False),
    }

    @classmethod
    def validate(cls, config: dict[str, Any]) -> None:
        """
        验证配置字典

        Args:
            config: 配置字典

        Raises:
            ConfigValidationError: 配置验证失败
        """
        logger.debug("开始验证配置")

        # 验证必需字段
        cls._validate_required_fields(config)

        # 验证字段类型
        cls._validate_field_types(config)

        # 验证 agent 子字段
        if "agent" in config:
            cls._validate_agent(config["agent"])

        # 验证 tools 子字段
        if "tools" in config:
            cls._validate_tools(config["tools"])

        # 验证 advanced 子字段
        if "advanced" in config:
            cls._validate_advanced(config["advanced"])

        # 验证子实例配置
        if "sub_claude_instances" in config:
            cls._validate_sub_instances(config["sub_claude_instances"])

        # 验证会话记录配置
        if "session_recording" in config:
            cls._validate_session_recording(config["session_recording"])

        # 检查提示词文件名建议
        if "system_prompt_file" in config:
            cls._check_prompt_file_name(config["system_prompt_file"])

        logger.debug("配置验证通过")

    @classmethod
    def _validate_required_fields(cls, config: dict[str, Any]) -> None:
        """验证必需字段"""
        for field, expected_type in cls.REQUIRED_FIELDS.items():
            if field not in config:
                raise ConfigValidationError(f"缺少必需字段", field=field)

    @classmethod
    def _validate_field_types(cls, config: dict[str, Any]) -> None:
        """验证字段类型"""
        all_fields = {**cls.REQUIRED_FIELDS, **cls.OPTIONAL_FIELDS}

        for field, value in config.items():
            if field in all_fields:
                expected_type = all_fields[field]
                if not isinstance(value, expected_type):
                    raise ConfigValidationError(
                        f"类型错误，期望 {expected_type.__name__}，实际为 {type(value).__name__}",
                        field=field
                    )

    @classmethod
    def _validate_agent(cls, agent_config: dict[str, Any]) -> None:
        """验证 agent 配置"""
        for field, (expected_type, required) in cls.AGENT_FIELDS.items():
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

    @classmethod
    def _validate_tools(cls, tools_config: dict[str, Any]) -> None:
        """验证 tools 配置"""
        for field, (expected_type, _) in cls.TOOLS_FIELDS.items():
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

    @classmethod
    def _validate_advanced(cls, advanced_config: dict[str, Any]) -> None:
        """验证 advanced 配置"""
        for field, (expected_type, _) in cls.ADVANCED_FIELDS.items():
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

    @classmethod
    def _validate_sub_instances(cls, instances_config: dict[str, Any]) -> None:
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

    @classmethod
    def _validate_session_recording(cls, recording_config: dict[str, Any]) -> None:
        """验证会话记录配置"""
        if not isinstance(recording_config, dict):
            raise ConfigValidationError(
                "会话记录配置必须是字典",
                field="session_recording"
            )

        for field, (expected_type, _) in cls.SESSION_RECORDING_FIELDS.items():
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

    @classmethod
    def _check_prompt_file_name(cls, prompt_file: str) -> None:
        """
        检查提示词文件名并提供建议

        Args:
            prompt_file: 提示词文件路径
        """
        import os
        filename = os.path.basename(prompt_file).lower()

        # 检查是否使用了可能与 Claude Code 冲突的文件名
        if filename == "claude.md":
            logger.warning(
                f"警告: 使用 'CLAUDE.md' 作为系统提示词文件可能会与 Claude Code 的项目配置冲突。\n"
                f"建议使用以下文件名之一:\n"
                f"  - agent.md (推荐)\n"
                f"  - system_prompt.md\n"
                f"  - agent_prompt.md\n"
                f"  - prompt.md\n\n"
                f"如果您确实想使用当前文件名，请确保这是您的本意。"
            )

        # 推荐的文件名
        recommended_names = ["agent.md", "system_prompt.md", "agent_prompt.md", "prompt.md"]
        if filename not in recommended_names and filename != "claude.md":
            logger.info(
                f"提示: 为了避免潜在的文件名冲突，建议使用以下标准文件名之一:\n"
                f"  - agent.md (推荐)\n"
                f"  - system_prompt.md\n"
                f"  - agent_prompt.md\n"
                f"  - prompt.md"
            )
