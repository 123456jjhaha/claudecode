"""
FastMCP 服务器主实现 - 简化版，直接支持原生工具格式
"""

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List

# FastMCP 导入
try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print("错误: 需要安装 mcp 包")
    print("请运行: pip install 'mcp[cli]'")
    sys.exit(1)

# 处理相对导入问题
try:
    from .tool_loader import load_tools_from_instance, load_sub_instance_tools, NativeToolFunction
    from ..logging_config import get_logger
except ImportError:
    # 直接运行时的绝对导入
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from mcp_server.tool_loader import load_tools_from_instance, load_sub_instance_tools, NativeToolFunction
    from logging_config import get_logger

logger = get_logger(__name__)


def create_fastmcp_server(instance_path: Path) -> FastMCP:
    """
    创建 FastMCP 服务器实例并注册工具（包括本地工具和子实例工具）

    Args:
        instance_path: 实例目录路径

    Returns:
        FastMCP 服务器实例
    """
    # 创建 FastMCP 服务器
    mcp = FastMCP(
        name=f"instance_tools_{instance_path.name}",
        json_response=True
    )

    # 1. 加载本地工具
    local_tools, local_tool_names = load_tools_from_instance(instance_path)

    if local_tools:
        logger.info(f"加载 {len(local_tools)} 个本地工具: {', '.join(local_tool_names)}")
        # 注册每个本地工具
        for tool in local_tools:
            register_tool(mcp, tool)
    else:
        logger.info("未找到本地工具")

    # 2. 加载子实例工具
    sub_instance_tools = load_sub_instance_tools(instance_path)

    if sub_instance_tools:
        logger.info(f"加载 {len(sub_instance_tools)} 个子实例工具")
        # 注册每个子实例工具
        for tool in sub_instance_tools:
            register_sub_instance_tool(mcp, tool)
    else:
        logger.info("未找到子实例工具")

    total_tools = len(local_tools) + len(sub_instance_tools)
    logger.info(f"总共注册 {total_tools} 个工具到 MCP 服务器")

    return mcp


def register_tool(mcp: FastMCP, tool: NativeToolFunction):
    """
    将原生工具函数注册到 FastMCP 服务器

    Args:
        mcp: FastMCP 服务器实例
        tool: 原生工具函数包装器
    """
    # 直接使用 FastMCP 的装饰器注册工具
    # 工具函数已经是异步的，可以直接使用
    mcp.tool(
        name=tool.name,
        description=tool.description
    )(tool.func)

    logger.debug(f"注册本地工具: {tool.name}")


def register_sub_instance_tool(mcp: FastMCP, tool: Any):
    """
    将子实例工具注册到 FastMCP 服务器

    Args:
        mcp: FastMCP 服务器实例
        tool: 子实例工具对象（SubInstanceTool）
    """
    # 子实例工具对象本身就是可调用的（实现了 __call__）
    mcp.tool(
        name=tool.name,
        description=tool._description
    )(tool)

    logger.debug(f"注册子实例工具: {tool.name}")


def run_server_sync(instance_path: Path):
    """
    同步运行 FastMCP 服务器

    Args:
        instance_path: 实例目录路径
    """
    logger.info(f"启动 MCP 服务器，实例路径: {instance_path}")

    try:
        # 创建 FastMCP 服务器
        mcp = create_fastmcp_server(instance_path)

        # 运行服务器（stdio 模式）
        # FastMCP.run() 是同步函数
        mcp.run(transport="stdio")

    except Exception as e:
        logger.error(f"MCP 服务器运行失败: {e}")
        sys.exit(1)


def run_server():
    """
    运行 MCP 服务器的入口点

    命令行参数:
        --instance-path: 实例目录路径（必需）
    """
    parser = argparse.ArgumentParser(
        description="运行实例工具的 MCP 服务器"
    )
    parser.add_argument(
        "--instance-path",
        type=str,
        required=True,
        help="实例目录路径"
    )

    args = parser.parse_args()

    # 验证实例路径
    instance_path = Path(args.instance_path).resolve()
    if not instance_path.exists():
        logger.error(f"实例目录不存在: {instance_path}")
        sys.exit(1)

    # 运行服务器
    run_server_sync(instance_path)


if __name__ == "__main__":
    run_server()