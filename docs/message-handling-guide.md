# 消息处理与显示指南

本文档详细说明如何正确处理和显示 Claude Agent System 中的各种消息类型，避免常见的消息解析错误。

## 🚨 常见问题：为什么我的消息显示"未知消息类型"？

### 问题现象
```python
async def on_parent_message(msg):
    msg_type = msg.get('type', 'unknown')  # ❌ 错误！
    print(f"消息类型: {msg_type}")
```

### 错误原因
系统消息的实际格式中，**消息类型存储在 `message_type` 字段**，而不是 `type` 字段。

### 正确做法
```python
async def on_parent_message(msg):
    msg_type = msg.get('message_type', 'unknown')  # ✅ 正确！
    print(f"消息类型: {msg_type}")
```

---

## 📊 消息格式详解

### 基本消息结构

所有消息都遵循以下JSON结构：

```json
{
  "message_type": "UserMessage|AssistantMessage|ResultMessage|SystemMessage",
  "timestamp": "2025-12-19T08:47:45.123Z",
  "data": {
    // 具体的消息内容
  }
}
```

### 消息类型详解

#### 1. UserMessage（用户消息）

**结构**：
```json
{
  "message_type": "UserMessage",
  "data": {
    "role": "user",
    "content": "请帮我分析这个文件"
  }
}
```

**处理示例**：
```python
async def handle_user_message(msg):
    content = msg.get('data', {}).get('content', '')
    print(f"👤 [用户输入]: {content}")
```

#### 2. AssistantMessage（AI回复消息）

**结构**：
```json
{
  "message_type": "AssistantMessage",
  "data": {
    "model": "claude-sonnet-4-5",
    "content": [
      {
        "type": "text",
        "text": "我来帮您分析这个文件..."
      },
      {
        "type": "tool_use",
        "id": "tool_123",
        "name": "file_analyzer",
        "input": {"path": "doc.txt", "analysis_type": "deep"}
      },
      {
        "type": "tool_result",
        "tool_use_id": "tool_123",
        "content": "文件分析完成",
        "is_error": false
      }
    ]
  }
}
```

**处理示例**：
```python
async def handle_assistant_message(msg):
    content_blocks = msg.get('data', {}).get('content', [])
    print("🤖 [AI回复]:")

    for block in content_blocks:
        block_type = block.get('type')

        if block_type == 'text':
            text = block.get('text', '')
            print(f"   {text}")

        elif block_type == 'tool_use':
            tool_name = block.get('name', 'unknown')
            tool_input = block.get('input', {})
            print(f"🔧 [工具调用] {tool_name}")
            if tool_input:
                print(f"   📋 参数: {tool_input}")

        elif block_type == 'tool_result':
            content = block.get('content', '')
            is_error = block.get('is_error', False)
            status = "❌ 失败" if is_error else "✅ 成功"
            print(f"{status} [工具结果] {content}")
```

#### 3. ResultMessage（结果消息）

**结构**：
```json
{
  "message_type": "ResultMessage",
  "data": {
    "subtype": "final_result",
    "duration_ms": 2100,
    "duration_api_ms": 1800,
    "is_error": false,
    "num_turns": 3,
    "total_cost_usd": 0.025,
    "usage": {
      "input_tokens": 150,
      "output_tokens": 200
    },
    "result": "分析完成，文件包含3个章节..."
  }
}
```

**处理示例**：
```python
async def handle_result_message(msg):
    data = msg.get('data', {})
    result = data.get('result', '')
    is_error = data.get('is_error', False)
    duration_ms = data.get('duration_ms', 0)
    cost_usd = data.get('total_cost_usd', 0)

    status = "❌ 执行失败" if is_error else "✅ 执行完成"
    print(f"\n🏁 [会话结束] {status}")
    print(f"   ⏱️ 耗时: {duration_ms}ms")
    print(f"   💰 成本: ${cost_usd:.4f}")

    if result and not is_error:
        print(f"   📄 结果: {result}")
```

#### 4. SystemMessage（系统消息）

**结构**：
```json
{
  "message_type": "SystemMessage",
  "data": {
    "subtype": "sub_instance_started",
    "instance_name": "file_analyzer",
    "session_id": "20251219T084746_5678_efgh5678"
  }
}
```

**处理示例**：
```python
async def handle_system_message(msg):
    data = msg.get('data', {})
    subtype = data.get('subtype', 'unknown')

    if subtype == 'sub_instance_started':
        instance_name = data.get('instance_name', 'unknown')
        print(f"\n🔔 [系统] 子实例启动: {instance_name}")
    else:
        print(f"\n📋 [系统] {subtype}")
```

---

## 🛠️ 完整的消息处理模板

### 基础模板

```python
async def on_parent_message(msg):
    """处理主Agent消息的完整模板"""
    msg_type = msg.get('message_type', 'unknown')

    try:
        if msg_type == 'UserMessage':
            content = msg.get('data', {}).get('content', '')
            print(f"\n👤 [用户输入]: {content}")

        elif msg_type == 'AssistantMessage':
            await handle_assistant_message(msg)

        elif msg_type == 'ResultMessage':
            await handle_result_message(msg)

        elif msg_type == 'SystemMessage':
            await handle_system_message(msg)

        else:
            print(f"\n📨 [未知消息类型]: {msg_type}")
            # 调试时可以查看完整结构
            # print(f"   详情: {msg}")

    except Exception as e:
        print(f"\n❌ [消息处理错误]: {e}")

async def handle_assistant_message(msg):
    """处理AI回复消息"""
    content_blocks = msg.get('data', {}).get('content', [])
    print(f"\n🤖 [AI回复]:")

    for block in content_blocks:
        block_type = block.get('type')

        if block_type == 'text':
            text = block.get('text', '')
            if text:
                # 处理长文本
                if len(text) > 300:
                    print(f"   {text[:300]}...")
                else:
                    print(f"   {text}")

        elif block_type == 'tool_use':
            tool_name = block.get('name', 'unknown')
            tool_input = block.get('input', {})
            print(f"\n🔧 [工具调用] {tool_name}")
            if tool_input and isinstance(tool_input, dict):
                # 限制参数长度显示
                args_str = ", ".join([f"{k}={v}" for k, v in tool_input.items()
                                    if len(str(v)) < 50])
                print(f"   📋 参数: {args_str}")

        elif block_type == 'tool_result':
            content = block.get('content', '')
            is_error = block.get('is_error', False)
            status_icon = "❌" if is_error else "✅"
            print(f"\n{status_icon} [工具结果] {'执行失败' if is_error else '执行完成'}")

            if content:
                if len(content) > 200:
                    print(f"   📄 结果: {content[:200]}...")
                else:
                    print(f"   📄 结果: {content}")
```

### 子实例消息处理模板

```python
async def on_child_message(child_id: str, instance: str, msg):
    """处理子实例消息"""
    msg_type = msg.get('message_type', 'unknown')

    # 使用与主实例相同的处理逻辑，但添加子实例标识
    if msg_type == 'UserMessage':
        content = msg.get('data', {}).get('content', '')
        print(f"\n👤 [子实例-{instance} 用户输入]: {content}")

    elif msg_type == 'AssistantMessage':
        content_blocks = msg.get('data', {}).get('content', [])
        print(f"\n🤖 [子实例-{instance} AI回复]:")

        for block in content_blocks:
            block_type = block.get('type')

            if block_type == 'tool_use':
                tool_name = block.get('name', 'unknown')
                print(f"\n🔧 [子实例-{instance} 工具调用] {tool_name}")

            # ... 其他块类型处理逻辑，注意增加缩进层级

    elif msg_type == 'ResultMessage':
        data = msg.get('data', {})
        duration_ms = data.get('duration_ms', 0)
        print(f"\n🏁 [子实例-{instance} 会话结束] 执行完成")
        print(f"         ⏱️ 耗时: {duration_ms}ms")
```

---

## 🔍 调试技巧

### 1. 查看完整消息结构

当遇到未知消息时，可以打印完整结构：

```python
import json

async def debug_message(msg):
    """调试消息结构"""
    msg_type = msg.get('message_type', 'unknown')
    print(f"\n🔍 [调试] 消息类型: {msg_type}")

    # 美化打印JSON结构
    pretty_json = json.dumps(msg, indent=2, ensure_ascii=False)
    print(f"📋 [结构]:\n{pretty_json}")
```

### 2. 处理异常情况

```python
async def safe_message_handler(msg):
    """安全的消息处理器"""
    try:
        msg_type = msg.get('message_type', 'unknown')

        if not msg_type or msg_type == 'unknown':
            print(f"\n⚠️  [警告] 无效消息格式: {msg.keys()}")
            return

        # 检查必要字段
        if 'data' not in msg:
            print(f"\n⚠️  [警告] 缺少data字段: {msg_type}")
            return

        # 正常处理逻辑...

    except Exception as e:
        print(f"\n❌ [处理错误]: {e}")
        import traceback
        traceback.print_exc()
```

### 3. 消息验证

```python
def validate_message(msg):
    """验证消息格式"""
    required_fields = ['message_type', 'data']

    for field in required_fields:
        if field not in msg:
            return False, f"缺少必要字段: {field}"

    msg_type = msg.get('message_type')
    valid_types = ['UserMessage', 'AssistantMessage', 'ResultMessage', 'SystemMessage']

    if msg_type not in valid_types:
        return False, f"无效消息类型: {msg_type}"

    return True, "消息格式正确"
```

---

## 🎯 最佳实践

### 1. 使用函数分离关注点

```python
class MessageHandler:
    """消息处理器类"""

    def __init__(self, instance_name="main"):
        self.instance_name = instance_name

    async def handle_message(self, msg, is_child=False):
        """统一消息处理入口"""
        msg_type = msg.get('message_type', 'unknown')
        prefix = f"[子实例-{self.instance_name}]" if is_child else "[主Agent]"

        handler_map = {
            'UserMessage': self._handle_user,
            'AssistantMessage': self._handle_assistant,
            'ResultMessage': self._handle_result,
            'SystemMessage': self._handle_system
        }

        handler = handler_map.get(msg_type)
        if handler:
            await handler(msg, prefix)
        else:
            print(f"\n📨 {prefix} 未知消息类型: {msg_type}")

    async def _handle_user(self, msg, prefix):
        content = msg.get('data', {}).get('content', '')
        print(f"\n👤 {prefix} [用户输入]: {content}")

    async def _handle_assistant(self, msg, prefix):
        # ... AssistantMessage 处理逻辑
        pass
```

### 2. 配置化的显示选项

```python
class MessageDisplayConfig:
    """消息显示配置"""
    show_tool_calls = True
    show_tool_results = True
    max_content_length = 300
    max_parameter_length = 50
    use_colors = True
    show_timestamps = True

def format_message(msg, config=MessageDisplayConfig()):
    """根据配置格式化消息"""
    # 根据配置决定显示的详细程度
    pass
```

### 3. 异常处理和恢复

```python
async def robust_message_handler(msg):
    """健壮的消息处理器"""
    try:
        # 验证消息
        is_valid, error_msg = validate_message(msg)
        if not is_valid:
            print(f"❌ 消息验证失败: {error_msg}")
            return

        # 处理消息
        await process_message(msg)

    except json.JSONDecodeError:
        print("❌ 消息JSON解析失败")
    except Exception as e:
        print(f"❌ 消息处理异常: {e}")
        # 记录错误消息到文件以便调试
        log_error_message(msg, e)
```

---

## 📚 相关文档

- [SessionQuery 完整使用指南](session-query-guide.md) - 查询和订阅的详细说明
- [会话系统完整指南](session-guide.md) - 会话管理和架构说明
- [API 参考](api-reference.md) - 完整的API文档
- [配置指南](configuration.md) - 系统配置选项

---

## 🎉 总结

正确处理系统消息的关键点：

1. **使用正确的字段名**：`message_type` 而不是 `type`
2. **从 `data` 字段提取内容**：`msg.get('data', {})`
3. **处理内容块数组**：AssistantMessage 的 `content` 是数组
4. **区分消息类型**：4种核心消息类型的结构不同
5. **添加错误处理**：网络异常、格式错误的处理
6. **考虑性能**：限制长内容显示，避免UI卡顿

遵循本指南，您就可以避免常见的"未知消息类型"问题，正确地显示和处理系统中的所有消息！