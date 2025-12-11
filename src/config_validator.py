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
