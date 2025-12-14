"""
文件分析工具 - 使用 FastMCP 原生格式
"""

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any

async def analyze_file(file_path: str) -> dict:
    """
    分析文件的基本信息

    Args:
        file_path: 要分析的文件路径

    Returns:
        文件分析结果
    """
    path = Path(file_path)

    if not path.exists():
        return {
            "error": "文件不存在",
            "file_path": file_path
        }

    try:
        # 获取文件统计信息
        stat = path.stat()

        # 读取文件内容（仅对文本文件）
        content_preview = ""
        line_count = 0

        if path.is_file() and path.stat().st_size < 1024 * 1024:  # 只读取小于1MB的文件
            try:
                # 尝试以文本模式读取
                with open(path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    line_count = len(lines)
                    content_preview = ''.join(lines[:5])  # 前5行预览
                    if len(lines) > 5:
                        content_preview += f"\n... ({len(lines)-5} more lines)"
            except UnicodeDecodeError:
                # 二进制文件
                content_preview = "[二进制文件]"

        result = {
            "file_path": str(path.absolute()),
            "file_name": path.name,
            "file_size": stat.st_size,
            "file_type": "directory" if path.is_dir() else "file",
            "last_modified": stat.st_mtime,
            "line_count": line_count,
            "content_preview": content_preview
        }

        # 如果是目录，统计子项目
        if path.is_dir():
            try:
                items = list(path.iterdir())
                result.update({
                    "items_count": len(items),
                    "subdirectories": sum(1 for item in items if item.is_dir()),
                    "files": sum(1 for item in items if item.is_file())
                })
            except PermissionError:
                result["error"] = "无权限访问目录内容"

        return result

    except Exception as e:
        return {
            "error": str(e),
            "file_path": file_path
        }

async def list_directory(dir_path: str, show_hidden: bool = False) -> dict:
    """
    列出目录内容

    Args:
        dir_path: 目录路径
        show_hidden: 是否显示隐藏文件

    Returns:
        目录内容列表
    """
    path = Path(dir_path)

    if not path.exists():
        return {
            "error": "目录不存在",
            "dir_path": dir_path
        }

    if not path.is_dir():
        return {
            "error": "路径不是目录",
            "dir_path": dir_path
        }

    try:
        items = []
        for item in path.iterdir():
            if not show_hidden and item.name.startswith('.'):
                continue

            item_stat = item.stat()
            items.append({
                "name": item.name,
                "type": "directory" if item.is_dir() else "file",
                "size": item_stat.st_size if item.is_file() else 0,
                "last_modified": item_stat.st_mtime
            })

        # 按类型和名称排序
        items.sort(key=lambda x: (x["type"], x["name"].lower()))

        return {
            "dir_path": str(path.absolute()),
            "items": items,
            "total_count": len(items)
        }

    except PermissionError:
        return {
            "error": "无权限访问目录",
            "dir_path": dir_path
        }
    except Exception as e:
        return {
            "error": str(e),
            "dir_path": dir_path
        }