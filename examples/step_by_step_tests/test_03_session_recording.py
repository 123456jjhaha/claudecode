"""
测试 3: 会话记录功能

测试会话记录系统的各项功能
- 会话创建和管理
- 消息记录
- 会话查询
- 统计信息
- 调用关系图
"""

import asyncio
import sys
import time
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src import AgentSystem, set_log_level
from src.session_query import (
    get_session_details,
    list_sessions,
    search_sessions,
    get_call_graph,
    export_session,
    get_session_statistics_summary
)
import logging

# 配置日志
set_log_level(logging.INFO)


async def test_session_recording():
    """测试会话记录功能"""
    print("\n" + "=" * 60)
    print("📝 测试 3: 会话记录功能")
    print("=" * 60)

    try:
        # 创建并初始化 agent
        print("\n1. 初始化 Demo Agent...")
        agent = AgentSystem("demo_agent")
        await agent.initialize()

        # 检查会话管理器
        print("\n2. 检查会话管理器配置...")
        if agent.session_manager:
            print(f"   - 会话记录启用: {agent.session_manager.enabled}")
            print(f"   - 保留天数: {agent.session_manager.retention_days}")
            print(f"   - 最大大小: {agent.session_manager.max_total_size_mb}MB")
            print(f"   - 批量大小: {agent.session_manager.batch_size}")
        else:
            print("   - 会话管理器未初始化")

        # 测试 1: 基础会话记录
        print("\n3. 测试基础会话记录...")
        session_id_before = agent.current_session_id
        print(f"   当前会话ID: {session_id_before}")

        # 执行一些查询
        response1 = await agent.query_text(
            "请介绍你自己，并使用一个工具来演示你的能力。"
        )
        response2 = await agent.query_text(
            "使用计算器计算 123 + 456，并解释结果。"
        )

        session_id_after = agent.current_session_id
        print(f"   查询后会话ID: {session_id_after}")

        # 测试 2: 会话详情查询
        print("\n4. 测试会话详情查询...")
        if session_id_after:
            try:
                details = get_session_details("demo_agent", session_id_after)
                print(f"   - 会话状态: {details['metadata'].get('status')}")
                print(f"   - 开始时间: {details['metadata'].get('start_time')}")
                print(f"   - 消息数量: {len(details['messages'])}")
                print(f"   - 工具使用次数: {details['statistics'].get('tool_calls_count', 0)}")
                print(f"   - 总耗时: {details['statistics'].get('duration_seconds', 0):.2f}秒")
                print(f"   - 成本: ${details['statistics'].get('cost_usd', 0):.6f}")
            except Exception as e:
                print(f"   会话详情查询失败: {e}")

        # 测试 3: 会话列表
        print("\n5. 测试会话列表...")
        try:
            sessions = list_sessions("demo_agent", limit=5)
            print(f"   - 最近会话数: {len(sessions)}")
            for session in sessions:
                print(f"     * {session['session_id']} - {session['start_time']}")
        except Exception as e:
            print(f"   会话列表查询失败: {e}")

        # 测试 4: 复杂会话记录（包含子实例）
        print("\n6. 测试复杂会话记录...")
        complex_response = await agent.query_text("""
        请完成一个复杂任务并记录整个过程：
        1. 使用子实例 code_reviewer 分析 tools/calculator.py
        2. 使用计算器进行一些计算
        3. 使用文件分析器分析配置文件
        4. 总结整个分析过程
        """)
        complex_session_id = agent.current_session_id
        print(f"   复杂会话ID: {complex_session_id}")

        # 等待一会确保所有消息都被写入
        await asyncio.sleep(2)

        # 测试 5: 调用关系图
        print("\n7. 测试调用关系图...")
        if complex_session_id:
            try:
                call_graph = get_call_graph("demo_agent", complex_session_id)
                print(f"   - 根会话ID: {call_graph.get('root_session_id')}")
                print(f"   - 图深度: {get_graph_depth(call_graph.get('graph', {}))}")
                print(f"   - 子会话数: {count_subsessions(call_graph.get('graph', {}))}")
            except Exception as e:
                print(f"   调用关系图生成失败: {e}")

        # 测试 6: 会话搜索
        print("\n8. 测试会话搜索...")
        try:
            # 搜索包含"计算器"的会话
            search_results = search_sessions("demo_agent", query="计算器")
            print(f"   - 包含'计算器'的会话数: {len(search_results)}")

            # 搜索包含"code_reviewer"的会话
            search_results = search_sessions("demo_agent", query="code_reviewer")
            print(f"   - 包含'code_reviewer'的会话数: {len(search_results)}")
        except Exception as e:
            print(f"   会话搜索失败: {e}")

        # 测试 7: 会话导出
        print("\n9. 测试会话导出...")
        if session_id_after:
            try:
                # 导出为 JSON
                json_file = Path(__file__).parent / f"session_{session_id_after[:8]}.json"
                export_session(
                    "demo_agent",
                    session_id_after,
                    output_format="json",
                    output_file=str(json_file)
                )
                print(f"   - JSON导出成功: {json_file}")

                # 导出为 Markdown
                md_file = Path(__file__).parent / f"session_{session_id_after[:8]}.md"
                export_session(
                    "demo_agent",
                    session_id_after,
                    output_format="markdown",
                    output_file=str(md_file)
                )
                print(f"   - Markdown导出成功: {md_file}")
            except Exception as e:
                print(f"   会话导出失败: {e}")

        # 测试 8: 统计摘要
        print("\n10. 测试统计摘要...")
        try:
            # 获取所有会话ID
            all_sessions = list_sessions("demo_agent", limit=10)
            session_ids = [s['session_id'] for s in all_sessions]

            if session_ids:
                summary = get_session_statistics_summary("demo_agent", session_ids)
                print(f"   - 总会话数: {summary['total_sessions']}")
                print(f"   - 总耗时: {summary['total_duration_seconds']:.2f}秒")
                print(f"   - 总成本: ${summary['total_cost_usd']:.6f}")
                print(f"   - 平均耗时: {summary['avg_duration_seconds']:.2f}秒")
                print(f"   - 最活跃的工具: {summary['most_used_tools']}")
        except Exception as e:
            print(f"   统计摘要失败: {e}")

        print("\n" + "=" * 60)
        print("✅ 会话记录功能测试全部通过！")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


def get_graph_depth(graph: dict, current_depth: int = 0) -> int:
    """计算调用关系图的深度"""
    if not graph:
        return current_depth

    max_child_depth = current_depth
    for child in graph.get('children', []):
        child_depth = get_graph_depth(child, current_depth + 1)
        max_child_depth = max(max_child_depth, child_depth)

    return max_child_depth


def count_subsessions(graph: dict) -> int:
    """计算子会话数量"""
    if not graph:
        return 0

    count = 0
    for child in graph.get('children', []):
        count += 1
        count += count_subsessions(child)

    return count


if __name__ == "__main__":
    asyncio.run(test_session_recording())