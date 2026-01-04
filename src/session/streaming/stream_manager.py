"""
查询流管理模块

负责管理查询流的生命周期和资源清理，确保：
1. Session 只被 finalize 一次（幂等性）
2. 上下文正确恢复（而不是清空）
3. 异常情况下资源正确释放
"""

from typing import Any, Optional
from contextvars import ContextVar, Token

from ...logging_config import get_logger
from ..utils import SessionContext

logger = get_logger(__name__)

# 全局上下文变量：存储当前会话（仅用于 stream_manager 内部）
_current_session_context: ContextVar[Optional['Any']] = ContextVar(
    'current_session',
    default=None
)


def set_current_session(session: Optional['Any']) -> Token:
    """设置当前会话上下文"""
    token = _current_session_context.set(session)
    logger.debug(f"[StreamManager] Set session: session_id={session.session_id if session else None}")
    return token


def reset_current_session(token: Token) -> None:
    """恢复之前的会话上下文"""
    _current_session_context.reset(token)
    logger.debug("[StreamManager] Reset session")


class QueryStreamManager:
    """
    查询流生命周期管理器

    使用异步上下文管理器模式，确保资源正确分配和释放。
    解决异步生成器生命周期管理的关键问题。
    """

    def __init__(
        self,
        stream: Any,
        session_manager: Optional[Any] = None,
        record_session: bool = True,
        prompt: Optional[str] = None,
        resume_session_id: Optional[str] = None,
        parent_session_id: Optional[str] = None,
        instance_path: Optional[str] = None,
        pregenerated_session_id: Optional[str] = None  # 🌟 新增：预生成的 session_id
    ):
        """
        初始化流管理器

        Args:
            stream: SDK 返回的查询流
            session_manager: SessionManager 对象
            record_session: 是否记录会话
            prompt: 查询提示词（用于创建新会话）
            resume_session_id: 要恢复的会话 ID
            parent_session_id: 父会话 ID（用于子实例调用）
            instance_path: 实例路径（用于 SessionContext）
            pregenerated_session_id: 预生成的 session_id（用于 workspace）
        """
        self.stream = stream
        self.session_manager = session_manager
        self.record_session = record_session
        self.prompt = prompt
        self.resume_session_id = resume_session_id
        self.parent_session_id = parent_session_id
        self.instance_path = instance_path
        self.pregenerated_session_id = pregenerated_session_id  # 🌟 保存预生成的 ID
        self.session = None  # 实际的 Session 对象
        self._finalized = False  # 防止双重 finalize
        self._context_token: Optional[Token] = None  # 保存上下文令牌
        self._initialized = False  # 标记是否已初始化

    async def initialize(self) -> None:
        """
        初始化 session（创建新会话或恢复已有会话）

        必须在开始迭代之前调用此方法
        """
        if self._initialized:
            return

        if not self.record_session or not self.session_manager:
            # 不记录会话
            self._initialized = True
            return

        try:
            if self.resume_session_id:
                # Resume 模式：恢复已有会话
                self.session = self.session_manager.get_session(self.resume_session_id)
                await self.session.start()  # 启动会话（确保JSONLWriter后台任务运行）
                logger.info(f"[StreamManager] Resume and started session: {self.resume_session_id}")
            else:
                # 创建新会话（可能使用预生成的 session_id）
                self.session = await self.session_manager.create_session(
                    initial_prompt=self.prompt or "",
                    context={},
                    parent_session_id=self.parent_session_id,  # 传递父会话 ID
                    session_id=self.pregenerated_session_id  # 🌟 传递预生成的 ID（如果有）
                )
                logger.info(f"[StreamManager] Created new session: {self.session.session_id}, parent: {self.parent_session_id}")

            # ✅ 将 session_id 写入临时文件，供子实例自动读取
            if self.session and self.instance_path:
                SessionContext.set_current_session(
                    session_id=self.session.session_id,
                    instance_path=str(self.instance_path)
                )
                logger.debug(f"[StreamManager] Set session context: {self.session.session_id}")

            self._initialized = True

        except Exception as e:
            logger.error(f"[StreamManager] Failed to initialize session: {e}", exc_info=True)
            # 继续执行，但不记录会话
            self.session = None
            self._initialized = True

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

        # ✅ 清理 session 上下文临时文件
        if self.session:
            SessionContext.clear_current_session(session_id=self.session.session_id)
            logger.debug(f"[StreamManager] Cleared session context: {self.session.session_id}")

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

    @property
    def session_id(self) -> Optional[str]:
        """获取会话 ID"""
        return self.session.session_id if self.session else None

    def __aiter__(self):
        """使 QueryStreamManager 可作为异步迭代器"""
        return self

    async def __anext__(self):
        """异步迭代器的下一个方法"""
        # 确保 session 已初始化（第一次迭代时）
        if not self._initialized:
            await self.initialize()

        try:
            # 从 SDK stream 获取下一个消息
            message = await self.stream.__anext__()

            # 记录消息
            if self.session:
                await self.session.record_message(message)

                # 如果是 ResultMessage，执行 finalize
                from claude_agent_sdk import ResultMessage
                if isinstance(message, ResultMessage):
                    await self.finalize_on_result(message)

            return message

        except StopAsyncIteration:
            # 流结束，执行 finalize
            if self.session and not self._finalized:
                self.session.metadata['status'] = 'completed'
                await self.session.finalize()
                self._finalized = True
            raise
