"""
基础使用示例

演示如何使用 AgentSystem 执行基本查询
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
    print("Claude Agent System - 基础使用示例")
    print("=" * 60)

    try:
        # 创建 agent 系统
        print("\n1. 创建 Agent 系统...")
        agent = AgentSystem("example_agent",instances_root='/root/myai/claude_agent_system/instances')

        # 初始化系统
        print("2. 初始化系统...")
        await agent.initialize()

        print(f"\nAgent 信息:")
        print(f"  - 名称: {agent.agent_name}")
        print(f"  - 描述: {agent.agent_description}")
        print(f"  - 工具数量: {agent.tools_count}")
        print(f"  - 子实例数量: {agent.instances_count}")

        # 示例 1：简单查询
        print("\n" + "=" * 60)
        print("示例 1：简单查询")
        print("=" * 60)

        response = await agent.query_text("你好！请介绍一下你自己。")
        print(f"\n响应:\n{response}")

        # 示例 2：使用计算器工具
        print("\n" + "=" * 60)
        print("示例 2：使用计算器工具")
        print("=" * 60)

        response = await agent.query_text("使用计算器计算 123 + 456")
        print(f"\n响应:\n{response}")

        # 示例 3：流式响应
        print("\n" + "=" * 60)
        print("示例 3：流式响应")
        print("=" * 60)

        print("\n响应:")
        async for message in agent.query("计算 100 的平方根，然后计算结果的平方"):
            if hasattr(message, "text"):
                print(message.text, end="", flush=True)
        print()  # 换行

        print("\n" + "=" * 60)
        print("示例完成！")
        print("=" * 60)

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
