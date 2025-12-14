"""
计算器工具 - 使用 FastMCP 原生格式
"""

from mcp.server.fastmcp import FastMCP

# 这个函数将被动态注册到 FastMCP 服务器
async def add(a: float, b: float) -> dict:
    """
    计算两个数字的和

    Args:
        a: 第一个数字
        b: 第二个数字

    Returns:
        计算结果
    """
    result = a + b
    return {
        "operation": "add",
        "operands": [a, b],
        "result": result
    }

async def multiply(a: float, b: float) -> dict:
    """
    计算两个数字的乘积

    Args:
        a: 第一个数字
        b: 第二个数字

    Returns:
        计算结果
    """
    result = a * b
    return {
        "operation": "multiply",
        "operands": [a, b],
        "result": result
    }