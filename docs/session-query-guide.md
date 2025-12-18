# SessionQuery 完整使用指南

SessionQuery 是 Claude Agent System 的统一会话查询与订阅服务，整合了会话查询、实时消息订阅和会话树构建功能。

## 🏗️ 架构概述

### 两大核心类设计

```
🏛️ 会话管理类（创建和管理）
├── SessionManager    # 会话工厂和管理器
│   ├── create_session()
│   ├── get_session()
│   ├── list_sessions()
│   └── cleanup_old_sessions()
└── Session          # 会话数据模型
    ├── record_message()
    ├── finalize()
    ├── get_messages()
    └── get_metadata()

🔍 会话查询类（查询和订阅）
└── SessionQuery      # 统一查询+订阅服务
    ├── 基础查询功能
    ├── 高级查询功能
    ├── 实时订阅功能
    └── 会话树构建功能
```

## 🚀 快速开始

### 基础查询

```python
from src.session import SessionQuery

# 创建查询实例
query = SessionQuery("demo_agent")

# 获取会话详情
details = query.get_session_details(
    session_id="20241218T140000_1000_parent123",
    include_messages=True,
    message_limit=50
)

# 列出会话
sessions = query.list_sessions(
    status="completed",
    limit=20
)

# 获取会话消息
messages = query.get_session_messages(
    session_id="20241218T140000_1000_parent123",
    message_types=["ToolUseMessage", "ResultMessage"],
    limit=100
)
```

### 高级查询

```python
# 搜索会话
results = query.search_sessions(
    query="文件分析",
    field="initial_prompt",
    limit=10
)

# 获取统计摘要
stats = query.get_statistics_summary(recent_days=7)
print(f"总会话数: {stats['total_sessions']}")
print(f"完成率: {stats['completed_sessions'] / stats['total_sessions']:.2%}")
print(f"平均耗时: {stats['avg_duration_ms']}ms")

# 导出会话
query.export_session(
    session_id="20241218T140000_1000_parent123",
    output_file=Path("session_export.json"),
    format="json",
    include_messages=True
)
```

### 实时消息订阅

```python
import asyncio
from src.session import MessageBus, SessionQuery

async def main():
    # 创建 MessageBus
    message_bus = MessageBus.from_config()
    await message_bus.connect()

    try:
        # 创建查询实例
        query = SessionQuery("demo_agent", message_bus=message_bus)

        # 开始订阅
        await query.subscribe(
            session_id="parent_session_id",
            on_parent_message=lambda msg: print(
                f"[父消息] {msg.get('message_type', 'unknown')}"
            ),
            on_child_message=lambda child_id, instance, msg: print(
                f"[子消息-{instance}] {msg.get('message_type', 'unknown')}"
            ),
            on_child_started=lambda child_id, instance: print(
                f"🔔 子实例启动: {child_id} ({instance})"
            )
        )

        # 保持订阅运行
        print("订阅已启动，等待消息...")
        await query.wait()

    finally:
        await query.stop()
        await message_bus.close()

asyncio.run(main())
```

### 会话树构建

```python
import asyncio
from src.session import SessionQuery

async def main():
    query = SessionQuery("demo_agent")

    # 构建会话树（递归获取父子关系）
    tree = await query.build_session_tree(
        session_id="parent_session_id",
        include_messages=False,  # 只获取结构，不包括消息内容
        max_depth=5
    )

    # 展平为列表
    flat_list = query.flatten_tree(tree)

    # 分析会话关系
    print(f"总会话数: {len(flat_list)}")
    for session in flat_list:
        indent = "  " * session.get('depth', 0)
        print(f"{indent}- {session['instance_name']} ({session['session_id'][:8]}...)")

asyncio.run(main())
```

## 📊 功能详解

### 1. 基础查询功能

#### `get_session_details()`
获取会话的完整信息，包括元数据、统计信息、消息和子会话。

**参数：**
- `session_id`: 会话 ID
- `include_messages`: 是否包含消息内容
- `message_limit`: 消息数量限制

**返回：**
```python
{
    "metadata": {
        "session_id": "...",
        "instance_name": "demo_agent",
        "start_time": "2024-12-18T14:00:00",
        "status": "completed",
        "depth": 0,
        "parent_session_id": null
    },
    "statistics": {
        "num_messages": 15,
        "num_tool_calls": 5,
        "total_duration_ms": 2500,
        "cost_usd": 0.025
    },
    "messages": [...],  # 如果 include_messages=True
    "subsessions": [...]  # 子会话信息
}
```

#### `list_sessions()`
列出会话，支持过滤和分页。

**参数：**
- `status`: 状态过滤 (`running/completed/failed`)
- `limit`: 返回数量限制
- `offset`: 偏移量

#### `get_session_messages()`
获取会话的详细消息列表。

**参数：**
- `session_id`: 会话 ID
- `message_types`: 过滤消息类型
- `limit`: 限制返回数量

### 2. 高级查询功能

#### `search_sessions()`
在会话中搜索关键词。

**参数：**
- `query`: 搜索关键词
- `field`: 搜索字段 (`initial_prompt/result`)
- `limit`: 返回数量限制

#### `get_statistics_summary()`
获取会话统计摘要。

**参数：**
- `recent_days`: 只统计最近N天的会话

**返回统计信息：**
- 总会话数、完成数、失败数
- 总消息数、工具调用数
- 总成本、平均耗时

#### `export_session()`
将会话导出为文件。

**支持格式：**
- `json`: 标准 JSON 格式
- `jsonl`: JSON Lines 格式
- `text`: 可读文本格式

### 3. 实时订阅功能

#### `subscribe()`
开始订阅会话消息，自动追踪子实例。

**回调函数：**
- `on_parent_message`: 父实例消息回调
- `on_child_message`: 子实例消息回调
- `on_child_started`: 子实例启动回调

**自动特性：**
- ✅ 自动订阅所有子实例
- ✅ 实时检测子实例启动
- ✅ 区分父子消息来源
- ✅ 支持多层嵌套

#### 生命周期管理
- `start()`: 启动订阅任务
- `stop()`: 停止所有订阅
- `wait()`: 等待订阅完成
- `is_running()`: 检查运行状态

### 4. 会话树构建功能

#### `build_session_tree()`
递归构建会话关系树。

**参数：**
- `session_id`: 根会话 ID
- `instance_name`: 实例名称（可选）
- `include_messages`: 是否包含消息
- `max_depth`: 最大递归深度

#### `flatten_tree()`
将树形结构展平为列表。

## 🎯 最佳实践

### 1. 性能优化

```python
# ✅ 推荐：限制消息数量
details = query.get_session_details(
    session_id="xxx",
    include_messages=True,
    message_limit=100  # 限制消息数量
)

# ✅ 推荐：使用分页
sessions = query.list_sessions(
    limit=50,
    offset=0
)
```

### 2. 内存管理

```python
# ✅ 推荐：及时清理订阅
async def with_subscription():
    query = SessionQuery("demo_agent", message_bus=message_bus)
    await query.subscribe(...)
    # ... 使用订阅 ...
    await query.stop()  # 确保清理

# ✅ 推荐：使用上下文管理器
class QueryContext:
    async def __aenter__(self):
        self.query = SessionQuery("demo_agent", message_bus=message_bus)
        await self.query.subscribe(...)
        return self.query

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.query.stop()
```

### 3. 错误处理

```python
# ✅ 推荐：异常处理
try:
    details = query.get_session_details("invalid_session_id")
except AgentSystemError as e:
    logger.error(f"获取会话详情失败: {e}")
    # 处理错误...
```

### 4. 批量操作

```python
# ✅ 推荐：批量导出
sessions = query.list_sessions(limit=100)
for session in sessions:
    session_id = session['session_id']
    output_file = Path(f"exports/{session_id}.json")
    query.export_session(session_id, output_file)
```

## 🔄 向后兼容

新架构完全向后兼容，旧的函数调用方式仍然有效：

```python
# 旧的函数调用（仍然有效）
from src.session.query.session_query import (
    get_session_details,
    list_sessions,
    search_sessions
)

# 使用旧 API
details = get_session_details("demo_agent", "session_id")
sessions = list_sessions("demo_agent", status="completed")
```

## 🔍 故障排除

### 常见问题

1. **订阅无消息**
   - 检查 MessageBus 连接状态
   - 确认会话 ID 正确
   - 检查 Redis 服务

2. **查询结果为空**
   - 确认实例名称正确
   - 检查会话目录权限
   - 验证会话 ID 格式

3. **性能问题**
   - 限制消息数量
   - 使用分页查询
   - 及时清理订阅

### 调试技巧

```python
# 启用调试日志
import logging
logging.getLogger('src.session').setLevel(logging.DEBUG)

# 检查会话存在性
try:
    query.get_session_details("session_id")
except AgentSystemError:
    print("会话不存在")

# 检查订阅状态
print(f"订阅运行状态: {query.is_running()}")
print(f"子会话数量: {len(query.get_child_sessions())}")
```

SessionQuery 为 Claude Agent System 提供了强大而简洁的会话查询和订阅能力，是新架构的核心组件。