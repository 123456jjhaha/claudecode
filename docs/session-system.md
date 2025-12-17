# 会话系统详解

本文档详细说明了 Claude Agent System 的会话记录和管理系统，包括最新的实时消息推送功能。

## 目录

- [系统架构概览](#系统架构概览)
- [核心组件](#核心组件)
- [实时消息推送](#实时消息推送)
- [会话生命周期](#会话生命周期)
- [会话树构建](#会话树构建)
- [会话查询 API](#会话查询-api)
- [消息格式](#消息格式)
- [性能优化](#性能优化)
- [使用示例](#使用示例)

## 系统架构概览

会话系统采用模块化设计，分为 5 个核心模块：

```
src/session/
├── core/                    # 会话核心模块
│   ├── session.py          # Session 类
│   └── session_manager.py  # SessionManager 类
├── streaming/              # 实时消息流模块
│   ├── message_bus.py     # Redis 消息总线
│   └── stream_manager.py  # 查询流管理器
├── storage/                # 存储模块
│   └── jsonl_writer.py    # 异步批量 JSONL 写入器
├── query/                  # 查询模块
│   ├── session_query.py   # 查询 API
│   └── tree_builder.py    # 会话树构建器
└── utils/                  # 工具模块
    ├── session_utils.py    # 工具函数
    └── session_serializer.py  # 消息序列化器
```

### 设计原则

1. **实时性**：消息产生后立即推送到 Redis（延迟 < 100ms）
2. **完整性**：父子会话自动整合，支持递归树构建
3. **可靠性**：Redis + JSONL 双层存储，确保消息不丢失
4. **兼容性**：支持降级运行，Redis 不可用时自动使用内存模式
5. **性能**：异步批量写入，减少 I/O 操作

## 核心组件

### 1. Session（会话对象）

**位置**: `src/session/core/session.py`

会话对象表示一次完整的对话，包含消息记录、统计信息和元数据。

```python
class Session:
    def __init__(
        self,
        session_id: str,
        instance_name: str,
        session_dir: Path,
        message_bus: Optional[MessageBus] = None,
        jsonl_writer: Optional[JSONLWriter] = None
    ):
```

**核心方法**：

- `record_message(message)`: 记录新消息
- `finalize()`: 完成会话并写入统计数据
- `get_statistics()`: 获取会话统计信息

### 2. SessionManager（会话管理器）

**位置**: `src/session/core/session_manager.py`

负责创建和管理会话实例。

```python
class SessionManager:
    def __init__(
        self,
        instance_name: str,
        sessions_root: Path,
        message_bus: Optional[MessageBus] = None
    ):
```

**核心方法**：

- `create_session()`: 创建新会话
- `get_session()`: 获取现有会话
- `list_sessions()`: 列出所有会话

### 3. MessageBus（消息总线）

**位置**: `src/session/streaming/message_bus.py`

全局单例，负责 Redis Pub/Sub 消息的发布和订阅。

```python
class MessageBus:
    @classmethod
    def from_config(cls, config_path: str = None) -> 'MessageBus'

    async def connect() -> bool
    async def publish(channel: str, message: dict) -> bool
    async def subscribe(*channels) -> AsyncIterator[dict]
```

**特性**：
- 全局单例模式，所有 AgentSystem 实例共享
- 支持多频道：`messages:session:{id}`、`messages:instance:{name}`、`messages:all`
- 连接池管理（默认 50 个连接）
- 降级策略：Redis 不可用时静默失败

### 4. JSONLWriter（异步写入器）

**位置**: `src/session/storage/jsonl_writer.py`

负责异步批量写入消息到 JSONL 文件。

```python
class JSONLWriter:
    def __init__(
        self,
        session_dir: Path,
        batch_size: int = 10,
        flush_interval: float = 1.0
    ):
```

**特性**：
- 批量写入缓冲区（默认 10 条消息）
- 定时刷新（默认 1 秒）
- 后台任务自动刷新
- 紧急备份机制（`.backup.jsonl`）

## 实时消息推送

### 消息流程

```
Session.record_message(message)
    ↓
[1] 序列化消息为字典
    ↓
[2] 发布到 Redis (实时) ← 延迟 < 100ms
    ├─ messages:session:{session_id}
    ├─ messages:instance:{instance_name}
    └─ messages:all
    ↓
[3] 写入 JSONLWriter 缓冲区
    ├─ 达到 batch_size (10条) → 立即刷新
    └─ 定时刷新 (1秒)
    ↓
[4] 写入 messages.jsonl (持久化)
    ↓
[5] finalize() 时强制刷新
```

### Redis 消息格式

```json
{
  "event_type": "message_created",
  "timestamp": "2025-12-16T10:30:00.123456",
  "instance_name": "demo_agent",
  "session_id": "20251216T103000_1234_abcd1234",
  "parent_session_id": "20251216T102900_5678_efgh5678",
  "depth": 1,
  "seq": 42,
  "message_type": "AssistantMessage",
  "data": {
    "content": [...],
    "model": "claude-sonnet-4-5"
  }
}
```

### 订阅实时消息

```python
from src.session.streaming import MessageBus
from src.session.query.session_query import subscribe_session_messages

async def monitor_session(session_id: str):
    """实时监控特定会话的消息"""
    message_bus = MessageBus.from_config()
    await message_bus.connect()

    try:
        async for event in subscribe_session_messages(session_id, message_bus):
            print(f"[{event['seq']}] {event['message_type']}")
            if event['message_type'] == 'AssistantMessage':
                print(f"  内容: {event['data']}")
    finally:
        await message_bus.close()
```

## 会话生命周期

### 会话 ID 格式

格式：`{timestamp}_{counter}_{short_hash}`

示例：`20251211T061755_0001_a3f9c2d8`

- **timestamp**: ISO 8601 格式的时间戳
- **counter**: 当日的会话计数器（4位，不足补零）
- **short_hash**: 基于 UUID 的短哈希（8位）

### 会话目录结构

```
instances/{instance_name}/sessions/{session_id}/
├── metadata.json        # 会话元数据
├── messages.jsonl       # 消息记录（JSON Lines）
└── statistics.json      # 统计信息
```

#### metadata.json
```json
{
  "session_id": "20251216T103000_1234_abcd1234",
  "instance_name": "demo_agent",
  "created_at": "2025-12-16T10:30:00",
  "status": "completed",
  "parent_session_id": null,
  "resume_count": 0
}
```

#### statistics.json
```json
{
  "total_messages": 25,
  "user_messages": 8,
  "assistant_messages": 10,
  "tool_messages": 7,
  "duration_seconds": 180,
  "tokens_used": 3500,
  "subsessions": [
    {
      "session_id": "20251216T103200_5678_efgh5678",
      "tool_name": "sub_claude_file_analyzer",
      "tool_use_id": "toolu_abc123",
      "timestamp": "2025-12-16T10:32:00"
    }
  ]
}
```

## 会话树构建

SessionTreeBuilder 可以递归构建父子会话关系树。

```python
from src.session.query import SessionTreeBuilder

async def build_session_tree():
    builder = SessionTreeBuilder()

    tree = await builder.build_tree(
        session_id="parent_session_id",
        include_messages=True,
        max_depth=10
    )

    print(f"会话树: {tree}")

    # 展平为列表
    flat_list = builder.flatten_tree(tree)
    print(f"共 {len(flat_list)} 个会话节点")
```

### 树形结构示例

```json
{
  "session_id": "20251216T103000_1234_abcd1234",
  "instance_name": "demo_agent",
  "depth": 0,
  "created_at": "2025-12-16T10:30:00",
  "messages": [...],
  "statistics": {...},
  "subsessions": [
    {
      "session_id": "20251216T103200_5678_efgh5678",
      "instance_name": "file_analyzer",
      "depth": 1,
      "messages": [...],
      "statistics": {...},
      "subsessions": [...]
    }
  ]
}
```

## 会话查询 API

### 基础查询

```python
from src.session.session_query import (
    get_session_details,
    list_sessions,
    search_sessions,
    export_session
)

# 获取会话详情
details = get_session_details(
    instance_name="demo_agent",
    session_id="20251216T103000_1234_abcd1234",
    include_messages=True
)

# 列出会话
sessions = list_sessions(
    instance_name="demo_agent",
    limit=50,
    offset=0
)

# 搜索会话
results = search_sessions(
    instance_name="demo_agent",
    query="Python 代码",
    date_from="2025-12-01",
    date_to="2025-12-31"
)

# 导出会话
export_data = export_session(
    instance_name="demo_agent",
    session_id="20251216T103000_1234_abcd1234",
    format="json"  # 支持 json, markdown, csv
)
```

### 实时订阅

```python
from src.session.query.session_query import (
    subscribe_session_messages,
    subscribe_instance_messages
)

# 订阅特定会话的消息
async for event in subscribe_session_messages(session_id, message_bus):
    print(f"新消息: {event}")

# 订阅实例的所有消息
async for event in subscribe_instance_messages("demo_agent", message_bus):
    print(f"实例消息: {event}")
```

## 消息格式

### 消息类型

支持的消息类型：
- `UserMessage`: 用户输入
- `AssistantMessage`: AI 助手回复
- `ToolResultMessage`: 工具执行结果
- `ToolUseMessage`: 工具调用请求

### JSONL 格式示例

每行一个 JSON 对象：

```jsonl
{"seq":1,"type":"UserMessage","timestamp":"2025-12-16T10:30:00","content":{"text":"你好"}}
{"seq":2,"type":"AssistantMessage","timestamp":"2025-12-16T10:30:05","content":{"text":"你好！有什么可以帮助你的吗？"}}
{"seq":3,"type":"ToolUseMessage","timestamp":"2025-12-16T10:30:10","content":{"tool_name":"calculator__add","args":{"a":1,"b":2}}}
```

## 性能优化

### 批量写入优化

- **批量大小**：默认 10 条消息批量写入
- **刷新间隔**：默认 1 秒定时刷新
- **后台任务**：独立的异步任务负责刷新

### 内存优化

- 消息写入后立即从内存清除
- 使用流式处理避免加载大文件
- 支持分页查询历史消息

### Redis 优化

- 连接池管理（默认 50 个连接）
- 发布操作非阻塞
- 订阅使用独立连接

## 使用示例

### 基础会话记录

```python
import asyncio
from src import AgentSystem

async def basic_session():
    agent = AgentSystem("demo_agent")
    await agent.initialize()

    # 执行查询（自动记录会话）
    result = await agent.query_text("计算 123 + 456")
    print(f"结果: {result.result}")
    print(f"会话 ID: {result.session_id}")

    agent.cleanup()
```

### 启用实时消息

```python
import asyncio
from src import AgentSystem
from src.session.streaming import MessageBus

async def real_time_session():
    # 创建全局 MessageBus
    message_bus = MessageBus.from_config()
    await message_bus.connect()

    try:
        # 创建 Agent 实例
        agent = AgentSystem("demo_agent", message_bus=message_bus)
        await agent.initialize()

        # 执行查询（消息自动推送到 Redis）
        result = await agent.query_text("分析这个文件")

        # 可以订阅实时消息流
        async for event in subscribe_session_messages(
            result.session_id,
            message_bus
        ):
            print(f"实时消息: {event}")

    finally:
        agent.cleanup()
        await message_bus.close()
```

### 会话树查询

```python
import asyncio
from src.session.query import SessionTreeBuilder

async def query_session_tree():
    builder = SessionTreeBuilder()

    # 构建完整的会话树
    tree = await builder.build_tree(
        session_id="root_session_id",
        include_messages=False,  # 不包含消息内容，只看结构
        max_depth=5
    )

    # 递归打印会话树
    def print_tree(node, indent=""):
        print(f"{indent}- {node['session_id']} ({node['instance_name']})")
        for sub in node.get('subsessions', []):
            print_tree(sub, indent + "  ")

    print_tree(tree)
```

### 会话导出

```python
import asyncio
from src.session.session_query import export_session

async def export_conversation():
    # 导出为 Markdown
    markdown = export_session(
        instance_name="demo_agent",
        session_id="20251216T103000_1234_abcd1234",
        format="markdown"
    )

    # 保存到文件
    with open("conversation.md", "w", encoding="utf-8") as f:
        f.write(markdown)

    print("会话已导出到 conversation.md")
```

## 故障排除

### 常见问题

1. **Redis 连接失败**
   - 检查 Redis 服务是否启动
   - 验证连接配置（URL、端口、密码）
   - 系统会自动降级到内存模式

2. **消息写入失败**
   - 检查磁盘空间
   - 验证目录权限
   - 查看是否有 `.backup.jsonl` 文件

3. **会话 ID 冲突**
   - 系统使用时间戳+计数器+哈希确保唯一性
   - 高并发时可能需要调整计数器位数

### 调试技巧

1. **启用调试日志**
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

2. **检查消息总线状态**
   ```python
   message_bus = MessageBus.from_config()
   print(f"连接状态: {message_bus.is_connected}")
   ```

3. **查看会话统计**
   ```python
   details = get_session_details("demo_agent", session_id)
   print(f"消息总数: {details['statistics']['total_messages']}")
   ```