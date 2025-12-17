# 实时消息系统重构计划

## 概述

重构现有 session 模块，实现实时消息推送和父子实例消息整合。核心目标：
- ✅ 实时性：消息产生时立即推送到 Redis
- ✅ 完整性：父子实例消息自动整合，提供层级化视图
- ✅ 可靠性：Redis + JSONL 双层存储，消息不丢失
- ✅ 兼容性：保持 query/query_text 接口不变

## 架构设计

### 1. 核心组件

```
应用启动时：
    ↓
创建全局 MessageBus (单例) ← 关键改变
    ├─ 从 streaming.yaml 或 .env 加载配置
    ├─ 建立 Redis 连接池
    └─ 所有 AgentSystem 实例共享
    ↓
创建 AgentSystem 实例（依赖注入）
    ├─ agent1 = AgentSystem("demo", message_bus=bus)
    └─ agent2 = AgentSystem("analyzer", message_bus=bus)
    ↓
消息产生流程：
Session.record_message(message)
    ↓
[1] 序列化消息
    ↓
[2] 发布到 Redis (实时) ← 使用注入的 MessageBus
    ├─ messages:session:{session_id}
    ├─ messages:instance:{instance_name}
    └─ messages:all
    ↓
[3] 写入 JSONLWriter 缓冲区 ← 新增
    ├─ 达到 batch_size (10条) → 立即刷新
    └─ 定时刷新 (1秒)
    ↓
[4] 写入 messages.jsonl (持久化)
    ↓
[5] finalize() 时强制刷新
```

### 2. 技术选型

| 组件 | 选型 | 理由 |
|------|------|------|
| **消息总线** | Redis Pub/Sub | 轻量级、高性能、跨平台、支持多频道订阅 |
| **持久化** | JSONL 文件 | 可靠、可审计、Redis Pub/Sub 消息是临时的 |
| **异步写入** | 批量刷新 + 定时器 | 减少 I/O，保持实时性（最多1秒延迟） |
| **消息格式** | JSON | 结构化、易解析、支持嵌套 |

### 3. Redis 消息格式

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
  "data": {...}  // 序列化的消息内容
}
```

### 4. 父子消息关联

```
父实例调用子实例：
SubInstanceTool.__call__(parent_session_id="parent_xxx")
    ↓
子实例创建会话：
metadata = {
    "session_id": "child_yyy",
    "parent_session_id": "parent_xxx",
    "depth": 1
}
    ↓
子实例发布消息（携带 parent_session_id）
    ↓
消息树构建器递归查询
```

## 实施步骤

### Phase 1: 基础设施搭建 (优先级：高)

#### 1.1 创建 MessageBus 类
**文件**: `src/session/streaming/message_bus.py` (新建)

**功能**:
- Redis 连接管理（使用 aioredis）
- 发布消息到多个频道
- 订阅频道并监听消息
- 降级策略（Redis 不可用时静默失败）

**核心接口**:
```python
class MessageBus:
    def __init__(redis_url: str, redis_db: int = 0, max_connections: int = 50)

    @classmethod
    def from_config(cls, config_path: str = None) -> 'MessageBus'
    # 从 streaming.yaml 或环境变量加载配置

    async def connect()
    async def publish(channel: str, message: dict)
    async def subscribe(*channels) -> AsyncIterator
    async def close()
```

**关键点**:
- **全局单例模式**：应用启动时创建一次，所有 Agent 共享
- 使用连接池，支持并发（默认 50 个连接）
- 发布失败时记录日志，不影响主流程
- 支持多频道批量订阅
- 支持从配置文件或环境变量加载

#### 1.2 创建 JSONLWriter 类
**文件**: `src/session/storage/jsonl_writer.py` (新建)

**功能**:
- 批量写入缓冲区（默认 10 条消息）
- 定时刷新（默认 1 秒）
- 后台任务自动刷新
- 紧急备份机制（写入失败时备份到 .backup.jsonl）

**核心接口**:
```python
class JSONLWriter:
    def __init__(session_dir: Path, batch_size: int = 10, flush_interval: float = 1.0)
    async def write(message_data: dict)
    async def _auto_flush()  # 后台任务
    async def finalize()  # 强制刷新并停止
```

**关键点**:
- 使用 asyncio.create_task 启动后台刷新任务
- finalize 时取消后台任务并强制刷新
- 支持追加模式（resume 会话）

#### 1.3 配置文件拆分（重要改变）

**全局配置** - `streaming.yaml` (项目根目录，新建)：
```yaml
# 实时消息总线配置（全局共享）
redis:
  url: "redis://localhost:6379"
  db: 0
  max_connections: 50

# 异步写入配置（全局默认值）
async_write:
  batch_size: 10
  flush_interval: 1.0
```

**或使用环境变量**（`.env`）：
```bash
REDIS_URL=redis://localhost:6379
REDIS_DB=0
REDIS_MAX_CONNECTIONS=50
ASYNC_WRITE_BATCH_SIZE=10
ASYNC_WRITE_FLUSH_INTERVAL=1.0
```

**实例配置** - `instances/{instance_name}/config.yaml`（简化）：
```yaml
session_recording:
  enabled: true

  # 原有配置（保留）
  retention_days: 30
  message_types: null

```

**配置优先级**：环境变量 > streaming.yaml > 默认值

---

### Phase 2: Session 集成 (优先级：高)

#### 2.1 重构 Session 类
**文件**: `src/session/core/session.py` (拆分自 session_manager.py)

**修改点**:

1. **构造函数新增参数**:
```python
class Session:
    def __init__(
        ...,
        message_bus: Optional[MessageBus] = None,  # 新增
        jsonl_writer: Optional[JSONLWriter] = None  # 新增
    ):
        self._message_bus = message_bus
        self._jsonl_writer = jsonl_writer
        self._messages = []  # 降级时使用
```

2. **record_message 重构**:
```python
async def record_message(self, message: Any):
    # 1. 序列化
    message_data = {
        "seq": self._message_count,
        "timestamp": datetime.now().isoformat(),
        "message_type": type(message).__name__,
        "data": MessageSerializer.serialize_message(message)
    }

    # 2. 发布到 Redis (实时)
    if self._message_bus:
        await self._publish_to_bus(message_data)

    # 3. 异步写入 JSONL
    if self._jsonl_writer:
        await self._jsonl_writer.write(message_data)
    else:
        # 降级：保存到内存（兼容旧逻辑）
        self._messages.append(message_data)

    # 4. 更新统计
    self._message_count += 1
    self._statistics.num_messages += 1
    self._detect_and_record_subsession(message)
```

3. **新增 _publish_to_bus 方法**:
```python
async def _publish_to_bus(self, message_data: dict):
    """发布消息到 Redis"""
    event = {
        "event_type": "message_created",
        "timestamp": message_data["timestamp"],
        "instance_name": self.metadata["instance_name"],
        "session_id": self.session_id,
        "parent_session_id": self.metadata.get("parent_session_id"),
        "depth": self.metadata.get("depth", 0),
        "seq": message_data["seq"],
        "message_type": message_data["message_type"],
        "data": message_data["data"]
    }

    # 发布到多个频道
    await self._message_bus.publish(
        f"messages:session:{self.session_id}", event
    )
    await self._message_bus.publish(
        f"messages:instance:{self.metadata['instance_name']}", event
    )
```

4. **finalize 修改**:
```python
async def finalize(self, result_message=None):
    # 强制刷新 JSONLWriter
    if self._jsonl_writer:
        await self._jsonl_writer.finalize()
    else:
        # 降级：一次性写入内存中的消息
        await self._write_messages_to_jsonl()

    # 写入元数据和统计信息（保持不变）
    ...

    self._finalized = True
```

#### 2.2 修改 SessionManager 类
**文件**: `src/session/core/session_manager.py` (拆分自 session_manager.py)

**修改点**:

1. **构造函数新增参数**:
```python
class SessionManager:
    def __init__(
        ...,
        message_bus: Optional[MessageBus] = None  # 新增
    ):
        self._message_bus = message_bus
```

2. **create_session 修改**:
```python
async def create_session(self, ...) -> Session:
    # ... 原有逻辑 ...

    # 创建 JSONLWriter（从全局配置或环境变量读取）
    jsonl_writer = None
    if self._message_bus:  # 如果启用了实时流，自动启用异步写入
        import os
        batch_size = int(os.getenv("ASYNC_WRITE_BATCH_SIZE", "10"))
        flush_interval = float(os.getenv("ASYNC_WRITE_FLUSH_INTERVAL", "1.0"))

        jsonl_writer = JSONLWriter(
            session_dir=session_dir,
            batch_size=batch_size,
            flush_interval=flush_interval
        )

    # 创建 Session
    session = Session(
        session_id=session_id,
        session_dir=session_dir,
        metadata=metadata,
        config=config,
        message_bus=self._message_bus,  # 传递 MessageBus（可能为 None）
        jsonl_writer=jsonl_writer  # 传递 JSONLWriter（可能为 None）
    )

    await session.start()
    return session
```

#### 2.3 修改 AgentSystem 类（重要改变）
**文件**: `src/agent_system.py`

**修改点**:

1. **构造函数新增参数（依赖注入）**:
```python
class AgentSystem:
    def __init__(
        self,
        instance_name: str,
        instances_root: Path | None = None,
        message_bus: Optional[MessageBus] = None  # ← 新增参数（可选）
    ):
        self.instance_path = ...
        self._message_bus = message_bus  # 保存引用（不创建）
        self._initialized = False
```

2. **initialize 方法简化（不再创建 MessageBus）**:
```python
async def initialize(self):
    # ... 原有逻辑 ...

    # ✅ 不再创建 MessageBus，直接使用传入的
    session_config = self.config_manager.config.get("session_recording", {})

    # 初始化 SessionManager（传递 MessageBus）
    self.session_manager = SessionManager(
        instance_path=self.instance_path,
        config=session_config,
        message_bus=self._message_bus  # 直接传递（可能为 None）
    )

    self._initialized = True
```

3. **cleanup 方法不再关闭 MessageBus**:
```python
def cleanup(self):
    # ... 原有逻辑 ...

    # ❌ 删除：不再关闭 MessageBus（由调用者管理生命周期）
    # MessageBus 是全局单例，由应用层负责关闭
```

---

### Phase 3: 查询 API 重写 (优先级：中)

#### 3.1 完全重写 session_query.py
**文件**: `src/session/query/session_query.py` (重写)

**新增功能**:

1. **实时订阅 API**:
```python
async def subscribe_session_messages(
    session_id: str,
    message_bus: MessageBus
) -> AsyncIterator[dict]:
    """订阅特定会话的实时消息流"""
    channel = f"messages:session:{session_id}"
    async for message in message_bus.subscribe(channel):
        yield json.loads(message["data"])
```

2. **实时订阅实例消息**:
```python
async def subscribe_instance_messages(
    instance_name: str,
    message_bus: MessageBus
) -> AsyncIterator[dict]:
    """订阅特定实例的所有消息"""
    channel = f"messages:instance:{instance_name}"
    async for message in message_bus.subscribe(channel):
        yield json.loads(message["data"])
```

3. **获取会话详情**（保留兼容性）:
```python
def get_session_details(
    instance_name: str,
    session_id: str,
    include_messages: bool = False
) -> dict:
    """从 JSONL 文件读取会话详情（历史数据）"""
    # 读取 metadata.json
    # 读取 statistics.json
    # 可选读取 messages.jsonl
    # 返回完整字典
```

#### 3.2 创建 TreeBuilder 类
**文件**: `src/session/query/tree_builder.py` (新建)

**功能**: 递归构建会话消息树

**核心方法**:
```python
class SessionTreeBuilder:
    async def build_tree(
        self,
        session_id: str,
        include_messages: bool = True,
        max_depth: int = 10
    ) -> dict:
        """
        递归构建会话树

        返回格式:
        {
            "session_id": "...",
            "instance_name": "...",
            "depth": 0,
            "messages": [...],  # 可选
            "subsessions": [
                {
                    "session_id": "...",
                    "depth": 1,
                    "messages": [...],
                    "subsessions": [...]
                }
            ]
        }
        """
        # 1. 获取会话详情
        details = get_session_details(
            instance_name=self._infer_instance_name(session_id),
            session_id=session_id,
            include_messages=include_messages
        )

        # 2. 递归构建子会话
        subsessions = []
        for subsess_info in details.get("subsessions", []):
            if len(subsessions) < max_depth:
                child_tree = await self.build_tree(
                    subsess_info["session_id"],
                    include_messages=include_messages,
                    max_depth=max_depth - 1
                )
                subsessions.append(child_tree)

        return {
            "session_id": session_id,
            "instance_name": details["metadata"]["instance_name"],
            "depth": details["metadata"].get("depth", 0),
            "messages": details.get("messages", []) if include_messages else [],
            "subsessions": subsessions
        }

    def _infer_instance_name(self, session_id: str) -> str:
        """从所有实例中查找包含该 session_id 的实例"""
        # 遍历 instances/ 目录
        # 查找包含该 session_id 的会话目录
        # 返回实例名称
```

---

### Phase 4: 目录重构 (优先级：低)

**目标**: 将 session 模块拆分为清晰的子模块

**重构后的目录结构**:
```
src/session/
├── core/
│   ├── __init__.py
│   ├── session.py              # Session 类
│   ├── session_manager.py      # SessionManager 类
│   └── metadata.py             # 元数据数据类
│
├── storage/
│   ├── __init__.py
│   ├── jsonl_writer.py         # 异步 JSONL 写入器
│   └── cleanup.py              # 清理策略（现有功能）
│
├── streaming/
│   ├── __init__.py
│   ├── message_bus.py          # Redis 消息总线
│   ├── stream_manager.py       # QueryStreamManager（保持）
│   └── realtime_api.py         # 实时订阅 API（新增）
│
├── query/
│   ├── __init__.py
│   ├── session_query.py        # 重写的查询 API
│   └── tree_builder.py         # 消息树构建器
│
└── utils/
    ├── __init__.py
    ├── session_utils.py        # 工具函数（保持）
    └── session_serializer.py   # 消息序列化（保持）
```

**迁移步骤**:
1. 创建新的子目录结构
2. 将 session_manager.py 拆分为 core/session.py 和 core/session_manager.py
3. 更新 `src/session/__init__.py` 的导入路径
4. 确保向后兼容（现有代码导入不变）

---

### Phase 5: 测试与验证 (优先级：高)

#### 5.1 单元测试

**测试文件**: `tests/test_session_realtime.py` (新建)

**测试内容**:
1. MessageBus 连接测试
2. MessageBus 发布/订阅测试
3. JSONLWriter 批量写入测试
4. JSONLWriter 定时刷新测试
5. Session 集成测试（发布 + 写入）
6. 降级测试（Redis 不可用）

#### 5.2 集成测试

**测试场景**:
1. 单实例消息记录和订阅
2. 父子实例消息整合
3. Resume 会话的消息连续性
4. 并发查询测试
5. 消息树构建测试

#### 5.3 性能测试

**测试指标**:
- 消息发布延迟（目标 < 10ms）
- JSONL 写入延迟（目标 < 100ms）
- 并发订阅数（目标 > 50）
- 内存占用（批量写入 vs 一次性写入）

---

## 关键文件清单

### 需要修改的文件

1. **src/session/session_manager.py** (重构为 core/session.py + core/session_manager.py)
   - Session 类：集成 MessageBus 和 JSONLWriter
   - SessionManager 类：传递 MessageBus 给 Session

2. **src/agent_system.py**
   - initialize(): 初始化 MessageBus
   - cleanup(): 关闭 MessageBus

3. **src/session/session_query.py** (完全重写)
   - 删除现有逻辑
   - 新增实时订阅 API
   - 保留 get_session_details（从 JSONL 读取）

4. **src/sub_instance_adapter.py**
   - 确保 parent_session_id 正确传递
   - 确保子实例消息包含 parent_session_id

### 需要新建的文件

5. **src/session/streaming/message_bus.py**
   - MessageBus 类实现

6. **src/session/storage/jsonl_writer.py**
   - JSONLWriter 类实现

7. **src/session/query/tree_builder.py**
   - SessionTreeBuilder 类实现

8. **src/session/streaming/realtime_api.py**
   - 实时订阅辅助函数

### 需要更新的配置文件

9. **instances/demo_agent/config.yaml**
   - 新增 realtime_streaming 配置
   - 新增 async_write 配置

10. **requirements.txt**
    - 新增依赖：`aioredis>=2.0.0`

---

## 实施优先级

### P0: 核心功能（必须完成）
1. MessageBus 类实现
2. JSONLWriter 类实现
3. Session.record_message 重构
4. AgentSystem.initialize 集成

### P1: 查询功能（重要）
5. session_query.py 重写
6. SessionTreeBuilder 实现
7. 实时订阅 API

### P2: 优化与重构（可选）
8. 目录重构
9. 性能优化
10. 监控指标

---

## 降级策略与错误处理

### 1. Redis 不可用
- 静默失败，不抛出异常
- 消息仍写入 JSONL（核心功能不受影响）
- 日志记录警告信息

### 2. JSONLWriter 写入失败
- 紧急备份到 `.backup.jsonl`
- 日志记录错误信息
- finalize 时再次尝试写入

### 3. 消息序列化失败
- 记录错误消息，跳过该消息
- 继续处理后续消息
- 统计信息中记录错误计数

---

## 配置示例

### 全局配置（新增）

**方式1: streaming.yaml**（项目根目录）
```yaml
# 实时消息总线配置
redis:
  url: "redis://localhost:6379"
  db: 0
  max_connections: 50

# 异步写入配置
async_write:
  batch_size: 10
  flush_interval: 1.0
```

**方式2: 环境变量**（`.env`）
```bash
REDIS_URL=redis://localhost:6379
REDIS_DB=0
REDIS_MAX_CONNECTIONS=50
ASYNC_WRITE_BATCH_SIZE=10
ASYNC_WRITE_FLUSH_INTERVAL=1.0
```

### 实例配置（简化后）

```yaml
# instances/demo_agent/config.yaml
agent:
  name: "demo_agent"
  description: "演示实例"

model: "claude-sonnet-4-5"
system_prompt_file: ".claude/agent.md"

session_recording:
  enabled: true

  # 原有配置（保留）
  retention_days: 30
  max_total_size_mb: 1000
  auto_cleanup: true
  message_types: null


```

---

## 使用示例（重要）

### 场景1: 启用实时流（推荐）

```python
import asyncio
from src import AgentSystem
from src.session.streaming import MessageBus

async def main():
    # 1. 创建全局 MessageBus（单例）
    message_bus = MessageBus.from_config()  # 从 streaming.yaml 或 .env 加载
    await message_bus.connect()
    logger.info("全局 MessageBus 已连接")

    try:
        # 2. 创建多个 Agent 实例（共享同一个 MessageBus）
        agent1 = AgentSystem("demo_agent", message_bus=message_bus)
        agent2 = AgentSystem("file_analyzer", message_bus=message_bus)

        await agent1.initialize()
        await agent2.initialize()

        # 3. 执行查询（消息会自动推送到 Redis）
        result1 = await agent1.query_text("计算 123 + 456")
        result2 = await agent2.query_text("分析文件")

        print(f"结果1: {result1.result}, 会话ID: {result1.session_id}")
        print(f"结果2: {result2.result}, 会话ID: {result2.session_id}")

        # 4. 清理 Agent 实例
        agent1.cleanup()
        agent2.cleanup()

    finally:
        # 5. 关闭全局 MessageBus
        await message_bus.close()
        logger.info("全局 MessageBus 已关闭")

asyncio.run(main())
```

### 场景2: 不启用实时流（向后兼容）

```python
import asyncio
from src import AgentSystem

async def main():
    # 不传递 message_bus 参数
    agent = AgentSystem("demo_agent")  # message_bus=None
    await agent.initialize()

    # 查询照常执行，只写入 JSONL，不发布到 Redis
    result = await agent.query_text("计算 123 + 456")
    print(f"结果: {result.result}")

    agent.cleanup()

asyncio.run(main())
```

### 场景3: 订阅实时消息流

```python
import asyncio
from src.session.streaming import MessageBus
from src.session.query import subscribe_session_messages

async def monitor_session(session_id: str):
    """实时监控特定会话的消息"""
    message_bus = MessageBus.from_config()
    await message_bus.connect()

    try:
        async for message_event in subscribe_session_messages(session_id, message_bus):
            print(f"[{message_event['seq']}] {message_event['message_type']}")
            if message_event['message_type'] == 'AssistantMessage':
                print(f"  内容: {message_event['data']['content']}")
    finally:
        await message_bus.close()

asyncio.run(monitor_session("20251216T103000_1234_abcd1234"))
```

---

## 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| Redis 部署困难 | 中 | 高 | 提供 Docker 部署方案，降级策略 |
| 异步写入 Bug | 高 | 中 | finalize() 兜底，完整测试 |
| 性能瓶颈 | 中 | 中 | 批量写入、消息过滤、性能测试 |
| 向后兼容性破坏 | 低 | 高 | query/query_text 接口保持不变 |

---

## 预计工作量

| 阶段 | 任务 | 预计时间 |
|------|------|----------|
| Phase 1 | MessageBus + JSONLWriter | 1-2 天 |
| Phase 2 | Session 集成 | 1-2 天 |
| Phase 3 | 查询 API 重写 | 1-2 天 |
| Phase 4 | 目录重构 | 0.5-1 天 |
| Phase 5 | 测试与验证 | 1-2 天 |
| **总计** |  | **4.5-9 天** |

---

## 后续扩展

完成本次重构后，可以轻松扩展以下功能：
1. **WebSocket 服务**：基于 FastAPI，实时推送到前端
2. **消息过滤**：按消息类型、实例、时间范围过滤
3. **消息搜索**：全文搜索、正则匹配
4. **监控面板**：实时查看系统状态、消息流量
5. **分布式部署**：多实例共享 Redis，实现集群监控

---

## 总结

本方案通过引入 **全局 MessageBus（Redis Pub/Sub）** 和 **异步批量写入**，在保持现有接口兼容的前提下，实现了：

### 核心特性
- ✅ **实时推送**：消息产生时立即发布到 Redis（延迟 < 100ms）
- ✅ **父子整合**：父子实例消息自动整合，支持递归树构建
- ✅ **双层存储**：JSONL 持久化兜底，Redis 消息临时推送
- ✅ **降级策略**：Redis 不可用时静默失败，核心功能不受影响

### 架构优势（全局单例设计）
- ✅ **资源高效**：所有 Agent 共享一个连接池，减少资源消耗
- ✅ **配置集中**：全局配置（streaming.yaml）与实例配置分离
- ✅ **松耦合**：依赖注入，AgentSystem 不依赖 Redis
- ✅ **易测试**：可直接注入 mock MessageBus
- ✅ **向后兼容**：message_bus 参数可选，不传递时保持原有行为

### 影响范围
- 核心修改集中在 session 模块
- AgentSystem 仅新增构造参数（可选），风险可控
- 配置分离后，实例配置更简洁
