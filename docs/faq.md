# 常见问题

本文档收集了用户在使用 Claude Agent System 时经常遇到的问题和解决方案。

## 目录

- [安装和配置](#安装和配置)
- [工具开发](#工具开发)
- [会话管理](#会话管理)
- [实时消息系统](#实时消息系统)
- [子实例](#子实例)
- [性能和优化](#性能和优化)
- [错误处理](#错误处理)
- [部署和运维](#部署和运维)

## 安装和配置

### Q: 如何安装 Claude Agent System？

A: 通过 pip 安装依赖：

```bash
pip install -r requirements.txt
```

主要依赖包括：
- `claude-agent-sdk` - Claude Agent SDK
- `mcp>=1.0.0` - Model Context Protocol
- `pyyaml>=6.0` - 配置解析
- `redis>=5.0.0` - 实时消息系统（可选）

### Q: 实例配置文件应该放在哪里？

A: 配置文件位于 `instances/{instance_name}/config.yaml`。例如：

```
instances/
└── demo_agent/
    └── config.yaml
```

### Q: 系统提示词文件的查找顺序是什么？

A: 系统按以下顺序查找提示词文件：
1. `system_prompt_file` 配置指定的文件
2. `agent.md`
3. `system_prompt.md`
4. `agent_prompt.md`

推荐使用 `agent.md` 作为系统提示词文件名。

### Q: 如何配置不同的 Claude 模型？

A: 在 `config.yaml` 中指定 `model` 字段：

```yaml
model: "claude-sonnet-4-5"  # 或 claude-opus-4-5
```

### Q: 工具权限如何配置？

A: 内置工具默认全部允许，要禁止需在 `disallowed` 中列出：

```yaml
tools:
  disallowed:
    - "WebFetch"
    - "WebSearch"
  allowed:
    - "mcp__custom_tools__*"
```

## 工具开发

### Q: 如何创建自定义工具？

A: 在 `instances/{instance_name}/tools/` 目录下创建 Python 文件，编写异步函数：

```python
# instances/demo_agent/tools/calculator.py

async def add(a: float, b: float) -> dict:
    """计算两个数字的和

    Args:
        a: 第一个数字
        b: 第二个数字

    Returns:
        计算结果
    """
    return {"result": a + b}
```

### Q: 工具必须是异步函数吗？

A: 是的。系统只会自动发现 `async def` 函数作为工具。

### Q: 工具名称如何生成？

A: 自动生成规则：
- 文件名：`calculator.py`，函数名：`add`
- 工具名：`calculator__add`
- 完整 MCP 名称：`mcp__custom_tools__calculator__add`

### Q: 工具函数应该返回什么？

A: 建议返回结构化字典：

```python
return {
    "status": "success",
    "result": processed_data,
    "metadata": {...}
}
```

### Q: 如何在工具中处理错误？

A: 使用 try-except 并返回错误信息：

```python
async def safe_tool(data: str) -> dict:
    try:
        result = process_data(data)
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

## 会话管理

### Q: 会话记录影响性能吗？

A: 几乎不会。消息在内存中收集，会话结束时一次性写入。启用实时消息系统后会有轻微延迟（< 100ms）。

### Q: 如何实现多轮对话？

A: 使用 `resume_session_id` 参数：

```python
result1 = await agent.query_text("第一个问题")
result2 = await agent.query_text(
    "继续讨论",
    resume_session_id=result1.session_id
)
```

### Q: 会话 ID 是如何生成的？

A: 格式：`{timestamp}_{counter}_{short_hash}`
- 示例：`20251211T061755_0001_a3f9c2d8`
- 保证唯一性和可排序性

### Q: 如何查询历史会话？

A: 使用查询 API：

```python
from src.session.session_query import get_session_details, list_sessions

# 获取会话详情
details = get_session_details("demo_agent", session_id)

# 列出所有会话
sessions = list_sessions("demo_agent", limit=50)
```

### Q: 如何导出会话记录？

A: 使用 `export_session` 函数：

```python
from src.session.session_query import export_session

# 导出为 Markdown
markdown = export_session(
    "demo_agent",
    session_id,
    format="markdown"
)
```

### Q: 会话文件存储在哪里？

A: 存储在 `instances/{instance_name}/sessions/{session_id}/` 目录下：

```
instances/demo_agent/sessions/20251216T103000_1234_abcd1234/
├── metadata.json      # 会话元数据
├── messages.jsonl     # 消息记录
└── statistics.json   # 统计信息
```

## 实时消息系统

### Q: 必须使用 Redis 吗？

A: 不是。Redis 是可选的，用于实时消息推送。如果没有 Redis，系统会自动降级到批量写入模式。

### Q: 如何配置 Redis？

A: 创建 `streaming.yaml` 文件：

```yaml
redis:
  url: "redis://localhost:6379"
  db: 0
  max_connections: 50
```

或使用环境变量：
```bash
REDIS_URL=redis://localhost:6379
```

### Q: Redis 连接失败怎么办？

A: 系统会自动降级到内存模式，不会影响核心功能。检查 Redis 服务状态和配置。

### Q: 如何订阅实时消息？

A: 使用订阅 API：

```python
from src.session.query.session_query import subscribe_session_messages

async for event in subscribe_session_messages(session_id, message_bus):
    print(f"新消息: {event}")
```

### Q: 消息延迟是多少？

A: 正常情况下延迟 < 100ms。如果延迟过高，检查：
- Redis 服务器负载
- 网络连接质量
- 批量写入配置

## 子实例

### Q: 什么是子实例？

A: 子实例是完整的 AgentSystem 实例，作为工具被父实例调用，用于实现任务的专业化分解。

### Q: 如何创建子实例？

A: 创建独立的实例目录和配置：

```
instances/
├── parent_agent/
│   └── config.yaml
└── child_agent/
    ├── config.yaml
    ├── .claude/
    │   └── agent.md
    └── tools/
```

在父实例配置中引用：
```yaml
sub_claude_instances:
  child: "child_agent"
```

### Q: 子实例可以嵌套吗？

A: 可以。支持无限层级的子实例嵌套。

### Q: 如何追踪子实例的会话？

A: 系统自动追踪父子会话关系。子实例的 session_id 会记录在父会话的 statistics.json 中：

```json
{
  "subsessions": [
    {
      "session_id": "child_session_id",
      "tool_name": "sub_claude_child",
      "timestamp": "2025-12-16T10:30:00"
    }
  ]
}
```

### Q: 子实例调用为什么要传递 parent_session_id？

A: 用于建立父子会话关系，实现完整的会话追踪。这是必填参数。

### Q: 如何在子实例中继续对话？

A: 使用 `resume_session_id`：

```python
# 第一次调用
result1 = await agent.query_text("审查代码", context_files=["code.py"])

# 继续在子会话中
result2 = await agent.query_text(
    "详细解释第三个问题",
    resume_session_id=result1.session_id
)
```

## 性能和优化

### Q: 如何优化系统性能？

A: 几个优化建议：

1. **批量写入配置**：
   ```yaml
   async_write:
     batch_size: 20        # 增加批量大小
     flush_interval: 0.5   # 减少刷新间隔
   ```

2. **连接池配置**：
   ```yaml
   redis:
     max_connections: 100  # 增加连接数
   ```

3. **重用 Agent 实例**：避免频繁创建和销毁实例。

### Q: 内存使用过高怎么办？

A: 检查：
- `max_memory_messages` 配置
- 会话自动清理是否启用
- 是否有内存泄漏

### Q: 如何监控消息延迟？

A: 使用性能监控代码：

```python
import time
start = time.time()
await agent.query_text("测试消息")
latency = time.time() - start
print(f"消息延迟: {latency:.3f}s")
```

### Q: 批量写入参数如何调整？

A: 根据负载调整：
- 高负载：增加 `batch_size`（20-50），减少 `flush_interval`（0.5-1.0）
- 低负载：减少 `batch_size`（5-10），增加 `flush_interval`（2.0-5.0）

## 错误处理

### Q: 常见的错误类型有哪些？

A: 主要错误类型：
- `ConfigError`: 配置错误
- `ToolError`: 工具执行错误
- `SessionError`: 会话相关错误
- `AgentSystemError`: 系统级错误

### Q: 如何调试工具错误？

A: 启用调试日志：

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

在工具中添加日志：
```python
import logging
logger = logging.getLogger(__name__)

async def debug_tool(param: str):
    logger.info(f"开始处理: {param}")
    try:
        result = await process(param)
        logger.info(f"处理成功: {result}")
        return result
    except Exception as e:
        logger.error(f"处理失败: {e}", exc_info=True)
        raise
```

### Q: MCP 服务器启动失败怎么办？

A: 检查：
1. 配置文件语法
2. 工具代码是否有语法错误
3. 端口是否被占用
4. 依赖是否安装完整

### Q: 如何处理超时错误？

A: 配置合适的超时时间：

```yaml
advanced:
  env:
    CLAUDE_CODE_STREAM_CLOSE_TIMEOUT: "300000"  # 5分钟
    MCP_TIMEOUT: "120000"                       # 2分钟
    MCP_TOOL_TIMEOUT: "180000"                  # 3分钟
```

## 部署和运维

### Q: 如何在生产环境部署？

A: 推荐使用 Docker：

```yaml
# docker-compose.yml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  claude-agent:
    build: .
    depends_on:
      - redis
    environment:
      - REDIS_URL=redis://redis:6379
    volumes:
      - ./instances:/app/instances
```

### Q: 如何备份会话数据？

A: 会话数据存储在文件系统中，直接备份 `instances/` 目录：

```bash
# 创建备份
tar -czf instances_backup_$(date +%Y%m%d).tar.gz instances/

# 或使用 rsync
rsync -av instances/ backup/instances/
```

### Q: 如何清理过期会话？

A: 配置自动清理：

```yaml
session_recording:
  auto_cleanup: true
  retention_days: 30
```

或手动清理：
```python
from src.session.core.session_manager import SessionManager

manager = SessionManager("demo_agent", Path("instances/demo_agent"))
await manager.cleanup_expired_sessions(retention_days=30)
```

### Q: 如何监控系统健康状态？

A: 实现健康检查：

```python
async def health_check():
    checks = {
        "redis": await check_redis(),
        "disk_space": check_disk_space(),
        "active_sessions": count_active_sessions()
    }
    return checks
```

### Q: 如何升级到新版本？

A: 查看迁移指南：[docs/migration-guide.md](migration-guide.md)

主要步骤：
1. 备份现有数据
2. 更新代码和依赖
3. 运行迁移脚本（如需要）
4. 验证功能正常

### Q: 如何配置日志？

A: 在代码中配置：

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('claude_agent.log'),
        logging.StreamHandler()
    ]
)
```

或通过环境变量：
```bash
export LOG_LEVEL=INFO
export LOG_FILE=claude_agent.log
```

## 更多问题

如果您的问题不在此列表中，请：

1. 查看相关文档：
   - [配置指南](configuration.md)
   - [API 参考](api-reference.md)
   - [工具开发指南](tool-development.md)

2. 检查 GitHub Issues
3. 提交新的 Issue 或联系维护团队

## 常用命令速查

```bash
# 安装依赖
pip install -r requirements.txt

# 启动 Redis（Docker）
docker run -d -p 6379:6379 redis:7-alpine

# 查看会话列表
python -c "
from src.session.session_query import list_sessions
print(list_sessions('demo_agent'))
"

# 导出会话
python -c "
from src.session.session_query import export_session
print(export_session('demo_agent', 'session_id', 'markdown'))
"

# 测试工具
python instances/demo_agent/tools/your_tool.py
```