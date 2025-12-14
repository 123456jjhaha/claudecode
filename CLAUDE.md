# Claude Agent System

基于 Claude Agent SDK (Python) 的可扩展智能体系统，具备完整的会话记录和管理功能。

## 核心特性

- 📝 **YAML 配置驱动** - 通过简单的 YAML 文件管理 Claude Agent 实例
- 🔧 **自动工具发现** - 自动扫描和加载 `tools/` 目录下的自定义工具
- 🔄 **递归子实例** - 将完整的 Claude 实例封装成工具，支持无限层级嵌套
- ⚡ **自然并行执行** - 依赖 Claude SDK 自动并行调用工具，无需手动管理
- 🛠️ **统一工具管理** - 本地工具 + 标准 `.mcp.json` 配置外部 MCP 服务器 + 子实例
- 📦 **模块化设计** - 清晰的模块划分，易于维护和扩展
- 🚀 **延迟实例化** - 配置时创建工具定义，调用时才实例化，节省资源
- 📊 **智能会话记录** - 自动记录所有对话消息，支持层级化存储和查询
- 🔁 **Resume 多轮对话** - 支持恢复之前的会话，实现真正的多轮连续对话
- 🔍 **强大查询系统** - 通过 ID 查询会话详情、生成调用关系图、统计分析
- ⚙️ **灵活配置系统** - 可配置的消息过滤、性能参数、存储管理策略

## 核心设计理念

### 1. 完整的会话生命周期管理

**设计原则**：每次 Agent 执行都是一次完整的会话，从创建到结束全程记录。

```
会话生命周期
  ├─ 创建会话 (generate_session_id)
  ├─ 启动消息写入器 (AsyncMessageWriter)
  ├─ 记录所有消息 (UserMessage, AssistantMessage, ResultMessage...)
  ├─ 更新统计信息 (工具使用、成本、耗时)
  ├─ 完成会话 (更新元数据)
  └─ 生成调用关系图 (支持子实例嵌套)
```

**会话 ID 格式**：`{timestamp}_{counter}_{short_hash}`
- 示例：`20251211T061755_0001_a3f9c2d8`
- 保证唯一性和可排序性

### 2. 无状态 Agent 设计

**设计原则**：Agent 不保存任何 session 信息，每个查询返回自己的 session_id。

```
无状态 Agent 架构
  ├─ Agent 只负责配置和初始化
  ├─ query() 返回 QueryStream（包含 session_id）
  ├─ query_text() 返回 QueryResult（包含 result 和 session_id）
  ├─ SessionManager 通过 session_id 管理会话
  └─ 支持并发：同一个 agent 可以同时处理多个查询
```

**架构优势**：
```python
# ✅ 支持并发查询
agent = AgentSystem("demo_agent")
await agent.initialize()

# 同时处理 3 个独立查询
task1 = agent.query_text("分析项目结构")
task2 = agent.query_text("统计代码行数")
task3 = agent.query_text("列出所有依赖")

results = await asyncio.gather(task1, task2, task3)
# 每个查询都有自己的 session_id
for r in results:
    print(f"Session: {r.session_id}, Result: {r.result[:100]}")
```

**关键对比**：
| 设计 | 有状态 Agent | 无状态 Agent（当前） |
|------|--------------|---------------------|
| Session 存储 | `agent.current_session_id` | `result.session_id` |
| 并发查询 | ❌ 不支持 | ✅ 支持 |
| 线程安全 | ❌ 需要加锁 | ✅ 天然安全 |
| Resume 方式 | 依赖 agent 状态 | 通过 session_id 参数 |

### 3. 简化的内存收集系统

**设计原则**：遵循 KISS 原则（Keep It Simple, Stupid），避免过早优化。

```python
Session 消息收集特性：
  ├─ 内存收集 (_messages 列表)
  ├─ 一次性写入 (会话结束时)
  ├─ 消息类型过滤 (可配置)
  ├─ 完整的错误处理 (序列化失败不影响主流程)
  └─ 自动内存释放 (写入后清空列表)
```

**实现逻辑**：
1. `record_message()` - 将消息追加到内存列表（无 I/O）
2. `finalize()` - 检测到 ResultMessage 时一次性写入所有消息
3. 性能优化：每个会话只有 1 次磁盘写入操作
4. 内存友好：写入完成后立即清空 `_messages` 列表

### 4. 层级化会话存储

**目录结构**：
```
instances/agent_name/sessions/
└── 20251211T061755_0001_a3f9c2d8/      # 父会话
    ├── metadata.json                    # 会话元数据
    ├── messages.jsonl                   # 消息记录（JSON Lines）
    ├── statistics.json                  # 统计信息
    ├── call_graph.json                  # 调用关系图
    └── subsessions/                     # 子会话目录
        └── 20251211T061800_0001_b4e8d3f9/  # 子会话
            ├── metadata.json
            ├── messages.jsonl
            └── statistics.json
```

**数据格式**：
- **metadata.json**: 会话基础信息（ID、时间、状态、深度等）
- **messages.jsonl**: 逐行 JSON 格式的消息记录
- **statistics.json**: 性能统计（耗时、轮次、工具使用、成本等）
- **call_graph.json**: 完整的调用关系树

### 5. 延迟实例化 (Lazy Instantiation)

**设计原则**：配置加载时只创建工具定义，工具被调用时才实例化。

```
初始化阶段 (initialize):
  ├─ 加载 config.yaml（包括会话记录配置）
  ├─ 发现 tools/ 目录下的工具
  ├─ 创建工具定义（函数签名）
  ├─ 生成 MCP 服务器配置
  ├─ 初始化 SessionManager（根据配置）
  └─ ❌ 不实例化子 Claude（延迟到调用时）

工具调用阶段 (tool execution):
  ├─ Claude 决定调用某个工具
  ├─ ✅ 动态创建 AgentSystem 实例
  ├─ 初始化并执行查询（自动记录会话）
  └─ 返回结果
```

### 6. 自然并行执行

**设计原则**：依赖 Claude SDK 的自动并行能力，不手动实现并行逻辑。

```python
# ❌ 不需要手动实现：
# await instance_manager.execute_parallel(tasks)

# ✅ 让 Claude 自然决定：
prompt = "请同时调用 code_reviewer 和 document_writer 子实例"
result = await agent.query_text(prompt)
# Claude SDK 自动并行执行工具调用
# 每个子实例的会话独立记录，并通过 contextvars 自动关联
```

### 7. 递归嵌套支持

**设计原则**：每一层都是完整的 `AgentSystem`，支持无限嵌套。

```
Parent Agent (Session ID: 20251211T061755_0001_a3f9c2d8)
  ├─ Tool: calculator
  └─ Sub Claude: code_reviewer (Session ID: 20251211T061800_0001_b4e8d3f9)
       ├─ Tool: lint_checker
       └─ Sub Claude: syntax_analyzer (Session ID: 20251211T061805_0001_c5e9f4a0)
            ├─ Tool: parser
            └─ Sub Claude: ...（继续嵌套）
```

## 安装

```bash
# 克隆仓库
git clone https://github.com/yourusername/claude_agent_system.git
cd claude_agent_system

# 安装依赖
pip install -r requirements.txt

# 配置 API 密钥
cp .env.example .env
# 编辑 .env 文件，填入你的 ANTHROPIC_API_KEY
```

## 快速开始

### 1. 流式访问 - 查看完整执行过程

```python
import asyncio
from src import AgentSystem

async def main():
    # 创建 agent 系统（使用示例实例）
    agent = AgentSystem("example_agent")

    # 初始化系统（会自动初始化会话管理器）
    await agent.initialize()

    # query() 返回 QueryStream 对象 - 可迭代访问所有消息
    stream = await agent.query("使用计算器计算 123 + 456")

    async for message in stream:
        message_type = type(message).__name__

        if message_type == "AssistantMessage":
            # 处理 AI 助手消息（包含文本、工具调用等）
            from claude_agent_sdk import TextBlock, ToolUseBlock
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(f"AI: {block.text}")
                elif isinstance(block, ToolUseBlock):
                    print(f"工具调用: {block.name}({block.input})")

        elif message_type == "ToolResultBlock":
            # 处理工具结果
            print(f"工具结果: {message.content}")

        elif message_type == "ResultMessage":
            # 最终结果
            print(f"完成: {message.result}")

    # 从 stream 对象获取会话 ID
    print(f"会话 ID: {stream.session_id}")

# 运行
asyncio.run(main())
```

### 2. 只获取结果 - 不需要中间过程

```python
import asyncio
from src import AgentSystem

async def main():
    # 创建 agent 系统
    agent = AgentSystem("example_agent")
    await agent.initialize()

    # query_text() 返回 QueryResult 对象 - 包含结果和会话 ID
    result = await agent.query_text("计算 123 + 456")

    print(f"结果: {result.result}")         # 输出: "579"
    print(f"会话 ID: {result.session_id}")  # 会话标识

# 运行
asyncio.run(main())
```

### 3. Resume 模式 - 继续之前的对话

**核心概念**：每次 `query()` 调用都是独立的，但可以通过 `resume_session_id` 参数继续之前的对话。

**架构优势**：
- ✅ **无状态 Agent**：Agent 不保存任何 session 信息，可以并发处理多个查询
- ✅ **Session ID 由查询返回**：每个查询返回自己的 session_id
- ✅ **SessionManager 按 ID 管理**：通过 session_id 加载和恢复会话

**两级 Session ID 映射**：
- **本地 session_id**：我们的会话记录系统标识（如 `20251212T120000_0001_abcd1234`）
- **Claude SDK session_id**：Claude API 层面的会话标识（如 `session-xyz`）
- Resume 时，系统自动根据本地 session_id 查找对应的 Claude session_id

```python
import asyncio
from src import AgentSystem

async def main():
    agent = AgentSystem("demo_agent")
    await agent.initialize()

    # 第一次对话
    print("=== 第一次对话 ===")
    result1 = await agent.query_text("分析这个项目的结构")
    print(result1.result)

    # 从结果中获取会话 ID（而不是从 agent）
    session_id = result1.session_id
    print(f"\n会话 ID: {session_id}\n")

    # 继续之前的对话（Resume）
    print("=== 继续对话（Resume）===")
    result2 = await agent.query_text(
        "根据刚才的分析，建议优化方案",
        resume_session_id=session_id
    )
    print(result2.result)
    print(f"会话 ID: {result2.session_id}")  # 同一个 session_id

    # 再次继续
    print("\n=== 再次继续 ===")
    result3 = await agent.query_text(
        "生成详细的实施计划",
        resume_session_id=session_id
    )
    print(result3.result)

    # 查看会话记录
    # 所有消息都追加到同一个 messages.jsonl 文件
    # 统计信息被最新的 ResultMessage 覆盖（因为它已经是累计值）

asyncio.run(main())
```

**Resume 行为说明**：
1. **消息追加**：新消息追加到原会话的 `messages.jsonl` 文件
2. **序列号连续**：`seq` 序列号自动从之前的消息数量继续递增
3. **统计信息覆盖**：`statistics.json` 被覆盖（ResultMessage 包含累计统计）
4. **元数据更新**：`end_time` 更新为最新时间，添加 `resumed_at` 时间戳
5. **Claude session_id**：在第一条 SystemMessage (subtype='init') 时自动获取并保存

**技术细节**：
- 系统在会话创建时就获取 Claude session_id（从第一条 SystemMessage）
- Resume 时，加载会话元数据，提取 Claude session_id
- 使用 `ClaudeAgentOptions(resume=claude_session_id)` 恢复 API 层面的会话
- 会话状态重置为 `running`，`_finalized` 标志重置为 `False`

### 4. 并发查询 - 无状态 Agent 的优势

```python
import asyncio
from src import AgentSystem

async def main():
    agent = AgentSystem("example_agent")
    await agent.initialize()

    # Agent 是无状态的，可以并发处理多个查询！
    task1 = agent.query_text("分析项目结构")
    task2 = agent.query_text("统计代码行数")
    task3 = agent.query_text("列出所有依赖")

    # 并发执行
    results = await asyncio.gather(task1, task2, task3)

    for i, result in enumerate(results, 1):
        print(f"\n=== 查询 {i} ===")
        print(f"结果: {result.result[:100]}...")
        print(f"会话 ID: {result.session_id}")

asyncio.run(main())
```

### 5. 流式响应与会话记录

```python
import asyncio
from src import AgentSystem
from src.session_query import get_session_details

async def main():
    agent = AgentSystem("example_agent")
    await agent.initialize()

    # 流式获取响应（所有消息自动记录）
    stream = await agent.query("分析这个项目的目录结构")
    async for message in stream:
        if hasattr(message, "text"):
            print(message.text, end="", flush=True)

    # 查询会话详情
    session_id = stream.session_id
    details = get_session_details("example_agent", session_id)

    print(f"\n\n会话统计:")
    print(f"- 状态: {details['metadata']['status']}")
    print(f"- 轮次: {details['statistics']['num_turns']}")
    print(f"- 成本: ${details['statistics']['cost_usd']:.4f}")

asyncio.run(main())
```

### 6. 配置会话记录

```yaml
# config.yaml
agent:
  name: "my_agent"
  description: "我的智能体"

model: "claude-sonnet-4-5"
# 推荐使用 agent.md 而不是 CLAUDE.md，避免与 Claude Code 项目配置冲突
system_prompt_file: ".claude/agent.md"

# 会话记录配置
session_recording:
  enabled: true                    # 是否启用会话记录

  # 存储管理
  retention_days: 30               # 保留天数
  max_total_size_mb: 1000          # 最大总大小（MB）
  auto_cleanup: true               # 是否自动清理

  # 消息过滤（哪些消息类型要记录）
  # None 表示记录所有类型（推荐），也可以指定具体类型
  message_types: null              # 记录所有消息类型
  # 或者只记录特定类型：
  # message_types:
  #   - "UserMessage"       # 用户消息
  #   - "AssistantMessage"  # AI 助手消息
  #   - "ResultMessage"     # 结果消息
  #   - "SystemMessage"     # 系统消息
  #   - "StreamEvent"       # 流事件

  # 内容控制
  include_content: true            # 是否包含消息内容
  include_metadata: true           # 是否包含元数据

# 工具配置
tools:
  # 重要：内置工具（Read, Write, Bash 等）默认全部允许
  # 必须在 disallowed 中明确列出才能禁止
  disallowed:
    - "WebFetch"      # 禁止网页获取
    - "WebSearch"     # 禁止网页搜索
    - "KillShell"     # 禁止杀死 shell 进程

  # allowed 主要用于限制 MCP 工具（自定义工具、外部 MCP、子实例）
  # 内置工具不需要在这里列出
  allowed:
    - "mcp__custom_tools__calculator__*"
    - "mcp__sub_instances__sub_claude_*"
```

## 会话记录和查询系统

### 📊 功能概述

会话记录系统自动记录每次对话的完整信息，支持：

- ✅ **自动记录**：父级和子级 Agent 的所有消息自动保存
- ✅ **层级化存储**：父子会话通过嵌套目录体现调用关系
- ✅ **简单高效**：内存收集 + 一次性写入，性能最优
- ✅ **智能过滤**：可配置的消息类型过滤
- ✅ **完整查询 API**：通过会话 ID 查询详情、统计、消息列表
- ✅ **调用关系图**：可视化整个工作流程的调用树
- ✅ **自动清理**：配置化的过期会话清理机制

### 🔍 查询 API

#### 1. 获取会话详情

```python
from src.session_query import get_session_details

details = get_session_details(
    instance_name="example_agent",
    session_id="20251211T061755_0001_a3f9c2d8"
)

# 访问各类信息
metadata = details['metadata']      # 元数据
statistics = details['statistics']  # 统计信息
messages = details['messages']      # 消息列表
subsessions = details['subsessions'] # 子会话列表
```

#### 2. 列出会话

```python
from src.session_query import list_sessions

# 列出所有会话
sessions = list_sessions("example_agent", limit=100)

# 过滤已完成的会话
completed = list_sessions("example_agent", status="completed")
```

#### 3. 搜索会话

```python
from src.session_query import search_sessions

# 按提示词搜索
results = search_sessions(
    "example_agent",
    query="代码审查",
    field="initial_prompt"
)
```

#### 4. 生成调用关系图

```python
from src.session_query import get_call_graph

graph = get_call_graph("example_agent", session_id)

# 调用关系图结构
{
  "root_session_id": "...",
  "graph": {
    "session_id": "...",
    "instance_name": "example_agent",
    "depth": 0,
    "children": [
      {
        "session_id": "...",
        "instance_name": "code_reviewer",
        "depth": 1,
        "children": [...]
      }
    ]
  }
}
```

#### 5. 统计摘要

```python
from src.session_query import get_session_statistics_summary

summary = get_session_statistics_summary(
    "example_agent",
    session_ids=["session1", "session2"]
)

print(f"总会话数: {summary['total_sessions']}")
print(f"总成本: ${summary['total_cost_usd']}")
print(f"工具使用: {summary['tools_usage']}")
```

#### 6. 导出会话

```python
from src.session_query import export_session

# 导出为 JSON
export_session(
    "example_agent",
    session_id,
    output_format="json",
    output_file="session.json"
)

# 导出为 Markdown
export_session(
    "example_agent",
    session_id,
    output_format="markdown",
    output_file="session.md"
)
```

### 🔄 父子会话关系

**父级 Agent**：
- 返回所有详细消息（流式）
- 用户可以实时看到执行进度
- 通过 `agent.current_session_id` 获取会话 ID

**子级 Agent（子实例）**：
- 只返回最终结果给父级
- 完整过程记录到文件
- 在响应的 `_session_metadata` 字段包含会话 ID

**自动关联**：
- 使用 `contextvars` 实现父子会话自动关联
- 子会话嵌套在父会话的 `subsessions/` 目录下
- 无需手动管理会话关系

## 子 Claude 实例（高级特性）

### 核心概念

子 Claude 实例是完整的 `AgentSystem`，可以：
- 拥有自己的配置和工具
- 拥有自己的子实例（递归嵌套）
- 被封装成工具供父 Claude 调用
- 在工具调用时才实例化（延迟加载）
- **自动拥有独立的会话记录**

### 创建子实例

#### 1. 创建子实例目录
```bash
instances/
├── parent_agent/              # 父实例
│   └── config.yaml
└── code_reviewer_agent/       # 子实例
    ├── config.yaml            # 完整配置，包括会话记录
    ├── .claude/
    │   └── CLAUDE.md          # 子实例的系统提示词
    └── tools/                 # 子实例可以有自己的工具
        └── lint.py
```

#### 2. 配置子实例（config.yaml）
```yaml
# code_reviewer_agent/config.yaml
agent:
  name: "code_reviewer"
  description: "专业的代码审查助手"

model: "claude-opus-4-5"  # 可以使用不同的模型
system_prompt_file: ".claude/CLAUDE.md"

# 子实例也可以有自己的会话记录配置！
session_recording:
  enabled: true
  retention_days: 60        # 不同的保留策略
  message_types: null       # 记录所有消息类型（推荐）
  # 或只记录特定类型：
  # message_types:
  #   - "UserMessage"
  #   - "AssistantMessage"
  #   - "ResultMessage"

tools:
  allowed:
    - "Read"
    - "Grep"
    - "mcp__custom_tools__lint__*"

# 子实例也可以有自己的子实例！
sub_claude_instances:
  syntax_checker: "syntax_checker_agent"
```

### 使用子实例

#### 基础使用

```python
agent = AgentSystem("parent_agent")
await agent.initialize()

# Claude 会自动决定何时使用子实例工具
prompt = """
请审查以下代码文件：
- src/main.py
- src/utils.py

使用 code_reviewer 子实例进行详细分析。
"""

result = await agent.query_text(prompt)
print(result.result)
print(f"父会话 ID: {result.session_id}")

# 会话记录：
# - 父会话：20251211T061755_0001_a3f9c2d8
#   └─ 子会话：20251211T061800_0001_b4e8d3f9 (code_reviewer)
```

#### 子实例 Resume（高级）

子实例工具也支持 `resume_session_id` 参数，可以继续之前的子实例对话：

```python
# 第一次调用子实例
result1 = await agent.query_text("""
使用 code_reviewer 子实例审查 src/main.py 文件
""")

# 从父级工具响应中提取子会话 ID
# （需要自定义处理工具响应中的 _session_metadata 字段）
# sub_session_id = "20251211T061800_0001_b4e8d3f9"

# 继续子实例对话
result2 = await agent.query_text("""
使用 code_reviewer 子实例，根据之前的审查结果生成修复建议。
resume_session_id: {sub_session_id}
""")

# 注意：子实例的 resume_session_id 需要通过提示词传递给工具
# 工具参数支持：
# - task: 任务描述
# - context_files: 相关文件列表
# - output_format: 输出格式（text/json/markdown）
# - resume_session_id: 要恢复的子会话 ID（新增）
# - variables: 变量字典
# - cwd: 工作目录
```

## 系统架构

### 整体架构图

```
┌─────────────────────────────────────────────────────────┐
│                     AgentSystem                         │
│  (主类，整合所有组件，包括会话管理)                       │
└─────────────────────────────────────────────────────────┘
              ▲         ▲          ▲          ▲
              │         │          │          │
      ┌───────┘    ┌────┘     ┌────┘     ┌────┘
      │            │          │          │
┌─────┴─────┐ ┌───┴────┐ ┌───┴────┐ ┌───┴────────┐
│  Config   │ │ Tool   │ │Session  │ │   Claude   │
│  Loader   │ │Manager │ │Manager  │ │  SDK/API   │
└───────────┘ └────────┘ └────────┘ └────────────┘
      │            │          │
      │            │          │
  ┌───▼───┐   ┌───▼───┐  ┌───▼────────┐
  │ YAML  │   │tools/ │  │ Sub Claude │
  │ File  │   │ @tool │  │  Instance  │
  └───────┘   └───────┘  └────────────┘
                                │
                         (递归 AgentSystem)
```

### 执行流程（包含会话记录）

#### 初始化流程
```
1. 创建 AgentSystem(instance_name)
   │
2. await agent.initialize()
   │
   ├─> ConfigLoader.load() (读取会话记录配置)
   │   ├─ 读取 config.yaml
   │   ├─ 验证配置（包括 session_recording）
   │   └─ 解析路径和环境变量
   │
   ├─> ToolManager.discover_tools()
   │   ├─ 扫描 tools/ 目录
   │   └─ 提取 @tool 装饰的函数
   │
   ├─> InstanceManager.load_instances()
   │   ├─ 读取子实例配置
   │   └─ 创建工具定义（不实例化）
   │
   ├─> SessionManager.__init__()
   │   ├─ 合并会话记录配置和默认值
   │   ├─ 创建 sessions/ 目录
   │   └─ 设置消息过滤、性能参数等
   │
   └─> 合并所有 MCP 服务器并生成 ClaudeAgentOptions
```

#### 查询执行流程（包含会话记录）
```
1. await agent.query(prompt)
   │
2. 创建新会话
   │   ├─ 生成唯一会话 ID
   │   ├─ 创建会话目录
   │   ├─ 启动 AsyncMessageWriter
   │   └─ 记录初始元数据
   │
3. 执行 Claude SDK 查询
   │   ├─ 记录 UserMessage
   │   ├─ 记录所有 AssistantMessage
   │   ├─ 记录工具调用（ToolUseBlock）
   │   ├─ 记录工具结果（ToolResultBlock）
   │   └─ 处理子实例调用
   │       ├─ 创建子 AgentSystem
   │       ├─ 子实例自动继承会话配置
   │       ├─ 创建子会话（嵌套在 subsessions/）
   │       └─ 子会话完整记录
   │
4. 完成 ResultMessage
   │   ├─ 记录最终结果
   │   ├─ 更新统计信息（耗时、成本、工具使用）
   │   ├─ 生成调用关系图
   │   └─ 停止 AsyncMessageWriter
   │
5. 返回结果给用户
```

## 项目结构

```
claude_agent_system/
├── src/                              # 核心框架源码
│   ├── agent_system.py              # 系统主类（整合所有组件）
│   ├── config_loader.py             # 配置加载器
│   ├── config_validator.py          # 配置验证器（包含会话记录验证）
│   ├── tool_manager.py              # 工具管理器
│   ├── claude_instance_wrapper.py   # 子实例封装（延迟实例化）
│   ├── instance_manager.py          # 子实例管理器
│   ├── session_manager.py           # 会话管理器（核心新增）
│   ├── session_context.py           # 会话上下文管理
│   ├── session_query.py             # 会话查询 API
│   ├── error_handling.py            # 自定义异常
│   ├── logging_config.py            # 日志配置
│   └── __init__.py                  # 模块导出
│
├── instances/                        # 工作实例目录
│   └── example_agent/               # 示例实例
│       ├── config.yaml              # 实例配置文件
│       ├── .claude/                 # Claude 标准配置
│       │   ├── CLAUDE.md           # 系统提示词
│       │   ├── agents/             # 子代理定义
│       │   ├── commands/           # 自定义命令
│       │   ├── skills/             # 技能定义
│       │   └── hooks/              # 钩子脚本
│       ├── tools/                   # 自定义工具
│       │   ├── __init__.py
│       │   └── calculator.py        # 示例工具
│       └── sessions/                 # 会话记录目录（自动创建）
│           └── 20251211T061755_0001_a3f9c2d8/
│
├── examples/                         # 使用示例
│   ├── basic_usage.py               # 基础使用
│   ├── parallel_execution.py        # 并行执行
│   ├── custom_tools.py              # 自定义工具
│   └── session_recording.py         # 会话记录示例
│
├── requirements.txt                  # 依赖列表
├── README.md                         # 项目文档
└── .env.example                      # 环境变量示例
```

## API 文档

### AgentSystem

主类，用于管理和运行 Claude Agent 实例。

**架构特点**：
- ✅ **无状态设计**：Agent 不保存 session 信息，支持并发查询
- ✅ **Session ID 由查询返回**：每个查询返回自己的 session_id
- ✅ **线程安全**：可以安全地并发处理多个查询

**初始化**

```python
agent = AgentSystem(
    instance_name="example_agent",  # 实例名称或实例目录路径
    instances_root=None             # 实例根目录（可选）
)
```

**方法**

- `async initialize()` - 初始化系统（包括会话管理器）

- `async query(prompt: str, record_session: bool = True, resume_session_id: Optional[str] = None) -> QueryStream`
  - **返回**: `QueryStream` 对象（可迭代，包含 `session_id` 属性）
  - `prompt`: 查询提示词
  - `record_session`: 是否记录会话到文件（默认 True）
  - `resume_session_id`: 要恢复的会话 ID（可选，用于继续之前的对话）

- `async query_text(prompt: str, record_session: bool = True, resume_session_id: Optional[str] = None) -> QueryResult`
  - **返回**: `QueryResult` 对象（包含 `result` 和 `session_id`）
  - `prompt`: 查询提示词
  - `record_session`: 是否记录会话到文件（默认 True）
  - `resume_session_id`: 要恢复的会话 ID（可选，用于继续之前的对话）

**属性**

- `agent_name` - Agent 名称
- `agent_description` - Agent 描述
- `tools_count` - 工具数量
- `instances_count` - 子实例数量

### QueryResult

查询结果对象（`query_text()` 的返回值）

**属性**

- `result: str` - 查询结果文本
- `session_id: Optional[str]` - 会话 ID（如果启用了会话记录）

**示例**

```python
result = await agent.query_text("你好")
print(result.result)      # 访问结果文本
print(result.session_id)  # 访问会话 ID
```

### QueryStream

查询流对象（`query()` 的返回值）

**特性**

- 实现了异步迭代器协议，可以使用 `async for` 遍历
- 包含 `session_id` 属性，用于获取会话标识

**属性**

- `session_id: Optional[str]` - 会话 ID（如果启用了会话记录）

**示例**

```python
stream = await agent.query("分析代码")
async for message in stream:
    print(message)
print(f"会话 ID: {stream.session_id}")
```

## 性能优化建议

### 1. 会话记录配置优化

```yaml
session_recording:
  # 标准配置（推荐）
  enabled: true
  message_types: null      # 记录所有消息类型
  include_content: true
  include_metadata: true

  # 减少存储空间
  message_types:           # 只记录必要消息
    - "UserMessage"
    - "ResultMessage"
  include_content: false   # 不记录消息内容
  include_metadata: false  # 不记录元数据
```

### 2. 消息过滤优化

```yaml
# 只记录关键消息，减少存储开销
session_recording:
  message_types:
    - "ResultMessage"     # 只记录结果
  include_metadata: false  # 不记录详细元数据
  include_content: false   # 不记录消息内容
```

### 3. 存储管理策略

```yaml
session_recording:
  retention_days: 7        # 短期保留策略
  max_total_size_mb: 100   # 限制总大小
  auto_cleanup: true       # 启用自动清理
```

## ⚙️ SDK 超时配置（避免子实例崩溃）

### 问题描述

当你使用子实例时，可能会遇到子实例执行到一半就崩溃的问题。这通常是由 Claude SDK 的超时机制导致的：

**默认行为**：
- SDK 默认只等待 60 秒的第一个结果
- 如果 60 秒内子实例没有返回响应，SDK 会强制关闭流
- 这会导致 TaskGroup 被取消，所有并行任务被中断

### 解决方案：配置超时环境变量

在 `config.yaml` 的 `advanced.env` 部分添加以下配置：

```yaml
advanced:
  env:
    # === SDK 超时配置（避免子实例崩溃） ===

    # 1. 流关闭超时（最重要的配置）
    # 作用：控制 SDK 等待第一个结果的超时时间（毫秒）
    # 默认：60000ms (60秒) - 太短，容易导致崩溃
    # 建议：300000ms (5分钟) - 给子实例充足的执行时间
    CLAUDE_CODE_STREAM_CLOSE_TIMEOUT: "300000"  # 5分钟

    # 2. MCP 服务器启动超时
    # 作用：启动子实例的 MCP 服务器时的等待时间
    # 默认：30000ms (30秒)
    # 建议：120000ms (2分钟)
    MCP_TIMEOUT: "120000"                       # 2分钟

    # 3. MCP 工具执行超时
    # 作用：单个 MCP 工具执行的超时时间
    # 默认：可能存在 bug，不一定生效
    # 建议：180000ms (3分钟) - 作为额外保障
    MCP_TOOL_TIMEOUT: "180000"                  # 3分钟
```

### 为什么需要这些配置？

#### 1. CLAUDE_CODE_STREAM_CLOSE_TIMEOUT（最重要）
- **问题**：SDK 在等待子实例的第一个结果时，默认只等待 60 秒
- **后果**：如果子实例执行复杂任务（如代码分析、文件处理），60 秒可能不够用，SDK 会强制关闭流
- **解决**：延长到 5 分钟，给子实例充足的时间

#### 2. MCP_TIMEOUT
- **作用**：控制 MCP 服务器启动的超时时间
- **场景**：启动子实例时，需要等待 MCP 服务器就绪
- **解决**：从 30 秒延长到 2 分钟，适合复杂的服务器

#### 3. MCP_TOOL_TIMEOUT
- **作用**：控制单个工具执行的超时时间
- **注意**：当前可能存在 bug，不一定生效
- **解决**：设置为 3 分钟作为额外保障

### 配置示例

```yaml
# 完整的实例配置示例
agent:
  name: "my_agent"
  description: "我的智能体"

model: "claude-sonnet-4-5"

# 子实例配置
sub_claude_instances:
  code_analyzer: "code_analyzer_agent"
  file_processor: "file_processor_agent"

# 超时配置
advanced:
  env:
    CLAUDE_CODE_STREAM_CLOSE_TIMEOUT: "300000"  # 5分钟
    MCP_TIMEOUT: "120000"                       # 2分钟
    MCP_TOOL_TIMEOUT: "180000"                  # 3分钟
```

### 验证配置

```python
# 检查环境变量是否设置成功
import os

print(f"流关闭超时: {os.environ.get('CLAUDE_CODE_STREAM_CLOSE_TIMEOUT')}ms")
print(f"MCP 超时: {os.environ.get('MCP_TIMEOUT')}ms")
print(f"MCP 工具超时: {os.environ.get('MCP_TOOL_TIMEOUT')}ms")
```

### 效果

配置后：
- ✅ 子实例不会因为执行时间长而崩溃
- ✅ 复杂任务可以正常完成
- ✅ 避免了 SDK 强制关闭流导致的 TaskGroup 取消
- ✅ 提供了更稳定的用户体验

## 错误处理

```python
from src import AgentSystem, AgentSystemError
from src.session_query import SessionQueryError

try:
    agent = AgentSystem("example_agent")
    await agent.initialize()
except AgentSystemError as e:
    print(f"系统错误: {e}")

try:
    details = get_session_details("agent", session_id)
except SessionQueryError as e:
    print(f"会话查询错误: {e}")
```

## 完整示例：demo_agent

我们在 `instances/demo_agent/` 中提供了一个完整的示例实例，展示了系统的所有功能：

### 目录结构
```
instances/demo_agent/
├── config.yaml              # 完整的配置文件
├── .claude/                 # Claude 标准配置目录
│   ├── agent.md            # 系统提示词（推荐使用，避免与 CLAUDE.md 冲突）
│   ├── .mcp.json           # 外部 MCP 服务器配置
│   ├── agents/             # 子代理定义
│   │   └── code_reviewer.md
│   └── skills/             # 技能定义
│       └── project_analysis.md
└── tools/                   # 自定义工具
    ├── __init__.py
    ├── calculator.py        # 数学计算工具
    ├── file_analyzer.py     # 文件分析工具
    └── text_processor.py    # 文本处理工具
```

### 使用示例
```python
import asyncio
from src import AgentSystem

async def main():
    # 使用完整示例
    agent = AgentSystem("demo_agent")
    await agent.initialize()

    # 演示多种功能
    prompt = """
    请演示你的能力：
    1. 使用计算器计算 2^10
    2. 分析 config.yaml 文件
    3. 统计 README.md 的文本信息
    4. 提取关键词
    """

    result = await agent.query_text(prompt)
    print(result)

    # 查看会话记录
    print(f"会话 ID: {agent.current_session_id}")

asyncio.run(main())
```

### 常见问题

#### 会话记录相关

**Q1: 会话记录会影响性能吗？**
A: 几乎不会。消息在内存中收集，会话结束时一次性写入磁盘（每个会话只有 1 次 I/O 操作），性能影响极小。

**Q2: 可以只记录特定类型的消息吗？**
A: 可以。通过 `message_types` 配置要记录的消息类型，支持过滤掉不必要的消息。

**Q3: 如何查看子实例的执行过程？**
A: 子实例会创建独立的会话记录，嵌套在父会话的 `subsessions/` 目录下，可通过调用关系图查看完整流程。

**Q4: 会话数据存储在哪里？**
A: 存储在 `instances/{agent_name}/sessions/` 目录下，每个会话一个目录，包含元数据、消息、统计等信息。

**Q5: 如何管理大量会话数据？**
A: 配置 `retention_days` 和 `max_total_size_mb` 参数，启用 `auto_cleanup` 自动清理过期数据。

#### Resume 多轮对话

**Q6: 如何实现多轮连续对话？**
A: 使用 `resume_session_id` 参数继续之前的对话：
```python
# 第一次对话
result1 = await agent.query_text("分析项目结构")
session_id = agent.current_session_id

# 继续对话
result2 = await agent.query_text(
    "根据刚才的分析给建议",
    resume_session_id=session_id
)
```

**Q7: Resume 时消息如何存储？**
A: 新消息会追加到原会话的 `messages.jsonl` 文件，序列号（seq）自动连续递增，不会重复。

**Q8: 两个 Session ID 有什么区别？**
A: 系统使用两级 Session ID 映射：
- **本地 session_id**：我们的会话记录标识（如 `20251212T120000_0001_abcd1234`）
- **Claude SDK session_id**：Claude API 层面的会话标识（如 `session-xyz`）
- Resume 时，系统根据本地 session_id 自动查找对应的 Claude session_id

**Q9: Resume 模式下统计信息会累加吗？**
A: 不会。统计信息直接覆盖（不累加），因为 Claude SDK 的 ResultMessage 已经包含了累计的统计值（token 使用量、成本、轮次等）。

**Q10: 何时获取 Claude session_id？**
A: 系统在第一条 SystemMessage (subtype='init') 时就会获取并保存 Claude session_id，而不是等到最后的 ResultMessage，确保 Resume 功能随时可用。

#### 工具权限管理

**Q11: 为什么在 allowed 中列出内置工具但仍然可以使用？**
A: **这是一个重要的设计特点**：内置的 Claude 工具（如 Read, Write, Bash 等）默认全部允许。`allowed` 列表主要用于限制 MCP 工具（自定义工具、外部 MCP 服务器、子实例）。要禁止内置工具，必须在 `disallowed` 中明确列出。

**Q12: 如何正确配置工具权限？**
A: 推荐的配置方式：

```yaml
tools:
  # 禁止特定的内置工具（可选）
  disallowed:
    - "WebFetch"    # 禁止网页访问
    - "WebSearch"   # 禁止网络搜索
    - "KillShell"   # 禁止危险操作

  # 允许特定的 MCP 工具
  allowed:
    # 自定义工具
    - "mcp__custom_tools__calculator__*"

    # 子实例工具
    - "mcp__sub_instances__sub_claude_*"

    # 外部 MCP 服务器
    - "mcp__external_database__*"
```

**Q13: 什么是 MCP 工具？**
A: MCP (Model Context Protocol) 工具包括：
- **自定义工具**：`tools/` 目录下用 `@tool` 装饰器定义的工具
- **子实例工具**：封装成工具的子 Claude 实例
- **外部 MCP 服务器**：通过 `.mcp.json` 配置的外部服务

**Q14: 如何使用通配符？**
A: 工具名称支持 `*` 通配符：
- `"mcp__custom_tools__*"` - 所有自定义工具
- `"mcp__sub_instances__sub_claude_*"` - 所有子实例工具
- `"Read*"` - 所有以 Read 开头的工具（如果有）

#### 提示词文件配置

**Q15: 为什么不应该使用 CLAUDE.md 作为系统提示词文件？**
A: **重要**：`CLAUDE.md` 是 Claude Code 的项目配置文件名，使用它可能会导致：
- 与 Claude Code 的项目级配置冲突
- 提示词被意外覆盖或读取错误的内容
- 混淆 Claude Code 配置和 Agent System 配置

**Q11: 推荐使用什么文件名？**
A: 推荐的提示词文件名（按优先级）：
1. **`agent.md`** (最推荐) - 简洁明了
2. `system_prompt.md` - 描述性强
3. `agent_prompt.md` - 清晰的表达
4. `prompt.md` - 简单直接

**Q12: 如果没有配置提示词文件会怎样？**
A: 系统会自动按以下顺序查找提示词文件：
1. 用户配置的 `system_prompt_file`
2. `agent.md`
3. `system_prompt.md`
4. `agent_prompt.md`

如果都没找到，系统会使用内置的默认提示词，包含基础的 Agent 行为指导。

**Q13: 配置示例**
A:
```yaml
# 好的配置
agent:
  name: "my_agent"
model: "claude-sonnet-4-5"
system_prompt_file: ".claude/agent.md"  # 推荐

# 或不配置（系统会自动查找 agent.md）
agent:
  name: "my_agent"
model: "claude-sonnet-4-5"
# system_prompt_file: .claude/agent.md  # 可选，系统会自动查找
```