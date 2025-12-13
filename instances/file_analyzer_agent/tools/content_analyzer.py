"""
内容分析器工具 - 深度分析文件内容和结构
"""

from claude_agent_sdk import tool
from typing import Dict, Any, List, Union
import re
import json
import ast
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

@tool(
    name="analyze_content",
    description="深度分析文件内容，提取结构、统计和语义信息",
    input_schema={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "要分析的文件路径"
            },
            "analysis_depth": {
                "type": "string",
                "description": "分析深度",
                "enum": ["basic", "detailed", "full"],
                "default": "detailed"
            },
            "include_statistics": {
                "type": "boolean",
                "description": "是否包含统计分析",
                "default": True
            },
            "max_sample_size": {
                "type": "integer",
                "description": "大文件的最大采样大小（KB）",
                "default": 1000
            }
        },
        "required": ["file_path"]
    }
)
async def analyze_content(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    分析文件内容和结构

    Args:
        args: 包含文件路径和分析选项的字典

    Returns:
        内容分析结果
    """
    file_path = args.get("file_path", "")
    analysis_depth = args.get("analysis_depth", "detailed")
    include_statistics = args.get("include_statistics", True)
    max_sample_size = args.get("max_sample_size", 1000)

    try:
        # 读取文件内容
        content, is_sampled = read_file_content(file_path, max_sample_size * 1024)

        # 获取文件类型
        file_type = detect_content_type(file_path, content)

        analysis_result = {
            "file_path": file_path,
            "file_type": file_type,
            "content_size": len(content),
            "is_sampled": is_sampled,
            "analysis_depth": analysis_depth,
            "structure": {},
            "statistics": {},
            "patterns": {},
            "metadata": {}
        }

        # 根据文件类型选择分析方法
        if file_type in ["python", "javascript", "java", "cpp"]:
            result = analyze_code_content(content, file_type, analysis_depth)
        elif file_type in ["json", "yaml", "xml", "csv"]:
            result = analyze_structured_data(content, file_type, analysis_depth)
        elif file_type in ["markdown", "html", "txt"]:
            result = analyze_text_content(content, file_type, analysis_depth)
        else:
            result = analyze_generic_content(content, file_type, analysis_depth)

        analysis_result.update(result)

        # 添加统计分析
        if include_statistics:
            analysis_result["statistics"] = calculate_content_statistics(content)

        # 生成报告
        report = generate_analysis_report(analysis_result)

        return {
            "content": [{
                "type": "text",
                "text": report
            }],
            "analysis_result": analysis_result
        }

    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"❌ 分析失败: {str(e)}"
            }],
            "error": str(e)
        }

def read_file_content(file_path: str, max_size: int) -> tuple[str, bool]:
    """读取文件内容，大文件进行采样"""
    try:
        # 尝试以文本方式读取
        with open(file_path, 'r', encoding='utf-8') as f:
            # 检查文件大小
            f.seek(0, 2)  # 移到文件末尾
            size = f.tell()
            f.seek(0)  # 回到开头

            if size <= max_size:
                return f.read(), False
            else:
                # 大文件采样读取
                sample_size = max_size // 2
                # 读取开头部分
                head = f.read(sample_size)
                # 读取末尾部分
                f.seek(max(0, size - sample_size))
                tail = f.read(sample_size)
                return head + "\n...[内容省略]...\n" + tail, True

    except UnicodeDecodeError:
        # 尝试二进制模式读取并转换
        with open(file_path, 'rb') as f:
            content = f.read(max_size)
            try:
                return content.decode('utf-8', errors='ignore'), True
            except:
                return str(content), True

def detect_content_type(file_path: str, content: str) -> str:
    """检测内容类型"""
    ext = file_path.split('.')[-1].lower()

    # 基于扩展名的基础检测
    ext_map = {
        'py': 'python',
        'js': 'javascript',
        'java': 'java',
        'cpp': 'cpp',
        'c': 'cpp',
        'h': 'cpp',
        'json': 'json',
        'yaml': 'yaml',
        'yml': 'yaml',
        'xml': 'xml',
        'csv': 'csv',
        'md': 'markdown',
        'html': 'html',
        'htm': 'html',
        'txt': 'txt'
    }

    # 基于内容的检测
    content = content.strip()
    if content.startswith('def ') or content.startswith('import ') or 'def ' in content:
        return 'python'
    elif content.startswith('function ') or 'function ' in content:
        return 'javascript'
    elif content.startswith('{') and content.endswith('}'):
        return 'json'
    elif content.startswith('#') and ':' in content:
        return 'yaml'
    elif content.startswith('<') and content.endswith('>'):
        return 'xml'
    elif content.startswith('# ') or content.startswith('## '):
        return 'markdown'

    return ext_map.get(ext, 'unknown')

def analyze_code_content(content: str, language: str, depth: str) -> Dict[str, Any]:
    """分析代码内容"""
    result = {
        "structure": {},
        "patterns": {},
        "metadata": {}
    }

    try:
        if language == "python":
            # Python特定分析
            tree = ast.parse(content)

            # 统计结构元素
            functions = []
            classes = []
            imports = []
            decorators = []

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    functions.append({
                        "name": node.name,
                        "line": node.lineno,
                        "args": len(node.args.args),
                        "has_docstring": ast.get_docstring(node) is not None
                    })
                elif isinstance(node, ast.ClassDef):
                    classes.append({
                        "name": node.name,
                        "line": node.lineno,
                        "methods": len([n for n in node.body if isinstance(n, ast.FunctionDef)])
                    })
                elif isinstance(node, ast.Import):
                    imports.extend([alias.name for alias in node.names])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)

            result["structure"] = {
                "functions": functions,
                "classes": classes,
                "imports": list(set(imports))
            }

            # 代码模式分析
            lines = content.split('\n')
            comment_lines = sum(1 for line in lines if line.strip().startswith('#'))
            blank_lines = sum(1 for line in lines if not line.strip())

            result["patterns"] = {
                "comment_ratio": comment_lines / len(lines) if lines else 0,
                "blank_line_ratio": blank_lines / len(lines) if lines else 0,
                "avg_line_length": sum(len(line) for line in lines) / len(lines) if lines else 0
            }

        elif language == "javascript":
            # JavaScript特定分析
            functions = re.findall(r'(?:function\s+(\w+)|(\w+)\s*=\s*(?:function|\([^)]*\)\s*=>))', content)
            result["structure"]["functions"] = [f[0] or f[1] for f in functions if f[0] or f[1]]

            # 模式检测
            result["patterns"] = {
                "has_arrow_functions": '=>' in content,
                "has_async_await": 'async ' in content and 'await ' in content,
                "has_es6_imports": 'import ' in content
            }

    except Exception as e:
        result["parse_error"] = str(e)

    return result

def analyze_structured_data(content: str, format_type: str, depth: str) -> Dict[str, Any]:
    """分析结构化数据"""
    result = {
        "structure": {},
        "patterns": {},
        "metadata": {}
    }

    try:
        if format_type == "json":
            data = json.loads(content)

            def analyze_json_structure(obj, path="root"):
                structure = {}

                if isinstance(obj, dict):
                    structure["type"] = "object"
                    structure["keys"] = list(obj.keys())
                    structure["key_count"] = len(obj)
                    if depth == "full":
                        structure["children"] = {
                            key: analyze_json_structure(value, f"{path}.{key}")
                            for key, value in list(obj.items())[:10]  # 限制深度
                        }
                elif isinstance(obj, list):
                    structure["type"] = "array"
                    structure["length"] = len(obj)
                    structure["item_types"] = list(set(type(item).__name__ for item in obj[:10]))
                else:
                    structure["type"] = type(obj).__name__
                    structure["value"] = str(obj)[:100]  # 截断长值

                return structure

            result["structure"] = analyze_json_structure(data)

        elif format_type in ["yaml", "yml"]:
            # 简单的YAML结构分析
            lines = content.split('\n')
            indent_levels = [len(line) - len(line.lstrip()) for line in lines if line.strip()]
            max_indent = max(indent_levels) if indent_levels else 0

            result["structure"] = {
                "type": "yaml",
                "max_indent_level": max_indent // 2 if max_indent else 0,  # 假设2空格缩进
                "line_count": len(lines),
                "has_comments": any(line.strip().startswith('#') for line in lines)
            }

        elif format_type == "xml":
            # XML结构分析
            root = ET.fromstring(content)

            def count_elements(element):
                count = 1
                for child in element:
                    count += count_elements(child)
                return count

            result["structure"] = {
                "type": "xml",
                "root_tag": root.tag,
                "element_count": count_elements(root),
                "has_attributes": bool(root.attrib),
                "namespace": root.tag.split('}')[0][1:] if '}' in root.tag else None
            }

        elif format_type == "csv":
            # CSV结构分析
            lines = content.split('\n')
            non_empty_lines = [line for line in lines if line.strip()]

            if non_empty_lines:
                headers = non_empty_lines[0].split(',')
                result["structure"] = {
                    "type": "csv",
                    "row_count": len(non_empty_lines) - 1,
                    "column_count": len(headers),
                    "headers": headers,
                    "has_header": True
                }

    except Exception as e:
        result["parse_error"] = str(e)

    return result

def analyze_text_content(content: str, format_type: str, depth: str) -> Dict[str, Any]:
    """分析文本内容"""
    result = {
        "structure": {},
        "patterns": {},
        "metadata": {}
    }

    lines = content.split('\n')
    words = re.findall(r'\b\w+\b', content)
    sentences = re.split(r'[.!?]+', content)

    if format_type == "markdown":
        # Markdown特定分析
        headers = re.findall(r'^(#{1,6})\s+(.+)$', content, re.MULTILINE)
        code_blocks = re.findall(r'```', content)
        links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', content)

        result["structure"] = {
            "headers": [{"level": len(h[0]), "text": h[1]} for h in headers],
            "code_block_count": len(code_blocks) // 2,
            "link_count": len(links)
        }

    elif format_type == "html":
        # HTML特定分析
        tags = re.findall(r'<(\w+)', content)
        tag_counts = Counter(tags)

        result["structure"] = {
            "tag_distribution": dict(tag_counts.most_common(10)),
            "has_doctype": content.strip().lower().startswith('<!doctype')
        }

    # 通用文本分析
    result["patterns"] = {
        "word_count": len(words),
        "sentence_count": len([s for s in sentences if s.strip()]),
        "avg_word_length": sum(len(word) for word in words) / len(words) if words else 0,
        "unique_words": len(set(word.lower() for word in words))
    }

    return result

def analyze_generic_content(content: str, format_type: str, depth: str) -> Dict[str, Any]:
    """分析通用内容"""
    result = {
        "structure": {},
        "patterns": {},
        "metadata": {}
    }

    lines = content.split('\n')
    chars = list(content)

    # 基础统计
    result["structure"] = {
        "line_count": len(lines),
        "non_empty_lines": len([line for line in lines if line.strip()]),
        "max_line_length": max(len(line) for line in lines) if lines else 0
    }

    # 字符分析
    char_types = {
        "letters": sum(1 for c in chars if c.isalpha()),
        "digits": sum(1 for c in chars if c.isdigit()),
        "spaces": sum(1 for c in chars if c.isspace()),
        "punctuation": sum(1 for c in chars if not c.isalnum() and not c.isspace())
    }

    result["patterns"] = {
        "character_distribution": char_types,
        "readability": "high" if char_types["spaces"] > len(chars) * 0.15 else "low"
    }

    return result

def calculate_content_statistics(content: str) -> Dict[str, Any]:
    """计算内容统计信息"""
    lines = content.split('\n')
    chars = list(content)
    words = re.findall(r'\b\w+\b', content)

    return {
        "line_count": len(lines),
        "character_count": len(chars),
        "word_count": len(words),
        "avg_line_length": sum(len(line) for line in lines) / len(lines) if lines else 0,
        "empty_lines": sum(1 for line in lines if not line.strip()),
        "unicode_chars": sum(1 for c in chars if ord(c) > 127),
        "printable_chars": sum(1 for c in chars if c.isprintable())
    }

def generate_analysis_report(result: Dict[str, Any]) -> str:
    """生成分析报告"""
    report_lines = [
        f"## 内容分析报告",
        f"**文件**: {result['file_path']}",
        f"**类型**: {result['file_type']}",
        f"**内容大小**: {len(str(result.get('content_size', 0)))} 字符",
        f"**分析深度**: {result['analysis_depth']}",
        ""
    ]

    # 基础统计
    if "statistics" in result:
        stats = result["statistics"]
        report_lines.extend([
            "### 📊 基础统计",
            f"- **行数**: {stats.get('line_count', 0)}",
            f"- **字符数**: {stats.get('character_count', 0)}",
            f"- **单词数**: {stats.get('word_count', 0)}",
            f"- **平均行长度**: {stats.get('avg_line_length', 0):.1f}",
            ""
        ])

    # 结构分析
    if "structure" in result and result["structure"]:
        report_lines.append("### 🏗️ 结构分析")
        structure = result["structure"]

        if "functions" in structure:
            report_lines.append(f"- **函数数量**: {len(structure['functions'])}")
        if "classes" in structure:
            report_lines.append(f"- **类数量**: {len(structure['classes'])}")
        if "type" in structure:
            report_lines.append(f"- **数据类型**: {structure['type']}")

        report_lines.append("")

    # 模式分析
    if "patterns" in result and result["patterns"]:
        report_lines.append("### 🎯 内容模式")
        patterns = result["patterns"]

        for key, value in patterns.items():
            if isinstance(value, float):
                report_lines.append(f"- **{key}**: {value:.2f}")
            else:
                report_lines.append(f"- **{key}**: {value}")

    # 采样提示
    if result.get("is_sampled"):
        report_lines.extend([
            "",
            "ℹ️ **注意**: 此文件过大，分析基于采样内容"
        ])

    return "\n".join(report_lines)