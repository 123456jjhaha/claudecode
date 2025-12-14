"""
会话管理模块

提供会话记录、查询和管理功能，包括：
- Session: 单个会话对象
- SessionManager: 会话管理器
"""

import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional, List, Dict, Generator
from dataclasses import dataclass, asdict
import secrets

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

    表示一次 Agent 执行会话，负责收集消息、更新元数据和统计信息。
    所有消息在内存中收集，会话结束时一次性写入磁盘。
    """

    def __init__(
        self,
        session_id: str,
        session_dir: Path,
        metadata: dict,
        parent_session: Optional['Session'] = None,
        config: Optional[dict] = None
    ):
        """
        初始化会话对象

        Args:
            session_id: 会话 ID
            session_dir: 会话目录路径
            metadata: 元数据字典
            parent_session: 父会话对象（如果是子会话）
            config: 会话记录配置
        """
        self.session_id = session_id
        self.session_dir = session_dir
        self.metadata = metadata
        self.parent_session = parent_session
        self.config = config or {}

        # 内存中收集所有消息
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

        logger.info(f"会话已启动: {self.session_id}")

    async def record_message(self, message: Any) -> None:
        """
        记录单条消息到内存

        Args:
            message: Claude SDK 消息对象
        """
        # 检查消息类型过滤
        message_type = type(message).__name__
        message_types = self.config.get("message_types")
        if message_types and message_type not in message_types:
            return  # 跳过不需要记录的消息类型

        # 只追加到内存列表（使用全局计数器确保 seq 连续）
        self._messages.append({
            "seq": self._message_count,
            "timestamp": datetime.now().isoformat(),
            "message": message
        })
        self._message_count += 1

        # 更新统计信息
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

    async def finalize(self, result_message: Optional[Any] = None) -> None:
        """
        完成会话（一次性写入所有数据到磁盘）

        Args:
            result_message: ResultMessage 对象（可选）
        """
        if self._finalized:
            logger.warning(f"会话 {self.session_id} 已经完成")
            return

        self._finalized = True

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

        # 一次性写入所有消息到 messages.jsonl
        if self._messages:
            messages_file = self.session_dir / "messages.jsonl"

            # 如果文件存在，说明是 resume 模式，使用追加模式
            mode = 'a' if messages_file.exists() else 'w'

            with open(messages_file, mode, encoding='utf-8') as f:
                for msg_data in self._messages:
                    try:
                        message_dict = self._serialize_message(msg_data['message'])
                        json_line = json.dumps({
                            "seq": msg_data['seq'],
                            "timestamp": msg_data['timestamp'],
                            "message_type": type(msg_data['message']).__name__,
                            "data": message_dict
                        }, ensure_ascii=False)
                        f.write(json_line + '\n')
                    except Exception as e:
                        logger.error(f"序列化消息失败: {e}")

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

        # 清空内存中的消息，释放内存
        self._messages.clear()

        logger.info(f"会话已完成: {self.session_id} (状态={self._statistics.final_status}, 消息数={self._statistics.num_messages})")

    def _serialize_message(self, message: Any) -> dict:
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
                    "content": [self._serialize_content_block(b) for b in message.content]
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
                    content_data = [self._serialize_content_block(b) for b in content]

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
                return self._generic_serialize(message)

        except Exception as e:
            logger.error(f"消息序列化失败 ({message_type}): {e}")
            return {
                "error": str(e),
                "message_type": message_type
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

            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)

            subsessions.append(Session(
                session_id=sub_dir.name,
                session_dir=sub_dir,
                metadata=metadata,
                parent_session=self
            ))

        return subsessions


class SessionManager:
    """
    会话管理器

    负责创建和管理会话，提供会话查询和清理功能。
    """

    def __init__(
        self,
        instance_path: Path,
        parent_session: Optional[Session] = None,
        config: Optional[dict] = None
    ):
        """
        初始化会话管理器

        Args:
            instance_path: 实例目录路径
            parent_session: 父会话对象（如果是子实例）
            config: 会话记录配置
        """
        self.instance_path = Path(instance_path)
        self.sessions_dir = self.instance_path / "sessions"
        self.parent_session = parent_session

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

        # 新增：会话路径缓存（用于递归查找子会话）
        self._session_path_cache: dict[str, Path] = {}

    async def create_session(
        self,
        initial_prompt: str,
        context: Optional[dict] = None
    ) -> Session:
        """
        创建新会话

        Args:
            initial_prompt: 初始提示词
            context: 额外的上下文信息

        Returns:
            Session 对象
        """
        if not self.config.get("enabled"):
            # 会话记录未启用，返回空会话
            logger.info("会话记录未启用")
            return None

        # 生成会话 ID
        session_id = generate_session_id()

        # 确定会话目录（如果有父会话，嵌套在父会话的 subsessions/ 下）
        if self.parent_session:
            session_dir = self.parent_session.session_dir / "subsessions" / session_id
            depth = self.parent_session.metadata.get('depth', 0) + 1
        else:
            session_dir = self.sessions_dir / session_id
            depth = 0

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
            "parent_session_id": self.parent_session.session_id if self.parent_session else None,
            "context": context or {}
        }

        # 创建会话对象
        session = Session(
            session_id=session_id,
            session_dir=session_dir,
            metadata=metadata,
            parent_session=self.parent_session,
            config=self.config
        )

        # 启动会话
        await session.start()

        # 记录子会话到父会话的统计信息
        if self.parent_session:
            self.parent_session._statistics.subsessions.append({
                "session_id": session_id,
                "instance_name": self.instance_path.name
            })

        return session

    def _build_session_path_cache(self) -> None:
        """
        构建会话 ID 到路径的缓存

        递归扫描所有 sessions/ 和 subsessions/ 目录，
        将每个会话 ID 映射到其完整路径。

        这样可以快速查找任意深度的子会话。
        """
        self._session_path_cache.clear()

        def scan_directory(base_dir: Path):
            """递归扫描目录"""
            if not base_dir.exists():
                return

            for session_dir in base_dir.iterdir():
                if session_dir.is_dir():
                    # 从目录名提取 session_id
                    session_id = session_dir.name
                    self._session_path_cache[session_id] = session_dir

                    # 递归扫描 subsessions
                    subsessions_dir = session_dir / "subsessions"
                    if subsessions_dir.exists():
                        scan_directory(subsessions_dir)

        scan_directory(self.sessions_dir)
        logger.debug(f"缓存了 {len(self._session_path_cache)} 个会话路径")

    def get_session(self, session_id: str, rebuild_cache: bool = False) -> Session:
        """
        获取已存在的会话对象（用于 resume）

        支持递归查找子会话，并恢复 parent_session 引用。

        Args:
            session_id: 会话 ID
            rebuild_cache: 是否重建路径缓存

        Returns:
            Session 对象（保留完整的 parent 引用）

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

        # ✅ 关键：恢复 parent_session 引用
        parent_session = None
        parent_session_id = metadata.get('parent_session_id')

        if parent_session_id:
            # 递归加载父会话
            try:
                parent_session = self.get_session(parent_session_id)
                logger.debug(f"恢复父会话引用: {parent_session_id}")
            except Exception as e:
                logger.warning(f"无法加载父会话 {parent_session_id}: {e}")
                # 不抛出异常，允许子会话独立使用

        # 创建 Session 对象
        session = Session(
            session_id=session_id,
            session_dir=session_dir,
            metadata=metadata,
            parent_session=parent_session,  # ✅ 保留父引用
            config=self.config
        )

        # 设置状态为可追加（重要：允许 resume 时追加消息）
        session._finalized = False

        logger.info(f"加载会话: {session_id}, parent={parent_session_id}")

        return session

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

    def list_all_sessions(self, include_subsessions: bool = True) -> List[dict]:
        """
        列出所有会话（包括子会话）

        Args:
            include_subsessions: 是否包含子会话（默认 True）

        Returns:
            会话信息列表（包含 session_id, path, depth, parent_id, status, created_at）
        """
        self._build_session_path_cache()

        sessions = []
        for session_id, session_path in self._session_path_cache.items():
            metadata_file = session_path / "metadata.json"
            if metadata_file.exists():
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)

                sessions.append({
                    "session_id": session_id,
                    "path": str(session_path),
                    "depth": metadata.get('depth', 0),
                    "parent_session_id": metadata.get('parent_session_id'),
                    "status": metadata.get('status'),
                    "created_at": metadata.get('created_at')
                })

        return sorted(sessions, key=lambda x: x['created_at'], reverse=True)

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
