#!/usr/bin/env python3
"""
MessageProvider 使用示例

演示如何使用统一消息提供器获取历史和实时消息。
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.session import MessageProvider
from src.session.streaming import MessageBus


async def demo_basic_usage():
    """基础使用示例"""
    print("=== MessageProvider 基础使用示例 ===\n")

    # 实例和会话信息
    instance_name = "demo_agent"
    session_id = "20251216T210032_7347_8e02a38f"

    # 创建 MessageBus（可选，用于实时消息）
    message_bus = None
    try:
        message_bus = MessageBus.from_config()
        await message_bus.connect()
        print("✅ MessageBus 连接成功")
    except Exception as e:
        print(f"⚠️  MessageBus 连接失败: {e}")
        print("   将仅使用历史消息")

    try:
        # 创建 MessageProvider（使用上下文管理器）
        async with MessageProvider(
            instance_name=instance_name,
            session_id=session_id,
            message_bus=message_bus
        ) as provider:
            print(f"✅ MessageProvider 初始化成功")
            print(f"   实例: {instance_name}")
            print(f"   会话: {session_id}")
            print(f"   连接状态: {provider.is_connected}")
            print(f"   实时消息可用: {provider.is_realtime_available}\n")

            # 验证会话
            if not await provider.validate_session():
                print("❌ 会话不存在，请检查实例名称和会话 ID")
                return

            # 获取会话信息
            session_info = await provider.get_session_info()
            print(f"📊 会话信息:")
            print(f"   总消息数: {session_info.get('total_messages', 0)}")
            print(f"   最新序号: {session_info.get('latest_seq', -1)}")
            print(f"   会话状态: {session_info.get('metadata', {}).get('status', 'unknown')}\n")

            # 演示1: 获取完整消息流（历史 + 实时）
            print("🔍 演示1: 获取最近5条消息")
            message_count = 0
            async for message in provider.get_messages(max_messages=5):
                message_count += 1
                print(f"   [{message['seq']:3d}] {message['message_type']:20s} @ {message['timestamp'][:19]}")
                print(f"        来源: {message['source']:10s}")

                # 显示消息内容摘要
                if message['message_type'] == 'AssistantMessage':
                    content = message['data'].get('content', [])
                    text_parts = [c.get('text', '') for c in content if c.get('type') == 'text']
                    if text_parts:
                        text = ' '.join(text_parts)[:50]
                        print(f"        内容: {text}...")

                print()

            if message_count == 0:
                print("   (没有找到消息)")

            # 演示2: 仅获取历史消息
            print("📚 演示2: 获取历史消息（最多3条）")
            async for message in provider.get_historical_messages(limit=3):
                print(f"   [历史] {message['message_type']} - 序号: {message['seq']}")

            # 演示3: 实时消息订阅（如果有 MessageBus）
            if provider.is_realtime_available:
                print("\n📡 演示3: 订阅实时消息（等待5秒）")

                try:
                    # 设置超时，避免无限等待
                    async def wait_for_realtime():
                        count = 0
                        async for message in provider.subscribe_realtime_messages():
                            count += 1
                            print(f"   [实时] {message['message_type']} @ {message['received_at'][:19]}")
                            if count >= 3:  # 最多显示3条
                                break

                    # 等待5秒
                    await asyncio.wait_for(wait_for_realtime(), timeout=5.0)

                except asyncio.TimeoutError:
                    print("   (5秒内没有收到新的实时消息)")

            # 演示4: 消息类型过滤
            print("\n🎯 演示4: 消息类型过滤（仅 AssistantMessage 和 UserMessage）")
            async for message in provider.get_messages(
                from_beginning=True,
                include_realtime=False,  # 仅历史消息
                message_types=["AssistantMessage", "UserMessage"],
                max_messages=3
            ):
                print(f"   [{message['seq']:3d}] {message['message_type']}")

            # 显示统计信息
            print("\n📈 统计信息:")
            stats = provider.get_statistics()
            print(f"   已处理消息数: {stats['merger']['seen_sequences_count']}")
            print(f"   活跃订阅数: {len(stats.get('realtime_subscriptions', []))}")

    except Exception as e:
        print(f"❌ 示例执行失败: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # 清理 MessageBus
        if message_bus:
            await message_bus.close()
            print("\n🔚 MessageBus 已关闭")


async def demo_advanced_usage():
    """高级使用示例"""
    print("\n=== MessageProvider 高级使用示例 ===\n")

    # 不同的合并策略
    instance_name = "demo_agent"
    session_id = "20251216T210032_7347_8e02a38f"

    try:
        provider = MessageProvider(instance_name, session_id)
        await provider.connect()

        if not await provider.validate_session():
            print("❌ 会话不存在")
            return

        print("🔀 测试不同的合并策略:")

        # 历史优先策略
        print("\n1. 历史优先策略 (historical_first)")
        async for message in provider.get_messages(
            from_beginning=True,
            include_realtime=False,  # 禁用实时消息以便演示
            merge_strategy="historical_first",
            max_messages=2
        ):
            print(f"   [{message['seq']}] {message['message_type']} - {message['source']}")

        # 交错合并策略
        print("\n2. 交错合并策略 (interleaved)")
        async for message in provider.get_messages(
            from_beginning=True,
            include_realtime=False,  # 禁用实时消息以便演示
            merge_strategy="interleaved",
            max_messages=2
        ):
            print(f"   [{message['seq']}] {message['message_type']} - {message['source']}")

        await provider.disconnect()

    except Exception as e:
        print(f"❌ 高级示例执行失败: {e}")


async def main():
    """主函数"""
    print("Claude Agent System - MessageProvider 演示\n")

    # 检查是否存在会话数据
    instances_root = Path("instances")
    demo_session = instances_root / "demo_agent" / "sessions" / "20251216T210032_7347_8e02a38f"

    if not demo_session.exists():
        print("⚠️  演示会话数据不存在")
        print(f"   期望路径: {demo_session}")
        print("\n请确保:")
        print("1. instances/demo_agent/sessions/ 目录存在")
        print("2. 包含有效的会话数据")
        print("3. 可以通过运行 AgentSystem 生成一些测试数据")
        return

    # 运行基础示例
    await demo_basic_usage()

    # 运行高级示例
    await demo_advanced_usage()

    print("\n✅ 演示完成!")


if __name__ == "__main__":
    # 运行演示
    asyncio.run(main())