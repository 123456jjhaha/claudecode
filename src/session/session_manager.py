"""
会话管理模块 - 精简重构版

提供会话记录、查询和管理功能，包括：
- Session: 单个会话对象
- SessionManager: 会话管理器
"""

import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional, List, Dict, Generator
from dataclasses import asdict

from ..logging_config import get_logger
from ..error_handling import AgentSystemError
from .session_utils import generate_session_id, Statistics
from .session_serializer import MessageSerializer

logger = get_logger(__name__)


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
        config: Optional[dict] = None
    ):
        """
        初始化会话对象

        Args:
            session_id: 会话 ID
            session_dir: 会话目录路径
            metadata: 元数据字典
            config: 会话记录配置
        """
        self.session_id = session_id
        self.session_dir = session_dir
        self.metadata = metadata
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

        # ✅ 检测子实例工具调用并记录 session_id
        if message_type == "AssistantMessage":
            self._detect_and_record_subsession(message)

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


class SessionManager:
    """
    会话管理器

    负责创建和管理会话，提供会话查询和清理功能。
    """

    def __init__(
        self,
        instance_path: Path,
        config: Optional[dict] = None
    ):
        """
        初始化会话管理器

        Args:
            instance_path: 实例目录路径
            config: 会话记录配置
        """
        self.instance_path = Path(instance_path)
        self.sessions_dir = self.instance_path / "sessions"

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

        # 会话路径缓存（用于快速查找）
        self._session_path_cache: dict[str, Path] = {}

    async def create_session(
        self,
        initial_prompt: str,
        context: Optional[dict] = None,
        parent_session_id: Optional[str] = None
    ) -> Session:
        """
        创建新会话

        Args:
            initial_prompt: 初始提示词
            context: 额外的上下文信息
            parent_session_id: 父会话 ID（用于追踪调用链）
                **重要**：对于子实例调用，必须传递此参数以建立父子关系

        Returns:
            Session 对象
        """
        if not self.config.get("enabled"):
            # 会话记录未启用，返回空会话
            logger.info("会话记录未启用")
            return None

        # 生成会话 ID
        session_id = generate_session_id()

        # 会话目录（总是在当前实例的 sessions/ 目录下）
        session_dir = self.sessions_dir / session_id

        # 计算深度（如果有父会话 ID）
        depth = 0
        if parent_session_id:
            # TODO: 未来可以从数据库或缓存中查询父会话的 depth 并递增
            depth = 1  # 简化处理，子会话深度为 1

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
            "parent_session_id": parent_session_id,  # 直接使用传入的 parent_session_id
            "context": context or {}
        }

        # 创建会话对象
        session = Session(
            session_id=session_id,
            session_dir=session_dir,
            metadata=metadata,
            config=self.config
        )

        # 启动会话
        await session.start()

        return session

    def _build_session_path_cache(self) -> None:
        """
        构建会话 ID 到路径的缓存

        只扫描当前实例的 sessions/ 目录，不再递归扫描 subsessions。
        """
        self._session_path_cache.clear()

        if not self.sessions_dir.exists():
            return

        for session_dir in self.sessions_dir.iterdir():
            if session_dir.is_dir():
                # 从目录名提取 session_id
                session_id = session_dir.name
                self._session_path_cache[session_id] = session_dir

        logger.debug(f"缓存了 {len(self._session_path_cache)} 个会话路径")

    def get_session(self, session_id: str, rebuild_cache: bool = False) -> Session:
        """
        获取已存在的会话对象（用于 resume）

        Args:
            session_id: 会话 ID
            rebuild_cache: 是否重建路径缓存

        Returns:
            Session 对象

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

        # 创建 Session 对象
        session = Session(
            session_id=session_id,
            session_dir=session_dir,
            metadata=metadata,
            config=self.config
        )

        # 设置状态为可追加（重要：允许 resume 时追加消息）
        session._finalized = False

        logger.info(f"加载会话: {session_id}")

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
