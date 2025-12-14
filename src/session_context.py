"""
会话上下文模块

使用 contextvars 实现跨异步调用的会话上下文传递，
支持父子实例间自动关联会话。

新增功能：
- Token 机制：允许恢复之前的上下文值（而不是总是清空）
- SessionContext：上下文管理器，确保子实例的上下文变化不影响父级
"""

from contextvars import ContextVar, Token
from typing import Optional, TYPE_CHECKING

from .logging_config import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from .session_manager import Session

# 全局上下文变量：存储当前会话
_current_session_context: ContextVar[Optional['Session']] = ContextVar(
    'current_session',
    default=None
)


def set_current_session(session: Optional['Session']) -> Token:
    """
    设置当前会话上下文

    Args:
        session: Session 对象，或 None（清除上下文）

    Returns:
        Token - 可用于恢复之前的上下文（通过 reset_current_session）
    """
    token = _current_session_context.set(session)
    logger.debug(
        f"[SessionContext] Set session: "
        f"session_id={session.session_id if session else None}, token={token}"
    )
    return token


def get_current_session() -> Optional['Session']:
    """
    获取当前会话上下文

    Returns:
        当前的 Session 对象，如果没有则返回 None
    """
    session = _current_session_context.get()
    logger.debug(
        f"[SessionContext] Get session: "
        f"session_id={session.session_id if session else None}"
    )
    return session


def reset_current_session(token: Token) -> None:
    """
    使用 token 恢复之前的上下文

    这比 set_current_session(None) 更安全，因为它会恢复到之前的值
    而不是总是清空。这对于嵌套调用特别重要。

    Args:
        token: 由 set_current_session() 返回的 Token
    """
    _current_session_context.reset(token)
    # 获取恢复后的值以便记录日志
    restored_session = _current_session_context.get()
    logger.debug(
        f"[SessionContext] Reset session: token={token}, "
        f"restored_to={restored_session.session_id if restored_session else None}"
    )


class SessionContext:
    """
    会话上下文管理器 - 用于子实例调用

    确保子实例的上下文变化不影响父级。

    使用方式：
    ```python
    with SessionContext(sub_session):
        # 在这个块中，get_current_session() 返回 sub_session
        result = await sub_agent.query_text(...)
    # 退出后，上下文自动恢复到之前的值
    ```
    """

    def __init__(self, session: Optional['Session']):
        """
        初始化上下文管理器

        Args:
            session: 要设置的会话对象
        """
        self.session = session
        self._token: Optional[Token] = None

    def __enter__(self):
        """
        进入上下文时保存当前上下文并设置新的

        Returns:
            self
        """
        self._token = set_current_session(self.session)
        logger.debug(
            f"[SessionContext] Enter: "
            f"session_id={self.session.session_id if self.session else None}"
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        退出上下文时恢复之前的上下文

        Args:
            exc_type: 异常类型
            exc_val: 异常值
            exc_tb: 异常回溯

        Returns:
            False - 不抑制异常
        """
        if self._token:
            reset_current_session(self._token)
            logger.debug(
                f"[SessionContext] Exit: token={self._token}, "
                f"exception={exc_type.__name__ if exc_type else None}"
            )
        return False
