"""
消息格式化器

负责统一历史消息和实时消息的格式，确保两种来源的消息具有相同的字段结构。
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class MessageFormatter:
    """
    消息格式化器

    统一历史消息和实时消息的格式，消除两种来源的差异。
    """

    @staticmethod
    def normalize_historical_message(
        message: Dict[str, Any],
        instance_name: str,
        session_id: str,
        parent_session_id: Optional[str] = None,
        depth: int = 0
    ) -> Dict[str, Any]:
        """
        标准化历史消息格式

        Args:
            message: 从 messages.jsonl 读取的原始消息
            instance_name: 实例名称
            session_id: 会话 ID
            parent_session_id: 父会话 ID
            depth: 会话深度

        Returns:
            标准化后的消息字典
        """
        try:
            # 获取基础信息
            seq = message.get('seq', 0)
            timestamp = message.get('timestamp', datetime.now().isoformat())
            message_type = message.get('message_type', 'Unknown')
            data = message.get('data', {})

            # 构建标准化消息
            normalized = {
                # 基础元数据
                'seq': seq,
                'timestamp': timestamp,
                'message_type': message_type,

                # 会话关联信息
                'instance_name': instance_name,
                'session_id': session_id,
                'parent_session_id': parent_session_id,
                'depth': depth,

                # 消息内容
                'data': data,

                # 来源标记
                'source': 'historical',
                # 历史消息没有接收时间
            }

            # 验证必要字段
            if not isinstance(seq, int) or seq < 0:
                logger.warning(f"无效的消息序号: {seq}, 消息将被忽略")
                return None

            return normalized

        except Exception as e:
            logger.error(f"标准化历史消息失败: {e}, 消息: {message}")
            return None

    @staticmethod
    def normalize_realtime_message(event: Dict[str, Any]) -> Dict[str, Any]:
        """
        标准化实时消息格式

        Args:
            event: 从 Redis 接收的实时事件

        Returns:
            标准化后的消息字典
        """
        try:
            # 获取事件信息
            seq = event.get('seq', 0)
            timestamp = event.get('timestamp', datetime.now().isoformat())
            message_type = event.get('message_type', 'Unknown')
            data = event.get('data', {})

            # 获取会话关联信息
            instance_name = event.get('instance_name')
            session_id = event.get('session_id')
            parent_session_id = event.get('parent_session_id')
            depth = event.get('depth', 0)

            # 验证必要字段
            if not instance_name or not session_id:
                logger.warning(f"实时消息缺少必要信息: instance_name={instance_name}, session_id={session_id}")
                return None

            # 构建标准化消息
            normalized = {
                # 基础元数据
                'seq': seq,
                'timestamp': timestamp,
                'message_type': message_type,

                # 会话关联信息
                'instance_name': instance_name,
                'session_id': session_id,
                'parent_session_id': parent_session_id,
                'depth': depth,

                # 消息内容
                'data': data,

                # 来源标记
                'source': 'realtime',
                'received_at': datetime.now().isoformat(),  # 接收时间
            }

            # 验证消息序号
            if not isinstance(seq, int) or seq < 0:
                logger.warning(f"无效的消息序号: {seq}, 实时消息将被忽略")
                return None

            return normalized

        except Exception as e:
            logger.error(f"标准化实时消息失败: {e}, 事件: {event}")
            return None

    @staticmethod
    def extract_metadata_from_session(metadata: Dict[str, Any]) -> tuple:
        """
        从会话元数据中提取格式化所需的信息

        Args:
            metadata: 会话元数据字典

        Returns:
            (instance_name, session_id, parent_session_id, depth) 元组
        """
        instance_name = metadata.get('instance_name', '')
        session_id = metadata.get('session_id', '')
        parent_session_id = metadata.get('parent_session_id')
        depth = metadata.get('depth', 0)

        return instance_name, session_id, parent_session_id, depth

    @staticmethod
    def is_valid_message_type(message_type: str) -> bool:
        """
        检查消息类型是否有效

        Args:
            message_type: 消息类型

        Returns:
            是否为有效的消息类型
        """
        valid_types = {
            'SystemMessage',
            'UserMessage',
            'AssistantMessage',
            'ResultMessage',
            'ToolResultMessage',
        }

        return message_type in valid_types

    @staticmethod
    def get_message_priority(message_type: str) -> int:
        """
        获取消息类型的优先级（用于排序）

        Args:
            message_type: 消息类型

        Returns:
            优先级数值（数字越小优先级越高）
        """
        priority_map = {
            'SystemMessage': 1,
            'UserMessage': 2,
            'AssistantMessage': 3,
            'ToolResultMessage': 4,
            'ResultMessage': 5,
        }

        return priority_map.get(message_type, 10)

    @staticmethod
    def format_message_for_display(message: Dict[str, Any]) -> Dict[str, Any]:
        """
        为前端显示格式化消息（添加便利字段）

        Args:
            message: 标准化后的消息

        Returns:
            前端友好的消息格式
        """
        try:
            # 复制基础信息
            display_message = message.copy()

            # 添加便利字段
            message_type = message.get('message_type', '')
            data = message.get('data', {})

            # 提取内容摘要
            if message_type == 'AssistantMessage':
                content_list = data.get('content', [])
                text_content = []
                tool_calls = []

                for content in content_list:
                    if content.get('type') == 'text':
                        text_content.append(content.get('text', ''))
                    elif content.get('type') == 'tool_use':
                        tool_calls.append({
                            'name': content.get('name', ''),
                            'id': content.get('id', ''),
                        })

                display_message['summary'] = {
                    'text': ' '.join(text_content)[:100] + ('...' if len(' '.join(text_content)) > 100 else ''),
                    'tool_calls': tool_calls,
                    'has_tools': len(tool_calls) > 0,
                }

            elif message_type == 'UserMessage':
                content = data.get('content', [])
                if isinstance(content, str):
                    text = content
                elif isinstance(content, list) and content:
                    text = content[0].get('text', '')
                else:
                    text = ''

                display_message['summary'] = {
                    'text': text[:100] + ('...' if len(text) > 100 else ''),
                }

            elif message_type == 'SystemMessage':
                subtype = data.get('subtype', '')
                display_message['summary'] = {
                    'subtype': subtype,
                }

            elif message_type == 'ResultMessage':
                result = data.get('result', '')
                is_error = data.get('is_error', False)
                display_message['summary'] = {
                    'result': result[:100] + ('...' if len(result) > 100 else ''),
                    'is_error': is_error,
                }

            # 添加时间解析
            timestamp = message.get('timestamp', '')
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    display_message['parsed_time'] = {
                        'datetime': dt,
                        'date_str': dt.strftime('%Y-%m-%d %H:%M:%S'),
                        'relative': _get_relative_time(dt),
                    }
                except Exception as e:
                    logger.warning(f"解析时间戳失败: {e}, timestamp: {timestamp}")

            # 添加消息类型图标
            display_message['icon'] = _get_message_icon(message_type)

            return display_message

        except Exception as e:
            logger.error(f"格式化消息显示失败: {e}, 消息: {message}")
            return message


def _get_relative_time(dt: datetime) -> str:
    """获取相对时间描述"""
    from datetime import datetime as dt_now, timezone

    now = dt_now.now(timezone.utc)
    delta = now - dt

    if delta.total_seconds() < 60:
        return "刚刚"
    elif delta.total_seconds() < 3600:
        minutes = int(delta.total_seconds() / 60)
        return f"{minutes}分钟前"
    elif delta.total_seconds() < 86400:
        hours = int(delta.total_seconds() / 3600)
        return f"{hours}小时前"
    else:
        days = int(delta.total_seconds() / 86400)
        return f"{days}天前"


def _get_message_icon(message_type: str) -> str:
    """获取消息类型对应的图标"""
    icon_map = {
        'SystemMessage': '⚙️',
        'UserMessage': '👤',
        'AssistantMessage': '🤖',
        'ToolResultMessage': '🔧',
        'ResultMessage': '📋',
    }

    return icon_map.get(message_type, '❓')