"""
实时消息订阅器

负责订阅 Redis 实时消息流，支持会话级别和实例级别的订阅。
"""

import asyncio
import logging
from typing import Any, AsyncIterator, Dict, List, Optional, Set

from .message_formatter import MessageFormatter

logger = logging.getLogger(__name__)


class RealtimeSubscriber:
    """
    实时消息订阅器

    提供对 Redis 实时消息的订阅功能，支持会话级别和实例级别的消息过滤。
    """

    def __init__(
        self,
        message_bus,
        buffer_size: int = 100,
        heartbeat_interval: float = 30.0
    ):
        """
        初始化实时消息订阅器

        Args:
            message_bus: MessageBus 实例
            buffer_size: 内部缓冲区大小
            heartbeat_interval: 心跳间隔（秒）
        """
        self.message_bus = message_bus
        self.buffer_size = buffer_size
        self.heartbeat_interval = heartbeat_interval
        self._subscriptions: Set[str] = set()
        self._running = False

    async def subscribe_session(
        self,
        session_id: str,
        message_types: Optional[List[str]] = None,
        include_metadata: bool = True
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        订阅特定会话的实时消息

        Args:
            session_id: 会话 ID
            message_types: 过滤的消息类型列表
            include_metadata: 是否包含会话元数据信息

        Yields:
            标准化后的实时消息
        """
        if not self.message_bus or not self.message_bus.is_connected:
            logger.warning("MessageBus 未连接，无法订阅会话消息")
            return

        channel = f"messages:session:{session_id}"
        subscription_id = f"session_{session_id}"

        logger.info(f"开始订阅会话消息: {channel}")

        try:
            self._subscriptions.add(subscription_id)
            self._running = True

            async with self.message_bus.subscribe(channel) as subscription:
                while self._running:
                    try:
                        # 等待消息，设置超时用于心跳检查
                        event = await asyncio.wait_for(
                            subscription.__anext__(),
                            timeout=self.heartbeat_interval
                        )

                        # 处理接收到的消息
                        if event:
                            # 标准化消息格式
                            normalized_message = MessageFormatter.normalize_realtime_message(event)

                            if normalized_message:
                                # 消息类型过滤
                                if message_types and normalized_message.get('message_type') not in message_types:
                                    continue

                                # 添加订阅信息
                                if include_metadata:
                                    normalized_message['_subscription_info'] = {
                                        'channel': channel,
                                        'subscription_type': 'session',
                                        'session_id': session_id,
                                    }

                                yield normalized_message

                    except asyncio.TimeoutError:
                        # 心跳超时，发送心跳消息
                        yield self._create_heartbeat_message(
                            subscription_type='session',
                            target_id=session_id,
                            channel=channel
                        )

                    except Exception as e:
                        logger.error(f"处理会话消息时出错: {e}")
                        # 继续运行，不中断订阅
                        continue

        except Exception as e:
            logger.error(f"订阅会话消息失败: {e}, channel: {channel}")
            raise

        finally:
            self._subscriptions.discard(subscription_id)
            logger.info(f"停止订阅会话消息: {channel}")

    async def subscribe_instance(
        self,
        instance_name: str,
        message_types: Optional[List[str]] = None,
        include_metadata: bool = True
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        订阅特定实例的所有实时消息

        Args:
            instance_name: 实例名称
            message_types: 过滤的消息类型列表
            include_metadata: 是否包含会话元数据信息

        Yields:
            标准化后的实时消息
        """
        if not self.message_bus or not self.message_bus.is_connected:
            logger.warning("MessageBus 未连接，无法订阅实例消息")
            return

        channel = f"messages:instance:{instance_name}"
        subscription_id = f"instance_{instance_name}"

        logger.info(f"开始订阅实例消息: {channel}")

        try:
            self._subscriptions.add(subscription_id)
            self._running = True

            async with self.message_bus.subscribe(channel) as subscription:
                while self._running:
                    try:
                        # 等待消息，设置超时用于心跳检查
                        event = await asyncio.wait_for(
                            subscription.__anext__(),
                            timeout=self.heartbeat_interval
                        )

                        # 处理接收到的消息
                        if event:
                            # 标准化消息格式
                            normalized_message = MessageFormatter.normalize_realtime_message(event)

                            if normalized_message:
                                # 消息类型过滤
                                if message_types and normalized_message.get('message_type') not in message_types:
                                    continue

                                # 添加订阅信息
                                if include_metadata:
                                    normalized_message['_subscription_info'] = {
                                        'channel': channel,
                                        'subscription_type': 'instance',
                                        'instance_name': instance_name,
                                    }

                                yield normalized_message

                    except asyncio.TimeoutError:
                        # 心跳超时，发送心跳消息
                        yield self._create_heartbeat_message(
                            subscription_type='instance',
                            target_id=instance_name,
                            channel=channel
                        )

                    except Exception as e:
                        logger.error(f"处理实例消息时出错: {e}")
                        # 继续运行，不中断订阅
                        continue

        except Exception as e:
            logger.error(f"订阅实例消息失败: {e}, channel: {channel}")
            raise

        finally:
            self._subscriptions.discard(subscription_id)
            logger.info(f"停止订阅实例消息: {channel}")

    async def subscribe_multiple(
        self,
        targets: List[Dict[str, Any]],
        message_types: Optional[List[str]] = None,
        include_metadata: bool = True
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        同时订阅多个目标（会话或实例）

        Args:
            targets: 目标列表，每个元素包含 {'type': 'session'|'instance', 'id': str}
            message_types: 过滤的消息类型列表
            include_metadata: 是否包含会话元数据信息

        Yields:
            标准化后的实时消息
        """
        if not targets:
            return

        logger.info(f"开始订阅 {len(targets)} 个目标")

        # 创建任务列表
        tasks = []
        for target in targets:
            target_type = target.get('type')
            target_id = target.get('id')

            if target_type == 'session':
                task = self.subscribe_session(
                    session_id=target_id,
                    message_types=message_types,
                    include_metadata=include_metadata
                )
            elif target_type == 'instance':
                task = self.subscribe_instance(
                    instance_name=target_id,
                    message_types=message_types,
                    include_metadata=include_metadata
                )
            else:
                logger.warning(f"未知的目标类型: {target_type}")
                continue

            if task:
                tasks.append(task)

        if not tasks:
            logger.warning("没有有效的订阅目标")
            return

        try:
            # 合并多个订阅的消息流
            async for message in self._merge_streams(*tasks):
                yield message

        except Exception as e:
            logger.error(f"多目标订阅失败: {e}")
            raise

    async def stop_all(self):
        """
        停止所有订阅
        """
        logger.info("停止所有实时消息订阅")
        self._running = False
        self._subscriptions.clear()

    @property
    def is_connected(self) -> bool:
        """
        检查 MessageBus 是否连接

        Returns:
            是否已连接
        """
        return self.message_bus and self.message_bus.is_connected

    @property
    def active_subscriptions(self) -> List[str]:
        """
        获取当前活跃的订阅列表

        Returns:
            订阅 ID 列表
        """
        return list(self._subscriptions)

    async def _merge_streams(self, *streams: AsyncIterator[Dict[str, Any]]) -> AsyncIterator[Dict[str, Any]]:
        """
        合并多个消息流

        Args:
            *streams: 多个异步迭代器

        Yields:
            合并后的消息
        """
        # 使用 asyncio.Queue 来合并多个流
        queue = asyncio.Queue(maxsize=self.buffer_size)

        async def producer(stream: AsyncIterator[Dict[str, Any]]):
            """生产者协程"""
            try:
                async for message in stream:
                    await queue.put(message)
            except Exception as e:
                logger.error(f"消息流生产者出错: {e}")
            finally:
                # 发送结束信号
                await queue.put(None)

        # 启动生产者协程
        tasks = [asyncio.create_task(producer(stream)) for stream in streams]
        finished_tasks = 0

        try:
            while finished_tasks < len(tasks):
                try:
                    # 等待消息
                    message = await asyncio.wait_for(queue.get(), timeout=1.0)

                    if message is None:
                        # 收到结束信号
                        finished_tasks += 1
                    else:
                        # 产出消息
                        yield message

                except asyncio.TimeoutError:
                    # 超时继续等待
                    continue

        finally:
            # 取消未完成的任务
            for task in tasks:
                if not task.done():
                    task.cancel()

            # 等待所有任务完成
            await asyncio.gather(*tasks, return_exceptions=True)

    def _create_heartbeat_message(
        self,
        subscription_type: str,
        target_id: str,
        channel: str
    ) -> Dict[str, Any]:
        """
        创建心跳消息

        Args:
            subscription_type: 订阅类型（session 或 instance）
            target_id: 目标 ID
            channel: 频道名称

        Returns:
            心跳消息字典
        """
        from datetime import datetime

        return {
            'seq': -1,  # 心跳消息使用特殊序号
            'timestamp': datetime.now().isoformat(),
            'message_type': 'SystemMessage',
            'instance_name': target_id if subscription_type == 'instance' else '',
            'session_id': target_id if subscription_type == 'session' else '',
            'parent_session_id': None,
            'depth': 0,
            'data': {
                'subtype': 'heartbeat',
                'data': {
                    'subscription_type': subscription_type,
                    'target_id': target_id,
                    'channel': channel,
                    'subscription_count': len(self._subscriptions),
                }
            },
            'source': 'realtime',
            'received_at': datetime.now().isoformat(),
        }