# Claude Agent System 使用示例

本目录包含了 Claude Agent System 的完整使用示例和测试套件。

## 📁 目录结构

```
examples/
├── README.md                     # 本文件 - 使用指南
├── demo_test_suite.py           # 完整测试套件 - 测试所有功能
├── basic_usage.py               # 基础使用示例
├── parallel_execution.py        # 并行执行示例
├── custom_tools.py              # 自定义工具示例
├── session_recording.py         # 会话记录示例
└── step_by_step_tests/          # 分步测试目录
    ├── test_01_basic_tools.py       # 测试1: 基础工具
    ├── test_02_custom_tools.py      # 测试2: 自定义工具
    ├── test_03_session_recording.py # 测试3: 会话记录
    ├── test_04_sub_instances.py     # 测试4: 子实例系统
    └── test_05_parallel_execution.py # 测试5: 并行执行
```

## 🚀 快速开始

### 1. 完整功能测试

运行完整的测试套件，测试系统的所有功能：

```bash
cd examples
python demo_test_suite.py
```

这将运行 9 个综合测试，包括：
- 系统初始化
- 配置系统
- 基础工具
- 自定义工具
- 会话记录
- 子实例系统
- 并行执行
- 综合场景
- 会话查询

### 2. 基础使用示例

如果您是第一次使用，建议先运行基础示例：

```bash
python basic_usage.py
```

### 3. 分步测试

如果您想深入了解特定功能，可以运行分步测试：

```bash
# 测试基础工具
python step_by_step_tests/test_01_basic_tools.py

# 测试自定义工具
python step_by_step_tests/test_02_custom_tools.py

# 测试会话记录
python step_by_step_tests/test_03_session_recording.py

# 测试子实例系统
python step_by_step_tests/test_04_sub_instances.py

# 测试并行执行
python step_by_step_tests/test_05_parallel_execution.py
```

## 📋 测试说明

### test_01_basic_tools.py - 基础工具测试

测试 Claude Agent System 的基础工具：
- **Read**: 文件读取
- **Write**: 文件写入
- **Bash**: 命令执行
- **Glob**: 文件模式匹配
- **Grep**: 文本搜索
- **工具组合**: 多工具协同工作

### test_02_custom_tools.py - 自定义工具测试

测试 Demo Agent 的自定义工具：
- **Calculator**: 数学计算
- **File Analyzer**: 文件分析
- **Text Processor**: 文本处理
- **错误处理**: 异常情况处理
- **工具组合**: 自定义工具协同

### test_03_session_recording.py - 会话记录测试

测试会话记录系统的各项功能：
- **会话管理**: 创建、更新、查询
- **消息记录**: 自动记录所有交互
- **统计信息**: 性能和使用统计
- **调用关系图**: 可视化调用链
- **会话导出**: JSON/Markdown 格式导出
- **会话搜索**: 按内容搜索会话

### test_04_sub_instances.py - 子实例系统测试

测试子实例的创建和调用：
- **基础调用**: 简单的子实例调用
- **多实例协作**: 多个子实例协同工作
- **嵌套调用**: 子实例调用其他子实例
- **参数传递**: 实例间的数据传递
- **错误处理**: 异常传播和处理
- **性能对比**: 直接调用 vs 子实例调用

### test_05_parallel_execution.py - 并行执行测试

测试系统的并行处理能力：
- **工具并行**: 多个工具同时执行
- **串行对比**: 性能对比分析
- **子实例并行**: 多个子实例并行执行
- **混合并行**: 工具和子实例混合并行
- **流式响应**: 实时结果流
- **并发限制**: 高并发处理能力

## 📊 测试结果

运行测试后，您会看到详细的测试报告，包括：

- ✅ **通过测试**: 成功的功能
- ❌ **失败测试**: 遇到的问题
- ⏱️ **性能数据**: 执行时间统计
- 📈 **成功率**: 整体测试通过率
- 💾 **详细报告**: 保存到 `test_report.json`

## 🔧 环境要求

确保您的环境满足以下要求：

1. **Python 3.8+**
2. **依赖包**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Anthropic API Key**: 设置环境变量 `ANTHROPIC_API_KEY`
4. **Demo Agent**: 确保 `instances/demo_agent/` 目录存在且配置正确

## 🐛 故障排除

### 常见问题

1. **导入错误**
   ```
   ModuleNotFoundError: No module named 'src'
   ```
   - 确保在项目根目录运行
   - 检查 Python 路径设置

2. **API 错误**
   ```
   anthropic.APIError: Invalid API key
   ```
   - 检查 `ANTHROPIC_API_KEY` 环境变量
   - 确认 API Key 有效

3. **实例未找到**
   ```
   FileNotFoundError: instances/demo_agent/config.yaml
   ```
   - 确保 demo_agent 实例存在
   - 检查文件路径是否正确

4. **权限错误**
   ```
   PermissionError: [Errno 13] Permission denied
   ```
   - 检查文件/目录权限
   - 确保有写入权限（会话记录需要）

### 调试模式

启用详细日志进行调试：

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

或在测试文件中修改：

```python
set_log_level(logging.DEBUG)
```

## 📚 更多示例

### 自定义场景

您可以基于这些测试创建自己的场景：

```python
import asyncio
from src import AgentSystem

async def custom_test():
    agent = AgentSystem("demo_agent")
    await agent.initialize()

    # 您的自定义测试代码
    response = await agent.query_text("您的自定义提示")
    print(response)

asyncio.run(custom_test())
```

### 性能测试

测试特定场景的性能：

```python
import time

start_time = time.time()
response = await agent.query_text("复杂任务")
duration = time.time() - start_time

print(f"执行时间: {duration:.2f}秒")
```

## 📝 贡献

如果您想贡献更多示例：

1. 在 `step_by_step_tests/` 添加新测试
2. 遵循命名规范 `test_XX_description.py`
3. 包含完整的错误处理
4. 添加详细的注释
5. 更新本 README 文档

## 🔗 相关文档

- [主项目文档](../CLAUDE.md)
- [API 文档](../docs/)
- [配置指南](../docs/configuration.md)
- [开发指南](../docs/development.md)

---

💡 **提示**: 建议按顺序运行测试，从基础工具开始，逐步深入到复杂功能。每个测试都是独立的，可以单独运行。