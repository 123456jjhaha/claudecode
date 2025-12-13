"""
Resume 功能测试

测试多轮对话的 resume 功能，验证：
1. 第一次对话正常创建会话
2. Resume 模式能正确继续对话
3. 消息追加到 messages.jsonl
4. seq 序列号连续
5. 统计信息正确覆盖
6. Claude session_id 正确保存和使用
"""

import asyncio
import sys
import json
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src import AgentSystem, set_log_level
from src.session_query import get_session_details
import logging


async def test_resume():
    """测试 Resume 功能"""

    # 设置日志级别
    set_log_level(logging.INFO)

    print("=" * 80)
    print("Resume 功能测试")
    print("=" * 80)

    try:
        # 创建 agent 系统
        print("\n📌 步骤 1: 创建并初始化 Agent 系统...")
        agent = AgentSystem("demo_agent", instances_root="C:/Users/Lenovo/Desktop/test2/claudecode/instances")
        await agent.initialize()

        print(f"   ✓ Agent: {agent.agent_name}")
        print(f"   ✓ 工具数量: {agent.tools_count}")

        # ===== 第一次对话 =====
        print("\n" + "=" * 80)
        print("📌 步骤 2: 第一次对话")
        print("=" * 80)

        print("\n提示词: '请记住这个数字：42。然后告诉我你记住了什么。'")
        response1 = await agent.query_text("请记住这个数字：42。然后告诉我你记住了什么。")

        print(f"\n响应:\n{response1.result}")

        # 保存会话 ID
        session_id = response1.session_id
        print(f"\n✓ 会话 ID: {session_id}")

        # 查看会话详情
        print("\n--- 会话详情 ---")
        details1 = get_session_details("demo_agent", session_id, instances_root="C:/Users/Lenovo/Desktop/test2/claudecode/instances")
        print(f"状态: {details1['metadata']['status']}")
        print(f"消息数: {details1['statistics']['num_messages']}")
        print(f"轮次: {details1['statistics']['num_turns']}")
        if details1['statistics'].get('cost_usd'):
            print(f"成本: ${details1['statistics']['cost_usd']:.6f}")

        # 检查 Claude session_id
        claude_session_id = details1['metadata'].get('claude_session_id')
        print(f"Claude Session ID: {claude_session_id}")
        if not claude_session_id:
            print("⚠️  警告: Claude session_id 未保存！")

        # 查看消息文件
        messages_file = Path(f"instances/demo_agent/sessions/{session_id}/messages.jsonl")
        if messages_file.exists():
            with open(messages_file, 'r', encoding='utf-8') as f:
                first_messages = f.readlines()
            print(f"消息文件行数: {len(first_messages)}")
            print(f"最后一条消息 seq: {json.loads(first_messages[-1])['seq']}")

        # ===== Resume 第一次 =====
        print("\n" + "=" * 80)
        print("📌 步骤 3: Resume - 继续对话（第一次）")
        print("=" * 80)

        print(f"\n使用 session_id: {session_id}")
        print("提示词: '刚才我让你记住的数字是多少？请回答。'")

        response2 = await agent.query_text(
            "刚才我让你记住的数字是多少？请回答。",
            resume_session_id=session_id
        )

        print(f"\n响应:\n{response2.result}")

        # 验证是否记住了上下文
        if "42" in response2.result:
            print("\n✅ 成功：AI 记住了之前的数字 42！")
        else:
            print("\n❌ 失败：AI 没有记住之前的数字")

        # 查看更新后的会话详情
        print("\n--- Resume 后的会话详情 ---")
        details2 = get_session_details("demo_agent", session_id, instances_root="C:/Users/Lenovo/Desktop/test2/claudecode/instances")
        print(f"状态: {details2['metadata']['status']}")
        print(f"消息数: {details2['statistics']['num_messages']}")
        print(f"轮次: {details2['statistics']['num_turns']}")
        if details2['statistics'].get('cost_usd'):
            print(f"成本: ${details2['statistics']['cost_usd']:.6f}")

        # 检查是否有 resumed_at 时间戳
        if 'resumed_at' in details2['metadata']:
            print(f"Resume 时间: {details2['metadata']['resumed_at']}")

        # 验证消息追加
        if messages_file.exists():
            with open(messages_file, 'r', encoding='utf-8') as f:
                second_messages = f.readlines()
            print(f"\n消息文件行数: {len(second_messages)} (之前: {len(first_messages)})")
            print(f"新增消息: {len(second_messages) - len(first_messages)} 条")

            # 检查 seq 是否连续
            seqs = [json.loads(line)['seq'] for line in second_messages]
            is_continuous = seqs == list(range(len(seqs)))
            if is_continuous:
                print("✅ seq 序列号连续")
            else:
                print(f"❌ seq 序列号不连续: {seqs}")

        # ===== Resume 第二次 =====
        print("\n" + "=" * 80)
        print("📌 步骤 4: Resume - 继续对话（第二次）")
        print("=" * 80)

        print(f"\n使用 session_id: {session_id}")
        print("提示词: '如果把刚才的数字乘以 2，结果是多少？'")

        response3 = await agent.query_text(
            "如果把刚才的数字乘以 2，结果是多少？",
            resume_session_id=session_id
        )

        print(f"\n响应:\n{response3.result}")

        # 验证计算结果
        if "84" in response3.result:
            print("\n✅ 成功：AI 正确计算了 42 × 2 = 84！")
        else:
            print("\n⚠️  注意：AI 的回答中没有出现 84")

        # 最终会话详情
        print("\n--- 最终会话详情 ---")
        details3 = get_session_details("demo_agent", session_id, instances_root="C:/Users/Lenovo/Desktop/test2/claudecode/instances")
        print(f"状态: {details3['metadata']['status']}")
        print(f"消息数: {details3['statistics']['num_messages']}")
        print(f"轮次: {details3['statistics']['num_turns']}")
        if details3['statistics'].get('cost_usd'):
            print(f"总成本: ${details3['statistics']['cost_usd']:.6f}")

        # 最终消息统计
        if messages_file.exists():
            with open(messages_file, 'r', encoding='utf-8') as f:
                final_messages = f.readlines()
            print(f"\n最终消息文件行数: {len(final_messages)}")
            print(f"总新增消息: {len(final_messages) - len(first_messages)} 条")

        # ===== 总结 =====
        print("\n" + "=" * 80)
        print("📊 测试总结")
        print("=" * 80)

        print(f"\n✓ 完成了 3 次对话（1 次新建 + 2 次 Resume）")
        print(f"✓ Session ID: {session_id}")
        print(f"✓ Claude Session ID: {claude_session_id}")
        print(f"✓ 总消息数: {details3['statistics']['num_messages']}")
        print(f"✓ 总轮次: {details3['statistics']['num_turns']}")

        # 验证点
        print("\n🔍 验证点:")
        checks = []

        # 1. Claude session_id 保存
        if claude_session_id:
            checks.append("✅ Claude session_id 已保存")
        else:
            checks.append("❌ Claude session_id 未保存")

        # 2. 消息追加
        if len(final_messages) > len(first_messages):
            checks.append("✅ 消息成功追加")
        else:
            checks.append("❌ 消息未追加")

        # 3. seq 连续
        if is_continuous:
            checks.append("✅ seq 序列号连续")
        else:
            checks.append("❌ seq 序列号不连续")

        # 4. 上下文记忆
        if "42" in response2.result:
            checks.append("✅ AI 记住了上下文（数字 42）")
        else:
            checks.append("❌ AI 未记住上下文")

        # 5. resumed_at 时间戳
        if 'resumed_at' in details3['metadata']:
            checks.append("✅ resumed_at 时间戳已记录")
        else:
            checks.append("❌ resumed_at 时间戳未记录")

        for check in checks:
            print(f"   {check}")

        # 成功/失败判断
        success_count = sum(1 for c in checks if c.startswith("✅"))
        total_count = len(checks)

        print(f"\n通过率: {success_count}/{total_count} ({success_count/total_count*100:.0f}%)")

        if success_count == total_count:
            print("\n🎉 所有测试通过！Resume 功能正常工作！")
        else:
            print(f"\n⚠️  {total_count - success_count} 个测试失败，请检查")

        # 显示会话文件位置
        print(f"\n📁 会话文件位置:")
        print(f"   instances/demo_agent/sessions/{session_id}/")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_resume())
