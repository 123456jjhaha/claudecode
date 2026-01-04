"""
会话序列化模块

负责将 Claude SDK 消息对象序列化为 JSON 可存储的格式
"""

from typing import Any
from ...logging_config import get_logger

logger = get_logger(__name__)


class MessageSerializer:
    """消息序列化器"""

    @staticmethod
    def serialize_message(message: Any) -> dict:
        """
        序列化消息对象为 JSON 可序列化的字典

        Args:
            message: Claude SDK 消息对象

        Returns:
            消息数据字典
        """
        message_type = type(message).__name__

        try:
            # 导入消息类型（延迟导入避免循环依赖）
            from claude_agent_sdk import (
                AssistantMessage,
                ResultMessage,
                UserMessage,
                SystemMessage
            )

            if isinstance(message, AssistantMessage):
                return {
                    "model": message.model,
                    "content": [MessageSerializer._serialize_content_block(b) for b in message.content]
                }

            elif isinstance(message, ResultMessage):
                return {
                    "subtype": message.subtype,
                    "duration_ms": message.duration_ms,
                    "duration_api_ms": message.duration_api_ms,
                    "is_error": message.is_error,
                    "num_turns": message.num_turns,
                    "session_id": getattr(message, 'session_id', None),
                    "total_cost_usd": message.total_cost_usd,
                    "usage": message.usage,
                    "result": message.result
                }

            elif isinstance(message, UserMessage):
                content = message.content
                if isinstance(content, str):
                    content_data = content
                else:
                    content_data = [MessageSerializer._serialize_content_block(b) for b in content]

                return {
                    "role": "user",
                    "content": content_data
                }

            elif isinstance(message, SystemMessage):
                return {
                    "subtype": message.subtype,
                    "data": message.data
                }

            else:
                # 未知类型，尝试通用序列化
                return MessageSerializer._generic_serialize(message)

        except Exception as e:
            logger.error(f"消息序列化失败 ({message_type}): {e}")
            return {
                "error": str(e),
                "message_type": message_type
            }

    @staticmethod
    def _serialize_content_block(block: Any) -> dict:
        """序列化内容块"""
        from claude_agent_sdk import TextBlock, ToolUseBlock, ToolResultBlock

        try:
            if isinstance(block, TextBlock):
                return {
                    "type": "text",
                    "text": block.text
                }

            elif isinstance(block, ToolUseBlock):
                return {
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input
                }

            elif isinstance(block, ToolResultBlock):
                return {
                    "type": "tool_result",
                    "tool_use_id": block.tool_use_id,
                    "content": block.content,
                    "is_error": block.is_error
                }

            # ThinkingBlock
            elif hasattr(block, 'thinking'):
                return {
                    "type": "thinking",
                    "thinking": block.thinking,
                    "signature": getattr(block, 'signature', None)
                }

            else:
                return MessageSerializer._generic_serialize(block)

        except Exception as e:
            logger.error(f"内容块序列化失败: {e}")
            return {"type": "error", "error": str(e)}

    @staticmethod
    def _generic_serialize(obj: Any) -> Any:
        """通用对象序列化"""
        if hasattr(obj, '__dict__'):
            return {k: MessageSerializer._generic_serialize(v) for k, v in obj.__dict__.items() if not k.startswith('_')}
        elif isinstance(obj, (list, tuple)):
            return [MessageSerializer._generic_serialize(item) for item in obj]
        elif isinstance(obj, dict):
            return {k: MessageSerializer._generic_serialize(v) for k, v in obj.items()}
        else:
            return obj
