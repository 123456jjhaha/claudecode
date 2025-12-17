# Claude Agent System 会话记录提取与查看教程

本教程将详细介绍如何使用 Claude Agent System 的会话记录系统，包括查询、分析和管理对话历史。

## 目录

1. [系统概览](#1-系统概览)
2. [会话记录结构](#2-会话记录结构)
3. [基础查询操作](#3-基础查询操作)
4. [高级查询功能](#4-高级查询功能)
5. [实时消息订阅](#5-实时消息订阅)
6. [会话分析与统计](#6-会话分析与统计)
7. [编程接口详解](#7-编程接口详解)
8. [实用工具脚本](#8-实用工具脚本)
9. [故障排除](#9-故障排除)

## 1. 系统概览

### 1.1 会话记录架构

Claude Agent System 采用分层式存储架构来管理会话记录：

```
instances/
└── {instance_name}/           # 实例目录
    └── sessions/              # 会话存储目录
        └── {session_id}/      # 每个会话的独立目录
            ├── metadata.json   # 会话元数据
            ├── statistics.json # 统计信息
            └── messages.jsonl # 消息记录（JSON Lines格式）
```

### 1.2 核心特性

- **完整记录**: 自动记录所有对话消息、工具调用和系统事件
- **实时存储**: 消息产生时立即写入，支持异步批量优化
- **层级关系**: 支持子实例会话的父子关系追踪
- **多格式支持**: JSON元数据 + JSONL消息流
- **实时推送**: 基于Redis的实时消息订阅（可选）

## 2. 会话记录结构

### 2.1 Session ID 格式

每个会话都有唯一的标识符，格式为：`{timestamp}_{counter}_{short_hash}`

示例：`20251216T210032_7347_8e02a38f`

- `timestamp`: 会话开始时间（UTC）
- `counter`: 当日会话计数器
- `short_hash`: 唯一性哈希值

### 2.2 文件结构详解

#### metadata.json - 会话元数据

```json
{
  "session_id": "20251216T210032_7347_8e02a38f",
  "instance_name": "demo_agent",
  "start_time": "2025-12-16T21:00:32.317347",
  "end_time": "2025-12-16T21:03:50.362179",
  "status": "completed",
  "prompts": [
    {
      "prompt": "分析这个项目的配置文件",
      "timestamp": "2025-12-16T21:00:32.317347"
    }
  ],
  "results": [
    {
      "result": "分析完成，发现了3个配置文件...",
      "timestamp": "2025-12-16T21:03:50.362179",
      "is_error": false
    }
  ],
  "depth": 0,
  "parent_session_id": null,
  "context": {}
}
```

#### statistics.json - 统计信息

```json
{
  "session_id": "20251216T210032_7347_8e02a38f",
  "total_duration_ms": 196405,
  "api_duration_ms": 72337,
  "num_turns": 2,
  "num_messages": 6,
  "num_tool_calls": 1,
  "tools_used": {
    "file_analyzer": 1
  },
  "subsessions": [
    {
      "session_id": "20251216T210102_0907_7d06e081",
      "tool_name": "sub_claude_file_analyzer",
      "tool_use_id": "call_n6l2jb3tc7g",
      "timestamp": "2025-12-16T21:03:43.526217"
    }
  ],
  "token_usage": {
    "input_tokens": 2669,
    "output_tokens": 542,
    "cache_read_input_tokens": 34432
  },
  "cost_usd": 0.0767961,
  "final_status": "completed",
  "error_count": 0
}
```

#### messages.jsonl - 消息记录

每行一个JSON对象，按时间顺序排列：

```json
{"seq": 0, "timestamp": "2025-12-16T21:00:33.987905", "message_type": "SystemMessage", "data": {"type": "system", "subtype": "init", ...}}
{"seq": 1, "timestamp": "2025-12-16T21:01:02.058971", "message_type": "UserMessage", "data": {"role": "user", "content": [...]}}
{"seq": 2, "timestamp": "2025-12-16T21:01:02.098806", "message_type": "AssistantMessage", "data": {"model": "claude-sonnet-4-5", "content": [...]}}
{"seq": 3, "timestamp": "2025-12-16T21:01:05.123456", "message_type": "UserMessage", "data": {"role": "user", "content": [...]}}
```

### 2.3 消息类型说明

- **SystemMessage**: 系统内部消息（初始化、配置等）
- **UserMessage**: 用户输入消息（包括工具结果）
- **AssistantMessage**: Claude助手的响应
- **ResultMessage**: 执行结果消息

## 3. 基础查询操作

### 3.1 初始化查询环境

```python
import asyncio
from pathlib import Path
from src.session.query.session_query import (
    get_session_details,
    list_sessions,
    search_sessions,
    get_session_statistics_summary
)

# 设置实例路径
instances_root = Path("instances")
instance_name = "demo_agent"
```

### 3.2 获取会话列表

```python
# 列出最近的会话
async def list_recent_sessions():
    """列出最近10个完成的会话"""
    sessions = list_sessions(
        instance_name=instance_name,
        status="completed",  # 可选: "running", "completed", "failed", None(全部)
        limit=10
    )

    print(f"最近10个会话 ({instance_name}):")
    print("-" * 80)
    for i, session in enumerate(sessions, 1):
        print(f"{i:2d}. {session['session_id'][:19]}...")
        print(f"    状态: {session['status']}")
        print(f"    开始: {session['start_time']}")
        print(f"    时长: {session.get('duration_ms', 0) // 1000}秒")
        print(f"    轮数: {session.get('num_turns', 0)}")
        print()

# 运行
await list_recent_sessions()
```

### 3.3 获取会话详情

```python
async def view_session_details(session_id: str):
    """查看特定会话的详细信息"""
    details = get_session_details(
        instance_name=instance_name,
        session_id=session_id,
        include_messages=True,  # 是否包含消息
        message_limit=50       # 最多返回50条消息
    )

    if not details:
        print(f"会话 {session_id} 不存在")
        return

    # 显示基本信息
    metadata = details['metadata']
    stats = details['statistics']

    print(f"会话ID: {metadata['session_id']}")
    print(f"实例: {metadata['instance_name']}")
    print(f"状态: {metadata['status']}")
    print(f"开始时间: {metadata['start_time']}")
    print(f"结束时间: {metadata['end_time']}")
    print(f"持续时间: {stats['total_duration_ms'] / 1000:.2f}秒")
    print(f"对话轮数: {stats['num_turns']}")
    print(f"消息总数: {stats['num_messages']}")
    print(f"工具调用: {stats['num_tool_calls']}")

    # 显示初始提示词
    if metadata['prompts']:
        print(f"\n初始提示词:")
        print(metadata['prompts'][0]['prompt'])

    # 显示最终结果
    if metadata['results']:
        print(f"\n最终结果:")
        print(metadata['results'][-1]['result'])

    # 显示使用的工具
    if stats['tools_used']:
        print(f"\n使用的工具:")
        for tool, count in stats['tools_used'].items():
            print(f"  - {tool}: {count}次")

    # 显示消息流
    if details.get('messages'):
        print(f"\n最近消息 (最多50条):")
        print("-" * 80)
        for msg in details['messages']:
            timestamp = msg['timestamp'][:19]  # 去掉微秒
            msg_type = msg['message_type']
            seq = msg['seq']

            print(f"[{timestamp}] {seq:03d} {msg_type}")

            # 根据消息类型显示关键信息
            if msg_type == "UserMessage":
                content = msg['data']['content'][0] if msg['data']['content'] else ""
                if content.get('type') == 'text':
                    text = content['text'][:100]
                    print(f"    用户: {text}...")
            elif msg_type == "AssistantMessage":
                for block in msg['data']['content']:
                    if block.get('type') == 'text':
                        text = block['text'][:100]
                        print(f"    助手: {text}...")
                    elif block.get('type') == 'tool_use':
                        print(f"    工具调用: {block['name']}")

# 使用示例
session_id = "20251216T210032_7347_8e02a38f"
await view_session_details(session_id)
```

### 3.4 搜索会话

```python
async def search_conversations():
    """搜索包含特定内容的会话"""
    # 搜索结果中包含"分析"的会话
    results = search_sessions(
        instance_name=instance_name,
        query="分析",
        field="result",  # 搜索字段: "initial_prompt" | "result" | "both"
        limit=5
    )

    print(f"搜索结果 (包含'分析'的会话):")
    print("-" * 80)
    for i, result in enumerate(results, 1):
        print(f"{i}. {result['session_id'][:19]}...")
        print(f"   时间: {result['start_time']}")
        print(f"   匹配内容: {result['matched_content'][:100]}...")
        print()

await search_conversations()
```

## 4. 高级查询功能

### 4.1 会话树构建（处理子实例）

```python
from src.session.query.tree_builder import SessionTreeBuilder

async def build_session_tree(session_id: str):
    """构建包含子实例的会话树"""
    tree_builder = SessionTreeBuilder(instances_root=instances_root)

    # 构建树形结构
    tree = await tree_builder.build_tree(
        session_id=session_id,
        instance_name=instance_name,
        include_messages=False,
        max_depth=3
    )

    # 递归显示树结构
    def print_tree(node, level=0):
        indent = "  " * level
        metadata = node['metadata']
        stats = node.get('statistics', {})

        print(f"{indent}📁 {metadata['session_id'][:19]}...")
        print(f"{indent}   状态: {metadata['status']}")
        print(f"{indent}   实例: {metadata['instance_name']}")
        print(f"{indent}   深度: {metadata['depth']}")

        if stats:
            print(f"{indent}   时长: {stats.get('total_duration_ms', 0) / 1000:.1f}s")
            print(f"{indent}   工具调用: {stats.get('num_tool_calls', 0)}")

        if 'children' in node:
            for child in node['children']:
                print_tree(child, level + 1)

    print("会话树结构:")
    print_tree(tree)

# 使用示例
await build_session_tree("20251216T210032_7347_8e02a38f")
```

### 4.2 批量分析会话

```python
async def analyze_recent_sessions(days: int = 7):
    """分析最近几天的会话统计"""
    from datetime import datetime, timedelta

    # 获取统计摘要
    stats = get_session_statistics_summary(
        instance_name=instance_name,
        recent_days=days
    )

    print(f"最近 {days} 天的会话统计:")
    print("=" * 50)

    # 基础统计
    print(f"总会话数: {stats['total_sessions']}")
    print(f"已完成: {stats['completed_sessions']}")
    print(f"运行中: {stats['running_sessions']}")
    print(f"失败: {stats['failed_sessions']}")
    print(f"完成率: {stats['completed_sessions'] / stats['total_sessions'] * 100:.1f}%")

    # 时间统计
    print(f"\n时间统计:")
    print(f"总时长: {stats['total_duration_ms'] / 3600000:.2f} 小时")
    print(f"平均时长: {stats['avg_duration_ms'] / 1000:.1f} 秒")
    print(f"API调用占比: {stats['api_duration_ms'] / stats['total_duration_ms'] * 100:.1f}%")

    # 成本统计
    print(f"\n成本统计:")
    print(f"总成本: ${stats['total_cost_usd']:.4f}")
    print(f"平均每会话: ${stats['avg_cost_usd']:.4f}")

    # Token统计
    if 'token_usage' in stats:
        tokens = stats['token_usage']
        print(f"\nToken使用:")
        print(f"输入: {tokens['input_tokens']:,}")
        print(f"输出: {tokens['output_tokens']:,}")
        print(f"缓存命中: {tokens['cache_read_input_tokens']:,}")

        if tokens['input_tokens'] > 0:
            cache_hit_rate = tokens['cache_read_input_tokens'] / (tokens['input_tokens'] + tokens['cache_read_input_tokens']) * 100
            print(f"缓存命中率: {cache_hit_rate:.1f}%")

await analyze_recent_sessions(7)
```

## 5. 实时消息订阅

### 5.1 启用实时消息系统

首先确保配置了Redis连接：

```python
import asyncio
from src.session.streaming import MessageBus

async def setup_realtime_system():
    """设置实时消息系统"""
    # 从配置文件创建MessageBus
    message_bus = MessageBus.from_config()  # 读取streaming.yaml

    try:
        await message_bus.connect()
        print("✅ 实时消息系统已连接")
        return message_bus
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        print("将使用离线模式")
        return None

# 使用示例
message_bus = await setup_realtime_system()
```

### 5.2 订阅会话消息

```python
async def subscribe_to_session(session_id: str):
    """订阅特定会话的实时消息"""
    if not message_bus:
        print("实时消息系统未启用")
        return

    print(f"订阅会话 {session_id} 的实时消息:")
    print("-" * 50)

    try:
        async for event in subscribe_session_messages(session_id, message_bus):
            # 解析事件数据
            event_data = event.get('data', {})
            message_type = event_data.get('message_type', 'Unknown')
            timestamp = event.get('timestamp', '')[:19]

            print(f"[{timestamp}] {message_type}")

            # 根据消息类型显示详细信息
            if message_type == "AssistantMessage":
                content = event_data.get('data', {}).get('content', [])
                for block in content:
                    if block.get('type') == 'text':
                        text = block.get('text', '')[:100]
                        print(f"  🤖: {text}...")
                    elif block.get('type') == 'tool_use':
                        tool_name = block.get('name', '')
                        print(f"  🔧: 调用工具 {tool_name}")

            elif message_type == "UserMessage":
                content = event_data.get('data', {}).get('content', [])
                if content and content[0].get('type') == 'text':
                    text = content[0].get('text', '')[:100]
                    print(f"  👤: {text}...")

    except KeyboardInterrupt:
        print("\n停止订阅")
    except Exception as e:
        print(f"订阅错误: {e}")

# 使用示例
await subscribe_to_session("20251216T210032_7347_8e02a38f")
```

### 5.3 监控实例活动

```python
async def monitor_instance(instance_name: str):
    """监控整个实例的活动"""
    if not message_bus:
        print("实时消息系统未启用")
        return

    # 订阅实例级别的消息
    channel = f"messages:instance:{instance_name}"

    print(f"监控实例 {instance_name} 的所有活动:")
    print("-" * 50)

    try:
        async for event in message_bus.subscribe(channel):
            event_type = event.get('event_type', '')
            session_id = event.get('session_id', '')

            if event_type == 'session_started':
                print(f"🆕 会话开始: {session_id[:19]}...")
            elif event_type == 'session_completed':
                print(f"✅ 会话完成: {session_id[:19]}...")
            elif event_type == 'message_added':
                print(f"💬 新消息: {session_id[:19]}...")
            elif event_type == 'tool_called':
                tool_name = event.get('tool_name', '')
                print(f"🔧 工具调用: {tool_name} in {session_id[:19]}...")

    except KeyboardInterrupt:
        print("\n停止监控")
    except Exception as e:
        print(f"监控错误: {e}")

# 使用示例
await monitor_instance("demo_agent")
```

## 6. 会话分析与统计

### 6.1 工具使用分析

```python
async def analyze_tool_usage(days: int = 30):
    """分析工具使用情况"""
    sessions = list_sessions(
        instance_name=instance_name,
        status="completed",
        limit=1000  # 获取足够多的样本
    )

    # 统计工具使用
    tool_stats = {}
    tool_costs = {}

    for session in sessions:
        session_path = instances_root / instance_name / "sessions" / session['session_id']
        stats_file = session_path / "statistics.json"

        if stats_file.exists():
            import json
            with open(stats_file, 'r', encoding='utf-8') as f:
                stats = json.load(f)

                # 统计工具使用次数
                for tool, count in stats.get('tools_used', {}).items():
                    tool_stats[tool] = tool_stats.get(tool, 0) + count

                    # 估算工具使用成本
                    cost_per_use = stats.get('cost_usd', 0) / max(1, stats.get('num_tool_calls', 1))
                    tool_costs[tool] = tool_costs.get(tool, 0) + cost_per_use * count

    # 排序并显示
    print(f"工具使用统计 (最近{days}天):")
    print("=" * 50)

    sorted_tools = sorted(tool_stats.items(), key=lambda x: x[1], reverse=True)

    for tool, count in sorted_tools[:10]:  # 显示前10个
        cost = tool_costs.get(tool, 0)
        print(f"{tool:30s}: {count:3d}次, ${cost:.4f}")

await analyze_tool_usage(30)
```

### 6.2 错误分析

```python
async def analyze_errors(days: int = 30):
    """分析会话错误"""
    sessions = list_sessions(
        instance_name=instance_name,
        status="failed",
        limit=100
    )

    print(f"失败会话分析 (最近{days}天):")
    print("=" * 50)

    error_types = {}
    error_messages = []

    for session in sessions:
        session_path = instances_root / instance_name / "sessions" / session['session_id']
        metadata_file = session_path / "metadata.json"

        if metadata_file.exists():
            import json
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)

                # 分析错误结果
                for result in metadata.get('results', []):
                    if result.get('is_error'):
                        error_msg = result.get('result', '')[:100]
                        error_messages.append({
                            'session_id': session['session_id'],
                            'timestamp': result.get('timestamp'),
                            'error': error_msg
                        })

                        # 简单的错误分类
                        if 'timeout' in error_msg.lower():
                            error_types['Timeout'] = error_types.get('Timeout', 0) + 1
                        elif 'permission' in error_msg.lower():
                            error_types['Permission'] = error_types.get('Permission', 0) + 1
                        elif 'not found' in error_msg.lower():
                            error_types['NotFound'] = error_types.get('NotFound', 0) + 1
                        else:
                            error_types['Other'] = error_types.get('Other', 0) + 1

    # 显示错误统计
    print("错误类型分布:")
    for error_type, count in error_types.items():
        print(f"  {error_type}: {count}")

    # 显示最近错误
    print(f"\n最近错误 (最多5个):")
    for error in error_messages[-5:]:
        print(f"  会话: {error['session_id'][:19]}...")
        print(f"  时间: {error['timestamp']}")
        print(f"  错误: {error['error']}")
        print()

await analyze_errors(30)
```

## 7. 编程接口详解

### 7.1 核心查询函数

#### `get_session_details()`

获取会话的完整信息，包括元数据、统计和消息。

```python
def get_session_details(
    instance_name: str,
    session_id: str,
    include_messages: bool = True,
    message_limit: int = 100
) -> Optional[Dict]:
    """
    参数:
        instance_name: 实例名称
        session_id: 会话ID
        include_messages: 是否包含消息
        message_limit: 最多返回的消息数

    返回:
        {
            'metadata': Dict,      # 会话元数据
            'statistics': Dict,    # 统计信息
            'messages': List[Dict] # 消息列表（可选）
        }
    """
```

#### `list_sessions()`

列出会话，支持过滤和分页。

```python
def list_sessions(
    instance_name: str,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> List[Dict]:
    """
    参数:
        instance_name: 实例名称
        status: 会话状态过滤 ("running", "completed", "failed")
        limit: 返回数量限制
        offset: 偏移量（分页）

    返回:
        List[Dict]: 会话基本信息列表
    """
```

#### `search_sessions()`

在会话内容中搜索关键词。

```python
def search_sessions(
    instance_name: str,
    query: str,
    field: str = "both",  # "initial_prompt", "result", "both"
    limit: int = 10
) -> List[Dict]:
    """
    参数:
        instance_name: 实例名称
        query: 搜索关键词
        field: 搜索字段
        limit: 结果数量限制

    返回:
        List[Dict]: 匹配的会话列表
    """
```

### 7.2 自定义查询示例

#### 查询特定时间段的会话

```python
from datetime import datetime

def get_sessions_by_date_range(instance_name: str, start_date: str, end_date: str):
    """获取指定日期范围内的会话"""
    start_dt = datetime.fromisoformat(start_date)
    end_dt = datetime.fromisoformat(end_date)

    sessions = list_sessions(instance_name, limit=1000)

    filtered = []
    for session in sessions:
        session_dt = datetime.fromisoformat(session['start_time'])
        if start_dt <= session_dt <= end_dt:
            filtered.append(session)

    return filtered

# 使用示例
sessions = get_sessions_by_date_range(
    "demo_agent",
    "2025-12-15T00:00:00",
    "2025-12-16T23:59:59"
)
print(f"12月15-16日共有 {len(sessions)} 个会话")
```

#### 导出会话数据

```python
import json
from pathlib import Path

def export_session_to_json(instance_name: str, session_id: str, output_path: str):
    """将会话导出为单个JSON文件"""
    details = get_session_details(
        instance_name=instance_name,
        session_id=session_id,
        include_messages=True
    )

    if details:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(details, f, ensure_ascii=False, indent=2)

        print(f"会话已导出到: {output_file}")
    else:
        print("会话不存在")

# 使用示例
export_session_to_json(
    "demo_agent",
    "20251216T210032_7347_8e02a38f",
    "exports/session_20251216.json"
)
```

## 8. 实用工具脚本

### 8.1 会话查看命令行工具

创建 `scripts/session_viewer.py`:

```python
#!/usr/bin/env python3
"""
Claude Agent System 会话查看工具

使用方法:
    python scripts/session_viewer.py list demo_agent
    python scripts/session_viewer.py view demo_agent 20251216T210032_7347_8e02a38f
    python scripts/session_viewer.py search demo_agent "关键词"
"""

import argparse
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.session.query.session_query import (
    get_session_details,
    list_sessions,
    search_sessions
)

async def main():
    parser = argparse.ArgumentParser(description="会话查看工具")
    subparsers = parser.add_subparsers(dest='command', help='命令')

    # list 命令
    list_parser = subparsers.add_parser('list', help='列出会话')
    list_parser.add_argument('instance', help='实例名称')
    list_parser.add_argument('--status', help='状态过滤',
                           choices=['running', 'completed', 'failed'])
    list_parser.add_argument('--limit', type=int, default=10, help='数量限制')

    # view 命令
    view_parser = subparsers.add_parser('view', help='查看会话详情')
    view_parser.add_argument('instance', help='实例名称')
    view_parser.add_argument('session_id', help='会话ID')
    view_parser.add_argument('--no-messages', action='store_true',
                           help='不显示消息')

    # search 命令
    search_parser = subparsers.add_parser('search', help='搜索会话')
    search_parser.add_argument('instance', help='实例名称')
    search_parser.add_argument('query', help='搜索关键词')
    search_parser.add_argument('--field', default='both',
                             choices=['initial_prompt', 'result', 'both'],
                             help='搜索字段')
    search_parser.add_argument('--limit', type=int, default=10, help='结果限制')

    args = parser.parse_args()

    if args.command == 'list':
        sessions = list_sessions(
            instance_name=args.instance,
            status=args.status,
            limit=args.limit
        )

        print(f"实例 {args.instance} 的会话列表:")
        print("-" * 80)

        for i, session in enumerate(sessions, 1):
            print(f"{i:2d}. {session['session_id']}")
            print(f"    状态: {session['status']}")
            print(f"    时间: {session['start_time']}")
            print()

    elif args.command == 'view':
        details = get_session_details(
            instance_name=args.instance,
            session_id=args.session_id,
            include_messages=not args.no_messages
        )

        if not details:
            print(f"会话 {args.session_id} 不存在")
            return

        # 显示详细信息
        metadata = details['metadata']
        stats = details['statistics']

        print(f"会话ID: {metadata['session_id']}")
        print(f"实例: {metadata['instance_name']}")
        print(f"状态: {metadata['status']}")
        print(f"开始: {metadata['start_time']}")
        print(f"结束: {metadata['end_time']}")
        print(f"时长: {stats.get('total_duration_ms', 0) / 1000:.1f}秒")

        if details.get('messages'):
            print(f"\n消息 ({len(details['messages'])}条):")
            for msg in details['messages'][-10:]:  # 显示最后10条
                print(f"  [{msg['timestamp'][:19]}] {msg['message_type']}")

    elif args.command == 'search':
        results = search_sessions(
            instance_name=args.instance,
            query=args.query,
            field=args.field,
            limit=args.limit
        )

        print(f"搜索结果 ({args.query}):")
        print("-" * 80)

        for i, result in enumerate(results, 1):
            print(f"{i}. {result['session_id']}")
            print(f"   时间: {result['start_time']}")
            print(f"   匹配: {result['matched_content'][:100]}...")
            print()

if __name__ == "__main__":
    asyncio.run(main())
```

### 8.2 会话数据清理工具

创建 `scripts/session_cleaner.py`:

```python
#!/usr/bin/env python3
"""
会话数据清理工具

用于清理过期的会话数据，释放存储空间
"""

import argparse
import asyncio
import shutil
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

def clean_old_sessions(instance_name: str, days: int, dry_run: bool = True):
    """清理超过指定天数的会话"""
    instances_root = Path("instances")
    session_dir = instances_root / instance_name / "sessions"

    if not session_dir.exists():
        print(f"会话目录不存在: {session_dir}")
        return

    cutoff_date = datetime.now() - timedelta(days=days)
    cleaned_count = 0
    cleaned_size = 0

    for session_path in session_dir.iterdir():
        if not session_path.is_dir():
            continue

        # 检查会话时间
        metadata_file = session_path / "metadata.json"
        if metadata_file.exists():
            import json
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
                session_time = datetime.fromisoformat(metadata['start_time'])

                if session_time < cutoff_date:
                    # 计算大小
                    size = sum(f.stat().st_size for f in session_path.rglob('*') if f.is_file())

                    if dry_run:
                        print(f"将要删除: {session_path.name} ({size / 1024 / 1024:.2f} MB)")
                    else:
                        shutil.rmtree(session_path)
                        print(f"已删除: {session_path.name} ({size / 1024 / 1024:.2f} MB)")

                    cleaned_count += 1
                    cleaned_size += size

    action = "将要清理" if dry_run else "已清理"
    print(f"\n{action} {cleaned_count} 个会话，释放 {cleaned_size / 1024 / 1024:.2f} MB 空间")

def main():
    parser = argparse.ArgumentParser(description="会话清理工具")
    parser.add_argument('instance', help='实例名称')
    parser.add_argument('--days', type=int, default=30,
                       help='保留天数（默认30天）')
    parser.add_argument('--dry-run', action='store_true',
                       help='仅显示将要删除的内容，不实际删除')

    args = parser.parse_args()

    print(f"清理实例 {args.instance} 超过 {args.days} 天的会话")
    if args.dry_run:
        print("(DRY RUN - 不会实际删除)")
    print("-" * 50)

    clean_old_sessions(args.instance, args.days, args.dry_run)

if __name__ == "__main__":
    main()
```

## 9. 故障排除

### 9.1 常见问题

#### Q: 找不到会话文件

**症状**: `get_session_details()` 返回 `None`

**解决方案**:
1. 确认实例名称和会话ID正确
2. 检查文件路径: `instances/{instance_name}/sessions/{session_id}/`
3. 确认会话已完成（status为"completed"）

```python
# 调试代码
from pathlib import Path

session_path = Path("instances") / instance_name / "sessions" / session_id
print(f"会话路径: {session_path}")
print(f"目录存在: {session_path.exists()}")
print(f"包含文件: {list(session_path.glob('*')) if session_path.exists() else 'None'}")
```

#### Q: 消息不完整

**症状**: `messages.jsonl` 文件缺少最近的消息

**原因**: 可能是异步写入缓冲区还未刷新

**解决方案**:
1. 等待会话完成
2. 检查是否有 `.backup.jsonl` 文件
3. 手动触发会话清理

```python
# 强制刷新会话（如果会话仍在运行）
from src import AgentSystem

agent = AgentSystem(instance_name)
await agent.initialize()
# 执行一个简单的查询来触发清理
result = await agent.query_text("ping")
agent.cleanup()
```

#### Q: 实时消息订阅失败

**症状**: `subscribe_session_messages()` 抛出异常

**解决方案**:
1. 检查Redis连接配置 (`streaming.yaml`)
2. 确认Redis服务运行
3. 检查网络连接

```python
# 测试Redis连接
import redis
try:
    r = redis.Redis(host='localhost', port=6379, db=0)
    r.ping()
    print("Redis连接正常")
except Exception as e:
    print(f"Redis连接失败: {e}")
```

### 9.2 性能优化

#### 大量会话查询优化

当处理大量会话时，建议：

1. **使用分页**:
```python
# 分页获取所有会话
page_size = 100
page = 0
all_sessions = []

while True:
    sessions = list_sessions(
        instance_name=instance_name,
        limit=page_size,
        offset=page * page_size
    )

    if not sessions:
        break

    all_sessions.extend(sessions)
    page += 1
```

2. **过滤不必要的字段**:
```python
# 只获取基本信息，不包含消息
sessions = list_sessions(instance_name, limit=1000)
```

3. **使用异步并发**:
```python
import asyncio

async def process_multiple_sessions(session_ids):
    tasks = []
    for session_id in session_ids:
        task = asyncio.create_task(
            get_session_details(instance_name, session_id)
        )
        tasks.append(task)

    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results
```

### 9.3 数据迁移

#### 迁移到新的存储位置

```python
import shutil
from pathlib import Path

def migrate_sessions(instance_name: str, new_location: Path):
    """迁移会话数据到新位置"""
    old_path = Path("instances") / instance_name / "sessions"
    new_path = new_location / instance_name / "sessions"

    # 创建新目录
    new_path.mkdir(parents=True, exist_ok=True)

    # 复制数据
    if old_path.exists():
        shutil.copytree(old_path, new_path, dirs_exist_ok=True)
        print(f"会话数据已迁移到: {new_path}")
    else:
        print("源目录不存在")
```

## 总结

本教程详细介绍了 Claude Agent System 的会话记录系统的使用方法，包括：

1. **基础操作**: 列出、查看、搜索会话
2. **高级功能**: 会话树构建、批量分析、实时订阅
3. **编程接口**: 核心API的使用方法和示例
4. **工具脚本**: 命令行工具和数据清理脚本
5. **故障排除**: 常见问题的解决方案

通过这些工具和方法，您可以有效地管理和分析 Claude Agent 的所有对话历史，获取有价值的洞察，并优化系统的性能。

更多详细信息请参考：
- [配置指南](docs/configuration.md)
- [API参考](docs/api-reference.md)
- [会话系统详解](docs/session-system.md)