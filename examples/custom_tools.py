"""
自定义工具示例

演示如何创建和使用自定义工具
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
    print("Claude Agent System - 自定义工具示例")
    print("=" * 60)

    print("\n本示例演示如何创建和使用自定义工具。")
    print("示例实例已经包含了计算器工具（calculator.py）。")

    try:
        # 创建 agent 系统
        print("\n1. 创建 Agent 系统...")
        agent = AgentSystem("example_agent",instances_root='/root/myai/claude_agent_system/instances')

        # 初始化系统
        print("2. 初始化系统...")
        await agent.initialize()

        print(f"\n工具信息:")
        print(f"  - 工具数量: {agent.tools_count}")

        if agent.tool_manager:
            tool_names = agent.tool_manager.get_tool_names()
            print(f"  - 可用工具:")
            for tool_name in tool_names:
                print(f"    * {tool_name}")

        # 示例 1：使用加法工具
        print("\n" + "=" * 60)
        print("示例 1：使用加法工具")
        print("=" * 60)

        response = await agent.query_text("计算 1234 + 5678")
        print(f"\n响应:\n{response}")

        # 示例 2：使用乘法工具
        print("\n" + "=" * 60)
        print("示例 2：使用乘法工具")
        print("=" * 60)

        response = await agent.query_text("计算 99 × 88")
        print(f"\n响应:\n{response}")

        # 示例 3：使用除法工具
        print("\n" + "=" * 60)
        print("示例 3：使用除法工具")
        print("=" * 60)

        response = await agent.query_text("计算 1024 ÷ 16")
        print(f"\n响应:\n{response}")

        # 示例 4：使用幂运算工具
        print("\n" + "=" * 60)
        print("示例 4：使用幂运算工具")
        print("=" * 60)

        response = await agent.query_text("计算 2 的 10 次方")
        print(f"\n响应:\n{response}")

        # 示例 5：组合使用多个工具
        print("\n" + "=" * 60)
        print("示例 5：组合使用多个工具")
        print("=" * 60)

        response = await agent.query_text(
            "先计算 (123 + 456)，然后将结果乘以 2，最后计算结果的平方"
        )
        print(f"\n响应:\n{response}")

        print("\n" + "=" * 60)
        print("如何创建自己的工具")
        print("=" * 60)
        print("""
1. 在 instances/<your_agent>/tools/ 目录下创建 Python 文件
2. 使用 @tool 装饰器定义工具函数：

    from claude_agent_sdk import tool
    from typing import Any, Dict

    @tool(
        name="my_tool",
        description="我的自定义工具",
        input_schema={
            "param1": {
                "type": "string",
                "description": "参数1"
            }
        }
    )
    async def my_tool(args: Dict[str, Any]) -> Dict[str, Any]:
        result = args.get("param1", "")
        return {
            "content": [{
                "type": "text",
                "text": f"处理结果: {result}"
            }]
        }

3. 在 config.yaml 中添加工具权限：

    tools:
      allowed:
        - "mcp__custom_tools__<模块名>__*"

4. 工具会被自动发现和加载！
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
