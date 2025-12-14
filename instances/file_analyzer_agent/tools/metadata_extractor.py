"""
元数据提取器工具 - 从文件中提取元数据和属性信息
"""

from typing import Dict, Any, Optional
import os
import json
import time
from datetime import datetime
from pathlib import Path
import re

async def extract_metadata(file_path: str, extract_exif: bool = False, extract_document_props: bool = True, include_file_hash: bool = False) -> Dict[str, Any]:
    """
    提取文件元数据

    Args:
        file_path: 要提取元数据的文件路径
        extract_exif: 是否提取图像EXIF数据（如果适用）
        extract_document_props: 是否提取文档属性（如果适用）
        include_file_hash: 是否计算文件哈希值

    Returns:
        提取的元数据
    """
    try:
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": "file_not_found",
                "message": f"文件不存在: {file_path}"
            }

        # 初始化元数据结构
        metadata = {
            "file_path": file_path,
            "file_system": {},
            "content_metadata": {},
            "format_specific": {},
            "security": {},
            "file_hash": None
        }

        # 提取文件系统元数据
        metadata["file_system"] = extract_filesystem_metadata(file_path)

        # 提取内容元数据
        metadata["content_metadata"] = extract_content_metadata(file_path)

        # 提取格式特定元数据
        file_ext = os.path.splitext(file_path)[1].lower()
        metadata["format_specific"] = extract_format_metadata(
            file_path, file_ext, extract_exif, extract_document_props
        )

        # 计算文件哈希（如果需要）
        if include_file_hash:
            metadata["file_hash"] = calculate_file_hashes(file_path)

        # 安全相关信息
        metadata["security"] = extract_security_metadata(file_path)

        # 生成报告
        report = generate_metadata_report(metadata)

        return {
            "success": True,
            "metadata": metadata,
            "report": report
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"元数据提取失败: {str(e)}"
        }

async def quick_metadata(file_path: str) -> Dict[str, Any]:
    """
    快速获取基础元数据

    Args:
        file_path: 文件路径

    Returns:
        基础元数据
    """
    try:
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": "file_not_found",
                "message": f"文件不存在: {file_path}"
            }

        # 只提取基础信息
        stat = os.stat(file_path)
        file_path_obj = Path(file_path)

        # MIME类型检测
        import mimetypes
        mime_type, _ = mimetypes.guess_type(file_path)

        # 简单的内容检测
        is_text = False
        encoding = None
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                f.read(100)  # 尝试读取前100字符
                is_text = True
                encoding = 'utf-8'
        except:
            pass

        return {
            "success": True,
            "file_path": file_path,
            "basic_info": {
                "name": file_path_obj.name,
                "size": stat.st_size,
                "size_formatted": format_file_size(stat.st_size),
                "extension": file_path_obj.suffix.lower(),
                "mime_type": mime_type,
                "modified": format_timestamp(stat.st_mtime),
                "is_text": is_text,
                "encoding": encoding
            }
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"获取基础元数据失败: {str(e)}"
        }

def extract_filesystem_metadata(file_path: str) -> Dict[str, Any]:
    """提取文件系统元数据"""
    stat = os.stat(file_path)
    file_path_obj = Path(file_path)

    return {
        "name": os.path.basename(file_path),
        "size": stat.st_size,
        "size_formatted": format_file_size(stat.st_size),
        "created": format_timestamp(stat.st_ctime),
        "modified": format_timestamp(stat.st_mtime),
        "accessed": format_timestamp(stat.st_atime),
        "extension": os.path.splitext(file_path)[1].lower(),
        "is_file": os.path.isfile(file_path),
        "is_readable": os.access(file_path, os.R_OK),
        "is_writable": os.access(file_path, os.W_OK),
        "is_executable": os.access(file_path, os.X_OK),
        "permissions": oct(stat.st_mode)[-3:],
        "inode": stat.st_ino,
        "device": stat.st_dev
    }

def extract_content_metadata(file_path: str) -> Dict[str, Any]:
    """提取内容元数据"""
    content_metadata = {
        "encoding": None,
        "line_count": 0,
        "character_count": 0,
        "word_count": 0,
        "language": None,
        "mime_type": None,
        "is_binary": False
    }

    try:
        # 尝试以文本方式读取
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read(1024)  # 只读取前1KB进行检测
            content_metadata["encoding"] = "utf-8"

            # 简单的语言检测
            if content.strip():
                lines = content.split('\n')
                content_metadata["line_count"] = len(lines)
                content_metadata["character_count"] = len(content)
                content_metadata["word_count"] = len(content.split())

                # 基于内容的语言检测
                if 'def ' in content or 'import ' in content:
                    content_metadata["language"] = "Python"
                elif 'function ' in content or 'var ' in content:
                    content_metadata["language"] = "JavaScript"
                elif content.strip().startswith('<') and content.strip().endswith('>'):
                    content_metadata["language"] = "HTML/XML"
                elif content.strip().startswith('{') or content.strip().startswith('#'):
                    content_metadata["language"] = "Data/Config"

    except UnicodeDecodeError:
        # 二进制文件
        content_metadata["is_binary"] = True
        content_metadata["encoding"] = "binary"

    # MIME类型检测
    import mimetypes
    mime_type, _ = mimetypes.guess_type(file_path)
    content_metadata["mime_type"] = mime_type

    return content_metadata

def extract_format_metadata(file_path: str, file_ext: str,
                          extract_exif: bool, extract_document_props: bool) -> Dict[str, Any]:
    """提取格式特定的元数据"""
    format_metadata = {
        "format": file_ext,
        "metadata_available": False,
        "properties": {}
    }

    try:
        # 图像文件EXIF数据
        if file_ext in ['.jpg', '.jpeg', '.png', '.tiff', '.bmp'] and extract_exif:
            exif_data = extract_image_exif(file_path)
            if exif_data:
                format_metadata["properties"]["exif"] = exif_data
                format_metadata["metadata_available"] = True

        # PDF文档属性
        elif file_ext == '.pdf' and extract_document_props:
            pdf_props = extract_pdf_properties(file_path)
            if pdf_props:
                format_metadata["properties"]["pdf"] = pdf_props
                format_metadata["metadata_available"] = True

        # JSON文件结构
        elif file_ext == '.json':
            json_props = extract_json_properties(file_path)
            if json_props:
                format_metadata["properties"]["json"] = json_props
                format_metadata["metadata_available"] = True

        # 音频文件元数据
        elif file_ext in ['.mp3', '.flac', '.wav']:
            audio_props = extract_audio_properties(file_path)
            if audio_props:
                format_metadata["properties"]["audio"] = audio_props
                format_metadata["metadata_available"] = True

        # 视频文件元数据
        elif file_ext in ['.mp4', '.avi', '.mkv']:
            video_props = extract_video_properties(file_path)
            if video_props:
                format_metadata["properties"]["video"] = video_props
                format_metadata["metadata_available"] = True

    except Exception as e:
        format_metadata["extraction_error"] = str(e)

    return format_metadata

def extract_image_exif(file_path: str) -> Optional[Dict[str, Any]]:
    """提取图像EXIF数据"""
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS

        with Image.open(file_path) as image:
            exif_data = {}

            # 基本信息
            exif_data["format"] = image.format
            exif_data["mode"] = image.mode
            exif_data["size"] = image.size

            # EXIF数据
            if hasattr(image, '_getexif') and image._getexif():
                exif = image._getexif()
                for tag_id, value in exif.items():
                    tag = TAGS.get(tag_id, tag_id)
                    # 过滤掉二进制数据
                    if isinstance(value, (str, int, float, tuple)):
                        exif_data[tag] = value

            return exif_data

    except ImportError:
        return {"error": "PIL库未安装，无法提取EXIF数据"}
    except Exception:
        return {"error": "无法提取EXIF数据"}

def extract_pdf_properties(file_path: str) -> Optional[Dict[str, Any]]:
    """提取PDF属性"""
    try:
        import PyPDF2

        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)

            pdf_props = {
                "page_count": len(reader.pages),
                "is_encrypted": reader.is_encrypted,
                "pdf_version": getattr(reader, 'pdf_header', {}).get('version', 'Unknown')
            }

            # 元数据
            if reader.metadata:
                metadata = reader.metadata
                pdf_props["metadata"] = {
                    "title": metadata.get('/Title', ''),
                    "author": metadata.get('/Author', ''),
                    "subject": metadata.get('/Subject', ''),
                    "creator": metadata.get('/Creator', ''),
                    "producer": metadata.get('/Producer', ''),
                    "creation_date": str(metadata.get('/CreationDate', '')),
                    "modification_date": str(metadata.get('/ModDate', ''))
                }

            return pdf_props

    except ImportError:
        return {"error": "PyPDF2库未安装，无法提取PDF属性"}
    except Exception as e:
        return {"error": f"无法提取PDF属性: {str(e)}"}

def extract_json_properties(file_path: str) -> Optional[Dict[str, Any]]:
    """提取JSON结构属性"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        def analyze_structure(obj, depth=0):
            if depth > 5:  # 限制深度
                return {"type": "max_depth_reached"}

            if isinstance(obj, dict):
                return {
                    "type": "object",
                    "key_count": len(obj),
                    "keys": list(obj.keys())[:10],  # 只显示前10个键
                    "sample_structure": {
                        key: analyze_structure(value, depth + 1)
                        for key, value in list(obj.items())[:5]  # 只分析前5个值
                    }
                }
            elif isinstance(obj, list):
                return {
                    "type": "array",
                    "length": len(obj),
                    "sample_items": [
                        analyze_structure(item, depth + 1)
                        for item in obj[:3]  # 只分析前3个元素
                    ]
                }
            else:
                return {
                    "type": type(obj).__name__,
                    "sample_value": str(obj)[:50] if len(str(obj)) > 50 else str(obj)
                }

        return {
            "structure": analyze_structure(data),
            "total_size": len(str(data))
        }

    except json.JSONDecodeError as e:
        return {"error": f"JSON解析错误: {str(e)}"}
    except Exception as e:
        return {"error": f"无法分析JSON结构: {str(e)}"}

def extract_audio_properties(file_path: str) -> Optional[Dict[str, Any]]:
    """提取音频属性"""
    try:
        import mutagen

        audio_file = mutagen.File(file_path)
        if audio_file is None:
            return {"error": "无法识别的音频格式"}

        properties = {
            "format": audio_file.format if hasattr(audio_file, 'format') else 'Unknown',
            "length": getattr(audio_file, 'info', {}).get('length', 0),
            "bitrate": getattr(audio_file, 'info', {}).get('bitrate', 0),
            "sample_rate": getattr(audio_file, 'info', {}).get('sample_rate', 0),
            "channels": getattr(audio_file, 'info', {}).get('channels', 0)
        }

        # 标签信息
        if audio_file.tags:
            tags = {}
            for key, value in audio_file.tags.items():
                if isinstance(value, list) and value:
                    tags[key] = str(value[0])
                else:
                    tags[key] = str(value)
            properties["tags"] = tags

        return properties

    except ImportError:
        return {"error": "mutagen库未安装，无法提取音频属性"}
    except Exception as e:
        return {"error": f"无法提取音频属性: {str(e)}"}

def extract_video_properties(file_path: str) -> Optional[Dict[str, Any]]:
    """提取视频属性"""
    try:
        import cv2

        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            return {"error": "无法打开视频文件"}

        properties = {
            "fps": cap.get(cv2.CAP_PROP_FPS),
            "frame_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "duration": cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS) if cap.get(cv2.CAP_PROP_FPS) > 0 else 0
        }

        cap.release()
        return properties

    except ImportError:
        return {"error": "OpenCV库未安装，无法提取视频属性"}
    except Exception as e:
        return {"error": f"无法提取视频属性: {str(e)}"}

def extract_security_metadata(file_path: str) -> Dict[str, Any]:
    """提取安全相关元数据"""
    security_info = {}

    try:
        # 文件权限
        stat = os.stat(file_path)
        security_info["permissions"] = {
            "owner_read": bool(stat.st_mode & 0o400),
            "owner_write": bool(stat.st_mode & 0o200),
            "owner_execute": bool(stat.st_mode & 0o100),
            "group_read": bool(stat.st_mode & 0o040),
            "group_write": bool(stat.st_mode & 0o020),
            "group_execute": bool(stat.st_mode & 0o010),
            "other_read": bool(stat.st_mode & 0o004),
            "other_write": bool(stat.st_mode & 0o002),
            "other_execute": bool(stat.st_mode & 0o001)
        }

        # 文件扩展名安全检查
        dangerous_extensions = ['.exe', '.bat', '.cmd', '.scr', '.vbs', '.js', '.jar']
        ext = os.path.splitext(file_path)[1].lower()
        security_info["potentially_dangerous"] = ext in dangerous_extensions

        # 文件名安全检查
        suspicious_patterns = [
            r'.*\.(exe|scr|bat|cmd)$',
            r'.*\.part$',
            r'.*\.temp$',
            r'.*~$',
            r'^\.'
        ]

        security_info["suspicious_name"] = any(
            re.match(pattern, os.path.basename(file_path), re.IGNORECASE)
            for pattern in suspicious_patterns
        )

    except Exception as e:
        security_info["error"] = str(e)

    return security_info

def calculate_file_hashes(file_path: str) -> Dict[str, str]:
    """计算文件的各种哈希值"""
    import hashlib

    hashes = {}

    # MD5
    md5_hash = hashlib.md5()
    # SHA1
    sha1_hash = hashlib.sha1()
    # SHA256
    sha256_hash = hashlib.sha256()

    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            md5_hash.update(chunk)
            sha1_hash.update(chunk)
            sha256_hash.update(chunk)

    hashes["md5"] = md5_hash.hexdigest()
    hashes["sha1"] = sha1_hash.hexdigest()
    hashes["sha256"] = sha256_hash.hexdigest()

    return hashes

def format_timestamp(timestamp: float) -> str:
    """格式化时间戳"""
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

def format_file_size(size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes == 0:
        return "0 B"

    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1

    return f"{size_bytes:.2f} {size_names[i]}"

def generate_metadata_report(metadata: Dict[str, Any]) -> str:
    """生成元数据报告"""
    report_lines = [
        "## 文件元数据报告",
        f"**文件**: {metadata['file_path']}",
        ""
    ]

    # 文件系统信息
    fs = metadata.get("file_system", {})
    report_lines.extend([
        "### 📁 文件系统信息",
        f"- **名称**: {fs.get('name', 'Unknown')}",
        f"- **大小**: {fs.get('size_formatted', 'Unknown')}",
        f"- **创建时间**: {fs.get('created', 'Unknown')}",
        f"- **修改时间**: {fs.get('modified', 'Unknown')}",
        f"- **权限**: {fs.get('permissions', 'Unknown')}",
        ""
    ])

    # 内容信息
    content = metadata.get("content_metadata", {})
    report_lines.extend([
        "### 📄 内容信息",
        f"- **类型**: {content.get('mime_type', 'Unknown')}",
        f"- **编码**: {content.get('encoding', 'Unknown')}",
        f"- **语言**: {content.get('language', 'Unknown')}",
        f"- **字符数**: {content.get('character_count', 0)}",
        f"- **行数**: {content.get('line_count', 0)}",
        ""
    ])

    # 格式特定信息
    format_meta = metadata.get("format_specific", {})
    if format_meta.get("metadata_available"):
        report_lines.append("### 🎯 格式特定信息")
        properties = format_meta.get("properties", {})

        for format_type, props in properties.items():
            if isinstance(props, dict) and "error" not in props:
                report_lines.append(f"**{format_type.upper()}属性**:")
                for key, value in props.items():
                    if key != "error" and value:
                        report_lines.append(f"- {key}: {value}")
        report_lines.append("")

    # 安全信息
    security = metadata.get("security", {})
    if security:
        report_lines.extend([
            "### 🔒 安全信息",
            f"- **潜在危险**: {'是' if security.get('potentially_dangerous') else '否'}",
            f"- **可疑名称**: {'是' if security.get('suspicious_name') else '否'}",
            ""
        ])

    # 文件哈希
    if metadata.get("file_hash"):
        file_hash = metadata["file_hash"]
        report_lines.extend([
            "### 🔐 文件哈希",
            f"- **MD5**: {file_hash.get('md5', 'Unknown')}",
            f"- **SHA256**: {file_hash.get('sha256', 'Unknown')}",
            ""
        ])

    return "\n".join(report_lines)