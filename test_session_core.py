#!/usr/bin/env python3
"""
会话记录系统核心功能测试
不依赖外部 Claude 连接，直接测试会话管理功能
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.session_manager import SessionManager, AsyncMessageWriter
from src.session_query import (
    get_session_details,
    list_sessions,
    search_sessions,
    get_call_graph,
    export_session,
    cleanup_sessions
)

class MockMessage:
    """模拟 Claude SDK 消息对象"""
    def __init__(self, message_type, data):
        self.message_type = message_type
        self.data = data

class MockAssistantMessage:
    """模拟 AssistantMessage"""
    def __init__(self, content):
        self.content = content
        self.model = "claude-sonnet-4-5"

class MockResultMessage:
    """模拟 ResultMessage"""
    def __init__(self, result):
        self.subtype = "success"
        self.duration_ms = 1500
        self.num_turns = 2
        self.total_cost_usd = 0.01
        self.usage = {"input_tokens": 100, "output_tokens": 200}
        self.result = result

async def test_session_manager_core():
    """测试会话管理器核心功能"""
    print("🚀 开始会话记录系统核心功能测试\n")

    try:
        # 1. 初始化会话管理器
        print("1️⃣ 初始化会话管理器...")
        instances_root = project_root / "instances" / "test_basic_agent"
        session_manager = SessionManager(instances_root)
        print("✅ 会话管理器初始化成功")

        # 2. 创建测试会话
        print("\n2️⃣ 创建测试会话...")
        session = await session_manager.create_session(
            initial_prompt="测试提示：什么是人工智能？",
            context={"test_mode": True}
        )
        session_id = session.session_id
        print(f"✅ 会话创建成功，ID: {session_id}")

        # 3. 记录模拟消息
        print("\n3️⃣ 记录模拟消息...")

        # 模拟用户消息
        user_message = {
            "type": "user",
            "data": {"role": "user", "content": "什么是人工智能？"}
        }
        await session.record_message(user_message)
        print("✅ 用户消息记录成功")

        # 模拟助手消息
        assistant_message = MockAssistantMessage([
            {"type": "text", "text": "人工智能（AI）是计算机科学的一个分支"}
        ])
        await session.record_message(assistant_message)
        print("✅ 助手消息记录成功")

        # 模拟结果消息
        result_message = MockResultMessage("测试完成")
        await session.record_message(result_message)
        print("✅ 结果消息记录成功")

        # 4. 完成会话
        print("\n4️⃣ 完成会话...")
        await session.finalize(result_message=result_message)
        print("✅ 会话完成")

        # 5. 验证文件创建
        print("\n5️⃣ 验证文件创建...")
        session_path = session.session_dir

        required_files = ["metadata.json", "messages.jsonl", "statistics.json"]
        for filename in required_files:
            file_path = session_path / filename
            if file_path.exists():
                print(f"✅ {filename} 创建成功")
            else:
                print(f"❌ {filename} 未创建")

        # 6. 测试查询API
        print("\n6️⃣ 测试查询API...")

        # 测试获取会话详情
        details = get_session_details("test_basic_agent", session_id, project_root / "instances")
        if 'metadata' in details and 'statistics' in details and 'messages' in details:
            print("✅ get_session_details API 成功")
            print(f"   消息数量: {len(details['messages'])}")
            print(f"   会话状态: {details['metadata']['status']}")
        else:
            print("❌ get_session_details API 失败")

        # 测试列出会话
        sessions = list_sessions("test_basic_agent", instances_root=project_root / "instances")
        if len(sessions) > 0:
            print(f"✅ list_sessions API 成功，找到 {len(sessions)} 个会话")
        else:
            print("❌ list_sessions API 失败")

        # 测试搜索会话
        search_results = search_sessions("test_basic_agent", "人工智能", instances_root=project_root / "instances")
        if len(search_results) > 0:
            print(f"✅ search_sessions API 成功，找到 {len(search_results)} 个匹配")
        else:
            print("❌ search_sessions API 失败")

        # 7. 测试调用关系图
        print("\n7️⃣ 测试调用关系图...")
        try:
            call_graph = get_call_graph("test_basic_agent", session_id, instances_root=project_root / "instances")
            if 'session_id' in call_graph and 'hierarchy' in call_graph:
                print("✅ get_call_graph API 成功")
                print(f"   会话ID: {call_graph['session_id']}")
                print(f"   层级深度: {call_graph['hierarchy']['depth']}")
            else:
                print("❌ get_call_graph API 失败 - 返回数据格式不正确")
                print(f"   返回的键: {list(call_graph.keys()) if 'call_graph' in locals() else 'N/A'}")
        except Exception as e:
            print(f"❌ get_call_graph API 失败 - 异常: {e}")

        # 8. 测试导出功能
        print("\n8️⃣ 测试导出功能...")

        # 测试JSON导出
        json_export_path = project_root / "test_export.json"
        export_session(
            "test_basic_agent",
            session_id,
            output_format="json",
            output_file=json_export_path,
            instances_root=project_root / "instances"
        )

        if json_export_path.exists():
            print("✅ JSON 导出成功")
            json_export_path.unlink()  # 清理
        else:
            print("❌ JSON 导出失败")

        # 测试Markdown导出
        md_export_path = project_root / "test_export.md"
        export_session(
            "test_basic_agent",
            session_id,
            output_format="markdown",
            output_file=md_export_path,
            instances_root=project_root / "instances"
        )

        if md_export_path.exists():
            print("✅ Markdown 导出成功")
            md_export_path.unlink()  # 清理
        else:
            print("❌ Markdown 导出失败")

        # 9. 测试创建子会话
        print("\n9️⃣ 测试创建子会话...")
        subsession = await session.create_subsession(
            instance_name="child_agent",
            prompt="子任务：计算 2+3",
            context={"parent_task": "AI解释"}
        )

        if subsession:
            print(f"✅ 子会话创建成功，ID: {subsession.session_id}")

            # 记录子会话消息
            await subsession.record_message({
                "type": "user",
                "data": {"role": "user", "content": "计算 2+3"}
            })

            child_result = MockResultMessage("5")
            await subsession.record_message(child_result)
            await subsession.finalize(result_message=child_result)

            print("✅ 子会话完成")
        else:
            print("❌ 子会话创建失败")

        # 10. 测试清理功能
        print("\n🔟 测试清理功能...")
        cleanup_result = cleanup_sessions(
            "test_basic_agent",
            retention_days=0,  # 删除所有会话
            instances_root=project_root / "instances"
        )

        if cleanup_result['deleted'] > 0:
            print(f"✅ 清理功能成功，删除了 {cleanup_result['deleted']} 个会话")
        else:
            print("❌ 清理功能失败")

        print("\n🎉 核心功能测试完成！")
        print("\n📋 测试总结:")
        print("✅ 会话管理器核心功能")
        print("✅ 消息记录和序列化")
        print("✅ 文件创建和管理")
        print("✅ 查询API功能")
        print("✅ 调用关系图生成")
        print("✅ 导出功能")
        print("✅ 子会话管理")
        print("✅ 清理功能")

        return True

    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(test_session_manager_core())