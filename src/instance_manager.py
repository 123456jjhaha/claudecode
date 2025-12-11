"""
实例管理模块

管理多个子 Claude 实例，创建工具定义
注意：此模块只创建工具定义，不实例化 AgentSystem
"""

from pathlib import Path
from typing import Dict, Callable

from .claude_instance_wrapper import create_claude_instance_tool
from .error_handling import InstanceError, InstanceNotFoundError
from .logging_config import get_logger

logger = get_logger(__name__)


class InstanceManager:
    """
    子实例管理器

    负责：
    1. 加载子实例配置
    2. 为每个子实例创建工具定义
    3. 创建 MCP 服务器配置

    不负责：
    - 实例化 AgentSystem（延迟到工具调用时）
    - 并行执行（由 Claude SDK 自动处理）
    """

    def __init__(
        self,
        instances_config: dict[str, str],
        instances_root: Path
    ):
        """
        初始化实例管理器

        Args:
            instances_config: 子实例配置字典 {实例名: 相对路径}
            instances_root: 实例根目录
        """
        self.instances_config = instances_config
        self.instances_root = Path(instances_root)

        # 存储实例工具定义
        self._instance_tools: dict[str, Callable] = {}

    def load_instances(self) -> dict[str, Callable]:
        """
        为所有子实例创建工具定义

        注意：此方法只创建工具定义，不实例化 AgentSystem。
        当工具被 Claude 调用时，才会动态创建 AgentSystem 实例。

        Returns:
            实例工具字典 {实例名: 工具函数}

        Raises:
            InstanceError: 实例加载失败
        """
        if not self.instances_config:
            logger.info("没有配置子实例")
            return {}

        logger.info(f"开始为 {len(self.instances_config)} 个子实例创建工具定义")

        for instance_name, relative_path in self.instances_config.items():
            try:
                instance_path = self.instances_root / relative_path

                if not instance_path.exists():
                    raise InstanceNotFoundError(
                        f"实例目录不存在: {instance_path}",
                        instance_name=instance_name
                    )

                logger.debug(f"为子实例创建工具: {instance_name} ({instance_path})")

                # 创建工具定义（不实例化 AgentSystem）
                tool = create_claude_instance_tool(
                    instance_name=instance_name,
                    instance_path=instance_path,
                    instances_root=self.instances_root
                )

                self._instance_tools[instance_name] = tool
                logger.info(f"成功创建子实例工具: {instance_name}")

            except Exception as e:
                if isinstance(e, InstanceError):
                    raise
                raise InstanceError(f"创建子实例工具失败: {e}", instance_name=instance_name)

        logger.info(f"所有子实例工具创建完成，共 {len(self._instance_tools)} 个")
        return self._instance_tools

    def create_mcp_server(self, server_name: str = "sub_instances"):
        """
        创建子实例的 MCP SDK 服务器

        Args:
            server_name: 服务器名称

        Returns:
            McpSdkServerConfig 对象（如果有子实例的话）
        """
        if not self._instance_tools:
            logger.debug("没有子实例工具，跳过创建 MCP 服务器")
            return None

        try:
            from claude_agent_sdk import create_sdk_mcp_server

            logger.info(f"创建子实例 MCP 服务器: {server_name}")

            tools_list = list(self._instance_tools.values())

            mcp_server = create_sdk_mcp_server(
                name=server_name,
                version="1.0.0",
                tools=tools_list
            )

            return mcp_server

        except ImportError:
            raise InstanceError("无法导入 claude_agent_sdk，请确保已安装")
        except Exception as e:
            raise InstanceError(f"创建子实例 MCP 服务器失败: {e}")

    def get_instance_tool(self, instance_name: str) -> Callable:
        """
        获取指定实例的工具函数

        Args:
            instance_name: 实例名称

        Returns:
            工具函数

        Raises:
            InstanceNotFoundError: 实例不存在
        """
        if instance_name not in self._instance_tools:
            raise InstanceNotFoundError(
                f"子实例不存在",
                instance_name=instance_name
            )

        return self._instance_tools[instance_name]

    def get_tool_names(self) -> list[str]:
        """
        获取所有子实例工具的名称

        Returns:
            工具名称列表（格式：sub_claude_<instance_name>）
        """
        return [f"sub_claude_{name}" for name in self._instance_tools.keys()]

    @property
    def instances(self) -> dict[str, Callable]:
        """获取所有实例工具定义"""
        return self._instance_tools.copy()

    @property
    def instance_count(self) -> int:
        """获取实例数量"""
        return len(self._instance_tools)
