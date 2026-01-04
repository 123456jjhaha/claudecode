"""
错误处理模块

定义自定义异常类，用于 Claude Agent System 中的错误处理
"""


class AgentSystemError(Exception):
    """Agent System 基础异常类"""
    pass


class ConfigError(AgentSystemError):
    """配置相关错误"""
    def __init__(self, message: str, config_path: str | None = None):
        self.config_path = config_path
        if config_path:
            message = f"配置错误 ({config_path}): {message}"
        super().__init__(message)


class ConfigValidationError(ConfigError):
    """配置验证错误"""
    def __init__(self, message: str, field: str | None = None):
        self.field = field
        if field:
            message = f"配置字段 '{field}' 验证失败: {message}"
        super().__init__(message)


class ToolError(AgentSystemError):
    """工具相关错误"""
    def __init__(self, message: str, tool_name: str | None = None):
        self.tool_name = tool_name
        if tool_name:
            message = f"工具错误 ({tool_name}): {message}"
        super().__init__(message)


class ToolDiscoveryError(ToolError):
    """工具发现错误"""
    pass


class ToolLoadError(ToolError):
    """工具加载错误"""
    pass




class MCPServerError(AgentSystemError):
    """MCP 服务器相关错误"""
    def __init__(self, message: str, server_name: str | None = None):
        self.server_name = server_name
        if server_name:
            message = f"MCP 服务器错误 ({server_name}): {message}"
        super().__init__(message)
