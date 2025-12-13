"""
编码风格检查器工具 - 检查Python编码规范
"""

from claude_agent_sdk import tool
from typing import Dict, Any, List
import ast

@tool(
    name="check_style",
    description="检查Python代码的编码风格，包括命名规范、导入顺序等",
    input_schema={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "要检查的Python文件路径"
            },
            "strict_mode": {
                "type": "boolean",
                "description": "是否启用严格模式检查",
                "default": False
            }
        },
        "required": ["file_path"]
    }
)
async def check_style(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    执行编码风格检查

    Args:
        args: 包含文件路径和严格模式标志的字典

    Returns:
        风格检查结果
    """
    file_path = args.get("file_path", "")
    strict_mode = args.get("strict_mode", False)

    style_issues = []

    try:
        # 读取文件
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')

        # 解析AST
        tree = ast.parse(content)

        # 1. 检查导入顺序
        import_issues = check_import_order(tree, lines)
        style_issues.extend(import_issues)

        # 2. 检查命名规范
        naming_issues = check_naming_conventions(tree)
        style_issues.extend(naming_issues)

        # 3. 检查文档字符串
        docstring_issues = check_docstrings(tree)
        style_issues.extend(docstring_issues)

        # 4. 检查类型注解
        if strict_mode:
            type_issues = check_type_annotations(tree)
            style_issues.extend(type_issues)

        # 5. 检查魔法方法
        magic_method_issues = check_magic_methods(tree)
        style_issues.extend(magic_method_issues)

        # 统计结果
        error_count = sum(1 for issue in style_issues if issue["severity"] == "error")
        warning_count = sum(1 for issue in style_issues if issue["severity"] == "warning")
        info_count = sum(1 for issue in style_issues if issue["severity"] == "info")

        # 生成报告
        report_lines = [
            f"## 编码风格检查报告",
            f"**文件**: {file_path}",
            f"**模式**: {'严格' if strict_mode else '标准'}",
            f"**问题总数**: {len(style_issues)} (错误: {error_count}, 警告: {warning_count}, 建议: {info_count})",
            "",
        ]

        if style_issues:
            # 按严重程度分组
            errors = [i for i in style_issues if i["severity"] == "error"]
            warnings = [i for i in style_issues if i["severity"] == "warning"]
            infos = [i for i in style_issues if i["severity"] == "info"]

            if errors:
                report_lines.append("### 🚨 错误")
                for issue in errors[:5]:
                    report_lines.append(f"- 第{issue['line']}行: {issue['message']}")

            if warnings:
                report_lines.append("\n### ⚠️ 警告")
                for issue in warnings[:5]:
                    report_lines.append(f"- 第{issue['line']}行: {issue['message']}")

            if infos:
                report_lines.append("\n### 💡 建议")
                for issue in infos[:5]:
                    report_lines.append(f"- 第{issue['line']}行: {issue['message']}")
        else:
            report_lines.append("✅ 编码风格检查通过！")

        # 添加改进建议
        report_lines.extend([
            "\n### 📋 改进建议",
            "1. 遵循PEP 8编码规范",
            "2. 使用描述性的变量和函数名",
            "3. 为公共API编写文档字符串",
            "4. 考虑添加类型注解以提高代码可读性"
        ])

        return {
            "content": [{
                "type": "text",
                "text": "\n".join(report_lines)
            }],
            "summary": {
                "total_issues": len(style_issues),
                "errors": error_count,
                "warnings": warning_count,
                "infos": info_count,
                "file_path": file_path
            },
            "issues": style_issues
        }

    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"❌ 风格检查失败: {str(e)}"
            }],
            "error": str(e)
        }

def check_import_order(tree: ast.AST, lines: List[str]) -> List[Dict[str, Any]]:
    """检查导入顺序"""
    issues = []
    imports = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append({
                    "line": node.lineno,
                    "type": "import",
                    "module": alias.name,
                    "node": node
                })
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append({
                    "line": node.lineno,
                    "type": "from",
                    "module": node.module,
                    "node": node
                })

    # 检查是否按标准库、第三方、本地模块的顺序
    stdlib_imports = []
    third_party_imports = []
    local_imports = []

    for imp in imports:
        module = imp["module"].split('.')[0]
        if module in ['os', 'sys', 'json', 'datetime', 'collections', 'itertools',
                      'functools', 'operator', 're', 'math', 'random', 'time', 'io']:
            stdlib_imports.append(imp)
        elif module.startswith('.'):
            local_imports.append(imp)
        else:
            third_party_imports.append(imp)

    # 检查顺序是否正确
    all_imports = stdlib_imports + third_party_imports + local_imports
    if all_imports != sorted(imports, key=lambda x: x["line"]):
        issues.append({
            "line": min([i["line"] for i in imports]) if imports else 1,
            "rule": "import_order",
            "severity": "warning",
            "message": "导入顺序不规范，应按：标准库 -> 第三方 -> 本地模块的顺序排列",
            "suggestion": "重新排列import语句"
        })

    return issues

def check_naming_conventions(tree: ast.AST) -> List[Dict[str, Any]]:
    """检查命名规范"""
    issues = []

    for node in ast.walk(tree):
        # 检查变量名（小写+下划线）
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            if node.id.isupper() and not node.id.isupper():  # 常量应该全大写
                # 这里简化处理，实际需要更复杂的上下文分析
                pass

        # 检查函数名
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.islower() or '_' not in node.name and len(node.name) > 1:
                if not node.name.startswith('_') or not node.name.endswith('_'):  # 排除魔术方法
                    issues.append({
                        "line": node.lineno,
                        "rule": "function_naming",
                        "severity": "warning",
                        "message": f"函数名 '{node.name}' 不符合snake_case规范",
                        "suggestion": "使用小写字母和下划线"
                    })

        # 检查类名
        if isinstance(node, ast.ClassDef):
            if not node.name[0].isupper() or '_' in node.name:
                issues.append({
                    "line": node.lineno,
                    "rule": "class_naming",
                    "severity": "warning",
                    "message": f"类名 '{node.name}' 不符合PascalCase规范",
                    "suggestion": "使用首字母大写的驼峰命名"
                })

        # 检查常量（模块级别的全大写变量）
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    if target.id.isupper():
                        # 检查是否在模块顶层（简化处理）
                        issues.append({
                            "line": node.lineno,
                            "rule": "constant_naming",
                            "severity": "info",
                            "message": f"常量 '{target.id}' 应该在模块顶部定义",
                            "suggestion": "将常量定义移到模块顶部"
                        })

    return issues

def check_docstrings(tree: ast.AST) -> List[Dict[str, Any]]:
    """检查文档字符串"""
    issues = []

    for node in ast.walk(tree):
        # 检查类文档字符串
        if isinstance(node, ast.ClassDef):
            if not ast.get_docstring(node):
                issues.append({
                    "line": node.lineno,
                    "rule": "class_docstring",
                    "severity": "info",
                    "message": f"类 '{node.name}' 缺少文档字符串",
                    "suggestion": "添加类文档字符串说明类的用途"
                })

        # 检查公共函数的文档字符串
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith('_'):  # 公共函数
                if not ast.get_docstring(node):
                    issues.append({
                        "line": node.lineno,
                        "rule": "function_docstring",
                        "severity": "info",
                        "message": f"公共函数 '{node.name}' 缺少文档字符串",
                        "suggestion": "添加函数文档字符串说明功能和参数"
                    })

    return issues

def check_type_annotations(tree: ast.AST) -> List[Dict[str, Any]]:
    """检查类型注解"""
    issues = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # 检查参数类型注解
            for arg in node.args.args:
                if not arg.annotation and arg.arg != 'self':
                    issues.append({
                        "line": node.lineno,
                        "rule": "parameter_type_annotation",
                        "severity": "info",
                        "message": f"函数 '{node.name}' 的参数 '{arg.arg}' 缺少类型注解",
                        "suggestion": "添加参数类型注解"
                    })

            # 检查返回值类型注解
            if not node.returns:
                issues.append({
                    "line": node.lineno,
                    "rule": "return_type_annotation",
                    "severity": "info",
                    "message": f"函数 '{node.name}' 缺少返回值类型注解",
                    "suggestion": "添加返回值类型注解"
                })

    return issues

def check_magic_methods(tree: ast.AST) -> List[Dict[str, Any]]:
    """检查魔法方法的实现"""
    issues = []

    magic_methods = {
        '__str__': '应该返回用户友好的字符串表示',
        '__repr__': '应该返回开发友好的、可重现的字符串表示',
        '__eq__': '实现了__eq__后应该也实现__hash__',
        '__lt__': '实现了__lt__后应该考虑实现其他比较方法'
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_methods = [n.name for n in node.body
                           if isinstance(n, ast.FunctionDef)]

            # 检查__str__和__repr__的平衡
            has_str = '__str__' in class_methods
            has_repr = '__repr__' in class_methods

            if has_str and not has_repr:
                issues.append({
                    "line": node.lineno,
                    "rule": "magic_methods_balance",
                    "severity": "info",
                    "message": f"类 '{node.name}' 实现了__str__但缺少__repr__",
                    "suggestion": "同时实现__repr__方法"
                })

            # 检查比较方法的完整性
            comparison_methods = ['__lt__', '__le__', '__gt__', '__ge__', '__eq__', '__ne__']
            has_comparison = any(m in class_methods for m in comparison_methods)

            if has_comparison and '__eq__' not in class_methods:
                issues.append({
                    "line": node.lineno,
                    "rule": "comparison_methods",
                    "severity": "warning",
                    "message": f"类 '{node.name}' 有比较方法但缺少__eq__",
                    "suggestion": "实现__eq__方法确保对象比较的正确性"
                })

    return issues