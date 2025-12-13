"""
语法验证器工具 - 验证代码语法正确性
"""

from claude_agent_sdk import tool
from typing import Dict, Any, List
import ast
import subprocess
import sys
import tempfile
import os

@tool(
    name="validate_syntax",
    description="验证代码文件的语法正确性，支持多种语言",
    input_schema={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "要验证的文件路径"
            },
            "language": {
                "type": "string",
                "description": "语言类型（可选，自动检测）",
                "enum": ["python", "javascript", "json", "yaml", "html", "css", "auto"]
            },
            "use_linter": {
                "type": "boolean",
                "description": "是否使用外部linter工具进行更严格的检查",
                "default": false
            }
        },
        "required": ["file_path"]
    }
)
async def validate_syntax(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    验证代码语法正确性

    Args:
        args: 包含文件路径、语言类型和linter选项的字典

    Returns:
        验证结果
    """
    file_path = args.get("file_path", "")
    language = args.get("language", "auto")
    use_linter = args.get("use_linter", False)

    # 自动检测语言
    if language == "auto":
        language = detect_language(file_path)

    validation_result = {
        "file_path": file_path,
        "language": language,
        "valid": True,
        "errors": [],
        "warnings": [],
        "lint_results": None
    }

    try:
        # 读取文件
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 根据语言类型进行验证
        if language == "python":
            result = validate_python(content, use_linter)
        elif language == "javascript":
            result = validate_javascript(content, use_linter)
        elif language == "json":
            result = validate_json(content)
        elif language == "yaml":
            result = validate_yaml(content)
        elif language == "html":
            result = validate_html(content, use_linter)
        elif language == "css":
            result = validate_css(content, use_linter)
        else:
            result = validate_generic(content)

        validation_result.update(result)
        validation_result["valid"] = len(validation_result["errors"]) == 0

        # 生成报告
        status_emoji = "✅" if validation_result["valid"] else "❌"
        report_lines = [
            f"## 语法验证结果",
            f"**文件**: {file_path}",
            f"**语言**: {language}",
            f"**状态**: {status_emoji} {'通过' if validation_result['valid'] else '失败'}",
            f"**错误数**: {len(validation_result['errors'])}",
            f"**警告数**: {len(validation_result['warnings'])}",
            "",
        ]

        # 错误详情
        if validation_result["errors"]:
            report_lines.append("### ❌ 语法错误")
            for error in validation_result["errors"][:10]:
                if isinstance(error, dict):
                    report_lines.append(
                        f"- **{error.get('type', 'Error')}** (第{error.get('line', '?')}行)\n"
                        f"  {error.get('message', 'Unknown error')}"
                    )
                else:
                    report_lines.append(f"- {error}")

        # 警告详情
        if validation_result["warnings"]:
            report_lines.append("\n### ⚠️ 警告")
            for warning in validation_result["warnings"][:5]:
                if isinstance(warning, dict):
                    report_lines.append(f"- {warning.get('message', 'Warning')}")
                else:
                    report_lines.append(f"- {warning}")

        # Linter结果
        if validation_result.get("lint_results"):
            report_lines.append("\n### 🔍 Linter检查")
            lint = validation_result["lint_results"]
            report_lines.append(f"- 检查工具: {lint.get('tool', 'Unknown')}")
            report_lines.append(f"- 发现问题: {len(lint.get('issues', []))}")
            if lint.get("score"):
                report_lines.append(f"- 评分: {lint['score']}/10")

        if validation_result["valid"]:
            report_lines.append("\n🎉 语法验证通过！代码结构正确。")

        return {
            "content": [{
                "type": "text",
                "text": "\n".join(report_lines)
            }],
            "validation_result": validation_result
        }

    except FileNotFoundError:
        return {
            "content": [{
                "type": "text",
                "text": f"❌ 错误: 找不到文件 {file_path}"
            }],
            "error": "file_not_found"
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"❌ 验证失败: {str(e)}"
            }],
            "error": str(e)
        }

def detect_language(file_path: str) -> str:
    """根据文件扩展名检测语言"""
    ext = file_path.split('.')[-1].lower()
    language_map = {
        'py': 'python',
        'js': 'javascript',
        'json': 'json',
        'yaml': 'yaml',
        'yml': 'yaml',
        'html': 'html',
        'htm': 'html',
        'css': 'css'
    }
    return language_map.get(ext, 'unknown')

def validate_python(content: str, use_linter: bool) -> Dict[str, Any]:
    """验证Python代码"""
    result = {
        "errors": [],
        "warnings": [],
        "lint_results": None
    }

    # 基础语法检查
    try:
        ast.parse(content)
    except SyntaxError as e:
        result["errors"].append({
            "type": "SyntaxError",
            "message": e.msg,
            "line": e.lineno,
            "column": e.offset,
            "text": e.text.strip() if e.text else ""
        })

    # 使用linter（如果可用）
    if use_linter:
        lint_result = run_python_linter(content)
        result["lint_results"] = lint_result
        result["warnings"].extend(lint_result.get("warnings", []))

    return result

def validate_javascript(content: str, use_linter: bool) -> Dict[str, Any]:
    """验证JavaScript代码"""
    result = {
        "errors": [],
        "warnings": [],
        "lint_results": None
    }

    # 基础语法检查（简化版）
    js_checks = [
        (r"function\s+\w+\s*\([^)]*\)\s*{", "函数定义"),
        (r"var\s+\w+\s*=", "变量声明"),
        (r"const\s+\w+\s*=", "常量声明"),
        (r"let\s+\w+\s*=", "块级变量声明"),
    ]

    # 检查括号匹配
    open_braces = content.count('{')
    close_braces = content.count('}')
    open_parens = content.count('(')
    close_parens = content.count(')')

    if open_braces != close_braces:
        result["errors"].append({
            "type": "BraceMismatch",
            "message": f"大括号不匹配: 开{open_braces}个，闭{close_braces}个"
        })

    if open_parens != close_parens:
        result["errors"].append({
            "type": "ParenMismatch",
            "message": f"圆括号不匹配: 开{open_parens}个，闭{close_parens}个"
        })

    return result

def validate_json(content: str) -> Dict[str, Any]:
    """验证JSON格式"""
    result = {
        "errors": [],
        "warnings": []
    }

    import json

    try:
        json.loads(content)
    except json.JSONDecodeError as e:
        result["errors"].append({
            "type": "JSONError",
            "message": e.msg,
            "line": e.lineno,
            "column": e.colno
        })

    return result

def validate_yaml(content: str) -> Dict[str, Any]:
    """验证YAML格式"""
    result = {
        "errors": [],
        "warnings": []
    }

    try:
        import yaml
        yaml.safe_load(content)
    except yaml.YAMLError as e:
        result["errors"].append({
            "type": "YAMLError",
            "message": str(e)
        })

    # 检查常见问题
    if '\t' in content:
        result["warnings"].append({
            "type": "TabIndentation",
            "message": "YAML使用Tab缩进，建议使用空格"
        })

    return result

def validate_html(content: str, use_linter: bool) -> Dict[str, Any]:
    """验证HTML格式"""
    result = {
        "errors": [],
        "warnings": []
    }

    # 简单的标签匹配检查
    import re

    # 查找所有标签
    tags = re.findall(r'<(/?)([a-zA-Z][a-zA-Z0-9]*)\b[^>]*>', content)

    tag_stack = []
    for closing, tag_name in tags:
        if not closing:  # 开标签
            if tag_name.lower() not in ['br', 'hr', 'img', 'meta', 'link']:  # 自闭合标签
                tag_stack.append(tag_name.lower())
        else:  # 闭标签
            if tag_stack and tag_stack[-1] == tag_name.lower():
                tag_stack.pop()
            else:
                result["errors"].append({
                    "type": "HTMLTagMismatch",
                    "message": f"HTML标签不匹配: </{tag_name}>"
                })

    if tag_stack:
        result["errors"].append({
            "type": "UnclosedTags",
            "message": f"未闭合的标签: {', '.join(tag_stack)}"
        })

    return result

def validate_css(content: str, use_linter: bool) -> Dict[str, Any]:
    """验证CSS格式"""
    result = {
        "errors": [],
        "warnings": []
    }

    # 简单的CSS语法检查
    import re

    # 检查选择器和大括号匹配
    rules = re.findall(r'([^{]+)\s*{([^}]*)}', content, re.DOTALL)

    for selector, properties in rules:
        # 检查属性声明
        props = properties.split(';')
        for prop in props:
            prop = prop.strip()
            if prop and ':' not in prop:
                result["errors"].append({
                    "type": "CSSPropertyError",
                    "message": f"CSS属性缺少冒号: {prop}"
                })

    return result

def validate_generic(content: str) -> Dict[str, Any]:
    """验证通用文本文件"""
    result = {
        "errors": [],
        "warnings": []
    }

    # 检查编码问题
    try:
        content.encode('utf-8')
    except UnicodeEncodeError as e:
        result["errors"].append({
            "type": "EncodingError",
            "message": f"文件包含非UTF-8字符: {e}"
        })

    return result

def run_python_linter(content: str) -> Dict[str, Any]:
    """运行Python linter（如果可用）"""
    result = {
        "tool": "none",
        "issues": [],
        "warnings": [],
        "score": None
    }

    try:
        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(content)
            temp_file = f.name

        # 尝试运行flake8（如果安装）
        try:
            result_flake8 = subprocess.run(
                [sys.executable, '-m', 'flake8', temp_file],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result_flake8.returncode == 0:
                result["tool"] = "flake8"
                result["warnings"] = [
                    {"message": line.strip(), "tool": "flake8"}
                    for line in result_flake8.stdout.split('\n')
                    if line.strip()
                ]
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            pass

        # 清理临时文件
        os.unlink(temp_file)

    except Exception:
        pass

    # 如果没有linter可用，进行基础检查
    if result["tool"] == "none":
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            if len(line) > 120:
                result["warnings"].append({
                    "message": f"第{i}行过长 ({len(line)} > 120)",
                    "tool": "basic"
                })

        result["tool"] = "basic"

    # 计算评分（简化版）
    if result["warnings"]:
        result["score"] = max(1, 10 - len(result["warnings"]))
    else:
        result["score"] = 10

    return result