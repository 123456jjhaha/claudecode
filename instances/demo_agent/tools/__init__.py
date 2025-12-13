"""
Demo Agent 自定义工具包

包含以下工具：
- calculator: 数学计算工具
- file_analyzer: 文件分析工具
- text_processor: 文本处理工具
"""

from .calculator import calculator_add
from .file_analyzer import analyze_file
from .text_processor import count_words, extract_keywords

__all__ = [
    "calculator_add",
    "analyze_file",
    "count_words",
    "extract_keywords"
]