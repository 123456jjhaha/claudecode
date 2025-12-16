"""
测试新的子实例 session_id 追踪功能
"""

import asyncio
from src import AgentSystem

async def test_new_subinstance():
    """测试新的子实例功能"""
    print("=" * 80)
    print("测试新的子实例 session_id 追踪")
    print("=" * 80)

    # 创建主 Agent
    agent = AgentSystem("demo_agent", instances_root="C:/Users/Lenovo/Desktop/test2/claudecode/instances")
    await agent.initialize()

    try:
        # 执行一个需要调用子实例的任务
        prompt = """
        请使用 calculator 工具计算 123 + 456，然后使用 file_analyzer 子实例分析 test_files/example.py 文件。
        """

        print(f"\n执行任务: {prompt[:50]}...")
        result = await agent.query_text(prompt)

        print(f"\n任务完成！")
        print(f"主会话 ID: {result.session_id}")
        print(f"结果长度: {len(result.result)} 字符")

        # 查看会话统计信息
        session_manager = agent.session_manager
        session = session_manager.get_session(result.session_id)

        statistics = session.get_statistics()
        print(f"\n统计信息:")
        print(f"  消息数: {statistics['num_messages']}")
        print(f"  工具调用数: {statistics['num_tool_calls']}")
        print(f"  子会话数: {len(statistics['subsessions'])}")

        # 显示子会话信息
        if statistics['subsessions']:
            print(f"\n✅ 成功记录的子会话:")
            for sub in statistics['subsessions']:
                print(f"  - {sub['session_id']}")
                print(f"    工具: {sub['tool_name']}")
                print(f"    调用ID: {sub['tool_use_id']}")
                print(f"    时间: {sub['timestamp']}")
        else:
            print("\n❌ 没有记录到子会话信息")

        # 检查消息内容中是否有 session_id
        messages = list(session.get_messages())
        print(f"\n📨 检查消息内容中的 session_id:")
        for msg in messages:
            if msg['message_type'] == "UserMessage":
                data = msg['data']
                if isinstance(data.get('content'), list):
                    for block in data['content']:
                        if block.get('type') == 'tool_result' and isinstance(block.get('content'), str):
                            content = block['content']
                            if 'SESSION_ID:' in content:
                                import re
                                match = re.search(r'<!--SESSION_ID:([^>]+)-->', content)
                                if match:
                                    print(f"  ✅ 找到 session_id: {match.group(1)}")
                                    break
                            if 'session_id' in content:
                                print(f"  ⚠️  发现旧格式 session_id")
                                break

        return result.session_id

    finally:
        agent.cleanup()

async def main():
    session_id = await test_new_subinstance()

    if session_id:
        print(f"\n🔍 检查会话目录: instances/demo_agent/sessions/{session_id[:20]}...")
        print(f"请查看该目录下的 statistics.json 文件确认 subsessions 字段")

if __name__ == "__main__":
    asyncio.run(main())