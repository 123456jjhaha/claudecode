"""
会话记录模块

负责 Claude Agent System 的会话管理、记录、查询和统计功能。

主要组件：
- SessionManager: 会话管理器，负责创建和管理会话
- QueryStreamManager: 查询流管理器，处理消息流和记录
- SessionContext: 会话上下文，提供统一的上下文管理
- MessageSerializer: 消息序列化器
- session_query: 会话查询 API

工具函数：
- generate_session_id: 生成唯一的会话 ID
- Statistics: 会话统计信息数据类
"""

# 核心类
from .session_manager import SessionManager, Session
from .stream_manager import QueryStreamManager

# 序列化
from .session_serializer import MessageSerializer

# 工具函数
from .session_utils import generate_session_id, Statistics

# 查询 API
from . import session_query

__all__ = [
    # 核心类
    "SessionManager",
    "Session",
    "QueryStreamManager",

    # 序列化
    "MessageSerializer",

    # 工具函数
    "generate_session_id",
    "Statistics",

    # 查询模块
    "session_query",
]
