"""
统一消息提供器

作为前端访问消息的唯一入口，自动处理历史消息和实时消息的合并，
提供统一的消息格式和流式处理能力。
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional

from .message_formatter import MessageFormatter
from .message_merger import MessageMerger
from .message_reader import MessageReader
from .realtime_subscriber import RealtimeSubscriber

logger = logging.getLogger(__name__)


class MessageProvider:
    """
    统一消息提供器

    提供历史消息和实时消息的统一访问接口，自动处理消息合并和格式标准化。
    """

    def __init__(
        self,
        instance_name: str,
        session_id: str,
        instances_root: Optional[Path] = None,
        message_bus=None,
        auto_connect: bool = True,
        buffer_size: int = 100
    ):
        """
        初始化消息提供器

        Args:
            instance_name: 实例名称
            session_id: 会话 ID
            instances_root: 实例根目录路径
            message_bus: MessageBus 实例（可选）
            auto_connect: 是否自动连接 MessageBus
            buffer_size: 内部缓冲区大小
        """
        self.instance_name = instance_name
        self.session_id = session_id
        self.instances_root = instances_root or Path("instances")
        self.buffer_size = buffer_size

        # 初始化组件
        self.message_reader = MessageReader(instances_root, buffer_size)
        self.realtime_subscriber = None
        self.message_merger = MessageMerger()

        # MessageBus 相关
        self.message_bus = message_bus
        self._auto_connect = auto_connect

        # 状态管理
        self._connected = False
        self._session_info = None

        # 异步上下文管理器支持
        self._context_active = False

    async def __aenter__(self):
        """异步上下文管理器入口"""
        self._context_active = True
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        self._context_active = False
        await self.disconnect()

    async def connect(self) -> bool:
        """
        连接到必要的服务（主要是 MessageBus）

        Returns:
            连接是否成功
        """
        try:
            # 检查会话是否存在
            if not await self.validate_session():
                logger.error(f"会话不存在: {self.instance_name}/{self.session_id}")
                return False

            # 获取会话信息
            self._session_info = await self.message_reader.get_session_info(
                self.instance_name,
                self.session_id
            )

            # 连接 MessageBus
            if self.message_bus and not self.message_bus.is_connected:
                if self._auto_connect:
                    await self.message_bus.connect()
                else:
                    logger.warning("MessageBus 未连接且 auto_connect=False")
                    return False

            # 初始化实时订阅器
            if self.message_bus:
                self.realtime_subscriber = RealtimeSubscriber(
                    message_bus=self.message_bus,
                    buffer_size=self.buffer_size
                )

            self._connected = True
            logger.info(f"MessageProvider 连接成功: {self.instance_name}/{self.session_id}")
            return True

        except Exception as e:
            logger.error(f"连接失败: {e}")
            self._connected = False
            return False

    async def disconnect(self):
        """
        断开连接并清理资源
        """
        try:
            # 停止实时订阅
            if self.realtime_subscriber:
                await self.realtime_subscriber.stop_all()
                self.realtime_subscriber = None

            # 断开 MessageBus（注意：不关闭共享的 MessageBus）
            # MessageBus 的生命周期由外部管理

            self._connected = False
            self._session_info = None
            logger.info(f"MessageProvider 已断开: {self.instance_name}/{self.session_id}")

        except Exception as e:
            logger.error(f"断开连接时出错: {e}")

    async def get_messages(
        self,
        from_beginning: bool = True,
        include_realtime: bool = True,
        message_types: Optional[List[str]] = None,
        merge_strategy: str = "historical_first",
        max_messages: Optional[int] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        获取完整消息流（历史 + 实时）

        Args:
            from_beginning: 是否从历史消息开始
            include_realtime: 是否包含实时消息
            message_types: 过滤的消息类型列表
            merge_strategy: 合并策略（"historical_first", "interleaved", "realtime_priority"）
            max_messages: 最大消息数量限制

        Yields:
            标准化后的消息字典

        Raises:
            ValueError: 参数无效时
            RuntimeError: 连接未建立时
        """
        if not self._connected and self._context_active:
            # 在上下文中自动连接
            await self.connect()

        # 验证参数
        if not from_beginning and not include_realtime:
            raise ValueError("至少需要选择一种消息源（from_beginning 或 include_realtime）")

        if max_messages is not None and max_messages <= 0:
            raise ValueError("max_messages 必须大于 0")

        try:
            # 创建流
            historical_stream = None
            realtime_stream = None

            # 历史消息流
            if from_beginning:
                historical_stream = self.message_reader.read_messages(
                    instance_name=self.instance_name,
                    session_id=self.session_id,
                    message_types=message_types,
                    normalize=True
                )

            # 实时消息流
            if include_realtime and self.realtime_subscriber:
                realtime_stream = self.realtime_subscriber.subscribe_session(
                    session_id=self.session_id,
                    message_types=message_types,
                    include_metadata=True
                )

            # 合并流
            if historical_stream and realtime_stream:
                merged_stream = self.message_merger.merge_streams(
                    historical_stream=historical_stream,
                    realtime_stream=realtime_stream,
                    strategy=merge_strategy
                )
            elif historical_stream:
                merged_stream = historical_stream
            elif realtime_stream:
                merged_stream = realtime_stream
            else:
                logger.warning("没有可用的消息流")
                return

            # 产出消息（限制数量）
            message_count = 0
            async for message in merged_stream:
                if message is None:
                    continue

                # 添加会话信息
                if self._session_info:
                    message['_session_info'] = {
                        'total_messages': self._session_info['total_messages'],
                        'instance_name': self.instance_name,
                        'session_id': self.session_id,
                    }

                yield message

                # 检查数量限制
                message_count += 1
                if max_messages and message_count >= max_messages:
                    logger.info(f"达到最大消息数量限制: {max_messages}")
                    break

        except Exception as e:
            logger.error(f"获取消息流失败: {e}")
            raise

    async def get_historical_messages(
        self,
        message_types: Optional[List[str]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        仅获取历史消息

        Args:
            message_types: 过滤的消息类型列表
            limit: 消息数量限制
            offset: 偏移量（跳过的消息数）

        Yields:
            历史消息字典
        """
        try:
            count = 0
            skipped = 0

            async for message in self.message_reader.read_messages(
                instance_name=self.instance_name,
                session_id=self.session_id,
                message_types=message_types,
                normalize=True
            ):
                # 跳过偏移量
                if offset is not None and skipped < offset:
                    skipped += 1
                    continue

                # 检查数量限制
                if limit is not None and count >= limit:
                    break

                # 添加会话信息
                if self._session_info:
                    message['_session_info'] = {
                        'total_messages': self._session_info['total_messages'],
                        'instance_name': self.instance_name,
                        'session_id': self.session_id,
                        'source': 'historical_only',
                    }

                yield message
                count += 1

        except Exception as e:
            logger.error(f"获取历史消息失败: {e}")
            raise

    async def subscribe_realtime_messages(
        self,
        message_types: Optional[List[str]] = None,
        include_heartbeat: bool = False
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        仅订阅实时消息

        Args:
            message_types: 过滤的消息类型列表
            include_heartbeat: 是否包含心跳消息

        Yields:
            实时消息字典
        """
        if not self.realtime_subscriber:
            logger.warning("实时订阅器未初始化")
            return

        try:
            async for message in self.realtime_subscriber.subscribe_session(
                session_id=self.session_id,
                message_types=message_types,
                include_metadata=True
            ):
                # 过滤心跳消息
                if not include_heartbeat and message.get('seq') == -1:
                    continue

                # 添加会话信息
                if self._session_info:
                    message['_session_info'] = {
                        'total_messages': self._session_info['total_messages'],
                        'instance_name': self.instance_name,
                        'session_id': self.session_id,
                        'source': 'realtime_only',
                    }

                yield message

        except Exception as e:
            logger.error(f"订阅实时消息失败: {e}")
            raise

    async def get_single_message(
        self,
        seq: int,
        prefer_realtime: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        获取指定序号的单条消息

        Args:
            seq: 消息序号
            prefer_realtime: 是否优先从实时消息获取

        Returns:
            消息字典，如果找不到则返回 None
        """
        try:
            # 优先从历史消息获取
            if not prefer_realtime:
                return await self.message_reader.read_single_message(
                    instance_name=self.instance_name,
                    session_id=self.session_id,
                    seq=seq,
                    normalize=True
                )

            # 从实时消息获取（更复杂，需要扫描）
            # 这里简化实现，优先从历史获取
            return await self.message_reader.read_single_message(
                instance_name=self.instance_name,
                session_id=self.session_id,
                seq=seq,
                normalize=True
            )

        except Exception as e:
            logger.error(f"获取单条消息失败: {e}, seq={seq}")
            return None

    async def get_message_count(self, message_types: Optional[List[str]] = None) -> int:
        """
        获取消息总数

        Args:
            message_types: 过滤的消息类型列表

        Returns:
            消息数量
        """
        try:
            return await self.message_reader.get_message_count(
                instance_name=self.instance_name,
                session_id=self.session_id,
                message_types=message_types
            )

        except Exception as e:
            logger.error(f"获取消息数量失败: {e}")
            return 0

    async def validate_session(self) -> bool:
        """
        验证会话是否存在

        Returns:
            会话是否存在
        """
        try:
            return await self.message_reader.validate_session_exists(
                self.instance_name,
                self.session_id
            )

        except Exception as e:
            logger.error(f"验证会话失败: {e}")
            return False

    async def get_session_info(self) -> Dict[str, Any]:
        """
        获取会话信息

        Returns:
            会话信息字典
        """
        try:
            if not self._session_info:
                self._session_info = await self.message_reader.get_session_info(
                    self.instance_name,
                    self.session_id
                )

            return self._session_info

        except Exception as e:
            logger.error(f"获取会话信息失败: {e}")
            return {}

    def normalize_message(self, raw_message: Dict[str, Any]) -> Dict[str, Any]:
        """
        标准化消息格式（兼容性方法）

        Args:
            raw_message: 原始消息

        Returns:
            标准化后的消息
        """
        try:
            # 判断消息来源
            source = raw_message.get('source', 'unknown')

            if source == 'historical':
                return MessageFormatter.normalize_historical_message(
                    message=raw_message,
                    instance_name=self.instance_name,
                    session_id=self.session_id
                )
            elif source == 'realtime':
                return MessageFormatter.normalize_realtime_message(raw_message)
            else:
                # 尝试自动判断
                if 'event_type' in raw_message:
                    return MessageFormatter.normalize_realtime_message(raw_message)
                else:
                    return MessageFormatter.normalize_historical_message(
                        message=raw_message,
                        instance_name=self.instance_name,
                        session_id=self.session_id
                    )

        except Exception as e:
            logger.error(f"标准化消息失败: {e}")
            return raw_message

    @property
    def is_connected(self) -> bool:
        """
        检查是否已连接

        Returns:
            连接状态
        """
        return self._connected

    @property
    def is_realtime_available(self) -> bool:
        """
        检查实时消息是否可用

        Returns:
            实时消息可用性
        """
        return self.realtime_subscriber is not None and self.realtime_subscriber.is_connected

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计信息字典
        """
        stats = {
            'instance_name': self.instance_name,
            'session_id': self.session_id,
            'connected': self._connected,
            'realtime_available': self.is_realtime_available,
            'has_session_info': self._session_info is not None,
        }

        # 添加合并器统计
        merger_stats = self.message_merger.get_statistics()
        stats['merger'] = merger_stats

        # 添加订阅器统计
        if self.realtime_subscriber:
            stats['realtime_subscriptions'] = self.realtime_subscriber.active_subscriptions

        return stats