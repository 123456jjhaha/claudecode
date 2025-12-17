"""
简单的Demo Agent测试 - 集成消息记录机制
"""

import asyncio
import sys
import os
from typing import AsyncIterator
from pathlib import Path

# 添加src到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src import AgentSystem
from src.session.streaming import MessageBus
from src.session.query.tree_builder import SessionTreeBuilder
from src.session.query.session_query import list_sessions


async def message_listener(message_bus: MessageBus, instance_name: str):
    """监听实时消息的示例函数"""
    print(f"\n[监听器] 开始监听 {instance_name} 的实时消息...")

    async for message in message_bus.subscribe(f"agent:{instance_name}:messages"):
        msg_type = message.get("type", "unknown")
        session_id = message.get("session_id", "N/A")

        if msg_type == "user_message":
            content = message.get("content", "")[:50]
            print(f"[监听器] 用户消息 [{session_id[:8]}...]: {content}...")
        elif msg_type == "assistant_message":
            content = message.get("content", "")[:50]
            print(f"[监听器] 助手回复 [{session_id[:8]}...]: {content}...")
        elif msg_type == "tool_call":
            tool_name = message.get("tool_name", "unknown")
            print(f"[监听器] 工具调用 [{session_id[:8]}...]: {tool_name}")


async def demonstrate_session_features(agent: AgentSystem, result) -> str:
    """演示会话记录功能"""
    print("\n[会话] 会话功能演示")
    print("-" * 30)

    session_id = result.session_id
    print(f"[会话] 会话ID: {session_id}")

    # 获取会话信息
    session = agent.session_manager.get_session(session_id)
    if session:
        print(f"[会话] 消息总数: {session._message_count}")

        # 获取会话统计
        stats = session.get_statistics()
        duration_ms = stats.get('total_duration_ms', 0)
        duration_sec = duration_ms / 1000 if duration_ms > 0 else 0
        print(f"[会话] 会话时长: {duration_sec:.2f}秒")

        print(f"[会话] 会话统计:")
        print(f"   - 总消息数: {stats.get('num_messages', 0)}")
        print(f"   - 工具调用数: {stats.get('num_tool_calls', 0)}")
        print(f"   - 对话轮数: {stats.get('num_turns', 0)}")
        print(f"   - 总时长: {duration_ms}ms")
        if stats.get('cost_usd'):
            print(f"   - 成本: ${stats.get('cost_usd'):.4f}")

        # 显示会话树（使用 SessionTreeBuilder）
        try:
            tree_builder = SessionTreeBuilder(instances_root=Path("instances"))
            tree = await tree_builder.build_tree(
                session_id=session_id,
                instance_name="demo_agent",
                include_messages=False,
                max_depth=2
            )
            print(f"[会话] 会话树结构:")
            print(f"   根节点: {tree['session_id'][:8]}... ({tree['instance_name']})")
            for child in tree.get('subsessions', []):
                print(f"   ├─ 子会话: {child['session_id'][:8]}... ({child['instance_name']})")
                for grandchild in child.get('subsessions', []):
                    print(f"   │  └─ 子子会话: {grandchild['session_id'][:8]}... ({grandchild['instance_name']})")
        except Exception as e:
            print(f"[会话] 构建会话树失败: {e}")

    return session_id


async def main():
    print("=" * 60)
    print("Demo Agent 测试 - 集成消息记录机制")
    print("=" * 60)

    # 1. 创建 MessageBus（全局单例）
    print("\n[1] 初始化 MessageBus...")
    message_bus = MessageBus.from_config()
    connected = await message_bus.connect()
    print(f"[1] MessageBus 连接状态: {'已连接' if connected else '未连接（降级模式）'}")

    try:
        # 2. 创建 Agent 实例（共享 MessageBus）
        print("\n[2] 初始化 Agent...")
        agent = AgentSystem(
            "C:/Users/Lenovo/Desktop/test2/claudecode/instances/demo_agent",
            message_bus=message_bus
        )
        await agent.initialize()

        print(f"[2] Agent名称: {agent.agent_name}")
        print(f"[2] 工具数量: {agent.tools_count}")
        print(f"[2] 子实例数量: {agent.sub_instances_count}")

        # 3. 启动消息监听器（后台任务）
        print("\n[3] 启动实时消息监听...")
        listener_task = asyncio.create_task(
            message_listener(message_bus, agent.agent_name)
        )

        # 4. 执行基础查询
        print("\n[4] Executing basic query...")
        result1 = await agent.query_text("Hello, please briefly introduce yourself")
        print(f"[4] Query result: {result1.result[:100]}...")

        # 5. 演示会话功能
        session_id = await demonstrate_session_features(agent, result1)

        # 6. Resume 对话（继续之前的会话）
        print("\n[6] Resume 对话...")
        result2 = await agent.query_text(
            "你能帮我计算一下 123 + 456 等于多少吗？",
            resume_session_id=session_id
        )
        print(f"[6] 计算结果: {result2.result[:100]}...")

        # 7. 测试子实例调用（这会产生子会话）
        print("\n[7] 测试子实例调用...")
        result3 = await agent.query_text(
            "使用file_analyzer子实例分析 instances/demo_agent/config.yaml 文件"
        )
        print(f"[7] 分析结果: {result3.result[:200]}...")

        # 8. 展示完整的会话树
        print("\n[8] 完整会话树结构:")
        try:
            tree_builder = SessionTreeBuilder(instances_root=Path("instances"))
            tree = await tree_builder.build_tree(
                session_id=session_id,
                instance_name="demo_agent",
                include_messages=False,
                max_depth=3
            )
            await print_session_tree(tree, agent.session_manager)
        except Exception as e:
            print(f"[8] 构建完整会话树失败: {e}")

        # 9. 查询最近的会话
        print("\n[9] 最近的会话记录:")
        try:
            recent_sessions = list_sessions(
                instance_name="demo_agent",
                instances_root=Path("instances"),
                limit=5
            )
            for i, session_info in enumerate(recent_sessions, 1):
                print(f"   {i}. {session_info['session_id'][:16]}... "
                      f"(状态: {session_info.get('status', 'N/A')})")
        except Exception as e:
            print(f"[9] 查询最近会话失败: {e}")

        print("\n[测试完成!")

        # 取消监听器任务
        listener_task.cancel()
        try:
            await listener_task
        except asyncio.CancelledError:
            pass

    finally:
        # 清理资源
        print("\n[清理资源...")
        agent.cleanup()
        await message_bus.close()
        print("[资源清理完成")


async def print_session_tree(tree: dict, session_manager, level: int = 0):
    """递归打印会话树"""
    indent = "   " * level

    session_id = tree['session_id']
    instance_name = tree.get('instance_name', 'unknown')
    depth = tree.get('depth', 0)

    # 尝试获取会话信息
    try:
        session = session_manager.get_session(session_id)
        if session:
            msg_count = session._message_count
            # 获取时长信息
            stats = session.get_statistics()
            duration_ms = stats.get('total_duration_ms', 0)
            duration_sec = duration_ms / 1000 if duration_ms > 0 else 0
            print(f"{indent}[会话] {session_id[:16]}... ({instance_name}, depth={depth}, {msg_count} 条消息, {duration_sec:.1f}s)")
        else:
            print(f"{indent}[会话] {session_id[:16]}... ({instance_name}, depth={depth}, 会话不存在)")
    except Exception as e:
        print(f"{indent}[会话] {session_id[:16]}... ({instance_name}, depth={depth}, 错误: {e})")

    # 递归打印子会话（注意：key 是 'subsessions' 不是 'children'）
    for child in tree.get('subsessions', []):
        await print_session_tree(child, session_manager, level + 1)


if __name__ == "__main__":
    asyncio.run(main())