"""
日志配置模块

提供统一的日志配置和日志记录器
"""

import logging
import sys
from pathlib import Path


# 默认日志格式
DEFAULT_FORMAT = "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logger(
    name: str = "claude_agent_system",
    level: int = logging.INFO,
    log_file: Path | None = None,
    format_string: str = DEFAULT_FORMAT,
    date_format: str = DEFAULT_DATE_FORMAT
) -> logging.Logger:
    """
    设置并返回日志记录器

    Args:
        name: 日志记录器名称
        level: 日志级别
        log_file: 日志文件路径（可选）
        format_string: 日志格式
        date_format: 日期格式

    Returns:
        配置好的日志记录器
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 避免重复添加处理器
    if logger.handlers:
        return logger

    # 创建格式化器
    formatter = logging.Formatter(format_string, date_format)

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件处理器（如果指定了日志文件）
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str = "claude_agent_system") -> logging.Logger:
    """
    获取日志记录器

    Args:
        name: 日志记录器名称

    Returns:
        日志记录器
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        # 如果没有配置过，使用默认配置
        return setup_logger(name)
    return logger


def set_log_level(level: int | str, logger_name: str = "claude_agent_system"):
    """
    设置指定日志记录器的级别

    Args:
        level: 日志级别（可以是 int 或 str，如 "INFO", "DEBUG"）
        logger_name: 日志记录器名称（默认为根日志记录器）
    """
    if isinstance(level, str):
        level = getattr(logging, level.upper())

    logger = get_logger(logger_name)
    logger.setLevel(level)
    for handler in logger.handlers:
        handler.setLevel(level)
