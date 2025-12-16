"""
简单的Demo Agent测试
"""

import asyncio
import sys
import os

# 添加src到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src import AgentSystem


async def main():
    print("=" * 50)
    print("Demo Agent 测试")
    print("=" * 50)

    agent = AgentSystem("instances/demo_agent")
    await agent.initialize()

    print(f"Agent名称: {agent.agent_name}")
    print(f"工具数量: {agent.tools_count}")
    print(f"子实例数量: {agent.sub_instances_count}")

    # 测试计算器工具
    print("\n1. 测试计算器工具")
    result = await agent.query_text("使用计算器计算: 123 + 456")
    print(f"结果: {result.result[:200]}...")

    # 测试子实例
    print("\n2. 测试子实例调用")
    result2 = await agent.query_text(
        "使用file_analyzer子实例分析 instances/demo_agent/config.yaml 文件"
    )
    print(f"结果: {result2.result[:200]}...")

    print("\n测试完成！")
    agent.cleanup()


if __name__ == "__main__":
    asyncio.run(main())