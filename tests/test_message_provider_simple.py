#!/usr/bin/env python3
"""
MessageProvider 简化测试脚本
"""

import asyncio
import json
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.session.provider import (
    MessageProvider,
    MessageFormatter,
    MessageReader,
    MessageMerger
)


async def test_message_formatter():
    """测试消息格式化器"""
    print("测试 MessageFormatter...")

    # 测试历史消息格式化
    historical_message = {
        "seq": 1,
        "timestamp": "2025-01-01T12:00:00",
        "message_type": "UserMessage",
        "data": {"content": "Hello, world!"}
    }

    normalized = MessageFormatter.normalize_historical_message(
        historical_message,
        instance_name="test_instance",
        session_id="test_session"
    )

    assert normalized is not None
    assert normalized['instance_name'] == "test_instance"
    assert normalized['session_id'] == "test_session"
    assert normalized['source'] == "historical"
    print("历史消息格式化测试通过")

    # 测试实时消息格式化
    realtime_event = {
        "event_type": "message_created",
        "seq": 2,
        "timestamp": "2025-01-01T12:01:00",
        "message_type": "AssistantMessage",
        "data": {"content": [{"type": "text", "text": "Hi there!"}]},
        "instance_name": "test_instance",
        "session_id": "test_session"
    }

    normalized = MessageFormatter.normalize_realtime_message(realtime_event)

    assert normalized is not None
    assert normalized['instance_name'] == "test_instance"
    assert normalized['session_id'] == "test_session"
    assert normalized['source'] == "realtime"
    assert 'received_at' in normalized
    print("实时消息格式化测试通过")


async def test_message_merger():
    """测试消息合并器"""
    print("\n测试 MessageMerger...")

    # 创建模拟的历史和实时消息流
    async def mock_historical_stream():
        messages = [
            {"seq": 0, "timestamp": "2025-01-01T12:00:00", "message_type": "SystemMessage", "source": "historical"},
            {"seq": 1, "timestamp": "2025-01-01T12:00:01", "message_type": "UserMessage", "source": "historical"},
        ]
        for msg in messages:
            yield msg

    async def mock_realtime_stream():
        messages = [
            {"seq": 2, "timestamp": "2025-01-01T12:00:02", "message_type": "AssistantMessage", "source": "realtime"},
            {"seq": 1, "timestamp": "2025-01-01T12:00:01", "message_type": "AssistantMessage", "source": "realtime"},  # 重复
        ]
        for msg in messages:
            yield msg

    merger = MessageMerger()
    merged_messages = []

    async for message in merger.merge_streams(
        historical_stream=mock_historical_stream(),
        realtime_stream=mock_realtime_stream(),
        strategy="historical_first"
    ):
        merged_messages.append(message)

    assert len(merged_messages) >= 2, "至少应该包含所有历史消息"
    print("历史优先合并测试通过")

    # 重置合并器
    merger.reset()

    # 测试去重功能
    seq_set = set()
    duplicate_found = False

    async for message in merger.merge_streams(
        historical_stream=mock_historical_stream(),
        realtime_stream=mock_realtime_stream(),
        strategy="historical_first"
    ):
        if message['seq'] in seq_set:
            duplicate_found = True
            break
        seq_set.add(message['seq'])

    assert not duplicate_found, "不应该有重复的消息"
    print("消息去重测试通过")


async def run_all_tests():
    """运行所有测试"""
    print("开始运行 MessageProvider 测试套件\n")

    try:
        await test_message_formatter()
        await test_message_merger()

        print("\n所有测试通过！")
        print("MessageProvider 实现验证成功")
        print("核心功能正常工作")

    except AssertionError as e:
        print(f"\n测试失败: {e}")
        raise
    except Exception as e:
        print(f"\n测试出错: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    # 运行测试
    asyncio.run(run_all_tests())