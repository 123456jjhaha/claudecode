#!/usr/bin/env python3
"""
完整会话记录演示
展示一次真实、详细的长时间对话和完整的会话记录
"""

import asyncio
import sys
import json
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.session_manager import SessionManager, AsyncMessageWriter

class MockClaudeMessage:
    """模拟真实的Claude消息"""
    @staticmethod
    def create_user_message(content):
        return {
            "type": "user",
            "data": {"role": "user", "content": content}
        }

    @staticmethod
    def create_assistant_message(content_blocks):
        class AssistantMessage:
            def __init__(self, content):
                self.content = content
                self.model = "claude-sonnet-4-5"

        return AssistantMessage(content_blocks)

    @staticmethod
    def create_tool_call(tool_name, input_data, result):
        """创建工具调用消息"""
        class ToolUseBlock:
            def __init__(self, name, input_data):
                self.type = "tool_use"
                self.name = name
                self.input = input_data

        class ToolResultBlock:
            def __init__(self, result):
                self.type = "tool_result"
                self.result = result

        return {
            "type": "assistant",
            "content": [
                ToolUseBlock(tool_name, input_data),
                ToolResultBlock(result)
            ]
        }

    @staticmethod
    def create_result_message(duration_ms=5000, num_turns=3, cost=0.05):
        class ResultMessage:
            def __init__(self):
                self.subtype = "success"
                self.duration_ms = duration_ms
                self.num_turns = num_turns
                self.total_cost_usd = cost
                self.usage = {
                    "input_tokens": 850,
                    "output_tokens": 1200
                }
                self.result = "对话完成"

        return ResultMessage()

async def demo_complete_session():
    """演示完整的会话记录"""
    print("🎬 完整会话记录演示\n")

    try:
        # 创建会话管理器
        instances_root = project_root / "instances" / "demo_agent"
        session_manager = SessionManager(instances_root)

        print("1️⃣ 开始复杂技术讨论会话...")

        # 创建会话
        session = await session_manager.create_session(
            initial_prompt="请详细解释微服务架构的优势和挑战，并提供一个实际的设计案例。",
            context={"topic": "software_architecture", "complexity": "advanced"}
        )

        session_id = session.session_id
        print(f"📝 会话ID: {session_id}")

        # 模拟一个真实的多轮技术讨论对话
        conversation_flow = [
            {
                "role": "user",
                "content": "请详细解释微服务架构的优势和挑战，并提供一个实际的设计案例。",
                "description": "用户提出技术问题"
            },
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "微服务架构是一种将应用程序构建为一组小型、独立服务的方法。让我详细为您分析其优势和挑战。\n\n## 微服务架构的优势\n\n### 1. 技术栈灵活性\n- 每个服务可以使用最适合的技术栈\n- 支持渐进式升级和现代化\n- 避免技术锁定风险\n\n### 2. 独立部署和扩展\n- 服务可以独立部署，不影响其他服务\n- 根据负载单独扩展高需求服务\n- 提高整体系统的可靠性和可用性"}
                ],
                "description": "助手开始详细回答"
            },
            {
                "role": "tool_use",
                "tool_name": "calculator__multiply",
                "input": {"a": 100, "b": 5},
                "result": 500,
                "description": "助手使用计算器工具计算系统容量"
            },
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "基于刚才的计算，如果一个微服务需要处理100个请求，每个请求需要5毫秒，那么总处理时间是500毫秒。\n\n### 3. 团队自治和敏捷开发\n- 小团队可以独立开发和维护服务\n- 减少团队间的协调成本\n- 加快开发和部署节奏"}
                ],
                "description": "助手继续解释，结合计算结果"
            },
            {
                "role": "user",
                "content": "很好！现在请具体说明微服务架构面临的主要挑战，特别是服务间通信和数据一致性问题。",
                "description": "用户追问具体挑战"
            },
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "微服务架构确实面临一些重要挑战，让我详细说明：\n\n## 主要挑战\n\n### 1. 服务间通信复杂性\n- **网络延迟**：服务调用通过网络进行，存在延迟\n- **服务发现**：需要动态定位和调用服务\n- **负载均衡**：需要合理分配请求到多个服务实例\n\n### 2. 数据一致性\n- **分布式事务**：跨服务的数据一致性难以保证\n- **最终一致性**：接受短期不一致，保证最终一致\n- **补偿机制**：实现事务补偿和回滚策略"}
                ],
                "description": "助手详细解释挑战"
            },
            {
                "role": "tool_use",
                "tool_name": "calculator__add",
                "input": {"a": 99, "b": 1},
                "result": 100,
                "description": "助手计算一致性百分比"
            },
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "通过计算验证：99% + 1% = 100%，这代表了系统的一致性保障策略。\n\n### 3. 运维复杂性\n- **监控和日志**：需要集中管理分布式系统\n- **配置管理**：动态配置多个服务\n- **故障排查**：分布式环境下的问题定位更复杂"}
                ],
                "description": "助手继续说明运维挑战"
            },
            {
                "role": "user",
                "content": "请提供一个具体的微服务架构设计案例，包括主要的服务划分和它们之间的交互关系。",
                "description": "用户要求具体案例"
            },
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "我来为您提供一个电商平台微服务架构的详细案例：\n\n## 电商平台微服务架构案例\n\n### 核心服务划分\n\n1. **用户服务**\n   - 用户注册、登录、认证\n   - 用户信息管理\n   - 权限控制\n\n2. **产品服务**\n   - 产品信息管理\n   - 库存管理\n   - 产品搜索\n\n3. **订单服务**\n   - 订单创建和管理\n   - 订单状态跟踪\n   - 订单历史查询\n\n4. **支付服务**\n   - 支付处理\n   - 退款管理\n   - 交易记录"}
                ],
                "description": "助手提供详细案例"
            }
        ]

        print(f"\n📞 模拟 {len(conversation_flow)} 轮对话...")

        # 记录每个对话轮次
        for i, turn in enumerate(conversation_flow, 1):
            print(f"  轮次 {i}: {turn['description']}")

            if turn["role"] == "user":
                # 记录用户消息
                user_msg = MockClaudeMessage.create_user_message(turn["content"])
                await session.record_message(user_msg)

            elif turn["role"] == "assistant":
                # 记录助手消息
                assistant_msg = MockClaudeMessage.create_assistant_message(turn["content"])
                await session.record_message(assistant_msg)

            elif turn["role"] == "tool_use":
                # 记录工具调用
                tool_msg = MockClaudeMessage.create_tool_call(
                    turn["tool_name"],
                    turn["input"],
                    turn["result"]
                )
                await session.record_message(tool_msg)

            # 模拟对话间隔
            await asyncio.sleep(0.1)

        # 完成会话
        print(f"\n✅ 完成会话记录...")
        result_message = MockClaudeMessage.create_result_message(
            duration_ms=15000,  # 15秒的对话
            num_turns=len([t for t in conversation_flow if t["role"] == "user"]),
            cost=0.08
        )
        await session.finalize(result_message=result_message)

        # 分析会话结果
        print(f"\n📊 会话分析结果:")

        # 获取会话详情
        from src.session_query import get_session_details
        details = get_session_details("demo_agent", session_id, project_root / "instances")

        metadata = details['metadata']
        statistics = details['statistics']

        print(f"  📅 开始时间: {metadata['start_time']}")
        print(f"  📅 结束时间: {metadata['end_time']}")
        print(f"  ✅ 状态: {metadata['status']}")
        print(f"  📝 初始提示: {metadata['initial_prompt'][:50]}...")

        print(f"\n📈 统计信息:")
        print(f"  💬 总消息数: {statistics['num_messages']}")
        print(f"  🔧 工具调用次数: {statistics['num_tool_calls']}")
        print(f"  🕐 会话时长: {statistics.get('total_duration_ms', 0)} ms")
        print(f"  💰 成本: ${statistics.get('cost_usd', 0):.4f}")

        if statistics['tools_used']:
            print(f"  🔧 使用的工具: {list(statistics['tools_used'].keys())}")

        if statistics.get('token_usage'):
            usage = statistics['token_usage']
            print(f"  🪙 Token使用: 输入 {usage.get('input_tokens', 0)}, 输出 {usage.get('output_tokens', 0)}")

        print(f"\n📁 会话文件位置:")
        session_path = session.session_dir
        print(f"  📂 目录: {session_path}")

        # 检查生成的文件
        files = ["metadata.json", "messages.jsonl", "statistics.json"]
        for filename in files:
            file_path = session_path / filename
            if file_path.exists():
                size = file_path.stat().st_size
                print(f"  📄 {filename}: {size} 字节")

                # 显示部分内容
                if filename == "messages.jsonl":
                    with open(file_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        print(f"    包含 {len(lines)} 条消息记录")

                        # 显示前3条消息的类型
                        for i, line in enumerate(lines[:3], 1):
                            try:
                                msg_data = json.loads(line)
                                msg_type = msg_data.get('message_type', 'unknown')
                                timestamp = msg_data.get('timestamp', 'N/A')
                                print(f"    消息 {i}: {msg_type} at {timestamp}")
                            except:
                                print(f"    消息 {i}: [解析错误]")

        # 导出会话
        print(f"\n📤 导出会话记录...")

        from src.session_query import export_session

        # 导出JSON格式
        json_file = project_root / f"demo_session_{session_id}.json"
        export_session(
            "demo_agent",
            session_id,
            output_format="json",
            output_file=json_file,
            instances_root=project_root / "instances"
        )
        print(f"  📄 JSON导出: {json_file}")

        # 导出Markdown格式
        md_file = project_root / f"demo_session_{session_id}.md"
        export_session(
            "demo_agent",
            session_id,
            output_format="markdown",
            output_file=md_file,
            instances_root=project_root / "instances"
        )
        print(f"  📄 Markdown导出: {md_file}")

        # 展示部分导出内容
        if md_file.exists():
            print(f"\n📖 Markdown导出预览:")
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()
                preview = content[:800] + "..." if len(content) > 800 else content
                print(preview)

        print(f"\n🎉 完整会话记录演示完成！")
        print(f"💡 这展示了一个真实的多轮技术对话的完整记录过程")

    except Exception as e:
        print(f"❌ 演示过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(demo_complete_session())