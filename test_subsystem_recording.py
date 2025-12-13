#!/usr/bin/env python3
"""
测试子系统调用和会话记录功能

这个测试脚本验证：
1. 基础子系统调用功能
2. 会话记录功能（包括父子会话）
3. 调用图生成
4. 查询API的功能
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src import AgentSystem
from src.session_query import (
    get_session_details,
    get_call_graph,
    list_sessions,
    search_sessions,
    export_session
)


async def test_basic_subsystem_call():
    """测试1: 基础子系统调用"""
    print("\n" + "="*60)
    print("测试1: 基础子系统调用")
    print("="*60)

    # 创建demo_agent
    agent = AgentSystem(
        "demo_agent",
        instances_root="C:/Users/Lenovo/Desktop/test2/claudecode/instances"
    )

    try:
        await agent.initialize()
        print(f"✓ Agent初始化成功")
        print(f"  - Agent名称: {agent.agent_name}")
        print(f"  - 工具数量: {agent.tools_count}")
        print(f"  - 子实例数量: {agent.instances_count}")

        # 测试调用子系统
        prompt = """
        请使用file_analyzer子实例，让他回复一下他有哪些可用的工具！
        """

        print(f"\n执行提示词: {prompt}")
        result = await agent.query_text(prompt)

        print(f"\n✓ 查询完成")
        print(f"  会话ID: {result.session_id}")
        print(f"  结果摘要: {result.result[:200]}...")

        return result.session_id

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return None


async def test_session_recording():
    """测试2: 会话记录功能"""
    print("\n" + "="*60)
    print("测试2: 会话记录功能")
    print("="*60)

    agent = AgentSystem(
        "demo_agent",
        instances_root="C:/Users/Lenovo/Desktop/test2/claudecode/instances"
    )

    try:
        await agent.initialize()

        # 创建一个会产生多个子实例调用的任务
        prompt = """
        请执行以下任务：
        1. 使用calculator工具计算 15 * 8 + 32
        2. 使用file_analyzer子实例分析 src/ 目录结构
        3. 使用text_processor工具提取关键词
        4. 使用syntax_checker子实例检查Python代码语法
        """

        print(f"执行复杂任务...")
        result = await agent.query_text(prompt)

        session_id = result.session_id
        print(f"\n✓ 会话记录测试完成")
        print(f"  主会话ID: {session_id}")

        # 查看会话详情
        details = get_session_details(
            "demo_agent",
            session_id,instances_root="C:/Users/Lenovo/Desktop/test2/claudecode/instances"
        )

        print(f"\n📊 会话统计:")
        print(f"  - 状态: {details['metadata']['status']}")
        print(f"  - 轮次: {details['statistics']['num_turns']}")
        print(f"  - 工具使用次数: {details['statistics']['tool_use_count']}")
        print(f"  - 子会话数: {len(details['subsessions'])}")

        # 列出子会话
        if details['subsessions']:
            print(f"\n📁 子会话列表:")
            for sub in details['subsessions']:
                print(f"  - {sub['session_id']} ({sub['instance_name']})")

        return session_id

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return None


async def test_call_graph_generation():
    """测试3: 调用图生成"""
    print("\n" + "="*60)
    print("测试3: 调用图生成")
    print("="*60)

    agent = AgentSystem(
        "demo_agent",
        instances_root="C:/Users/Lenovo/Desktop/test2/claudecode/instances"
    )

    try:
        await agent.initialize()

        # 创建嵌套调用场景
        prompt = """
        请创建一个嵌套的工作流：
        1. 首先使用file_analyzer子实例分析项目结构
        2. 然后让file_analyzer子实例调用syntax_checker来检查它发现的文件
        3. 最后返回综合报告
        """

        result = await agent.query_text(prompt)
        session_id = result.session_id
        print(f"✓ 嵌套调用完成，会话ID: {session_id}")

        # 生成调用关系图
        call_graph = get_call_graph("demo_agent", session_id)

        print(f"\n🌳 调用关系图:")
        print(f"  根会话: {call_graph['root_session_id']}")

        def print_graph_node(node, indent=0):
            prefix = "  " * indent
            print(f"{prefix}├─ {node['session_id']} ({node['instance_name']}, 深度={node['depth']})")
            for child in node.get('children', []):
                print_graph_node(child, indent + 1)

        print_graph_node(call_graph['graph'])

        return session_id

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return None


async def test_session_query_api():
    """测试4: 会话查询API"""
    print("\n" + "="*60)
    print("测试4: 会话查询API")
    print("="*60)

    agent = AgentSystem(
        "demo_agent",
        instances_root="C:/Users/Lenovo/Desktop/test2/claudecode/instances"
    )

    try:
        await agent.initialize()

        # 创建多个会话用于测试查询
        session_ids = []

        for i, task in enumerate([
            "计算数学表达式: 100 * (2 + 3)",
            "分析Python代码文件",
            "处理文本数据"
        ]):
            result = await agent.query_text(f"任务{i+1}: {task}")
            session_ids.append(result.session_id)
            print(f"✓ 创建会话 {i+1}: {result.session_id}")

        # 测试列出会话
        print(f"\n📋 会话列表:")
        sessions = list_sessions("demo_agent", limit=10)
        for session in sessions[:5]:  # 只显示前5个
            print(f"  - {session['session_id']} (状态: {session['status']})")

        # 测试搜索会话
        print(f"\n🔍 搜索包含'计算'的会话:")
        search_results = search_sessions(
            "demo_agent",
            query="计算",
            field="initial_prompt"
        )
        for result in search_results[:3]:
            print(f"  - {result['session_id']}: {result['initial_prompt'][:50]}...")

        # 测试导出功能
        if session_ids:
            test_session_id = session_ids[0]
            print(f"\n💾 导出会话 {test_session_id}:")

            # 导出为JSON
            json_file = f"test_session_{test_session_id}.json"
            export_session(
                "demo_agent",
                test_session_id,
                output_format="json",
                output_file=json_file
            )
            print(f"  ✓ JSON导出完成: {json_file}")

            # 导出为Markdown
            md_file = f"test_session_{test_session_id}.md"
            export_session(
                "demo_agent",
                test_session_id,
                output_format="markdown",
                output_file=md_file
            )
            print(f"  ✓ Markdown导出完成: {md_file}")

        return session_ids

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return []


async def test_resume_conversation():
    """测试5: Resume对话功能"""
    print("\n" + "="*60)
    print("测试5: Resume对话功能")
    print("="*60)

    agent = AgentSystem(
        "demo_agent",
        instances_root="C:/Users/Lenovo/Desktop/test2/claudecode/instances"
    )

    try:
        await agent.initialize()

        # 第一次对话
        print("1️⃣ 第一次对话...")
        result1 = await agent.query_text(
            "请分析这个项目的结构，并给出一个概述"
        )
        session_id = result1.session_id
        print(f"   会话ID: {session_id}")

        # Resume继续对话
        print("\n2️⃣ Resume继续对话...")
        result2 = await agent.query_text(
            "根据刚才的分析，请提出3个改进建议",
            resume_session_id=session_id
        )
        print(f"   结果: {result2.result[:100]}...")

        # 再次Resume
        print("\n3️⃣ 再次Resume...")
        result3 = await agent.query_text(
            "请生成详细的实施计划",
            resume_session_id=session_id
        )
        print(f"   结果: {result3.result[:100]}...")

        # 检查会话记录
        details = get_session_details("demo_agent", session_id)
        print(f"\n📊 最终会话统计:")
        print(f"  - 总消息数: {len(details['messages'])}")
        print(f"  - 轮次: {details['statistics']['num_turns']}")
        print(f"  - 状态: {details['metadata']['status']}")
        print(f"  - 是否被Resume: {'resumed_at' in details['metadata'] and details['metadata']['resumed_at']}")

        return session_id

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return None


async def main():
    """主测试函数"""
    print("\n🚀 开始子系统调用和会话记录测试")
    print(f"⏰ 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 执行所有测试
    test_results = {}
    test_results['session_recording'] = await test_session_recording()

    # 测试3: 调用图生成
    test_results['call_graph'] = await test_call_graph_generation()

    # 测试4: 查询API
    test_results['query_api'] = await test_session_query_api()

    # 测试5: Resume功能
    test_results['resume'] = await test_resume_conversation()

    # 测试总结
    print("\n" + "="*60)
    print("📋 测试总结")
    print("="*60)

    for test_name, session_id in test_results.items():
        if session_id:
            print(f"✅ {test_name}: 成功 (会话ID: {session_id})")
        else:
            print(f"❌ {test_name}: 失败")

    print(f"\n🎉 所有测试完成！")
    print(f"📁 会话记录位置: C:/Users/Lenovo/Desktop/test2/claudecode/instances/demo_agent/sessions/")


if __name__ == "__main__":
    asyncio.run(main())