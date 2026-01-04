# 子实例系统

子实例系统是 Claude Agent System 的高级特性，允许创建嵌套的 Agent 实例，实现复杂任务的分解和专业化处理。

## 目录

- [系统概述](#系统概述)
- [创建子实例](#创建子实例)
- [子实例配置](#子实例配置)
- [子实例工具](#子实例工具)
- [会话追踪](#会话追踪)
- [使用场景](#使用场景)
- [最佳实践](#最佳实践)
- [高级特性](#高级特性)

## 系统概述

### 什么是子实例

子实例是完整的 `AgentSystem` 实例，可以作为工具被父实例调用。每个子实例都有：

- 独立的配置文件
- 专用的工具集
- 独立的会话记录
- 可选的专用模型

### 架构设计

```
Parent Agent (demo_agent)
├─ Tools: calculator, file_reader
├─ Sub Instances:
│  ├─ code_reviewer (使用 opus 模型)
│  │  ├─ Tools: lint_checker, security_scanner
│  │  └─ Prompts: 专注代码审查
│  │
│  └─ data_analyzer (使用 sonnet 模型)
│     ├─ Tools: csv_reader, chart_generator
│     └─ Prompts: 专注数据分析
│
└─ Session: 记录所有子实例调用
```

### 核心特性

1. **递归嵌套**：支持无限层级的子实例嵌套
2. **延迟实例化**：只在调用时创建子实例
3. **自动清理**：调用完成后自动释放资源
4. **会话追踪**：自动记录父子会话关系
5. **独立存储**：子实例会话独立存储

## 创建子实例

### 1. 创建子实例目录

首先创建子实例的目录结构：

```
instances/
├── parent_agent/              # 父实例
│   ├── config.yaml
│   ├── .claude/
│   │   └── agent.md
│   └── tools/
│       └── calculator.py
│
└── code_reviewer_agent/       # 子实例
    ├── config.yaml           # 子实例配置
    ├── .claude/
    │   └── agent.md          # 子实例专用提示词
    └── tools/                # 子实例专用工具
        ├── lint_checker.py
        ├── security_scanner.py
        └── complexity_analyzer.py
```

### 2. 配置子实例

#### 子实例配置示例

```yaml
# instances/code_reviewer_agent/config.yaml

agent:
  name: "code_reviewer"
  description: "专业的代码审查助手"

model: "claude-opus-4-5"  # 使用更强大的模型
system_prompt_file: ".claude/agent.md"

# 代码审查专用的工具权限
tools:
  allowed:
    - "mcp__custom_tools__lint_checker_*"
    - "mcp__custom_tools__security_scanner_*"
    - "mcp__custom_tools__complexity_analyzer_*"
  disallowed:
    - "WebSearch"           # 禁止网络搜索

# 会话记录配置
session_recording:
  enabled: true
  retention_days: 90        # 代码审查记录保留更久

# 高级配置
advanced:
  max_turns: 50             # 限制对话轮数
  permission_mode: "auto"
```

#### 子实例专用提示词

```markdown
<!-- instances/code_reviewer_agent/.claude/agent.md -->

# 代码审查助手

你是一个专业的代码审查助手，专注于发现代码中的问题并提供改进建议。

## 审查重点

1. **代码质量**
   - 命名规范
   - 代码结构
   - 设计模式
   - 可读性

2. **安全性**
   - 注入攻击
   - 权限控制
   - 数据验证
   - 敏感信息泄露

3. **性能**
   - 算法效率
   - 内存使用
   - 数据库查询
   - 缓存策略

4. **最佳实践**
   - 错误处理
   - 日志记录
   - 单元测试
   - 文档注释

## 输出格式

使用以下结构输出审查结果：

```markdown
# 代码审查报告

## 总体评价
[整体评价和评分]

## 发现的问题
### 严重问题
- [问题描述]

### 建议改进
- [改进建议]

## 代码示例
[提供改进后的代码示例]

```

请专注于代码质量和安全性，提供具体可行的改进建议。
```

### 3. 在父实例中配置子实例

```yaml
# instances/parent_agent/config.yaml

# 其他配置...

# 子实例配置
sub_claude_instances:
  code_reviewer: "code_reviewer_agent"
  data_analyzer: "data_analyzer_agent"
  document_writer: "document_writer_agent"
```

## 子实例工具

### SubInstanceTool 参数

子实例作为工具时，支持以下参数：

```python
# 子实例工具调用示例（由 Claude 自动生成）
await sub_claude_code_reviewer(
    task="审查这段 Python 代码的质量和安全性",
    parent_session_id="parent_session_id",  # 必填：父会话ID
    context_files=[                       # 相关文件
        "src/main.py",
        "src/utils.py"
    ],
    output_format="markdown",             # 输出格式
    resume_session_id=None,               # 恢复之前的子会话
    variables={                           # 额外变量
        "focus_areas": ["security", "performance"]
    }
)
```

### 参数说明

- **task**（必填）：任务描述，告诉子实例要做什么
- **parent_session_id**（必填）：父会话ID，用于追踪会话关系
- **context_files**（可选）：相关文件列表，子实例可以访问这些文件
- **output_format**（可选）：输出格式，支持 `text`、`json`、`markdown`
- **resume_session_id**（可选）：恢复之前的子会话，实现多轮对话
- **variables**（可选）：额外的键值对，传递给子实例

## 会话追踪

### 自动追踪机制

系统会自动追踪子实例的会话，建立父子关系：

1. **调用时**：父实例记录子实例调用信息
2. **返回时**：子实例在响应中嵌入会话ID标记
3. **解析时**：父实例解析并记录子会话ID

### 会话树结构

```json
{
  "session_id": "20251216T103000_1234_abcd1234",
  "instance_name": "parent_agent",
  "depth": 0,
  "subsessions": [
    {
      "session_id": "20251216T103200_5678_efgh5678",
      "tool_name": "sub_claude_code_reviewer",
      "tool_use_id": "toolu_abc123",
      "timestamp": "2025-12-16T10:32:00",
      "instance_name": "code_reviewer_agent",
      "depth": 1
    }
  ]
}
```

### 查询子会话

```python
from src.session.session_query import get_session_details

# 获取父会话详情
parent_details = get_session_details(
    instance_name="parent_agent",
    session_id="parent_session_id"
)

# 查看子会话列表
subsessions = parent_details['statistics']['subsessions']
for sub in subsessions:
    print(f"子会话: {sub['session_id']}")
    print(f"工具: {sub['tool_name']}")

    # 获取子会话详情
    sub_details = get_session_details(
        instance_name=sub['instance_name'],
        session_id=sub['session_id']
    )
```

## 使用场景

### 1. 专业化处理

不同类型的任务使用专门配置的子实例：

```python
# 父实例：项目管理器
agent = AgentSystem("project_manager")

# Claude 会根据任务自动选择合适的子实例
prompt = """
请帮我完成以下任务：

1. 审查 src/auth.py 的安全性
2. 分析 sales_data.csv 并生成报告
3. 编写 API 文档

"""
result = await agent.query_text(prompt)
```

### 2. 多模态处理

不同子实例处理不同类型的数据：

```yaml
# instances/multimodal_agent/config.yaml
sub_claude_instances:
  text_processor: "text_analyzer_agent"      # 文本分析
  image_analyzer: "image_vision_agent"       # 图像分析
  code_reviewer: "code_reviewer_agent"       # 代码审查
  data_analyzer: "data_analyzer_agent"       # 数据分析
```

### 3. 工作流编排

构建复杂的任务工作流：

```python
# 示例：自动化代码审查流程
async def automated_code_review(pr_id: str):
    manager = AgentSystem("pr_manager")
    await manager.initialize()

    # 第一步：代码审查
    review_result = await manager.query_text(
        f"使用 code_reviewer 子实例审查 PR #{pr_id}",
        context_files=["pr_diff.patch"]
    )

    # 第二步：安全扫描
    security_result = await manager.query_text(
        f"使用 security_scanner 子实例扫描 PR #{pr_id}",
        resume_session_id=review_result.session_id
    )

    # 第三步：生成报告
    report = await manager.query_text(
        "生成综合审查报告",
        resume_session_id=security_result.session_id
    )

    return report
```

## 最佳实践

### 1. 子实例设计原则

- **单一职责**：每个子实例专注于特定领域
- **适当规模**：避免创建过多或过大的子实例
- **清晰接口**：明确子实例的输入输出格式
- **独立测试**：子实例应该可以独立测试

### 2. 配置建议

```yaml
# 专业化配置示例
agent:
  name: "security_analyzer"
  description: "专注于安全分析"

model: "claude-opus-4-5"  # 复杂任务使用更强模型

# 限制工具范围
tools:
  allowed:
    - "mcp__custom_tools__security_*"
    - "Read"              # 只允许读取文件
    - "Grep"              # 和搜索
  disallowed:
    - "Write"             # 禁止写入
    - "Bash"              # 禁止执行命令

# 短会话配置
session_recording:
  enabled: true
  retention_days: 30
  max_total_size_mb: 100  # 安全分析不需要大量存储
```

### 3. 性能优化

- **延迟创建**：子实例只在首次调用时创建
- **及时清理**：调用完成后自动清理资源
- **并发控制**：避免同时创建过多子实例
- **缓存结果**：对重复任务使用会话恢复

### 4. 错误处理

```python
# 父实例中的错误处理
async def safe_sub_instance_call(task: str):
    try:
        result = await agent.query_text(
            f"使用 code_reviewer 审查: {task}"
        )
        return result
    except Exception as e:
        # 记录错误并继续
        logger.error(f"子实例调用失败: {e}")
        return {
            "result": f"子实例不可用，错误: {e}",
            "fallback_used": True
        }
```

## 高级特性

### 1. 动态子实例

根据运行时条件选择子实例：

```python
# instances/adaptive_agent/config.yaml
sub_claude_instances:
  reviewer: "code_reviewer_agent"
  analyzer: "code_analyzer_agent"
  optimizer: "code_optimizer_agent"
```

```python
# 父实例会根据任务类型自动选择
prompt = """
这段代码性能有问题，请帮我分析和优化。

# 代码：
def process_data(data):
    result = []
    for item in data:
        if item.type == "A":
            result.append(process_a(item))
        elif item.type == "B":
            result.append(process_b(item))
    return result
"""

# Claude 会自动选择 code_optimizer_agent 而不是 code_reviewer_agent
```

### 2. 子实例链式调用

子实例可以调用其他子实例：

```
Parent Agent
└─ Sub Instance: project_manager
   ├─ Calls: code_reviewer
   │  └─ Calls: security_scanner
   └─ Calls: document_generator
```

### 3. 会话恢复

在子实例中实现多轮对话：

```python
# 第一次调用
result1 = await agent.query_text(
    "审查这段代码的安全性",
    # 使用 code_reviewer 子实例
)

# 继续在同一个子会话中对话
result2 = await agent.query_text(
    "请详细解释第二个安全漏洞",
    resume_session_id=result1.session_id  # 继续子会话
)
```

### 4. 变量传递

通过 variables 参数传递上下文：

```python
await agent.query_text(
    "生成测试计划",
    variables={
        "project_type": "web_api",
        "testing_framework": "pytest",
        "coverage_target": 80
    }
)
```

子实例可以访问这些变量：

```python
# 在子实例的工具中
def get_testing_plan(context):
    project_type = context.get("variables", {}).get("project_type")
    # 根据变量生成不同的测试计划
```

## 故障排除

### 常见问题

1. **子实例创建失败**
   - 检查子实例配置文件
   - 验证子实例目录结构
   - 确认依赖项已安装

2. **会话追踪丢失**
   - 确保传递了 `parent_session_id`
   - 检查会话记录是否启用
   - 验证消息总线连接

3. **性能问题**
   - 减少子实例数量
   - 优化子实例配置
   - 使用会话恢复避免重复创建

4. **权限问题**
   - 检查子实例的工具权限配置
   - 验证文件访问权限
   - 确认 MCP 服务器配置

### 调试技巧

1. **查看子实例调用日志**
   ```python
   # 在父实例中
   logging.getLogger("src.sub_instance_adapter").setLevel(logging.DEBUG)
   ```

2. **独立测试子实例**
   ```python
   # 直接创建子实例测试
   sub_agent = AgentSystem("code_reviewer_agent")
   await sub_agent.initialize()
   result = await sub_agent.query_text("测试任务")
   ```

3. **检查会话关系**
   ```python
   from src.session.query import SessionTreeBuilder
   builder = SessionTreeBuilder()
   tree = await builder.build_tree(parent_session_id)
   print(tree)
   ```

## 总结

子实例系统提供了强大的任务分解和专业化处理能力：

- **模块化**：将复杂任务分解为专门的子任务
- **专业化**：每个子实例专注于特定领域
- **可扩展**：支持无限层级嵌套
- **可追踪**：完整的会话关系记录
- **高效**：延迟创建和自动清理

合理使用子实例系统可以大大提高 Claude Agent 的处理能力和任务完成质量。