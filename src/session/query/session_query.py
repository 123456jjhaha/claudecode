"""
会话查询 API 模块 - 精简版

提供核心的会话查询功能：
- 查询会话详情
- 列出会话
- 搜索会话
- 统计摘要
- 导出会话
- 实时订阅消息（新增）
"""

import json
from pathlib import Path
from typing import Optional, List, Dict, Any, AsyncIterator
from datetime import datetime

from ..core.session_manager import SessionManager
from ...error_handling import AgentSystemError
from ...logging_config import get_logger

# 新增：导入 MessageBus 类型
try:
    from ..streaming.message_bus import MessageBus
except ImportError:
    MessageBus = None

logger = get_logger(__name__)


def _get_instance_path(
    instance_name: str,
    instances_root: Optional[Path] = None
) -> Path:
    """
    获取实例目录路径

    Args:
        instance_name: 实例名称
        instances_root: 实例根目录（默认为当前目录下的 instances/）

    Returns:
        实例目录路径

    Raises:
        AgentSystemError: 实例目录不存在
    """
    if instances_root is None:
        instances_root = Path.cwd() / "instances"

    instance_path = Path(instances_root) / instance_name

    if not instance_path.exists():
        raise AgentSystemError(f"实例目录不存在: {instance_path}")

    return instance_path


def get_session_details(
    instance_name: str,
    session_id: str,
    instances_root: Optional[Path] = None,
    include_messages: bool = False,
    message_limit: Optional[int] = 100
) -> Dict[str, Any]:
    """
    获取会话详情

    Args:
        instance_name: 实例名称
        session_id: 会话 ID
        instances_root: 实例根目录
        include_messages: 是否包含消息内容
        message_limit: 消息数量限制

    Returns:
        会话详情字典，包含：
        - metadata: 会话元数据
        - statistics: 统计信息
        - messages: 消息列表（如果 include_messages=True）
        - subsessions: 子会话列表（从 statistics.subsessions 读取）

    Raises:
        AgentSystemError: 查询失败
    """
    try:
        instance_path = _get_instance_path(instance_name, instances_root)
        session_manager = SessionManager(instance_path)

        # 获取会话对象
        session = session_manager.get_session(session_id)

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
    instance_name: str,
    instances_root: Optional[Path] = None,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    列出会话

    Args:
        instance_name: 实例名称
        instances_root: 实例根目录
        status: 状态过滤（running/completed/failed）
        limit: 返回数量限制
        offset: 偏移量

    Returns:
        会话元数据列表

    Raises:
        AgentSystemError: 查询失败
    """
    try:
        instance_path = _get_instance_path(instance_name, instances_root)
        session_manager = SessionManager(instance_path)

        return session_manager.list_sessions(
            status=status,
            limit=limit,
            offset=offset
        )

    except Exception as e:
        raise AgentSystemError(f"列出会话失败: {e}")


def search_sessions(
    instance_name: str,
    query: str,
    instances_root: Optional[Path] = None,
    field: str = "initial_prompt",
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    搜索会话

    Args:
        instance_name: 实例名称
        query: 搜索关键词
        instances_root: 实例根目录
        field: 搜索字段（initial_prompt/result）
        limit: 返回数量限制

    Returns:
        匹配的会话元数据列表

    Raises:
        AgentSystemError: 搜索失败
    """
    try:
        instance_path = _get_instance_path(instance_name, instances_root)
        session_manager = SessionManager(instance_path)

        # 获取所有会话
        all_sessions = session_manager.list_sessions(limit=1000)

        # 搜索匹配
        matched_sessions = []

        for session_meta in all_sessions:
            match_found = False

            if field == "initial_prompt":
                # 搜索初始提示词
                if 'prompts' in session_meta and session_meta['prompts']:
                    first_prompt = session_meta['prompts'][0].get('prompt', '')
                    if query.lower() in first_prompt.lower():
                        match_found = True

            elif field == "result":
                # 搜索结果
                if 'results' in session_meta and session_meta['results']:
                    for result in session_meta['results']:
                        if query.lower() in result.get('result', '').lower():
                            match_found = True
                            break

            if match_found:
                matched_sessions.append(session_meta)

            if len(matched_sessions) >= limit:
                break

        return matched_sessions

    except Exception as e:
        raise AgentSystemError(f"搜索会话失败: {e}")


def get_session_statistics_summary(
    instance_name: str,
    instances_root: Optional[Path] = None,
    recent_days: Optional[int] = None
) -> Dict[str, Any]:
    """
    获取会话统计摘要

    Args:
        instance_name: 实例名称
        instances_root: 实例根目录
        recent_days: 只统计最近N天的会话（可选）

    Returns:
        统计摘要字典，包含：
        - total_sessions: 总会话数
        - completed_sessions: 完成的会话数
        - failed_sessions: 失败的会话数
        - total_messages: 总消息数
        - total_tool_calls: 总工具调用数
        - total_cost_usd: 总成本
        - avg_duration_ms: 平均耗时

    Raises:
        AgentSystemError: 查询失败
    """
    try:
        instance_path = _get_instance_path(instance_name, instances_root)
        session_manager = SessionManager(instance_path)

        # 获取所有会话
        all_sessions = session_manager.list_sessions(limit=10000)

        # 过滤时间范围
        if recent_days:
            cutoff_time = datetime.now().timestamp() - (recent_days * 24 * 60 * 60)
            filtered_sessions = []
            for session_meta in all_sessions:
                start_time_str = session_meta.get('start_time')
                if start_time_str:
                    start_time = datetime.fromisoformat(start_time_str).timestamp()
                    if start_time >= cutoff_time:
                        filtered_sessions.append(session_meta)
            all_sessions = filtered_sessions

        # 统计
        total_sessions = len(all_sessions)
        completed_sessions = 0
        failed_sessions = 0
        total_messages = 0
        total_tool_calls = 0
        total_cost_usd = 0.0
        total_duration_ms = 0
        duration_count = 0

        for session_meta in all_sessions:
            status = session_meta.get('status', 'unknown')
            if status == 'completed':
                completed_sessions += 1
            elif status == 'failed':
                failed_sessions += 1

            # 读取统计信息
            session_id = session_meta.get('session_id')
            try:
                session = session_manager.get_session(session_id)
                stats_file = session.session_dir / "statistics.json"
                if stats_file.exists():
                    with open(stats_file, 'r', encoding='utf-8') as f:
                        stats = json.load(f)

                    total_messages += stats.get('num_messages', 0)
                    total_tool_calls += stats.get('num_tool_calls', 0)
                    total_cost_usd += stats.get('cost_usd', 0) or 0

                    duration = stats.get('total_duration_ms', 0)
                    if duration > 0:
                        total_duration_ms += duration
                        duration_count += 1
            except Exception as e:
                logger.warning(f"读取会话统计失败 {session_id}: {e}")

        avg_duration_ms = total_duration_ms / duration_count if duration_count > 0 else 0

        return {
            "total_sessions": total_sessions,
            "completed_sessions": completed_sessions,
            "failed_sessions": failed_sessions,
            "running_sessions": total_sessions - completed_sessions - failed_sessions,
            "total_messages": total_messages,
            "total_tool_calls": total_tool_calls,
            "total_cost_usd": round(total_cost_usd, 4),
            "avg_duration_ms": round(avg_duration_ms, 2),
            "recent_days": recent_days
        }

    except Exception as e:
        raise AgentSystemError(f"获取统计摘要失败: {e}")


def export_session(
    instance_name: str,
    session_id: str,
    output_file: Path,
    instances_root: Optional[Path] = None,
    format: str = "json",
    include_messages: bool = True
) -> None:
    """
    导出会话到文件

    Args:
        instance_name: 实例名称
        session_id: 会话 ID
        output_file: 输出文件路径
        instances_root: 实例根目录
        format: 输出格式（json/jsonl/text）
        include_messages: 是否包含消息

    Raises:
        AgentSystemError: 导出失败
    """
    try:
        instance_path = _get_instance_path(instance_name, instances_root)
        session_manager = SessionManager(instance_path)

        session = session_manager.get_session(session_id)

        # 收集数据
        data = {
            "metadata": session.get_metadata(),
            "statistics": session.get_statistics()
        }

        if include_messages:
            data["messages"] = list(session.get_messages())

        # 写入文件
        if format == "json":
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        elif format == "jsonl":
            with open(output_file, 'w', encoding='utf-8') as f:
                # 写入元数据
                json.dump({"type": "metadata", "data": data["metadata"]}, f, ensure_ascii=False)
                f.write('\n')
                # 写入统计信息
                json.dump({"type": "statistics", "data": data["statistics"]}, f, ensure_ascii=False)
                f.write('\n')
                # 写入消息
                if include_messages:
                    for msg in data["messages"]:
                        json.dump({"type": "message", "data": msg}, f, ensure_ascii=False)
                        f.write('\n')

        elif format == "text":
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"=== Session: {session_id} ===\n\n")
                f.write(f"Instance: {data['metadata']['instance_name']}\n")
                f.write(f"Status: {data['metadata']['status']}\n")
                f.write(f"Start Time: {data['metadata']['start_time']}\n")
                f.write(f"End Time: {data['metadata'].get('end_time', 'N/A')}\n")
                f.write(f"\n=== Statistics ===\n")
                f.write(f"Messages: {data['statistics']['num_messages']}\n")
                f.write(f"Tool Calls: {data['statistics']['num_tool_calls']}\n")
                f.write(f"Duration: {data['statistics']['total_duration_ms']}ms\n")
                f.write(f"Cost: ${data['statistics'].get('cost_usd', 0)}\n")

                if include_messages:
                    f.write(f"\n=== Messages ===\n")
                    for msg in data["messages"]:
                        f.write(f"\n[{msg['seq']}] {msg['message_type']} @ {msg['timestamp']}\n")

        logger.info(f"已导出会话到: {output_file}")

    except Exception as e:
        raise AgentSystemError(f"导出会话失败: {e}")


def cleanup_sessions(
    instance_name: str,
    instances_root: Optional[Path] = None,
    retention_days: int = 30,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    清理过期会话

    Args:
        instance_name: 实例名称
        instances_root: 实例根目录
        retention_days: 保留天数
        dry_run: 是否模拟运行（不实际删除）

    Returns:
        清理报告

    Raises:
        AgentSystemError: 清理失败
    """
    try:
        instance_path = _get_instance_path(instance_name, instances_root)
        session_manager = SessionManager(instance_path)

        return session_manager.cleanup_old_sessions(
            retention_days=retention_days,
            dry_run=dry_run
        )

    except Exception as e:
        raise AgentSystemError(f"清理会话失败: {e}")


def get_session_messages(
    instance_name: str,
    session_id: str,
    instances_root: Optional[Path] = None,
    message_types: Optional[List[str]] = None,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    获取会话消息

    Args:
        instance_name: 实例名称
        session_id: 会话 ID
        instances_root: 实例根目录
        message_types: 过滤消息类型
        limit: 限制返回数量

    Returns:
        消息列表

    Raises:
        AgentSystemError: 查询失败
    """
    try:
        instance_path = _get_instance_path(instance_name, instances_root)
        session_manager = SessionManager(instance_path)

        session = session_manager.get_session(session_id)

        return list(session.get_messages(
            message_types=message_types,
            limit=limit
        ))

    except Exception as e:
        raise AgentSystemError(f"获取会话消息失败: {e}")


# =====================================================
# 实时订阅 API（新增）
# =====================================================

async def subscribe_session_messages(
    session_id: str,
    message_bus: "MessageBus"
) -> AsyncIterator[Dict[str, Any]]:
    """
    订阅特定会话的实时消息流

    Args:
        session_id: 会话 ID
        message_bus: MessageBus 实例

    Yields:
        消息事件字典，格式：
        {
            "event_type": "message_created",
            "timestamp": "2025-12-16T10:30:00",
            "instance_name": "demo_agent",
            "session_id": "xxx",
            "parent_session_id": "yyy",
            "depth": 0,
            "seq": 42,
            "message_type": "AssistantMessage",
            "data": {...}
        }

    Raises:
        AgentSystemError: MessageBus 未连接
    """
    if not message_bus or not message_bus.is_connected:
        raise AgentSystemError("MessageBus 未连接，无法订阅实时消息")

    channel = f"messages:session:{session_id}"
    logger.info(f"订阅会话消息: {session_id}")

    try:
        async for event in message_bus.subscribe(channel):
            yield event
    except Exception as e:
        logger.error(f"订阅会话消息失败: {e}")
        raise AgentSystemError(f"订阅会话消息失败: {e}")


async def subscribe_instance_messages(
    instance_name: str,
    message_bus: "MessageBus"
) -> AsyncIterator[Dict[str, Any]]:
    """
    订阅特定实例的所有实时消息

    Args:
        instance_name: 实例名称
        message_bus: MessageBus 实例

    Yields:
        消息事件字典（格式同 subscribe_session_messages）

    Raises:
        AgentSystemError: MessageBus 未连接
    """
    if not message_bus or not message_bus.is_connected:
        raise AgentSystemError("MessageBus 未连接，无法订阅实时消息")

    channel = f"messages:instance:{instance_name}"
    logger.info(f"订阅实例消息: {instance_name}")

    try:
        async for event in message_bus.subscribe(channel):
            yield event
    except Exception as e:
        logger.error(f"订阅实例消息失败: {e}")
        raise AgentSystemError(f"订阅实例消息失败: {e}")


# 简化别名
get_details = get_session_details
list_all = list_sessions
search = search_sessions
get_stats = get_session_statistics_summary
export = export_session
cleanup = cleanup_sessions
get_messages = get_session_messages
