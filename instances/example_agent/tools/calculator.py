"""
计算器工具示例

演示如何使用 @tool 装饰器定义自定义工具
"""

from claude_agent_sdk import tool
from typing import Any, Dict


@tool(
    name="add",
    description="将两个数字相加",
    input_schema={
        "a": {
            "type": "number",
            "description": "第一个数字"
        },
        "b": {
            "type": "number",
            "description": "第二个数字"
        }
    }
)
async def add(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    加法工具

    Args:
        args: 包含 a 和 b 的字典

    Returns:
        工具执行结果
    """
    # 确保参数是数字类型
    a = float(args.get("a", 0))
    b = float(args.get("b", 0))
    result = a + b

    return {
        "content": [{
            "type": "text",
            "text": f"{a} + {b} = {result}"
        }]
    }


@tool(
    name="multiply",
    description="将两个数字相乘",
    input_schema={
        "a": {
            "type": "number",
            "description": "第一个数字"
        },
        "b": {
            "type": "number",
            "description": "第二个数字"
        }
    }
)
async def multiply(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    乘法工具

    Args:
        args: 包含 a 和 b 的字典

    Returns:
        工具执行结果
    """
    # 确保参数是数字类型
    a = float(args.get("a", 1))
    b = float(args.get("b", 1))
    result = a * b

    return {
        "content": [{
            "type": "text",
            "text": f"{a} × {b} = {result}"
        }]
    }


@tool(
    name="divide",
    description="将第一个数字除以第二个数字",
    input_schema={
        "a": {
            "type": "number",
            "description": "被除数"
        },
        "b": {
            "type": "number",
            "description": "除数"
        }
    }
)
async def divide(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    除法工具

    Args:
        args: 包含 a 和 b 的字典

    Returns:
        工具执行结果
    """
    # 确保参数是数字类型
    a = float(args.get("a", 0))
    b = float(args.get("b", 1))

    if b == 0:
        return {
            "content": [{
                "type": "text",
                "text": "错误：除数不能为零"
            }],
            "is_error": True
        }

    result = a / b

    return {
        "content": [{
            "type": "text",
            "text": f"{a} ÷ {b} = {result}"
        }]
    }


@tool(
    name="power",
    description="计算第一个数字的第二个数字次幂",
    input_schema={
        "base": {
            "type": "number",
            "description": "底数"
        },
        "exponent": {
            "type": "number",
            "description": "指数"
        }
    }
)
async def power(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    幂运算工具

    Args:
        args: 包含 base 和 exponent 的字典

    Returns:
        工具执行结果
    """
    # 确保参数是数字类型
    base = float(args.get("base", 0))
    exponent = float(args.get("exponent", 1))
    result = base ** exponent

    return {
        "content": [{
            "type": "text",
            "text": f"{base}^{exponent} = {result}"
        }]
    }
