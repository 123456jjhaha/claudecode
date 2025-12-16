"""
会话工具模块

提供会话相关的工具函数和数据类
"""

import secrets
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict


def generate_session_id() -> str:
    """
    生成会话 ID

    格式：{timestamp}_{counter}_{short_hash}
    示例：20251211T061755_0001_a3f9c2d8

    Returns:
        会话 ID 字符串
    """
    # ISO 8601 格式时间戳（精确到秒）
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")

    # 4位数字计数器（同一秒内递增）
    # 使用纳秒的后4位作为简单计数器
    counter = f"{datetime.now().microsecond % 10000:04d}"

    # 8位随机十六进制字符串
    short_hash = secrets.token_hex(4)

    return f"{timestamp}_{counter}_{short_hash}"


@dataclass
class Statistics:
    """会话统计信息"""
    total_duration_ms: int = 0
    api_duration_ms: int = 0
    num_turns: int = 0
    num_messages: int = 0
    num_tool_calls: int = 0
    tools_used: Dict[str, int] = None
    subsessions: List[Dict[str, Any]] = None
    token_usage: Optional[Dict[str, int]] = None
    cost_usd: Optional[float] = None
    final_status: str = "running"
    error_count: int = 0

    def __post_init__(self):
        if self.tools_used is None:
            self.tools_used = {}
        if self.subsessions is None:
            self.subsessions = []

    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)
