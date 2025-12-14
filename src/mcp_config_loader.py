"""
MCP 配置加载模块

负责读取和解析 .mcp.json 文件
"""

import json
from pathlib import Path
from typing import Any

from .error_handling import ConfigError
from .logging_config import get_logger

logger = get_logger(__name__)


def load_mcp_config(instance_path: Path) -> dict[str, dict[str, Any]]:
    """
    加载实例目录下的 .mcp.json 文件

    Args:
        instance_path: 实例目录路径

    Returns:
        MCP 服务器配置字典 {服务器名: 配置}
        如果文件不存在或解析失败，返回空字典

    注意：
        返回的配置格式为 stdio/sse/http 类型的配置，
        不包含 type="sdk" 的配置（那是我们内部创建的）
    """
    mcp_file = instance_path / ".mcp.json"

    if not mcp_file.exists():
        logger.debug(f"未找到 .mcp.json 文件: {mcp_file}")
        return {}

    try:
        logger.info(f"加载 MCP 配置文件: {mcp_file}")

        with open(mcp_file, "r", encoding="utf-8") as f:
            content = f.read()

        # 解析 JSON
        data = json.loads(content)

        # 标准格式：{ "mcpServers": { "server_name": {...} } }
        if "mcpServers" not in data:
            logger.warning(f".mcp.json 格式错误：缺少 'mcpServers' 字段")
            return {}

        mcp_servers = data["mcpServers"]

        if not isinstance(mcp_servers, dict):
            logger.warning(f".mcp.json 格式错误：'mcpServers' 必须是字典")
            return {}

        # 验证和标准化配置
        validated_servers = {}
        for server_name, server_config in mcp_servers.items():
            if not isinstance(server_config, dict):
                logger.warning(f"跳过无效的服务器配置: {server_name}")
                continue

            # 获取服务器类型，默认为 stdio（向后兼容）
            server_type = server_config.get("type", "stdio")

            # 验证配置完整性
            if not _validate_server_config(server_name, server_type, server_config):
                logger.warning(f"跳过无效的服务器配置: {server_name}")
                continue

            # 健康检查：过滤掉明显会失败的配置
            if server_type == 'stdio':
                command = server_config.get('command', '')

                # 跳过示例/测试配置（避免污染 MCP 系统）
                if command.lower() in ['echo', 'test', 'example', 'demo']:
                    logger.warning(
                        f"跳过示例 MCP 服务器配置: {server_name} "
                        f"(command={command})"
                    )
                    continue

                # TODO: 可以添加更多检查，如验证命令是否在 PATH 中
                # import shutil
                # if not shutil.which(command):
                #     logger.warning(f"命令不存在: {command}")
                #     continue

            # 通过所有检查，添加到 validated_servers
            validated_servers[server_name] = server_config
            logger.debug(f"加载 MCP 服务器: {server_name} (type={server_type})")

        logger.info(f"成功加载 {len(validated_servers)} 个 MCP 服务器")
        return validated_servers

    except json.JSONDecodeError as e:
        logger.error(f"解析 .mcp.json 失败: {e}")
        return {}
    except Exception as e:
        logger.error(f"加载 .mcp.json 失败: {e}")
        return {}


def _validate_server_config(
    server_name: str,
    server_type: str,
    config: dict[str, Any]
) -> bool:
    """
    验证 MCP 服务器配置的完整性

    Args:
        server_name: 服务器名称
        server_type: 服务器类型 (stdio/http/sse)
        config: 服务器配置

    Returns:
        配置是否有效
    """
    # 验证类型
    valid_types = ["stdio", "http", "sse"]
    if server_type not in valid_types:
        logger.warning(
            f"服务器 '{server_name}' 的类型 '{server_type}' 无效，"
            f"有效类型: {', '.join(valid_types)}"
        )
        return False

    # 验证必需字段
    if server_type == "stdio":
        if "command" not in config:
            logger.warning(f"stdio 类型服务器 '{server_name}' 缺少 'command' 字段")
            return False
    elif server_type in ["http", "sse"]:
        if "url" not in config:
            logger.warning(f"{server_type} 类型服务器 '{server_name}' 缺少 'url' 字段")
            return False

    return True


def merge_mcp_configs(
    sdk_servers: dict[str, Any],
    external_servers: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """
    合并 SDK 服务器和外部 MCP 服务器配置

    Args:
        sdk_servers: SDK 创建的服务器配置 (type="sdk")
        external_servers: 从 .mcp.json 加载的外部服务器配置

    Returns:
        合并后的服务器配置字典

    注意：
        如果有名称冲突，SDK 服务器优先（防止覆盖内部服务器）
    """
    merged = {}

    # 先添加外部服务器
    for name, config in external_servers.items():
        merged[name] = config
        logger.debug(f"添加外部 MCP 服务器: {name}")

    # 再添加 SDK 服务器（优先级更高）
    for name, config in sdk_servers.items():
        if name in merged:
            logger.warning(
                f"MCP 服务器名称冲突: '{name}' "
                f"（SDK 服务器将覆盖 .mcp.json 中的配置）"
            )
        merged[name] = config
        logger.debug(f"添加 SDK MCP 服务器: {name}")

    return merged
