"""
会话查询示例代码

演示如何查询和分析 Claude Agent System 的会话记录
"""

import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from src.session_query import *

async def main():
    """主函数 - 演示各种会话查询功能"""

    # 配置参数
    instance_name = "demo_agent"  # 实例名称
    instances_root = Path("C:/Users/Lenovo/Desktop/test2/claudecode/instances")

    print("=" * 80)
    print("🔍 Claude Agent 会话查询示例")
    print("=" * 80)

    try:
        # 1. 列出所有会话
        print("\n1. 📋 列出最近的所有会话")
        print("-" * 50)
        sessions = list_sessions(
            instance_name=instance_name,
            instances_root=instances_root,
            limit=10
        )

        if not sessions:
            print("❌ 没有找到任何会话记录")
            return

        print(f"📊 找到 {len(sessions)} 个会话：\n")
        for i, session in enumerate(sessions, 1):
            print(f"{i}. [{session['session_id'][:20]}...] {session['instance_name']}")
            print(f"   状态: {session['status']}")
            print(f"   开始时间: {session['start_time']}")
            if session.get('prompts'):
                print(f"   首个提示: {session['prompts'][0]['prompt'][:100]}...")
            print()

        # 选择最近的会话进行分析
        if not sessions:
            print("没有可用的会话")
            return

        latest_session = sessions[0]
        session_id = latest_session['session_id']

        # 2. 获取会话详情
        print(f"\n2. 📊 获取会话详情: {session_id[:20]}...")
        print("-" * 50)
        details = get_session_details(
            instance_name=instance_name,
            session_id=session_id,
            instances_root=instances_root,
            include_messages=False  # 先不包含消息，只看元数据
        )

        metadata = details['metadata']
        statistics = details['statistics']

        print(f"📝 基本信息:")
        print(f"   实例名称: {metadata['instance_name']}")
        print(f"   状态: {metadata['status']}")
        print(f"   嵌套深度: {metadata.get('depth', 0)}")
        print(f"   父会话: {metadata.get('parent_session_id', 'None')}")

        if statistics:
            print(f"\n📈 统计信息:")
            print(f"   消息数量: {statistics.get('num_messages', 0)}")
            print(f"   工具调用: {statistics.get('num_tool_calls', 0)}")
            print(f"   耗时: {statistics.get('total_duration_ms', 0)} ms")
            print(f"   Token使用: {statistics.get('token_usage', {}).get('input_tokens', 0)} 输入 / "
                  f"{statistics.get('token_usage', {}).get('output_tokens', 0)} 输出")

        # 3. 显示子会话信息
        if statistics.get('subsessions'):
            print(f"\n🔄 子会话信息:")
            for i, sub in enumerate(statistics['subsessions'], 1):
                print(f"   {i}. {sub['session_id']}")
                print(f"      工具: {sub['tool_name']}")
                print(f"      时间: {sub['timestamp']}")

        # 4. 显示会话树（如果有子会话）
        if statistics.get('subsessions'):
            print(f"\n3. 🌳 会话树结构")
            print("-" * 50)
            tree_str = print_session_tree(
                instance_name=instance_name,
                session_id=session_id,
                instances_root=instances_root,
                include_statistics=True
            )
            print(tree_str)

        # 5. 获取消息列表
        print(f"\n4. 📨 最近的消息")
        print("-" * 50)

        # 获取原始消息
        messages = get_session_messages(
            instance_name=instance_name,
            session_id=session_id,
            instances_root=instances_root,
            limit=10  # 只获取最近10条
        )

        print(f"📨 共 {len(messages)} 条消息（显示最近10条）:\n")
        for msg in messages:
            msg_type = msg['message_type']
            timestamp = msg['timestamp']

            print(f"[{msg_type}] {timestamp}")

            # 简化显示消息内容
            data = msg['data']

            if msg_type == "AssistantMessage":
                content = data.get('content', [])
                for block in content:
                    if block.get('type') == 'text':
                        text = block['text'][:100] + "..." if len(block['text']) > 100 else block['text']
                        print(f"  📝 {text}")
                    elif block.get('type') == 'tool_use':
                        print(f"  🔧 调用工具: {block['name']}")

            elif msg_type == "UserMessage":
                if isinstance(data.get('content'), str):
                    text = data['content'][:100] + "..." if len(data['content']) > 100 else data['content']
                    print(f"  👤 {text}")
                elif isinstance(data.get('content'), list):
                    for block in data['content']:
                        if block.get('type') == 'tool_result':
                            print(f"  ✅ 工具结果")
                        elif block.get('type') == 'text':
                            print(f"  👤 {block['text'][:100]}")

            print()

        # 6. 获取整合的消息（包含子会话）
        print(f"\n5. 🔄 整合的消息（包含子会话）")
        print("-" * 50)

        merged_messages = get_merged_messages(
            instance_name=instance_name,
            session_id=session_id,
            include_subsessions=True,
            instances_root=instances_root,
            message_types=["AssistantMessage", "UserMessage"],  # 只显示主要消息
            limit=20
        )

        print(f"📨 整合后共 {len(merged_messages)} 条消息:\n")
        for msg in merged_messages:
            indent = "  " * msg.get('indent_level', 0)
            msg_type = msg['message_type']
            session_id_short = msg.get('session_id', 'unknown')[:12]
            timestamp = msg.get('timestamp', '')[:19]

            print(f"{indent}[{msg_type}] {timestamp} ({session_id_short}...)")

            # 显示消息内容摘要
            if msg_type == "AssistantMessage":
                data = msg.get('data', {})
                content = data.get('content', [])
                for block in content:
                    if block.get('type') == 'text':
                        text = block['text'][:80] + "..." if len(block['text']) > 80 else block['text']
                        # 清理换行符
                        text = text.replace('\n', ' ')
                        print(f"{indent}  📝 {text}")
                    elif block.get('type') == 'tool_use':
                        print(f"{indent}  🔧 调用: {block['name']}")

            print()

        # 7. 导出功能演示
        print(f"\n6. 💾 导出会话记录")
        print("-" * 50)

        # 创建输出目录
        output_dir = Path("exported_sessions")
        output_dir.mkdir(exist_ok=True)

        # 导出为 JSON
        json_file = output_dir / f"session_{session_id[:20]}.json"
        export_merged_messages(
            instance_name=instance_name,
            session_id=session_id,
            output_file=json_file,
            format="json",
            include_subsessions=True,
            instances_root=instances_root
        )
        print(f"✅ 已导出整合消息到: {json_file}")

        # 导出为易读文本
        text_file = output_dir / f"session_{session_id[:20]}.txt"
        export_merged_messages(
            instance_name=instance_name,
            session_id=session_id,
            output_file=text_file,
            format="text",
            include_subsessions=True,
            instances_root=instances_root
        )
        print(f"✅ 已导出易读文本到: {text_file}")

        # 8. 搜索功能演示
        print(f"\n7. 🔍 搜索功能演示")
        print("-" * 50)

        # 搜索包含"分析"的会话
        search_results = search_sessions(
            instance_name=instance_name,
            query="分析",
            field="prompts",
            instances_root=instances_root
        )

        print(f"🔍 搜索包含'分析'的提示词: 找到 {len(search_results)} 个会话")
        for i, session in enumerate(search_results, 1):
            print(f"  {i}. {session['session_id'][:20]}... - {session['status']}")

        # 9. 统计摘要
        print(f"\n8. 📊 统计摘要")
        print("-" * 50)

        # 获取最近7天的统计
        end_time = datetime.now()
        start_time = end_time - timedelta(days=7)

        summary = get_session_statistics_summary(
            instance_name=instance_name,
            instances_root=instances_root,
            time_range=(start_time, end_time)
        )

        print(f"📊 最近7天统计:")
        print(f"   总会话数: {summary['total_sessions']}")
        print(f"   总耗时: {summary['total_duration_ms']} ms ({summary['total_duration_ms']/1000:.1f} 秒)")
        print(f"   总轮次: {summary['total_turns']}")
        print(f"   总成本: ${summary['total_cost_usd']:.4f}")
        print(f"   平均耗时: {summary['avg_duration_ms']} ms")

        print(f"\n   状态分布:")
        for status, count in summary['status_breakdown'].items():
            print(f"     {status}: {count}")

        if summary['tools_usage']:
            print(f"\n   工具使用排行:")
            # 按使用次数排序
            sorted_tools = sorted(summary['tools_usage'].items(), key=lambda x: x[1], reverse=True)
            for tool, count in sorted_tools[:10]:  # 只显示前10个
                print(f"     {tool}: {count} 次")

        print("\n" + "=" * 80)
        print("✅ 会话查询示例完成！")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())