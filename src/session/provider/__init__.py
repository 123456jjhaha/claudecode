"""
统一消息提供器模块

提供统一的消息访问接口，自动处理历史消息和实时消息的合并。
"""

from .message_formatter import MessageFormatter
from .message_merger import MessageMerger
from .message_provider import MessageProvider
from .message_reader import MessageReader
from .realtime_subscriber import RealtimeSubscriber

__all__ = [
    'MessageProvider',      # 主要的统一接口
    'MessageFormatter',     # 消息格式化器
    'MessageMerger',        # 消息合并器
    'MessageReader',        # 历史消息读取器
    'RealtimeSubscriber',   # 实时消息订阅器
]

# 版本信息
__version__ = '1.0.0'

# 模块说明
"""
MessageProvider 统一消息提供器

这个模块提供了一套完整的解决方案来处理 Claude Agent System 中的消息访问问题：

核心类：
- MessageProvider: 主要接口，提供统一的消息访问
- MessageReader: 异步读取历史消息
- RealtimeSubscriber: 订阅实时消息
- MessageMerger: 智能合并历史和实时消息
- MessageFormatter: 统一消息格式

使用示例：

```python
import asyncio
from src.session.provider import MessageProvider
from src.session.streaming import MessageBus

async def main():
    # 创建 MessageBus（可选）
    message_bus = MessageBus.from_config()
    await message_bus.connect()

    try:
        # 使用上下文管理器自动处理连接
        async with MessageProvider(
            instance_name="demo_agent",
            session_id="20251216T210032_7347_8e02a38f",
            message_bus=message_bus
        ) as provider:

            # 获取完整消息流（历史 + 实时）
            print("=== 完整消息流 ===")
            async for message in provider.get_messages():
                print(f"[{message['seq']}] {message['message_type']} @ {message['timestamp']}")
                print(f"  来源: {message['source']}")
                if message['source'] == 'realtime':
                    print(f"  接收时间: {message['received_at']}")

            # 仅获取历史消息
            print("\n=== 历史消息 ===")
            async for message in provider.get_historical_messages(limit=10):
                print(f"[历史] {message['message_type']}")

            # 仅订阅实时消息
            print("\n=== 实时消息 ===")
            async for message in provider.subscribe_realtime_messages():
                print(f"[实时] {message['message_type']}")

    finally:
        await message_bus.close()

# 运行示例
asyncio.run(main())
```

高级功能：

1. **消息类型过滤**
```python
# 只获取对话消息
async for message in provider.get_messages(
    message_types=["AssistantMessage", "UserMessage"]
):
    # 处理消息
    pass
```

2. **不同的合并策略**
```python
# 交错合并（按时间戳）
async for message in provider.get_messages(
    merge_strategy="interleaved"
):
    pass

# 实时优先
async for message in provider.get_messages(
    merge_strategy="realtime_priority"
):
    pass
```

3. **批量处理**
```python
async def process_in_batches(provider, batch_size=50):
    batch = []
    async for message in provider.get_messages():
        batch.append(message)

        if len(batch) >= batch_size:
            await process_batch(batch)
            batch = []

    if batch:  # 处理最后一批
        await process_batch(batch)
```

4. **会话信息获取**
```python
session_info = await provider.get_session_info()
print(f"总消息数: {session_info['total_messages']}")
print(f"最新序号: {session_info['latest_seq']}")
```

5. **统计和监控**
```python
stats = provider.get_statistics()
print(f"连接状态: {stats['connected']}")
print(f"实时消息可用: {stats['realtime_available']}")
print(f"已处理消息数: {stats['merger']['seen_sequences_count']}")
```

优势：
- **统一接口**: 一个API处理所有消息类型
- **自动合并**: 智能处理历史和实时消息的合并
- **格式统一**: 消除不同来源的消息格式差异
- **高性能**: 异步流式处理，支持大量消息
- **容错性**: 完善的错误处理和降级策略
- **易于使用**: 简单直观的API设计

这个模块为前端开发提供了强大而简单的消息访问能力，解决了历史消息查询和实时消息订阅分离的问题。
"""