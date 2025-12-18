# API 参考

本文档提供了 Claude Agent System 的完整 API 参考。

## 目录

- [AgentSystem](#agentsystem)
- [ConfigManager](#configmanager)
- [会话系统 API](#会话系统-api)
- [消息总线 API](#消息总线-api)
- [查询 API](#查询-api)
- [工具 API](#工具-api)
- [子实例 API](#子实例-api)
- [错误处理](#错误处理)

## AgentSystem

主类，用于管理和运行 Claude Agent 实例。

### 构造函数

```python
class AgentSystem:
    def __init__(
        self,
        instance_name: str,
        instances_root: Optional[str] = None,
        message_bus: Optional[MessageBus] = None
    ):
```

**参数**:
- `instance_name` (str): 实例名称或路径
- `instances_root` (Optional[str]): 实例根目录路径，默认为当前目录下的 `instances/`
- `message_bus` (Optional[MessageBus]): 全局消息总线实例，可选

### 方法

#### initialize()

```python
async def initialize(self) -> None:
```

初始化 Agent 系统，加载配置并启动 MCP 服务器。

**异常**:
- `AgentSystemError`: 初始化失败时抛出

**示例**:
```python
agent = AgentSystem("demo_agent")
await agent.initialize()
```

#### query()

```python
async def query(
    self,
    prompt: str,
    record_session: bool = True,
    resume_session_id: Optional[str] = None,
    parent_session_id: Optional[str] = None
) -> QueryStream:
```

执行查询并返回消息流。

**参数**:
- `prompt` (str): 查询提示词
- `record_session` (bool): 是否记录会话，默认 True
- `resume_session_id` (Optional[str]): 恢复的会话ID
- `parent_session_id` (Optional[str]): 父会话ID（子实例调用时使用）

**返回**:
- `QueryStream`: 异步消息流对象

**示例**:
```python
stream = await agent.query("分析这段代码")
async for message in stream:
    if isinstance(message, AssistantMessage):
        for block in message.content:
            if isinstance(block, TextBlock):
                print(block.text)
```

#### query_text()

```python
async def query_text(
    self,
    prompt: str,
    record_session: bool = True,
    resume_session_id: Optional[str] = None,
    parent_session_id: Optional[str] = None
) -> QueryResult:
```

执行查询并返回文本结果。

**参数**:
- 同 `query()` 方法

**返回**:
- `QueryResult`: 包含结果和会话ID的对象

**示例**:
```python
result = await agent.query_text("计算 123 + 456")
print(f"结果: {result.result}")
print(f"会话ID: {result.session_id}")
```

#### 使用实时消息（新架构）

```python
import asyncio
from src import AgentSystem
from src.session import MessageBus, SessionQuery

async def main():
    # 创建 MessageBus
    message_bus = MessageBus.from_config()
    await message_bus.connect()

    try:
        # 创建 Agent
        agent = AgentSystem("demo_agent", message_bus=message_bus)
        await agent.initialize()

        # 执行查询（后台运行）
        query_task = asyncio.create_task(
            agent.query_text("请调用子实例分析项目")
        )

        # 等待 session 创建
        await asyncio.sleep(1.0)

        # 获取 session_id 并开始订阅
        from src.session.utils import SessionContext
        session_id = SessionContext.get_current_session()

        if session_id:
            # 🎉 新的统一查询服务
            query = SessionQuery("demo_agent", message_bus=message_bus)

            # 开始订阅（自动追踪子实例）
            await query.subscribe(
                session_id=session_id,
                on_parent_message=lambda msg: print(f"[父消息] {msg['type']}"),
                on_child_message=lambda child_id, instance, msg: print(
                    f"[子消息-{instance}] {msg['type']}"
                ),
                on_child_started=lambda child_id, instance: print(
                    f"🔔 子实例启动: {instance}"
                )
            )

            # 等待查询完成
            result = await query_task
            await query.stop()

        agent.cleanup()
    finally:
        await message_bus.close()

asyncio.run(main())
```

#### 会话查询示例（新架构）

```python
from src.session import SessionQuery

# 创建查询实例
query = SessionQuery("demo_agent")

# 基础查询
details = query.get_session_details("20241218T140000_1000_parent123")
sessions = query.list_sessions(status="completed")

# 高级查询
results = query.search_sessions("文件分析", field="initial_prompt")
stats = query.get_statistics_summary(recent_days=7)

# 会话树构建
tree = await query.build_session_tree("parent_session_id")
flat_list = query.flatten_tree(tree)

# 导出功能
query.export_session("session_id", Path("export.json"), format="json")
```

#### cleanup()

```python
def cleanup(self) -> None:
```

清理资源，停止 MCP 服务器。

**示例**:
```python
try:
    result = await agent.query_text("你好")
finally:
    agent.cleanup()
```

### 属性

- `agent_name` (str): Agent 名称
- `agent_description` (str): Agent 描述
- `tools_count` (int): 工具数量
- `sub_instances_count` (int): 子实例数量

## ConfigManager

配置管理器，统一处理所有配置相关功能。

### 构造函数

```python
class ConfigManager:
    def __init__(self, instance_path: str):
```

**参数**:
- `instance_path` (str): 实例路径

### 方法

#### load_config()

```python
def load_config(self) -> Dict[str, Any]:
```

加载并验证主配置文件。

**返回**:
- `Dict[str, Any]`: 配置字典

#### load_mcp_config()

```python
def load_mcp_config(self) -> Dict[str, Dict[str, Any]]:
```

加载 MCP 服务器配置。

**返回**:
- `Dict[str, Dict[str, Any]]`: MCP 配置字典

#### validate_config()

```python
def validate_config(self, config: Dict[str, Any]) -> None:
```

验证配置结构。

**参数**:
- `config` (Dict[str, Any]): 要验证的配置

**异常**:
- `ValueError`: 配置无效时抛出

#### resolve_path()

```python
def resolve_path(self, path: str) -> Path:
```

解析路径（相对或绝对）。

**参数**:
- `path` (str): 路径字符串

**返回**:
- `Path`: 解析后的路径对象

#### get_claude_options_dict()

```python
def get_claude_options_dict(self) -> Dict[str, Any]:
```

生成 Claude SDK 配置参数。

**返回**:
- `Dict[str, Any]`: SDK 配置字典

### 属性

- `config` (Dict[str, Any]): 已加载的配置
- `agent_name` (str): Agent 名称
- `agent_description` (str): Agent 描述
- `mcp_config` (Dict[str, Dict[str, Any]]): MCP 配置

### 便捷函数

```python
def load_mcp_config(instance_path: str) -> Dict[str, Dict[str, Any]]:
    """加载 MCP 配置（无需实例化）"""

def merge_mcp_configs(
    sdk_config: Dict[str, Any],
    external_config: Dict[str, Any]
) -> Dict[str, Any]:
    """合并 SDK 和外部 MCP 配置"""
```

## 会话系统 API

### SessionQuery 🌟

> **重要说明**：SessionQuery 是新架构的**统一查询服务**，整合了会话查询、实时消息订阅和会话树构建功能。推荐使用 SessionQuery 作为主要接口。

SessionQuery 提供完整的会话查询和实时订阅功能。

#### 构造函数

```python
class SessionQuery:
    def __init__(
        self,
        instance_name: str,
        instances_root: Optional[Path] = None,
        message_bus: Optional["MessageBus"] = None
    ):
```

**参数**:
- `instance_name` (str): 实例名称
- `instances_root` (Optional[Path]): 实例根目录路径
- `message_bus` (Optional["MessageBus"]): 消息总线实例，用于实时订阅

### 基础查询功能

#### get_session_details()

```python
def get_session_details(
    self,
    session_id: str,
    include_messages: bool = False,
    message_limit: Optional[int] = 100
) -> Dict[str, Any]:
```

获取会话的完整信息，包括元数据、统计信息、消息和子会话。

**参数**:
- `session_id` (str): 会话 ID
- `include_messages` (bool): 是否包含消息内容（默认 False）
- `message_limit` (Optional[int]): 消息数量限制（默认 100）

**返回**:
```python
{
    "metadata": {
        "session_id": "20241218T140000_1000_abc123",
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

#### get_session_messages()

```python
def get_session_messages(
    self,
    session_id: str,
    message_types: Optional[List[str]] = None,
    limit: int = 1000
) -> List[Dict[str, Any]]:
```

获取会话的详细消息列表。

**参数**:
- `session_id` (str): 会话 ID
- `message_types` (Optional[List[str]]): 过滤消息类型，如 ["ToolUseMessage", "ResultMessage"]
- `limit` (int): 限制返回数量

**返回**:
- `List[Dict[str, Any]]`: 消息列表

#### list_sessions()

```python
def list_sessions(
    self,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
```

列出会话，支持过滤和分页。

**参数**:
- `status` (Optional[str]): 状态过滤 (`running/completed/failed`)
- `limit` (int): 返回数量限制
- `offset` (int): 偏移量

**返回**:
- `List[Dict[str, Any]]`: 会话列表

### 高级查询功能

#### search_sessions()

```python
def search_sessions(
    self,
    query: str,
    field: str = "initial_prompt",
    limit: int = 50
) -> List[Dict[str, Any]]:
```

在会话中搜索关键词。

**参数**:
- `query` (str): 搜索关键词
- `field` (str): 搜索字段 (`initial_prompt/result`)
- `limit` (int): 返回数量限制

**返回**:
- `List[Dict[str, Any]]`: 搜索结果

#### get_statistics_summary()

```python
def get_statistics_summary(self, recent_days: Optional[int] = None) -> Dict[str, Any]:
```

获取会话统计摘要。

**参数**:
- `recent_days` (Optional[int]): 只统计最近N天的会话（可选，None 表示统计全部）

**返回统计信息**:
- 总会话数、完成数、失败数
- 总消息数、工具调用数
- 总成本、平均耗时

#### export_session()

```python
def export_session(
    self,
    session_id: str,
    output_file: Path,
    format: str = "json",
    include_messages: bool = True
) -> None:
```

将会话导出为文件。

**参数**:
- `session_id` (str): 会话 ID
- `output_file` (Path): 输出文件路径
- `format` (str): 导出格式（`json`, `jsonl`, `text`）
- `include_messages` (bool): 是否包含消息内容

**支持格式**:
- `json`: 标准 JSON 格式
- `jsonl`: JSON Lines 格式
- `text`: 可读文本格式

### 管理功能

#### cleanup_sessions()

```python
def cleanup_sessions(
    self,
    retention_days: int = 30,
    dry_run: bool = False
) -> Dict[str, Any]:
```

清理过期会话（代理到 SessionManager）。

**参数**:
- `retention_days` (int): 保留天数（默认 30）
- `dry_run` (bool): 是否模拟运行，不实际删除（默认 False）

**返回**:
- `Dict[str, Any]`: 清理报告，包含删除的会话数量和详细信息

### 实时订阅功能 🚀

#### subscribe()

```python
async def subscribe(
    self,
    session_id: str,
    on_parent_message: Optional[Callable[[Any], None]] = None,
    on_child_message: Optional[Callable[[str, str, Any], None]] = None,
    on_child_started: Optional[Callable[[str, str], None]] = None,
    auto_start: bool = True
) -> None:
```

开始订阅会话消息，自动追踪子实例。

**参数**:
- `session_id` (str): 父会话 ID
- `on_parent_message` (Optional[Callable[[Any], None]]): 父实例消息回调
- `on_child_message` (Optional[Callable[[str, str, Any], None]]): 子实例消息回调
- `on_child_started` (Optional[Callable[[str, str], None]]): 子实例启动回调
- `auto_start` (bool): 是否自动启动订阅任务

**回调函数参数**:
- `on_parent_message`: `(message: Any) -> None`
- `on_child_message`: `(child_session_id: str, instance_name: str, message: Any) -> None`
- `on_child_started`: `(child_session_id: str, instance_name: str) -> None`

**核心特性**:
- ✅ 自动订阅所有子实例
- ✅ 实时检测子实例启动
- ✅ 区分父子消息来源
- ✅ 支持多层嵌套

#### 生命周期管理

```python
async def start(self) -> None:
    """启动订阅任务"""

async def stop(self) -> None:
    """停止所有订阅"""

async def wait(self, timeout: Optional[float] = None) -> None:
    """等待订阅完成"""

def is_running(self) -> bool:
    """检查订阅器是否正在运行"""

def get_child_sessions(self) -> Dict[str, str]:
    """获取所有子会话 {child_session_id: instance_name}"""
```

### 会话树构建功能 🌳

#### build_session_tree()

```python
async def build_session_tree(
    self,
    session_id: str,
    instance_name: Optional[str] = None,
    include_messages: bool = True,
    max_depth: int = 10
) -> Dict[str, Any]:
```

递归构建会话关系树。

**参数**:
- `session_id` (str): 根会话 ID
- `instance_name` (Optional[str]): 实例名称（可选）
- `include_messages` (bool): 是否包含消息内容
- `max_depth` (int): 最大递归深度

**返回**:
```python
{
    "session_id": "parent_id",
    "instance_name": "demo_agent",
    "depth": 0,
    "metadata": {...},
    "statistics": {...},
    "subsessions": [
        {
            "session_id": "child_id",
            "instance_name": "file_analyzer",
            "depth": 1,
            "subsessions": [...]
        }
    ]
}
```

#### flatten_tree()

```python
def flatten_tree(self, tree: Dict[str, Any]) -> List[Dict[str, Any]]:
```

将树形结构展平为列表。

**参数**:
- `tree` (Dict[str, Any]): 会话树

**返回**:
- `List[Dict[str, Any]]`: 展平后的会话列表

### Session

会话对象，表示一次完整的对话。（底层实现类，一般用户无需直接使用）

#### 构造函数

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

#### 方法

##### start()

```python
async def start(self) -> None:
```

初始化会话目录和元数据。

##### record_message()

```python
async def record_message(self, message: Message) -> None:
```

记录新消息，包含实时消息发布和异步写入。

**参数**:
- `message` (Message): 消息对象

##### finalize()

```python
async def finalize(self, result_message: Optional[Message] = None) -> None:
```

完成会话并写入统计数据。

**参数**:
- `result_message` (Optional[Message]): 最终结果消息

##### get_messages()

```python
def get_messages(
    self,
    message_types: Optional[List[str]] = None,
    limit: Optional[int] = None,
    reverse: bool = False
) -> Iterator[Dict[str, Any]]:
```

获取会话消息列表。

**参数**:
- `message_types` (Optional[List[str]]): 过滤消息类型
- `limit` (Optional[int]): 限制返回数量
- `reverse` (bool): 是否反转顺序

**返回**:
- `Iterator[Dict[str, Any]]`: 消息迭代器

##### get_metadata()

```python
def get_metadata(self) -> Dict[str, Any]:
```

获取会话元数据。

**返回**:
- `Dict[str, Any]`: 元数据字典

##### get_statistics()

```python
def get_statistics(self) -> Statistics:
```

获取会话统计信息。

**返回**:
- `Statistics`: 统计信息对象

### SessionManager

会话管理器，负责创建和管理会话。（底层实现类，一般用户无需直接使用）

#### 构造函数

```python
class SessionManager:
    def __init__(
        self,
        instance_name: str,
        sessions_root: Path,
        message_bus: Optional[MessageBus] = None
    ):
```

#### 方法

##### create_session()

```python
async def create_session(
    self,
    initial_prompt: str = "",
    context: Optional[Dict[str, Any]] = None,
    parent_session_id: Optional[str] = None
) -> Session:
```

创建新会话。

**参数**:
- `initial_prompt` (str): 初始提示词
- `context` (Optional[Dict[str, Any]]): 上下文信息
- `parent_session_id` (Optional[str]): 父会话ID

**返回**:
- `Session`: 新创建的会话对象

##### get_session()

```python
def get_session(self, session_id: str) -> Optional[Session]:
```

获取现有会话。

**参数**:
- `session_id` (str): 会话ID

**返回**:
- `Optional[Session]`: 会话对象或 None

##### list_sessions()

```python
def list_sessions(
    self,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> List[Dict[str, Any]]:
```

列出会话。

**参数**:
- `status` (Optional[str]): 状态过滤
- `limit` (int): 限制数量（默认 100）
- `offset` (int): 偏移量（默认 0）

**返回**:
- `List[Dict[str, Any]]`: 会话信息列表

##### cleanup_old_sessions()

```python
def cleanup_old_sessions(
    self,
    retention_days: int = 30,
    dry_run: bool = False
) -> Dict[str, Any]:
```

清理过期会话。

**参数**:
- `retention_days` (int): 保留天数
- `dry_run` (bool): 是否模拟运行

**返回**:
- `Dict[str, Any]`: 清理报告

### QueryStreamManager

查询流生命周期管理器，负责管理查询流和会话。（内部使用，一般用户无需直接操作）

#### 构造函数

```python
class QueryStreamManager:
    def __init__(
        self,
        stream: Any,
        session_manager: Optional[SessionManager] = None,
        record_session: bool = True,
        prompt: Optional[str] = None,
        resume_session_id: Optional[str] = None,
        parent_session_id: Optional[str] = None,
        instance_path: Optional[str] = None
    ):
```

**参数**:
- `stream` (Any): SDK 返回的查询流
- `session_manager` (Optional[SessionManager]): 会话管理器
- `record_session` (bool): 是否记录会话
- `prompt` (Optional[str]): 查询提示词
- `resume_session_id` (Optional[str]): 要恢复的会话 ID
- `parent_session_id` (Optional[str]): 父会话 ID
- `instance_path` (Optional[str]): 实例路径

#### 方法

##### initialize()

```python
async def initialize(self) -> None:
```

初始化 session（创建新会话或恢复已有会话）。

##### finalize_on_result()

```python
async def finalize_on_result(self, result_message: Message) -> None:
```

在收到 ResultMessage 时 finalize（幂等操作）。

**参数**:
- `result_message` (Message): ResultMessage 对象

##### 使用示例

```python
async with QueryStreamManager(stream, session_manager) as stream_manager:
    async for message in stream_manager:
        # 处理消息
        pass
```

### SessionContext

Session 上下文管理器，用于在进程间传递会话信息。使用临时文件存储当前查询的 session_id，允许 MCP 服务器子进程自动读取父 session_id。

#### 类方法

##### set_current_session()

```python
@classmethod
def set_current_session(cls, session_id: str, instance_path: str) -> None:
```

设置当前会话上下文（写入临时文件）。

**参数**:
- `session_id` (str): 会话 ID
- `instance_path` (str): 实例路径

##### get_current_session()

```python
@classmethod
def get_current_session(cls, pid: Optional[int] = None) -> Optional[str]:
```

获取当前会话 ID（从临时文件读取）。

**参数**:
- `pid` (Optional[int]): 进程 ID，默认使用当前进程

**返回**:
- `Optional[str]`: 会话 ID，如果不存在则返回 None

##### clear_current_session()

```python
@classmethod
def clear_current_session(cls, pid: Optional[int] = None) -> None:
```

清除当前会话上下文（删除临时文件）。

**参数**:
- `pid` (Optional[int]): 进程 ID，默认使用当前进程

##### cleanup_all()

```python
@classmethod
def cleanup_all(cls) -> None:
```

清理所有临时文件（启动时调用，清理上次未清理的文件）。

### QueryStreamManager

查询流生命周期管理器，负责管理查询流和会话。（内部使用，一般用户无需直接操作）

#### 构造函数

```python
class QueryStreamManager:
    def __init__(
        self,
        stream: Any,
        session_manager: Optional[Any] = None,
        record_session: bool = True,
        prompt: Optional[str] = None,
        resume_session_id: Optional[str] = None,
        parent_session_id: Optional[str] = None,
        instance_path: Optional[str] = None
    ):
```

**参数**:
- `stream` (Any): SDK 返回的查询流
- `session_manager` (Optional[Any]): SessionManager 对象
- `record_session` (bool): 是否记录会话
- `prompt` (Optional[str]): 查询提示词
- `resume_session_id` (Optional[str]): 要恢复的会话 ID
- `parent_session_id` (Optional[str]): 父会话 ID
- `instance_path` (Optional[str]): 实例路径

#### 方法

##### initialize()

```python
async def initialize(self) -> None:
```

初始化 session（创建新会话或恢复已有会话）。

##### finalize_on_result()

```python
async def finalize_on_result(self, result_message: Message) -> None:
```

在收到 ResultMessage 时 finalize（幂等操作）。

**参数**:
- `result_message` (Message): ResultMessage 对象

##### 使用示例

```python
async with QueryStreamManager(stream, session_manager) as stream_manager:
    async for message in stream_manager:
        # 处理消息
        pass
```

## 消息总线 API

### MessageBus

全局消息总线，负责 Redis Pub/Sub 消息的发布和订阅。

#### 构造函数

```python
class MessageBus:
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        redis_db: int = 0,
        max_connections: int = 50
    ):
```

**参数**:
- `redis_url` (str): Redis 连接 URL
- `redis_db` (int): Redis 数据库编号
- `max_connections` (int): 连接池最大连接数

#### 类方法

##### from_config()

```python
@classmethod
def from_config(
    cls,
    config_path: Optional[str] = None
) -> 'MessageBus':
```

从配置文件或环境变量加载配置创建 MessageBus 实例。

配置优先级：环境变量 > streaming.yaml > 默认值

**参数**:
- `config_path` (Optional[str]): 配置文件路径

**返回**:
- `MessageBus`: 消息总线实例

#### 实例方法

##### connect()

```python
async def connect(self) -> bool:
```

连接到 Redis。

**返回**:
- `bool`: 连接是否成功

##### publish()

```python
async def publish(
    self,
    channel: str,
    message: dict
) -> bool:
```

发布消息到指定频道。

**参数**:
- `channel` (str): 频道名称
- `message` (dict): 消息内容

**返回**:
- `bool`: 发布是否成功

##### subscribe()

```python
async def subscribe(
    self,
    *channels: str
) -> AsyncIterator[dict]:
```

订阅一个或多个频道。

**参数**:
- `*channels` (str): 频道名称列表

**返回**:
- `AsyncIterator[dict]`: 消息迭代器

##### close()

```python
async def close(self):
```

关闭 Redis 连接。

#### 属性

- `is_connected` (bool): 是否已连接

> **注意**：`SessionSubscriber` 已整合到 `SessionQuery` 中，推荐使用 `SessionQuery.subscribe()` 方法进行订阅。

## 查询 API

### 会话查询函数

#### get_session_details()

```python
def get_session_details(
    instance_name: str,
    session_id: str,
    include_messages: bool = True
) -> Dict[str, Any]:
```

获取会话详情。

**参数**:
- `instance_name` (str): 实例名称
- `session_id` (str): 会话ID
- `include_messages` (bool): 是否包含消息内容

**返回**:
- `Dict[str, Any]`: 会话详情

#### list_sessions()

```python
def list_sessions(
    instance_name: str,
    limit: int = 50,
    offset: int = 0,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> List[Dict[str, Any]]:
```

列出会话。

**参数**:
- `instance_name` (str): 实例名称
- `limit` (int): 限制数量
- `offset` (int): 偏移量
- `date_from` (Optional[str]): 开始日期
- `date_to` (Optional[str]): 结束日期

**返回**:
- `List[Dict[str, Any]]`: 会话列表

#### search_sessions()

```python
def search_sessions(
    instance_name: str,
    query: str,
    limit: int = 50,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> List[Dict[str, Any]]:
```

搜索会话。

**参数**:
- `instance_name` (str): 实例名称
- `query` (str): 搜索关键词
- `limit` (int): 限制数量
- `date_from` (Optional[str]): 开始日期
- `date_to` (Optional[str]): 结束日期

**返回**:
- `List[Dict[str, Any]]`: 搜索结果

#### export_session()

```python
def export_session(
    instance_name: str,
    session_id: str,
    format: str = "json"
) -> str:
```

导出会话。

**参数**:
- `instance_name` (str): 实例名称
- `session_id` (str): 会话ID
- `format` (str): 导出格式（json, markdown, csv）

**返回**:
- `str`: 导出的内容

### SessionTreeBuilder

会话树构建器，用于构建父子会话关系。

#### 方法

##### build_tree()

```python
async def build_tree(
    self,
    session_id: str,
    instance_name: Optional[str] = None,
    include_messages: bool = True,
    max_depth: int = 10
) -> Dict[str, Any]:
```

递归构建会话树。

**参数**:
- `session_id` (str): 根会话ID
- `instance_name` (Optional[str]): 实例名称
- `include_messages` (bool): 是否包含消息内容
- `max_depth` (int): 最大递归深度

**返回**:
- `Dict[str, Any]`: 会话树结构

##### flatten_tree()

```python
def flatten_tree(self, tree: Dict[str, Any]) -> List[Dict[str, Any]]:
```

将树形结构展平为列表。

**参数**:
- `tree` (Dict[str, Any]): 会话树

**返回**:
- `List[Dict[str, Any]]`: 展平后的会话列表

## 工具 API

### 工具定义

工具是通过异步函数定义的：

```python
async def tool_function(
    param1: type1,
    param2: type2 = default_value,
    *args,
    **kwargs
) -> Dict[str, Any]:
    """工具描述

    Args:
        param1: 参数1描述
        param2: 参数2描述

    Returns:
        返回值描述
    """
    # 工具实现
    return {"result": "处理结果"}
```

### 工具命名规则

- **文件名**: `tool_name.py`
- **函数名**: `function_name`
- **工具名**: `tool_name__function_name`
- **MCP 名称**: `mcp__custom_tools__tool_name__function_name`

### 工具管理器

#### ToolManager

工具管理器，负责自动发现和加载工具。

##### 方法

###### load_tools()

```python
def load_tools(self, tools_dir: Path) -> List[Callable]:
```

从指定目录加载所有工具。

**参数**:
- `tools_dir` (Path): 工具目录路径

**返回**:
- `List[Callable]`: 工具函数列表

###### get_tool_info()

```python
def get_tool_info(self, tool_func: Callable) -> Dict[str, Any]:
```

获取工具信息。

**参数**:
- `tool_func` (Callable): 工具函数

**返回**:
- `Dict[str, Any]`: 工具信息字典

## 子实例 API

### SubInstanceTool

子实例工具类，将子实例封装为可调用工具。

#### 参数

- `task` (str): 任务描述（必填）
- `parent_session_id` (str): 父会话ID（必填）
- `context_files` (Optional[List[str]]): 相关文件列表
- `output_format` (str): 输出格式（text/json/markdown）
- `resume_session_id` (Optional[str]): 恢复的子会话ID
- `variables` (Optional[Dict[str, Any]]): 额外变量

#### 使用示例

```python
# Claude 自动生成的调用示例
await sub_code_analyzer(
    task="分析这段代码的复杂度",
    parent_session_id="parent_session_id",
    context_files=["src/main.py"],
    output_format="json"
)
```

## 错误处理

### 异常类

#### AgentSystemError

```python
class AgentSystemError(Exception):
    """Agent 系统错误基类"""
    pass
```

#### ConfigError

```python
class ConfigError(AgentSystemError):
    """配置错误"""
    pass
```

#### ToolError

```python
class ToolError(AgentSystemError):
    """工具执行错误"""
    pass
```

#### SessionError

```python
class SessionError(AgentSystemError):
    """会话错误"""
    pass
```

### 错误处理示例

```python
from src import AgentSystem, AgentSystemError

async def safe_query():
    agent = AgentSystem("demo_agent")

    try:
        await agent.initialize()
        result = await agent.query_text("你好")
        return result
    except ConfigError as e:
        print(f"配置错误: {e}")
    except ToolError as e:
        print(f"工具错误: {e}")
    except SessionError as e:
        print(f"会话错误: {e}")
    except AgentSystemError as e:
        print(f"系统错误: {e}")
    finally:
        agent.cleanup()
```

## 数据类型

### QueryResult

查询结果对象。

```python
@dataclass
class QueryResult:
    result: str                          # 查询结果文本
    session_id: Optional[str]            # 会话ID
```

### QueryStream

查询流对象，实现异步迭代器协议。

```python
class QueryStream:
    def __init__(self, iterator: AsyncIterator[Any], session_id: Optional[str] = None):
        self._iterator = iterator
        self.session_id = session_id

    def __aiter__(self) -> AsyncIterator[Message]:
        """异步迭代器接口"""

    async def __anext__(self) -> Message:
        """异步迭代器的下一个方法"""
```

### Statistics

会话统计信息。

```python
@dataclass
class Statistics:
    total_messages: int = 0
    user_messages: int = 0
    assistant_messages: int = 0
    tool_messages: int = 0
    duration_seconds: float = 0.0
    tokens_used: int = 0
    subsessions: List[Dict[str, Any]] = field(default_factory=list)
```

### Message

消息类型来自 Claude Agent SDK，主要包括：

- `UserMessage`: 用户消息
- `AssistantMessage`: 助手消息
- `ToolUseMessage`: 工具使用消息
- `ToolResultMessage`: 工具结果消息
- `ResultMessage`: 查询结果消息

消息通常包含内容块（blocks），如：
- `TextBlock`: 文本内容块
- `ToolUseBlock`: 工具使用块
- `ToolResultBlock`: 工具结果块

**使用示例**:
```python
from claude_agent_sdk import AssistantMessage, TextBlock

# 检查消息类型并处理
if isinstance(message, AssistantMessage):
    for block in message.content:
        if isinstance(block, TextBlock):
            print(block.text)
```

## 配置选项

### 实例配置

```yaml
agent:
  name: str              # 实例名称
  description: str       # 实例描述

model: str               # Claude 模型
system_prompt_file: str  # 系统提示词文件路径

tools:
  disallowed: List[str]  # 禁止的工具列表
  allowed: List[str]     # 允许的工具列表（支持通配符）

sub_claude_instances:
  key: value            # 子实例映射

session_recording:
  enabled: bool         # 是否启用会话记录
  retention_days: int   # 保留天数
  max_total_size_mb: int # 最大总大小
  auto_cleanup: bool    # 自动清理
  message_types: List[str] # 记录的消息类型

advanced:
  permission_mode: str  # 权限模式
  max_turns: int        # 最大对话轮数
  env: Dict[str, str]   # 环境变量
```

### 实时消息配置

```yaml
# streaming.yaml
redis:
  url: "redis://localhost:6379"  # Redis URL
  db: 0                         # 数据库编号
  max_connections: 50           # 最大连接数

async_write:
  batch_size: 10                # 批量大小
  flush_interval: 1.0          # 刷新间隔（秒）
```

## 最佳实践

1. **资源管理**
   - 始终调用 `cleanup()` 释放资源
   - 使用 try/finally 确保清理

2. **错误处理**
   - 捕获特定的异常类型
   - 记录详细的错误信息

3. **性能优化**
   - 重用 AgentSystem 实例
   - 合理配置批量写入参数
   - 使用会话恢复避免重复初始化

4. **安全性**
   - 验证输入参数
   - 限制工具权限
   - 定期清理过期会话
