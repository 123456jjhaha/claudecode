"""
文件类型检测器工具 - 识别文件的真实类型和格式
"""

from claude_agent_sdk import tool
from typing import Dict, Any, List, Tuple
import os
import mimetypes
import hashlib
from pathlib import Path

# 文件签名（魔术数字）
FILE_SIGNATURES = {
    # 图片格式
    b'\xFF\xD8\xFF': 'image/jpeg',
    b'\x89PNG\r\n\x1a\n': 'image/png',
    b'GIF87a': 'image/gif',
    b'GIF89a': 'image/gif',
    b'RIFF': 'image/webp',  # WebP starts with RIFF
    b'%PDF': 'application/pdf',

    # 压缩格式
    b'PK\x03\x04': 'application/zip',
    b'PK\x05\x06': 'application/zip',
    b'PK\x07\x08': 'application/zip',
    b'\x1f\x8b\x08': 'application/gzip',
    b'BZh': 'application/x-bzip2',
    b'\x37\x7a\xbc\xaf\x27\x1c': 'application/x-7z-compressed',

    # 音频格式
    b'ID3': 'audio/mpeg',
    b'\xFF\xFB': 'audio/mpeg',
    b'\xFF\xF3': 'audio/mpeg',
    b'\xFF\xF2': 'audio/mpeg',
    b'OggS': 'audio/ogg',
    b'fLaC': 'audio/flac',
    b'RIFF': 'audio/wav',  # WAV also starts with RIFF

    # 视频格式
    b'\x00\x00\x00\x18ftypmp42': 'video/mp4',
    b'\x00\x00\x00\x20ftypisom': 'video/mp4',
    b'\x1a\x45\xdf\xa3': 'video/webm',

    # 可执行文件
    b'MZ': 'application/x-msdos-executable',
    b'\x7fELF': 'application/x-executable',
    b'\xca\xfe\xba\xbe': 'application/x-java-applet',

    # 文档格式
    b'PK\x03\x04': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # DOCX
    b'\xD0\xCF\x11\xE0': 'application/msword',  # Old DOC format

    # 数据库
    b'SQLite format 3': 'application/x-sqlite3',
}

@tool(
    name="detect_file_type",
    description="检测文件的真实类型，包括MIME类型、编码和格式信息",
    input_schema={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "要检测的文件路径"
            },
            "deep_scan": {
                "type": "boolean",
                "description": "是否进行深度扫描（读取更多字节进行检测）",
                "default": False
            },
            "calculate_hash": {
                "type": "boolean",
                "description": "是否计算文件哈希值",
                "default": False
            }
        },
        "required": ["file_path"]
    }
)
async def detect_file_type(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    检测文件类型和格式

    Args:
        args: 包含文件路径和分析选项的字典

    Returns:
        文件类型检测结果
    """
    file_path = args.get("file_path", "")
    deep_scan = args.get("deep_scan", False)
    calculate_hash = args.get("calculate_hash", False)

    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return {
                "content": [{
                    "type": "text",
                    "text": f"❌ 错误: 文件不存在 {file_path}"
                }],
                "error": "file_not_found"
            }

        # 获取文件基本信息
        file_stat = os.stat(file_path)
        file_size = file_stat.st_size
        file_path_obj = Path(file_path)

        detection_result = {
            "file_path": file_path,
            "file_name": file_path_obj.name,
            "file_size": file_size,
            "extension": file_path_obj.suffix.lower(),
            "mime_type": None,
            "detected_type": None,
            "encoding": None,
            "is_binary": False,
            "file_hash": None,
            "signatures": []
        }

        # 计算文件哈希（如果需要）
        if calculate_hash:
            detection_result["file_hash"] = calculate_file_hash(file_path)

        # 读取文件头部进行类型检测
        try:
            with open(file_path, 'rb') as f:
                # 读取前1024字节用于检测
                header = f.read(1024)

                # 检测二进制/文本文件
                detection_result["is_binary"] = is_binary_content(header)

                # 基于文件签名检测类型
                detected_mime = detect_by_signature(header)
                if detected_mime:
                    detection_result["detected_type"] = detected_mime
                    detection_result["mime_type"] = detected_mime
                    detection_result["signatures"].append(f"Magic Number: {detected_mime}")

                # 深度扫描（读取更多内容）
                if deep_scan and file_size > 1024:
                    f.seek(0)
                    more_content = f.read(min(file_size, 8192))
                    additional_detection = detect_by_content_analysis(more_content)
                    if additional_detection:
                        detection_result["signatures"].extend(additional_detection)

        except PermissionError:
            detection_result["error"] = "permission_denied"

        # 使用mimetypes进行基础检测
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type and not detection_result["mime_type"]:
            detection_result["mime_type"] = mime_type
            detection_result["signatures"].append(f"Extension: {mime_type}")

        # 检测文本编码（如果是文本文件）
        if not detection_result["is_binary"]:
            encoding = detect_text_encoding(file_path)
            if encoding:
                detection_result["encoding"] = encoding

        # 生成检测报告
        report_lines = [
            f"## 文件类型检测报告",
            f"**文件**: {file_path}",
            f"**大小**: {format_file_size(file_size)}",
            f"**扩展名**: {detection_result['extension'] or '无'}",
            "",
            "### 🔍 检测结果",
            f"- **MIME类型**: {detection_result['mime_type'] or '未知'}",
            f"- **检测类型**: {detection_result['detected_type'] or '未知'}",
            f"- **文件类型**: {'二进制' if detection_result['is_binary'] else '文本'}",
            f"- **编码格式**: {detection_result['encoding'] or '不适用'}",
            ""
        ]

        # 文件签名信息
        if detection_result["signatures"]:
            report_lines.append("### 📋 检测依据")
            for signature in detection_result["signatures"]:
                report_lines.append(f"- {signature}")

        # 文件哈希
        if detection_result["file_hash"]:
            report_lines.extend([
                "",
                "### 🔐 文件哈希",
                f"**SHA256**: {detection_result['file_hash']}"
            ])

        # 类型说明
        type_info = get_type_info(detection_result)
        if type_info:
            report_lines.extend([
                "",
                "### 📚 类型说明",
                type_info
            ])

        # 安全提示
        security_notes = get_security_notes(detection_result)
        if security_notes:
            report_lines.extend([
                "",
                "### ⚠️ 安全提示",
                security_notes
            ])

        return {
            "content": [{
                "type": "text",
                "text": "\n".join(report_lines)
            }],
            "detection_result": detection_result
        }

    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"❌ 检测失败: {str(e)}"
            }],
            "error": str(e)
        }

def is_binary_content(data: bytes) -> bool:
    """检测内容是否为二进制"""
    # 检查null字节
    if b'\x00' in data:
        return True

    # 检查非打印字符比例
    text_chars = sum(1 for b in data if 32 <= b <= 126 or b in [9, 10, 13])
    if len(data) == 0:
        return False

    return text_chars / len(data) < 0.7

def detect_by_signature(data: bytes) -> str:
    """基于文件签名检测类型"""
    for signature, mime_type in FILE_SIGNATURES.items():
        if data.startswith(signature):
            return mime_type
    return None

def detect_by_content_analysis(data: bytes) -> List[str]:
    """通过内容分析检测文件特征"""
    detections = []

    # 检测是否为脚本文件
    try:
        text_data = data.decode('utf-8', errors='ignore')

        # Python脚本
        if text_data.strip().startswith('#!') and 'python' in text_data[:100]:
            detections.append("Python Script (Shebang)")
        elif 'import ' in text_data or 'def ' in text_data or 'class ' in text_data:
            detections.append("Python Source Code (Content)")

        # Shell脚本
        if text_data.strip().startswith('#!') and 'bash' in text_data[:100]:
            detections.append("Bash Script (Shebang)")
        elif 'echo ' in text_data or 'export ' in text_data:
            detections.append("Shell Script (Content)")

        # JSON检测
        if text_data.strip().startswith('{') and text_data.strip().endswith('}'):
            detections.append("JSON Format")

        # XML检测
        if text_data.strip().startswith('<') and text_data.strip().endswith('>'):
            detections.append("XML/HTML Format")

    except UnicodeDecodeError:
        pass

    return detections

def detect_text_encoding(file_path: str) -> str:
    """检测文本文件的编码"""
    try:
        import chardet

        with open(file_path, 'rb') as f:
            raw_data = f.read(10000)  # 读取前10KB
            result = chardet.detect(raw_data)
            if result and result['confidence'] > 0.7:
                return result['encoding']
    except ImportError:
        # 如果没有chardet，使用简单的检测
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                f.read(1000)
            return 'utf-8'
        except UnicodeDecodeError:
            try:
                with open(file_path, 'r', encoding='gbk') as f:
                    f.read(1000)
                return 'gbk'
            except UnicodeDecodeError:
                return 'unknown'
    except Exception:
        pass

    return None

def calculate_file_hash(file_path: str) -> str:
    """计算文件的SHA256哈希值"""
    sha256_hash = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()

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

def get_type_info(detection_result: Dict[str, Any]) -> str:
    """获取文件类型的说明信息"""
    mime_type = detection_result.get("detected_type") or detection_result.get("mime_type")

    type_descriptions = {
        "image/jpeg": "JPEG图像格式，广泛用于照片和复杂图像",
        "image/png": "PNG图像格式，支持透明度，适合图标和简单图形",
        "image/gif": "GIF图像格式，支持动画，适合简单动画图标",
        "application/pdf": "PDF文档格式，保留格式的电子文档",
        "application/zip": "ZIP压缩格式，包含一个或多个压缩文件",
        "application/json": "JSON数据格式，轻量级数据交换格式",
        "text/plain": "纯文本文件，只包含基本文本内容",
        "audio/mpeg": "MP3音频格式，有损压缩音频文件",
        "video/mp4": "MP4视频格式，广泛使用的视频容器格式"
    }

    return type_descriptions.get(mime_type, "未知或自定义文件格式")

def get_security_notes(detection_result: Dict[str, Any]) -> str:
    """获取安全提示信息"""
    notes = []

    # 可执行文件警告
    if detection_result.get("detected_type") in [
        "application/x-msdos-executable",
        "application/x-executable"
    ]:
        notes.append("⚠️ 这是一个可执行文件，运行前请确保来源安全")

    # 脚本文件提示
    if detection_result.get("extension") in ['.bat', '.cmd', '.ps1', '.sh']:
        notes.append("⚠️ 这是一个脚本文件，执行前请检查内容")

    # 大文件提示
    if detection_result.get("file_size", 0) > 100 * 1024 * 1024:  # 100MB
        notes.append("📊 这是一个大文件，处理时请注意内存使用")

    return "\n".join(notes) if notes else None