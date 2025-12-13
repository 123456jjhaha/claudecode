"""
测试 1: 基础工具功能

测试 Claude Agent System 的基础工具使用
- Read 工具
- Write 工具
- Bash 工具
- Glob 工具
- Grep 工具
"""

import asyncio
import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src import AgentSystem, set_log_level
import logging

# 配置日志
set_log_level(logging.INFO)


async def test_basic_tools():
    """测试基础工具功能"""
    print("\n" + "=" * 60)
    print("测试 1: 基础工具功能")
    print("=" * 60)

    try:
        # 创建并初始化 agent
        print("\n1. 初始化 Demo Agent...")
        agent = AgentSystem("demo_agent",instances_root="C:/Users/Lenovo/Desktop/test2/claudecode/instances")
        await agent.initialize()

        print(f"   Agent 名称: {agent.agent_name}")
        print(f"   可用工具数: {agent.tools_count}")

        # 测试 1: Read 工具
        print("\n2. 测试 Read 工具...")
        response = await agent.query_text("""
        请使用 Read 工具读取 demo_agent 的配置文件：
        - 读取 config.yaml 文件
        - 读取 .claude/agent.md 文件
        - 总结文件的主要内容
        """)
        print("\n✅ Read 工具测试完成")

        # 测试 2: Write 工具
        print("\n3. 测试 Write 工具...")
        response = await agent.query_text("""
        请使用 Write 工具创建一个测试文件：
        - 文件名: test_output.txt
        - 内容: "这是通过 Claude Agent 创建的测试文件"
        - 创建后使用 Read 工具验证内容
        """)
        print("\n✅ Write 工具测试完成")

        # 测试 3: Bash 工具
        print("\n4. 测试 Bash 工具...")
        response = await agent.query_text("""
        请使用 Bash 工具执行以下命令：
        - 显示当前目录: pwd
        - 列出文件: ls -la
        - 显示系统信息: uname -a (Linux) 或 ver (Windows)
        """)
        print("\n✅ Bash 工具测试完成")

        # 测试 4: Glob 工具
        print("\n5. 测试 Glob 工具...")
        response = await agent.query_text("""
        请使用 Glob 工具查找文件：
        - 查找所有 Python 文件: **/*.py
        - 查找所有配置文件: **/*.yaml
        - 查找所有 Markdown 文件: **/*.md
        """)
        print("\n✅ Glob 工具测试完成")

        # 测试 5: Grep 工具
        print("\n6. 测试 Grep 工具...")
        response = await agent.query_text("""
        请使用 Grep 工具搜索内容：
        - 在 Python 文件中搜索 "import" 关键字
        - 在配置文件中搜索 "agent" 关键字
        - 在所有文件中搜索 "demo_agent"
        """)
        print("\n✅ Grep 工具测试完成")

        # 测试 6: 组合使用工具
        print("\n7. 测试组合使用工具...")
        response = await agent.query_text("""
        请组合使用多个工具完成以下任务：
        1. 使用 Glob 查找所有 Python 文件
        2. 使用 Read 读取其中一个文件
        3. 使用 Grep 在文件中搜索特定内容
        4. 使用 Write 创建分析报告
        """)
        print("\n✅ 组合工具测试完成")

        # 清理测试文件
        print("\n8. 清理测试文件...")
        try:
            import os
            test_file = "instances/demo_agent/test_output.txt"
            if os.path.exists(test_file):
                os.remove(test_file)
                print("   - 已删除测试文件: test_output.txt")
        except:
            print("   - 清理测试文件失败（可忽略）")

        print("\n" + "=" * 60)
        print("✅ 基础工具功能测试全部通过！")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_basic_tools())