"""
工具管理模块

负责发现、加载和管理工具，包括：
- 本地自定义工具（tools/ 目录）
- 外部 MCP 服务器
- 子 Claude 实例工具
"""

import sys
import importlib
import importlib.util
import inspect
from pathlib import Path
from typing import Any, Callable
from fnmatch import fnmatch

from .error_handling import ToolError, ToolDiscoveryError, ToolLoadError
from .logging_config import get_logger

logger = get_logger(__name__)

# 导入 SdkMcpTool 用于识别使用 @tool 装饰器定义的工具
try:
    from claude_agent_sdk import SdkMcpTool
except ImportError:
    SdkMcpTool = None
    logger.warning("无法导入 SdkMcpTool，工具发现功能将受限")


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

        # 存储发现的工具
        self._tools: list[Callable] = []
        self._tool_names: list[str] = []

    def discover_tools(self) -> list[Callable]:
        """
        发现 tools/ 目录下的所有工具函数

        Returns:
            工具函数列表

        Raises:
            ToolDiscoveryError: 工具发现失败
        """
        if not self.tools_dir.exists():
            logger.warning(f"工具目录不存在: {self.tools_dir}")
            return []

        logger.info(f"开始扫描工具目录: {self.tools_dir}")

        tools = []
        tool_names = []

        try:
            # 遍历 tools/ 目录下的所有 .py 文件
            for py_file in self.tools_dir.glob("*.py"):
                if py_file.name.startswith("_"):
                    continue  # 跳过私有文件（如 __init__.py）

                module_name = py_file.stem
                logger.debug(f"扫描模块: {module_name}")

                # 动态导入模块
                module = self._import_module(py_file, module_name)

                # 在模块中查找带 @tool 装饰器的函数
                module_tools = self._extract_tools_from_module(module, module_name)

                tools.extend(module_tools)
                tool_names.extend([self._get_tool_name(t, module_name) for t in module_tools])

            self._tools = tools
            self._tool_names = tool_names

            logger.info(f"发现 {len(tools)} 个工具: {', '.join(tool_names)}")
            return tools

        except Exception as e:
            raise ToolDiscoveryError(f"工具发现失败: {e}")

    def _import_module(self, py_file: Path, module_name: str) -> Any:
        """
        动态导入 Python 模块

        Args:
            py_file: Python 文件路径
            module_name: 模块名

        Returns:
            导入的模块对象

        Raises:
            ToolLoadError: 模块导入失败
        """
        try:
            spec = importlib.util.spec_from_file_location(module_name, py_file)
            if spec is None or spec.loader is None:
                raise ToolLoadError(f"无法加载模块规范: {py_file}")

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            return module

        except Exception as e:
            raise ToolLoadError(f"模块导入失败: {e}", tool_name=module_name)

    def _extract_tools_from_module(self, module: Any, module_name: str) -> list[Callable]:
        """
        从模块中提取使用 @tool 装饰器定义的工具

        Args:
            module: Python 模块对象
            module_name: 模块名

        Returns:
            工具对象列表 (SdkMcpTool 实例)
        """
        tools = []

        for name, obj in inspect.getmembers(module):
            # 检查是否是 SdkMcpTool 实例（由 @tool 装饰器创建）
            if SdkMcpTool is not None and isinstance(obj, SdkMcpTool):
                logger.debug(f"发现工具: {module_name}.{name} (工具名: {obj.name})")
                tools.append(obj)

        return tools

    def _get_tool_name(self, tool_obj: Any, module_name: str) -> str:
        """
        获取工具的完整名称（模块名__函数名）

        Args:
            tool_obj: 工具对象 (SdkMcpTool 实例)
            module_name: 模块名

        Returns:
            工具名称（格式：module__tool_name）
        """
        # 从 SdkMcpTool 实例中获取工具名称
        if SdkMcpTool is not None and isinstance(tool_obj, SdkMcpTool):
            tool_name = tool_obj.name
        else:
            # 兼容：如果不是 SdkMcpTool，尝试获取 __name__ 属性
            tool_name = getattr(tool_obj, "__name__", "unknown")

        return f"{module_name}__{tool_name}"

    def create_mcp_server(self, server_name: str = "custom_tools"):
        """
        创建本地工具的 MCP SDK 服务器

        Args:
            server_name: 服务器名称

        Returns:
            McpSdkServerConfig 对象（如果有工具的话）

        Raises:
            ToolError: MCP 服务器创建失败
        """
        if not self._tools:
            logger.debug("没有发现本地工具，跳过创建 MCP 服务器")
            return None

        try:
            from claude_agent_sdk import create_sdk_mcp_server

            logger.info(f"创建本地工具 MCP 服务器: {server_name}")

            mcp_server = create_sdk_mcp_server(
                name=server_name,
                version="1.0.0",
                tools=self._tools
            )

            return mcp_server

        except ImportError:
            raise ToolError("无法导入 claude_agent_sdk，请确保已安装")
        except Exception as e:
            raise ToolError(f"创建 MCP 服务器失败: {e}")

    def get_tool_names(self) -> list[str]:
        """
        获取所有工具名称列表

        Returns:
            工具名称列表
        """
        return self._tool_names.copy()

    def filter_tools(self, allowed: list[str] | None = None, disallowed: list[str] | None = None) -> list[str]:
        """
        根据 allowed/disallowed 规则过滤工具

        注意：此方法是辅助工具方法，当前系统使用 ClaudeAgentOptions 的
        allowed_tools/disallowed_tools 配置进行过滤。
        此方法可用于手动获取过滤后的工具名称列表。

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

    @property
    def tools(self) -> list[Callable]:
        """获取所有工具函数"""
        return self._tools.copy()

    @property
    def tools_count(self) -> int:
        """获取工具数量"""
        return len(self._tools)
