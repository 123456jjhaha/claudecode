# Claude Agent System

基于 Claude Agent SDK (Python) 的可扩展智能体系统。

## 核心特性

- 📝 **YAML 配置驱动** - 通过简单的 YAML 文件管理 Claude Agent 实例
- 🔧 **自动工具发现** - 自动扫描和加载 `tools/` 目录下的自定义工具
- 🔄 **递归子实例** - 将完整的 Claude 实例封装成工具，支持无限层级嵌套
- ⚡ **自然并行执行** - 依赖 Claude SDK 自动并行调用工具，无需手动管理
- 🛠️ **统一工具管理** - 本地工具 + 标准 `.mcp.json` 配置外部 MCP 服务器 + 子实例
- 📦 **模块化设计** - 清晰的模块划分，易于维护和扩展
- 🚀 **延迟实例化** - 配置时创建工具定义，调用时才实例化，节省资源

## 核心设计理念

### 1. 延迟实例化 (Lazy Instantiation)

**设计原则**：配置加载时只创建工具定义，工具被调用时才实例化。

```
初始化阶段 (initialize):
  ├─ 加载 config.yaml
  ├─ 发现 tools/ 目录下的工具
  ├─ 创建工具定义（函数签名）
  ├─ 生成 MCP 服务器配置
  └─ ❌ 不实例化子 Claude（延迟到调用时）

工具调用阶段 (tool execution):
  ├─ Claude 决定调用某个工具
  ├─ ✅ 动态创建 AgentSystem 实例
  ├─ 初始化并执行查询
  └─ 返回结果
```

**优势**：
- 避免不必要的资源消耗
- 支持大量子实例配置而不影响启动速度
- 每次调用都是全新的上下文

### 2. 子实例即 AgentSystem

**设计原则**：子 Claude 实例使用与父实例相同的 `AgentSystem` 类。

```python
# 父实例
parent = AgentSystem("parent_agent")
await parent.initialize()

# 子实例工具被调用时
# 内部创建：
sub_agent = AgentSystem("child_agent", api_key, instances_root)
await sub_agent.initialize()  # 递归初始化，可以有自己的子实例
result = await sub_agent.query_text(task)
```

**优势**：
- 统一的接口和实现
- 支持递归嵌套（子实例可以有自己的子实例）
- 配置方式一致，易于理解

### 3. 自然并行执行

**设计原则**：依赖 Claude SDK 的自动并行能力，不手动实现并行逻辑。

```python
# ❌ 不需要手动实现：
# await instance_manager.execute_parallel(tasks)

# ✅ 让 Claude 自然决定：
prompt = "请同时调用 code_reviewer 和 document_writer 子实例"
result = await agent.query_text(prompt)
# Claude SDK 自动并行执行工具调用
```

**优势**：
- 更简洁的代码
- 利用 Claude SDK 的优化
- Claude 可以智能决定何时并行

### 4. 递归嵌套支持

**设计原则**：每一层都是完整的 `AgentSystem`，支持无限嵌套。

```
Parent Agent
  ├─ Tool: calculator
  └─ Sub Claude: code_reviewer
       ├─ Tool: lint_checker
       └─ Sub Claude: syntax_analyzer
            ├─ Tool: parser
            └─ Sub Claude: ...（继续嵌套）
```

**使用场景**：
- 分层任务分解
- 专业领域代理
- 复杂工作流编排

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

### 1. 基本使用

```python
import asyncio
from src import AgentSystem

async def main():
    # 创建 agent 系统（使用示例实例）
    agent = AgentSystem("example_agent")

    # 初始化系统
    await agent.initialize()

    # 执行查询
    response = await agent.query_text("使用计算器计算 123 + 456")
    print(response)

# 运行
asyncio.run(main())
```

### 2. 流式响应

```python
import asyncio
from src import AgentSystem

async def main():
    agent = AgentSystem("example_agent")
    await agent.initialize()

    # 流式获取响应
    async for message in agent.query("分析这个项目的目录结构"):
        if hasattr(message, "text"):
            print(message.text, end="", flush=True)

asyncio.run(main())
```

## 系统架构

### 整体架构图

```
┌─────────────────────────────────────────────────────────┐
│                     AgentSystem                         │
│  (主类，整合所有组件)                                   │
└─────────────────────────────────────────────────────────┘
              ▲         ▲          ▲          ▲
              │         │          │          │
      ┌───────┘    ┌────┘     ┌────┘     ┌────┘
      │            │          │          │
┌─────┴─────┐ ┌───┴────┐ ┌───┴────┐ ┌───┴────────┐
│  Config   │ │ Tool   │ │Instance│ │   Claude   │
│  Loader   │ │Manager │ │Manager │ │  SDK/API   │
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

### 核心模块职责

#### 1. **AgentSystem** (系统主类)
- **职责**：整合所有组件，提供统一接口
- **关键方法**：
  - `initialize()` - 初始化所有组件
  - `query()` / `query_text()` - 执行查询
- **特点**：子实例也是 AgentSystem，支持递归

#### 2. **ConfigLoader** (配置加载器)
- **职责**：读取和解析 config.yaml
- **功能**：
  - YAML 解析和验证
  - 环境变量替换
  - 路径解析（相对/绝对）
  - 生成 ClaudeAgentOptions

#### 3. **ToolManager** (工具管理器)
- **职责**：发现和管理自定义工具
- **功能**：
  - 扫描 tools/ 目录
  - 发现带 @tool 装饰器的函数
  - 创建本地 MCP 服务器
  - 工具名称生成（模块名__函数名）

#### 4. **InstanceManager** (子实例管理器)
- **职责**：管理子 Claude 实例的工具定义
- **功能**：
  - 创建子实例工具定义
  - 生成子实例 MCP 服务器
  - **不负责**：实例化（延迟到调用时）、并行执行（由 SDK 处理）

#### 5. **claude_instance_wrapper** (子实例封装)
- **职责**：创建子实例工具函数
- **特点**：
  - 工具定义在配置时创建
  - 工具调用时动态创建 AgentSystem
  - 支持参数：task, context_files, output_format, max_turns, variables, cwd

### 执行流程

#### 初始化流程
```
1. 创建 AgentSystem(instance_name)
   │
2. await agent.initialize()
   │
   ├─> ConfigLoader.load()
   │   ├─ 读取 config.yaml
   │   ├─ 验证配置
   │   └─ 解析路径和环境变量
   │
   ├─> ToolManager.discover_tools()
   │   ├─ 扫描 tools/ 目录
   │   ├─ 提取 @tool 装饰的函数
   │   └─ 创建本地 MCP 服务器
   │
   ├─> InstanceManager.load_instances()
   │   ├─ 读取子实例配置
   │   ├─ 创建工具定义（不实例化）
   │   └─ 生成子实例 MCP 服务器
   │
   └─> 合并所有 MCP 服务器
       └─ 生成 ClaudeAgentOptions
```

#### 子实例调用流程
```
1. Claude 决定调用子实例工具
   │
2. 触发工具函数 execute_instance(args)
   │
3. 动态创建 AgentSystem
   │   sub_agent = AgentSystem(instance_path)
   │
4. 初始化子实例
   │   await sub_agent.initialize()
   │   (可能递归加载子实例的子实例)
   │
5. 执行查询
   │   result = await sub_agent.query_text(prompt)
   │
6. 返回结果给父 Claude
```

#### 并行执行流程
```
Claude 收到提示词
   │
Claude 分析任务
   │
Claude 决定使用多个工具
   ├─ Tool A
   ├─ Tool B (子实例)
   └─ Tool C (子实例)
   │
Claude SDK 自动并行执行
   ├─ 同时调用多个工具
   ├─ 等待所有完成
   └─ 聚合结果
   │
Claude 综合结果并响应
```

## 项目结构

```
claude_agent_system/
├── src/                              # 核心框架源码
│   ├── agent_system.py              # 系统主类（整合所有组件）
│   ├── config_loader.py             # 配置加载器
│   ├── config_validator.py          # 配置验证器
│   ├── tool_manager.py              # 工具管理器
│   ├── claude_instance_wrapper.py   # 子实例封装（延迟实例化）
│   ├── instance_manager.py          # 子实例管理器
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
│       └── tools/                   # 自定义工具
│           ├── __init__.py
│           └── calculator.py        # 示例工具
│
├── examples/                         # 使用示例
│   ├── basic_usage.py               # 基础使用
│   ├── parallel_execution.py        # 并行执行（展示自然并行）
│   └── custom_tools.py              # 自定义工具
│
├── requirements.txt                  # 依赖列表
├── README.md                         # 项目文档
└── .env.example                      # 环境变量示例
```

## 配置文件说明

### config.yaml

```yaml
# 基础配置
agent:
  name: "example_agent"
  description: "示例智能体"

model: "claude-sonnet-4-5"
system_prompt_file: ".claude/CLAUDE.md"

# 工具配置
tools:
  allowed:
    - "Read"
    - "Write"
    - "mcp__custom_tools__calculator__*"

# 高级配置
advanced:
  permission_mode: "acceptEdits"
  max_turns: 50
  setting_sources:
    - "project"
```

## 自定义工具

在 `instances/<your_agent>/tools/` 目录下创建 Python 文件，使用 `@tool` 装饰器定义工具：

```python
from claude_agent_sdk import tool
from typing import Any, Dict

@tool(
    name="my_tool",
    description="我的自定义工具",
    input_schema={
        "param1": {
            "type": "string",
            "description": "参数1"
        }
    }
)
async def my_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    result = args.get("param1", "")

    return {
        "content": [{
            "type": "text",
            "text": f"处理结果: {result}"
        }]
    }
```

工具会被自动发现并加载，命名格式为 `mcp__custom_tools__<模块名>__<工具名>`。

## 子 Claude 实例（高级特性）

### 核心概念

子 Claude 实例是完整的 `AgentSystem`，可以：
- 拥有自己的配置和工具
- 拥有自己的子实例（递归嵌套）
- 被封装成工具供父 Claude 调用
- 在工具调用时才实例化（延迟加载）

### 创建子实例

#### 1. 创建子实例目录
```bash
instances/
├── parent_agent/              # 父实例
│   └── config.yaml
└── code_reviewer_agent/       # 子实例
    ├── config.yaml            # 完整配置，和父实例一样
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

tools:
  allowed:
    - "Read"
    - "Grep"
    - "mcp__custom_tools__lint__*"

# 子实例也可以有自己的子实例！
sub_claude_instances:
  syntax_checker: "syntax_checker_agent"
```

#### 3. 在父实例中配置子实例
```yaml
# parent_agent/config.yaml
sub_claude_instances:
  code_reviewer: "code_reviewer_agent"
  document_writer: "document_writer_agent"

tools:
  allowed:
    - "Read"
    - "Write"
    - "mcp__sub_instances__sub_claude_*"  # 允许子实例工具
```

### 使用子实例

#### 方式 1：让 Claude 自然调用（推荐）

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
```

**发生了什么？**
1. 父 Claude 分析提示词
2. 决定调用 `mcp__sub_instances__sub_claude_code_reviewer` 工具
3. 工具被调用时，动态创建 `AgentSystem("code_reviewer_agent")`
4. 子实例初始化并执行任务
5. 结果返回给父 Claude
6. 父 Claude 综合结果并响应

#### 方式 2：并行调用多个子实例

```python
prompt = """
请同时执行以下任务：
1. 使用 code_reviewer 审查代码质量
2. 使用 document_writer 生成技术文档

两个任务可以并行进行。
"""

result = await agent.query_text(prompt)
# Claude SDK 自动并行执行两个子实例
```

### 子实例工具参数

子实例工具接受以下参数：

```python
{
    "task": "要执行的任务",           # 必需
    "context_files": [              # 可选，传递文件路径
        "src/main.py",
        "docs/README.md"
    ],
    "output_format": "markdown",    # 可选：text/json/markdown
    "max_turns": 10,                # 可选，限制执行轮次
    "variables": {                  # 可选，传递变量
        "project_name": "MyApp",
        "version": "1.0.0"
    },
    "cwd": "/path/to/project"       # 可选，工作目录
}
```

Claude 会根据需要填充这些参数。

### 递归嵌套示例

```yaml
# 三层嵌套结构
Level 1: main_agent
  ├─ code_reviewer (Level 2)
  │   └─ syntax_checker (Level 3)
  └─ document_writer (Level 2)
      └─ markdown_formatter (Level 3)
```

每一层都是完整的 AgentSystem，可以独立运行或被上层调用。

### 延迟实例化的好处

```python
# 初始化时
agent = AgentSystem("parent_agent")
await agent.initialize()
# ✅ 只创建了工具定义
# ❌ 没有创建 code_reviewer 的 AgentSystem 实例

# 调用时
result = await agent.query_text("请 code_reviewer 审查代码")
# ✅ 现在才创建 AgentSystem("code_reviewer_agent")
# ✅ 执行完毕后释放资源

# 好处：
# - 启动速度快（即使配置了100个子实例）
# - 内存占用少（只实例化需要的）
# - 每次调用都是全新的上下文
```

## 示例

查看 `examples/` 目录获取完整示例：

- `basic_usage.py` - 基础使用示例
- `parallel_execution.py` - 并行执行子实例
- `custom_tools.py` - 自定义工具示例

## API 文档

### AgentSystem

主类，用于管理和运行 Claude Agent 实例。

**初始化**

```python
agent = AgentSystem(
    instance_name="example_agent",  # 实例名称或路径
    api_key=None,                   # API 密钥（可选，从环境变量读取）
    instances_root=None             # 实例根目录（可选）
)
```

**方法**

- `async initialize()` - 初始化系统
- `async query(prompt: str)` - 执行查询，返回异步迭代器
- `async query_text(prompt: str)` - 执行查询，返回文本字符串

**属性**

- `agent_name` - Agent 名称
- `agent_description` - Agent 描述
- `tools_count` - 工具数量
- `instances_count` - 子实例数量

## 错误处理

```python
from src import AgentSystem, AgentSystemError

try:
    agent = AgentSystem("example_agent")
    await agent.initialize()
except AgentSystemError as e:
    print(f"系统错误: {e}")
```

## 日志配置

```python
from src import set_log_level
import logging

# 设置日志级别
set_log_level(logging.DEBUG)
```

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！

## 常见问题

### 设计理念相关

#### Q1: 为什么不在初始化时就实例化所有子 Claude？
**A**: 延迟实例化有以下优势：
- **性能**：启动速度快，即使配置了大量子实例
- **资源**：只实例化需要的子实例，节省内存
- **灵活性**：每次调用都是全新的上下文，不会互相干扰

#### Q2: 为什么删除了 execute_parallel 函数？
**A**: 因为我们不需要手动实现并行逻辑：
- Claude SDK 本身支持并行调用工具
- 当 Claude 决定同时使用多个工具时，SDK 自动并行执行
- 这使得代码更简洁，更符合 Claude 的工作方式

#### Q3: 子实例为什么使用 AgentSystem 而不是直接调用 SDK？
**A**: 使用 AgentSystem 的好处：
- **统一接口**：父子实例使用相同的类和配置方式
- **递归嵌套**：子实例可以有自己的子实例
- **完整功能**：子实例也能使用工具、配置等所有功能

#### Q4: 子实例可以无限嵌套吗？
**A**: 理论上可以，但建议：
- 保持在 2-3 层以内
- 过深的嵌套会增加复杂度和延迟
- 根据实际需求设计层级结构

### 使用相关

#### Q5: 如何添加新的实例？
**A**: 在 `instances/` 目录下创建新目录，复制 `example_agent` 的配置并修改。

#### Q6: 工具命名规则是什么？
**A**:
- 自定义工具：`mcp__custom_tools__<模块名>__<工具名>`
- 子实例工具：`mcp__sub_instances__sub_claude_<实例名>`
- 外部 MCP 工具：`mcp__<服务器名>__<工具名>`

#### Q7: 如何让 Claude 并行调用多个子实例？
**A**: 在提示词中明确说明需要并行执行：
```python
prompt = """
请同时使用以下子实例：
1. code_reviewer - 审查代码
2. test_writer - 编写测试

两个任务可以并行进行。
"""
```
Claude SDK 会自动处理并行执行。

#### Q8: 如何调试工具加载问题？
**A**: 设置日志级别为 DEBUG：
```python
from src import set_log_level
import logging
set_log_level(logging.DEBUG)
```

#### Q9: 如何配置外部 MCP 服务器？
**A**: 在实例目录下创建 `.mcp.json` 文件：
```json
{
  "mcpServers": {
    "weather": {
      "type": "stdio",
      "command": "node",
      "args": ["./mcp-servers/weather/index.js"]
    }
  }
}
```
然后在 `config.yaml` 中通过 `allowed_tools` 控制访问：
```yaml
tools:
  allowed:
    - "mcp__weather__*"
```
支持的类型：stdio、http、sse

详细说明请参考：`instances/example_agent/MCP_SETUP.md`

#### Q10: 子实例可以使用不同的模型吗？
**A**: 可以！每个实例的 config.yaml 都可以指定不同的模型：
```yaml
# parent: claude-sonnet-4-5
# child1: claude-opus-4-5  (需要更强推理能力)
# child2: claude-haiku-4   (简单任务，速度快)
```

## 联系方式

如有问题或建议，请提交 Issue 或联系维护者。
