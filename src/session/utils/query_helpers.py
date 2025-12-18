"""
会话查询工具函数

这些函数专门用于会话查询相关的辅助操作，
从 session_query.py 和 tree_builder.py 中提取出来，
保持 SessionQuery 类的干净和整洁。
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from ...error_handling import AgentSystemError
from ...logging_config import get_logger

logger = get_logger(__name__)


def calculate_session_statistics(all_sessions: List[Dict[str, Any]], session_manager, recent_days: Optional[int] = None) -> Dict[str, Any]:
    """
    计算会话统计摘要

    Args:
        all_sessions: 所有会话的元数据列表
        session_manager: SessionManager 实例
        recent_days: 只统计最近N天的会话（可选）

    Returns:
        统计摘要字典
    """
    try:
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
        raise AgentSystemError(f"计算统计摘要失败: {e}")


def search_sessions_in_list(
    all_sessions: List[Dict[str, Any]],
    query: str,
    field: str = "initial_prompt",
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    在会话列表中搜索匹配的会话

    Args:
        all_sessions: 所有会话的元数据列表
        query: 搜索关键词
        field: 搜索字段（initial_prompt/result）
        limit: 返回数量限制

    Returns:
        匹配的会话元数据列表
    """
    try:
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


def export_session_to_text(output_file: Path, session_id: str, data: Dict[str, Any]) -> None:
    """
    导出会话为文本格式

    Args:
        output_file: 输出文件路径
        session_id: 会话 ID
        data: 会话数据
    """
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

        if 'messages' in data:
            f.write(f"\n=== Messages ===\n")
            for msg in data["messages"]:
                f.write(f"\n[{msg['seq']}] {msg['message_type']} @ {msg['timestamp']}\n")


def export_session_to_jsonl(output_file: Path, data: Dict[str, Any], include_messages: bool = True) -> None:
    """
    导出会话为 JSONL 格式

    Args:
        output_file: 输出文件路径
        data: 会话数据
        include_messages: 是否包含消息
    """
    with open(output_file, 'w', encoding='utf-8') as f:
        # 写入元数据
        json.dump({"type": "metadata", "data": data["metadata"]}, f, ensure_ascii=False)
        f.write('\n')
        # 写入统计信息
        json.dump({"type": "statistics", "data": data["statistics"]}, f, ensure_ascii=False)
        f.write('\n')
        # 写入消息
        if include_messages and 'messages' in data:
            for msg in data["messages"]:
                json.dump({"type": "message", "data": msg}, f, ensure_ascii=False)
                f.write('\n')




def build_tree_node(
    session_id: str,
    instance_name: str,
    details: Dict[str, Any],
    include_messages: bool = True
) -> Dict[str, Any]:
    """
    构建会话树节点

    Args:
        session_id: 会话 ID
        instance_name: 实例名称
        details: 会话详情
        include_messages: 是否包含消息

    Returns:
        树节点字典
    """
    tree_node = {
        "session_id": session_id,
        "instance_name": details["metadata"]["instance_name"],
        "depth": details["metadata"].get("depth", 0),
        "metadata": details["metadata"],
        "statistics": details["statistics"],
        "subsessions": []
    }

    # 可选：包含消息
    if include_messages:
        tree_node["messages"] = details.get("messages", [])

    return tree_node


def flatten_tree_to_list(tree: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    将树形结构展平为列表

    Args:
        tree: 会话树

    Returns:
        会话列表（按深度优先顺序）
    """
    result = []

    def traverse(node: Dict[str, Any]):
        # 提取节点信息（不包含 subsessions）
        node_info = {k: v for k, v in node.items() if k != "subsessions"}
        result.append(node_info)

        # 递归遍历子节点
        for child in node.get("subsessions", []):
            traverse(child)

    traverse(tree)
    return result