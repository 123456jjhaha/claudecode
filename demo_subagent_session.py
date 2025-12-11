#!/usr/bin/env python3
"""
包含子智能体调用的完整会话记录演示
展示父会话调用子智能体，以及调用关系图的生成
"""

import asyncio
import sys
import json
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.session_manager import SessionManager
from src.session_query import get_session_details, get_call_graph

class MockSubagentCall:
    """模拟子智能体调用"""

    @staticmethod
    def create_subagent_session(parent_session, subagent_name="data_analyst"):
        """创建子智能体会话"""
        # 创建子会话
        asyncio.create_task(
            parent_session.create_subsession(
                instance_name=subagent_name,
                prompt="请分析这份数据并生成报告",
                context={"parent_task": "数据分析", "data_source": "sales_data.csv"}
            )
        )

        # 返回模拟的子会话结果
        return {
            "status": "success",
            "result": "数据分析完成：销售数据Q3增长23%，主要来自新产品线",
            "_session_metadata": {
                "session_id": f"child_{parent_session.session_id[-8:]}",
                "instance_name": subagent_name
            }
        }

async def demo_subagent_call():
    """演示包含子智能体调用的完整会话"""
    print("🚀 子智能体调用会话记录演示\n")

    try:
        # 创建父会话管理器
        parent_instances_root = project_root / "instances" / "parent_agent"
        parent_session_manager = SessionManager(parent_instances_root)

        print("1️⃣ 开始父智能体复杂任务...")

        # 创建父会话
        parent_session = await parent_session_manager.create_session(
            initial_prompt="请分析公司Q3销售数据，并生成详细的业务报告。包括数据可视化和建议。",
            context={"task_type": "complex_analysis", "requires_subagents": True}
        )

        parent_session_id = parent_session.session_id
        print(f"📝 父会话ID: {parent_session_id}")

        # 模拟父智能体的工作流程
        workflow_steps = [
            {
                "role": "assistant",
                "content": "我来帮您分析Q3销售数据。这是一个复杂的分析任务，我需要调用专门的子智能体来处理不同方面的分析。",
                "description": "父智能体分析任务并决定调用子智能体"
            },
            {
                "role": "subagent_call",
                "subagent": "data_analyst",
                "task": "分析销售数据和统计指标",
                "description": "调用数据分析子智能体"
            },
            {
                "role": "subagent_call",
                "subagent": "visualization_expert",
                "task": "生成数据可视化图表",
                "description": "调用可视化专家子智能体"
            },
            {
                "role": "subagent_call",
                "subagent": "business_strategist",
                "task": "提供业务建议和策略",
                "description": "调用商业策略师子智能体"
            },
            {
                "role": "assistant",
                "content": "基于各个子智能体的分析结果，我现在为您整合完整的业务报告。",
                "description": "父智能体汇总子智能体结果"
            }
        ]

        print(f"\n🔄 模拟 {len(workflow_steps)} 步工作流程...")

        subsession_ids = []

        for i, step in enumerate(workflow_steps, 1):
            print(f"  步骤 {i}: {step['description']}")

            if step["role"] == "assistant":
                # 记录助手消息
                from demo_complete_session import MockClaudeMessage
                assistant_msg = MockClaudeMessage.create_assistant_message([
                    {"type": "text", "text": step["content"]}
                ])
                await parent_session.record_message(assistant_msg)

            elif step["role"] == "subagent_call":
                # 创建子智能体会话
                print(f"    📞 调用子智能体: {step['subagent']}")

                # 创建子会话
                subsession = await parent_session.create_subsession(
                    instance_name=step["subagent"],
                    prompt=step["task"],
                    context={
                        "parent_session_id": parent_session_id,
                        "parent_task": "销售数据分析",
                        "specialization": step["subagent"]
                    }
                )

                subsession_ids.append(subsession.session_id)

                # 模拟子智能体工作
                await asyncio.sleep(0.1)

                # 记录子智能体的响应
                sub_result = f"{step['subagent']}分析完成：基于Q3数据，{'销售增长明显' if 'analyst' in step['subagent'] else '图表显示上升趋势' if 'viz' in step['subagent'] else '建议加大投入'}"

                # 创建模拟的结果消息
                result_msg = {
                    "type": "subagent_result",
                    "data": {
                        "subagent": step["subagent"],
                        "result": sub_result,
                        "session_id": subsession.session_id
                    }
                }
                await parent_session.record_message(result_msg)

                print(f"    ✅ 子智能体完成: {sub_result}")

            await asyncio.sleep(0.1)

        # 完成父会话
        print(f"\n✅ 完成父会话记录...")
        from demo_complete_session import MockClaudeMessage
        result_message = MockClaudeMessage.create_result_message(
            duration_ms=25000,  # 25秒的复杂任务
            num_turns=len(workflow_steps),
            cost=0.15
        )
        await parent_session.finalize(result_message=result_message)

        # 分析会话结果
        print(f"\n📊 父会话分析结果:")

        from src.session_query import get_session_details
        parent_details = get_session_details("parent_agent", parent_session_id, project_root / "instances")

        parent_metadata = parent_details['metadata']
        parent_statistics = parent_details['statistics']

        print(f"  📅 开始时间: {parent_metadata['start_time']}")
        print(f"  📅 结束时间: {parent_metadata['end_time']}")
        print(f"  ✅ 状态: {parent_metadata['status']}")
        print(f"  📝 初始提示: {parent_metadata['initial_prompt'][:50]}...")

        print(f"\n📈 父会话统计信息:")
        print(f"  💬 总消息数: {parent_statistics['num_messages']}")
        print(f"  🔧 工具调用次数: {parent_statistics['num_tool_calls']}")
        print(f"  🕐 会话时长: {parent_statistics.get('total_duration_ms', 0)} ms")
        print(f"  💰 成本: ${parent_statistics.get('cost_usd', 0):.4f}")
        print(f"  📊 子会话数量: {len(parent_statistics.get('subsessions', []))}")

        # 分析子会话
        print(f"\n📊 子会话分析结果:")

        for i, subsession_id in enumerate(subsession_ids, 1):
            try:
                # 获取子会话详情
                sub_details = get_session_details(
                    f"parent_agent/subsessions/{subsession_id}",
                    subsession_id,
                    parent_session.session_dir
                )

                if sub_details:
                    sub_metadata = sub_details['metadata']
                    sub_stats = sub_details['statistics']

                    print(f"  📋 子会话 {i} ({sub_metadata['instance_name']}):")
                    print(f"    📝 ID: {sub_metadata['session_id']}")
                    print(f"    ⏱️  时长: {sub_stats.get('total_duration_ms', 0)} ms")
                    print(f"    💬 消息数: {sub_stats['num_messages']}")
                    print(f"    💰 成本: ${sub_stats.get('cost_usd', 0):.4f}")

            except Exception as e:
                print(f"  ❌ 无法获取子会话 {subsession_id} 详情: {e}")

        # 生成调用关系图
        print(f"\n🔗 生成调用关系图...")

        try:
            call_graph = get_call_graph("parent_agent", parent_session_id, project_root / "instances")

            print(f"  ✅ 调用关系图生成成功")
            print(f"  📊 图表结构:")
            print(f"    - 根会话: {call_graph.get('root_session_id', 'N/A')}")
            print(f"    - 生成时间: {call_graph.get('generated_at', 'N/A')}")

            if 'graph' in call_graph:
                graph_data = call_graph['graph']
                print(f"    - 节点数量: {len(graph_data.get('nodes', []))}")
                print(f"    - 边数量: {len(graph_data.get('edges', []))}")

                # 显示节点信息
                if 'nodes' in graph_data:
                    print(f"    📋 节点列表:")
                    for node in graph_data['nodes']:
                        node_type = node.get('type', 'unknown')
                        node_name = node.get('name', 'unnamed')
                        node_instance = node.get('instance_name', 'N/A')
                        print(f"      - {node_type}: {node_name} ({node_instance})")

                # 显示边（调用关系）
                if 'edges' in graph_data:
                    print(f"    🔗 调用关系:")
                    for edge in graph_data['edges']:
                        source = edge.get('source', 'unknown')
                        target = edge.get('target', 'unknown')
                        relation = edge.get('relation', 'calls')
                        print(f"      {source} --[{relation}]--> {target}")

        except Exception as e:
            print(f"  ❌ 调用关系图生成失败: {e}")

        # 展示文件结构
        print(f"\n📁 完整的文件结构:")
        parent_session_path = parent_session.session_dir
        print(f"  📂 父会话目录: {parent_session_path}")

        # 检查子会话目录
        subsessions_dir = parent_session_path / "subsessions"
        if subsessions_dir.exists():
            print(f"  📂 子会话目录: {subsessions_dir}")
            for sub_dir in subsessions_dir.iterdir():
                if sub_dir.is_dir():
                    print(f"    📄 {sub_dir.name}/")
                    for file in sub_dir.iterdir():
                        if file.is_file():
                            size = file.stat().st_size
                            print(f"      📄 {file.name}: {size} 字节")

        # 保存调用关系图到文件
        call_graph_file = project_root / f"call_graph_{parent_session_id}.json"
        if 'call_graph' in locals():
            with open(call_graph_file, 'w', encoding='utf-8') as f:
                json.dump(call_graph, f, indent=2, ensure_ascii=False)
            print(f"  📄 调用关系图已保存: {call_graph_file}")

        print(f"\n🎉 子智能体调用会话记录演示完成！")
        print(f"💡 这展示了包含多个子智能体调用的复杂工作流程和完整的调用关系图")

    except Exception as e:
        print(f"❌ 演示过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(demo_subagent_call())