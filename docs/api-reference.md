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

### Session

会话对象，表示一次完整的对话。

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

##### record_message()

```python
async def record_message(self, message: Message) -> None:
```

记录新消息。

**参数**:
- `message` (Message): 消息对象

##### finalize()

```python
async def finalize(self) -> None:
```

完成会话并写入统计数据。

##### get_statistics()

```python
def get_statistics(self) -> Statistics:
```

获取会话统计信息。

**返回**:
- `Statistics`: 统计信息对象

### SessionManager

会话管理器，负责创建和管理会话。

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
def create_session(
    self,
    parent_session_id: Optional[str] = None
) -> Session:
```

创建新会话。

**参数**:
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
    limit: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
```

列出会话。

**参数**:
- `limit` (int): 限制数量
- `offset` (int): 偏移量

**返回**:
- `List[Dict[str, Any]]`: 会话信息列表

## 消息总线 API

### MessageBus

全局消息总线，负责 Redis Pub/Sub 消息的发布和订阅。

#### 类方法

##### from_config()

```python
@classmethod
def from_config(
    cls,
    config_path: Optional[str] = None
) -> 'MessageBus':
```

从配置文件创建 MessageBus 实例。

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

##### disconnect()

```python
async def disconnect(self) -> None:
```

断开 Redis 连接。

##### publish()

```python
async def publish(
    self,
    channel: str,
    message: Dict[str, Any]
) -> bool:
```

发布消息到指定频道。

**参数**:
- `channel` (str): 频道名称
- `message` (Dict[str, Any]): 消息内容

**返回**:
- `bool`: 发布是否成功

##### subscribe()

```python
async def subscribe(
    self,
    *channels: str
) -> AsyncIterator[Dict[str, Any]]:
```

订阅一个或多个频道。

**参数**:
- `*channels` (str): 频道名称列表

**返回**:
- `AsyncIterator[Dict[str, Any]]`: 消息迭代器

##### close()

```python
async def close(self) -> None:
```

关闭消息总线，释放所有资源。

#### 属性

- `is_connected` (bool): 连接状态

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
# Claude 自动生成的调用
await sub_claude_code_reviewer(
    task="审查这段代码的安全性",
    parent_session_id="parent_session_id",
    context_files=["src/auth.py"],
    output_format="markdown"
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
    def __init__(self, session_id: str):
        self.session_id = session_id

    def __aiter__(self) -> AsyncIterator[Message]:
        """异步迭代器接口"""
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

消息基类。

```python
class Message(ABC):
    def __init__(self, role: str, content: List[Any]):
        self.role = role
        self.content = content
        self.timestamp = datetime.now()
```

#### UserMessage

```python
class UserMessage(Message):
    def __init__(self, content: List[TextBlock]):
        super().__init__("user", content)
```

#### AssistantMessage

```python
class AssistantMessage(Message):
    def __init__(self, content: List[TextBlock], model: str):
        super().__init__("assistant", content)
        self.model = model
```

#### ToolUseMessage

```python
class ToolUseMessage(Message):
    def __init__(self, tool_name: str, tool_args: Dict[str, Any]):
        super().__init__("tool_use", [])
        self.tool_name = tool_name
        self.tool_args = tool_args
```

#### ToolResultMessage

```python
class ToolResultMessage(Message):
    def __init__(self, tool_name: str, result: Any, error: Optional[str] = None):
        super().__init__("tool_result", [])
        self.tool_name = tool_name
        self.result = result
        self.error = error
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
redis:
  url: str             # Redis URL
  db: int             # 数据库编号
  max_connections: int # 最大连接数
  password: str       # 密码（可选）
  ssl: bool          # 是否启用 SSL

async_write:
  batch_size: int     # 批量大小
  flush_interval: float # 刷新间隔
  backup_enabled: bool # 是否启用备份

publishing:
  enabled: bool       # 是否启用发布
  channel_prefix: str # 频道前缀
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