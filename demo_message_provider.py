#!/usr/bin/env python3
"""
MessageProvider 演示脚本

演示如何使用统一消息提供器。
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from src.session.provider import MessageProvider


async def demo():
    """演示 MessageProvider 的基本使用"""
    print("MessageProvider 演示\n")

    # 检查是否有可用的会话
    instances_root = Path("instances")
    demo_session = instances_root / "demo_agent" / "sessions"

    if not demo_session.exists():
        print("没有找到演示会话数据")
        print("请先运行 AgentSystem 生成一些会话数据")
        return

    # 列出可用的会话
    sessions = list(demo_session.glob("*"))
    if not sessions:
        print(f"没有找到会话数据在 {demo_session}")
        return

    # 使用第一个会话进行演示
    session_id = sessions[0].name
    instance_name = "demo_agent"

    print(f"使用会话: {instance_name} / {session_id}\n")

    try:
        # 创建 MessageProvider
        async with MessageProvider(
            instance_name=instance_name,
            session_id=session_id
        ) as provider:

            # 检查连接状态
            print(f"连接状态: {provider.is_connected}")
            print(f"实时消息可用: {provider.is_realtime_available}")

            # 获取会话信息
            session_info = await provider.get_session_info()
            print(f"总消息数: {session_info.get('total_messages', 0)}")
            print(f"最新序号: {session_info.get('latest_seq', -1)}")

            # 演示获取消息
            print("\n最近的消息:")
            message_count = 0
            async for message in provider.get_messages(max_messages=5):
                message_count += 1
                print(f"[{message['seq']:3d}] {message['message_type']:20s} @ {message['timestamp'][:19]}")
                print(f"        来源: {message['source']}")

                # 显示简单的消息内容
                if message['message_type'] == 'UserMessage':
                    content = message['data'].get('content', '...')
                    print(f"        用户: {str(content)[:50]}...")
                elif message['message_type'] == 'AssistantMessage':
                    content_list = message['data'].get('content', [])
                    if content_list:
                        text_parts = [c.get('text', '') for c in content_list if c.get('type') == 'text']
                        if text_parts:
                            text = ' '.join(text_parts)[:50]
                            print(f"        助手: {text}...")
                print()

            if message_count == 0:
                print("(没有找到消息)")

            # 演示消息类型过滤
            print("\n用户和助手消息:")
            async for message in provider.get_messages(
                from_beginning=True,
                include_realtime=False,
                message_types=["UserMessage", "AssistantMessage"],
                max_messages=3
            ):
                print(f"[{message['seq']:3d}] {message['message_type']}")

            # 显示统计信息
            print(f"\n统计信息:")
            stats = provider.get_statistics()
            print(f"  已处理消息数: {stats['merger']['seen_sequences_count']}")
            print(f"  连接状态: {stats['connected']}")
            print(f"  实时消息: {stats['realtime_available']}")

    except Exception as e:
        print(f"演示过程中出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(demo())