"""
历史消息读取器

负责异步读取会话的历史消息，支持流式处理和消息过滤。
"""

import json
import logging
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional

import aiofiles

from .message_formatter import MessageFormatter

logger = logging.getLogger(__name__)


class MessageReader:
    """
    历史消息读取器

    提供异步流式读取历史消息的功能，支持消息类型过滤和错误处理。
    """

    def __init__(
        self,
        instances_root: Optional[Path] = None,
        batch_size: int = 100
    ):
        """
        初始化消息读取器

        Args:
            instances_root: 实例根目录路径
            batch_size: 批量读取大小，用于性能优化
        """
        self.instances_root = instances_root or Path("instances")
        self.batch_size = batch_size

    async def read_messages(
        self,
        instance_name: str,
        session_id: str,
        message_types: Optional[List[str]] = None,
        normalize: bool = True
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        读取会话的历史消息

        Args:
            instance_name: 实例名称
            session_id: 会话 ID
            message_types: 过滤的消息类型列表，None 表示不过滤
            normalize: 是否标准化消息格式

        Yields:
            原始或标准化后的消息字典
        """
        session_dir = self.instances_root / instance_name / "sessions" / session_id
        messages_file = session_dir / "messages.jsonl"

        if not messages_file.exists():
            logger.warning(f"消息文件不存在: {messages_file}")
            return

        try:
            # 读取会话元数据
            metadata = await self._read_session_metadata(session_dir)

            batch = []
            async with aiofiles.open(messages_file, 'r', encoding='utf-8') as f:
                async for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        # 解析消息
                        message = json.loads(line)

                        # 类型过滤
                        if message_types and message.get('message_type') not in message_types:
                            continue

                        # 标准化消息
                        if normalize:
                            normalized_message = MessageFormatter.normalize_historical_message(
                                message=message,
                                instance_name=instance_name,
                                session_id=session_id,
                                parent_session_id=metadata.get('parent_session_id'),
                                depth=metadata.get('depth', 0)
                            )
                            if normalized_message:
                                batch.append(normalized_message)
                        else:
                            batch.append(message)

                        # 批量产出
                        if len(batch) >= self.batch_size:
                            for msg in batch:
                                yield msg
                            batch = []

                    except json.JSONDecodeError as e:
                        logger.warning(f"跳过无效的JSON行: {e}, 内容: {line[:100]}...")
                        continue
                    except Exception as e:
                        logger.error(f"处理消息时出错: {e}, 行内容: {line[:100]}...")
                        continue

                # 产出最后一批
                for msg in batch:
                    yield msg

        except Exception as e:
            logger.error(f"读取消息文件失败: {e}, 文件: {messages_file}")
            raise

    async def read_single_message(
        self,
        instance_name: str,
        session_id: str,
        seq: int,
        normalize: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        读取指定序号的单条消息

        Args:
            instance_name: 实例名称
            session_id: 会话 ID
            seq: 消息序号
            normalize: 是否标准化消息格式

        Returns:
            消息字典，如果找不到则返回 None
        """
        try:
            async for message in self.read_messages(instance_name, session_id, normalize=normalize):
                if message.get('seq') == seq:
                    return message

            return None

        except Exception as e:
            logger.error(f"读取单条消息失败: {e}, instance={instance_name}, session={session_id}, seq={seq}")
            return None

    async def get_message_count(
        self,
        instance_name: str,
        session_id: str,
        message_types: Optional[List[str]] = None
    ) -> int:
        """
        获取消息总数

        Args:
            instance_name: 实例名称
            session_id: 会话 ID
            message_types: 过滤的消息类型列表

        Returns:
            消息数量
        """
        count = 0
        try:
            async for _ in self.read_messages(
                instance_name,
                session_id,
                message_types=message_types,
                normalize=False
            ):
                count += 1

            return count

        except Exception as e:
            logger.error(f"获取消息数量失败: {e}, instance={instance_name}, session={session_id}")
            return 0

    async def get_message_range(
        self,
        instance_name: str,
        session_id: str,
        start_seq: Optional[int] = None,
        end_seq: Optional[int] = None,
        normalize: bool = True
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        获取指定序号范围的消息

        Args:
            instance_name: 实例名称
            session_id: 会话 ID
            start_seq: 起始序号（包含），None 表示从第一条开始
            end_seq: 结束序号（包含），None 表示到最后一条
            normalize: 是否标准化消息格式

        Yields:
            指定范围内的消息
        """
        try:
            async for message in self.read_messages(instance_name, session_id, normalize=normalize):
                seq = message.get('seq', -1)

                # 检查序号范围
                if start_seq is not None and seq < start_seq:
                    continue
                if end_seq is not None and seq > end_seq:
                    break

                yield message

        except Exception as e:
            logger.error(f"获取消息范围失败: {e}, instance={instance_name}, session={session_id}")

    async def get_latest_messages(
        self,
        instance_name: str,
        session_id: str,
        limit: int = 50,
        message_types: Optional[List[str]] = None,
        normalize: bool = True
    ) -> List[Dict[str, Any]]:
        """
        获取最新的 N 条消息

        Args:
            instance_name: 实例名称
            session_id: 会话 ID
            limit: 消息数量限制
            message_types: 过滤的消息类型列表
            normalize: 是否标准化消息格式

        Returns:
            最新的消息列表（按时间倒序）
        """
        messages = []
        try:
            async for message in self.read_messages(
                instance_name,
                session_id,
                message_types=message_types,
                normalize=normalize
            ):
                messages.append(message)

                # 限制数量
                if len(messages) > limit:
                    messages = messages[-limit:]

            return messages

        except Exception as e:
            logger.error(f"获取最新消息失败: {e}, instance={instance_name}, session={session_id}")
            return []

    async def validate_session_exists(
        self,
        instance_name: str,
        session_id: str
    ) -> bool:
        """
        验证会话是否存在

        Args:
            instance_name: 实例名称
            session_id: 会话 ID

        Returns:
            会话是否存在
        """
        session_dir = self.instances_root / instance_name / "sessions" / session_id
        messages_file = session_dir / "messages.jsonl"

        return session_dir.exists() and messages_file.exists()

    async def get_session_info(
        self,
        instance_name: str,
        session_id: str
    ) -> Dict[str, Any]:
        """
        获取会话基本信息

        Args:
            instance_name: 实例名称
            session_id: 会话 ID

        Returns:
            包含会话信息的字典
        """
        session_dir = self.instances_root / instance_name / "sessions" / session_id

        # 读取元数据
        metadata = await self._read_session_metadata(session_dir)

        # 获取消息统计
        total_messages = await self.get_message_count(instance_name, session_id)
        latest_seq = await self._get_latest_seq(instance_name, session_id)

        return {
            'instance_name': instance_name,
            'session_id': session_id,
            'exists': await self.validate_session_exists(instance_name, session_id),
            'total_messages': total_messages,
            'latest_seq': latest_seq,
            'metadata': metadata,
        }

    async def _read_session_metadata(self, session_dir: Path) -> Dict[str, Any]:
        """
        读取会话元数据

        Args:
            session_dir: 会话目录路径

        Returns:
            元数据字典
        """
        metadata_file = session_dir / "metadata.json"

        if not metadata_file.exists():
            return {}

        try:
            async with aiofiles.open(metadata_file, 'r', encoding='utf-8') as f:
                content = await f.read()
                return json.loads(content)

        except Exception as e:
            logger.error(f"读取会话元数据失败: {e}, 文件: {metadata_file}")
            return {}

    async def _get_latest_seq(
        self,
        instance_name: str,
        session_id: str
    ) -> int:
        """
        获取最新的消息序号

        Args:
            instance_name: 实例名称
            session_id: 会话 ID

        Returns:
            最新消息序号，-1 表示没有消息
        """
        latest_seq = -1
        try:
            async for message in self.read_messages(
                instance_name,
                session_id,
                normalize=False
            ):
                seq = message.get('seq', -1)
                if seq > latest_seq:
                    latest_seq = seq

            return latest_seq

        except Exception as e:
            logger.error(f"获取最新序号失败: {e}, instance={instance_name}, session={session_id}")
            return -1