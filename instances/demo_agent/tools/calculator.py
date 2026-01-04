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

async def divide(a: float, b: float) -> dict:
    """
    计算两个数字的除法

    Args:
        a: 被除数
        b: 除数

    Returns:
        计算结果
    """
    if b == 0:
        return {
            "operation": "divide",
            "operands": [a, b],
            "result": None,
            "error": "除数不能为零"
        }
    result = a / b
    return {
        "operation": "divide",
        "operands": [a, b],
        "result": result
    }