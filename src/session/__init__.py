"""
会话记录模块

负责 Claude Agent System 的会话管理、记录、查询和统计功能。

目录结构：
- core/: 会话核心类（Session, SessionManager）
- streaming/: 实时消息流（MessageBus, QueryStreamManager）
- storage/: 存储组件（JSONLWriter）
- query/: 查询 API（session_query, SessionTreeBuilder）
- utils/: 工具函数（session_utils, session_serializer）

主要组件：
- SessionManager: 会话管理器，负责创建和管理会话
- Session: 单个会话对象
- QueryStreamManager: 查询流管理器，处理消息流和记录
- MessageBus: Redis 消息总线（实时推送）
- SessionSubscriber: 会话订阅器（自动订阅父子会话）
- JSONLWriter: 异步批量 JSONL 写入器
- SessionTreeBuilder: 会话树构建器
- MessageSerializer: 消息序列化器

工具函数：
- generate_session_id: 生成唯一的会话 ID
- Statistics: 会话统计信息数据类
- infer_instance_name: 从 session_id 推断实例名称
- extract_instance_from_tool_name: 从工具名称提取实例名称
- get_instance_path: 获取实例目录路径
"""

# 核心类
from .core import SessionManager, Session

# 流管理
from .streaming import QueryStreamManager

# 工具函数
from .utils import (
    generate_session_id,
    Statistics,
    MessageSerializer,
    infer_instance_name,
    extract_instance_from_tool_name,
    get_instance_path
)

# 查询 API
from .query import SessionQuery

# 实时消息和存储模块
try:
    from .streaming import MessageBus
    from .storage import JSONLWriter
    _streaming_available = True
except ImportError:
    MessageBus = None
    JSONLWriter = None
    _streaming_available = False


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
    "infer_instance_name",
    "extract_instance_from_tool_name",
    "get_instance_path",

    # 查询模块
    "SessionQuery",
    "session_query",

    # 实时消息和存储
    "MessageBus",
    "JSONLWriter",
]
