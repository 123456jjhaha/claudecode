"""
统一的会话查询与订阅服务

整合了：
1. 会话查询功能（从原 session_query.py）
2. 实时消息订阅功能（从 SessionSubscriber）
3. 会话树构建功能（从 SessionTreeBuilder）
"""

import asyncio
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from ...logging_config import get_logger
from ...error_handling import AgentSystemError
from ..core.session_manager import SessionManager
from ..utils.query_helpers import (
    calculate_session_statistics,
    search_sessions_in_list,
    export_session_to_text,
    export_session_to_jsonl,
    build_tree_node,
    flatten_tree_to_list
)

if TYPE_CHECKING:
    from ..streaming.message_bus import MessageBus

logger = get_logger(__name__)


class SessionQuery:
    """
    统一的会话查询与订阅服务

    职责：
    1. 会话查询（基础+高级）
    2. 实时消息订阅
    3. 会话树构建
    4. 会话导出与统计
    """

    def __init__(
        self,
        instance_name: str,
        instances_root: Optional[Path] = None,
        message_bus: Optional["MessageBus"] = None
    ):
        """
        初始化会话查询服务

        Args:
            instance_name: 实例名称
            instances_root: 实例根目录
            message_bus: 消息总线（用于订阅功能）
        """
        from ..utils import get_instance_path

        self.instance_name = instance_name
        self.instances_root = instances_root
        self.instance_path = get_instance_path(instance_name, instances_root)

        # 核心组件
        self.session_manager = SessionManager(self.instance_path)
        self.message_bus = message_bus

        # 订阅相关状态
        self.child_sessions: Dict[str, str] = {}
        self.subscription_tasks: List[asyncio.Task] = []
        self._running = False
        self._stopped = False

        # 回调函数
        self.on_parent_message: Optional[Callable[[Any], None]] = None
        self.on_child_message: Optional[Callable[[str, str, Any], None]] = None
        self.on_child_started: Optional[Callable[[str, str], None]] = None

    # === 基础查询功能 ===

    def get_session_details(
        self,
        session_id: str,
        include_messages: bool = False,
        message_limit: Optional[int] = 100
    ) -> Dict[str, Any]:
        """
        获取会话详情

        Args:
            session_id: 会话 ID
            include_messages: 是否包含消息内容
            message_limit: 消息数量限制

        Returns:
            会话详情字典
        """
        try:
            session = self.session_manager.get_session(session_id)

            # 读取元数据
            metadata = session.get_metadata()

            # 读取统计信息
            statistics_file = session.session_dir / "statistics.json"
            if statistics_file.exists():
                with open(statistics_file, 'r', encoding='utf-8') as f:
                    statistics = json.load(f)
            else:
                statistics = session.get_statistics()

            # 读取消息
            messages = []
            if include_messages:
                messages = list(session.get_messages(limit=message_limit))

            # 获取子会话信息（从 statistics.json 中读取）
            subsessions = []
            if 'subsessions' in statistics and statistics['subsessions']:
                for subsess_info in statistics['subsessions']:
                    subsessions.append({
                        "session_id": subsess_info.get('session_id'),
                        "tool_name": subsess_info.get('tool_name'),
                        "tool_use_id": subsess_info.get('tool_use_id'),
                        "timestamp": subsess_info.get('timestamp')
                    })

            return {
                "metadata": metadata,
                "statistics": statistics,
                "messages": messages,
                "subsessions": subsessions
            }

        except Exception as e:
            raise AgentSystemError(f"获取会话详情失败: {e}")

    def list_sessions(
        self,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        列出会话（代理到 SessionManager）

        Args:
            status: 状态过滤（running/completed/failed）
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            会话元数据列表
        """
        return self.session_manager.list_sessions(
            status=status,
            limit=limit,
            offset=offset
        )

    def get_session_messages(
        self,
        session_id: str,
        message_types: Optional[List[str]] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        获取会话消息

        Args:
            session_id: 会话 ID
            message_types: 过滤消息类型
            limit: 限制返回数量

        Returns:
            消息列表
        """
        try:
            session = self.session_manager.get_session(session_id)
            return list(session.get_messages(
                message_types=message_types,
                limit=limit
            ))
        except Exception as e:
            raise AgentSystemError(f"获取会话消息失败: {e}")

    # === 高级查询功能 ===

    def search_sessions(
        self,
        query: str,
        field: str = "initial_prompt",
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        搜索会话

        Args:
            query: 搜索关键词
            field: 搜索字段（initial_prompt/result）
            limit: 返回数量限制

        Returns:
            匹配的会话元数据列表
        """
        try:
            # 获取所有会话
            all_sessions = self.session_manager.list_sessions(limit=1000)

            # 搜索匹配
            return search_sessions_in_list(all_sessions, query, field, limit)
        except Exception as e:
            raise AgentSystemError(f"搜索会话失败: {e}")

    def get_statistics_summary(self, recent_days: Optional[int] = None) -> Dict[str, Any]:
        """
        获取会话统计摘要

        Args:
            recent_days: 只统计最近N天的会话（可选）

        Returns:
            统计摘要字典
        """
        try:
            # 获取所有会话
            all_sessions = self.session_manager.list_sessions(limit=10000)

            # 计算统计信息
            return calculate_session_statistics(all_sessions, self.session_manager, recent_days)
        except Exception as e:
            raise AgentSystemError(f"获取统计摘要失败: {e}")

    def export_session(
        self,
        session_id: str,
        output_file: Path,
        format: str = "json",
        include_messages: bool = True
    ) -> None:
        """
        导出会话到文件

        Args:
            session_id: 会话 ID
            output_file: 输出文件路径
            format: 输出格式（json/jsonl/text）
            include_messages: 是否包含消息
        """
        try:
            # 获取会话数据
            data = self.get_session_details(
                session_id=session_id,
                include_messages=include_messages
            )

            # 写入文件
            if format == "json":
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

            elif format == "jsonl":
                export_session_to_jsonl(output_file, data, include_messages)

            elif format == "text":
                export_session_to_text(output_file, session_id, data)

            logger.info(f"已导出会话到: {output_file}")

        except Exception as e:
            raise AgentSystemError(f"导出会话失败: {e}")

    # === 管理功能 ===

    def cleanup_sessions(
        self,
        retention_days: int = 30,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        清理过期会话（代理到 SessionManager）

        Args:
            retention_days: 保留天数
            dry_run: 是否模拟运行（不实际删除）

        Returns:
            清理报告
        """
        return self.session_manager.cleanup_old_sessions(retention_days, dry_run)

    # === 订阅功能 ===

    async def subscribe(
        self,
        session_id: str,
        on_parent_message: Optional[Callable[[Any], None]] = None,
        on_child_message: Optional[Callable[[str, str, Any], None]] = None,
        on_child_started: Optional[Callable[[str, str], None]] = None,
        auto_start: bool = True
    ) -> None:
        """
        开始订阅会话消息

        Args:
            session_id: 要订阅的会话 ID
            on_parent_message: 父实例消息回调
            on_child_message: 子实例消息回调
            on_child_started: 子实例启动回调
            auto_start: 是否自动启动订阅任务
        """
        if not self.message_bus:
            raise AgentSystemError("未配置 MessageBus，无法使用订阅功能")

        if self._running:
            logger.warning("订阅器已在运行")
            return

        self.session_id = session_id
        self.on_parent_message = on_parent_message
        self.on_child_message = on_child_message
        self.on_child_started = on_child_started

        if auto_start:
            await self.start()

    async def start(self) -> None:
        """启动订阅任务"""
        if not self.message_bus:
            raise AgentSystemError("未配置 MessageBus，无法启动订阅")

        if self._running:
            return

        self._running = True
        self._stopped = False

        logger.info(f"[SessionQuery] 开始订阅 session: {self.session_id}")

        # 启动父会话订阅任务
        parent_task = asyncio.create_task(self._subscribe_parent())
        self.subscription_tasks.append(parent_task)

    async def stop(self) -> None:
        """停止所有订阅任务"""
        if self._stopped:
            return

        logger.info(f"[SessionQuery] 停止订阅 session: {self.session_id}")

        self._running = False
        self._stopped = True

        # 取消所有订阅任务
        for task in self.subscription_tasks:
            if not task.done():
                task.cancel()

        # 等待所有任务完成
        if self.subscription_tasks:
            await asyncio.gather(*self.subscription_tasks, return_exceptions=True)

        self.subscription_tasks.clear()
        logger.info(f"[SessionQuery] 已停止所有订阅")

    async def wait(self) -> None:
        """等待所有订阅任务完成"""
        if self.subscription_tasks:
            await asyncio.gather(*self.subscription_tasks, return_exceptions=True)

    def get_child_sessions(self) -> Dict[str, str]:
        """获取所有子会话"""
        return self.child_sessions.copy()

    def is_running(self) -> bool:
        """检查订阅器是否正在运行"""
        return self._running

    # === 会话树功能 ===

    async def build_session_tree(
        self,
        session_id: str,
        instance_name: Optional[str] = None,
        include_messages: bool = True,
        max_depth: int = 10
    ) -> Dict[str, Any]:
        """
        递归构建会话树

        Args:
            session_id: 会话 ID
            instance_name: 实例名称（可选，如果不提供则自动推断）
            include_messages: 是否包含消息内容
            max_depth: 最大递归深度

        Returns:
            会话树字典
        """
        from ..utils import infer_instance_name, extract_instance_from_tool_name

        # 推断实例名称（如果未提供）
        if instance_name is None:
            instance_name = infer_instance_name(session_id, self.instances_root)

        if instance_name is None:
            raise ValueError(f"无法推断会话 {session_id} 的实例名称，请手动指定")

        # 1. 获取会话详情
        details = self.get_session_details(
            session_id=session_id,
            include_messages=include_messages
        )

        # 2. 构建当前节点
        tree_node = build_tree_node(session_id, instance_name, details, include_messages)

        # 3. 递归构建子会话树
        if max_depth > 0 and details.get("subsessions"):
            for subsess_info in details["subsessions"]:
                child_session_id = subsess_info.get('session_id')
                if not child_session_id:
                    continue

                # 从工具名称推断子实例名称
                tool_name = subsess_info.get('tool_name', "")
                child_instance_name = extract_instance_from_tool_name(tool_name, self.instances_root)

                if child_instance_name:
                    try:
                        child_tree = await self.build_session_tree(
                            session_id=child_session_id,
                            instance_name=child_instance_name,
                            include_messages=include_messages,
                            max_depth=max_depth - 1
                        )
                        tree_node["subsessions"].append(child_tree)
                    except Exception as e:
                        logger.warning(f"构建子会话树失败 {child_session_id}: {e}")
                        # 添加错误节点
                        tree_node["subsessions"].append({
                            "session_id": child_session_id,
                            "instance_name": child_instance_name,
                            "error": str(e)
                        })
                else:
                    logger.warning(f"无法从工具名称 {tool_name} 推断实例名称")

        return tree_node

    def flatten_tree(self, tree: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        将树形结构展平为列表

        Args:
            tree: 会话树

        Returns:
            会话列表（按深度优先顺序）
        """
        return flatten_tree_to_list(tree)

    # === 内部订阅方法 ===

    async def _subscribe_parent(self) -> None:
        """订阅父会话消息（内部方法）"""
        channel = f"session:{self.session_id}"
        logger.info(f"[SessionQuery] 订阅父频道: {channel}")

        try:
            async for message in self.message_bus.subscribe(channel):
                if self._stopped:
                    break

                # 检查是否是子实例启动通知
                if isinstance(message, dict) and message.get("type") == "sub_instance_started":
                    logger.info(f"[SessionQuery] 检测到子实例启动通知: {message}")
                    await self._handle_child_started(message)
                else:
                    # 普通消息，调用父实例消息回调
                    logger.debug(f"[SessionQuery] 收到父会话消息: {type(message)} - {str(message)[:100]}")
                    if self.on_parent_message:
                        try:
                            if asyncio.iscoroutinefunction(self.on_parent_message):
                                await self.on_parent_message(message)
                            else:
                                self.on_parent_message(message)
                        except Exception as e:
                            logger.error(f"[SessionQuery] 父消息回调错误: {e}", exc_info=True)

        except asyncio.CancelledError:
            logger.info(f"[SessionQuery] 父会话订阅已取消: {self.session_id}")
        except Exception as e:
            logger.error(f"[SessionQuery] 父会话订阅错误: {e}", exc_info=True)

    async def _handle_child_started(self, notification: Dict[str, Any]) -> None:
        """处理子实例启动通知（内部方法）"""
        child_session_id = notification.get("child_session_id")
        child_instance_name = notification.get("child_instance_name")

        if not child_session_id:
            logger.warning(f"[SessionQuery] 子实例启动通知缺少 child_session_id")
            return

        logger.info(
            f"[SessionQuery] 🔔 子实例启动: {child_session_id} ({child_instance_name})"
        )

        # 记录子会话
        self.child_sessions[child_session_id] = child_instance_name

        # 调用子实例启动回调
        if self.on_child_started:
            try:
                if asyncio.iscoroutinefunction(self.on_child_started):
                    await self.on_child_started(child_session_id, child_instance_name)
                else:
                    self.on_child_started(child_session_id, child_instance_name)
            except Exception as e:
                logger.error(f"[SessionQuery] 子实例启动回调错误: {e}", exc_info=True)

        # 自动订阅子会话
        if self.on_child_message:
            task = asyncio.create_task(
                self._subscribe_child(child_session_id, child_instance_name)
            )
            self.subscription_tasks.append(task)

    async def _subscribe_child(self, child_session_id: str, instance_name: str) -> None:
        """订阅子会话消息（内部方法）"""
        channel = f"session:{child_session_id}"
        logger.info(f"[SessionQuery] 订阅子频道: {channel} ({instance_name})")

        try:
            async for message in self.message_bus.subscribe(channel):
                if self._stopped:
                    break

                # 记录收到的子会话消息
                logger.debug(f"[SessionQuery] 收到子会话消息 ({instance_name}): {type(message)} - {str(message)[:100]}")

                # 调用子实例消息回调
                if self.on_child_message:
                    try:
                        if asyncio.iscoroutinefunction(self.on_child_message):
                            await self.on_child_message(child_session_id, instance_name, message)
                        else:
                            self.on_child_message(child_session_id, instance_name, message)
                    except Exception as e:
                        logger.error(
                            f"[SessionQuery] 子消息回调错误 ({instance_name}): {e}",
                            exc_info=True
                        )

        except asyncio.CancelledError:
            logger.info(f"[SessionQuery] 子会话订阅已取消: {child_session_id} ({instance_name})")
        except Exception as e:
            logger.error(
                f"[SessionQuery] 子会话订阅错误 ({instance_name}): {e}",
                exc_info=True
            )

    def __repr__(self) -> str:
        return (
            f"SessionQuery(instance='{self.instance_name}', "
            f"child_count={len(self.child_sessions)}, "
            f"running={self._running})"
        )


# === 向后兼容的函数别名 ===

def get_session_details(*args, **kwargs) -> Dict[str, Any]:
    """向后兼容的函数别名"""
    # 从参数中提取 instance_name 和 session_id
    if len(args) >= 2:
        instance_name = args[0]
        session_id = args[1]
    else:
        instance_name = kwargs.get('instance_name')
        session_id = kwargs.get('session_id')

    query = SessionQuery(instance_name, kwargs.get('instances_root'))
    return query.get_session_details(session_id, kwargs.get('include_messages', False), kwargs.get('message_limit', 100))


def list_sessions(*args, **kwargs) -> List[Dict[str, Any]]:
    """向后兼容的函数别名"""
    instance_name = args[0] if args else kwargs.get('instance_name')
    query = SessionQuery(instance_name, kwargs.get('instances_root'))
    return query.list_sessions(kwargs.get('status'), kwargs.get('limit', 100), kwargs.get('offset', 0))


def search_sessions(*args, **kwargs) -> List[Dict[str, Any]]:
    """向后兼容的函数别名"""
    instance_name = args[0] if args else kwargs.get('instance_name')
    query = SessionQuery(instance_name, kwargs.get('instances_root'))
    return query.search_sessions(args[1] if len(args) > 1 else kwargs.get('query'), kwargs.get('field', 'initial_prompt'), kwargs.get('limit', 10))


def get_session_statistics_summary(*args, **kwargs) -> Dict[str, Any]:
    """向后兼容的函数别名"""
    instance_name = args[0] if args else kwargs.get('instance_name')
    query = SessionQuery(instance_name, kwargs.get('instances_root'))
    return query.get_statistics_summary(kwargs.get('recent_days'))


def export_session(*args, **kwargs) -> None:
    """向后兼容的函数别名"""
    instance_name = args[0] if args else kwargs.get('instance_name')
    session_id = args[1] if len(args) > 1 else kwargs.get('session_id')
    output_file = args[2] if len(args) > 2 else kwargs.get('output_file')

    query = SessionQuery(instance_name, kwargs.get('instances_root'))
    return query.export_session(
        session_id,
        output_file,
        kwargs.get('format', 'json'),
        kwargs.get('include_messages', True)
    )


def cleanup_sessions(*args, **kwargs) -> Dict[str, Any]:
    """向后兼容的函数别名"""
    instance_name = args[0] if args else kwargs.get('instance_name')
    query = SessionQuery(instance_name, kwargs.get('instances_root'))
    return query.cleanup_sessions(kwargs.get('retention_days', 30), kwargs.get('dry_run', False))


def get_session_messages(*args, **kwargs) -> List[Dict[str, Any]]:
    """向后兼容的函数别名"""
    instance_name = args[0] if args else kwargs.get('instance_name')
    session_id = args[1] if len(args) > 1 else kwargs.get('session_id')

    query = SessionQuery(instance_name, kwargs.get('instances_root'))
    return query.get_session_messages(session_id, kwargs.get('message_types'), kwargs.get('limit'))


# === 简化别名（保持兼容性） ===
get_details = get_session_details
list_all = list_sessions
search = search_sessions
get_stats = get_session_statistics_summary
export = export_session
cleanup = cleanup_sessions
get_messages = get_session_messages