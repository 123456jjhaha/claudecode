"""
查询流管理模块

负责管理查询流的生命周期和资源清理，确保：
1. Session 只被 finalize 一次（幂等性）
2. 上下文正确恢复（而不是清空）
3. 异常情况下资源正确释放
"""

from typing import Any, Optional
from contextvars import Token

from .session_context import set_current_session, reset_current_session
from .logging_config import get_logger

logger = get_logger(__name__)


class QueryStreamManager:
    """
    查询流生命周期管理器

    使用异步上下文管理器模式，确保资源正确分配和释放。
    解决异步生成器生命周期管理的关键问题。
    """

    def __init__(self, session: Optional[Any], options: Any):
        """
        初始化流管理器

        Args:
            session: Session 对象（如果启用了会话记录）
            options: ClaudeAgentOptions 对象
        """
        self.session = session
        self.options = options
        self._finalized = False  # 防止双重 finalize
        self._context_token: Optional[Token] = None  # 保存上下文令牌

    async def __aenter__(self):
        """
        进入上下文时设置 session

        Returns:
            self
        """
        if self.session:
            self._context_token = set_current_session(self.session)
            logger.debug(
                f"[StreamManager] Context set: session_id={self.session.session_id}, "
                f"token={self._context_token}"
            )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        退出时确保资源清理

        Args:
            exc_type: 异常类型
            exc_val: 异常值
            exc_tb: 异常回溯

        Returns:
            False - 不抑制异常
        """
        # 确保 session 被 finalize（如果尚未完成）
        if self.session and not self._finalized:
            if exc_type is None:
                # 正常结束但未 finalize（stream 未完全消费）
                self.session.metadata['status'] = 'interrupted'
                self.session.metadata['error'] = 'Stream not fully consumed'
                logger.warning(
                    f"[StreamManager] Session interrupted (not fully consumed): "
                    f"session_id={self.session.session_id}"
                )
            else:
                # 异常结束
                self.session.metadata['status'] = 'failed'
                self.session.metadata['error'] = str(exc_val)
                logger.error(
                    f"[StreamManager] Session failed: session_id={self.session.session_id}, "
                    f"error={exc_type.__name__}: {exc_val}"
                )

            # 执行 finalize
            try:
                await self.session.finalize()
                self._finalized = True
                logger.debug(
                    f"[StreamManager] Session finalized in __aexit__: "
                    f"session_id={self.session.session_id}"
                )
            except Exception as e:
                logger.error(
                    f"[StreamManager] Finalize failed in __aexit__: "
                    f"session_id={self.session.session_id}, error={e}",
                    exc_info=True
                )

        # 恢复上下文（而不是清空）
        if self._context_token:
            reset_current_session(self._context_token)
            logger.debug(
                f"[StreamManager] Context reset: token={self._context_token}"
            )

        # 不抑制异常，让它继续传播
        return False

    async def finalize_on_result(self, result_message):
        """
        在收到 ResultMessage 时 finalize（幂等操作）

        这个方法可以被多次调用，但只会执行一次 finalize。

        Args:
            result_message: ResultMessage 对象
        """
        if not self._finalized:
            logger.debug(
                f"[StreamManager] Finalizing on result: "
                f"session_id={self.session.session_id if self.session else 'None'}"
            )

            if self.session:
                try:
                    await self.session.finalize(result_message=result_message)
                    self._finalized = True
                    logger.info(
                        f"[StreamManager] Session finalized successfully: "
                        f"session_id={self.session.session_id}"
                    )
                except Exception as e:
                    logger.error(
                        f"[StreamManager] Finalize failed: "
                        f"session_id={self.session.session_id}, error={e}",
                        exc_info=True
                    )
                    # 标记为已 finalize，避免重试
                    self._finalized = True
                    raise
        else:
            logger.debug(
                f"[StreamManager] Finalize skipped (already finalized): "
                f"session_id={self.session.session_id if self.session else 'None'}"
            )

    @property
    def is_finalized(self) -> bool:
        """检查是否已经 finalize"""
        return self._finalized
