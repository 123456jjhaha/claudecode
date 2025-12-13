"""
代码解析器工具 - 解析各种格式的代码文件
"""

from claude_agent_sdk import tool
from typing import Dict, Any, List
import ast
import json
import yaml
import re

@tool(
    name="parse_code",
    description="解析代码文件，检查语法结构和基本错误",
    input_schema={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "要解析的文件路径"
            },
            "language": {
                "type": "string",
                "description": "文件语言类型（可选，自动检测）"
            },
            "strict": {
                "type": "boolean",
                "description": "是否启用严格模式解析",
                "default": false
            }
        },
        "required": ["file_path"]
    }
)
async def parse_code(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    解析代码文件并检查语法

    Args:
        args: 包含文件路径、语言类型和严格模式标志的字典

    Returns:
        解析结果和错误信息
    """
    file_path = args.get("file_path", "")
    language = args.get("language", "")
    strict = args.get("strict", False)

    # 自动检测语言类型
    if not language:
        language = detect_language(file_path)

    try:
        # 读取文件
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        parse_result = {
            "file_path": file_path,
            "language": language,
            "content_size": len(content),
            "lines": len(content.splitlines()),
            "errors": [],
            "warnings": [],
            "structure": {}
        }

        # 根据语言类型解析
        if language == "python":
            result = parse_python(content, strict)
            parse_result.update(result)
        elif language == "json":
            result = parse_json(content, strict)
            parse_result.update(result)
        elif language == "yaml":
            result = parse_yaml(content, strict)
            parse_result.update(result)
        elif language == "markdown":
            result = parse_markdown(content, strict)
            parse_result.update(result)
        else:
            # 对于未知语言，进行基础检查
            result = parse_generic(content, strict)
            parse_result.update(result)

        # 生成报告
        report_lines = [
            f"## 代码解析报告",
            f"**文件**: {file_path}",
            f"**语言**: {language}",
            f"**状态**: {'✅ 通过' if not parse_result['errors'] else '❌ 发现错误'}",
            f"**统计**: {parse_result['lines']} 行, {parse_result['content_size']} 字符",
            "",
        ]

        # 显示错误
        if parse_result["errors"]:
            report_lines.append("### ❌ 语法错误")
            for error in parse_result["errors"][:10]:  # 限制显示数量
                if isinstance(error, dict):
                    report_lines.append(
                        f"- **{error.get('type', 'Error')}**: {error.get('message', 'Unknown error')}\n"
                        f"  位置: 第{error.get('line', '?')}行"
                    )
                else:
                    report_lines.append(f"- {error}")

        # 显示警告
        if parse_result["warnings"]:
            report_lines.append("\n### ⚠️ 警告")
            for warning in parse_result["warnings"][:5]:
                if isinstance(warning, dict):
                    report_lines.append(f"- {warning.get('message', 'Warning')}")
                else:
                    report_lines.append(f"- {warning}")

        # 显示结构信息
        if parse_result.get("structure"):
            report_lines.append("\n### 📊 代码结构")
            for key, value in parse_result["structure"].items():
                report_lines.append(f"- **{key}**: {value}")

        if not parse_result["errors"] and not parse_result["warnings"]:
            report_lines.append("\n✅ 代码结构良好，未发现语法问题。")

        return {
            "content": [{
                "type": "text",
                "text": "\n".join(report_lines)
            }],
            "parse_result": parse_result
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
                "text": f"❌ 解析失败: {str(e)}"
            }],
            "error": str(e)
        }

def detect_language(file_path: str) -> str:
    """根据文件扩展名检测语言类型"""
    ext = file_path.split('.')[-1].lower()
    language_map = {
        'py': 'python',
        'json': 'json',
        'yaml': 'yaml',
        'yml': 'yaml',
        'md': 'markdown',
        'txt': 'text',
        'js': 'javascript',
        'html': 'html',
        'css': 'css',
        'xml': 'xml'
    }
    return language_map.get(ext, 'unknown')

def parse_python(content: str, strict: bool) -> Dict[str, Any]:
    """解析Python代码"""
    result = {
        "errors": [],
        "warnings": [],
        "structure": {}
    }

    try:
        # 使用AST解析
        tree = ast.parse(content)

        # 统计结构信息
        functions = []
        classes = []
        imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions.append(node.name)
            elif isinstance(node, ast.ClassDef):
                classes.append(node.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)

        result["structure"] = {
            "函数数量": len(functions),
            "类数量": len(classes),
            "导入模块": len(set(imports)),
            "函数列表": functions[:5],  # 只显示前5个
            "类列表": classes[:5]
        }

        # 严格模式下的额外检查
        if strict:
            # 检查未使用的导入（简化版）
            lines = content.split('\n')
            for imp in set(imports):
                found_usage = any(imp in line for line in lines if not line.strip().startswith('import') and not line.strip().startswith('from'))
                if not found_usage and imp not in ['os', 'sys']:  # 排除常用模块
                    result["warnings"].append({
                        "type": "unused_import",
                        "message": f"可能未使用的导入: {imp}"
                    })

    except SyntaxError as e:
        result["errors"].append({
            "type": "SyntaxError",
            "message": e.msg,
            "line": e.lineno,
            "column": e.offset,
            "text": e.text
        })

    return result

def parse_json(content: str, strict: bool) -> Dict[str, Any]:
    """解析JSON内容"""
    result = {
        "errors": [],
        "warnings": [],
        "structure": {}
    }

    try:
        data = json.loads(content)

        # 统计结构
        if isinstance(data, dict):
            result["structure"] = {
                "类型": "对象",
                "键数量": len(data),
                "嵌套层级": get_json_depth(data)
            }
        elif isinstance(data, list):
            result["structure"] = {
                "类型": "数组",
                "元素数量": len(data),
                "嵌套层级": get_json_depth(data)
            }
        else:
            result["structure"] = {
                "类型": type(data).__name__,
                "大小": len(str(data))
            }

    except json.JSONDecodeError as e:
        result["errors"].append({
            "type": "JSONDecodeError",
            "message": e.msg,
            "line": e.lineno,
            "column": e.colno
        })

    return result

def parse_yaml(content: str, strict: bool) -> Dict[str, Any]:
    """解析YAML内容"""
    result = {
        "errors": [],
        "warnings": [],
        "structure": {}
    }

    try:
        data = yaml.safe_load(content)

        if isinstance(data, dict):
            result["structure"] = {
                "类型": "YAML对象",
                "键数量": len(data),
                "顶级键": list(data.keys())[:10]
            }

        # 严格模式检查
        if strict:
            # 检查常见问题
            if '\t' in content:
                result["warnings"].append({
                    "type": "yaml_indentation",
                    "message": "YAML不应使用Tab缩进，请使用空格"
                })

    except yaml.YAMLError as e:
        result["errors"].append({
            "type": "YAMLError",
            "message": str(e)
        })

    return result

def parse_markdown(content: str, strict: bool) -> Dict[str, Any]:
    """解析Markdown内容"""
    result = {
        "errors": [],
        "warnings": [],
        "structure": {}
    }

    lines = content.split('\n')

    # 统计Markdown元素
    headers = []
    code_blocks = 0
    links = []
    images = []

    for i, line in enumerate(lines):
        # 标题
        if line.strip().startswith('#'):
            level = len(line) - len(line.lstrip('#'))
            if level <= 6:
                headers.append(f"H{level}: {line.strip('#').strip()}")

        # 代码块
        if line.strip().startswith('```'):
            code_blocks += 1

        # 链接
        link_matches = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', line)
        for text, url in link_matches:
            links.append(f"{text} -> {url}")

        # 图片
        image_matches = re.findall(r'!\[([^\]]*)\]\(([^)]+)\)', line)
        for alt, url in image_matches:
            images.append(f"{alt} -> {url}")

    result["structure"] = {
        "总行数": len(lines),
        "标题数量": len(headers),
        "代码块": code_blocks // 2,  # 每个代码块有开始和结束
        "链接数量": len(links),
        "图片数量": len(images),
        "标题列表": headers[:5]
    }

    # 严格模式检查
    if strict:
        # 检查未闭合的代码块
        if code_blocks % 2 != 0:
            result["errors"].append({
                "type": "unclosed_code_block",
                "message": "存在未闭合的代码块"
            })

    return result

def parse_generic(content: str, strict: bool) -> Dict[str, Any]:
    """解析通用文本文件"""
    result = {
        "errors": [],
        "warnings": [],
        "structure": {}
    }

    lines = content.split('\n')

    # 基础统计
    empty_lines = sum(1 for line in lines if not line.strip())
    non_empty_lines = len(lines) - empty_lines

    result["structure"] = {
        "总行数": len(lines),
        "非空行": non_empty_lines,
        "空行": empty_lines,
        "字符数": len(content),
        "平均行长度": sum(len(line) for line in lines) / len(lines) if lines else 0
    }

    return result

def get_json_depth(obj, current_depth=0):
    """获取JSON数据的嵌套深度"""
    if isinstance(obj, dict):
        if not obj:
            return current_depth
        return max(get_json_depth(v, current_depth + 1) for v in obj.values())
    elif isinstance(obj, list):
        if not obj:
            return current_depth
        return max(get_json_depth(item, current_depth + 1) for item in obj)
    else:
        return current_depth