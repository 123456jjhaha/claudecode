"""
会话上下文模块

使用 contextvars 实现跨异步调用的会话上下文传递，
支持父子实例间自动关联会话。
"""

from contextvars import ContextVar
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .session_manager import Session

# 全局上下文变量：存储当前会话
_current_session_context: ContextVar[Optional['Session']] = ContextVar(
    'current_session',
    default=None
)


def set_current_session(session: Optional['Session']) -> None:
    """
    设置当前会话上下文

    Args:
        session: Session 对象，或 None（清除上下文）
    """
    _current_session_context.set(session)


def get_current_session() -> Optional['Session']:
    """
    获取当前会话上下文

    Returns:
        当前的 Session 对象，如果没有则返回 None
    """
    return _current_session_context.get()
