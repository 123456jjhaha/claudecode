"""
Session 上下文管理器

使用临时文件在进程间传递当前会话的 session_id，
用于子实例自动获取父会话 ID，无需 Claude 手动传递。
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any
from ...logging_config import get_logger

logger = get_logger(__name__)


class SessionContext:
    """
    Session 上下文管理器

    使用临时文件存储当前查询的 session_id，
    允许 MCP 服务器子进程（SubInstanceTool）自动读取父 session_id
    """

    # 临时文件路径（使用进程 ID 避免冲突）
    _temp_dir = Path(tempfile.gettempdir()) / "claude_agent_sessions"

    @classmethod
    def _get_context_file(cls, pid: Optional[int] = None) -> Path:
        """
        获取当前进程的上下文文件路径

        Args:
            pid: 进程 ID（默认使用当前进程）

        Returns:
            上下文文件路径
        """
        if pid is None:
            pid = os.getpid()

        cls._temp_dir.mkdir(parents=True, exist_ok=True)
        return cls._temp_dir / f"session_context_{pid}.json"

    @classmethod
    def _get_global_context_file(cls, session_id: Optional[str] = None) -> Path:
        """
        获取全局上下文文件路径（基于 session_id，支持并发）

        Args:
            session_id: 会话 ID（用于生成唯一文件名）

        Returns:
            全局上下文文件路径
        """
        cls._temp_dir.mkdir(parents=True, exist_ok=True)

        if session_id:
            # 使用 session_id 作为文件名的一部分，避免并发冲突
            return cls._temp_dir / f"session_context_{session_id}.json"
        else:
            # 兼容模式：返回最新的全局文件
            return cls._temp_dir / "session_context_latest.json"

    @classmethod
    def set_current_session(cls, session_id: str, instance_path: str) -> None:
        """
        设置当前会话上下文（写入临时文件）

        写入三个文件：
        1. 进程级文件（用于同进程内访问）
        2. session_id 专属文件（支持并发，子进程可根据 session_id 读取）
        3. latest 指针文件（记录最新的 session_id，兼容模式）

        Args:
            session_id: 会话 ID
            instance_path: 实例路径
        """
        import time

        context_data = {
            "session_id": session_id,
            "instance_path": str(instance_path),
            "pid": os.getpid(),
            "timestamp": time.time()
        }

        try:
            # 1. 写入进程级文件
            context_file = cls._get_context_file()
            with open(context_file, 'w', encoding='utf-8') as f:
                json.dump(context_data, f)

            # 2. 写入 session_id 专属文件（避免并发冲突）
            session_file = cls._get_global_context_file(session_id)
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(context_data, f)

            # 3. 写入 latest 指针文件（记录当前进程的最新 session_id）
            latest_file = cls._get_global_context_file(None)
            with open(latest_file, 'w', encoding='utf-8') as f:
                json.dump(context_data, f)

            logger.debug(
                f"[SessionContext] Set session context: {session_id} "
                f"(pid={os.getpid()}, files=3)"
            )

        except Exception as e:
            logger.warning(f"[SessionContext] Failed to set session context: {e}")

    @classmethod
    def get_current_session(cls, pid: Optional[int] = None) -> Optional[str]:
        """
        获取当前会话 ID（从临时文件读取）

        查找顺序：
        1. 先尝试读取进程级文件（同进程内）
        2. 读取 latest 指针文件（跨进程场景，获取最新的 session_id）

        Args:
            pid: 进程 ID（默认使用当前进程）

        Returns:
            会话 ID，如果不存在则返回 None
        """
        # 1. 尝试读取进程级文件（同进程场景）
        context_file = cls._get_context_file(pid)

        if context_file.exists():
            try:
                with open(context_file, 'r', encoding='utf-8') as f:
                    context_data = json.load(f)

                session_id = context_data.get("session_id")
                logger.debug(
                    f"[SessionContext] Get from process file: {session_id} "
                    f"(pid={pid or os.getpid()})"
                )
                return session_id

            except Exception as e:
                logger.warning(f"[SessionContext] Failed to read process file: {e}")

        # 2. 尝试读取 latest 指针文件（跨进程场景）
        latest_file = cls._get_global_context_file(None)

        if latest_file.exists():
            try:
                with open(latest_file, 'r', encoding='utf-8') as f:
                    context_data = json.load(f)

                session_id = context_data.get("session_id")
                logger.debug(
                    f"[SessionContext] Get from latest file: {session_id} "
                    f"(pid={pid or os.getpid()})"
                )
                return session_id

            except Exception as e:
                logger.warning(f"[SessionContext] Failed to read latest file: {e}")

        logger.debug(f"[SessionContext] No session context found (pid={pid or os.getpid()})")
        return None

    @classmethod
    def get_session_by_id(cls, session_id: str) -> Optional[Dict[str, Any]]:
        """
        根据 session_id 获取会话上下文（用于子进程查询特定会话）

        Args:
            session_id: 会话 ID

        Returns:
            会话上下文数据，如果不存在则返回 None
        """
        session_file = cls._get_global_context_file(session_id)

        if session_file.exists():
            try:
                with open(session_file, 'r', encoding='utf-8') as f:
                    context_data = json.load(f)

                logger.debug(f"[SessionContext] Get session by ID: {session_id}")
                return context_data

            except Exception as e:
                logger.warning(f"[SessionContext] Failed to read session file: {e}")

        return None

    @classmethod
    def clear_current_session(cls, pid: Optional[int] = None, session_id: Optional[str] = None) -> None:
        """
        清除当前会话上下文（删除临时文件）

        删除：
        1. 进程级文件
        2. session_id 专属文件（如果提供了 session_id）
        3. latest 指针文件（可选，避免影响其他并发会话）

        Args:
            pid: 进程 ID（默认使用当前进程）
            session_id: 会话 ID（可选，用于删除特定会话的文件）
        """
        try:
            # 1. 删除进程级文件
            context_file = cls._get_context_file(pid)
            if context_file.exists():
                context_file.unlink()

            # 2. 删除 session_id 专属文件
            if session_id:
                session_file = cls._get_global_context_file(session_id)
                if session_file.exists():
                    session_file.unlink()

            # 注意：不删除 latest 指针文件，避免影响其他并发会话

            logger.debug(
                f"[SessionContext] Cleared session context "
                f"(pid={pid or os.getpid()}, session_id={session_id})"
            )

        except Exception as e:
            logger.warning(f"[SessionContext] Failed to clear session context: {e}")

    @classmethod
    def cleanup_all(cls) -> None:
        """
        清理所有临时文件（启动时调用，清理上次未清理的文件）
        """
        try:
            if cls._temp_dir.exists():
                for file in cls._temp_dir.glob("session_context_*.json"):
                    try:
                        file.unlink()
                    except Exception:
                        pass
                logger.debug("[SessionContext] Cleaned up all session context files")
        except Exception as e:
            logger.warning(f"[SessionContext] Failed to cleanup all context files: {e}")
