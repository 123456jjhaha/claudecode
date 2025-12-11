"""
配置加载模块

负责读取、解析和转换 config.yaml 配置文件
"""

import os
import re
import yaml
from pathlib import Path
from typing import Any
from functools import wraps
from dotenv import load_dotenv

from .error_handling import ConfigError, PathResolutionError
from .config_validator import ConfigValidator
from .logging_config import get_logger

logger = get_logger(__name__)


def require_config_loaded(func):
    """装饰器：确保配置已加载"""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if self._config is None:
            raise ConfigError("配置未加载，请先调用 load()")
        return func(self, *args, **kwargs)
    return wrapper


class AgentConfigLoader:
    """Agent 配置加载器"""

    def __init__(self, instance_path: Path | str):
        """
        初始化配置加载器

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

    def load(self) -> dict[str, Any]:
        """
        加载配置文件

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
            ConfigValidator.validate(config)

            self._config = config
            logger.info("配置加载成功")
            return config

        except yaml.YAMLError as e:
            raise ConfigError(f"YAML 解析错误: {e}", str(self.config_file))
        except Exception as e:
            if isinstance(e, ConfigError):
                raise
            raise ConfigError(f"配置加载失败: {e}", str(self.config_file))

    def resolve_path(self, path: str) -> Path:
        """
        解析路径（相对路径或绝对路径）

        Args:
            path: 路径字符串

        Returns:
            解析后的绝对路径

        Raises:
            PathResolutionError: 路径解析失败
        """
        if not path:
            raise PathResolutionError("路径为空")

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
            if "system_prompt_file" in self._config:
                prompt_file = self._config["system_prompt_file"]
                options["system_prompt"] = self.load_prompt_file(prompt_file)

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

            logger.debug("成功生成 ClaudeAgentOptions 参数")
            return options

        except Exception as e:
            if isinstance(e, ConfigError):
                raise
            raise ConfigError(f"转换配置失败: {e}")

    def _replace_env_vars(self, obj: Any) -> Any:
        """
        递归替换配置中的环境变量

        Args:
            obj: 配置对象（可以是 dict、list、str 等）

        Returns:
            替换后的对象
        """
        if isinstance(obj, dict):
            return {k: self._replace_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._replace_env_vars(item) for item in obj]
        elif isinstance(obj, str):
            return self._replace_env_var_in_string(obj)
        else:
            return obj

    def _replace_env_var_in_string(self, text: str) -> str:
        """
        替换字符串中的环境变量

        仅支持 ${VAR_NAME} 格式，这是最安全和明确的方式
        （不支持 $VAR_NAME 格式以避免意外替换）

        Args:
            text: 原始字符串

        Returns:
            替换后的字符串
        """
        # 仅替换 ${VAR_NAME} 格式
        pattern = r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}'
        text = re.sub(
            pattern,
            lambda m: os.environ.get(m.group(1), m.group(0)),
            text
        )
        return text

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
