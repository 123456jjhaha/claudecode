"""
并行执行示例

演示 Claude 如何自然地并行调用多个子 Claude 实例工具

关键概念：
- 不需要手动实现并行逻辑
- 当 Claude 决定同时使用多个工具时，SDK 会自动并行执行
- 子实例工具和普通工具一样，都是通过 MCP 提供给 Claude

注意：此示例需要配置子实例才能运行。
请在 instances/example_agent/config.yaml 中配置 sub_claude_instances。
"""

import asyncio
import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src import AgentSystem, set_log_level
import logging


async def main():
    # 设置日志级别
    set_log_level(logging.INFO)

    print("=" * 60)
    print("Claude Agent System - 并行执行示例")
    print("=" * 60)

    try:
        # 创建 agent 系统
        print("\n1. 创建 Agent 系统...")
        agent = AgentSystem("example_agent")

        # 初始化系统
        print("2. 初始化系统...")
        await agent.initialize()

        # 检查是否有子实例
        if agent.instances_count == 0:
            print("\n提示：当前没有配置子实例。")
            print("要使用并行执行功能，请按照以下步骤操作：")
            print()
            print("1. 创建子实例目录:")
            print("   - instances/code_reviewer_agent/")
            print("   - instances/document_writer_agent/")
            print()
            print("2. 配置子实例的 config.yaml 和 .claude/CLAUDE.md")
            print()
            print("3. 在 instances/example_agent/config.yaml 中添加：")
            print("   sub_claude_instances:")
            print("     code_reviewer: 'code_reviewer_agent'")
            print("     document_writer: 'document_writer_agent'")
            print()
            print("4. 在 tools.allowed 中添加：")
            print("   - 'mcp__sub_instances__sub_claude_*'")
            print()
            return

        print(f"\n子实例数量: {agent.instances_count}")

        # 列出可用的子实例
        print("\n可用的子实例工具:")
        if agent.instance_manager:
            for instance_name in agent.instance_manager.instances.keys():
                print(f"  - mcp__sub_instances__sub_claude_{instance_name}")

        # 示例 1：让 Claude 自然地调用多个子实例
        print("\n" + "=" * 60)
        print("示例 1：Claude 自然并行调用子实例")
        print("=" * 60)
        print("\n当我们给 Claude 一个需要多个子实例的任务时，")
        print("Claude 会自动决定如何并行调用这些工具。\n")

        # 构建一个需要多个子实例的提示词
        prompt = """
请使用可用的子 Claude 实例工具来完成以下任务：

1. 如果有 code_reviewer 实例，让它分析一段代码的质量
2. 如果有 document_writer 实例，让它生成一份技术文档

你可以同时调用多个子实例工具。请告诉我每个子实例的响应。
        """

        print("执行查询（流式输出）：")
        print("-" * 60)
        async for message in agent.query(prompt):
            if hasattr(message, "text"):
                print(message.text, end="", flush=True)
        print("\n" + "-" * 60)

        # 示例 2：显式要求并行执行
        print("\n" + "=" * 60)
        print("示例 2：显式要求并行执行")
        print("=" * 60)
        print("\n我们可以明确告诉 Claude 同时使用多个工具。\n")

        prompt2 = """
请同时调用所有可用的子 Claude 实例，让每个实例介绍自己的能力。
        """

        print("执行查询（流式输出）：")
        print("-" * 60)
        result = await agent.query_text(prompt2)
        print(result)
        print("-" * 60)

        print("\n" + "=" * 60)
        print("关键要点：")
        print("=" * 60)
        print("""
1. 子实例工具就像普通工具一样被 Claude 使用
2. Claude SDK 会自动处理并行执行
3. 我们不需要手动实现 execute_parallel 函数
4. 并行执行完全由 Claude 的决策和 SDK 的实现处理
5. 这使得系统更简单、更灵活
        """)

        print("=" * 60)
        print("示例完成！")
        print("=" * 60)

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
