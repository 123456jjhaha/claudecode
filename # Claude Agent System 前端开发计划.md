# Claude Agent System 前端开发计划

## 项目概述

为 Claude Agent System 开发一个功能完整的 Web 前端界面，重点实现第一阶段：实例选择、实时对话、树状消息展示和历史会话管理。

**技术栈：**
- 前端：React 18 + TypeScript + Ant Design
- 后端：FastAPI + WebSocket
- 通信：WebSocket（实时）+ REST API（查询）
- 状态管理：React Context + Hooks
- 样式：Ant Design + CSS Modules

---

## 整体架构设计

### 1. 系统架构图

```
┌─────────────────────────────────────────────────┐
│              前端 (React + TypeScript)            │
│  ┌──────────────┐  ┌──────────────┐             │
│  │ InstancePanel│  │ SessionPanel │             │
│  │   (实例列表)  │  │  (历史会话)   │             │
│  └──────────────┘  └──────────────┘             │
│  ┌─────────────────────────────────────────┐    │
│  │      ChatInterface (对话界面)             │    │
│  │  ┌─────────────────────────────────┐    │    │
│  │  │  MessageTree (嵌套卡片式消息树)   │    │    │
│  │  │  - 父消息                         │    │    │
│  │  │  └─ 子实例消息 (可折叠)           │    │    │
│  │  └─────────────────────────────────┘    │    │
│  └─────────────────────────────────────────┘    │
└─────────────────────────────────────────────────┘
                       ↕ WebSocket + REST
┌─────────────────────────────────────────────────┐
│          后端 (FastAPI WebSocket 网关)           │
│  ┌──────────────┐  ┌──────────────┐             │
│  │  REST APIs   │  │  WebSocket   │             │
│  │ - 实例列表    │  │ - 实时消息流  │             │
│  │ - 会话查询    │  │ - 子实例追踪  │             │
│  │ - 历史消息    │  │ - 自动订阅    │             │
│  └──────────────┘  └──────────────┘             │
└─────────────────────────────────────────────────┘
                       ↕
┌─────────────────────────────────────────────────┐
│        现有 Python 后端 (AgentSystem)            │
│  ┌──────────────┐  ┌──────────────┐             │
│  │ AgentSystem  │  │ SessionQuery │             │
│  │ MessageBus   │  │   (Redis)    │             │
│  └──────────────┘  └──────────────┘             │
└─────────────────────────────────────────────────┘
```

---

## 详细功能设计

### 阶段一：核心功能实现

#### 功能 1：实例选择和管理
**位置：**左侧面板（InstancePanel）

**功能点：**
- 展示所有可用实例列表（从 `instances/` 目录扫描）
- 显示实例基本信息：名称、描述、工具数量
- 点击实例切换当前活动实例
- 显示当前选中状态

**数据来源：**
- API: `GET /api/instances` - 列出所有实例
- 数据格式：
```typescript
interface Instance {
  name: string;
  description: string | null;
  tools_count: number;
  sub_instances_count: number;
  config_path: string;
}
```

---

#### 功能 2：新对话创建
**位置：**主界面顶部（ChatInterface Header）

**功能点：**
- 输入框输入对话内容
- 发送按钮触发新对话
- 自动切换到实时流模式
- 显示"正在思考..."加载状态

**API 调用：**
- WebSocket: 连接到 `/ws/chat/{instance_name}`
- 发送消息：
```typescript
{
  "action": "start_query",
  "prompt": "用户输入的内容",
  "resume_session_id": null  // 新对话时为 null
}
```

---

#### 功能 3：实时消息流展示（核心功能）
**位置：**主对话区域（MessageTree Component）

**设计方案：嵌套卡片式树状展示**

##### 3.1 消息类型和展示样式

**UserMessage（用户消息）**
```
┌─────────────────────────────────────┐
│ 👤 User                              │
│ 计算 123 + 456 并分析结果           │
│                         10:30:45    │
└─────────────────────────────────────┘
```

**AssistantMessage（助手消息）**
```
┌─────────────────────────────────────┐
│ 🤖 Assistant                         │
│ 我来帮你计算...                     │
│                                     │
│ ToolUse: calculator.add              │
│   input: {a: 123, b: 456}           │
│                         10:30:46    │
└─────────────────────────────────────┘
```

**ToolResultBlock（工具结果）**
```
┌─────────────────────────────────────┐
│ 🔧 Tool Result: calculator.add      │
│ ✅ Success                           │
│ Result: 579                         │
│                         10:30:47    │
└─────────────────────────────────────┘
```

**子实例消息（嵌套卡片）**
```
┌─────────────────────────────────────┐
│ 🤖 Assistant                         │
│ 让我调用文件分析器分析这个文件...     │
│                                     │
│ ToolUse: sub_claude_file_analyzer    │
│   input: {file: "test.py"}          │
│                                     │
│ ┌─────────────────────────────────┐ │ ◀─ 子实例区域（可折叠）
│ │ 📦 Sub-Instance: file_analyzer  │ │
│ │ Session: 20251218...            │ │
│ │ ┌─ 展开 ▼ ─────────────────────┐│ │
│ │ │ 👤 [子] User                  ││ │
│ │ │ 分析文件 test.py               ││ │
│ │ │                               ││ │
│ │ │ 🤖 [子] Assistant             ││ │
│ │ │ 这是一个 Python 文件...       ││ │
│ │ │                               ││ │
│ │ │ 🔧 [子] Tool: read_file       ││ │
│ │ │ ✅ Success                    ││ │
│ │ └───────────────────────────────┘│ │
│ └─────────────────────────────────┘ │
│                                     │
│ 🔧 Tool Result: sub_claude_...      │
│ ✅ Success                           │
│ 分析完成，发现 3 个函数定义          │
└─────────────────────────────────────┘
```

##### 3.2 树状结构数据模型（简化版）

```typescript
// 消息节点 - 简化结构
// 📖 对应后端消息格式：参考 src/session/utils/session_serializer.py - serialize_message 方法
interface MessageNode {
  seq: number;                                    // 消息序号
  timestamp: string;                              // 时间戳
  message_type: 'UserMessage' | 'AssistantMessage' | 'ToolResultBlock' | 'ResultMessage';
  data: {
    role?: string;                                // user/assistant
    content?: string | any[];                     // 消息内容
    model?: string;                               // 模型名称
    tool_use_id?: string;                         // 工具使用ID
    // 📖 完整字段：参考 src/session/core/session.py - Message 类的属性
  };
  // 移除了复杂的子实例相关字段，因为通过消息流自动关联
}

// 子会话信息 - 大幅简化
// 📖 对应后端会话结构：参考 src/session/core/session.py - Session 类
interface ChildSession {
  session_id: string;                             // 子会话唯一标识
  instance_name: string;                          // 子实例名称
  messages: MessageNode[];                        // 子会话消息列表
  collapsed: boolean;                             // UI折叠状态
  // 移除了 parent_tool_use_id，因为通过消息时间顺序自动关联
}

// 对话树 - 清晰的分离
// 📖 对应后端查询结果：参考 src/session/query/session_query.py - get_session_details 方法
interface ConversationTree {
  session_id: string;                             // 父会话ID
  instance_name: string;                          // 父实例名称
  messages: MessageNode[];                        // 父会话消息
  child_sessions: Map<string, ChildSession>;      // 子会话映射：child_session_id -> ChildSession
}

// 使用示例
const conversationTree: ConversationTree = {
  session_id: "20241218T103000_1234_parent5678",
  instance_name: "demo_agent",
  messages: [
    {
      seq: 0,
      timestamp: "2024-12-18T10:30:00Z",
      message_type: "UserMessage",
      data: { role: "user", content: "请分析这个文件" }
    },
    {
      seq: 1,
      timestamp: "2024-12-18T10:30:01Z",
      message_type: "AssistantMessage",
      data: { role: "assistant", content: "我来调用文件分析器..." }
    }
  ],
  child_sessions: new Map([
    ["20241218T103100_1234_child5678", {
      session_id: "20241218T103100_1234_child5678",
      instance_name: "file_analyzer",
      messages: [],
      collapsed: false
    }]
  ])
};

// 📖 SessionID 格式说明
// 格式：{timestamp}_{counter}_{hash}
// 示例：20241218T103000_1234_abcd1234
// 📖 生成逻辑：参考 src/session/utils/session_utils.py - generate_session_id 方法
```

##### 3.3 实时消息接收和树构建逻辑

**WebSocket 消息处理流程：**

```typescript
// WebSocket 消息监听
ws.onmessage = (event) => {
  const message = JSON.parse(event.data);

  switch (message.type) {
    case 'parent_message':
      // 父会话消息
      handleParentMessage(message.data);
      break;

    case 'child_started':
      // 子实例启动通知
      handleChildStarted(message.child_session_id, message.instance_name);
      break;

    case 'child_message':
      // 子实例消息
      handleChildMessage(
        message.child_session_id,
        message.instance_name,
        message.message
      );
      break;

    case 'query_complete':
      // 查询完成
      handleQueryComplete(message.result);
      break;
  }
};

// 处理父消息
function handleParentMessage(msg: any) {
  // 1. 添加到父消息列表
  const messageNode = createMessageNode(msg);
  addMessageToTree(conversationTree, messageNode);

  // 2. 检测是否是子实例工具调用
  if (isSubInstanceToolUse(msg)) {
    const toolUseId = extractToolUseId(msg);
    // 标记这个位置，等待子实例启动通知
    markPendingSubInstance(toolUseId);
  }

  // 3. 更新 UI
  updateConversationDisplay();
}

// 处理子实例启动
function handleChildStarted(childSessionId: string, instanceName: string) {
  // 1. 找到对应的 ToolUse 位置
  const parentToolUse = findPendingSubInstance(childSessionId);

  // 2. 创建子会话容器
  const childSession: ChildSessionInfo = {
    session_id: childSessionId,
    instance_name: instanceName,
    parent_tool_use_id: parentToolUse.id,
    messages: [],
    collapsed: false  // 默认展开
  };

  // 3. 插入到树结构中
  insertChildSession(conversationTree, parentToolUse.id, childSession);

  // 4. 更新 UI（显示子实例卡片）
  updateConversationDisplay();
}

// 处理子实例消息
function handleChildMessage(
  childSessionId: string,
  instanceName: string,
  msg: any
) {
  // 1. 找到对应的子会话
  const childSession = conversationTree.child_sessions.get(childSessionId);
  if (!childSession) return;

  // 2. 添加消息到子会话
  const messageNode = createMessageNode(msg);
  messageNode.is_sub_instance_message = true;
  childSession.messages.push(messageNode);

  // 3. 更新 UI（如果未折叠则显示）
  if (!childSession.collapsed) {
    updateConversationDisplay();
  }
}
```

##### 3.4 关键组件实现

**MessageTree 组件：**
```typescript
interface MessageTreeProps {
  conversationTree: ConversationTree;
  onToggleChild: (sessionId: string) => void;
}

const MessageTree: React.FC<MessageTreeProps> = ({ conversationTree, onToggleChild }) => {
  return (
    <div className="message-tree">
      {conversationTree.messages.map((msg, idx) => (
        <MessageCard
          key={msg.seq}
          message={msg}
          childSessions={getChildSessionsForMessage(msg, conversationTree)}
          onToggleChild={onToggleChild}
        />
      ))}
    </div>
  );
};
```

**MessageCard 组件：**
```typescript
interface MessageCardProps {
  message: MessageNode;
  childSessions?: ChildSessionInfo[];
  onToggleChild: (sessionId: string) => void;
  depth?: number;  // 嵌套深度，用于缩进
}

const MessageCard: React.FC<MessageCardProps> = ({
  message,
  childSessions,
  onToggleChild,
  depth = 0
}) => {
  const cardStyle = {
    marginLeft: `${depth * 24}px`,  // 根据深度缩进
  };

  return (
    <Card className="message-card" style={cardStyle}>
      {/* 消息头部：类型图标 + 角色 */}
      <MessageHeader message={message} />

      {/* 消息内容 */}
      <MessageContent message={message} />

      {/* 子实例区域 */}
      {childSessions && childSessions.length > 0 && (
        <div className="child-sessions">
          {childSessions.map(child => (
            <ChildSessionCard
              key={child.session_id}
              childSession={child}
              onToggle={() => onToggleChild(child.session_id)}
              depth={depth + 1}
            />
          ))}
        </div>
      )}

      {/* 时间戳 */}
      <MessageFooter message={message} />
    </Card>
  );
};
```

**ChildSessionCard 组件：**
```typescript
const ChildSessionCard: React.FC<{
  childSession: ChildSessionInfo;
  onToggle: () => void;
  depth: number;
}> = ({ childSession, onToggle, depth }) => {
  return (
    <div className="child-session-container">
      {/* 子实例头部：可折叠 */}
      <Card
        className="child-session-header"
        onClick={onToggle}
        style={{ cursor: 'pointer' }}
      >
        <Space>
          <Tag color="blue">📦 Sub-Instance</Tag>
          <Text strong>{childSession.instance_name}</Text>
          <Text type="secondary" style={{ fontSize: '12px' }}>
            {childSession.session_id.slice(0, 20)}...
          </Text>
          {childSession.collapsed ? <DownOutlined /> : <UpOutlined />}
        </Space>
      </Card>

      {/* 子实例消息（可折叠） */}
      {!childSession.collapsed && (
        <div className="child-session-messages">
          {childSession.messages.map(msg => (
            <MessageCard
              key={msg.seq}
              message={msg}
              depth={depth}
            />
          ))}
        </div>
      )}
    </div>
  );
};
```

---

#### 功能 4：历史会话列表
**位置：**右侧面板（SessionPanel）

**功能点：**
- 列出当前实例的所有历史会话
- 显示：会话 ID（截断）、开始时间、状态、初始提示词（截断）
- 支持筛选：按状态（运行中/已完成/失败）
- 支持搜索：按提示词内容搜索
- 分页显示（每页 20 条）
- 点击会话加载详情

**API：**
- `GET /api/sessions?instance={name}&status={status}&limit=20&offset=0`
- `GET /api/sessions/search?query={keyword}&field=initial_prompt`

**数据格式：**
```typescript
interface SessionSummary {
  session_id: string;
  start_time: string;
  end_time: string | null;
  status: 'running' | 'completed' | 'failed';
  initial_prompt: string;  // 截断到 100 字符
  num_messages: number;
  num_tool_calls: number;
  has_subsessions: boolean;
}
```

---

#### 功能 5：会话详情查看
**位置：**点击历史会话后，在主对话区域展示

**功能点：**
- 加载完整的会话消息
- 使用相同的 MessageTree 组件展示
- 支持展开/折叠子实例
- 显示会话统计信息：
  - 总耗时、API 耗时
  - Token 使用量、成本
  - 工具调用次数
- 支持导出会话（JSON/文本格式）

**API：**
- `GET /api/sessions/{session_id}/details?include_messages=true`
- `GET /api/sessions/{session_id}/tree` - 获取完整的会话树

---

#### 功能 6：Resume 对话
**位置：**会话详情页面顶部

**功能点：**
- "继续对话"按钮
- 点击后切换到输入模式
- 发送新消息时携带 `resume_session_id`
- WebSocket 发送：
```typescript
{
  "action": "start_query",
  "prompt": "继续的内容",
  "resume_session_id": "20251218T140000_1234_abcd1234"
}
```

---

## 后端 API 实现

### 文件结构

```
backend/
├── main.py                 # FastAPI 应用入口
├── api/
│   ├── __init__.py
│   ├── instances.py        # 实例管理 API
│   ├── sessions.py         # 会话查询 API
│   └── websocket.py        # WebSocket 端点
├── models/
│   ├── __init__.py
│   ├── instance.py         # 数据模型定义
│   └── session.py
├── services/
│   ├── __init__.py
│   ├── instance_service.py # 实例服务
│   ├── session_service.py  # 会话服务
│   └── websocket_service.py # WebSocket 服务
└── requirements.txt
```

### API 端点设计

#### 1. 实例管理

**`GET /api/instances`**
- 功能：列出所有可用实例
- 返回：
```json
{
  "instances": [
    {
      "name": "demo_agent",
      "description": "Demo instance",
      "tools_count": 5,
      "sub_instances_count": 2,
      "config_path": "instances/demo_agent/config.yaml"
    }
  ]
}
```

**实现：**
```python
# backend/api/instances.py
from fastapi import APIRouter
from src import AgentSystem
from pathlib import Path

router = APIRouter()

@router.get("/instances")
async def list_instances():
    instances_root = Path("instances")
    instances = []

    for instance_dir in instances_root.iterdir():
        if instance_dir.is_dir() and (instance_dir / "config.yaml").exists():
            # 临时初始化 agent 获取信息
            agent = AgentSystem(instance_dir.name)
            await agent.initialize()

            instances.append({
                "name": agent.agent_name,
                "description": agent.agent_description,
                "tools_count": agent.tools_count,
                "sub_instances_count": agent.sub_instances_count,
                "config_path": str(instance_dir / "config.yaml")
            })

            agent.cleanup()

    return {"instances": instances}
```

---

#### 2. 会话查询

**`GET /api/sessions?instance={name}&status={status}&limit=20&offset=0`**
- 功能：列出会话
- 参数：
  - `instance`: 实例名称（必需）
  - `status`: 过滤状态（可选）
  - `limit`: 每页数量（默认 20）
  - `offset`: 偏移量（默认 0）

**`GET /api/sessions/{session_id}/details?include_messages=true`**
- 功能：获取会话详情
- 参数：
  - `include_messages`: 是否包含消息（默认 true）
  - `message_limit`: 消息数量限制（默认 1000）

**`GET /api/sessions/{session_id}/tree`**
- 功能：获取会话树（包含子实例）
- 返回：完整的树状结构

**`GET /api/sessions/search?instance={name}&query={keyword}&field=initial_prompt`**
- 功能：搜索会话
- 参数：
  - `query`: 搜索关键词
  - `field`: 搜索字段（initial_prompt / result）

**实现：**
```python
# backend/api/sessions.py
from fastapi import APIRouter, Query
from src.session import SessionQuery

router = APIRouter()

@router.get("/sessions")
async def list_sessions(
    instance: str,
    status: str = None,
    limit: int = 20,
    offset: int = 0
):
    query = SessionQuery(instance)
    sessions = query.list_sessions(
        status=status,
        limit=limit,
        offset=offset
    )
    return {"sessions": sessions, "total": len(sessions)}

@router.get("/sessions/{session_id}/details")
async def get_session_details(
    session_id: str,
    instance: str,
    include_messages: bool = True,
    message_limit: int = 1000
):
    query = SessionQuery(instance)
    details = query.get_session_details(
        session_id=session_id,
        include_messages=include_messages,
        message_limit=message_limit
    )
    return details

@router.get("/sessions/{session_id}/tree")
async def get_session_tree(
    session_id: str,
    instance: str
):
    query = SessionQuery(instance)
    tree = await query.build_session_tree(
        session_id=session_id,
        include_messages=True
    )
    return tree

@router.get("/sessions/search")
async def search_sessions(
    instance: str,
    query: str,
    field: str = "initial_prompt",
    limit: int = 10
):
    session_query = SessionQuery(instance)
    results = session_query.search_sessions(
        query=query,
        field=field,
        limit=limit
    )
    return {"results": results}
```

---

#### 3. WebSocket 实时通信

**WebSocket 端点：`/ws/chat/{instance_name}`**

**连接流程：**
1. 前端建立 WebSocket 连接
2. 发送 `start_query` 消息开始对话
3. 后端创建 AgentSystem 并开始查询
4. 订阅实时消息流（SessionQuery）
5. 将消息转发到 WebSocket
6. 自动追踪子实例并转发子消息
7. 查询完成后发送 `query_complete` 消息

**消息格式：**

前端 → 后端：
```json
{
  "action": "start_query",
  "prompt": "用户输入",
  "resume_session_id": null  // 或实际的 session_id
}
```

后端 → 前端（通过 SessionQuery 转发）：
```json
// 类型 1: 父消息（来自 SessionQuery.subscribe on_parent_message）
{
  "type": "parent_message",
  "data": {
    "event_type": "message_created",
    "session_id": "parent_session_id",
    "seq": 0,
    "timestamp": "2024-12-18T10:30:45Z",
    "message_type": "UserMessage",
    "data": {
      "role": "user",
      "content": "用户输入的内容"
    }
  }
}

// 类型 2: 子实例启动（来自 SessionQuery.subscribe on_child_started）
{
  "type": "child_started",
  "child_session_id": "20241218T103100_1234_child5678",
  "instance_name": "file_analyzer",
  "timestamp": "2024-12-18T10:31:00Z"
}

// 类型 3: 子实例消息（来自 SessionQuery.subscribe on_child_message）
{
  "type": "child_message",
  "child_session_id": "20241218T103100_1234_child5678",
  "instance_name": "file_analyzer",
  "message": {
    "event_type": "message_created",
    "seq": 0,
    "timestamp": "2024-12-18T10:31:01Z",
    "message_type": "UserMessage",
    "data": {
      "role": "user",
      "content": "分析文件 test.py"
    }
  }
}

// 类型 4: 查询完成
{
  "type": "query_complete",
  "session_id": "parent_session_id",
  "result": "最终结果文本"
}

// 类型 5: 错误
{
  "type": "error",
  "message": "错误描述"
}
```

**关键简化：**
- ✅ 不需要解析 `<!--SESSION_ID:xxx-->` 标记
- ✅ 不需要维护 `tool_use_id` 映射
- ✅ 子实例消息自带 `child_session_id` 标识
- ✅ SessionQuery 处理所有复杂的订阅逻辑

**简化实现（使用 SessionQuery）：**
```python
# backend/api/websocket.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from src import AgentSystem
from src.session import MessageBus, SessionQuery
import asyncio
import json

router = APIRouter()

@router.websocket("/ws/chat/{instance_name}")
async def websocket_endpoint(websocket: WebSocket, instance_name: str):
    await websocket.accept()

    # 初始化 MessageBus
    # 📖 参考：src/session/streaming/message_bus.py - MessageBus 类的 from_config() 方法
    message_bus = MessageBus.from_config()
    await message_bus.connect()

    try:
        # 等待前端发送 start_query 消息
        data = await websocket.receive_json()

        if data.get("action") != "start_query":
            await websocket.send_json({
                "type": "error",
                "message": "Expected start_query action"
            })
            return

        prompt = data.get("prompt")
        resume_session_id = data.get("resume_session_id")

        # 创建 AgentSystem
        # 📖 参考：src/agent_system.py - AgentSystem 类的初始化和 query_text 方法
        agent = AgentSystem(instance_name, message_bus=message_bus)
        await agent.initialize()

        # 启动查询任务（后台运行）
        # 📖 参考：src/agent_system.py - query_text 方法的实现
        query_task = asyncio.create_task(
            agent.query_text(
                prompt=prompt,
                resume_session_id=resume_session_id
            )
        )

        # 等待 session 创建
        await asyncio.sleep(1.0)

        # 获取 session_id
        # 📖 参考：src/session/utils/session_context.py - SessionContext 类的 get_current_session() 方法
        from src.session.utils import SessionContext
        session_id = SessionContext.get_current_session()

        if not session_id:
            await websocket.send_json({
                "type": "error",
                "message": "Failed to get session_id"
            })
            return

        # 🎉 使用 SessionQuery 统一处理所有订阅逻辑
        # 📖 参考：src/session/query/session_query.py - SessionQuery 类的 subscribe 方法
        query = SessionQuery(instance_name, message_bus=message_bus)

        # 开始订阅（SessionQuery 会自动处理子实例追踪）
        # 📖 参考：src/session/query/session_query.py:294-325 - subscribe 方法的完整实现
        await query.subscribe(
            session_id=session_id,
            on_parent_message=lambda msg: websocket.send_json({
                "type": "parent_message",
                "data": msg
            }),
            on_child_message=lambda child_id, instance, msg: websocket.send_json({
                "type": "child_message",
                "child_session_id": child_id,
                "instance_name": instance,
                "message": msg
            }),
            on_child_started=lambda child_id, instance: websocket.send_json({
                "type": "child_started",
                "child_session_id": child_id,
                "instance_name": instance,
                "timestamp": asyncio.get_event_loop().time()
            })
        )

        # 等待查询完成
        result = await query_task

        # 发送完成消息
        await websocket.send_json({
            "type": "query_complete",
            "session_id": result.session_id,
            "result": result.result
        })

        # 清理资源
        await query.stop()
        agent.cleanup()

    except WebSocketDisconnect:
        print(f"WebSocket disconnected for {instance_name}")
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })
    finally:
        await message_bus.close()
```

**关键简化点：**
- ✅ **使用 SessionQuery**：统一处理所有订阅逻辑
  - 📖 **源码位置**：`src/session/query/session_query.py` - 完整的 SessionQuery 实现
  - 📖 **自动子实例追踪**：`src/session/query/session_query.py:496-527` - `_handle_child_started` 方法
- ✅ **自动子实例追踪**：无需手动管理订阅
  - 📖 **源码位置**：`src/session/query/session_query.py:465-494` - `_subscribe_parent` 方法自动检测子实例启动
- ✅ **简化回调函数**：直接转发消息到 WebSocket
  - 📖 **源码位置**：`src/session/query/session_query.py:529-561` - `_subscribe_child` 方法处理子消息
- ✅ **更好的错误处理**：SessionQuery 内部处理异常情况
  - 📖 **源码位置**：`src/error_handling.py` - 统一的错误处理机制

---

## 前端实现

### 文件结构

```
frontend/
├── src/
│   ├── components/
│   │   ├── InstancePanel.tsx        # 实例列表面板
│   │   ├── SessionPanel.tsx         # 历史会话面板
│   │   ├── ChatInterface.tsx        # 对话主界面
│   │   ├── MessageTree.tsx          # 消息树组件
│   │   ├── MessageCard.tsx          # 单条消息卡片
│   │   ├── ChildSessionCard.tsx     # 子实例卡片
│   │   └── SessionDetails.tsx       # 会话详情
│   ├── contexts/
│   │   ├── AppContext.tsx           # 全局状态
│   │   └── WebSocketContext.tsx     # WebSocket 管理
│   ├── hooks/
│   │   ├── useInstances.ts          # 实例管理 hook
│   │   ├── useSessions.ts           # 会话管理 hook
│   │   └── useWebSocket.ts          # WebSocket hook
│   ├── services/
│   │   ├── api.ts                   # REST API 封装
│   │   └── websocket.ts             # WebSocket 封装
│   ├── types/
│   │   ├── instance.ts              # 实例类型定义
│   │   ├── session.ts               # 会话类型定义
│   │   └── message.ts               # 消息类型定义
│   ├── utils/
│   │   ├── messageParser.ts         # 消息解析工具
│   │   └── treeBuilder.ts           # 树构建工具
│   ├── App.tsx                      # 主应用
│   └── main.tsx                     # 入口文件
├── package.json
├── tsconfig.json
└── vite.config.ts
```

### 核心组件实现

#### App.tsx（主布局）

```typescript
import React, { useState } from 'react';
import { Layout } from 'antd';
import InstancePanel from './components/InstancePanel';
import SessionPanel from './components/SessionPanel';
import ChatInterface from './components/ChatInterface';
import { AppProvider } from './contexts/AppContext';

const { Sider, Content } = Layout;

const App: React.FC = () => {
  const [selectedInstance, setSelectedInstance] = useState<string | null>(null);
  const [selectedSession, setSelectedSession] = useState<string | null>(null);

  return (
    <AppProvider>
      <Layout style={{ height: '100vh' }}>
        {/* 左侧：实例列表 */}
        <Sider width={250} theme="light">
          <InstancePanel
            selectedInstance={selectedInstance}
            onSelectInstance={setSelectedInstance}
          />
        </Sider>

        {/* 中间：对话界面 */}
        <Content>
          <ChatInterface
            instanceName={selectedInstance}
            sessionId={selectedSession}
          />
        </Content>

        {/* 右侧：历史会话 */}
        <Sider width={300} theme="light">
          <SessionPanel
            instanceName={selectedInstance}
            selectedSession={selectedSession}
            onSelectSession={setSelectedSession}
          />
        </Sider>
      </Layout>
    </AppProvider>
  );
};

export default App;
```

#### WebSocket Hook

```typescript
// hooks/useWebSocket.ts
import { useState, useEffect, useCallback, useRef } from 'react';
import { ConversationTree, MessageNode, ChildSessionInfo } from '../types/message';

export const useWebSocket = (instanceName: string | null) => {
  const [conversationTree, setConversationTree] = useState<ConversationTree | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isQuerying, setIsQuerying] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  // 连接 WebSocket
  const connect = useCallback(() => {
    if (!instanceName || wsRef.current) return;

    const ws = new WebSocket(`ws://localhost:8000/ws/chat/${instanceName}`);

    ws.onopen = () => {
      setIsConnected(true);
      console.log('WebSocket connected');
    };

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      handleWebSocketMessage(message);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    ws.onclose = () => {
      setIsConnected(false);
      wsRef.current = null;
    };

    wsRef.current = ws;
  }, [instanceName]);

  // 处理 WebSocket 消息
  const handleWebSocketMessage = (message: any) => {
    switch (message.type) {
      case 'parent_message':
        handleParentMessage(message.data);
        break;
      case 'child_started':
        handleChildStarted(message.child_session_id, message.instance_name);
        break;
      case 'child_message':
        handleChildMessage(message.child_session_id, message.instance_name, message.message);
        break;
      case 'query_complete':
        handleQueryComplete(message);
        break;
      case 'error':
        console.error('WebSocket error:', message.message);
        break;
    }
  };

  // 处理父消息
  const handleParentMessage = (msg: any) => {
    setConversationTree((prev) => {
      if (!prev) {
        // 初始化树
        return {
          session_id: msg.session_id,
          instance_name: msg.instance_name,
          messages: [createMessageNode(msg)],
          child_sessions: new Map()
        };
      }

      // 添加消息
      return {
        ...prev,
        messages: [...prev.messages, createMessageNode(msg)]
      };
    });
  };

  // 处理子实例启动
  const handleChildStarted = (childSessionId: string, instanceName: string) => {
    setConversationTree((prev) => {
      if (!prev) return prev;

      const childSession: ChildSession = {
        session_id: childSessionId,
        instance_name: instanceName,
        messages: [],
        collapsed: false  // 默认展开
      };

      const newMap = new Map(prev.child_sessions);
      newMap.set(childSessionId, childSession);

      return {
        ...prev,
        child_sessions: newMap
      };
    });
  };

  // 处理子消息
  const handleChildMessage = (childSessionId: string, instanceName: string, msg: any) => {
    setConversationTree((prev) => {
      if (!prev) return prev;

      const childSession = prev.child_sessions.get(childSessionId);
      if (!childSession) return prev;

      const messageNode = createMessageNode(msg);
      // 移除了 is_sub_instance_message 标记，因为通过 child_session_id 自动关联

      const newMap = new Map(prev.child_sessions);
      newMap.set(childSessionId, {
        ...childSession,
        messages: [...childSession.messages, messageNode]
      });

      return {
        ...prev,
        child_sessions: newMap
      };
    });
  };

  // 处理查询完成
  const handleQueryComplete = (message: any) => {
    setIsQuerying(false);
    console.log('Query complete:', message.result);
  };

  // 发送查询
  const sendQuery = useCallback((prompt: string, resumeSessionId?: string) => {
    if (!wsRef.current || !isConnected) return;

    setIsQuerying(true);
    setConversationTree(null); // 清空之前的对话

    wsRef.current.send(JSON.stringify({
      action: 'start_query',
      prompt,
      resume_session_id: resumeSessionId || null
    }));
  }, [isConnected]);

  // 断开连接
  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  // 切换子实例折叠状态
  const toggleChildSession = useCallback((sessionId: string) => {
    setConversationTree((prev) => {
      if (!prev) return prev;

      const childSession = prev.child_sessions.get(sessionId);
      if (!childSession) return prev;

      const newMap = new Map(prev.child_sessions);
      newMap.set(sessionId, {
        ...childSession,
        collapsed: !childSession.collapsed
      });

      return {
        ...prev,
        child_sessions: newMap
      };
    });
  }, []);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  return {
    conversationTree,
    isConnected,
    isQuerying,
    sendQuery,
    toggleChildSession
  };
};

// 辅助函数：创建消息节点
function createMessageNode(msg: any): MessageNode {
  return {
    seq: msg.seq,
    timestamp: msg.timestamp,
    message_type: msg.message_type,
    data: msg.data
    // 移除了 children 字段，因为通过 child_sessions Map 管理
  };
}
```

---

## 关键技术点

### 1. 子实例消息的自动关联机制

**核心优势：** SessionQuery 已经自动处理了所有子实例追踪，前端无需复杂的映射逻辑。

**SessionQuery 的自动处理流程：**

1. **订阅父会话** - SessionQuery 订阅 `session:{parent_id}` 频道
2. **检测子实例启动** - 自动识别 `sub_instance_started` 通知
3. **自动订阅子会话** - 自动订阅 `session:{child_id}` 频道
4. **消息转发** - 将所有消息通过 WebSocket 转发给前端

**前端简化实现：**
```typescript
// WebSocket 消息处理 - 非常简单！
// 📖 对应后端消息类型：参考 WebSocket 端点的回调函数实现
const handleWebSocketMessage = (message: any) => {
  switch (message.type) {
    case 'parent_message':
      // 来自 SessionQuery.subscribe 的 on_parent_message 回调
      // 📖 参考：src/session/query/session_query.py:482-489 - 父消息回调处理
      addParentMessage(message.data);
      break;

    case 'child_started':
      // 来自 SessionQuery.subscribe 的 on_child_started 回调
      // 📖 参考：src/session/query/session_query.py:513-520 - 子实例启动回调
      // 📖 参考：src/session/core/session_manager.py:319-338 - notify_sub_instance_started 方法
      createChildSession(message.child_session_id, message.instance_name);
      break;

    case 'child_message':
      // 来自 SessionQuery.subscribe 的 on_child_message 回调
      // 📖 参考：src/session/query/session_query.py:543-553 - 子消息回调处理
      addChildMessage(message.child_session_id, message.message);
      break;

    case 'query_complete':
      handleQueryComplete(message);
      break;
  }
};

// 创建子会话容器
function createChildSession(childSessionId: string, instanceName: string) {
  const childSession: ChildSession = {
    session_id: childSessionId,
    instance_name: instanceName,
    messages: [],
    collapsed: false  // 默认展开
  };

  conversationTree.child_sessions.set(childSessionId, childSession);
  updateConversationDisplay();
}
```

**为什么不需要手动映射？**
- SessionQuery 在 `_handle_child_started` 方法中自动记录 `child_sessions` 映射
- 子实例消息通过独立的订阅通道发送，自带 `child_session_id` 标识
- 消息的时间顺序保证了正确的显示位置

### 2. 消息顺序保证

**问题：** WebSocket 消息可能乱序到达，如何保证显示顺序正确？

**解决方案：**

1. **使用 seq（序列号）排序**
   - 所有消息都有 `seq` 字段
   - 插入消息时按 seq 排序

2. **缓冲乱序消息：**
```typescript
const messageBuffer = new Map<number, MessageNode>();
let expectedSeq = 0;

function addMessageInOrder(msg: MessageNode) {
  messageBuffer.set(msg.seq, msg);

  // 尝试消费连续的消息
  while (messageBuffer.has(expectedSeq)) {
    const orderedMsg = messageBuffer.get(expectedSeq)!;
    messageBuffer.delete(expectedSeq);

    // 添加到显示列表
    displayMessage(orderedMsg);
    expectedSeq++;
  }
}
```

### 3. 性能优化

**问题：** 大量消息（特别是深层嵌套）可能导致性能问题

**优化策略：**

1. **虚拟滚动**
   - 使用 `react-window` 或 `react-virtuoso`
   - 只渲染可见区域的消息

2. **懒加载子实例消息**
   - 默认折叠子实例
   - 展开时才加载消息

3. **消息分页**
   - 历史会话加载时，分批加载消息
   - "加载更多"按钮

---

## 实施步骤

### Phase 1: 后端 API 开发（1-2 天）

1. **搭建 FastAPI 项目**
   - 安装依赖：`fastapi`, `uvicorn`, `websockets`, `python-multipart`
   - 创建项目结构

2. **实现 REST API**
   - 实例列表 API
   - 会话查询 API
   - 会话详情 API
   - 会话树 API

3. **实现 WebSocket 端点**
   - 连接管理
   - 消息转发
   - 子实例追踪

4. **集成现有 Python 代码**
   - 导入 `AgentSystem`, `SessionQuery`, `MessageBus`
   - 配置 Redis 连接

5. **测试**
   - 使用 Postman 测试 REST API
   - 使用 WebSocket 客户端测试实时通信

### Phase 2: 前端基础框架（1 天）

1. **创建 React 项目**
   - 使用 Vite: `npm create vite@latest frontend -- --template react-ts`
   - 安装依赖：`antd`, `axios`, `dayjs`

2. **搭建项目结构**
   - 创建目录结构
   - 配置 TypeScript

3. **实现主布局**
   - 三栏布局（实例/对话/会话）
   - 响应式设计

4. **封装 API 服务**
   - REST API 封装
   - WebSocket 封装

### Phase 3: 核心功能开发（3-4 天）

**Day 1: 实例和会话列表**
- 实例列表面板
- 历史会话面板
- 筛选和搜索

**Day 2: 基础对话功能**
- 输入框和发送
- WebSocket 连接
- 基础消息显示

**Day 3: 树状消息展示**
- MessageTree 组件
- MessageCard 组件
- 消息类型渲染

**Day 4: 子实例功能**
- ChildSessionCard 组件
- 折叠/展开交互
- 子实例消息流

### Phase 4: 完善和优化（1-2 天）

1. **功能完善**
   - Resume 对话
   - 会话导出
   - 错误处理

2. **UI 优化**
   - 加载状态
   - 动画效果
   - 响应式适配

3. **性能优化**
   - 虚拟滚动
   - 懒加载
   - 防抖节流

4. **测试**
   - 功能测试
   - 边界情况测试
   - 性能测试

---

## 关键文件清单

### 后端需要创建的文件：

1. `backend/main.py` - FastAPI 入口
2. `backend/api/instances.py` - 实例 API
3. `backend/api/sessions.py` - 会话 API
4. `backend/api/websocket.py` - WebSocket 端点
5. `backend/requirements.txt` - Python 依赖

### 前端需要创建的文件：

1. `frontend/src/App.tsx` - 主应用
2. `frontend/src/components/InstancePanel.tsx` - 实例面板
3. `frontend/src/components/SessionPanel.tsx` - 会话面板
4. `frontend/src/components/ChatInterface.tsx` - 对话界面
5. `frontend/src/components/MessageTree.tsx` - 消息树
6. `frontend/src/components/MessageCard.tsx` - 消息卡片
7. `frontend/src/components/ChildSessionCard.tsx` - 子实例卡片
8. `frontend/src/hooks/useWebSocket.ts` - WebSocket hook
9. `frontend/src/services/api.ts` - API 服务
10. `frontend/src/types/message.ts` - 类型定义

### 现有代码需要调用的文件：

1. `src/agent_system.py` - AgentSystem 类
2. `src/session/query/session_query.py` - SessionQuery 类
3. `src/session/streaming/message_bus.py` - MessageBus 类
4. `src/session/utils/session_context.py` - SessionContext 工具

---

## 📚 完整源代码指引

### 🏗️ **核心架构组件**

#### 1. AgentSystem - 主系统类
**文件位置**：`src/agent_system.py`
**关键方法**：
- `__init__(instance_name, message_bus=None)` - 初始化系统
- `initialize()` - 加载配置和工具
- `query_text(prompt, resume_session_id=None)` - 执行查询
- `cleanup()` - 清理资源

#### 2. SessionQuery - 统一会话查询与订阅服务
**文件位置**：`src/session/query/session_query.py`
**关键功能**：
- 🎉 **实时订阅**：`subscribe()` 方法自动处理父子会话订阅
- 🎉 **子实例追踪**：`_handle_child_started()` 自动检测子实例启动
- 🎉 **消息转发**：通过回调函数实时转发消息
- **查询方法**：`get_session_details()`, `list_sessions()`, `search_sessions()`

#### 3. MessageBus - Redis 消息总线
**文件位置**：`src/session/streaming/message_bus.py`
**关键方法**：
- `from_config()` - 从配置文件创建实例
- `connect()` / `close()` - 连接管理
- `subscribe(channel)` - 订阅 Redis 频道
- `publish(channel, message)` - 发布消息

#### 4. SessionContext - 会话上下文管理
**文件位置**：`src/session/utils/session_context.py`
**关键方法**：
- `get_current_session()` - 获取当前会话ID
- `set_current_session(session_id)` - 设置当前会话

### 🗄️ **会话存储组件**

#### 1. Session - 会话数据模型
**文件位置**：`src/session/core/session.py`
**关键功能**：
- 消息存储和检索
- 会话元数据管理
- 统计信息生成

#### 2. SessionManager - 会话生命周期管理
**文件位置**：`src/session/core/session_manager.py`
**关键方法**：
- `create_session()` - 创建新会话
- `get_session()` - 获取已有会话
- `notify_sub_instance_started()` - 发送子实例启动通知

#### 3. MessageSerializer - 消息序列化
**文件位置**：`src/session/utils/session_serializer.py`
**关键功能**：
- 消息对象与JSON的相互转换
- 时间戳和序号处理

### 🔧 **工具和配置组件**

#### 1. ToolManager - 工具管理器
**文件位置**：`src/tool_manager.py`
**功能**：自动发现和加载工具函数

#### 2. SubInstanceAdapter - 子实例适配器
**文件位置**：`src/sub_instance_adapter.py`
**关键功能**：
- 将子实例封装为工具函数
- 在工具结果中嵌入 `<!--SESSION_ID:xxx-->` 标记

#### 3. ConfigManager - 配置管理器
**文件位置**：`src/config_manager.py`
**功能**：加载和管理实例配置

### 📁 **实例目录结构**

#### 标准实例布局
```
instances/{instance_name}/
├── config.yaml          # 实例配置文件
├── .claude/              # Claude 相关配置
├── tools/                # 自定义工具目录
│   └── *.py             # 工具文件（异步函数）
├── agent.md             # 实例提示词文档
└── sessions/             # 会话记录目录（自动创建）
    └── {session_id}/     # 每个会话的独立目录
        ├── messages.jsonl    # 消息文件
        ├── metadata.json     # 元数据文件
        └── statistics.json   # 统计信息文件
```

#### 现有实例示例
- **demo_agent**：`instances/demo_agent/` - 演示实例
  - 工具：`calculator.py`, `file_analyzer.py`
- **file_analyzer_agent**：`instances/file_analyzer_agent/` - 文件分析实例
  - 工具：`file_detector.py`, `content_analyzer.py`, `metadata_extractor.py`

### 🔄 **消息流和订阅机制**

#### Redis 频道命名规则
- 父会话频道：`session:{parent_session_id}`
- 子会话频道：`session:{child_session_id}`

#### 子实例启动通知格式
```json
{
  "type": "sub_instance_started",
  "parent_session_id": "parent_id",
  "child_session_id": "child_id",
  "child_instance_name": "instance_name",
  "timestamp": "2024-12-18T10:31:00Z"
}
```
**源码位置**：`src/session/core/session_manager.py:319-338`

### 🌐 **WebSocket 端点实现指南**

#### 需要创建的文件
```
backend/
├── api/
│   ├── websocket.py      # WebSocket 端点实现
│   └── __init__.py
└── main.py              # FastAPI 应用入口
```

#### 关键导入和依赖
```python
from src import AgentSystem
from src.session import MessageBus, SessionQuery
from src.session.utils import SessionContext
```

### 💡 **开发最佳实践**

#### 1. 错误处理
- 使用 `src/error_handling.py` 中的 `AgentSystemError` 异常类
- WebSocket 断开时正确清理资源

#### 2. 资源管理
- 确保 `MessageBus.connect()` 和 `close()` 成对调用
- 使用 `asyncio.create_task()` 创建后台任务
- 调用 `query.stop()` 和 `agent.cleanup()` 清理资源

#### 3. 配置管理
- 实例配置存储在 `instances/{instance_name}/config.yaml`
- Redis 配置在 `streaming.yaml`（可选）

#### 4. 日志记录
- 使用 `src/logging_config.py` 中的日志配置
- WebSocket 连接和消息处理应有适当的日志记录

### 🎯 **快速开始检查清单**

1. ✅ 检查现有实例：`instances/` 目录下的 demo_agent, file_analyzer_agent
2. ✅ 确认 Redis 服务运行（用于实时消息）
3. ✅ 创建 FastAPI 项目结构
4. ✅ 实现 WebSocket 端点（参考上面的完整示例）
5. ✅ 创建前端 React + TypeScript 项目
6. ✅ 实现前端组件（参考数据模型和消息处理逻辑）
7. ✅ 测试父子实例消息流

这个源代码指引为前端开发提供了完整的后端架构理解，确保实现时能够充分利用现有的强大功能！


