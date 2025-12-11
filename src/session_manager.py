"""
会话管理模块

提供会话记录、查询和管理功能，包括：
- AsyncMessageWriter: 异步消息写入器
- Session: 单个会话对象
- SessionManager: 会话管理器
"""

import json
import asyncio
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional, List, Dict, Generator
from dataclasses import dataclass, asdict
import secrets
import time

from .logging_config import get_logger
from .error_handling import AgentSystemError

logger = get_logger(__name__)


def generate_session_id() -> str:
    """
    生成会话 ID

    格式：{timestamp}_{counter}_{short_hash}
    示例：20251211T061755_0001_a3f9c2d8

    Returns:
        会话 ID 字符串
    """
    # ISO 8601 格式时间戳（精确到秒）
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")

    # 4位数字计数器（同一秒内递增）
    # 使用纳秒的后4位作为简单计数器
    counter = f"{datetime.now().microsecond % 10000:04d}"

    # 8位随机十六进制字符串
    short_hash = secrets.token_hex(4)

    return f"{timestamp}_{counter}_{short_hash}"


class AsyncMessageWriter:
    """
    异步消息写入器

    使用后台队列和异步任务实现非阻塞消息写入，
    支持批量写入优化以减少 I/O 次数。
    """

    def __init__(
        self,
        messages_file: Path,
        batch_size: int = 10,
        batch_timeout: float = 0.5,
        queue_size: int = 1000
    ):
        """
        初始化写入器

        Args:
            messages_file: messages.jsonl 文件路径
            batch_size: 批量写入大小
            batch_timeout: 批量超时（秒）
            queue_size: 消息队列最大大小
        """
        self._messages_file = messages_file
        self._batch_size = batch_size
        self._batch_timeout = batch_timeout
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=queue_size)
        self._seq = 0
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._started = False

    async def start(self) -> None:
        """启动后台写入任务"""
        if self._started:
            logger.warning("AsyncMessageWriter 已经启动")
            return

        self._started = True
        self._task = asyncio.create_task(self._writer_loop())
        logger.debug(f"AsyncMessageWriter 已启动: {self._messages_file}")

    async def write(self, message: Any) -> None:
        """
        写入消息到队列（非阻塞）

        Args:
            message: Claude SDK 消息对象
        """
        if not self._started:
            logger.warning("AsyncMessageWriter 未启动，消息将被丢弃")
            return

        try:
            # 使用 put_nowait 避免阻塞
            self._queue.put_nowait({
                "seq": self._seq,
                "timestamp": datetime.now().isoformat(),
                "message": message
            })
            self._seq += 1
        except asyncio.QueueFull:
            # 队列满时记录警告，但不阻塞主流程
            logger.warning(f"消息队列已满（大小={self._queue.maxsize}），跳过消息记录")

    async def stop(self) -> None:
        """停止写入器（等待队列清空）"""
        if not self._started:
            return

        self._stop_event.set()

        if self._task:
            await self._task

        self._started = False
        logger.debug(f"AsyncMessageWriter 已停止: {self._messages_file}")

    async def _writer_loop(self) -> None:
        """后台写入循环（批量写入版本）"""
        batch = []
        last_write = time.time()

        # 确保目录存在
        self._messages_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(self._messages_file, 'a', encoding='utf-8') as f:
                while not self._stop_event.is_set() or not self._queue.empty():
                    try:
                        # 尝试获取消息
                        item = await asyncio.wait_for(
                            self._queue.get(),
                            timeout=0.1
                        )
                        batch.append(item)

                        # 达到批量大小或超时，执行写入
                        current_time = time.time()
                        should_flush = (
                            len(batch) >= self._batch_size or
                            (current_time - last_write) > self._batch_timeout
                        )

                        if should_flush:
                            for b in batch:
                                try:
                                    message_dict = self._serialize_message(b['message'])
                                    json_line = json.dumps({
                                        "seq": b['seq'],
                                        "timestamp": b['timestamp'],
                                        "message_type": message_dict['type'],
                                        "data": message_dict['data']
                                    }, ensure_ascii=False)

                                    f.write(json_line + '\n')
                                except Exception as e:
                                    logger.error(f"序列化消息失败: {e}")

                            f.flush()
                            batch.clear()
                            last_write = current_time

                    except asyncio.TimeoutError:
                        # 超时也触发写入（如果有数据）
                        if batch and (time.time() - last_write) > self._batch_timeout:
                            for b in batch:
                                try:
                                    message_dict = self._serialize_message(b['message'])
                                    json_line = json.dumps({
                                        "seq": b['seq'],
                                        "timestamp": b['timestamp'],
                                        "message_type": message_dict['type'],
                                        "data": message_dict['data']
                                    }, ensure_ascii=False)

                                    f.write(json_line + '\n')
                                except Exception as e:
                                    logger.error(f"序列化消息失败: {e}")

                            f.flush()
                            batch.clear()
                            last_write = time.time()

                # 写入剩余消息
                if batch:
                    for b in batch:
                        try:
                            message_dict = self._serialize_message(b['message'])
                            json_line = json.dumps({
                                "seq": b['seq'],
                                "timestamp": b['timestamp'],
                                "message_type": message_dict['type'],
                                "data": message_dict['data']
                            }, ensure_ascii=False)

                            f.write(json_line + '\n')
                        except Exception as e:
                            logger.error(f"序列化消息失败: {e}")

                    f.flush()

        except Exception as e:
            logger.error(f"AsyncMessageWriter 写入循环异常: {e}")

    def _serialize_message(self, message: Any) -> dict:
        """
        序列化消息对象为 JSON 可序列化的字典

        Args:
            message: Claude SDK 消息对象

        Returns:
            包含 type 和 data 的字典
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
                    "type": "AssistantMessage",
                    "data": {
                        "model": message.model,
                        "content": [self._serialize_content_block(b) for b in message.content]
                    }
                }

            elif isinstance(message, ResultMessage):
                return {
                    "type": "ResultMessage",
                    "data": {
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
                }

            elif isinstance(message, UserMessage):
                content = message.content
                if isinstance(content, str):
                    content_data = content
                else:
                    content_data = [self._serialize_content_block(b) for b in content]

                return {
                    "type": "UserMessage",
                    "data": {
                        "role": "user",
                        "content": content_data
                    }
                }

            elif isinstance(message, SystemMessage):
                return {
                    "type": "SystemMessage",
                    "data": {
                        "subtype": message.subtype,
                        "data": message.data
                    }
                }

            else:
                # 未知类型，尝试通用序列化
                return {
                    "type": message_type,
                    "data": self._generic_serialize(message)
                }

        except Exception as e:
            logger.error(f"消息序列化失败 ({message_type}): {e}")
            return {
                "type": "SerializationError",
                "data": {
                    "error": str(e),
                    "message_type": message_type
                }
            }

    def _serialize_content_block(self, block: Any) -> dict:
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
                return self._generic_serialize(block)

        except Exception as e:
            logger.error(f"内容块序列化失败: {e}")
            return {"type": "error", "error": str(e)}

    def _generic_serialize(self, obj: Any) -> Any:
        """通用对象序列化"""
        if hasattr(obj, '__dict__'):
            return {k: self._generic_serialize(v) for k, v in obj.__dict__.items() if not k.startswith('_')}
        elif isinstance(obj, (list, tuple)):
            return [self._generic_serialize(item) for item in obj]
        elif isinstance(obj, dict):
            return {k: self._generic_serialize(v) for k, v in obj.items()}
        else:
            return obj


@dataclass
class Statistics:
    """会话统计信息"""
    total_duration_ms: int = 0
    api_duration_ms: int = 0
    num_turns: int = 0
    num_messages: int = 0
    num_tool_calls: int = 0
    tools_used: Dict[str, int] = None
    subsessions: List[Dict[str, Any]] = None
    token_usage: Optional[Dict[str, int]] = None
    cost_usd: Optional[float] = None
    final_status: str = "running"
    error_count: int = 0

    def __post_init__(self):
        if self.tools_used is None:
            self.tools_used = {}
        if self.subsessions is None:
            self.subsessions = []


class Session:
    """
    单个会话对象

    表示一次 Agent 执行会话，负责记录消息、更新元数据和统计信息。
    """

    def __init__(
        self,
        session_id: str,
        session_dir: Path,
        metadata: dict,
        parent_session: Optional['Session'] = None
    ):
        """
        初始化会话对象

        Args:
            session_id: 会话 ID
            session_dir: 会话目录路径
            metadata: 元数据字典
            parent_session: 父会话对象（如果是子会话）
        """
        self.session_id = session_id
        self.session_dir = session_dir
        self.metadata = metadata
        self.parent_session = parent_session

        self._message_writer: Optional[AsyncMessageWriter] = None
        self._statistics = Statistics()
        self._finalized = False

    async def start(self) -> None:
        """启动会话（创建目录和启动消息写入器）"""
        # 创建会话目录
        self.session_dir.mkdir(parents=True, exist_ok=True)

        # 写入元数据
        metadata_file = self.session_dir / "metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, indent=2, ensure_ascii=False)

        # 启动消息写入器
        messages_file = self.session_dir / "messages.jsonl"
        self._message_writer = AsyncMessageWriter(messages_file)
        await self._message_writer.start()

        logger.info(f"会话已启动: {self.session_id}")

    async def record_message(self, message: Any) -> None:
        """
        记录单条消息（异步非阻塞）

        Args:
            message: Claude SDK 消息对象
        """
        if not self._message_writer:
            logger.warning(f"会话 {self.session_id} 的消息写入器未启动")
            return

        # 异步写入消息
        await self._message_writer.write(message)

        # 更新统计信息
        self._statistics.num_messages += 1

        # 检查是否是工具调用
        message_type = type(message).__name__
        if message_type == "AssistantMessage":
            from claude_agent_sdk import ToolUseBlock

            for block in message.content:
                if isinstance(block, ToolUseBlock):
                    self._statistics.num_tool_calls += 1
                    tool_name = block.name
                    self._statistics.tools_used[tool_name] = \
                        self._statistics.tools_used.get(tool_name, 0) + 1

    async def finalize(self, result_message: Optional[Any] = None) -> None:
        """
        完成会话（更新元数据和统计信息）

        Args:
            result_message: ResultMessage 对象（可选）
        """
        if self._finalized:
            logger.warning(f"会话 {self.session_id} 已经完成")
            return

        self._finalized = True

        # 停止消息写入器
        if self._message_writer:
            await self._message_writer.stop()

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

            # 更新元数据中的结果摘要
            if hasattr(result_message, 'result') and result_message.result:
                self.metadata['result_summary'] = result_message.result[:500]  # 限制长度

        # 写入元数据
        metadata_file = self.session_dir / "metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, indent=2, ensure_ascii=False)

        # 写入统计信息
        statistics_file = self.session_dir / "statistics.json"
        statistics_dict = {
            "session_id": self.session_id,
            **asdict(self._statistics)
        }
        with open(statistics_file, 'w', encoding='utf-8') as f:
            json.dump(statistics_dict, f, indent=2, ensure_ascii=False)

        logger.info(f"会话已完成: {self.session_id} (状态={self._statistics.final_status})")

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
        return asdict(self._statistics)

    def get_subsessions(self) -> List['Session']:
        """获取所有子会话"""
        subsessions_dir = self.session_dir / "subsessions"

        if not subsessions_dir.exists():
            return []

        subsessions = []
        for sub_dir in subsessions_dir.iterdir():
            if not sub_dir.is_dir():
                continue

            metadata_file = sub_dir / "metadata.json"
            if not metadata_file.exists():
                continue

            with open(metadata_file, 'r') as f:
                metadata = json.load(f)

            subsession = Session(
                session_id=metadata['session_id'],
                session_dir=sub_dir,
                metadata=metadata,
                parent_session=self
            )
            subsessions.append(subsession)

        return subsessions

    async def create_subsession(
        self,
        instance_name: str,
        prompt: str,
        context: dict
    ) -> 'Session':
        """
        创建子会话

        Args:
            instance_name: 子实例名称
            prompt: 提示词
            context: 上下文参数

        Returns:
            子会话对象
        """
        subsessions_dir = self.session_dir / "subsessions"
        subsessions_dir.mkdir(exist_ok=True)

        session_id = generate_session_id()
        session_dir = subsessions_dir / session_id

        metadata = {
            "session_id": session_id,
            "instance_name": instance_name,
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "status": "running",
            "parent_session_id": self.session_id,
            "parent_instance_name": self.metadata['instance_name'],
            "depth": self.metadata['depth'] + 1,
            "initial_prompt": prompt,
            "result_summary": None,
            "error": None,
            "context": context
        }

        subsession = Session(
            session_id=session_id,
            session_dir=session_dir,
            metadata=metadata,
            parent_session=self
        )

        await subsession.start()

        # 记录到父会话的统计信息
        self._statistics.subsessions.append({
            "session_id": session_id,
            "instance_name": instance_name,
            "status": "running"
        })

        return subsession


class SessionManager:
    """
    会话管理器

    负责会话的创建、查询和管理。
    """

    def __init__(
        self,
        instance_path: Path,
        parent_session: Optional[Session] = None
    ):
        """
        初始化会话管理器

        Args:
            instance_path: 实例目录路径
            parent_session: 父会话对象（如果是子实例）
        """
        self.instance_path = Path(instance_path)
        self.sessions_dir = self.instance_path / "sessions"
        self.parent_session = parent_session

        # 确保会话目录存在
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    async def create_session(
        self,
        initial_prompt: str,
        context: Optional[dict] = None
    ) -> Session:
        """
        创建新会话

        Args:
            initial_prompt: 初始提示词
            context: 调用上下文（子实例参数）

        Returns:
            Session 对象
        """
        # 如果有父会话，创建为子会话
        if self.parent_session:
            return await self.parent_session.create_subsession(
                instance_name=self.instance_path.name,
                prompt=initial_prompt,
                context=context or {}
            )

        # 否则创建顶层会话
        session_id = generate_session_id()
        session_dir = self.sessions_dir / session_id

        metadata = {
            "session_id": session_id,
            "instance_name": self.instance_path.name,
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "status": "running",
            "parent_session_id": None,
            "parent_instance_name": None,
            "depth": 0,
            "initial_prompt": initial_prompt,
            "result_summary": None,
            "error": None,
            "context": context or {}
        }

        session = Session(
            session_id=session_id,
            session_dir=session_dir,
            metadata=metadata,
            parent_session=None
        )

        await session.start()

        return session

    def get_session(self, session_id: str) -> Session:
        """
        根据 ID 获取会话对象

        Args:
            session_id: 会话 ID

        Returns:
            Session 对象

        Raises:
            AgentSystemError: 会话不存在
        """
        session_dir = self.sessions_dir / session_id

        if not session_dir.exists():
            raise AgentSystemError(f"会话不存在: {session_id}")

        metadata_file = session_dir / "metadata.json"
        if not metadata_file.exists():
            raise AgentSystemError(f"会话元数据文件不存在: {session_id}")

        with open(metadata_file, 'r') as f:
            metadata = json.load(f)

        return Session(
            session_id=session_id,
            session_dir=session_dir,
            metadata=metadata,
            parent_session=None
        )

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

            with open(metadata_file, 'r') as f:
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

            with open(metadata_file, 'r') as f:
                metadata = json.load(f)

            # 检查是否过期
            end_time = metadata.get('end_time')
            if not end_time:
                continue

            try:
                session_time = datetime.fromisoformat(end_time)

                if session_time < cutoff_time:
                    # 计算大小
                    size = sum(
                        f.stat().st_size
                        for f in session_dir.rglob('*')
                        if f.is_file()
                    )

                    deleted_sessions.append({
                        "session_id": metadata['session_id'],
                        "end_time": end_time,
                        "size_mb": size / 1024 / 1024
                    })

                    total_size += size

                    # 删除目录
                    if not dry_run:
                        shutil.rmtree(session_dir)

                    deleted_count += 1

            except (ValueError, TypeError) as e:
                logger.warning(f"解析会话时间失败: {e}")

        logger.info(
            f"清理完成: 删除 {deleted_count} 个会话, "
            f"释放 {total_size / 1024 / 1024:.2f} MB (dry_run={dry_run})"
        )

        return {
            "deleted": deleted_count,
            "total_size_mb": total_size / 1024 / 1024,
            "sessions": deleted_sessions,
            "dry_run": dry_run
        }

    def generate_call_graph(self, session_id: str) -> dict:
        """
        生成调用关系图

        Args:
            session_id: 根会话 ID

        Returns:
            调用关系图字典
        """
        session = self.get_session(session_id)

        def build_graph_node(sess: Session) -> dict:
            """递归构建图节点"""
            metadata = sess.get_metadata()
            statistics = sess.get_statistics()

            node = {
                "session_id": sess.session_id,
                "instance_name": metadata['instance_name'],
                "depth": metadata['depth'],
                "start_time": metadata['start_time'],
                "end_time": metadata.get('end_time'),
                "duration_ms": statistics.get('total_duration_ms', 0),
                "status": metadata['status'],
                "num_turns": statistics.get('num_turns', 0),
                "children": []
            }

            # 递归处理子会话
            subsessions = sess.get_subsessions()
            for subsess in subsessions:
                node['children'].append(build_graph_node(subsess))

            return node

        graph = {
            "root_session_id": session_id,
            "generated_at": datetime.now().isoformat(),
            "graph": build_graph_node(session)
        }

        # 保存到文件
        call_graph_file = session.session_dir / "call_graph.json"
        with open(call_graph_file, 'w', encoding='utf-8') as f:
            json.dump(graph, f, indent=2, ensure_ascii=False)

        return graph
