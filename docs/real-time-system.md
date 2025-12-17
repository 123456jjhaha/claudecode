# 实时消息系统

实时消息系统是 Claude Agent System 的核心特性，提供基于 Redis Pub/Sub 的实时消息推送能力，支持低延迟（< 100ms）的消息分发和订阅。

## 目录

- [系统架构](#系统架构)
- [技术选型](#技术选型)
- [消息格式](#消息格式)
- [配置说明](#配置说明)
- [消息总线](#消息总线)
- [消息订阅](#消息订阅)
- [性能优化](#性能优化)
- [监控和调试](#监控和调试)
- [部署指南](#部署指南)

## 系统架构

### 整体架构图

```
应用层：AgentSystem 实例
    ↓
全局消息总线 (MessageBus - 单例)
    ├─ 从 streaming.yaml 或 .env 加载配置
    ├─ 建立 Redis 连接池
    └─ 所有 AgentSystem 实例共享
    ↓
消息产生流程：
Session.record_message(message)
    ↓
[1] 序列化消息为结构化字典
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
[5] finalize() 时强制刷新所有缓冲区
```

### 核心组件

1. **MessageBus（消息总线）**
   - 全局单例，管理 Redis 连接
   - 负责消息的发布和订阅
   - 支持多频道分发

2. **JSONLWriter（异步写入器）**
   - 批量缓冲消息
   - 定时刷新到磁盘
   - 支持紧急备份

3. **Session（会话对象）**
   - 集成消息发布功能
   - 自动追踪会话关系

## 技术选型

| 组件 | 技术选择 | 理由 |
|------|----------|------|
| **消息总线** | Redis Pub/Sub | 轻量级、高性能、跨平台、支持多频道订阅 |
| **持久化** | JSONL 文件 | 可靠、可审计、Redis Pub/Sub 消息是临时的 |
| **异步写入** | 批量刷新 + 定时器 | 减少 I/O，保持实时性（最多1秒延迟） |
| **消息格式** | JSON | 结构化、易解析、支持嵌套 |
| **连接管理** | 连接池 | 支持高并发，避免频繁创建连接 |

## 消息格式

### 标准消息格式

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
    "content": [
      {
        "type": "text",
        "text": "您好！有什么可以帮助您的吗？"
      }
    ],
    "model": "claude-sonnet-4-5"
  }
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `event_type` | string | 事件类型，目前固定为 "message_created" |
| `timestamp` | string | ISO 8601 格式的时间戳，包含微秒 |
| `instance_name` | string | Agent 实例名称 |
| `session_id` | string | 会话唯一标识 |
| `parent_session_id` | string | 父会话ID（子实例调用时） |
| `depth` | integer | 嵌套深度，0表示根会话 |
| `seq` | integer | 会话内的消息序号（从1开始） |
| `message_type` | string | 消息类型 |
| `data` | object | 消息内容，根据消息类型不同而不同 |

### 消息类型

- `UserMessage`: 用户输入消息
- `AssistantMessage`: AI 助手回复
- `ToolUseMessage`: 工具调用请求
- `ToolResultMessage`: 工具执行结果

## 配置说明

### 1. 全局配置文件

创建 `streaming.yaml`（推荐在项目根目录）：

```yaml
# Redis 连接配置
redis:
  url: "redis://localhost:6379"     # Redis 连接URL
  db: 0                             # 数据库编号
  max_connections: 50               # 最大连接数
  retry_attempts: 3                 # 连接重试次数
  retry_delay: 1.0                  # 重试延迟（秒）

# 异步写入配置
async_write:
  batch_size: 10                    # 批量写入的消息数量
  flush_interval: 1.0               # 定时刷新间隔（秒）
  backup_enabled: true              # 是否启用紧急备份
  max_memory_messages: 1000         # 内存中最大消息数

# 消息发布配置
publishing:
  enabled: true                     # 是否启用消息发布
  channel_prefix: "messages"        # 频道前缀
  include_metadata: true            # 是否包含元数据
  compress_large_messages: false    # 是否压缩大消息

# 订阅配置
subscription:
  buffer_size: 1000                 # 订阅缓冲区大小
  timeout: 30.0                     # 订阅超时（秒）
  heartbeat_interval: 10.0          # 心跳间隔（秒）
```

### 2. 环境变量配置

环境变量具有最高优先级：

```bash
# Redis 配置
REDIS_URL=redis://localhost:6379
REDIS_DB=0
REDIS_MAX_CONNECTIONS=50
REDIS_PASSWORD=your_password

# 异步写入配置
ASYNC_WRITE_BATCH_SIZE=10
ASYNC_WRITE_FLUSH_INTERVAL=1.0
ASYNC_WRITE_BACKUP_ENABLED=true

# 发布配置
PUBLISHING_ENABLED=true
PUBLISHING_CHANNEL_PREFIX=messages
```

### 3. 配置优先级

1. 环境变量（最高）
2. streaming.yaml
3. 默认值（最低）

## 消息总线

### MessageBus 类

```python
from src.session.streaming import MessageBus

class MessageBus:
    """全局消息总线单例"""

    @classmethod
    def from_config(cls, config_path: str = None) -> 'MessageBus':
        """从配置文件创建 MessageBus"""

    async def connect(self) -> bool:
        """连接到 Redis"""

    async def disconnect(self):
        """断开 Redis 连接"""

    async def publish(self, channel: str, message: dict) -> bool:
        """发布消息到指定频道"""

    async def subscribe(self, *channels) -> AsyncIterator[dict]:
        """订阅一个或多个频道"""

    @property
    def is_connected(self) -> bool:
        """检查连接状态"""
```

### 基本使用

```python
import asyncio
from src.session.streaming import MessageBus

async def message_bus_example():
    # 创建全局 MessageBus
    message_bus = MessageBus.from_config()  # 自动加载配置
    await message_bus.connect()

    try:
        # 发布消息
        await message_bus.publish(
            "messages:session:123",
            {
                "event_type": "message_created",
                "data": "Hello World"
            }
        )

        # 订阅消息
        async for message in message_bus.subscribe("messages:*"):
            print(f"收到消息: {message}")

    finally:
        await message_bus.disconnect()

asyncio.run(message_bus_example())
```

### 频道命名规则

- `messages:session:{session_id}`: 特定会话的消息
- `messages:instance:{instance_name}`: 特定实例的所有消息
- `messages:all`: 所有实例的所有消息

### 连接池管理

```python
# 查看连接池状态
print(f"活跃连接数: {message_bus.pool_size}")
print(f"空闲连接数: {message_bus.pool_idle}")

# 优雅关闭
await message_bus.close()  # 关闭所有连接
```

## 消息订阅

### 1. 订阅特定会话

```python
from src.session.query.session_query import subscribe_session_messages

async def monitor_session(session_id: str):
    """实时监控特定会话的消息流"""
    message_bus = MessageBus.from_config()
    await message_bus.connect()

    try:
        async for event in subscribe_session_messages(session_id, message_bus):
            print(f"[{event['seq']}] {event['message_type']}")

            # 处理不同类型的消息
            if event['message_type'] == 'AssistantMessage':
                content = event['data']['content'][0]['text']
                print(f"  AI 回复: {content[:100]}...")

            elif event['message_type'] == 'ToolResultMessage':
                tool_name = event['data'].get('tool_name', 'unknown')
                print(f"  工具结果: {tool_name}")

    finally:
        await message_bus.close()

# 使用示例
asyncio.run(monitor_session("20251216T103000_1234_abcd1234"))
```

### 2. 订阅实例消息

```python
from src.session.query.session_query import subscribe_instance_messages

async def monitor_instance(instance_name: str):
    """监控特定实例的所有消息"""
    message_bus = MessageBus.from_config()
    await message_bus.connect()

    message_count = 0

    try:
        async for event in subscribe_instance_messages(instance_name, message_bus):
            message_count += 1
            print(f"消息 #{message_count}: {event['session_id']}")

            # 实时统计
            if message_count % 10 == 0:
                print(f"已处理 {message_count} 条消息")

    finally:
        await message_bus.close()

# 使用示例
asyncio.run(monitor_instance("demo_agent"))
```

### 3. 高级订阅模式

```python
import asyncio
from typing import Dict, Set

class MessageAggregator:
    """消息聚合器，支持多会话监控"""

    def __init__(self, message_bus: MessageBus):
        self.message_bus = message_bus
        self.active_sessions: Dict[str, int] = {}
        self.message_types: Set[str] = set()

    async def monitor_multiple_sessions(self, session_ids: List[str]):
        """同时监控多个会话"""
        tasks = []

        for session_id in session_ids:
            task = asyncio.create_task(
                self._monitor_session(session_id)
            )
            tasks.append(task)

        await asyncio.gather(*tasks)

    async def _monitor_session(self, session_id: str):
        """监控单个会话并更新统计"""
        async for event in subscribe_session_messages(session_id, self.message_bus):
            # 更新统计
            self.active_sessions[session_id] = self.active_sessions.get(session_id, 0) + 1
            self.message_types.add(event['message_type'])

            # 实时处理
            await self._process_message(event)

    async def _process_message(self, event: dict):
        """处理收到的消息"""
        # 这里可以实现自定义的消息处理逻辑
        pass

    def get_statistics(self):
        """获取统计信息"""
        return {
            "active_sessions": len(self.active_sessions),
            "total_messages": sum(self.active_sessions.values()),
            "message_types": list(self.message_types)
        }

# 使用示例
async def advanced_monitoring():
    message_bus = MessageBus.from_config()
    await message_bus.connect()

    aggregator = MessageAggregator(message_bus)

    # 监控多个会话
    sessions = ["session1", "session2", "session3"]
    monitor_task = asyncio.create_task(
        aggregator.monitor_multiple_sessions(sessions)
    )

    # 定期打印统计
    async def print_stats():
        while True:
            await asyncio.sleep(10)
            stats = aggregator.get_statistics()
            print(f"统计信息: {stats}")

    stats_task = asyncio.create_task(print_stats())

    # 运行一段时间后停止
    await asyncio.sleep(60)
    monitor_task.cancel()
    stats_task.cancel()

    await message_bus.disconnect()

asyncio.run(advanced_monitoring())
```

## 性能优化

### 1. 批量操作优化

```python
# 配置建议
redis:
  max_connections: 50          # 根据并发量调整

async_write:
  batch_size: 20              # 增加批量大小（但不要太大）
  flush_interval: 0.5         # 减少刷新间隔，提高实时性
```

### 2. 内存优化

```python
# 限制内存使用
async_write:
  max_memory_messages: 500    # 减少内存消息数量
  backup_enabled: true        # 启用备份防止丢失
```

### 3. 网络优化

```python
# Redis 连接优化
redis:
  socket_keepalive: true      # 启用 socket keepalive
  socket_connect_timeout: 5   # 连接超时
  socket_timeout: 10          # 读写超时
```

### 4. 消息压缩

```python
publishing:
  compress_large_messages: true
  compression_threshold: 1024  # 大于1KB的消息压缩
```

## 监控和调试

### 1. 启用调试日志

```python
import logging

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 特定模块的日志
logging.getLogger("src.session.streaming").setLevel(logging.DEBUG)
logging.getLogger("src.session.storage").setLevel(logging.DEBUG)
```

### 2. 性能监控

```python
import time
from contextlib import asynccontextmanager

@asynccontextmanager
async def measure_performance(operation_name: str):
    """测量操作性能"""
    start_time = time.time()
    start_memory = get_memory_usage()

    try:
        yield
    finally:
        end_time = time.time()
        end_memory = get_memory_usage()

        print(f"{operation_name}:")
        print(f"  耗时: {end_time - start_time:.3f}s")
        print(f"  内存变化: {end_memory - start_memory:.2f}MB")

# 使用示例
async async publish_with_monitoring(message_bus, channel, message):
    async with measure_performance("消息发布"):
        await message_bus.publish(channel, message)
```

### 3. 健康检查

```python
async def health_check(message_bus: MessageBus) -> dict:
    """检查消息总线健康状态"""
    status = {
        "redis_connected": message_bus.is_connected,
        "pool_size": getattr(message_bus, 'pool_size', 0),
        "last_error": None
    }

    # 测试发布和订阅
    test_channel = "health_check_test"
    test_message = {"test": True, "timestamp": time.time()}

    try:
        # 发布测试消息
        await message_bus.publish(test_channel, test_message)

        # 尝试订阅（带超时）
        received = False
        timeout = 5.0

        async for msg in message_bus.subscribe(test_channel):
            if msg.get("test"):
                received = True
                break

        status["pubsub_test"] = "PASS" if received else "FAIL"

    except Exception as e:
        status["pubsub_test"] = f"ERROR: {e}"
        status["last_error"] = str(e)

    return status
```

### 4. 监控面板示例

```python
import asyncio
from datetime import datetime
from collections import defaultdict, deque

class RealTimeMonitor:
    """实时监控面板"""

    def __init__(self, message_bus: MessageBus):
        self.message_bus = message_bus
        self.metrics = defaultdict(int)
        self.message_timeline = deque(maxlen=1000)
        self.active_sessions = set()

    async def start_monitoring(self):
        """启动监控"""
        # 订阅所有消息
        subscribe_task = asyncio.create_task(
            self._subscribe_all_messages()
        )

        # 定期报告
        report_task = asyncio.create_task(
            self._generate_reports()
        )

        await asyncio.gather(subscribe_task, report_task)

    async def _subscribe_all_messages(self):
        """订阅所有消息并收集指标"""
        async for event in self.message_bus.subscribe("messages:*"):
            # 更新指标
            self.metrics["total_messages"] += 1
            self.metrics[f"type_{event['message_type']}"] += 1
            self.metrics[f"instance_{event['instance_name']}"] += 1

            # 记录时间线
            self.message_timeline.append({
                "timestamp": datetime.now(),
                "session_id": event["session_id"],
                "type": event["message_type"]
            })

            # 跟踪活跃会话
            self.active_sessions.add(event["session_id"])

    async def _generate_reports(self):
        """定期生成报告"""
        while True:
            await asyncio.sleep(30)  # 每30秒生成一次报告

            print("\n=== 实时监控报告 ===")
            print(f"总消息数: {self.metrics['total_messages']}")
            print(f"活跃会话数: {len(self.active_sessions)}")
            print(f"消息类型分布:")
            for key, value in self.metrics.items():
                if key.startswith("type_"):
                    print(f"  {key[5:]}: {value}")

            # 清理过期会话（5分钟无活动）
            cutoff = datetime.now().timestamp() - 300
            self.active_sessions = {
                sid for sid in self.active_sessions
                if any(
                    msg["timestamp"].timestamp() > cutoff
                    for msg in self.message_timeline
                    if msg["session_id"] == sid
                )
            }

# 使用示例
async def run_monitor():
    message_bus = MessageBus.from_config()
    await message_bus.connect()

    monitor = RealTimeMonitor(message_bus)
    await monitor.start_monitoring()
```

## 部署指南

### 1. Redis 部署

#### Docker 部署（推荐）

```bash
# 创建 Redis 容器
docker run -d \
  --name claude-redis \
  -p 6379:6379 \
  -v redis_data:/data \
  redis:7-alpine \
  redis-server --appendonly yes
```

#### Docker Compose 部署

```yaml
# docker-compose.yml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    container_name: claude-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    restart: unless-stopped

  claude-agent:
    build: .
    depends_on:
      - redis
    environment:
      - REDIS_URL=redis://redis:6379
    volumes:
      - ./instances:/app/instances
      - ./streaming.yaml:/app/streaming.yaml

volumes:
  redis_data:
```

### 2. 生产环境配置

```yaml
# streaming.yaml (生产环境)
redis:
  url: "redis://redis-cluster:6379"
  db: 0
  max_connections: 100
  password: ${REDIS_PASSWORD}        # 从环境变量读取
  ssl: true                          # 启用 SSL
  ssl_cert_reqs: "required"

async_write:
  batch_size: 50                     # 更大的批量
  flush_interval: 0.5                # 更频繁的刷新
  backup_enabled: true
  backup_retention_days: 7           # 备份保留7天

publishing:
  enabled: true
  channel_prefix: "messages"
  include_metadata: true
  compress_large_messages: true
  compression_threshold: 512

# 监控配置
monitoring:
  metrics_enabled: true
  health_check_interval: 30
  alert_thresholds:
    message_latency: 1000            # 延迟超过1秒报警
    error_rate: 0.05                 # 错误率超过5%报警
```

### 3. 高可用部署

```yaml
# Redis Sentinel 配置
redis:
  url: "redis://redis-master:6379"
  sentinels:
    - host: "redis-sentinel-1"
      port: 26379
    - host: "redis-sentinel-2"
      port: 26379
    - host: "redis-sentinel-3"
      port: 26379
  service_name: "mymaster"
  password: ${REDIS_PASSWORD}
```

### 4. 监控和告警

#### Prometheus 指标

```python
from prometheus_client import Counter, Histogram, Gauge

# 定义指标
message_counter = Counter(
    'claude_messages_total',
    'Total messages processed',
    ['instance', 'message_type']
)

message_latency = Histogram(
    'claude_message_latency_seconds',
    'Message processing latency'
)

active_sessions = Gauge(
    'claude_active_sessions',
    'Number of active sessions'
)

# 在消息处理中更新指标
async def publish_metrics(event: dict):
    message_counter.labels(
        instance=event['instance_name'],
        message_type=event['message_type']
    ).inc()

    # 计算延迟
    latency = time.time() - iso8601_to_timestamp(event['timestamp'])
    message_latency.observe(latency)
```

#### Grafana 仪表板

建议监控以下指标：
- 消息吞吐量（消息/秒）
- 消息延迟分布
- Redis 连接池状态
- 活跃会话数
- 错误率

## 故障排除

### 常见问题

1. **Redis 连接失败**
   ```
   错误: Connection refused
   解决: 检查 Redis 服务状态和网络连通性
   ```

2. **消息丢失**
   ```
   症状: 订阅者收不到部分消息
   原因: 网络中断或客户端重启
   解决: 启用消息持久化（AOF/RDB）
   ```

3. **内存泄漏**
   ```
   症状: 内存持续增长
   原因: 订阅者没有正确处理消息
   解决: 检查订阅循环和缓冲区清理
   ```

4. **性能问题**
   ```
   症状: 消息延迟高
   原因: 批量大小过大或 Redis 负载高
   解决: 调整批量参数和 Redis 配置
   ```

### 调试技巧

1. **启用 Redis 慢查询日志**
   ```bash
   CONFIG SET slowlog-log-slower-than 10000
   CONFIG SET slowlog-max-len 128
   ```

2. **监控 Redis 内存使用**
   ```bash
   redis-cli info memory
   redis-cli info stats
   ```

3. **检查消息积压**
   ```python
   # 检查未处理消息
   async def check_backlog(message_bus):
       for channel in ["messages:session:*", "messages:instance:*"]:
           pending = await message_bus.redis.pubsub_numsub(channel)
           if pending > 1000:
               print(f"警告: 频道 {channel} 有 {pending} 条积压消息")
   ```

## 总结

实时消息系统提供了：

- **低延迟**: 消息推送延迟 < 100ms
- **高可用**: 支持集群和哨兵模式
- **可扩展**: 支持水平扩展
- **可靠**: 双层存储确保消息不丢失
- **易监控**: 完整的指标和监控支持

合理配置和使用实时消息系统，可以构建高性能、高可靠的消息处理应用。