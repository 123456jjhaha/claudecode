# 配置指南

本文档详细说明了 Claude Agent System 的所有配置选项。

## 目录

- [实例配置](#实例配置)
- [实时消息系统配置](#实时消息系统配置)
- [环境变量配置](#环境变量配置)
- [工具权限配置](#工具权限配置)
- [子实例配置](#子实例配置)
- [会话记录配置](#会话记录配置)
- [高级配置选项](#高级配置选项)
- [外部 MCP 服务器配置](#外部-mcp-服务器配置)

## 实例配置

每个 Agent 实例都有自己的配置文件 `instances/{instance_name}/config.yaml`。

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

### 配置字段说明

#### agent 部分
- `name`: Agent 实例名称（必填）
- `description`: Agent 描述（可选）

#### model 部分
- `model`: 使用的 Claude 模型（必填）
  - 可选值：`claude-sonnet-4-5`、`claude-opus-4-5` 等
- `system_prompt_file`: 系统提示词文件路径（可选）
  - 默认查找顺序：`agent.md` → `system_prompt.md` → `agent_prompt.md`

## 实时消息系统配置

实时消息系统支持全局配置，通过 `streaming.yaml` 文件或环境变量配置。

### streaming.yaml 配置（推荐）

在项目根目录创建 `streaming.yaml`：

```yaml
# 实时消息总线配置
redis:
  url: "redis://localhost:6379"
  db: 0
  max_connections: 50

# 异步写入配置
async_write:
  batch_size: 10        # 批量写入的消息数量
  flush_interval: 1.0   # 定时刷新间隔（秒）
```

### 环境变量配置

也可以通过环境变量进行配置（优先级高于 streaming.yaml）：

```bash
# Redis 配置
REDIS_URL=redis://localhost:6379
REDIS_DB=0
REDIS_MAX_CONNECTIONS=50

# 异步写入配置
ASYNC_WRITE_BATCH_SIZE=10
ASYNC_WRITE_FLUSH_INTERVAL=1.0
```

### 配置优先级

1. 环境变量（最高优先级）
2. streaming.yaml
3. 默认值

## 工具权限配置

### 工具权限说明

**重要**：内置工具（Read, Write, Bash 等）默认全部允许，要禁止需在 `disallowed` 中明确列出。

`allowed` 列表主要用于限制 MCP 工具：
- **自定义工具**：`tools/` 目录下的异步函数
- **子实例工具**：封装的子 Claude 实例
- **外部 MCP 服务器**：通过 `.mcp.json` 配置的外部服务

### 通配符支持

支持通配符 `*` 进行模式匹配：

```yaml
tools:
  allowed:
    - "mcp__custom_tools__calculator__*"      # 允许所有 calculator 工具
    - "mcp__custom_tools__sub_claude_*"       # 允许所有子实例工具
    - "mcp__external_*"                       # 允许所有外部 MCP 服务器
```

## 子实例配置

子实例是完整的 `AgentSystem`，可以有自己的配置和工具。

### 配置子实例

```yaml
# 在父实例的 config.yaml 中
sub_claude_instances:
  file_analyzer: "file_analyzer_agent"
  code_reviewer: "code_reviewer_agent"
  syntax_checker: "syntax_checker_agent"
```

### 子实例目录结构

```
instances/
├── parent_agent/
│   ├── config.yaml
│   └── tools/
└── file_analyzer_agent/         # 子实例
    ├── config.yaml              # 子实例的独立配置
    ├── .claude/
    │   └── agent.md            # 子实例的系统提示词
    └── tools/                   # 子实例的专用工具
        └── analyzer.py
```

## 会话记录配置

### 配置选项

```yaml
session_recording:
  enabled: true              # 是否启用会话记录
  retention_days: 30         # 保留天数
  max_total_size_mb: 1000   # 最大总大小（MB）
  auto_cleanup: true         # 自动清理过期会话
  message_types: null        # 记录的消息类型（null=全部）
```

### 消息类型过滤

可以指定只记录特定类型的消息：

```yaml
session_recording:
  message_types:             # 只记录这些类型
    - "UserMessage"
    - "AssistantMessage"
    - "ToolResultMessage"
```

## 高级配置选项

### permission_mode

```yaml
advanced:
  permission_mode: "bypassPermissions"  # 绕过权限检查
```

可选值：
- `"bypassPermissions"`: 绕过所有权限检查
- `"ask"`: 需要用户确认
- `"auto"`: 自动决策

### max_turns

```yaml
advanced:
  max_turns: 100  # 最大对话轮数
```

### SDK 环境变量

可以通过 `advanced.env` 设置 SDK 相关的环境变量：

```yaml
advanced:
  env:
    # Claude SDK 超时配置（毫秒）
    CLAUDE_CODE_STREAM_CLOSE_TIMEOUT: "300000"  # 5分钟
    MCP_TIMEOUT: "120000"                       # 2分钟
    MCP_TOOL_TIMEOUT: "180000"                  # 3分钟

    # 其他环境变量
    PYTHONPATH: "/custom/path"
    LOG_LEVEL: "DEBUG"
```

## 外部 MCP 服务器配置

可以通过 `.mcp.json` 文件配置外部 MCP 服务器。

### 示例配置

```json
{
  "mcpServers": {
    "database": {
      "command": "python",
      "args": ["-m", "database_mcp_server"],
      "env": {
        "DATABASE_URL": "postgresql://user:pass@localhost/db"
      }
    },
    "weather": {
      "command": "node",
      "args": ["./weather_server.js"],
      "env": {
        "WEATHER_API_KEY": "your-api-key"
      }
    }
  }
}
```

### 配置文件位置

- 项目根目录：`.claude/.mcp.json`
- 实例目录：`instances/{instance_name}/.claude/.mcp.json`

## 配置验证

系统会在启动时自动验证配置文件的正确性。

### 常见错误

1. **YAML 语法错误**
   - 使用 2 个空格缩进（不要使用 Tab）
   - 注意冒号后的空格

2. **必需字段缺失**
   - `agent.name` 和 `model` 是必填字段

3. **路径错误**
   - 使用相对路径时，相对于实例目录
   - 系统提示词文件必须存在

4. **权限配置错误**
   - `disallowed` 只能包含内置工具名称
   - `allowed` 中的模式必须以 `mcp__` 开头

## 最佳实践

1. **使用版本控制**
   - 将配置文件纳入 Git 管理
   - 使用 `.gitignore` 排除敏感信息

2. **环境特定配置**
   - 开发环境和生产环境使用不同的配置
   - 通过环境变量管理敏感信息

3. **模块化配置**
   - 将大型配置拆分为多个文件
   - 使用 YAML 的 `!include` 功能（如支持）

4. **定期审查**
   - 定期检查配置的有效性
   - 及时更新过期的配置选项