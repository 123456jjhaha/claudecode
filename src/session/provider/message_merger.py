"""
消息合并器

负责智能合并历史消息流和实时消息流，确保时序正确和消息去重。
"""

import asyncio
import logging
from typing import Any, AsyncIterator, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class MessageMerger:
    """
    消息合并器

    提供智能的历史消息和实时消息合并功能，保证消息的时序和去重。
    """

    def __init__(
        self,
        dedup_strategy: str = "seq",
        time_tolerance: float = 1.0
    ):
        """
        初始化消息合并器

        Args:
            dedup_strategy: 去重策略（"seq" 使用序列号，"timestamp" 使用时间戳）
            time_tolerance: 时间容差（秒），用于时间戳去重
        """
        self.dedup_strategy = dedup_strategy
        self.time_tolerance = time_tolerance
        self._seen_sequences: Set[int] = set()
        self._seen_timestamps: Set[str] = set()
        self._last_historical_seq: int = -1
        self._last_historical_timestamp: str = ""

    async def merge_streams(
        self,
        historical_stream: Optional[AsyncIterator[Dict[str, Any]]] = None,
        realtime_stream: Optional[AsyncIterator[Dict[str, Any]]] = None,
        strategy: str = "historical_first"
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        合并历史消息流和实时消息流

        Args:
            historical_stream: 历史消息流
            realtime_stream: 实时消息流
            strategy: 合并策略
                - "historical_first": 先发送所有历史消息，然后实时消息
                - "interleaved": 按时间戳交错合并
                - "realtime_priority": 优先实时消息，历史消息作为补充

        Yields:
            合并后的消息流
        """
        if not historical_stream and not realtime_stream:
            logger.warning("没有可合并的消息流")
            return

        if strategy == "historical_first":
            async for message in self.merge_historical_first(historical_stream, realtime_stream):
                yield message
        elif strategy == "interleaved":
            async for message in self.merge_interleaved(historical_stream, realtime_stream):
                yield message
        elif strategy == "realtime_priority":
            async for message in self.merge_realtime_priority(historical_stream, realtime_stream):
                yield message
        else:
            raise ValueError(f"未知的合并策略: {strategy}")

    async def merge_historical_first(
        self,
        historical_stream: AsyncIterator[Dict[str, Any]],
        realtime_stream: AsyncIterator[Dict[str, Any]]
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        先发送所有历史消息，然后实时消息的合并策略

        这是最简单的策略，确保先看到完整的历史记录，然后接收实时更新。
        """
        # 第一阶段：发送所有历史消息
        if historical_stream:
            logger.info("开始发送历史消息")
            async for message in historical_stream:
                if self._should_include_message(message, is_historical=True):
                    self._mark_message_as_seen(message, is_historical=True)
                    yield message
            logger.info("历史消息发送完成")

        # 第二阶段：发送实时消息（去重）
        if realtime_stream:
            logger.info("开始发送实时消息")
            async for message in realtime_stream:
                if self._should_include_message(message, is_historical=False):
                    self._mark_message_as_seen(message, is_historical=False)
                    yield message
            logger.info("实时消息发送完成")

    async def merge_interleaved(
        self,
        historical_stream: AsyncIterator[Dict[str, Any]],
        realtime_stream: AsyncIterator[Dict[str, Any]]
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        按时间戳交错合并的策略

        将两个流按时间戳排序，产生真正的时间顺序消息流。
        """
        from datetime import datetime

        # 使用优先级队列来合并排序的流
        buffer = asyncio.Queue(maxsize=100)

        async def historical_producer():
            """历史消息生产者"""
            if not historical_stream:
                await buffer.put(None)
                return

            try:
                async for message in historical_stream:
                    if self._should_include_message(message, is_historical=True):
                        # 添加时间戳用于排序
                        timestamp = message.get('timestamp', '')
                        try:
                            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                            await buffer.put((dt.timestamp(), message, 'historical'))
                        except ValueError:
                            # 时间戳解析失败，使用当前时间
                            import time
                            await buffer.put((time.time(), message, 'historical'))

                # 发送结束标记
                await buffer.put(None)

            except Exception as e:
                logger.error(f"历史消息生产者出错: {e}")
                await buffer.put(None)

        async def realtime_producer():
            """实时消息生产者"""
            if not realtime_stream:
                await buffer.put(None)
                return

            try:
                async for message in realtime_stream:
                    if self._should_include_message(message, is_historical=False):
                        # 实时消息可能有延迟，使用接收时间
                        timestamp = message.get('timestamp', '')
                        received_at = message.get('received_at', '')

                        # 优先使用接收时间，因为实时消息可能有网络延迟
                        sort_timestamp = received_at or timestamp

                        try:
                            dt = datetime.fromisoformat(sort_timestamp.replace('Z', '+00:00'))
                            await buffer.put((dt.timestamp(), message, 'realtime'))
                        except ValueError:
                            # 时间戳解析失败，使用当前时间
                            import time
                            await buffer.put((time.time(), message, 'realtime'))

                # 发送结束标记
                await buffer.put(None)

            except Exception as e:
                logger.error(f"实时消息生产者出错: {e}")
                await buffer.put(None)

        # 启动生产者
        producers_finished = 0
        historical_task = asyncio.create_task(historical_producer())
        realtime_task = asyncio.create_task(realtime_producer())

        try:
            while producers_finished < 2:
                try:
                    item = await asyncio.wait_for(buffer.get(), timeout=1.0)

                    if item is None:
                        producers_finished += 1
                    else:
                        _, message, source = item
                        self._mark_message_as_seen(message, is_historical=(source == 'historical'))
                        yield message

                except asyncio.TimeoutError:
                    continue

        finally:
            # 清理任务
            for task in [historical_task, realtime_task]:
                if not task.done():
                    task.cancel()

            await asyncio.gather(historical_task, realtime_task, return_exceptions=True)

    async def merge_realtime_priority(
        self,
        historical_stream: AsyncIterator[Dict[str, Any]],
        realtime_stream: AsyncIterator[Dict[str, Any]]
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        优先实时消息的合并策略

        优先发送实时消息，历史消息作为补充填充空隙。
        """
        if not realtime_stream:
            # 没有实时消息，直接发送历史消息
            async for message in historical_stream:
                if self._should_include_message(message, is_historical=True):
                    yield message
            return

        # 创建历史消息缓存
        historical_cache = []
        if historical_stream:
            async for message in historical_stream:
                if self._should_include_message(message, is_historical=True):
                    historical_cache.append(message)

        # 按时间戳排序历史消息
        historical_cache.sort(key=lambda x: x.get('timestamp', ''))

        # 并发处理两个流
        async def yield_realtime():
            async for message in realtime_stream:
                if self._should_include_message(message, is_historical=False):
                    yield message

        async def yield_historical():
            for message in historical_cache:
                yield message

        # 创建协程
        realtime_coro = yield_realtime()
        historical_coro = yield_historical()

        # 使用 asyncio.merge 合并流（Python 3.10+）
        try:
            # 对于 Python < 3.10，使用手动实现
            async for message in self._manual_merge([realtime_coro, historical_coro]):
                yield message

        except Exception as e:
            logger.error(f"实时优先合并失败: {e}")

    def _should_include_message(self, message: Dict[str, Any], is_historical: bool) -> bool:
        """
        判断消息是否应该被包含在合并流中

        Args:
            message: 消息字典
            is_historical: 是否为历史消息

        Returns:
            是否应该包含该消息
        """
        # 跳过心跳消息
        if message.get('seq') == -1:
            return False

        if self.dedup_strategy == "seq":
            seq = message.get('seq', -1)
            if seq in self._seen_sequences:
                return False
            return True

        elif self.dedup_strategy == "timestamp":
            timestamp = message.get('timestamp', '')
            if timestamp in self._seen_timestamps:
                return False
            return True

        return True

    def _mark_message_as_seen(self, message: Dict[str, Any], is_historical: bool):
        """
        标记消息为已处理

        Args:
            message: 消息字典
            is_historical: 是否为历史消息
        """
        if self.dedup_strategy == "seq":
            seq = message.get('seq', -1)
            self._seen_sequences.add(seq)

            if is_historical:
                self._last_historical_seq = max(self._last_historical_seq, seq)

        elif self.dedup_strategy == "timestamp":
            timestamp = message.get('timestamp', '')
            self._seen_timestamps.add(timestamp)

            if is_historical:
                self._last_historical_timestamp = timestamp

    async def _manual_merge(self, streams: List[AsyncIterator[Dict[str, Any]]]) -> AsyncIterator[Dict[str, Any]]:
        """
        手动合并多个流（兼容 Python < 3.10）

        Args:
            streams: 异步迭代器列表

        Yields:
            合并后的消息
        """
        # 创建任务和队列
        queue = asyncio.Queue(maxsize=100)
        streams_remaining = len(streams)

        async def stream_producer(stream: AsyncIterator[Dict[str, Any]], index: int):
            """流生产者"""
            try:
                async for message in stream:
                    await queue.put((index, message))
            except Exception as e:
                logger.error(f"流生产者 {index} 出错: {e}")
            finally:
                await queue.put((index, None))  # 结束标记

        # 启动生产者任务
        tasks = [asyncio.create_task(stream_producer(stream, i)) for i, stream in enumerate(streams)]
        finished_streams = 0

        try:
            while finished_streams < streams_remaining:
                try:
                    index, message = await asyncio.wait_for(queue.get(), timeout=1.0)

                    if message is None:
                        finished_streams += 1
                    else:
                        yield message

                except asyncio.TimeoutError:
                    continue

        finally:
            # 清理任务
            for task in tasks:
                if not task.done():
                    task.cancel()

            await asyncio.gather(*tasks, return_exceptions=True)

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取合并统计信息

        Returns:
            统计信息字典
        """
        return {
            'dedup_strategy': self.dedup_strategy,
            'seen_sequences_count': len(self._seen_sequences),
            'seen_timestamps_count': len(self._seen_timestamps),
            'last_historical_seq': self._last_historical_seq,
            'last_historical_timestamp': self._last_historical_timestamp,
        }

    def reset(self):
        """
        重置合并器状态
        """
        self._seen_sequences.clear()
        self._seen_timestamps.clear()
        self._last_historical_seq = -1
        self._last_historical_timestamp = ""