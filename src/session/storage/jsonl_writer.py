"""异步批量 JSONL 写入器"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class JSONLWriter:
    """
    异步批量 JSONL 写入器

    特性：
    - 批量写入缓冲区（默认 10 条消息）
    - 定时刷新（默认 1 秒）
    - 后台任务自动刷新
    - 紧急备份机制（写入失败时备份到 .backup.jsonl）
    - finalize() 时强制刷新并停止
    """

    def __init__(
        self,
        session_dir: Path,
        batch_size: int = 10,
        flush_interval: float = 1.0
    ):
        """
        初始化 JSONLWriter

        Args:
            session_dir: 会话目录
            batch_size: 批量写入大小（达到此数量立即刷新）
            flush_interval: 定时刷新间隔（秒）
        """
        self.session_dir = Path(session_dir)
        self.batch_size = batch_size
        self.flush_interval = flush_interval

        self.messages_file = self.session_dir / "messages.jsonl"
        self.backup_file = self.session_dir / "messages.backup.jsonl"

        self._buffer: list[dict] = []
        self._lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None
        self._stopped = False

        # 启动后台刷新任务
        self._flush_task = asyncio.create_task(self._auto_flush())

    async def write(self, message_data: dict):
        """
        写入一条消息到缓冲区

        Args:
            message_data: 消息数据
        """
        if self._stopped:
            logger.warning("JSONLWriter 已停止，无法写入消息")
            return

        async with self._lock:
            self._buffer.append(message_data)

            # 达到批量大小，立即刷新
            if len(self._buffer) >= self.batch_size:
                await self._flush()

    async def _auto_flush(self):
        """后台定时刷新任务"""
        try:
            while not self._stopped:
                await asyncio.sleep(self.flush_interval)

                async with self._lock:
                    if self._buffer:
                        await self._flush()
        except asyncio.CancelledError:
            logger.debug("JSONLWriter 后台刷新任务已取消")
        except Exception as e:
            logger.error(f"JSONLWriter 后台刷新任务异常: {e}")

    async def _flush(self):
        """
        刷新缓冲区到文件

        注意：此方法不加锁，调用者需要持有锁
        """
        if not self._buffer:
            return

        try:
            # 确保目录存在
            self.session_dir.mkdir(parents=True, exist_ok=True)

            # 追加写入（支持 resume）
            with open(self.messages_file, "a", encoding="utf-8") as f:
                for message_data in self._buffer:
                    json_line = json.dumps(message_data, ensure_ascii=False)
                    f.write(json_line + "\n")

            logger.debug(f"刷新 {len(self._buffer)} 条消息到 {self.messages_file}")
            self._buffer.clear()

        except Exception as e:
            logger.error(f"写入 JSONL 失败: {e}，尝试紧急备份")
            await self._emergency_backup()

    async def _emergency_backup(self):
        """紧急备份（写入失败时）"""
        try:
            with open(self.backup_file, "a", encoding="utf-8") as f:
                for message_data in self._buffer:
                    json_line = json.dumps(message_data, ensure_ascii=False)
                    f.write(json_line + "\n")

            logger.warning(f"紧急备份 {len(self._buffer)} 条消息到 {self.backup_file}")
            self._buffer.clear()
        except Exception as e:
            logger.error(f"紧急备份失败: {e}，消息可能丢失")

    async def finalize(self):
        """
        强制刷新并停止后台任务

        此方法应在会话结束时调用
        """
        if self._stopped:
            return

        self._stopped = True

        # 取消后台任务
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

        # 强制刷新剩余消息
        async with self._lock:
            if self._buffer:
                await self._flush()

        logger.info(f"JSONLWriter 已停止，所有消息已写入 {self.messages_file}")
