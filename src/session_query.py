"""
会话查询 API 模块

提供便捷的会话查询函数，支持：
- 查询会话详情
- 列出会话
- 搜索会话
- 生成调用关系图
- 统计摘要
- 导出会话
"""

import json
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from datetime import datetime

from .session_manager import SessionManager
from .error_handling import AgentSystemError
from .logging_config import get_logger

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
    include_messages: bool = True,
    message_limit: Optional[int] = None
) -> Dict[str, Any]:
    """
    获取会话完整详情

    Args:
        instance_name: 实例名称
        session_id: 会话 ID
        instances_root: 实例根目录
        include_messages: 是否包含消息列表
        message_limit: 消息数量限制

    Returns:
        会话详情字典，包含：
        - metadata: 元数据
        - statistics: 统计信息
        - messages: 消息列表（可选）
        - subsessions: 子会话列表

    Raises:
        AgentSystemError: 会话不存在或读取失败
    """
    instance_path = _get_instance_path(instance_name, instances_root)
    session_manager = SessionManager(instance_path)

    try:
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

        # 获取子会话信息
        subsessions = []
        for subsess in session.get_subsessions():
            subsessions.append({
                "session_id": subsess.session_id,
                "instance_name": subsess.metadata['instance_name'],
                "status": subsess.metadata['status'],
                "start_time": subsess.metadata['start_time'],
                "end_time": subsess.metadata.get('end_time')
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
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    instances_root: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """
    列出会话（支持过滤和分页）

    Args:
        instance_name: 实例名称
        status: 过滤状态（可选）："running", "completed", "failed"
        limit: 限制返回数量
        offset: 偏移量
        instances_root: 实例根目录

    Returns:
        会话元数据列表

    Raises:
        AgentSystemError: 实例不存在
    """
    instance_path = _get_instance_path(instance_name, instances_root)
    session_manager = SessionManager(instance_path)

    return session_manager.list_sessions(status=status, limit=limit, offset=offset)


def search_sessions(
    instance_name: str,
    query: str,
    field: str = "prompts",
    instances_root: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """
    搜索会话（按字段内容）

    Args:
        instance_name: 实例名称
        query: 搜索关键词
        field: 搜索字段（"prompts", "results", "error"）
        instances_root: 实例根目录

    Returns:
        匹配的会话元数据列表

    Raises:
        AgentSystemError: 实例不存在
    """
    all_sessions = list_sessions(instance_name, instances_root=instances_root, limit=1000)

    matched_sessions = []
    for session in all_sessions:
        # 处理新的数组格式
        if field == "prompts":
            field_value = session.get("prompts", [])
            # 在所有提示词中搜索
            found = any(
                query.lower() in prompt_item.get("prompt", "").lower()
                for prompt_item in field_value
            )
        elif field == "results":
            field_value = session.get("results", [])
            # 在所有结果中搜索
            found = any(
                query.lower() in result_item.get("result", "").lower()
                for result_item in field_value
            )
        else:
            # 其他字段（如 error）
            field_value = session.get(field)
            found = field_value and query.lower() in str(field_value).lower()

        if found:
            matched_sessions.append(session)

    return matched_sessions




def get_session_statistics_summary(
    instance_name: str,
    session_ids: Optional[List[str]] = None,
    instances_root: Optional[Path] = None,
    time_range: Optional[tuple[datetime, datetime]] = None
) -> Dict[str, Any]:
    """
    获取多个会话的统计摘要

    Args:
        instance_name: 实例名称
        session_ids: 会话 ID 列表（可选，为空则统计所有会话）
        instances_root: 实例根目录
        time_range: 时间范围（可选）

    Returns:
        统计摘要字典：
        - total_sessions: 会话总数
        - total_duration_ms: 总耗时
        - total_turns: 总轮次
        - total_cost_usd: 总成本
        - avg_duration_ms: 平均耗时
        - status_breakdown: 状态分布
        - tools_usage: 工具使用统计

    Raises:
        AgentSystemError: 实例不存在
    """
    instance_path = _get_instance_path(instance_name, instances_root)
    session_manager = SessionManager(instance_path)

    # 获取所有会话或指定会话
    if session_ids is None:
        sessions_metadata = session_manager.list_sessions(limit=10000)
    else:
        sessions_metadata = []
        for sid in session_ids:
            try:
                session = session_manager.get_session(sid)
                sessions_metadata.append(session.get_metadata())
            except Exception as e:
                logger.warning(f"跳过会话 {sid}: {e}")

    # 过滤时间范围
    if time_range:
        start_time, end_time = time_range
        filtered_sessions = []
        for metadata in sessions_metadata:
            try:
                session_time = datetime.fromisoformat(metadata['start_time'])
                if start_time <= session_time <= end_time:
                    filtered_sessions.append(metadata)
            except (ValueError, TypeError, KeyError):
                continue
        sessions_metadata = filtered_sessions

    # 统计
    total_sessions = len(sessions_metadata)
    total_duration_ms = 0
    total_turns = 0
    total_cost_usd = 0.0
    status_breakdown = {}
    tools_usage = {}

    for metadata in sessions_metadata:
        # 读取统计信息
        session_id = metadata['session_id']
        statistics_file = session_manager.sessions_dir / session_id / "statistics.json"

        if statistics_file.exists():
            try:
                with open(statistics_file, 'r', encoding='utf-8') as f:
                    stats = json.load(f)

                total_duration_ms += stats.get('total_duration_ms', 0)
                total_turns += stats.get('num_turns', 0)
                total_cost_usd += stats.get('cost_usd', 0) or 0

                # 工具使用统计
                for tool, count in stats.get('tools_used', {}).items():
                    tools_usage[tool] = tools_usage.get(tool, 0) + count

            except Exception as e:
                logger.warning(f"读取会话 {session_id} 统计信息失败: {e}")

        # 状态分布
        status = metadata.get('status', 'unknown')
        status_breakdown[status] = status_breakdown.get(status, 0) + 1

    # 计算平均值
    avg_duration_ms = total_duration_ms / total_sessions if total_sessions > 0 else 0

    return {
        "total_sessions": total_sessions,
        "total_duration_ms": total_duration_ms,
        "total_turns": total_turns,
        "total_cost_usd": total_cost_usd,
        "avg_duration_ms": avg_duration_ms,
        "status_breakdown": status_breakdown,
        "tools_usage": tools_usage
    }


def export_session(
    instance_name: str,
    session_id: str,
    output_format: str = "json",
    instances_root: Optional[Path] = None,
    output_file: Optional[Path] = None
) -> Union[Dict[str, Any], str]:
    """
    导出会话（支持 JSON 和 Markdown 格式）

    Args:
        instance_name: 实例名称
        session_id: 会话 ID
        output_format: 输出格式（"json" 或 "markdown"）
        instances_root: 实例根目录
        output_file: 输出文件路径（可选，为空则返回字符串）

    Returns:
        导出的内容（字典或字符串）

    Raises:
        AgentSystemError: 导出失败
    """
    details = get_session_details(instance_name, session_id, instances_root)

    if output_format == "json":
        output = details

        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            logger.info(f"会话已导出到: {output_file}")

        return output

    elif output_format == "markdown":
        lines = []
        metadata = details['metadata']
        statistics = details['statistics']

        # 标题
        lines.append(f"# 会话详情：{session_id}")
        lines.append("")

        # 基本信息
        lines.append("## 基本信息")
        lines.append(f"- **实例名称**: {metadata['instance_name']}")
        lines.append(f"- **状态**: {metadata['status']}")
        lines.append(f"- **开始时间**: {metadata['start_time']}")
        lines.append(f"- **结束时间**: {metadata.get('end_time', 'N/A')}")
        lines.append(f"- **嵌套深度**: {metadata['depth']}")
        lines.append("")

        # 提示词历史
        lines.append("## 提示词历史")
        for i, prompt_item in enumerate(metadata.get('prompts', []), 1):
            lines.append(f"### 提示词 {i}")
            lines.append(f"**时间**: {prompt_item.get('timestamp', 'N/A')}")
            lines.append(f"```\n{prompt_item.get('prompt', 'N/A')}\n```")
            lines.append("")

        if not metadata.get('prompts'):
            lines.append("无提示词记录")
            lines.append("")

        # 结果历史
        lines.append("## 结果历史")
        for i, result_item in enumerate(metadata.get('results', []), 1):
            lines.append(f"### 结果 {i}")
            lines.append(f"**时间**: {result_item.get('timestamp', 'N/A')}")
            lines.append(f"**状态**: {'❌ 错误' if result_item.get('is_error', False) else '✅ 成功'}")
            lines.append(f"```\n{result_item.get('result', 'N/A')}\n```")
            lines.append("")

        if not metadata.get('results'):
            lines.append("无结果记录")
            lines.append("")

        # 统计信息
        lines.append("## 统计信息")
        lines.append(f"- **总耗时**: {statistics.get('total_duration_ms', 0)} ms")
        lines.append(f"- **对话轮次**: {statistics.get('num_turns', 0)}")
        lines.append(f"- **消息数量**: {statistics.get('num_messages', 0)}")
        lines.append(f"- **工具调用**: {statistics.get('num_tool_calls', 0)}")
        lines.append(f"- **成本**: ${statistics.get('cost_usd', 0):.4f}")
        lines.append("")

        # 工具使用
        if statistics.get('tools_used'):
            lines.append("## 工具使用")
            for tool, count in statistics['tools_used'].items():
                lines.append(f"- **{tool}**: {count} 次")
            lines.append("")

        # Token 使用
        if statistics.get('token_usage'):
            usage = statistics['token_usage']
            lines.append("## Token 使用")
            lines.append(f"- **输入**: {usage.get('input_tokens', 0)}")
            lines.append(f"- **输出**: {usage.get('output_tokens', 0)}")
            lines.append(f"- **总计**: {usage.get('input_tokens', 0) + usage.get('output_tokens', 0)}")
            lines.append("")

        # 子会话
        if details['subsessions']:
            lines.append("## 子会话")
            for subsess in details['subsessions']:
                lines.append(f"- **{subsess['session_id']}** ({subsess['instance_name']}) - {subsess['status']}")
            lines.append("")

        # 消息列表
        if details['messages']:
            lines.append("## 消息列表")
            lines.append(f"共 {len(details['messages'])} 条消息")
            lines.append("")

        output = "\n".join(lines)

        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(output)
            logger.info(f"会话已导出到: {output_file}")

        return output

    else:
        raise AgentSystemError(f"不支持的输出格式: {output_format}")


def cleanup_sessions(
    instance_name: str,
    retention_days: int = 30,
    dry_run: bool = False,
    instances_root: Optional[Path] = None
) -> Dict[str, Any]:
    """
    清理过期会话

    Args:
        instance_name: 实例名称
        retention_days: 保留天数
        dry_run: 是否模拟运行（不实际删除）
        instances_root: 实例根目录

    Returns:
        清理报告

    Raises:
        AgentSystemError: 实例不存在
    """
    instance_path = _get_instance_path(instance_name, instances_root)
    session_manager = SessionManager(instance_path)

    return session_manager.cleanup_old_sessions(
        retention_days=retention_days,
        dry_run=dry_run
    )


def get_session_messages(
    instance_name: str,
    session_id: str,
    message_types: Optional[List[str]] = None,
    limit: Optional[int] = None,
    instances_root: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """
    获取会话消息列表

    Args:
        instance_name: 实例名称
        session_id: 会话 ID
        message_types: 过滤消息类型（可选）
        limit: 限制返回数量（可选）
        instances_root: 实例根目录

    Returns:
        消息列表

    Raises:
        AgentSystemError: 会话不存在
    """
    instance_path = _get_instance_path(instance_name, instances_root)
    session_manager = SessionManager(instance_path)

    session = session_manager.get_session(session_id)
    return list(session.get_messages(message_types=message_types, limit=limit))


def get_session_tree(
    instance_name: str,
    session_id: str,
    instances_root: Optional[Path] = None
) -> Dict[str, Any]:
    """
    获取会话树（包含所有子会话的层级结构）

    Args:
        instance_name: 实例名称
        session_id: 主会话 ID
        instances_root: 实例根目录

    Returns:
        会话树字典

    Raises:
        AgentSystemError: 会话不存在
    """
    instance_path = _get_instance_path(instance_name, instances_root)
    session_manager = SessionManager(instance_path)

    try:
        return session_manager.get_session_tree(session_id)
    except Exception as e:
        raise AgentSystemError(f"获取会话树失败: {e}")


def print_session_tree(
    instance_name: str,
    session_id: str,
    include_statistics: bool = True,
    instances_root: Optional[Path] = None
) -> str:
    """
    打印会话树（树状格式）

    Args:
        instance_name: 实例名称
        session_id: 主会话 ID
        include_statistics: 是否包含统计信息
        instances_root: 实例根目录

    Returns:
        树状格式的字符串

    Raises:
        AgentSystemError: 会话不存在
    """
    instance_path = _get_instance_path(instance_name, instances_root)
    session_manager = SessionManager(instance_path)

    try:
        return session_manager.print_session_tree(session_id, include_statistics)
    except Exception as e:
        raise AgentSystemError(f"打印会话树失败: {e}")


def get_merged_messages(
    instance_name: str,
    session_id: str,
    include_subsessions: bool = True,
    message_types: Optional[List[str]] = None,
    instances_root: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """
    获取整合的消息（包括子会话）

    Args:
        instance_name: 实例名称
        session_id: 会话 ID
        include_subsessions: 是否包含子会话消息
        message_types: 过滤消息类型
        instances_root: 实例根目录

    Returns:
        整合后的消息列表

    Raises:
        AgentSystemError: 会话不存在
    """
    instance_path = _get_instance_path(instance_name, instances_root)
    session_manager = SessionManager(instance_path)

    try:
        session = session_manager.get_session(session_id)
        return list(session.get_merged_messages(
            include_subsessions=include_subsessions,
            message_types=message_types
        ))
    except Exception as e:
        raise AgentSystemError(f"获取整合消息失败: {e}")


def export_merged_messages(
    instance_name: str,
    session_id: str,
    output_file: Path,
    format: str = "json",
    include_subsessions: bool = True,
    instances_root: Optional[Path] = None
) -> None:
    """
    导出整合后的消息到文件

    Args:
        instance_name: 实例名称
        session_id: 会话 ID
        output_file: 输出文件路径
        format: 输出格式（json/jsonl/text）
        include_subsessions: 是否包含子会话
        instances_root: 实例根目录

    Raises:
        AgentSystemError: 导出失败
    """
    instance_path = _get_instance_path(instance_name, instances_root)
    session_manager = SessionManager(instance_path)

    try:
        session_manager.export_merged_messages(
            session_id,
            output_file,
            format=format,
            include_subsessions=include_subsessions
        )
    except Exception as e:
        raise AgentSystemError(f"导出整合消息失败: {e}")


# 便捷别名
get_details = get_session_details
list_all = list_sessions
search = search_sessions
get_summary = get_session_statistics_summary
export = export_session
cleanup = cleanup_sessions
get_messages = get_session_messages
get_tree = get_session_tree
print_tree = print_session_tree
get_merged = get_merged_messages
export_merged = export_merged_messages
