"""
File Analyzer Agent 自定义工具包

包含文件分析相关的专业工具：
- file_detector: 文件类型检测器
- content_analyzer: 内容分析器
- metadata_extractor: 元数据提取器
"""

from .file_detector import detect_file_type
from .content_analyzer import analyze_content
from .metadata_extractor import extract_metadata

__all__ = ["detect_file_type", "analyze_content", "extract_metadata"]