"""
测试会话记录和子实例 session_id 追踪功能
"""

import asyncio
from pathlib import Path
from src import AgentSystem


async def test_sub_instance_recording():
    """测试子实例会话记录"""
    print("=" * 80)
    print("测试 1: 子实例会话记录")
    print("=" * 80)

    # 创建主 Agent（假设 demo_agent 配置了子实例）
    agent = AgentSystem("demo_agent",instances_root="C:/Users/Lenovo/Desktop/test2/claudecode/instances")
    await agent.initialize()

    try:
        # 执行一个需要调用子实例的任务
        prompt = """
        请使用 file_analyzer 子实例分析 test_files/ 目录下的文件。
        分析每个文件的类型、大小和内容摘要。
        """

        print("\n执行任务...")
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
        print(f"  使用的工具: {list(statistics['tools_used'].keys())}")
        print(f"  子会话数: {len(statistics['subsessions'])}")

        # 显示子会话信息
        if statistics['subsessions']:
            print(f"\n子会话列表:")
            for sub in statistics['subsessions']:
                print(f"  - {sub['session_id']} (工具: {sub['tool_name']})")

        return result.session_id

    finally:
        agent.cleanup()


async def test_session_tree(session_id: str):
    """测试会话树查看功能"""
    print("\n" + "=" * 80)
    print("测试 2: 会话树查看")
    print("=" * 80)

    instance_path = Path("instances/demo_agent")
    from src.session_manager import SessionManager

    session_manager = SessionManager(instance_path)

    # 获取会话树
    tree = session_manager.get_session_tree(session_id)

    print("\n会话树结构:")
    tree_str = session_manager.print_session_tree(session_id)
    print(tree_str)


async def test_merged_messages(session_id: str):
    """测试整合消息查看功能"""
    print("\n" + "=" * 80)
    print("测试 3: 整合消息查看")
    print("=" * 80)

    instance_path = Path("instances/demo_agent")
    from src.session_manager import SessionManager

    session_manager = SessionManager(instance_path)
    session = session_manager.get_session(session_id)

    # 获取整合消息
    print("\n整合后的消息（包含子会话）:")
    count = 0
    for msg in session.get_merged_messages(include_subsessions=True):
        indent = "  " * msg['indent_level']
        print(f"{indent}[{msg['seq']}] {msg['message_type']} @ {msg['session_id'][:20]}...")

        count += 1
        if count > 20:  # 只显示前20条
            print(f"{indent}... (还有更多消息)")
            break


async def test_export_messages(session_id: str):
    """测试消息导出功能"""
    print("\n" + "=" * 80)
    print("测试 4: 消息导出")
    print("=" * 80)

    instance_path = Path("instances/demo_agent")
    from src.session_manager import SessionManager

    session_manager = SessionManager(instance_path)

    # 导出为 JSON
    output_dir = Path("test_files")
    output_dir.mkdir(exist_ok=True)

    json_file = output_dir / f"session_{session_id}_merged.json"
    text_file = output_dir / f"session_{session_id}_merged.txt"

    print(f"\n导出整合消息到:")
    print(f"  JSON: {json_file}")
    print(f"  TEXT: {text_file}")

    session_manager.export_merged_messages(
        session_id,
        json_file,
        format="json",
        include_subsessions=True
    )

    session_manager.export_merged_messages(
        session_id,
        text_file,
        format="text",
        include_subsessions=True
    )

    print(f"\n✅ 导出完成!")


async def main():
    """主测试流程"""
    print("\n🧪 开始测试会话记录和子实例追踪功能\n")

    # 测试 1: 子实例记录
    session_id = await test_sub_instance_recording()

    # 测试 2: 会话树
    await test_session_tree(session_id)

    # 测试 3: 整合消息
    await test_merged_messages(session_id)

    # 测试 4: 导出消息
    await test_export_messages(session_id)

    print("\n" + "=" * 80)
    print("✅ 所有测试完成!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
