#!/usr/bin/env python3
"""
真实会话测试
展示一次完整的长时间对话过程和会话记录结果
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.agent_system import AgentSystem
from src.session_query import get_session_details, export_session

async def test_real_conversation():
    """测试真实对话过程"""
    print("🚀 开始真实会话测试\n")

    try:
        # 初始化 Agent
        print("1️⃣ 初始化智能体...")
        agent = AgentSystem("example_agent")  # 使用已有的配置好的实例
        await agent.initialize()
        print("✅ 智能体初始化成功")

        # 执行一个复杂的、多轮对话
        print("\n2️⃣ 开始复杂对话...")
        conversation_prompts = [
            "你好！请详细解释一下机器学习的基本概念，包括监督学习、无监督学习和强化学习的主要区别。",
            "很好，现在请具体说明监督学习的典型应用场景，并给出一个简单的例子。",
            "请使用计算器工具帮我计算一下：如果有1000个训练样本，每个样本有10个特征，那么总共有多少个特征值需要处理？",
            "基于我们刚才的讨论，请总结一下机器学习的核心要点，并给出学习建议。"
        ]

        session_id = None
        conversation_log = []

        for i, prompt in enumerate(conversation_prompts, 1):
            print(f"\n--- 对话轮次 {i} ---")
            print(f"用户: {prompt}")

            response_text = ""
            message_count = 0

            try:
                # 使用 query_text 获取完整响应
                response_text = await agent.query_text(prompt, record_session=True)

                # 获取当前会话ID
                if i == 1:
                    session_id = agent.current_session_id
                    print(f"📝 会话ID: {session_id}")

                # 显示响应（截取前200字符）
                response_preview = response_text[:200] + "..." if len(response_text) > 200 else response_text
                print(f"助手: {response_preview}")

                conversation_log.append({
                    "round": i,
                    "prompt": prompt,
                    "response_length": len(response_text),
                    "session_id": session_id
                })

                print(f"✅ 第{i}轮对话完成，响应长度: {len(response_text)} 字符")

            except Exception as e:
                print(f"❌ 第{i}轮对话失败: {e}")
                break

            # 添加短暂延迟，避免过快请求
            await asyncio.sleep(1)

        # 展示会话记录结果
        if session_id:
            print(f"\n3️⃣ 分析会话记录结果...")
            print(f"📂 会话ID: {session_id}")

            try:
                # 获取详细会话信息
                session_details = get_session_details("example_agent", session_id, project_root / "instances")

                print(f"\n📊 会话统计信息:")
                metadata = session_details['metadata']
                statistics = session_details['statistics']

                print(f"   - 实例名: {metadata['instance_name']}")
                print(f"   - 开始时间: {metadata['start_time']}")
                print(f"   - 结束时间: {metadata.get('end_time', 'N/A')}")
                print(f"   - 状态: {metadata['status']}")
                print(f"   - 总消息数: {statistics['num_messages']}")
                print(f"   - 会话时长: {statistics.get('session_duration_ms', 0)} ms")
                print(f"   - 工具调用次数: {statistics['num_tool_calls']}")

                if statistics['tools_used']:
                    print(f"   - 使用的工具: {list(statistics['tools_used'].keys())}")

                print(f"\n📝 对话轮次总结:")
                for entry in conversation_log:
                    print(f"   - 轮次 {entry['round']}: {entry['response_length']} 字符响应")

                # 导出会话记录
                print(f"\n4️⃣ 导出会话记录...")

                # 导出为JSON
                json_file = project_root / f"conversation_{session_id}.json"
                export_session(
                    "example_agent",
                    session_id,
                    output_format="json",
                    output_file=json_file,
                    instances_root=project_root / "instances"
                )

                # 导出为Markdown
                md_file = project_root / f"conversation_{session_id}.md"
                export_session(
                    "example_agent",
                    session_id,
                    output_format="markdown",
                    output_file=md_file,
                    instances_root=project_root / "instances"
                )

                print(f"✅ JSON导出: {json_file}")
                print(f"✅ Markdown导出: {md_file}")

                # 显示文件内容预览
                print(f"\n5️⃣ 文件内容预览...")

                if json_file.exists():
                    print(f"\n📄 JSON文件大小: {json_file.stat().st_size} 字节")

                if md_file.exists():
                    print(f"\n📄 Markdown文件预览 (前500字符):")
                    with open(md_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        preview = content[:500] + "..." if len(content) > 500 else content
                        print(preview)

                print(f"\n🎉 真实会话测试完成！")
                print(f"📁 会话文件位置: instances/example_agent/sessions/{session_id}/")
                print(f"📁 导出文件: {json_file.name}, {md_file.name}")

            except Exception as e:
                print(f"❌ 分析会话记录失败: {e}")

    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_real_conversation())