# MessageProvider 统一消息提供器

## 概述

`MessageProvider` 是 Claude Agent System 中统一的消息访问接口，解决了历史消息查询和实时消息订阅分离的问题。通过 `MessageProvider`，前端开发者可以使用一个简单的 API 获取完整的对话历史，并实时接收新消息。

## 核心特性

- **统一接口**: 一个 API 同时处理历史消息和实时消息
- **格式统一**: 所有消息使用相同的数据格式，无论来源
- **智能合并**: 自动处理消息去重和时间排序
- **高性能**: 异步流式处理，支持大量消息
- **灵活过滤**: 支持按消息类型、时间范围等条件过滤
- **容错设计**: 完善的错误处理和降级策略

## 快速开始

### 基础使用

```python
import asyncio
from src.session.provider import MessageProvider
from src.session.streaming import MessageBus

async def main():
    # 创建 MessageBus（可选，用于实时消息）
    message_bus = MessageBus.from_config()
    await message_bus.connect()

    try:
        # 创建 MessageProvider
        provider = MessageProvider(
            instance_name="demo_agent",
            session_id="20251216T210032_7347_8e02a38f",
            message_bus=message_bus
        )
        await provider.connect()

        # 获取完整消息流（历史 + 实时）
        async for message in provider.get_messages():
            print(f"[{message['seq']}] {message['message_type']} @ {message['timestamp']}")
            print(f"  来源: {message['source']}")  # 'historical' 或 'realtime'

        # 清理
        await provider.disconnect()

    finally:
        await message_bus.close()

asyncio.run(main())
```

### 使用上下文管理器（推荐）

```python
async def main():
    message_bus = MessageBus.from_config()
    await message_bus.connect()

    try:
        # 自动处理连接和清理
        async with MessageProvider(
            instance_name="demo_agent",
            session_id="20251216T210032_7347_8e02a38f",
            message_bus=message_bus
        ) as provider:

            # 获取最近 10 条消息
            async for message in provider.get_messages(max_messages=10):
                print(f"[{message['seq']}] {message['message_type']}")

    finally:
        await message_bus.close()
```

## API 参考

### MessageProvider 类

#### 初始化

```python
MessageProvider(
    instance_name: str,
    session_id: str,
    instances_root: Optional[Path] = None,
    message_bus=None,
    auto_connect: bool = True,
    buffer_size: int = 100
)
```

**参数**:
- `instance_name`: 实例名称
- `session_id`: 会话 ID
- `instances_root`: 实例根目录路径，默认为 "instances"
- `message_bus`: MessageBus 实例（可选），用于实时消息
- `auto_connect`: 是否自动连接 MessageBus
- `buffer_size`: 内部缓冲区大小

#### 主要方法

##### get_messages()

获取完整消息流（历史 + 实时）

```python
async def get_messages(
    self,
    from_beginning: bool = True,
    include_realtime: bool = True,
    message_types: Optional[List[str]] = None,
    merge_strategy: str = "historical_first",
    max_messages: Optional[int] = None
) -> AsyncIterator[Dict[str, Any]]
```

**参数**:
- `from_beginning`: 是否从历史消息开始
- `include_realtime`: 是否包含实时消息
- `message_types`: 过滤的消息类型列表
- `merge_strategy`: 合并策略（"historical_first", "interleaved", "realtime_priority"）
- `max_messages`: 最大消息数量限制

**示例**:
```python
# 获取所有对话消息
async for message in provider.get_messages(
    message_types=["AssistantMessage", "UserMessage"]
):
    process_message(message)

# 仅获取最近 50 条消息
async for message in provider.get_messages(max_messages=50):
    print(message['data'])
```

##### get_historical_messages()

仅获取历史消息

```python
async def get_historical_messages(
    self,
    message_types: Optional[List[str]] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None
) -> AsyncIterator[Dict[str, Any]]
```

**示例**:
```python
# 分页获取历史消息
async for message in provider.get_historical_messages(
    limit=20,
    offset=100  # 跳过前100条
):
    print(message['seq'])
```

##### subscribe_realtime_messages()

仅订阅实时消息

```python
async def subscribe_realtime_messages(
    self,
    message_types: Optional[List[str]] = None,
    include_heartbeat: bool = False
) -> AsyncIterator[Dict[str, Any]]
```

**示例**:
```python
# 实时监听新消息
async for message in provider.subscribe_realtime_messages():
    if message['message_type'] == 'AssistantMessage':
        print(f"新回复: {message['data']['content'][0]['text']}")
```

## 消息格式

所有消息都使用统一的格式：

```python
{
    # 基础元数据
    'seq': int,                              # 消息序号
    'timestamp': str,                        # ISO 8601 时间戳
    'message_type': str,                     # 消息类型

    # 会话关联信息
    'instance_name': str,                    # 实例名称
    'session_id': str,                       # 会话 ID
    'parent_session_id': Optional[str],      # 父会话 ID
    'depth': int,                            # 会话深度

    # 消息内容
    'data': {...},                           # 序列化后的消息内容

    # 来源标记
    'source': 'historical' | 'realtime',     # 消息来源
    'received_at': str,                      # 接收时间（仅实时消息）
}
```

### 消息类型

- `SystemMessage`: 系统消息
- `UserMessage`: 用户消息
- `AssistantMessage`: AI 助手消息
- `ResultMessage`: 结果消息
- `ToolResultMessage`: 工具结果消息

## 合并策略

### historical_first（默认）
先发送所有历史消息，然后实时消息。

```python
async for message in provider.get_messages(merge_strategy="historical_first"):
    # 先看到完整历史，然后实时更新
```

### interleaved
按时间戳交错合并历史和实时消息。

```python
async for message in provider.get_messages(merge_strategy="interleaved"):
    # 真正的时间顺序
```

### realtime_priority
优先实时消息，历史消息作为补充。

```python
async for message in provider.get_messages(merge_strategy="realtime_priority"):
    # 实时消息优先显示
```

## 高级用法

### 消息过滤

```python
# 只获取特定类型的消息
async for message in provider.get_messages(
    message_types=["AssistantMessage", "UserMessage"]
):
    pass

# 只获取最近的对话
async for message in provider.get_messages(
    message_types=["AssistantMessage", "UserMessage"],
    max_messages=10
):
    pass
```

### 批量处理

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

await process_in_batches(provider)
```

### 会话信息

```python
# 获取会话基本信息
session_info = await provider.get_session_info()
print(f"总消息数: {session_info['total_messages']}")
print(f"最新序号: {session_info['latest_seq']}")

# 检查会话是否存在
if await provider.validate_session():
    print("会话存在")
else:
    print("会话不存在")
```

### 统计和监控

```python
# 获取统计信息
stats = provider.get_statistics()
print(f"连接状态: {stats['connected']}")
print(f"实时消息可用: {stats['realtime_available']}")
print(f"已处理消息数: {stats['merger']['seen_sequences_count']}")

# 获取消息总数
total_count = await provider.get_message_count()
print(f"消息总数: {total_count}")

# 获取特定类型的消息数量
user_msg_count = await provider.get_message_count(
    message_types=["UserMessage"]
)
```

## 错误处理

### 降级策略

当 MessageBus 不可用时，`MessageProvider` 会自动降级到仅历史消息模式：

```python
provider = MessageProvider("demo_agent", "session_id")
await provider.connect()

if provider.is_realtime_available:
    print("实时消息可用")
else:
    print("仅使用历史消息")
```

### 异常处理

```python
try:
    async with MessageProvider("demo_agent", "session_id") as provider:
        async for message in provider.get_messages():
            process_message(message)

except ValueError as e:
    print(f"参数错误: {e}")
except RuntimeError as e:
    print(f"连接错误: {e}")
except Exception as e:
    print(f"未知错误: {e}")
```

## 性能考虑

### 内存使用

- 使用流式处理，避免一次性加载所有消息到内存
- 设置合适的 `buffer_size` 控制内存使用
- 使用 `max_messages` 限制处理的消息数量

### I/O 优化

- 历史消息使用异步文件读取
- 实时消息使用 Redis Pub/Sub
- 支持批量处理减少网络开销

### 示例：高性能处理

```python
# 使用缓冲区和批量处理
provider = MessageProvider(
    "demo_agent",
    "session_id",
    buffer_size=1000  # 更大的缓冲区
)

async def high_performance_processing():
    batch = []
    async for message in provider.get_messages():
        batch.append(message)

        if len(batch) >= 100:  # 批量处理
            await process_batch(batch)
            batch = []

        if len(batch) >= 1000:  # 限制内存使用
            await process_batch(batch)
            batch.clear()
```

## 与现有 API 的兼容性

`MessageProvider` 是对现有 API 的增强，不会破坏现有功能：

```python
# 现有的查询方式仍然可用
from src.session.query import get_session_messages

# 新的统一方式
from src.session.provider import MessageProvider

# 两者可以并存使用
```

## 最佳实践

1. **使用上下文管理器**: 自动处理连接和清理
2. **合理设置缓冲区**: 根据消息量调整 `buffer_size`
3. **过滤不必要的消息**: 使用 `message_types` 参数
4. **限制消息数量**: 使用 `max_messages` 避免内存问题
5. **处理连接失败**: 检查 `is_connected` 和 `is_realtime_available`
6. **优雅降级**: 在实时消息不可用时仍可使用历史消息

## 故障排除

### 常见问题

1. **会话不存在**
   ```
   解决方案: 检查 instance_name 和 session_id 是否正确
   ```

2. **MessageBus 连接失败**
   ```
   解决方案: 检查 Redis 服务是否运行，配置是否正确
   ```

3. **消息文件损坏**
   ```
   解决方案: 检查 messages.jsonl 文件格式，删除损坏的行
   ```

4. **性能问题**
   ```
   解决方案: 减少缓冲区大小，使用消息过滤，限制消息数量
   ```

### 调试技巧

```python
# 启用详细日志
import logging
logging.basicConfig(level=logging.DEBUG)

# 检查会话状态
provider = MessageProvider("demo_agent", "session_id")
await provider.connect()
print(provider.get_statistics())

# 检查消息格式
async for message in provider.get_messages(max_messages=1):
    import json
    print(json.dumps(message, indent=2))
```

## 总结

`MessageProvider` 提供了一个强大而简单的接口来处理 Claude Agent System 中的消息访问。通过统一的 API、智能的消息合并和完善的错误处理，它大大简化了前端开发工作，同时保持了高性能和可靠性。