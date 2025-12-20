"""
会话核心模块 - Session 类

表示一次 Agent 执行会话，负责收集消息、更新元数据和统计信息。
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, List, Dict, Generator

from ...logging_config import get_logger
from ...error_handling import AgentSystemError
from ..utils.session_utils import Statistics
from ..utils.session_serializer import MessageSerializer

# 新增导入
try:
    from ..streaming.message_bus import MessageBus
    from ..storage.jsonl_writer import JSONLWriter
except ImportError:
    MessageBus = None
    JSONLWriter = None

logger = get_logger(__name__)


class Session:
    """
    单个会话对象

    表示一次 Agent 执行会话，负责收集消息、更新元数据和统计信息。
    支持实时消息推送和异步JSONL写入。
    """

    def __init__(
        self,
        session_id: str,
        session_dir: Path,
        metadata: dict,
        config: Optional[dict] = None,
        message_bus: Optional["MessageBus"] = None,  # 新增
        jsonl_writer: Optional["JSONLWriter"] = None  # 新增
    ):
        """
        初始化会话对象

        Args:
            session_id: 会话 ID
            session_dir: 会话目录路径
            metadata: 元数据字典
            config: 会话记录配置
            message_bus: 消息总线（可选）
            jsonl_writer: 异步 JSONL 写入器（可选）
        """
        self.session_id = session_id
        self.session_dir = session_dir
        self.metadata = metadata
        self.config = config or {}

        # 新增：MessageBus 和 JSONLWriter
        self._message_bus = message_bus
        self._jsonl_writer = jsonl_writer

        # 内存中收集所有消息（降级时使用）
        self._messages: List[Dict[str, Any]] = []
        self._statistics = Statistics()
        self._finalized = False

        # 消息计数器（用于 seq 序列号，支持 resume 模式）
        self._message_count = self._load_existing_message_count()

    async def start(self) -> None:
        """启动会话（创建目录和初始元数据）"""
        # 创建会话目录
        self.session_dir.mkdir(parents=True, exist_ok=True)

        # 写入初始元数据
        metadata_file = self.session_dir / "metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, indent=2, ensure_ascii=False)

        # JSONLWriter 在 __init__ 中已经自动启动了后台任务

        logger.info(f"会话已启动: {self.session_id}")

    async def record_message(self, message: Any) -> None:
        """
        记录单条消息（实时推送 + 异步写入）

        流程：
        1. 序列化消息
        2. 发布到 Redis（实时）
        3. 异步写入 JSONL
        4. 更新统计信息

        Args:
            message: Claude SDK 消息对象
        """
        # 检查消息类型过滤
        message_type = type(message).__name__
        message_types = self.config.get("message_types")
        if message_types and message_type not in message_types:
            return  # 跳过不需要记录的消息类型

        # 1. 序列化消息
        message_data = {
            "seq": self._message_count,
            "timestamp": datetime.now().isoformat(),
            "message_type": message_type,
            "data": MessageSerializer.serialize_message(message)
        }

        # 2. 发布到 Redis（实时）
        if self._message_bus:
            await self._publish_to_bus(message_data)

        # 3. 异步写入 JSONL
        if self._jsonl_writer:
            await self._jsonl_writer.write(message_data)
        else:
            # 降级：保存到内存（兼容旧逻辑）
            self._messages.append({
                "seq": self._message_count,
                "timestamp": message_data["timestamp"],
                "message": message
            })

        # 4. 更新计数器
        self._message_count += 1

        # 5. 更新统计信息
        self._statistics.num_messages += 1

        # 检查是否是工具调用
        if message_type == "AssistantMessage":
            from claude_agent_sdk import ToolUseBlock
            for block in message.content:
                if isinstance(block, ToolUseBlock):
                    self._statistics.num_tool_calls += 1
                    tool_name = block.name
                    self._statistics.tools_used[tool_name] = \
                        self._statistics.tools_used.get(tool_name, 0) + 1

        # ✅ 检测子实例工具调用并记录 session_id
        if message_type == "AssistantMessage":
            self._detect_and_record_subsession(message)

    async def _publish_to_bus(self, message_data: dict) -> None:
        """
        发布消息到 Redis

        Args:
            message_data: 序列化后的消息数据
        """
        if not self._message_bus or not self._message_bus.is_connected:
            return

        event = {
            "event_type": "message_created",
            "timestamp": message_data["timestamp"],
            "instance_name": self.metadata["instance_name"],
            "session_id": self.session_id,
            "parent_session_id": self.metadata.get("parent_session_id"),
            "depth": self.metadata.get("depth", 0),
            "seq": message_data["seq"],
            "message_type": message_data["message_type"],
            "data": message_data["data"]
        }

        # 发布到多个频道
        session_channel = f"session:{self.session_id}"
        instance_channel = f"instance:{self.metadata['instance_name']}"

        logger.info(f"[Session] {self.metadata['instance_name']} 发布消息到频道: {session_channel}")
        await self._message_bus.publish(session_channel, event)

        logger.info(f"[Session] {self.metadata['instance_name']} 发布消息到频道: {instance_channel}")
        await self._message_bus.publish(instance_channel, event)

    def _detect_and_record_subsession(self, message: Any) -> None:
        """
        检测并记录子实例工具调用

        Args:
            message: AssistantMessage 对象
        """
        from claude_agent_sdk import ToolUseBlock, ToolResultBlock

        # 收集工具调用 ID 和名称的映射
        tool_use_map = {}
        for block in message.content:
            if isinstance(block, ToolUseBlock):
                tool_use_map[block.id] = block.name

        # 检查工具结果中是否有子实例 session_id
        for block in message.content:
            if isinstance(block, ToolResultBlock):
                tool_name = tool_use_map.get(block.tool_use_id)

                # 只处理子实例工具（包含 "sub_claude_"）
                if tool_name and "sub_claude_" in tool_name:
                    sub_session_id = self._extract_session_id_from_result(block)
                    if sub_session_id:
                        self._statistics.subsessions.append({
                            "session_id": sub_session_id,
                            "tool_name": tool_name,
                            "tool_use_id": block.tool_use_id,
                            "timestamp": datetime.now().isoformat()
                        })
                        logger.info(f"检测到子实例调用: {tool_name} -> {sub_session_id}")

    def _extract_session_id_from_result(self, tool_result_block: Any) -> Optional[str]:
        """
        从 ToolResultBlock 中提取子实例的 session_id

        Args:
            tool_result_block: ToolResultBlock 对象

        Returns:
            session_id 字符串，如果不存在则返回 None
        """
        try:
            import json
            import re

            # ToolResultBlock.content 可能是字符串或列表
            content = tool_result_block.content

            # 如果是列表，查找包含 session_id 的 block
            if isinstance(content, list):
                for block in content:
                    # 检查 TextBlock
                    if hasattr(block, 'text'):
                        text = block.text
                        # 使用特殊标记 <!--SESSION_ID:xxx-->
                        match = re.search(r'<!--SESSION_ID:([^>]+)-->', text)
                        if match:
                            return match.group(1)

            # 如果是字符串，直接解析
            elif isinstance(content, str):
                match = re.search(r'<!--SESSION_ID:([^>]+)-->', content)
                if match:
                    return match.group(1)

            return None

        except Exception as e:
            logger.debug(f"提取 session_id 失败: {e}")
            return None

    async def finalize(self, result_message: Optional[Any] = None) -> None:
        """
        完成会话（强制刷新 + 写入元数据）

        Args:
            result_message: ResultMessage 对象（可选）
        """
        if self._finalized:
            logger.warning(f"会话 {self.session_id} 已经完成")
            return

        self._finalized = True

        # 强制刷新 JSONLWriter
        if self._jsonl_writer:
            await self._jsonl_writer.finalize()
        else:
            # 降级：一次性写入内存中的消息
            await self._write_messages_to_jsonl()

        # 更新元数据
        self.metadata['end_time'] = datetime.now().isoformat()

        if self.metadata.get('status') == 'running':
            self.metadata['status'] = 'completed'

        # 从 ResultMessage 提取信息
        if result_message:
            self._statistics.total_duration_ms = getattr(result_message, 'duration_ms', 0)
            self._statistics.api_duration_ms = getattr(result_message, 'duration_api_ms', 0)
            self._statistics.num_turns = getattr(result_message, 'num_turns', 0)
            self._statistics.token_usage = getattr(result_message, 'usage', None)
            self._statistics.cost_usd = getattr(result_message, 'total_cost_usd', None)
            self._statistics.final_status = 'failed' if getattr(result_message, 'is_error', False) else 'completed'

            # 更新元数据中的结果数组
            if hasattr(result_message, 'result') and result_message.result:
                if 'results' not in self.metadata:
                    self.metadata['results'] = []
                self.metadata['results'].append({
                    "result": result_message.result[:500],  # 限制长度
                    "timestamp": datetime.now().isoformat(),
                    "is_error": getattr(result_message, 'is_error', False)
                })

        # 写入元数据
        metadata_file = self.session_dir / "metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, indent=2, ensure_ascii=False)

        # 写入统计信息
        statistics_file = self.session_dir / "statistics.json"
        statistics_dict = {
            "session_id": self.session_id,
            **self._statistics.to_dict()
        }
        with open(statistics_file, 'w', encoding='utf-8') as f:
            json.dump(statistics_dict, f, indent=2, ensure_ascii=False)

        # 清空内存中的消息，释放内存
        self._messages.clear()

        logger.info(f"会话已完成: {self.session_id} (状态={self._statistics.final_status}, 消息数={self._statistics.num_messages})")

    async def _write_messages_to_jsonl(self) -> None:
        """
        降级方法：一次性写入内存中的消息

        只在没有 JSONLWriter 时使用
        """
        if not self._messages:
            return

        messages_file = self.session_dir / "messages.jsonl"

        # 如果文件存在，说明是 resume 模式，使用追加模式
        mode = 'a' if messages_file.exists() else 'w'

        with open(messages_file, mode, encoding='utf-8') as f:
            for msg_data in self._messages:
                try:
                    message_dict = MessageSerializer.serialize_message(msg_data['message'])
                    json_line = json.dumps({
                        "seq": msg_data['seq'],
                        "timestamp": msg_data['timestamp'],
                        "message_type": type(msg_data['message']).__name__,
                        "data": message_dict
                    }, ensure_ascii=False)
                    f.write(json_line + '\n')
                except Exception as e:
                    logger.error(f"序列化消息失败: {e}")

    def _load_existing_message_count(self) -> int:
        """
        加载已存在的消息数量（用于 resume 模式）

        Returns:
            已写入的消息数量
        """
        messages_file = self.session_dir / "messages.jsonl"

        if not messages_file.exists():
            return 0

        # 统计已有消息数量
        count = 0
        try:
            with open(messages_file, 'r', encoding='utf-8') as f:
                for _ in f:
                    count += 1
        except Exception as e:
            logger.warning(f"读取已有消息数量失败: {e}")
            return 0

        return count

    def get_messages(
        self,
        message_types: Optional[List[str]] = None,
        limit: Optional[int] = None
    ) -> Generator[dict, None, None]:
        """
        读取消息记录（流式生成器）

        Args:
            message_types: 过滤消息类型（可选）
            limit: 限制返回数量（可选）

        Yields:
            消息字典
        """
        messages_file = self.session_dir / "messages.jsonl"

        if not messages_file.exists():
            return

        count = 0
        with open(messages_file, 'r', encoding='utf-8') as f:
            for line in f:
                if limit and count >= limit:
                    break

                try:
                    msg = json.loads(line)

                    # 过滤消息类型
                    if message_types and msg['message_type'] not in message_types:
                        continue

                    yield msg
                    count += 1

                except json.JSONDecodeError:
                    logger.warning(f"跳过无效 JSON 行: {line[:100]}")

    def get_metadata(self) -> dict:
        """获取元数据"""
        return self.metadata.copy()

    def get_statistics(self) -> dict:
        """获取统计信息"""
        return self._statistics.to_dict()

