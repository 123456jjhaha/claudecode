"""
Claude Agent System

基于 Claude Agent SDK 的可扩展智能体系统
"""

__version__ = "1.0.0"

# 导出主类
from .agent_system import AgentSystem, QueryResult, QueryStream

# 导出核心组件
from .config_manager import ConfigManager, merge_mcp_configs
from .tool_manager import ToolManager
from .sub_instance_adapter import SubInstanceTool, create_sub_instance_tools

# 导出错误类
from .error_handling import (
    AgentSystemError,
    ConfigError,
    ConfigValidationError,
    ToolError,
    ToolDiscoveryError,
    ToolLoadError,
    MCPServerError,
)

# 导出日志配置
from .logging_config import setup_logger, get_logger, set_log_level

__all__ = [
    # 版本
    "__version__",
    # 主类
    "AgentSystem",
    "QueryResult",
    "QueryStream",
    # 核心组件
    "ConfigManager",
    "ToolManager",
    "SubInstanceTool",
    "create_sub_instance_tools",
    "merge_mcp_configs",
    # 错误类
    "AgentSystemError",
    "ConfigError",
    "ConfigValidationError",
    "ToolError",
    "ToolDiscoveryError",
    "ToolLoadError",
    "MCPServerError",
    # 日志
    "setup_logger",
    "get_logger",
    "set_log_level",
]
