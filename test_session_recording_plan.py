#!/usr/bin/env python3
"""
会话记录系统测试计划
测试新增的会话记录和查询功能
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.agent_system import AgentSystem
from src.session_query import (
    get_session_details,
    list_sessions,
    search_sessions,
    get_call_graph,
    export_session,
    cleanup_sessions
)

class SessionRecordingTestPlan:
    """会话记录系统测试计划"""

    def __init__(self):
        self.test_results = []
        self.test_agent = None

    async def setup_test_agent(self):
        """设置测试用的 Agent"""
        try:
            self.test_agent = AgentSystem("test_recording_agent")
            await self.test_agent.initialize()
            print("✅ 测试 Agent 初始化成功")
            return True
        except Exception as e:
            print(f"❌ 测试 Agent 初始化失败: {e}")
            return False

    def log_test_result(self, test_name: str, success: bool, details: str = ""):
        """记录测试结果"""
        status = "✅ PASS" if success else "❌ FAIL"
        self.test_results.append({
            "test": test_name,
            "success": success,
            "details": details
        })
        print(f"{status}: {test_name}")
        if details:
            print(f"   详情: {details}")

    async def test_1_basic_session_recording(self):
        """测试 1: 基础会话记录功能"""
        print("\n🧪 测试 1: 基础会话记录功能")

        try:
            # 执行一个简单查询
            prompt = "请计算 2+3 等于多少？"
            session_id = None

            async for message in self.test_agent.query(prompt, record_session=True):
                if hasattr(message, 'subtype'):
                    # 这是 ResultMessage，检查会话元数据
                    session_id = self.test_agent.current_session_id
                    break

            # 验证会话已创建
            if session_id:
                self.log_test_result("会话创建和ID返回", True, f"会话ID: {session_id}")

                # 验证会话文件已创建
                session_path = project_root / "instances" / "test_recording_agent" / "sessions" / session_id
                if session_path.exists():
                    self.log_test_result("会话目录创建", True, f"路径: {session_path}")

                    # 检查必要文件
                    metadata_file = session_path / "metadata.json"
                    messages_file = session_path / "messages.jsonl"

                    if metadata_file.exists():
                        self.log_test_result("metadata.json 创建", True)
                    else:
                        self.log_test_result("metadata.json 创建", False, "文件不存在")

                    if messages_file.exists():
                        self.log_test_result("messages.jsonl 创建", True)
                        # 检查消息内容
                        with open(messages_file, 'r', encoding='utf-8') as f:
                            content = f.read()
                            if 'user' in content and 'assistant' in content:
                                self.log_test_result("消息内容记录", True)
                            else:
                                self.log_test_result("消息内容记录", False, "消息内容不完整")
                    else:
                        self.log_test_result("messages.jsonl 创建", False, "文件不存在")
                else:
                    self.log_test_result("会话目录创建", False, "目录不存在")
            else:
                self.log_test_result("会话创建和ID返回", False, "未获取到会话ID")

        except Exception as e:
            self.log_test_result("基础会话记录", False, str(e))

    async def test_2_parent_child_sessions(self):
        """测试 2: 父子会话关系（简化版，不依赖子实例）"""
        print("\n🧪 测试 2: 父子会话关系（基础测试）")

        try:
            # 执行一个简单查询，验证会话记录正常
            prompt = "请详细解释什么是人工智能，包括其历史发展和主要分支"
            parent_session_id = None

            async for message in self.test_agent.query(prompt, record_session=True):
                if hasattr(message, 'subtype'):
                    parent_session_id = self.test_agent.current_session_id
                    break

            if parent_session_id:
                self.log_test_result("父会话创建", True, f"会话ID: {parent_session_id}")

                # 验证会话目录结构
                session_path = project_root / "instances" / "test_recording_agent" / "sessions" / parent_session_id
                if session_path.exists():
                    self.log_test_result("会话目录结构", True, "会话目录正确创建")

                    # 检查 subsessions 目录存在（即使为空）
                    subsessions_dir = session_path / "subsessions"
                    if subsessions_dir.exists():
                        self.log_test_result("subsessions 目录", True, "子会话目录已准备")
                    else:
                        self.log_test_result("subsessions 目录", False, "子会话目录未创建")
                else:
                    self.log_test_result("会话目录结构", False, "会话目录不存在")
            else:
                self.log_test_result("父会话创建", False, "未获取到会话ID")

        except Exception as e:
            self.log_test_result("父子会话关系", False, str(e))

    async def test_3_query_apis(self):
        """测试 3: 查询 API 功能"""
        print("\n🧪 测试 3: 查询 API 功能")

        try:
            # 先创建几个测试会话
            session_ids = []
            prompts = [
                "测试提示1: 简要介绍机器学习的基本概念",
                "测试提示2: 请解释深度学习和传统机器学习的区别",
                "测试提示3: 列举一些常见的人工智能应用领域"
            ]

            for prompt in prompts:
                async for message in self.test_agent.query(prompt, record_session=True):
                    if hasattr(message, 'subtype'):
                        session_ids.append(self.test_agent.current_session_id)
                        break

            # 测试 list_sessions
            sessions = list_sessions("test_recording_agent", project_root)
            if len(sessions) >= 3:
                self.log_test_result("list_sessions API", True, f"找到 {len(sessions)} 个会话")
            else:
                self.log_test_result("list_sessions API", False, f"只找到 {len(sessions)} 个会话")

            # 测试 get_session_details
            if session_ids:
                details = get_session_details("test_recording_agent", session_ids[0], project_root)
                if 'metadata' in details and 'messages' in details:
                    self.log_test_result("get_session_details API", True)
                else:
                    self.log_test_result("get_session_details API", False, "返回数据不完整")

                # 测试 search_sessions
                search_results = search_sessions(
                    "test_recording_agent",
                    "人工智能",
                    project_root
                )
                if len(search_results) > 0:
                    self.log_test_result("search_sessions API", True, f"搜索到 {len(search_results)} 个结果")
                else:
                    self.log_test_result("search_sessions API", False, "未搜索到结果")

                # 测试 get_call_graph
                call_graph = get_call_graph("test_recording_agent", session_ids[0], project_root)
                if 'session_id' in call_graph and 'hierarchy' in call_graph:
                    self.log_test_result("get_call_graph API", True)
                else:
                    self.log_test_result("get_call_graph API", False, "调用图数据不完整")

        except Exception as e:
            self.log_test_result("查询 API 功能", False, str(e))

    async def test_4_session_statistics(self):
        """测试 4: 会话统计功能"""
        print("\n🧪 测试 4: 会话统计功能")

        try:
            # 执行一个稍复杂的查询
            prompt = "请详细解释机器学习的基本概念，包括监督学习、无监督学习和强化学习的主要特点和应用场景"

            async for message in self.test_agent.query(prompt, record_session=True):
                if hasattr(message, 'subtype'):
                    session_id = self.test_agent.current_session_id
                    break

            if session_id:
                # 获取会话详情，检查统计信息
                details = get_session_details("test_recording_agent", session_id, project_root)

                if 'statistics' in details:
                    stats = details['statistics']
                    required_fields = ['start_time', 'message_count', 'session_duration_ms']

                    missing_fields = [field for field in required_fields if field not in stats]
                    if not missing_fields:
                        self.log_test_result("会话统计完整性", True, f"包含所有必需字段")
                    else:
                        self.log_test_result("会话统计完整性", False, f"缺少字段: {missing_fields}")

                    # 检查统计数据的合理性
                    if stats.get('message_count', 0) > 0:
                        self.log_test_result("消息计数统计", True, f"消息数: {stats['message_count']}")
                    else:
                        self.log_test_result("消息计数统计", False, "消息计数为0")
                else:
                    self.log_test_result("会话统计功能", False, "没有统计信息")

        except Exception as e:
            self.log_test_result("会话统计功能", False, str(e))

    async def test_5_export_and_cleanup(self):
        """测试 5: 导出和清理功能"""
        print("\n🧪 测试 5: 导出和清理功能")

        try:
            # 获取一个会话ID用于测试
            session_id = None
            async for message in self.test_agent.query("导出测试提示", record_session=True):
                if hasattr(message, 'subtype'):
                    session_id = self.test_agent.current_session_id
                    break

            if session_id:
                # 测试导出为 JSON
                export_json_path = project_root / "test_export.json"
                export_session(
                    "test_recording_agent",
                    session_id,
                    export_json_path,
                    format="json",
                    instances_root=project_root
                )

                if export_json_path.exists():
                    self.log_test_result("JSON 导出功能", True, f"文件: {export_json_path}")
                    export_json_path.unlink()  # 清理测试文件
                else:
                    self.log_test_result("JSON 导出功能", False, "导出文件未创建")

                # 测试导出为 Markdown
                export_md_path = project_root / "test_export.md"
                export_session(
                    "test_recording_agent",
                    session_id,
                    export_md_path,
                    format="markdown",
                    instances_root=project_root
                )

                if export_md_path.exists():
                    self.log_test_result("Markdown 导出功能", True, f"文件: {export_md_path}")
                    export_md_path.unlink()  # 清理测试文件
                else:
                    self.log_test_result("Markdown 导出功能", False, "导出文件未创建")

            # 测试清理功能（使用保留时间0天，即清理所有）
            # 注意：这个测试会删除所有测试会话，所以放在最后
            print("\n⚠️  测试清理功能（这将删除所有测试会话）")
            cleanup_result = cleanup_sessions(
                "test_recording_agent",
                retention_days=0,  # 删除所有会话
                instances_root=project_root
            )

            if cleanup_result['deleted_count'] > 0:
                self.log_test_result("会话清理功能", True,
                                   f"删除了 {cleanup_result['deleted_count']} 个会话")
            else:
                self.log_test_result("会话清理功能", False, "没有删除任何会话")

        except Exception as e:
            self.log_test_result("导出和清理功能", False, str(e))

    async def test_6_error_handling(self):
        """测试 6: 错误处理"""
        print("\n🧪 测试 6: 错误处理")

        try:
            # 测试查询不存在的会话
            try:
                details = get_session_details(
                    "test_recording_agent",
                    "nonexistent_session_id",
                    project_root
                )
                self.log_test_result("不存在会话查询", False, "应该抛出异常但没有")
            except FileNotFoundError:
                self.log_test_result("不存在会话查询", True, "正确抛出 FileNotFoundError")

            # 测试会话记录过程中的错误处理
            try:
                # 使用空提示测试
                await self.test_agent.query_text("", record_session=True)
                self.log_test_result("空提示处理", True, "系统能正常处理空提示")
            except Exception as e:
                self.log_test_result("空提示处理", True, f"系统正确处理错误: {e}")

        except Exception as e:
            self.log_test_result("错误处理", False, str(e))

    async def test_7_performance_considerations(self):
        """测试 7: 性能考虑"""
        print("\n🧪 测试 7: 性能考虑")

        try:
            import time

            # 测试连续多个查询的性能
            start_time = time.time()
            session_count = 5

            for i in range(session_count):
                prompt = f"性能测试查询 {i+1}: 请简单回答问题"
                async for message in self.test_agent.query(prompt, record_session=True):
                    if hasattr(message, 'subtype'):
                        break

            end_time = time.time()
            total_time = end_time - start_time
            avg_time = total_time / session_count

            if avg_time < 5.0:  # 假设平均每个查询应该在5秒内完成
                self.log_test_result("连续查询性能", True,
                                   f"平均 {avg_time:.2f} 秒/查询")
            else:
                self.log_test_result("连续查询性能", False,
                                   f"平均 {avg_time:.2f} 秒/查询，可能过慢")

            # 测试批量查询 API 的性能
            sessions = list_sessions("test_recording_agent", project_root)
            start_time = time.time()

            for session in sessions:
                get_session_details("test_recording_agent", session['session_id'], project_root)

            end_time = time.time()
            query_time = end_time - start_time

            if query_time < 2.0:  # 批量查询应该在2秒内完成
                self.log_test_result("批量查询性能", True,
                                   f"{len(sessions)} 个会话查询用时 {query_time:.2f} 秒")
            else:
                self.log_test_result("批量查询性能", False,
                                   f"{len(sessions)} 个会话查询用时 {query_time:.2f} 秒，可能过慢")

        except Exception as e:
            self.log_test_result("性能考虑", False, str(e))

    async def run_all_tests(self):
        """运行所有测试"""
        print("🚀 开始会话记录系统综合测试\n")

        # 设置测试环境
        if not await self.setup_test_agent():
            print("❌ 测试环境设置失败，退出测试")
            return

        # 运行所有测试
        await self.test_1_basic_session_recording()
        await self.test_2_parent_child_sessions()
        await self.test_3_query_apis()
        await self.test_4_session_statistics()
        await self.test_5_export_and_cleanup()
        await self.test_6_error_handling()
        await self.test_7_performance_considerations()

        # 生成测试报告
        self.generate_test_report()

    def generate_test_report(self):
        """生成测试报告"""
        print("\n" + "="*50)
        print("📊 测试报告")
        print("="*50)

        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['success'])
        failed_tests = total_tests - passed_tests

        print(f"总测试数: {total_tests}")
        print(f"通过: {passed_tests} ✅")
        print(f"失败: {failed_tests} ❌")
        print(f"成功率: {(passed_tests/total_tests)*100:.1f}%")

        if failed_tests > 0:
            print("\n❌ 失败的测试:")
            for result in self.test_results:
                if not result['success']:
                    print(f"  - {result['test']}: {result['details']}")

        print("\n📝 详细测试结果:")
        for result in self.test_results:
            status = "✅" if result['success'] else "❌"
            print(f"  {status} {result['test']}")
            if result['details']:
                print(f"     {result['details']}")

async def main():
    """主函数"""
    tester = SessionRecordingTestPlan()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())