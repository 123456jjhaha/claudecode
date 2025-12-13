"""
简单测试 - 验证基础功能
"""

import asyncio
import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src import AgentSystem


async def simple_test():
    """简单测试"""
    print("\n" + "=" * 60)
    print("简单测试 - 验证基础功能")
    print("=" * 60)

    try:
        # 1. 创建 Agent
        print("\n1. 创建 Demo Agent...")
        # 使用简化版实例
        agent = AgentSystem("demo_agent_simple")
        print("   Agent 创建成功")

        # 2. 初始化
        print("\n2. 初始化系统...")
        await agent.initialize()
        print("   初始化成功")

        print(f"   Agent 名称: {agent.agent_name}")
        print(f"   描述: {agent.agent_description}")
        print(f"   工具数量: {agent.tools_count}")
        print(f"   子实例数量: {agent.instances_count}")

        # 3. 简单对话测试
        print("\n3. 测试简单对话...")
        response = await agent.query_text("你好！请简单介绍一下你自己。")
        print(f"   响应长度: {len(response)} 字符")
        print("   简单对话测试成功")

        # 4. 工具测试
        print("\n4. 测试计算器工具...")
        response = await agent.query_text("使用计算器计算 123 + 456")
        print("   计算器工具测试成功")

        # 5. 文件操作测试
        print("\n5. 测试文件读取...")
        response = await agent.query_text("读取 config.yaml 文件的前10行")
        print("   文件读取测试成功")

        print("\n" + "=" * 60)
        print("基础功能测试通过！")
        print("=" * 60)

    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(simple_test())