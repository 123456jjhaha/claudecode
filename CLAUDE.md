# Claude Agent System

基于 Claude Agent SDK (Python) 的可扩展智能体系统，使用 FastMCP + stdio 架构，提供完整的会话记录和实时消息功能。

> **重要提示**：本文档是系统的核心架构文档。如需了解各组件的详细实现和使用方法，请查看文末的[文档索引](#文档索引)中的对应文档。

## 核心特性

- 📝 **YAML 配置驱动** - 通过简单的 YAML 文件管理 Claude Agent 实例
- 🔧 **自动工具发现** - 自动扫描 `tools/` 目录，无需装饰器，直接写异步函数
- 🏗️ **FastMCP + stdio 架构** - 使用标准 MCP 协议和子进程通信，稳定可靠
- 🔄 **递归子实例** - 子实例作为工具，支持无限层级嵌套
- ⚡ **无状态设计** - 支持并发查询，线程安全
- 📊 **智能会话记录** - 自动记录所有对话，支持层级化存储和查询
- 🔁 **Resume 多轮对话** - 支持恢复之前的会话
- 🚀 **实时消息推送** - 基于 Redis Pub/Sub，延迟 < 100ms
- 🧩 **模块化架构** - 清晰的模块化设计，便于维护和扩展

## 核心设计理念

### 1. FastMCP + stdio 架构

**进程隔离**：MCP 服务器运行在独立子进程中，工具崩溃不影响主进程。使用 JSON-RPC over stdio 通信，符合 MCP 规范，提供更高的稳定性。

```
Claude SDK → stdio → MCP 服务器子进程 → 工具执行 → 结果返回
```

**工作流程**：
1. AgentSystem 启动时，ProcessManager 创建 FastMCP 服务器子进程
2. 通过 stdio 建立通信通道，使用 JSON-RPC 协议交换消息
3. 扫描 `tools/` 目录，将发现的异步函数注册为 MCP 工具
4. 将子实例也注册为特殊类型的工具（SubInstanceTool）
5. 所有工具调用都通过统一的 MCP 协议转发

**设计原则**：
- 隔离性：工具执行在独立的子进程中
- 稳定性：避免工具错误影响主进程
- 标准化：遵循 MCP 协议规范
- 可扩展性：易于添加新的工具类型

### 2. 简化的工具格式

**零样板代码**：无需装饰器，直接写异步函数即可成为工具。系统自动发现、注册和调用。

**工作流程**：
1. ToolLoader 在启动时扫描 `tools/` 目录下的所有 `.py` 文件
2. 注册到 FastMCP 服务器，等待调用

**设计原则**：
- 简洁性：最小化学习成本
- 自动化：减少手动配置
- 可发现性：自动扫描和注册
- 标准化：统一的工具接口

### 3. 无状态 Agent 设计

**核心理念**：Agent 不保存任何 session 信息，每个查询返回自己的 session_id，天然支持并发查询。

**工作流程**：
1. 每次 `query()` 调用都会创建新的会话上下文
2. 会话信息存储在 Session 对象中，与 Agent 解耦
3. 查询结果包含 session_id，用于后续的会话恢复
4. 支持通过 `resume_session_id` 继续之前的会话
5. 多个查询可以并发执行，互不干扰

**设计原则**：
- 无状态：简化并发处理
- 线程安全：避免锁机制
- 可扩展：支持水平扩展
- 独立性：每个查询独立

### 4. 实时消息系统

基于 Redis Pub/Sub 的实时消息推送架构，支持：
- 消息产生时立即推送（延迟 < 100ms）
- 异步批量写入，提升性能
- 双层存储（Redis + JSONL），确保可靠性
- 自动降级策略，Redis 不可用时使用内存模式

**工作流程**：
1. MessageBus 作为全局单例管理所有 Redis 连接
2. Session 记录消息时，同时发布到 Redis 和写入 JSONLWriter
3. Redis 消息立即推送到订阅者（实时性）
4. JSONLWriter 批量缓冲，定时或达到阈值时刷新到文件（持久化）
5. 如果 Redis 不可用，自动降级到纯内存收集模式

**设计原则**：
- 实时性：最小化消息延迟
- 可靠性：双层存储保证
- 高性能：批量异步写入
- 容错性：自动降级机制

### 5. 模块化会话系统

会话系统采用清晰的模块化设计，各模块职责分离：

- **core**：会话核心功能，管理会话生命周期
- **streaming**：实时消息流，处理消息分发
- **storage**：异步批量存储，优化 I/O 性能
- **query**：查询和树构建，支持复杂查询
- **utils**：工具函数，提供通用功能

**工作流程**：
1. SessionManager 创建会话时，初始化所有相关模块
2. core.Session 负责会话的基本操作（记录消息、生成统计）
3. streaming.MessageBus 处理实时消息分发（如果启用）
4. storage.JSONLWriter 管理异步批量写入
5. query 模块提供会话查询和树构建功能

**设计原则**：
- 单一职责：每个模块专注特定功能
- 松耦合：模块间依赖最小化
- 可扩展：易于添加新功能
- 可维护：代码结构清晰

### 6. 递归子实例系统

**核心理念**：子实例是完整的 AgentSystem，可以无限嵌套，实现任务的分层处理。

**工作流程**：
1. 父实例启动时，读取配置中的 `sub_claude_instances` 定义
2. SubInstanceAdapter 将子实例封装为工具，但不立即创建
3. 当 Claude 决定使用子实例时，才动态创建子实例（延迟实例化）
4. 子实例作为工具被调用，传递 `parent_session_id` 建立关联
5. 子实例完成后自动清理，释放资源
6. 父实例的会话记录中自动包含所有子会话的引用

**设计原则**：
- 递归性：支持无限层级嵌套
- 延迟性：按需创建，节省资源
- 独立性：子实例有完整的生命周期
- 可追踪性：自动维护父子关系

### 7. 配置驱动的实例管理

**核心理念**：每个实例都是独立的，通过配置文件定义其行为和特性。

**工作流程**：
1. AgentSystem 实例化时，ConfigManager 读取实例目录的配置文件
2. 配置文件定义了模型、系统提示词、工具权限、子实例等
3. 根据配置加载相应的工具和子实例
4. 环境变量可以覆盖配置文件中的设置
5. 支持配置验证，确保配置的正确性

**设计原则**：
- 声明式：通过配置文件定义行为
- 灵活性：支持多层级配置覆盖
- 验证性：自动验证配置的完整性
- 隔离性：每个实例独立配置

### 系统整体工作流程

#### 初始化阶段
1. **配置加载**：ConfigManager 读取并验证实例配置
2. **工具发现**：ToolLoader 扫描 `tools/` 目录，自动注册工具
3. **子实例注册**：将配置的子实例封装为 SubInstanceTool
4. **MCP 服务器启动**：ProcessManager 创建 FastMCP 服务器子进程
5. **消息总线初始化**：如果启用，创建全局 MessageBus 并连接 Redis

#### 查询执行阶段
1. **查询接收**：AgentSystem 接收查询文本和可选参数
2. **会话创建**：SessionManager 创建新的会话或恢复已有会话
3. **上下文准备**：加载系统提示词、配置和工具列表
4. **Claude 调用**：通过 SDK 向 Claude 发送请求
5. **工具执行**：Claude 决定使用工具时，通过 MCP 协议调用
   - 本地工具：直接在子进程中执行异步函数
   - 子实例工具：动态创建子实例并执行查询
6. **消息记录**：每个消息都会记录到会话中
   - 同时发布到 Redis（如果启用）
   - 写入 JSONLWriter 缓冲区
7. **结果返回**：将 Claude 的响应和 session_id 返回给调用者

#### 会话管理阶段
1. **消息收集**：会话过程中持续收集所有消息
2. **实时推送**：如果启用 MessageBus，实时推送消息
3. **批量写入**：JSONLWriter 定期刷新消息到文件
4. **统计生成**：会话结束时生成详细的统计信息
5. **关系追踪**：自动记录子实例调用的会话关系

#### 清理阶段
1. **资源释放**：调用 cleanup() 释放所有资源
2. **进程终止**：停止 MCP 服务器子进程
3. **连接关闭**：关闭 Redis 连接（如果启用）
4. **缓冲区刷新**：强制刷新所有未写入的消息

## 系统组件

### AgentSystem（主控制器）
- 负责协调各个组件
- 管理 Agent 实例的生命周期
- 提供统一的查询接口
- 处理配置和初始化

### ConfigManager（配置管理器）
- 统一管理所有配置
- 支持配置验证和解析
- 处理环境变量覆盖
- 提供配置访问接口

### MCP Server 模块
- **ProcessManager**：MCP 服务器进程管理器，负责启动、管理和关闭 MCP 服务器子进程
- **MCPServer**：基于 FastMCP 的服务器实现，处理工具注册和调用
- **ToolLoader**：自动扫描和加载 `tools/` 目录下的异步函数工具

### ToolManager（工具管理器）
- 集成 MCP 服务器提供的工具接口
- 管理工具权限控制
- 处理工具调用请求
- 协调本地工具和子实例工具

### SubInstanceAdapter（子实例适配器）
- 将子实例封装为工具
- 管理子实例的创建和销毁
- 处理父子会话关系
- 实现延迟实例化

### SessionManager（会话管理器）
- 创建和管理会话实例
- 处理会话持久化
- 管理会话生命周期
- 支持会话查询和恢复

### MessageBus（消息总线）
- 全局单例，管理 Redis 连接
- 处理消息发布和订阅
- 支持多频道消息分发
- 提供连接池管理

### JSONLWriter（异步写入器）
- 批量缓冲消息写入
- 定时刷新机制
- 支持紧急备份
- 优化 I/O 性能

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
    └── sessions/             # 会话记录目录（自动创建）
        └── {session_id}/     # 每个会话的独立目录
    |———agent.md 实例的提示词文档
```

**目录说明**：
- **config.yaml**：定义实例的基本配置、模型、工具权限等
- **.claude/**：存放 Claude 相关的配置文件
- **tools/**：存放该实例专用的自定义工具
- **sessions/**：自动创建，存储该实例的所有会话记录

### Session ID vs Claude ID

**Session ID（会话ID）**：
- 格式：`{timestamp}_{counter}_{short_hash}`
- 示例：`20251216T103000_1234_abcd1234`
- 用途：标识一次完整的对话会话
- 特点：
  - 由系统生成，确保唯一性
  - 包含时间戳，支持按时间排序
  - 用于会话恢复和查询
  - 存储在文件系统中，持久化保存

**Claude ID**：
- 格式：由 Claude SDK 内部管理的唯一标识符
- 用途：标识与 Claude API 的单次对话会话
- 特点：
  - 仅在单次查询生命周期内有效
  - 由 SDK 管理，对用户透明
  - 用于 SDK 内部的状态管理
  - 不持久化，查询结束后失效


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

### 启用实时消息（可选）

```python
import asyncio
from src import AgentSystem
from src.session.streaming import MessageBus

async def main():
    # 创建全局 MessageBus（单例）
    message_bus = MessageBus.from_config()
    await message_bus.connect()

    try:
        # 创建 Agent 实例（共享同一个 MessageBus）
        agent = AgentSystem("demo_agent", message_bus=message_bus)
        await agent.initialize()

        # 执行查询（消息会自动推送到 Redis）
        result = await agent.query_text("分析这个项目")
        print(f"结果: {result.result}")
        print(f"会话 ID: {result.session_id}")

        agent.cleanup()
    finally:
        await message_bus.close()

asyncio.run(main())
```

## 项目结构

```
claude_agent_system/
├── src/                              # 核心框架
│   ├── session/                      # 会话记录模块
│   │   ├── core/                    # 会话核心
│   │   │   ├── session.py          # Session 类
│   │   │   └── session_manager.py  # SessionManager 类
│   │   ├── streaming/               # 实时消息流
│   │   │   ├── message_bus.py      # Redis 消息总线
│   │   │   └── stream_manager.py   # 查询流管理器
│   │   ├── storage/                 # 存储模块
│   │   │   └── jsonl_writer.py     # 异步批量写入器
│   │   ├── query/                   # 查询模块
│   │   │   ├── session_query.py   # 查询 API
│   │   │   └── tree_builder.py     # 会话树构建器
│   │   └── utils/                   # 工具模块
│   │       ├── session_utils.py    # 工具函数
│   │       └── session_serializer.py # 消息序列化器
│   ├── mcp_server/                  # MCP 服务器模块
│   │   ├── process_manager.py      # 进程管理器
│   │   ├── server.py               # FastMCP 服务器
│   │   └── tool_loader.py          # 工具加载器
│   ├── agent_system.py             # 系统主类
│   ├── config_manager.py           # 配置管理
│   ├── tool_manager.py             # 工具管理
│   ├── sub_instance_adapter.py     # 子实例适配器
│   ├── error_handling.py           # 错误处理
│   ├── logging_config.py           # 日志配置
│   └── __init__.py
│
├── instances/                       # 实例目录
│   ├── demo_agent/                  # 演示实例
│   │   ├── config.yaml             # 实例配置
│   │   ├── .claude/
│   │   │   ├── agent.md           # 系统提示词
│   │   │   └── settings.json      # Claude 设置
│   │   ├── tools/                  # 自定义工具
│   │   └── sessions/               # 会话记录（自动创建）
│   ├── file_analyzer_agent/        # 文件分析实例
│   └── syntax_checker_agent/       # 语法检查实例
│
├── docs/                           # 文档目录
│   ├── configuration.md           # 配置指南
│   ├── session-system.md          # 会话系统详解
│   ├── tool-development.md        # 工具开发指南
│   ├── sub-instances.md           # 子实例系统
│   ├── real-time-system.md        # 实时消息系统
│   ├── api-reference.md           # API 参考
│   ├── faq.md                    # 常见问题
│   └── migration-guide.md        # 迁移指南
│
├── streaming.yaml                 # 实时消息配置（可选）
├── requirements.txt
└── CLAUDE.md                      # 本文档
```

## 功能概览

### 自定义工具
- 在 `tools/` 目录下编写异步函数
- 自动发现和注册，无需手动配置
- 支持类型注解和文档字符串
- 详细指南：[工具开发指南](docs/tool-development.md)

### 子实例系统
- 支持无限层级的子实例嵌套
- 每个子实例是完整的 AgentSystem
- 自动追踪父子会话关系
- 详细指南：[子实例系统](docs/sub-instances.md)

### 配置管理
- YAML 配置文件驱动
- 支持环境变量覆盖
- 灵活的权限控制
- 详细指南：[配置指南](docs/configuration.md)

### 会话系统
- 完整的会话记录和管理
- 支持会话恢复和查询
- 实时消息推送
- 详细指南：[会话系统详解](docs/session-system.md)

## 文档索引

- [配置指南](docs/configuration.md) - 完整的配置选项说明
- [会话系统详解](docs/session-system.md) - 会话记录和管理系统
- [工具开发指南](docs/tool-development.md) - 创建自定义工具
- [子实例系统](docs/sub-instances.md) - 子实例的使用和配置
- [实时消息系统](docs/real-time-system.md) - Redis Pub/Sub 实时推送
- [API 参考](docs/api-reference.md) - 完整的 API 文档
- [常见问题](docs/faq.md) - FAQ 和故障排除
- [迁移指南](docs/migration-guide.md) - 版本升级指南

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
- **代码变更 → 文档更新**：任何代码结构变更都必须同步更新本文档
- **先文档后实现**：新功能开发必须先更新相关文档，再编写代码
- **版本一致性**：文档版本必须与代码版本保持一致
- **审查流程**：文档变更必须经过代码审查流程

#### 2. 文档内容约束
- **准确性**：所有描述必须与实际实现完全一致
- **完整性**：新增组件必须包含完整的架构描述和使用说明
- **可读性**：使用清晰的语言和适当的图表说明复杂概念
- **示例代码**：所有公共 API 都必须提供使用示例

#### 3. 文档索引维护
- **链接有效性**：确保所有文档链接指向实际存在的文件
- **内容覆盖**：每个系统组件都必须有对应的详细文档
- **更新及时性**：功能变更后必须更新相关文档

### 查看文档指南

#### 1. 本文档的定位
- **CLAUDE.md**：系统核心架构和设计理念的总览文档
- **重点内容**：系统整体设计、核心概念、组件关系、架构原则
- **适用场景**：了解系统整体架构、新开发者入门、架构决策参考

#### 2. 详细文档查找
如需了解具体组件的实现细节，请查看[文档索引](#文档索引)中的对应文档。


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

