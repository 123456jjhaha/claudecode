"""
会话管理器模块

提供 SessionManager 类，负责创建和管理会话。
"""

import json
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional, List, Dict

from ...logging_config import get_logger
from ...error_handling import AgentSystemError
from ..utils.session_utils import generate_session_id
from .session import Session

# 新增导入
try:
    from ..streaming.message_bus import MessageBus
    from ..storage.jsonl_writer import JSONLWriter
except ImportError:
    MessageBus = None
    JSONLWriter = None

logger = get_logger(__name__)


class SessionManager:
    """
    会话管理器

    负责创建和管理会话，提供会话查询和清理功能。
    """

    def __init__(
        self,
        instance_path: Path,
        config: Optional[dict] = None,
        message_bus: Optional["MessageBus"] = None  # 新增
    ):
        """
        初始化会话管理器

        Args:
            instance_path: 实例目录路径
            config: 会话记录配置
            message_bus: 消息总线（可选）
        """
        self.instance_path = Path(instance_path)
        self.sessions_dir = self.instance_path / "sessions"

        # 新增：MessageBus
        self._message_bus = message_bus

        # 合并配置和默认值
        default_config = {
            "enabled": True,
            "retention_days": 30,
            "max_total_size_mb": 1000,
            "auto_cleanup": True,
            "message_types": None,  # None 表示记录所有类型
            "include_content": True,
            "include_metadata": True,
        }

        # 合并用户配置
        self.config = {**default_config, **(config or {})}

        logger.debug(f"会话记录配置: {self.config}")

        # 创建 sessions 目录
        if self.config.get("enabled"):
            self.sessions_dir.mkdir(parents=True, exist_ok=True)

        # 会话路径缓存（用于快速查找）
        self._session_path_cache: dict[str, Path] = {}

    async def create_session(
        self,
        initial_prompt: str,
        context: Optional[dict] = None,
        parent_session_id: Optional[str] = None
    ) -> Session:
        """
        创建新会话

        Args:
            initial_prompt: 初始提示词
            context: 额外的上下文信息
            parent_session_id: 父会话 ID（用于追踪调用链）
                **重要**：对于子实例调用，必须传递此参数以建立父子关系

        Returns:
            Session 对象
        """
        if not self.config.get("enabled"):
            # 会话记录未启用，返回空会话
            logger.info("会话记录未启用")
            return None

        # 生成会话 ID
        session_id = generate_session_id()

        # 会话目录（总是在当前实例的 sessions/ 目录下）
        session_dir = self.sessions_dir / session_id

        # 计算深度（如果有父会话 ID）
        depth = 0
        if parent_session_id:
            # TODO: 未来可以从数据库或缓存中查询父会话的 depth 并递增
            depth = 1  # 简化处理，子会话深度为 1

        # 创建元数据
        metadata = {
            "session_id": session_id,
            "instance_name": self.instance_path.name,
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "status": "running",
            "prompts": [{
                "prompt": initial_prompt[:1000],  # 限制长度
                "timestamp": datetime.now().isoformat()
            }],
            "results": [],  # 初始为空，后续在 finalize 时追加
            "depth": depth,
            "parent_session_id": parent_session_id,  # 直接使用传入的 parent_session_id
            "context": context or {}
        }

        # 创建 JSONLWriter（如果启用了实时流，自动启用异步写入）
        jsonl_writer = None
        if self._message_bus:
            # 从环境变量或配置读取参数
            batch_size = int(os.getenv("ASYNC_WRITE_BATCH_SIZE", "10"))
            flush_interval = float(os.getenv("ASYNC_WRITE_FLUSH_INTERVAL", "1.0"))

            jsonl_writer = JSONLWriter(
                session_dir=session_dir,
                batch_size=batch_size,
                flush_interval=flush_interval
            )

        # 创建会话对象
        session = Session(
            session_id=session_id,
            session_dir=session_dir,
            metadata=metadata,
            config=self.config,
            message_bus=self._message_bus,  # 传递 MessageBus（可能为 None）
            jsonl_writer=jsonl_writer  # 传递 JSONLWriter（可能为 None）
        )

        # 启动会话
        await session.start()

        return session

    def _build_session_path_cache(self) -> None:
        """
        构建会话 ID 到路径的缓存

        只扫描当前实例的 sessions/ 目录，不再递归扫描 subsessions。
        """
        self._session_path_cache.clear()

        if not self.sessions_dir.exists():
            return

        for session_dir in self.sessions_dir.iterdir():
            if session_dir.is_dir():
                # 从目录名提取 session_id
                session_id = session_dir.name
                self._session_path_cache[session_id] = session_dir

        logger.debug(f"缓存了 {len(self._session_path_cache)} 个会话路径")

    def get_session(self, session_id: str, rebuild_cache: bool = False) -> Session:
        """
        获取已存在的会话对象（用于 resume）

        Args:
            session_id: 会话 ID
            rebuild_cache: 是否重建路径缓存

        Returns:
            Session 对象

        Raises:
            AgentSystemError: 会话不存在
        """
        # 重建缓存（如果需要）
        if rebuild_cache or not self._session_path_cache:
            self._build_session_path_cache()

        # 从缓存查找
        session_dir = self._session_path_cache.get(session_id)

        if not session_dir:
            # 缓存未命中，尝试重建缓存再查找一次
            self._build_session_path_cache()
            session_dir = self._session_path_cache.get(session_id)

        if not session_dir or not session_dir.exists():
            raise AgentSystemError(f"会话不存在: {session_id}")

        # 读取元数据
        metadata_file = session_dir / "metadata.json"
        if not metadata_file.exists():
            raise AgentSystemError(f"会话元数据缺失: {session_id}")

        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        # 创建 Session 对象
        session = Session(
            session_id=session_id,
            session_dir=session_dir,
            metadata=metadata,
            config=self.config
        )

        # 设置状态为可追加（重要：允许 resume 时追加消息）
        session._finalized = False

        logger.info(f"加载会话: {session_id}")

        return session

    def get_claude_session_id(self, local_session_id: str) -> Optional[str]:
        """
        从本地会话记录中提取Claude的session_id

        Args:
            local_session_id: 我们的session_id (格式: 20251216T051526_5440_021abcf7)

        Returns:
            Claude的session_id (UUID格式) 或 None
        """
        try:
            import json

            # 构建会话目录路径
            session_dir = self.sessions_dir / local_session_id
            if not session_dir.exists():
                logger.error(f"会话目录不存在: {session_dir}")
                return None

            # 读取messages.jsonl文件
            messages_file = session_dir / "messages.jsonl"
            if not messages_file.exists():
                logger.error(f"会话消息文件不存在: {messages_file}")
                return None

            # 查找第一个包含session_id的SystemMessage
            with open(messages_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        message_data = json.loads(line)
                        message_type = message_data.get("message_type")
                        data = message_data.get("data", {})

                        # 查找SystemMessage或ResultMessage中的session_id
                        if message_type in ["SystemMessage", "ResultMessage"]:
                            claude_session_id = data.get("session_id")
                            if claude_session_id:
                                logger.debug(f"找到Claude session_id: {claude_session_id}")
                                return claude_session_id

                    except json.JSONDecodeError as e:
                        logger.warning(f"解析消息行失败: {e}")
                        continue

            logger.warning(f"在会话 {local_session_id} 中未找到Claude session_id")
            return None

        except Exception as e:
            logger.error(f"提取Claude session_id失败: {e}")
            return None

    def list_sessions(
        self,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[dict]:
        """
        列出会话（支持过滤和分页）

        Args:
            status: 过滤状态（可选）
            limit: 限制返回数量
            offset: 偏移量

        Returns:
            会话信息列表
        """
        if not self.sessions_dir.exists():
            return []

        sessions = []

        for session_dir in self.sessions_dir.iterdir():
            if not session_dir.is_dir():
                continue

            metadata_file = session_dir / "metadata.json"
            if not metadata_file.exists():
                continue

            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)

            # 过滤状态
            if status and metadata.get('status') != status:
                continue

            sessions.append(metadata)

        # 按时间排序（最新的在前）
        sessions.sort(key=lambda x: x.get('start_time', ''), reverse=True)

        # 分页
        return sessions[offset:offset + limit]

    def cleanup_old_sessions(
        self,
        retention_days: int = 30,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        清理过期会话

        Args:
            retention_days: 保留天数
            dry_run: 是否模拟运行（不实际删除）

        Returns:
            清理报告
        """
        if not self.sessions_dir.exists():
            return {"deleted": 0, "total_size_mb": 0, "sessions": [], "dry_run": dry_run}

        cutoff_time = datetime.now() - timedelta(days=retention_days)

        deleted_count = 0
        total_size = 0
        deleted_sessions = []

        for session_dir in self.sessions_dir.iterdir():
            if not session_dir.is_dir():
                continue

            # 读取元数据
            metadata_file = session_dir / "metadata.json"
            if not metadata_file.exists():
                continue

            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)

            # 检查是否过期
            end_time = metadata.get('end_time')
            if not end_time:
                continue

            end_datetime = datetime.fromisoformat(end_time)
            if end_datetime < cutoff_time:
                # 计算目录大小
                size = sum(f.stat().st_size for f in session_dir.rglob('*') if f.is_file())
                total_size += size

                deleted_sessions.append({
                    "session_id": metadata['session_id'],
                    "end_time": end_time,
                    "size_bytes": size
                })

                # 删除目录
                if not dry_run:
                    shutil.rmtree(session_dir)

                deleted_count += 1

        return {
            "deleted": deleted_count,
            "total_size_mb": total_size / (1024 * 1024),
            "sessions": deleted_sessions,
            "dry_run": dry_run
        }

    def cleanup(self):
        """
        清理会话管理器资源

        当前 SessionManager 没有需要特别清理的资源，
        此方法仅用于兼容性。
        """
        logger.debug("SessionManager cleanup: 无资源需要清理")
        # 清理路径缓存
        self._session_path_cache.clear()
