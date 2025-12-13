"""
文件分析器 - 演示文件类型和内容分析功能
"""

from claude_agent_sdk import tool
from typing import Dict, Any
import os
import json
from pathlib import Path

@tool(
    name="analyze_file",
    description="分析文件的类型、大小、行数等基本信息",
    input_schema={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "要分析的文件路径"
            },
            "analyze_content": {
                "type": "boolean",
                "description": "是否分析文件内容（如代码行数、注释等）",
                "default": False
            }
        },
        "required": ["file_path"]
    }
)
async def analyze_file(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    分析文件的基本信息和内容

    Args:
        args: 包含 file_path 和可选的 analyze_content 字段

    Returns:
        文件分析结果
    """
    file_path = args.get("file_path", "")
    analyze_content = args.get("analyze_content", False)

    try:
        path = Path(file_path)

        if not path.exists():
            return {
                "content": [{
                    "type": "text",
                    "text": f"错误: 文件不存在: {file_path}"
                }],
                "error": "File not found"
            }

        if not path.is_file():
            return {
                "content": [{
                    "type": "text",
                    "text": f"错误: 不是一个文件: {file_path}"
                }],
                "error": "Not a file"
            }

        # 基本文件信息
        stat = path.stat()
        file_size = stat.st_size
        file_ext = path.suffix.lower()
        file_name = path.name

        # 文件类型判断
        type_map = {
            '.py': 'Python',
            '.js': 'JavaScript',
            '.ts': 'TypeScript',
            '.md': 'Markdown',
            '.txt': 'Text',
            '.json': 'JSON',
            '.yaml': 'YAML',
            '.yml': 'YAML',
            '.xml': 'XML',
            '.html': 'HTML',
            '.css': 'CSS',
            '.csv': 'CSV',
            '.log': 'Log'
        }

        file_type = type_map.get(file_ext, 'Unknown')

        analysis = {
            "file_name": file_name,
            "file_path": str(path.absolute()),
            "file_type": file_type,
            "file_size_bytes": file_size,
            "file_size_mb": round(file_size / (1024 * 1024), 3),
            "last_modified": stat.st_mtime
        }

        # 内容分析
        if analyze_content:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()

                lines = content.splitlines()
                total_lines = len(lines)
                non_empty_lines = len([line for line in lines if line.strip()])
                empty_lines = total_lines - non_empty_lines

                analysis.update({
                    "total_lines": total_lines,
                    "non_empty_lines": non_empty_lines,
                    "empty_lines": empty_lines,
                    "character_count": len(content),
                    "word_count": len(content.split())
                })

                # 特定文件类型的额外分析
                if file_ext == '.py':
                    # Python 特定分析
                    import_lines = len([line for line in lines if line.strip().startswith(('import ', 'from '))])
                    class_count = len([line for line in lines if line.strip().startswith('class ')])
                    function_count = len([line for line in lines if line.strip().startswith('def ')])

                    analysis.update({
                        "import_lines": import_lines,
                        "class_count": class_count,
                        "function_count": function_count
                    })

                elif file_ext == '.json':
                    # JSON 验证和结构分析
                    try:
                        json_data = json.loads(content)
                        analysis.update({
                            "is_valid_json": True,
                            "json_type": type(json_data).__name__,
                            "json_keys": list(json_data.keys()) if isinstance(json_data, dict) else None
                        })
                    except:
                        analysis.update({
                            "is_valid_json": False
                        })

            except UnicodeDecodeError:
                analysis["is_binary"] = True
            except Exception as e:
                analysis["content_error"] = str(e)

        # 格式化结果
        result_text = f"""📁 文件分析结果

文件名: {file_name}
类型: {file_type}
大小: {file_size:,} 字节 ({analysis['file_size_mb']} MB)
最后修改: {analysis['last_modified']}"""

        if analyze_content and not analysis.get("is_binary"):
            result_text += f"""

内容统计:
- 总行数: {analysis.get('total_lines', 'N/A')}
- 非空行: {analysis.get('non_empty_lines', 'N/A')}
- 空行: {analysis.get('empty_lines', 'N/A')}
- 字符数: {analysis.get('character_count', 'N/A')}
- 单词数: {analysis.get('word_count', 'N/A')}"""

            if file_ext == '.py' and 'function_count' in analysis:
                result_text += f"""
Python 特定:
- 导入语句: {analysis.get('import_lines', 0)}
- 类定义: {analysis.get('class_count', 0)}
- 函数定义: {analysis.get('function_count', 0)}"""

        return {
            "content": [{
                "type": "text",
                "text": result_text
            }],
            "analysis": analysis
        }

    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"分析文件时出错: {str(e)}"
            }],
            "error": str(e)
        }