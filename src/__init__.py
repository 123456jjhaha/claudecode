"""
Claude Agent System

基于 Claude Agent SDK 的可扩展智能体系统
"""

__version__ = "1.0.0"

# 导出主类
from .agent_system import AgentSystem

# 导出核心组件
from .config_loader import AgentConfigLoader
from .tool_manager import ToolManager
from .instance_manager import InstanceManager
from .mcp_config_loader import load_mcp_config, merge_mcp_configs

# 导出错误类
from .error_handling import (
    AgentSystemError,
    ConfigError,
    ConfigValidationError,
    ToolError,
    ToolDiscoveryError,
    ToolLoadError,
    InstanceError,
    InstanceNotFoundError,
    InstanceExecutionError,
    PathResolutionError,
    MCPServerError,
)

# 导出日志配置
from .logging_config import setup_logger, get_logger, set_log_level

__all__ = [
    # 版本
    "__version__",
    # 主类
    "AgentSystem",
    # 核心组件
    "AgentConfigLoader",
    "ToolManager",
    "InstanceManager",
    "load_mcp_config",
    "merge_mcp_configs",
    # 错误类
    "AgentSystemError",
    "ConfigError",
    "ConfigValidationError",
    "ToolError",
    "ToolDiscoveryError",
    "ToolLoadError",
    "InstanceError",
    "InstanceNotFoundError",
    "InstanceExecutionError",
    "PathResolutionError",
    "MCPServerError",
    # 日志
    "setup_logger",
    "get_logger",
    "set_log_level",
]
