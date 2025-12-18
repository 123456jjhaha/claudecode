# 会话系统完整指南

本文档是 Claude Agent System 会话系统的完整指南，涵盖会话管理、统一查询、实时消息订阅等所有功能。

> **💡 新架构说明**：系统已重构为**统一查询架构**，推荐使用 [SessionQuery 完整使用指南](session-query-guide.md) 获取最新功能。

## 目录

- [系统概览](#系统概览)
- [快速开始](#快速开始)
- [核心概念](#核心概念)
- [SessionManager 使用](#sessionmanager-使用)
- [SessionQuery 使用](#sessionquery-使用)
- [实时消息订阅](#实时消息订阅)
- [会话树构建](#会话树构建)
- [最佳实践](#最佳实践)

---

## 系统概览

### 新架构图

```
🏛️ 会话管理类                    🔍 会话查询类
┌─────────────────────┐         ┌─────────────────────┐
│   SessionManager    │         │    SessionQuery     │
│  ┌─────────────┐    │         │  ┌─────────────┐    │
│  │   Session   │    │◄────────┤  │ 查询功能    │    │
│  └─────────────┘    │         │  └─────────────┘    │
│                     │         │  ┌─────────────┐    │
│  create_session()   │         │  │ 订阅功能    │    │
│  get_session()      │         │  └─────────────┘    │
│  list_sessions()     │         │  ┌─────────────┐    │
│  cleanup_sessions()  │         │  │ 树构建功能  │    │
└─────────────────────┘         │  └─────────────┘    │
                                └─────────────────────┘
                 │                           │
                 ▼                           ▼
        ┌─────────────────────┐   ┌─────────────────────┐
        │   MessageBus        │   │   查询辅助函数      │
        │  (Redis Pub/Sub)    │   │   (utils/query_     │
        └─────────────────────┘   │    helpers.py)      │
                 │                   └─────────────────────┘
                 ▼
        ┌─────────────────────┐
        │   持久化存储         │
        │  (JSONL 文件)       │
        └─────────────────────┘
```

### 核心特性

✅ **统一查询架构** - 两大核心类，职责清晰分离
✅ **自动会话记录** - 所有对话自动记录，包括消息、工具调用、结果
✅ **实时消息推送** - 基于 Redis Pub/Sub，延迟 < 100ms
✅ **自动子实例追踪** - 订阅父会话，自动接收所有子实例消息
✅ **会话树构建** - 递归构建完整的调用链
✅ **双层存储** - Redis (实时) + JSONL (持久化)
✅ **向后兼容** - 旧 API 仍然有效

---

## 快速开始

### 基础会话管理

```python
from src.session import SessionManager

# 创建会话管理器
manager = SessionManager("instances/demo_agent")

# 创建新会话
session = await manager.create_session(
    initial_prompt="分析这个项目",
    parent_session_id=None
)

# 获取已有会话
session = manager.get_session("session_id")

# 列出会话
sessions = manager.list_sessions(limit=10)
```

### 统一查询服务

```python
from src.session import SessionQuery

# 创建查询服务
query = SessionQuery("demo_agent")

# 基础查询
details = query.get_session_details("session_id", include_messages=True)
sessions = query.list_sessions(status="completed")

# 高级查询
results = query.search_sessions("文件分析")
stats = query.get_statistics_summary(recent_days=7)

# 实时订阅
await query.subscribe(
    session_id="parent_session_id",
    on_parent_message=lambda msg: print(f"[父] {msg}"),
    on_child_message=lambda child_id, instance, msg: print(
        f"[子-{instance}] {msg}"
    )
)

# 会话树构建
tree = await query.build_session_tree("parent_session_id")
```

---

## 核心概念

### Session ID vs Claude ID

**Session ID（我们的会话ID）**：
- 格式：`{timestamp}_{counter}_{short_hash}`
- 示例：`20241218T140000_1000_abc123`
- 用途：标识一次完整的对话会话
- 特点：持久化保存，支持会话恢复和查询

**Claude ID（SDK 内部ID）**：
- 格式：UUID 格式
- 用途：标识与 Claude API 的单次对话
- 特点：仅在单次查询生命周期内有效

### 会话状态

- **`running`** - 会话正在进行中
- **`completed`** - 会话正常完成
- **`failed`** - 会话因错误终止
- **`interrupted`** - 会话被中断

---

## SessionManager 使用

SessionManager 负责会话的生命周期管理。

### 创建会话

```python
import asyncio
from src.session import SessionManager

async def create_new_session():
    manager = SessionManager("instances/demo_agent")

    # 创建新会话
    session = await manager.create_session(
        initial_prompt="请分析这个项目的架构",
        context={"project": "claude-agent-system"},
        parent_session_id=None  # 根会话
    )

    print(f"新会话创建: {session.session_id}")
    return session

# 运行
session = asyncio.run(create_new_session())
```

### 获取会话

```python
# 获取已有会话（用于 resume）
session = manager.get_session("20241218T140000_1000_abc123")

# 会话对象提供以下方法：
metadata = session.get_metadata()      # 获取元数据
messages = session.get_messages()      # 获取消息列表
statistics = session.get_statistics()  # 获取统计信息
```

### 列出会话

```python
# 列出所有会话
all_sessions = manager.list_sessions()

# 按状态过滤
completed_sessions = manager.list_sessions(status="completed")

# 分页查询
page1 = manager.list_sessions(limit=20, offset=0)
page2 = manager.list_sessions(limit=20, offset=20)
```

### 清理会话

```python
# 清理过期会话
report = manager.cleanup_old_sessions(
    retention_days=30,
    dry_run=False  # 设为 True 可以预览将要删除的内容
)

print(f"删除了 {report['deleted']} 个会话")
print(f"释放空间: {report['total_size_mb']:.2f} MB")
```

---

## SessionQuery 使用

SessionQuery 是统一查询服务，提供所有查询相关功能。

> **💡 详细说明**：请参考 [SessionQuery 完整使用指南](session-query-guide.md)

### 基础查询功能

```python
query = SessionQuery("demo_agent")

# 获取会话详情
details = query.get_session_details(
    session_id="20241218T140000_1000_abc123",
    include_messages=True,    # 包含消息内容
    message_limit=50         # 限制消息数量
)

# 获取特定消息
messages = query.get_session_messages(
    session_id="20241218T140000_1000_abc123",
    message_types=["ToolUseMessage", "ResultMessage"]
)
```

### 高级查询功能

```python
# 搜索会话
results = query.search_sessions(
    query="错误分析",           # 搜索关键词
    field="initial_prompt",    # 搜索字段
    limit=10
)

# 获取统计摘要
stats = query.get_statistics_summary(recent_days=7)
print(f"最近7天: {stats['total_sessions']} 个会话")
print(f"完成率: {stats['completed_sessions']/stats['total_sessions']:.1%}")

# 导出会话
query.export_session(
    session_id="20241218T140000_1000_abc123",
    output_file=Path("export.json"),
    format="json"
)
```

---

## 实时消息订阅

SessionQuery 提供强大的实时消息订阅功能。

### 基础订阅

```python
import asyncio
from src.session import MessageBus, SessionQuery

async def subscribe_messages():
    # 创建 MessageBus
    message_bus = MessageBus.from_config()
    await message_bus.connect()

    try:
        # 创建查询服务
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

        # 等待消息
        print("订阅已启动，等待消息...")
        await query.wait()

    finally:
        await query.stop()
        await message_bus.close()

asyncio.run(subscribe_messages())
```

### 自动子实例追踪

**核心特性**：当父会话调用子实例时，SessionQuery 会：

1. **自动检测** 子实例启动通知
2. **自动订阅** 子实例的消息频道
3. **实时推送** 所有子实例消息
4. **区分来源** 父消息 vs 子消息

```python
# 一个订阅就能接收所有消息！
await query.subscribe(
    session_id="parent_id",
    on_parent_message=lambda msg: print(f"主实例: {msg}"),
    on_child_message=lambda child_id, instance, msg:
        print(f"子实例({instance}): {msg}")
)

# 当主实例调用子实例时：
# 1. 自动检测到子实例启动
# 2. 自动订阅子实例消息
# 3. 所有消息都会推送到对应的回调函数
```

### 高级订阅模式

```python
class MessageCollector:
    def __init__(self):
        self.parent_messages = []
        self.child_messages = []
        self.started_children = []

    def on_parent_message(self, msg):
        self.parent_messages.append(msg)
        print(f"收集父消息: {len(self.parent_messages)}")

    def on_child_message(self, child_id, instance, msg):
        self.child_messages.append({
            "child_id": child_id,
            "instance": instance,
            "message": msg
        })

    def on_child_started(self, child_id, instance):
        self.started_children.append({
            "child_id": child_id,
            "instance": instance
        })
        print(f"🔔 子实例启动: {instance}")

# 使用收集器
collector = MessageCollector()
await query.subscribe(
    session_id="session_id",
    on_parent_message=collector.on_parent_message,
    on_child_message=collector.on_child_message,
    on_child_started=collector.on_child_started
)
```

---

## 会话树构建

SessionQuery 可以递归构建完整的会话调用链。

### 构建会话树

```python
async def build_session_tree_example():
    query = SessionQuery("demo_agent")

    # 构建会话树
    tree = await query.build_session_tree(
        session_id="parent_session_id",
        include_messages=False,  # 不包含消息，只获取结构
        max_depth=5
    )

    # 树结构示例：
    # {
    #     "session_id": "parent_id",
    #     "instance_name": "demo_agent",
    #     "depth": 0,
    #     "metadata": {...},
    #     "statistics": {...},
    #     "subsessions": [
    #         {
    #             "session_id": "child_id",
    #             "instance_name": "file_analyzer",
    #             "depth": 1,
    #             "subsessions": [...]
    #         }
    #     ]
    # }

    # 展平为列表
    flat_list = query.flatten_tree(tree)

    # 分析调用链
    for session in flat_list:
        indent = "  " * session.get('depth', 0)
        status = session['metadata'].get('status', 'unknown')
        print(f"{indent}- {session['instance_name']} ({status})")

asyncio.run(build_session_tree_example())
```

### 分析调用链

```python
# 调用深度分析
max_depth = max(session['depth'] for session in flat_list)
print(f"最大调用深度: {max_depth}")

# 实例使用统计
from collections import Counter
instances = Counter(session['instance_name'] for session in flat_list)
print(f"实例使用统计: {dict(instances)}")

# 成功率分析
completed = sum(1 for s in flat_list if s['metadata'].get('status') == 'completed')
total = len(flat_list)
print(f"调用成功率: {completed/total:.1%}")
```

---

## 最佳实践

### 1. 性能优化

```python
# ✅ 限制消息数量
details = query.get_session_details(
    session_id="xxx",
    include_messages=True,
    message_limit=100  # 限制消息数量，避免内存过大
)

# ✅ 使用分页查询
sessions = query.list_sessions(limit=50, offset=0)

# ✅ 限制树深度
tree = await query.build_session_tree(
    session_id="parent_id",
    max_depth=3  # 避免无限递归
)
```

### 2. 内存管理

```python
# ✅ 及时清理订阅
async def managed_subscription():
    query = SessionQuery("demo_agent", message_bus=message_bus)
    await query.subscribe(...)

    try:
        # 使用订阅
        await query.wait(timeout=300)  # 5分钟超时
    finally:
        await query.stop()  # 确保清理

# ✅ 使用上下文管理器
class QuerySubscription:
    async def __aenter__(self):
        self.query = SessionQuery("demo_agent", message_bus=message_bus)
        await self.query.subscribe(...)
        return self.query

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.query.stop()

async with QuerySubscription() as query:
    # 使用查询...
    pass
```

### 3. 错误处理

```python
# ✅ 异常处理
try:
    details = query.get_session_details("invalid_session_id")
except AgentSystemError as e:
    logger.error(f"获取会话详情失败: {e}")
    # 处理错误...

# ✅ 订阅错误处理
async def safe_subscription():
    try:
        await query.subscribe(...)
        await query.wait()
    except Exception as e:
        logger.error(f"订阅失败: {e}")
    finally:
        try:
            await query.stop()
        except Exception as e:
            logger.error(f"停止订阅失败: {e}")
```

### 4. 监控和调试

```python
# ✅ 启用调试日志
import logging
logging.getLogger('src.session').setLevel(logging.DEBUG)

# ✅ 监控订阅状态
print(f"订阅运行状态: {query.is_running()}")
print(f"子会话数量: {len(query.get_child_sessions())}")

# ✅ 性能监控
import time

start_time = time.time()
details = query.get_session_details("session_id")
duration = time.time() - start_time
print(f"查询耗时: {duration:.3f}秒")
```

---

## 📚 更多资源

- **[SessionQuery 完整使用指南](session-query-guide.md)** - 详细的功能说明和示例
- **[SessionQuery 迁移指南](session-migration-guide)** - 从旧架构平滑迁移
- **[配置指南](configuration.md)** - 完整的配置选项说明
- **[子实例系统](sub-instances.md)** - 子实例的详细说明

新的统一查询架构让会话管理变得更加简洁和强大，推荐所有新项目使用 SessionQuery 作为主要接口。