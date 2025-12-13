"""
计算器工具 - 演示基础数学计算功能
"""

from claude_agent_sdk import tool
from typing import Dict, Any
import ast
import operator

# 支持的运算符
OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
}

@tool(
    name="calculate",
    description="执行数学计算，支持加减乘除、幂运算、取模等",
    input_schema={
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "数学表达式，例如: 123 + 456, 2 ** 10, 100 % 7"
            }
        },
        "required": ["expression"]
    }
)
async def calculate(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    计算数学表达式

    Args:
        args: 包含 expression 字段的字典

    Returns:
        计算结果
    """
    expression = args.get("expression", "")

    try:
        # 解析表达式
        node = ast.parse(expression, mode='eval')

        # 递归计算
        def _eval(node):
            if isinstance(node, ast.Num):  # Python < 3.8
                return node.n
            elif isinstance(node, ast.Constant):  # Python >= 3.8
                if isinstance(node.value, (int, float)):
                    return node.value
                else:
                    raise ValueError("只支持数字常量")
            elif isinstance(node, ast.BinOp):
                left = _eval(node.left)
                right = _eval(node.right)
                op_type = type(node.op)
                if op_type in OPERATORS:
                    return OPERATORS[op_type](left, right)
                else:
                    raise ValueError(f"不支持的运算符: {op_type}")
            elif isinstance(node, ast.UnaryOp):
                operand = _eval(node.operand)
                if isinstance(node.op, ast.UAdd):
                    return +operand
                elif isinstance(node.op, ast.USub):
                    return -operand
                else:
                    raise ValueError(f"不支持的一元运算符: {type(node.op)}")
            else:
                raise ValueError(f"不支持的语法: {type(node)}")

        result = _eval(node.body)

        return {
            "content": [{
                "type": "text",
                "text": f"计算结果: {expression} = {result}"
            }],
            "expression": expression,
            "result": result
        }

    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"计算错误: {str(e)}\n请输入有效的数学表达式，例如: 123 + 456"
            }],
            "error": str(e)
        }

@tool(
    name="add_numbers",
    description="计算两个或多个数字的和",
    input_schema={
        "type": "object",
        "properties": {
            "numbers": {
                "type": "array",
                "items": {"type": "number"},
                "description": "要相加的数字列表"
            }
        },
        "required": ["numbers"]
    }
)
async def add_numbers(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    计算多个数字的和

    Args:
        args: 包含 numbers 列表的字典

    Returns:
        计算结果
    """
    numbers = args.get("numbers", [])

    if not numbers:
        return {
            "content": [{
                "type": "text",
                "text": "错误: 请提供至少一个数字"
            }]
        }

    total = sum(numbers)

    return {
        "content": [{
            "type": "text",
            "text": f"计算结果: {' + '.join(map(str, numbers))} = {total}"
        }],
        "numbers": numbers,
        "total": total
    }