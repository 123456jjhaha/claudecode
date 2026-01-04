"""
工具管理模块

负责发现、加载和管理工具，包括：
- 本地自定义工具（tools/ 目录）
- 子实例工具
"""

import sys
import importlib
import importlib.util
import inspect
from pathlib import Path
from typing import Any, Dict, Optional, List

from .error_handling import ToolError
from .logging_config import get_logger
from .mcp_server.process_manager import ProcessManagerRegistry
from .mcp_server.tool_loader import SimpleToolLoader, load_tools_from_instance

logger = get_logger(__name__)


class ToolManager:
    """工具管理器"""

    def __init__(self, instance_path: Path):
        """
        初始化工具管理器

        Args:
            instance_path: 实例目录路径
        """
        self.instance_path = Path(instance_path)
        self.tools_dir = self.instance_path / "tools"

        # MCP 服务器进程管理器
        self._process_manager = None
        self._server_config: Optional[Dict[str, Any]] = None

        # 工具名称缓存
        self._tool_names: list[str] = []

    def discover_tools(self) -> List[str]:
        """
        发现所有工具名称

        Returns:
            工具名称列表
        """
        if not self.tools_dir.exists():
            logger.info(f"工具目录不存在: {self.tools_dir}")
            self._tool_names = []
            return []

        logger.info(f"检查工具目录: {self.tools_dir}")

        try:
            # 加载本地工具
            _, local_tool_names = load_tools_from_instance(self.instance_path)
            self._tool_names = local_tool_names

            # TODO: 如果需要，也可以在这里添加其他类型的工具
            logger.info(f"发现 {len(self._tool_names)} 个工具")

            return self._tool_names

        except Exception as e:
            logger.error(f"工具发现失败: {e}")
            return []

    def start_mcp_server(self, server_name: str = "custom_tools") -> Dict[str, Any]:
        """
        启动 MCP 服务器子进程

        Args:
            server_name: 服务器名称（用于日志）

        Returns:
            MCP 服务器配置（stdio 格式）

        Raises:
            ToolError: MCP 服务器启动失败
        """
        if self._process_manager is not None and self._process_manager.is_running():
            logger.debug("MCP 服务器已经运行")
            return self._server_config

        try:
            logger.info(f"启动 {server_name} MCP 服务器")

            # 获取进程管理器
            self._process_manager = ProcessManagerRegistry.get_manager(self.instance_path)

            # 启动服务器
            self._server_config = self._process_manager.start_server()

            logger.info(f"{server_name} MCP 服务器启动成功")
            return self._server_config

        except Exception as e:
            logger.error(f"启动 {server_name} MCP 服务器失败: {e}")
            raise ToolError(f"启动 MCP 服务器失败: {e}")

    def stop_mcp_server(self):
        """停止 MCP 服务器子进程"""
        if self._process_manager is not None:
            try:
                self._process_manager.shutdown()
                logger.info("MCP 服务器已停止")
            except Exception as e:
                logger.error(f"停止 MCP 服务器失败: {e}")
            finally:
                self._process_manager = None
                self._server_config = None

    def get_mcp_server_config(self) -> Optional[Dict[str, Any]]:
        """
        获取 MCP 服务器配置

        Returns:
            MCP 服务器配置（stdio 格式）
        """
        return self._server_config.copy() if self._server_config else None

    def is_server_running(self) -> bool:
        """
        检查 MCP 服务器是否运行中

        Returns:
            True 如果服务器运行中
        """
        return self._process_manager is not None and self._process_manager.is_running()

    def get_tool_names(self) -> List[str]:
        """
        获取所有工具名称列表

        Returns:
            工具名称列表
        """
        return self._tool_names.copy()

    def filter_tools(self, allowed: List[str] | None = None, disallowed: List[str] | None = None) -> List[str]:
        """
        根据 allowed/disallowed 规则过滤工具

        Args:
            allowed: 允许的工具列表（支持通配符）
            disallowed: 禁止的工具列表（支持通配符）

        Returns:
            过滤后的工具名称列表（包含 mcp__custom_tools__ 前缀）
        """
        # 添加 MCP 前缀
        tool_names = [f"mcp__custom_tools__{name}" for name in self._tool_names]

        if allowed is None and disallowed is None:
            return tool_names

        from fnmatch import fnmatch
        filtered = []

        for tool_name in tool_names:
            # 检查是否在禁止列表中
            if disallowed and any(fnmatch(tool_name, pattern) for pattern in disallowed):
                logger.debug(f"工具 {tool_name} 在禁止列表中，已过滤")
                continue

            # 如果有允许列表，检查是否在允许列表中
            if allowed:
                if any(fnmatch(tool_name, pattern) for pattern in allowed):
                    filtered.append(tool_name)
                else:
                    logger.debug(f"工具 {tool_name} 不在允许列表中，已过滤")
            else:
                # 没有允许列表，默认允许（除非在禁止列表中）
                filtered.append(tool_name)

        return filtered

    def collect_all_mcp_tool_names(self, sub_instance_tools: Optional[list] = None) -> List[str]:
        """
        收集所有 MCP 工具的完整名称

        Args:
            sub_instance_tools: 子实例工具列表

        Returns:
            所有 MCP 工具名称列表
        """
        all_tool_names = []

        # 1. 收集本地自定义工具
        local_tool_names = self.get_tool_names()
        for tool_name in local_tool_names:
            full_name = f"mcp__custom_tools__{tool_name}"
            all_tool_names.append(full_name)
        logger.debug(f"收集到 {len(local_tool_names)} 个本地工具")

        # 2. 收集子实例工具（现在是主 MCP 服务器的一部分）
        if sub_instance_tools:
            for tool in sub_instance_tools:
                full_name = f"mcp__custom_tools__{tool.name}"
                all_tool_names.append(full_name)
            logger.debug(f"收集到 {len(sub_instance_tools)} 个子实例工具")

        logger.info(f"总共收集到 {len(all_tool_names)} 个 MCP 工具")
        return all_tool_names

    def expand_tool_permissions(
        self,
        options_dict: Dict[str, Any],
        all_mcp_tool_names: List[str]
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

        # 展开 disallowed_tools
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

    @property
    def tools_count(self) -> int:
        """获取工具数量"""
        return len(self._tool_names)