# Claude Agent System

基于 Claude Agent SDK (Python) 的可扩展智能体系统，使用 FastMCP + stdio 架构，提供完整的会话记录和管理功能。

## 核心特性

- 📝 **YAML 配置驱动** - 通过简单的 YAML 文件管理 Claude Agent 实例
- 🔧 **自动工具发现** - 自动扫描 `tools/` 目录，无需装饰器，直接写异步函数
- 🏗️ **FastMCP + stdio 架构** - 使用标准 MCP 协议和子进程通信，稳定可靠
- 🔄 **递归子实例** - 子实例作为工具，支持无限层级嵌套
- ⚡ **无状态设计** - 支持并发查询，线程安全
- 📊 **智能会话记录** - 自动记录所有对话，支持层级化存储和查询
- 🔁 **Resume 多轮对话** - 支持恢复之前的会话
- 🧩 **模块化架构** - 会话记录功能独立模块，便于维护和扩展

## 核心设计理念

### 1. FastMCP + stdio 架构

**为什么使用 FastMCP**：
- ✅ **进程隔离**：MCP 服务器运行在独立子进程中，工具崩溃不影响主进程
- ✅ **标准协议**：使用 JSON-RPC over stdio，符合 MCP 规范
- ✅ **更高稳定性**：避免 SDK 本地工具系统的 bug 和限制

**通信流程**：
```
Claude SDK → stdio → MCP 服务器子进程 → 工具执行 → 结果返回
```

**架构图**：
```
AgentSystem
  └─ ToolManager
      └─ ProcessManager (管理子进程)
          └─ FastMCP Server (独立子进程)
              ├─ 本地工具 (tools/*.py)
              └─ 子实例工具 (SubInstanceTool)
```

### 2. 简化的工具格式

**零样板代码**：无需装饰器，直接写异步函数即可成为工具。

```python
# ✅ 当前格式 - 简洁
async def add(a: float, b: float) -> dict:
    """计算两个数字的和"""
    return {"result": a + b}

# 工具自动命名：calculator__add
# 完整 MCP 名称：mcp__custom_tools__calculator__add
```

**自动发现机制**：
- 扫描 `tools/` 目录下的所有 `.py` 文件
- 提取所有异步函数（`async def`）
- 使用函数文档字符串作为工具描述
- 自动注册到 FastMCP 服务器

### 3. 无状态 Agent 设计

**核心理念**：Agent 不保存任何 session 信息，每个查询返回自己的 session_id。

```python
# 支持并发查询
task1 = agent.query_text("任务1")
task2 = agent.query_text("任务2")
results = await asyncio.gather(task1, task2)
# 每个查询都有独立的 session_id
```

**优势**：
- ✅ 支持并发查询
- ✅ 线程安全
- ✅ 简化状态管理

**对比**：
| 设计 | 有状态 Agent | 无状态 Agent（当前） |
|------|--------------|---------------------|
| Session 存储 | `agent.current_session_id` | `result.session_id` |
| 并发查询 | ❌ 不支持 | ✅ 支持 |
| 线程安全 | ❌ 需要加锁 | ✅ 天然安全 |

### 4. 子实例作为工具对象

**设计原则**：子实例不是独立的 MCP 服务器，而是注册到主 MCP 服务器的工具对象。

```
# ✅ 简化后的架构
所有工具和子实例 → 统一的 MCP 服务器子进程 → stdio 通信
```

**SubInstanceTool 特性**：
- 实现 `__call__` 方法，可直接被调用
- 延迟实例化：只在被调用时才创建 `AgentSystem`
- 自动清理：调用完成后自动 `cleanup()`
- 独立会话：子实例的会话记录在子实例自己的 `sessions/` 目录下
- 自动追踪：父实例自动追踪子实例的 `session_id` 并记录到统计信息中

### 5. 会话记录系统

**设计原则**：内存收集 + 一次性写入，KISS 原则（Keep It Simple, Stupid）。

**实现逻辑**：
1. `record_message()` - 将消息追加到内存列表（无 I/O）
2. `finalize()` - 会话结束时一次性写入所有消息
3. 性能优化：每个会话只有 1 次磁盘写入操作
4. 内存友好：写入完成后立即清空内存列表

**会话 ID 格式**：`{timestamp}_{counter}_{short_hash}`
- 示例：`20251211T061755_0001_a3f9c2d8`
- 保证唯一性和可排序性

**目录结构**：
```
instances/
├── parent_agent/sessions/
│   └── 20251211T061755_0001_a3f9c2d8/      # 父实例会话
│       ├── metadata.json                    # 会话元数据
│       ├── messages.jsonl                   # 消息记录（JSON Lines）
│       └── statistics.json                  # 统计信息（包含子会话追踪）
│
└── child_agent/sessions/
    └── 20251211T061800_0001_b4e8d3f9/      # 子实例会话（独立存储）
        ├── metadata.json
        ├── messages.jsonl
        └── statistics.json
```

**说明**：
- 每个实例的会话存储在自己的 `instances/{instance_name}/sessions/` 目录下
- 子实例会话不嵌套在父会话目录中（因为 MCP 子进程隔离）
- 父实例的 `statistics.json` 记录所有调用过的子实例的 `session_id`

**✨ 子实例 Session 自动追踪**：

系统会自动检测并记录子实例的 session_id，实现父子会话关联：

1. **自动提取**：子实例在返回结果时自动嵌入 `<!--SESSION_ID:xxx-->` 标记
2. **智能检测**：父实例检测到子实例工具调用时，自动解析 session_id
3. **关联记录**：将子实例 session_id 保存到父会话的 `statistics.json` 中
4. **完整追踪**：支持递归追踪多层嵌套的子实例调用链

```python
# 父会话的 statistics.json 自动包含：
{
  "subsessions": [
    {
      "session_id": "20251211T061800_0001_b4e8d3f9",  # 子实例的会话 ID
      "tool_name": "mcp__custom_tools__sub_claude_file_analyzer",
      "tool_use_id": "toolu_abc123",
      "timestamp": "2025-12-14T10:30:00"
    }
  ]
}

# 通过 session_id 可以查询子实例的完整会话记录：
# instances/file_analyzer_agent/sessions/20251211T061800_0001_b4e8d3f9/
```

### 6. 延迟实例化

**设计原则**：配置加载时只创建工具定义，工具被调用时才实例化。

```
初始化阶段 (initialize):
  ├─ 加载 config.yaml
  ├─ 发现 tools/ 目录下的工具
  ├─ 创建工具定义（函数签名）
  ├─ 启动 MCP 服务器子进程
  └─ ❌ 不实例化子 Claude（延迟到调用时）

工具调用阶段 (tool execution):
  ├─ Claude 决定调用某个工具
  ├─ ✅ 动态创建 AgentSystem 实例
  ├─ 初始化并执行查询
  └─ 返回结果后自动清理
```

**优势**：节省资源，提高启动速度。

### 7. 递归嵌套支持

**设计原则**：每一层都是完整的 `AgentSystem`，支持无限嵌套。

```
Parent Agent (Session: 20251211T061755_0001_a3f9c2d8)
  ├─ Tool: calculator
  └─ Sub Claude: code_reviewer (Session: 20251211T061800_0001_b4e8d3f9)
       ├─ Tool: lint_checker
       └─ Sub Claude: syntax_analyzer (Session: 20251211T061805_0001_c5e9f4a0)
            └─ Sub Claude: ...（继续嵌套）
```

### 8. Resume 多轮对话

**设计原则**：通过 `resume_session_id` 参数恢复之前的会话。

**行为说明**：
- 新消息追加到原会话的 `messages.jsonl` 文件
- 序列号（seq）自动从之前的消息数量继续递增
- 统计信息覆盖（ResultMessage 包含累计值）
- Claude session_id 在第一条 SystemMessage 时就获取并保存

**使用示例**：
```python
result1 = await agent.query_text("第一个问题")
result2 = await agent.query_text(
    "继续讨论",
    resume_session_id=result1.session_id
)
```

## 快速开始

### 安装

```bash
pip install -r requirements.txt
```

**依赖**：
- `claude-agent-sdk` - Claude Agent SDK
- `mcp>=1.0.0` - Model Context Protocol
- `pyyaml>=6.0` - 配置解析

### 基础使用

```python
import asyncio
from src import AgentSystem

async def main():
    # 初始化 Agent
    agent = AgentSystem("demo_agent")
    await agent.initialize()

    # 执行查询，获取结果和会话 ID
    result = await agent.query_text("计算 123 + 456")
    print(f"结果: {result.result}")
    print(f"会话 ID: {result.session_id}")

    # 继续对话（Resume）
    result2 = await agent.query_text(
        "再计算一下 789 + 012",
        resume_session_id=result.session_id
    )

    # 清理资源
    agent.cleanup()

asyncio.run(main())
```

### 流式访问

```python
async def main():
    agent = AgentSystem("demo_agent")
    await agent.initialize()

    # 流式获取所有消息
    stream = await agent.query("分析这个项目")
    async for message in stream:
        message_type = type(message).__name__
        if message_type == "AssistantMessage":
            # 处理 AI 助手消息
            from claude_agent_sdk import TextBlock
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text, end="", flush=True)

    print(f"\n会话 ID: {stream.session_id}")
```

## 自定义工具开发

### 创建工具

在 `instances/{your_agent}/tools/` 目录下创建 Python 文件，直接写异步函数：

```python
# instances/demo_agent/tools/calculator.py

async def add(a: float, b: float) -> dict:
    """
    计算两个数字的和

    Args:
        a: 第一个数字
        b: 第二个数字

    Returns:
        计算结果
    """
    result = a + b
    return {
        "operation": "add",
        "operands": [a, b],
        "result": result
    }

async def multiply(a: float, b: float) -> dict:
    """计算两个数字的乘积"""
    result = a * b
    return {
        "operation": "multiply",
        "operands": [a, b],
        "result": result
    }
```

**工具命名规则**：
- 文件名：`calculator.py`，函数名：`add`
- 自动生成工具名：`calculator__add`
- 完整 MCP 工具名：`mcp__custom_tools__calculator__add`

**最佳实践**：
- ✅ 使用异步函数（`async def`）
- ✅ 添加类型注解
- ✅ 编写详细的文档字符串
- ✅ 返回结构化字典
- ✅ 处理异常，返回错误信息

## 配置说明

### 完整配置示例

```yaml
# instances/demo_agent/config.yaml

agent:
  name: "demo_agent"
  description: "演示实例"

model: "claude-sonnet-4-5"
system_prompt_file: ".claude/agent.md"  # 推荐使用 agent.md

# 工具权限（内置工具默认全部允许）
tools:
  # 禁止特定内置工具
  disallowed:
    - "WebFetch"
    - "WebSearch"
    - "KillShell"

  # 允许 MCP 工具（自定义工具、外部 MCP、子实例）
  allowed:
    - "mcp__custom_tools__calculator__*"        # 本地工具
    - "mcp__custom_tools__sub_claude_*"         # 子实例工具
    - "mcp__external_database__*"               # 外部 MCP 服务器

# 子实例配置
sub_claude_instances:
  file_analyzer: "file_analyzer_agent"
  syntax_checker: "syntax_checker_agent"

# 会话记录配置
session_recording:
  enabled: true
  retention_days: 30
  max_total_size_mb: 1000
  auto_cleanup: true
  message_types: null  # null 表示记录所有类型（推荐）

# 高级配置
advanced:
  permission_mode: "bypassPermissions"
  max_turns: 100

  # SDK 超时配置（避免子实例崩溃）
  env:
    CLAUDE_CODE_STREAM_CLOSE_TIMEOUT: "300000"  # 5分钟
    MCP_TIMEOUT: "120000"                       # 2分钟
    MCP_TOOL_TIMEOUT: "180000"                  # 3分钟
```

### 工具权限说明

**重要**：内置工具（Read, Write, Bash 等）默认全部允许，要禁止需在 `disallowed` 中明确列出。

`allowed` 列表主要用于限制 MCP 工具：
- **自定义工具**：`tools/` 目录下的异步函数
- **子实例工具**：封装的子 Claude 实例
- **外部 MCP 服务器**：通过 `.mcp.json` 配置的外部服务

支持通配符 `*` 进行模式匹配。

## API 文档

### AgentSystem

主类，用于管理和运行 Claude Agent 实例。

**初始化**：
```python
agent = AgentSystem(
    instance_name="demo_agent",  # 实例名称或路径
    instances_root=None          # 实例根目录（可选）
)
await agent.initialize()
```

**方法**：

- `async query(prompt: str, record_session: bool = True, resume_session_id: Optional[str] = None, parent_session_id: Optional[str] = None) -> QueryStream`
  - 返回可迭代的 QueryStream 对象
  - 包含 `session_id` 属性
  - `parent_session_id` 用于子实例调用，标识父会话

- `async query_text(prompt: str, record_session: bool = True, resume_session_id: Optional[str] = None, parent_session_id: Optional[str] = None) -> QueryResult`
  - 返回 QueryResult 对象（包含 `result` 和 `session_id`）
  - `parent_session_id` 用于子实例调用，标识父会话

- `cleanup()` - 清理资源，停止 MCP 服务器

**属性**：

- `agent_name` - Agent 名称
- `agent_description` - Agent 描述
- `tools_count` - 工具数量
- `sub_instances_count` - 子实例数量

### QueryResult

查询结果对象（`query_text()` 返回）。

**属性**：
- `result: str` - 查询结果文本
- `session_id: Optional[str]` - 会话 ID

### QueryStream

查询流对象（`query()` 返回）。

**特性**：
- 实现异步迭代器协议，可使用 `async for` 遍历
- 包含 `session_id` 属性

### ConfigManager

配置管理器，统一处理所有配置相关功能（重构后的核心组件）。

**初始化**：
```python
from src.config_manager import ConfigManager

manager = ConfigManager("instances/demo_agent")
```

**主要方法**：
- `load_config() -> dict[str, Any]` - 加载并验证主配置文件
- `load_mcp_config() -> dict[str, dict[str, Any]]` - 加载MCP服务器配置
- `validate_config(config: dict[str, Any]) -> None` - 验证配置结构
- `resolve_path(path: str) -> Path` - 解析路径（相对或绝对）
- `get_claude_options_dict() -> dict[str, Any]` - 生成Claude SDK配置参数

**属性**：
- `config` - 获取已加载的配置字典
- `agent_name` - Agent名称
- `agent_description` - Agent描述
- `mcp_config` - 获取已加载的MCP配置

**便捷函数**：
```python
from src.config_manager import load_mcp_config, merge_mcp_configs

# 加载MCP配置（无需实例化）
mcp_config = load_mcp_config("instances/demo_agent")

# 合并SDK和外部MCP服务器配置
merged = merge_mcp_configs(sdk_servers, external_servers)
```

### Session 模块

会话记录相关功能已独立成 `src.session` 模块，提供：

**核心类**：
- `SessionManager` - 会话管理器
- `Session` - 单个会话对象
- `QueryStreamManager` - 查询流管理器
- `SessionContext` - 会话上下文管理器

**工具函数**：
- `generate_session_id()` - 生成唯一会话 ID
- `Statistics` - 会话统计数据类

**序列化**：
- `MessageSerializer` - 消息序列化器

**查询 API**：
- `get_session_details()` - 获取会话详情
- `list_sessions()` - 列出会话
- `search_sessions()` - 搜索会话
- `export_session()` - 导出会话

## 子实例（高级特性）

### 创建子实例

子实例是完整的 `AgentSystem`，可以有自己的配置和工具。

**1. 创建子实例目录**：
```
instances/
├── parent_agent/
│   └── config.yaml
└── code_reviewer_agent/
    ├── config.yaml
    ├── .claude/
    │   └── agent.md
    └── tools/
        └── lint.py
```

**2. 配置子实例**：
```yaml
# code_reviewer_agent/config.yaml
agent:
  name: "code_reviewer"
  description: "代码审查助手"

model: "claude-opus-4-5"  # 可使用不同模型
system_prompt_file: ".claude/agent.md"

session_recording:
  enabled: true
  retention_days: 60
```

**3. 在父实例中配置**：
```yaml
# parent_agent/config.yaml
sub_claude_instances:
  code_reviewer: "code_reviewer_agent"
```

### 使用子实例

```python
agent = AgentSystem("parent_agent")
await agent.initialize()

# Claude 会自动决定何时使用子实例
prompt = """
使用 code_reviewer 子实例审查以下文件：
- src/main.py
- src/utils.py
"""

result = await agent.query_text(prompt)

# 查询父会话的统计信息，可以获取子实例的 session_id
parent_session_id = result.session_id
from src.session.session_query import get_session_details
session_details = get_session_details(
    instance_name="parent_agent",
    session_id=parent_session_id
)
print(session_details['statistics']['subsessions'])
# [{"session_id": "...", "tool_name": "sub_claude_code_reviewer", ...}]
```

**SubInstanceTool 工具参数**：
- `task` - 任务描述
- `parent_session_id` - **必填**，父会话 ID（用于追踪）
- `context_files` - 相关文件列表
- `output_format` - 输出格式（text/json/markdown）
- `resume_session_id` - 要恢复的子会话 ID
- `variables` - 变量字典

## 项目结构

```
claude_agent_system/
├── src/                              # 核心框架
│   ├── agent_system.py              # 系统主类
│   ├── config_manager.py            # 配置管理（统一管理）
│   ├── tool_manager.py              # 工具管理
│   ├── sub_instance_adapter.py      # 子实例适配器
│   ├── session/                     # 会话记录模块（独立模块）
│   │   ├── __init__.py             # 模块接口
│   │   ├── session_utils.py        # 工具函数和数据类
│   │   ├── session_serializer.py   # 消息序列化
│   │   ├── session_query.py        # 查询 API
│   │   ├── session_context.py      # 上下文管理
│   │   └── stream_manager.py       # 流管理
│   ├── mcp_server/                  # FastMCP 服务器
│   │   ├── server.py                # 服务器主逻辑
│   │   ├── tool_loader.py           # 工具加载器
│   │   └── process_manager.py       # 进程管理
│   ├── error_handling.py            # 错误处理
│   ├── logging_config.py            # 日志配置
│   └── __init__.py
│
├── instances/                        # 实例目录
│   └── demo_agent/
│       ├── config.yaml
│       ├── .claude/
│       │   ├── agent.md            # 系统提示词
│       │   └── .mcp.json           # 外部 MCP 配置
│       ├── tools/                   # 自定义工具
│       │   ├── calculator.py
│       │   └── file_analyzer.py
│       └── sessions/                # 会话记录（自动创建）
│
├── requirements.txt
└── MCP_MIGRATION_WORK_LOG.md        # 迁移工作记录
```


## 常见问题

### 工具开发

**Q: 如何创建自定义工具？**

在 `tools/` 目录下创建 Python 文件，直接写异步函数，无需装饰器：
```python
async def my_function(param1: str) -> dict:
    """工具描述"""
    return {"result": "..."}
```

**Q: 工具必须是异步函数吗？**

是的。系统只会自动发现 `async def` 函数。

**Q: 工具名称如何生成？**

自动生成规则：`{文件名}__{函数名}`，完整 MCP 名称：`mcp__custom_tools__{文件名}__{函数名}`

### 工具权限

**Q: 为什么内置工具默认允许？**

内置的 Claude 工具（Read, Write, Bash 等）默认全部允许。要禁止需在 `disallowed` 中明确列出。

**Q: allowed 列表的作用？**

主要用于限制 MCP 工具（自定义工具、外部 MCP 服务器、子实例）。支持通配符 `*`。

### 会话记录

**Q: 会话记录影响性能吗？**

几乎不会。消息在内存中收集，会话结束时一次性写入（每个会话只有 1 次 I/O）。

**Q: 如何实现多轮对话？**

使用 `resume_session_id` 参数：
```python
result1 = await agent.query_text("第一个问题")
result2 = await agent.query_text(
    "继续讨论",
    resume_session_id=result1.session_id
)
```

**Q: 子实例调用为什么要传递 parent_session_id？**

用于追踪父子会话关系，实现会话层级记录和查询。这是**必填参数**，确保会话记录的完整性。

### 系统提示词

**Q: 推荐使用什么文件名？**

推荐使用 `agent.md`（而非 `CLAUDE.md`），避免与 Claude Code 项目配置冲突。

**Q: 如果不配置会怎样？**

系统会自动按顺序查找：`system_prompt_file` → `agent.md` → `system_prompt.md` → `agent_prompt.md`

### FastMCP 架构

**Q: 为什么使用 FastMCP + stdio？**

主要原因：
- 更高稳定性（避免 SDK 本地工具 bug）
- 进程隔离（工具崩溃不影响主进程）
- 标准协议（符合 MCP 规范）

**Q: 如何调试 MCP 服务器？**

MCP 服务器运行在独立子进程中，日志输出到标准错误（stderr）。可在工具中使用 `logger.error()` 输出调试信息。

### SDK 超时配置

**Q: 为什么需要配置超时？**

子实例执行复杂任务时，SDK 默认 60 秒超时可能不够，会导致强制关闭。建议配置：

```yaml
advanced:
  env:
    CLAUDE_CODE_STREAM_CLOSE_TIMEOUT: "300000"  # 5分钟
    MCP_TIMEOUT: "120000"                       # 2分钟
    MCP_TOOL_TIMEOUT: "180000"                  # 3分钟
```

## 错误处理

```python
from src import AgentSystem, AgentSystemError

try:
    agent = AgentSystem("demo_agent")
    await agent.initialize()
    result = await agent.query_text("你好")
except AgentSystemError as e:
    print(f"系统错误: {e}")
finally:
    agent.cleanup()
```

## 完整示例

查看 `instances/demo_agent/` 获取完整的配置示例和工具实现。