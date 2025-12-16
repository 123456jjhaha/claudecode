"""
简单的会话查看器

快速查看和分析 Claude Agent 会话记录的轻量级工具
"""

import asyncio
import sys
from pathlib import Path
from src.session_query import *

def print_header(title):
    """打印标题"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def print_section(title):
    """打印章节标题"""
    print(f"\n{title}")
    print("-" * 40)

async def view_session(session_id=None, limit=5):
    """查看指定会话或最新会话"""

    # 配置
    instance_name = "demo_agent"
    instances_root = Path("C:/Users/Lenovo/Desktop/test2/claudecode/instances")

    # 如果没有指定会话ID，获取最新的
    if not session_id:
        print_section("📋 获取最新会话")
        sessions = list_sessions(instance_name, instances_root=instances_root, limit=1)
        if not sessions:
            print("❌ 没有找到任何会话")
            return
        session_id = sessions[0]['session_id']
        print(f"✅ 找到最新会话: {session_id}")

    print_header(f"🔍 查看会话: {session_id[:20]}...")

    # 获取会话详情
    details = get_session_details(
        instance_name=instance_name,
        session_id=session_id,
        instances_root=instances_root
    )

    metadata = details['metadata']
    statistics = details['statistics']

    # 基本信息
    print_section("📊 基本信息")
    print(f"实例名称: {metadata['instance_name']}")
    print(f"状态: {metadata['status']}")
    print(f"开始时间: {metadata['start_time']}")
    print(f"结束时间: {metadata.get('end_time', '运行中...')}")
    print(f"嵌套深度: {metadata.get('depth', 0)}")

    # 统计信息
    if statistics:
        print_section("📈 统计信息")
        print(f"消息数量: {statistics.get('num_messages', 0)}")
        print(f"工具调用: {statistics.get('num_tool_calls', 0)}")
        print(f"对话轮次: {statistics.get('num_turns', 0)}")

        # Token使用
        usage = statistics.get('token_usage', {})
        if usage:
            print(f"Token使用: {usage.get('input_tokens', 0)} 输入 / {usage.get('output_tokens', 0)} 输出")

        # 成本
        cost = statistics.get('cost_usd')
        if cost:
            print(f"总成本: ${cost:.4f}")

    # 子会话
    if statistics.get('subsessions'):
        print_section("🔄 子会话")
        for i, sub in enumerate(statistics['subsessions'], 1):
            print(f"{i}. {sub['session_id'][:20]}...")
            print(f"   工具: {sub['tool_name']}")
            print(f"   时间: {sub['timestamp']}")

    # 最近的提示词
    if metadata.get('prompts'):
        print_section("💭 提示词历史")
        for i, prompt in enumerate(metadata['prompts'][-3:], 1):  # 显示最近3个
            print(f"{i}. {prompt['prompt'][:100]}...")
            print(f"   时间: {prompt['timestamp']}")

    # 最近的工具调用
    if statistics.get('tools_used'):
        print_section("🔧 工具使用")
        for tool, count in statistics['tools_used'].items():
            print(f"  {tool}: {count} 次")

    # 消息预览
    print_section("📨 消息预览")
    messages = get_session_messages(
        instance_name=instance_name,
        session_id=session_id,
        instances_root=instances_root,
        limit=limit
    )

    print(f"显示最近 {len(messages)} 条消息:\n")
    for msg in messages:
        msg_type = msg['message_type']
        timestamp = msg['timestamp'][:19]  # 只显示到秒

        icon = {"UserMessage": "👤", "AssistantMessage": "🤖", "SystemMessage": "⚙️"}.get(msg_type, "📄")
        print(f"{icon} [{msg_type}] {timestamp}")

        # 简化的内容显示
        data = msg['data']
        if msg_type == "AssistantMessage":
            content = data.get('content', [])
            for block in content:
                if block.get('type') == 'text':
                    text = block['text'][:150]
                    # 清理格式
                    text = text.replace('\n', ' ').replace('  ', ' ')
                    print(f"  📝 {text}...")
                elif block.get('type') == 'tool_use':
                    print(f"  🔧 调用: {block['name']}")

        elif msg_type == "UserMessage":
            if isinstance(data.get('content'), list):
                for block in data['content']:
                    if block.get('type') == 'tool_result':
                        print(f"  ✅ 工具结果")
                    elif block.get('type') == 'text':
                        print(f"  👤 {block['text'][:150]}...")

        print()

    # 导出选项
    print_section("💾 导出选项")
    print("如需导出完整会话记录，可以使用:")
    print(f"python -c \"from simple_session_viewer import export_session; export_session('{session_id}')\"")

async def list_recent_sessions(count=10):
    """列出最近的会话"""
    print_header("📋 最近的会话列表")

    sessions = list_sessions(
        "demo_agent",
        instances_root=Path("C:/Users/Lenovo/Desktop/test2/claudecode/instances"),
        limit=count
    )

    if not sessions:
        print("❌ 没有找到任何会话")
        return

    print(f"共找到 {len(sessions)} 个会话:\n")

    for i, session in enumerate(sessions, 1):
        print(f"{i}. [{session['session_id']}]")
        print(f"   实例: {session['instance_name']}")
        print(f"   状态: {session['status']}")
        print(f"   时间: {session['start_time']}")

        # 显示第一个提示词（如果有）
        if session.get('prompts'):
            first_prompt = session['prompts'][0]['prompt'][:100]
            print(f"   提示: {first_prompt}...")

        print()

async def search_sessions(query, field="prompts"):
    """搜索会话"""
    print_header(f"🔍 搜索: '{query}'")

    results = search_sessions(
        "demo_agent",
        query,
        field=field,
        instances_root=Path("C:/Users/Lenovo/Desktop/test2/claudecode/instances")
    )

    if not results:
        print("❌ 没有找到匹配的会话")
        return

    print(f"找到 {len(results)} 个匹配的会话:\n")

    for i, session in enumerate(results, 1):
        print(f"{i}. [{session['session_id']}] {session['status']}")
        print(f"   时间: {session['start_time']}")

        # 显示匹配的内容片段
        if field == "prompts" and session.get('prompts'):
            for prompt in session['prompts']:
                if query.lower() in prompt['prompt'].lower():
                    # 高亮显示匹配的部分
                    text = prompt['prompt']
                    start = text.lower().find(query.lower())
                    if start != -1:
                        highlighted = text[:start] + f"**{query}**" + text[start+len(query):]
                        print(f"   提示: {highlighted[:150]}...")
                    break

        print()

def export_session(session_id):
    """导出会话"""
    import asyncio

    async def _export():
        output_dir = Path("exported_sessions")
        output_dir.mkdir(exist_ok=True)

        # 导出为JSON
        json_file = output_dir / f"session_{session_id[:20]}.json"
        export_merged_messages(
            "demo_agent",
            session_id,
            json_file,
            format="json",
            instances_root=Path("C:/Users/Lenovo/Desktop/test2/claudecode/instances")
        )
        print(f"✅ 已导出JSON到: {json_file}")

        # 导出为文本
        text_file = output_dir / f"session_{session_id[:20]}.txt"
        export_merged_messages(
            "demo_agent",
            session_id,
            text_file,
            format="text",
            instances_root=Path("C:/Users/Lenovo/Desktop/test2/claudecode/instances")
        )
        print(f"✅ 已导出文本到: {text_file}")

    asyncio.run(_export())

# 主函数
async def main():
    """主菜单"""
    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "list":
            count = int(sys.argv[2]) if len(sys.argv) > 2 else 10
            await list_recent_sessions(count)

        elif command == "view":
            session_id = sys.argv[2] if len(sys.argv) > 2 else None
            limit = int(sys.argv[3]) if len(sys.argv) > 3 else 5
            await view_session(session_id, limit)

        elif command == "search":
            if len(sys.argv) < 3:
                print("请提供搜索关键词")
                return
            query = sys.argv[2]
            field = sys.argv[3] if len(sys.argv) > 3 else "prompts"
            await search_sessions(query, field)

        elif command == "export":
            if len(sys.argv) < 3:
                print("请提供会话ID")
                return
            export_session(sys.argv[2])

        else:
            print_usage()
    else:
        print_usage()

def print_usage():
    """打印使用说明"""
    print("""
🔍 Claude Agent 会话查看器

使用方法:
  python simple_session_viewer.py <命令> [参数]

命令:
  list [数量]           - 列出最近的会话 (默认10个)
  view [会话ID] [数量]   - 查看指定会话 (默认最新会话，显示5条消息)
  search <关键词> [字段] - 搜索会话 (字段: prompts, results)
  export <会话ID>        - 导出会话记录

示例:
  python simple_session_viewer.py list 20
  python simple_session_viewer.py view
  python simple_session_viewer.py view 20251214T040016_1842_99aea457
  python simple_session_viewer.py search "分析"
  python simple_session_viewer.py export 20251214T040016_1842_99aea457

快捷方式:
  # 查看最新会话
  python simple_session_viewer.py view

  # 列出最近会话
  python simple_session_viewer.py list
""")

if __name__ == "__main__":
    asyncio.run(main())