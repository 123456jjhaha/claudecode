"""
测试配置加载
"""
import asyncio
from pathlib import Path
from src.agent_system import AgentSystem


async def main():
    agent = AgentSystem(
        instance_name="example_agent",
        instances_root=Path("instances")
    )

    await agent.initialize()

    print("=" * 60)
    print("配置检查")
    print("=" * 60)

    # 检查配置
    config = agent.config
    print(f"\n配置文件中的 allowed 工具:")
    print(config.get("tools", {}).get("allowed", []))

    # 检查 ClaudeAgentOptions
    print(f"\nClaudeAgentOptions.allowed_tools:")
    print(agent.options.allowed_tools)

    print(f"\nClaudeAgentOptions.disallowed_tools:")
    print(agent.options.disallowed_tools)


if __name__ == "__main__":
    asyncio.run(main())
