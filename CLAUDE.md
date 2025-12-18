# Claude Agent System

基于 Claude Agent SDK (Python) 的可扩展智能体系统，使用 FastMCP + stdio 架构，提供完整的会话记录和实时消息功能。

> **文档定位**：本文档是系统的**核心架构文档**，只描述整体设计理念和关键概念。具体模块的实现细节请参考[文档索引](#文档索引)中的对应文档。

---

## 核心特性

- 📝 **YAML 配置驱动** - 通过简单的 YAML 文件管理 Claude Agent 实例
- 🔧 **自动工具发现** - 自动扫描 `tools/` 目录，无需装饰器，直接写异步函数
- 🏗️ **FastMCP + stdio 架构** - 使用标准 MCP 协议和子进程通信，稳定可靠
- 🔄 **递归子实例** - 子实例作为工具，支持无限层级嵌套
- ✨ **自动父子关联** - parent_session_id 自动传递，对 Claude 完全透明
- 📡 **子实例实时追踪** - 子实例启动时即刻通知，支持实时消息订阅
- ⚡ **无状态设计** - 支持并发查询，线程安全
- 📊 **智能会话记录** - 自动记录所有对话，支持层级化存储和查询
- 🔁 **Resume 多轮对话** - 支持恢复之前的会话
- 🚀 **实时消息推送** - 基于 Redis Pub/Sub，延迟 < 100ms
- 🧩 **统一查询架构** - 两大核心类：会话管理 + 会话查询，职责清晰

---

## 核心设计理念

### 1. FastMCP + stdio 架构

**进程隔离**：MCP 服务器运行在独立子进程中，工具崩溃不影响主进程。使用 JSON-RPC over stdio 通信，符合 MCP 规范。

```
Claude SDK → stdio → MCP 服务器子进程 → 工具执行 → 结果返回
```

**设计原则**：
- 隔离性：工具执行在独立的子进程中
- 稳定性：避免工具错误影响主进程
- 标准化：遵循 MCP 协议规范
- 可扩展性：易于添加新的工具类型

### 2. 简化的工具格式

**零样板代码**：无需装饰器，直接写异步函数即可成为工具。系统自动发现、注册和调用。

```python
# tools/calculator.py
async def add(a: int, b: int) -> int:
    """加法工具"""
    return a + b
```

### 3. 统一会话架构（新设计）

**核心理念**：会话系统采用两大核心类设计，职责清晰分离。

#### **🏛️ 会话管理类 (SessionManager + Session)**
```python
# SessionManager - 会话工厂和管理器
class SessionManager:
    - create_session()     # 创建新会话
    - get_session()        # 获取已有会话
    - list_sessions()      # 列出会话
    - cleanup_old_sessions()  # 清理过期会话

# Session - 会话数据模型
class Session:
    - record_message()     # 记录消息
    - finalize()           # 完成会话
    - get_messages()       # 获取消息
    - get_metadata()       # 获取元数据
```

#### **🔍 会话查询类 (SessionQuery)**
```python
# SessionQuery - 统一查询+订阅服务
class SessionQuery:
    # 基础查询
    - get_session_details()      # 获取完整会话详情
    - get_session_messages()     # 获取会话消息
    - list_sessions()            # 代理到 SessionManager

    # 高级查询
    - search_sessions()          # 搜索会话
    - get_statistics_summary()   # 统计分析
    - export_session()           # 导出功能

    # 实时订阅
    - subscribe()               # 订阅会话消息
    - 自动追踪子实例           # 🌟 核心特性

    # 会话树构建
    - build_session_tree()      # 递归构建会话关系
    - flatten_tree()           # 展平树结构
```

**设计原则**：
- 职责分离：管理 vs 查询
- 接口统一：单一入口访问所有会话功能
- 向后兼容：保持现有 API 不变
- 扩展友好：新功能易于添加

### 4. 无状态 Agent 设计

**核心理念**：Agent 不保存任何 session 信息，每个查询返回自己的 session_id，天然支持并发查询。

**设计原则**：
- 无状态：简化并发处理
- 线程安全：避免锁机制
- 可扩展：支持水平扩展
- 独立性：每个查询独立

### 5. 实时消息系统

基于 Redis Pub/Sub 的实时消息推送架构：
- 消息产生时立即推送（延迟 < 100ms）
- 双层存储（Redis + JSONL），确保可靠性
- 自动降级策略，Redis 不可用时使用内存模式
详细说明：[会话系统完整指南](docs/session-guide.md)

### 6. 递归子实例系统

**核心理念**：子实例是完整的 AgentSystem，可以无限嵌套，实现任务的分层处理。

**关键特性**：
- ✨ **子实例启动通知**：子实例创建 session 后，立即向父 session 频道发布启动通知
- ✨ **实时追踪**：SessionQuery 自动监听通知，实时获取子 session_id 并订阅子实例消息流
- ✨ **自动订阅**：订阅父会话后，所有子实例消息自动推送，无需手动配置

**设计原则**：
- 递归性：支持无限层级嵌套
- 延迟性：按需创建，节省资源
- 实时性：子实例启动时立即通知

详细说明：[子实例系统](docs/sub-instances.md)

### 7. 配置驱动的实例管理

**核心理念**：每个实例都是独立的，通过配置文件定义其行为和特性。

**设计原则**：
- 声明式：通过配置文件定义行为
- 灵活性：支持多层级配置覆盖
- 验证性：自动验证配置的完整性
- 隔离性：每个实例独立配置

详细说明：[配置指南](docs/configuration.md)

---

## 关键概念

### instances 目录结构

`instances/` 目录是系统的核心，存储所有 claude 实例的配置和数据：

```
instances/
└── {instance_name}/          # 实例目录
    ├── config.yaml          # 实例配置文件（必需）
    ├── .claude/              # Claude 相关配置
    │   ├── commands/
    │   ├── agents/
    │   ├── skills/
    │   ├── .mcp.json        # 外部 MCP 服务器配置（可选）
    │   └── settings.json    # Claude Code 设置（可选）
    ├── tools/                # 自定义工具目录（可选）
    │   └── *.py             # 工具文件
    ├── agent.md             # 实例的提示词文档
    └── sessions/             # 会话记录目录（自动创建）
        └── {session_id}/     # 每个会话的独立目录
```

### Session ID vs Claude ID

**Session ID（会话ID）**：
- 格式：`{timestamp}_{counter}_{short_hash}`
- 示例：`20251217T103000_1234_abcd1234`
- 用途：标识一次完整的对话会话
- 特点：系统生成，包含时间戳，支持会话恢复和查询，持久化保存

**Claude ID**：
- 格式：由 Claude SDK 内部管理的唯一标识符
- 用途：标识与 Claude API 的单次对话会话
- 特点：仅在单次查询生命周期内有效，SDK 内部管理，查询结束后失效

---

## 项目结构

```
claude_agent_system/
├── src/                              # 核心框架
│   ├── session/                      # 统一会话系统
│   │   ├── core/                    # 🏛️ 会话管理类
│   │   │   ├── session.py          # Session 数据模型
│   │   │   └── session_manager.py  # SessionManager 生命周期管理
│   │   ├── query/                   # 🔍 会话查询类
│   │   │   └── session_query.py    # SessionQuery 统一查询+订阅
│   │   ├── streaming/               # 🌊 实时消息流
│   │   │   ├── message_bus.py      # Redis 消息总线
│   │   │   └── stream_manager.py   # 查询流管理
│   │   ├── storage/                 # 💾 存储组件
│   │   │   └── jsonl_writer.py     # 异步批量写入
│   │   └── utils/                   # 🛠️ 工具函数
│   │       ├── session_utils.py    # 基础工具
│   │       ├── query_helpers.py    # 查询辅助函数
│   │       ├── session_context.py  # 上下文管理
│   │       └── instance_utils.py   # 实例工具
│   ├── mcp_server/                  # MCP 服务器模块
│   ├── agent_system.py             # 系统主类
│   ├── config_manager.py           # 配置管理
│   ├── tool_manager.py             # 工具管理
│   ├── sub_instance_adapter.py     # 子实例适配器
│   └── ...
│
├── instances/                       # 实例目录
│   ├── demo_agent/                  # 演示实例
│   ├── file_analyzer_agent/        # 文件分析实例
│   └── ...
│
├── docs/                           # 文档目录
│   ├── session-guide.md           # ⭐ 会话系统完整指南
│   ├── session-subscriber-guide.md # SessionQuery 详细使用指南
│   ├── configuration.md           # 配置指南
│   ├── tool-development.md        # 工具开发指南
│   ├── sub-instances.md           # 子实例系统
│   └── ...
│
├── streaming.yaml                 # 实时消息配置（可选）
├── requirements.txt
└── CLAUDE.md                      # 本文档
```

---

## 快速开始

### 基础使用

```python
import asyncio
from src import AgentSystem

async def main():
    # 创建 Agent
    agent = AgentSystem("demo_agent")
    await agent.initialize()

    # 执行查询
    result = await agent.query_text("计算 123 + 456")
    print(f"结果: {result.result}")
    print(f"会话 ID: {result.session_id}")

    # Resume 对话
    result2 = await agent.query_text(
        "再算一下 789",
        resume_session_id=result.session_id
    )

    agent.cleanup()

asyncio.run(main())
```

### 启用实时消息（新架构）

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

### 会话查询示例（新架构）

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

更多示例请参考：[会话系统完整指南](docs/session-guide.md)

---

## 文档索引

### 核心文档

- [SessionQuery 完整使用指南](docs/session-query-guide.md) ⭐ - 统一会话查询与订阅服务
- [会话系统完整指南](docs/session-guide.md) - 会话管理和查询完整指南
- [SessionQuery 迁移指南](docs/session-migration-guide) 🔄 - 从旧架构平滑迁移
- [配置指南](docs/configuration.md) - 完整的配置选项说明
- [工具开发指南](docs/tool-development.md) - 创建自定义工具
- [子实例系统](docs/sub-instances.md) - 子实例的使用和配置

### 参考文档
- [API 参考](docs/api-reference.md) - 完整的 API 文档
- [常见问题](docs/faq.md) - FAQ 和故障排除
- [迁移指南](docs/migration-guide.md) - 版本升级指南

---

## 开发和维护约束

### 代码开发约束

#### 1. 模块化设计原则
- **单一职责**：每个模块和类必须只负责一个明确的功能领域
- **松耦合**：模块间依赖最小化，优先使用接口和抽象
- **高内聚**：相关功能应该组织在同一个模块内
- **可测试性**：所有核心组件都必须支持单元测试

#### 2. 文件组织标准
- **目录结构**：严格遵循项目结构规范，不得随意创建新目录
- **命名规范**：
  - 文件名使用小写字母和下划线（snake_case）
  - 类名使用驼峰命名（PascalCase）
  - 函数和变量使用小写字母和下划线（snake_case）
- **导入顺序**：标准库 → 第三方库 → 本地模块
- **文档字符串**：所有公共函数和类必须有详细的文档字符串

#### 3. 架构约束
- **依赖方向**：高层模块不依赖低层模块，都依赖抽象
- **配置驱动**：所有行为必须通过配置文件控制，禁止硬编码
- **错误处理**：使用统一的异常处理机制，定义明确的异常类型
- **日志规范**：使用结构化日志，包含足够的上下文信息

#### 4. 解耦要求
- **接口隔离**：使用抽象接口隔离具体实现
- **依赖注入**：通过构造函数或工厂模式注入依赖
- **事件驱动**：使用事件总线处理组件间通信
- **配置外部化**：所有配置参数必须外部化，支持环境变量覆盖

### 文档维护约束

#### 1. 文档同步原则
- **代码变更 → 文档更新**：任何代码结构变更都必须同步更新相关文档
- **先文档后实现**：新功能开发必须先更新相关文档，再编写代码
- **版本一致性**：文档版本必须与代码版本保持一致
- **审查流程**：文档变更必须经过代码审查流程

#### 2. 文档内容约束
- **准确性**：所有描述必须与实际实现完全一致
- **完整性**：新增组件必须包含完整的架构描述和使用说明
- **可读性**：使用清晰的语言和适当的图表说明复杂概念
- **示例代码**：所有公共 API 都必须提供使用示例

#### 3. 文档分层
- **CLAUDE.md**：系统核心架构和设计理念（本文档）
- **功能文档**：各模块的详细实现和使用方法（docs/ 目录）
- **API 文档**：完整的 API 参考（docs/api-reference.md）

### 违反约束的后果

#### 1. 代码质量影响
- 违反模块化原则将导致代码难以维护和测试
- 不遵循文件组织标准会影响开发效率和代码可读性
- 缺乏解耦设计会限制系统的扩展性和灵活性

#### 2. 项目风险
- 文档不同步会增加开发成本和错误率
- 架构约束的违反会降低系统的稳定性和性能
- 不遵循开发约束会导致技术债务积累

#### 3. 合规要求
- 所有代码提交必须通过自动化检查（代码格式、结构规范）
- 文档变更必须包含在 Pull Request 中
