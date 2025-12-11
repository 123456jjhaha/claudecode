"""
Agent 系统主类

整合所有组件，提供统一的接口
"""

import os
from pathlib import Path
from typing import Any, AsyncIterator
from functools import wraps
from claude_agent_sdk import query, ClaudeAgentOptions

from .config_loader import AgentConfigLoader
from .tool_manager import ToolManager
from .instance_manager import InstanceManager
from .mcp_config_loader import load_mcp_config, merge_mcp_configs
from .error_handling import AgentSystemError
from .logging_config import get_logger

logger = get_logger(__name__)


def require_initialized(func):
    """装饰器：确保系统已初始化"""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self._initialized:
            raise AgentSystemError("系统未初始化，请先调用 initialize()")
        return func(self, *args, **kwargs)
    return wrapper


class AgentSystem:
    """Claude Agent 系统"""

    def __init__(
        self,
        instance_name: str,
        instances_root: Path | None = None
    ):
        """
        初始化 Agent 系统

        Args:
            instance_name: 实例名称或实例目录路径
            instances_root: 实例根目录（默认为当前目录下的 instances/）
        Raises:
            AgentSystemError: 初始化失败
        """

        # 实例目录
        if Path(instance_name).exists():
            # 如果是目录路径，直接使用
            self.instance_path = Path(instance_name)
        else:
            # 否则，从 instances_root 中查找
            if instances_root is None:
                instances_root = Path.cwd() / "instances"

            self.instance_path = Path(instances_root) / instance_name

        if not self.instance_path.exists():
            raise AgentSystemError(f"实例目录不存在: {self.instance_path}")

        self.instances_root = self.instance_path.parent

        logger.info(f"初始化 Agent 系统: {self.instance_path}")

        # 组件
        self.config_loader: AgentConfigLoader | None = None
        self.tool_manager: ToolManager | None = None
        self.instance_manager: InstanceManager | None = None

        # 配置和选项
        self._config: dict | None = None
        self._options: ClaudeAgentOptions | None = None

        # 初始化状态
        self._initialized = False

    async def initialize(self) -> None:
        """
        初始化系统（加载配置、工具和子实例）

        Raises:
            AgentSystemError: 初始化失败
        """
        if self._initialized:
            logger.warning("系统已初始化，跳过")
            return

        logger.info("开始初始化系统")

        try:
            # 1. 加载配置
            logger.info("加载配置...")
            self.config_loader = AgentConfigLoader(self.instance_path)
            self._config = self.config_loader.load()
            options_dict = self.config_loader.get_claude_options_dict()

            # 2. 加载工具
            logger.info("加载工具...")
            self.tool_manager = ToolManager(self.instance_path)
            self.tool_manager.discover_tools()

            # 创建本地工具 MCP 服务器
            custom_tools_server = self.tool_manager.create_mcp_server()

            # 3. 加载子实例
            logger.info("加载子实例...")
            sub_instances_config = options_dict.get("_sub_instances_config", {})

            if sub_instances_config:
                self.instance_manager = InstanceManager(
                    instances_config=sub_instances_config,
                    instances_root=self.instances_root
                )
                self.instance_manager.load_instances()

                # 创建子实例 MCP 服务器
                sub_instances_server = self.instance_manager.create_mcp_server()
            else:
                sub_instances_server = None

            # 4. 加载和合并 MCP 服务器配置
            logger.info("配置 MCP 服务器...")

            # 4.1 读取 .mcp.json 文件中的外部 MCP 服务器配置
            external_mcp_servers = load_mcp_config(self.instance_path)

            # 4.2 准备 SDK 服务器配置（本地工具和子实例）
            sdk_mcp_servers = {}
            if custom_tools_server is not None:
                sdk_mcp_servers["custom_tools"] = custom_tools_server
            if sub_instances_server is not None:
                sdk_mcp_servers["sub_instances"] = sub_instances_server

            # 4.3 合并所有 MCP 服务器配置
            # 注意：SDK 服务器优先级更高，防止被 .mcp.json 中的同名配置覆盖
            all_mcp_servers = merge_mcp_configs(sdk_mcp_servers, external_mcp_servers)

            # 5. 展开工具权限配置中的通配符
            logger.info("处理工具权限配置...")
            all_mcp_tool_names = self._collect_all_mcp_tool_names(
                custom_tools_server,
                sub_instances_server
            )
            self._expand_tool_permissions(options_dict, all_mcp_tool_names)

            # 6. 生成最终的 ClaudeAgentOptions
            logger.info("生成 ClaudeAgentOptions...")

            # 移除内部使用的自定义字段
            options_dict.pop("_sub_instances_config", None)

            # 设置完整的 MCP 服务器配置
            if all_mcp_servers:
                options_dict["mcp_servers"] = all_mcp_servers
                logger.info(f"配置了 {len(all_mcp_servers)} 个 MCP 服务器")
            else:
                logger.info("未配置 MCP 服务器")

            self._options = ClaudeAgentOptions(**options_dict)

            self._initialized = True
            logger.info("系统初始化完成")

        except Exception as e:
            if isinstance(e, AgentSystemError):
                raise
            raise AgentSystemError(f"初始化失败: {e}")

    def _collect_all_mcp_tool_names(
        self,
        custom_tools_server: Any,
        sub_instances_server: Any
    ) -> list[str]:
        """
        收集所有 MCP 工具的完整名称

        Args:
            custom_tools_server: 本地工具 MCP 服务器
            sub_instances_server: 子实例 MCP 服务器

        Returns:
            所有 MCP 工具名称列表
        """
        from fnmatch import fnmatch

        all_tool_names = []

        # 1. 收集本地自定义工具
        if custom_tools_server is not None and self.tool_manager:
            local_tool_names = self.tool_manager.get_tool_names()
            for tool_name in local_tool_names:
                full_name = f"mcp__custom_tools__{tool_name}"
                all_tool_names.append(full_name)
            logger.debug(f"收集到 {len(local_tool_names)} 个本地工具")

        # 2. 收集子实例工具
        if sub_instances_server is not None and self.instance_manager:
            sub_tool_names = self.instance_manager.get_tool_names()
            for tool_name in sub_tool_names:
                full_name = f"mcp__sub_instances__{tool_name}"
                all_tool_names.append(full_name)
            logger.debug(f"收集到 {len(sub_tool_names)} 个子实例工具")

        # TODO: 3. 收集外部 MCP 服务器的工具（如果需要的话）
        # 外部 MCP 服务器的工具名需要在运行时从服务器获取，
        # 这里暂时不处理，可以在后续版本中添加

        logger.info(f"总共收集到 {len(all_tool_names)} 个 MCP 工具")
        return all_tool_names

    def _expand_tool_permissions(
        self,
        options_dict: dict[str, Any],
        all_mcp_tool_names: list[str]
    ) -> None:
        """
        展开工具权限配置中的通配符模式

        Args:
            options_dict: ClaudeAgentOptions 配置字典
            all_mcp_tool_names: 所有 MCP 工具名称列表
        """
        from fnmatch import fnmatch

        # 展开 allowed_tools
        if "allowed_tools" in options_dict:
            allowed_patterns = options_dict["allowed_tools"]
            expanded_allowed = []

            for pattern in allowed_patterns:
                if "*" in pattern or "?" in pattern:
                    # 通配符模式，需要展开
                    matched = [name for name in all_mcp_tool_names if fnmatch(name, pattern)]
                    expanded_allowed.extend(matched)
                    logger.debug(f"通配符 '{pattern}' 匹配到 {len(matched)} 个工具")
                else:
                    # 具体工具名，直接添加
                    expanded_allowed.append(pattern)

            options_dict["allowed_tools"] = expanded_allowed
            logger.info(f"展开后的 allowed_tools 包含 {len(expanded_allowed)} 个工具")

        # 展开 disallowed_tools（如果需要的话）
        if "disallowed_tools" in options_dict:
            disallowed_patterns = options_dict["disallowed_tools"]
            expanded_disallowed = []

            for pattern in disallowed_patterns:
                if "*" in pattern or "?" in pattern:
                    # 通配符模式，需要展开
                    matched = [name for name in all_mcp_tool_names if fnmatch(name, pattern)]
                    expanded_disallowed.extend(matched)
                    logger.debug(f"通配符 '{pattern}' 匹配到 {len(matched)} 个工具")
                else:
                    # 具体工具名，直接添加
                    expanded_disallowed.append(pattern)

            options_dict["disallowed_tools"] = expanded_disallowed
            logger.info(f"展开后的 disallowed_tools 包含 {len(expanded_disallowed)} 个工具")

    async def query(self, prompt: str) -> AsyncIterator[Any]:
        """
        执行查询

        Args:
            prompt: 查询提示词

        Yields:
            查询响应消息

        Raises:
            AgentSystemError: 查询失败
        """
        if not self._initialized:
            await self.initialize()

        logger.info(f"执行查询...")
        logger.debug(f"提示词: {prompt}")

        try:
            # 修复：使用异步生成器提示词而不是字符串提示词
            # 这是为了解决 Claude Agent SDK 的一个已知 bug (Issue #266, #386)
            # 当使用 SDK MCP 服务器时，字符串提示词会导致 ProcessTransport 错误
            async def prompt_generator():
                yield {"type": "user", "message": {"role": "user", "content": prompt}}

            async for message in query(prompt=prompt_generator(), options=self._options):
                yield message

        except Exception as e:
            raise AgentSystemError(f"查询失败: {e}")

    async def query_text(self, prompt: str) -> str:
        """
        执行查询并返回文本响应

        Args:
            prompt: 查询提示词

        Returns:
            文本响应

        Raises:
            AgentSystemError: 查询失败
        """
        result_text = ""

        async for message in self.query(prompt):
            if hasattr(message, "text"):
                result_text += message.text

        return result_text

    @property
    @require_initialized
    def config(self) -> dict:
        """获取配置"""
        return self._config

    @property
    @require_initialized
    def options(self) -> ClaudeAgentOptions:
        """获取 ClaudeAgentOptions"""
        return self._options

    @property
    @require_initialized
    def agent_name(self) -> str:
        """获取 agent 名称"""
        return self._config["agent"]["name"]

    @property
    @require_initialized
    def agent_description(self) -> str | None:
        """获取 agent 描述"""
        return self._config["agent"].get("description")

    @property
    def tools_count(self) -> int:
        """获取工具数量"""
        if self.tool_manager is None:
            return 0
        return self.tool_manager.tools_count

    @property
    def instances_count(self) -> int:
        """获取子实例数量"""
        if self.instance_manager is None:
            return 0
        return self.instance_manager.instance_count

    def __repr__(self) -> str:
        """字符串表示"""
        if self._initialized:
            return (
                f"AgentSystem(name='{self.agent_name}', "
                f"tools={self.tools_count}, "
                f"instances={self.instances_count})"
            )
        else:
            return f"AgentSystem(path='{self.instance_path}', initialized=False)"
