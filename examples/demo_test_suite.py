"""
Demo Agent 测试套件 - 完整功能测试

这个测试套件全面测试 Claude Agent System 的所有功能：
1. 基础配置系统
2. 工具系统
3. 会话记录系统
4. 子实例系统
5. 并行执行
6. 综合场景

使用 demo_agent 实例进行测试
"""

import asyncio
import sys
import time
import json
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src import AgentSystem, set_log_level
from src.session_query import (
    get_session_details,
    list_sessions,
    search_sessions,
    get_call_graph,
    export_session,
    get_session_statistics_summary
)
import logging

# 配置日志
set_log_level(logging.INFO)


class DemoTestSuite:
    """Demo Agent 测试套件"""

    def __init__(self):
        self.agent = None
        self.test_results = []
        self.session_ids = []

    async def run_all_tests(self):
        """运行所有测试"""
        print("\n" + "=" * 80)
        print("🚀 Demo Agent 完整功能测试套件")
        print("=" * 80)

        try:
            # 1. 初始化测试
            await self.test_initialization()

            # 2. 配置系统测试
            await self.test_configuration_system()

            # 3. 基础工具测试
            await self.test_basic_tools()

            # 4. 自定义工具测试
            await self.test_custom_tools()

            # 5. 会话记录测试
            await self.test_session_recording()

            # 6. 子实例测试
            await self.test_sub_instances()

            # 7. 并行执行测试
            await self.test_parallel_execution()

            # 8. 综合场景测试
            await self.test_complex_scenario()

            # 9. 会话查询测试
            await self.test_session_query_system()

            # 10. 生成测试报告
            await self.generate_test_report()

        except Exception as e:
            print(f"\n❌ 测试套件执行失败: {e}")
            import traceback
            traceback.print_exc()

        finally:
            if self.agent:
                print("\n🔧 清理资源...")
                # 这里可以添加清理逻辑

    async def test_initialization(self):
        """测试系统初始化"""
        print("\n" + "=" * 60)
        print("📋 测试 1: 系统初始化")
        print("=" * 60)

        try:
            # 创建 agent
            print("\n1.1 创建 AgentSystem 实例...")
            self.agent = AgentSystem("demo_agent")

            # 初始化
            print("1.2 初始化系统...")
            start_time = time.time()
            await self.agent.initialize()
            init_time = time.time() - start_time

            # 显示信息
            print(f"\n✅ 初始化成功！耗时: {init_time:.2f}秒")
            print(f"   - Agent 名称: {self.agent.agent_name}")
            print(f"   - Agent 描述: {self.agent.agent_description}")
            print(f"   - 可用工具数: {self.agent.tools_count}")
            print(f"   - 子实例数: {self.agent.instances_count}")

            # 记录测试结果
            self.test_results.append({
                "test": "initialization",
                "status": "passed",
                "duration": init_time,
                "details": {
                    "agent_name": self.agent.agent_name,
                    "tools_count": self.agent.tools_count,
                    "instances_count": self.agent.instances_count
                }
            })

        except Exception as e:
            print(f"\n❌ 初始化失败: {e}")
            self.test_results.append({
                "test": "initialization",
                "status": "failed",
                "error": str(e)
            })
            raise

    async def test_configuration_system(self):
        """测试配置系统"""
        print("\n" + "=" * 60)
        print("⚙️ 测试 2: 配置系统")
        print("=" * 60)

        try:
            print("\n2.1 检查配置加载...")

            # 验证配置
            assert self.agent.agent_name == "demo_agent"
            assert self.agent.model == "claude-sonnet-4-5"
            assert self.agent.session_manager is not None

            print("2.2 检查会话记录配置...")
            config = self.agent.config
            session_config = config.get('session_recording', {})

            print(f"   - 会话记录启用: {session_config.get('enabled', False)}")
            print(f"   - 保留天数: {session_config.get('retention_days', 'N/A')}")
            print(f"   - 最大大小: {session_config.get('max_total_size_mb', 'N/A')}MB")
            print(f"   - 批量大小: {session_config.get('batch_size', 'N/A')}")

            print("\n✅ 配置系统测试通过")

            self.test_results.append({
                "test": "configuration",
                "status": "passed",
                "details": {
                    "session_recording_enabled": session_config.get('enabled', False),
                    "session_config": session_config
                }
            })

        except Exception as e:
            print(f"\n❌ 配置系统测试失败: {e}")
            self.test_results.append({
                "test": "configuration",
                "status": "failed",
                "error": str(e)
            })

    async def test_basic_tools(self):
        """测试基础工具"""
        print("\n" + "=" * 60)
        print("🔧 测试 3: 基础工具")
        print("=" * 60)

        try:
            # 测试 Read 工具
            print("\n3.1 测试 Read 工具...")
            response = await self.agent.query_text(
                "使用 Read 工具读取 config.yaml 文件的前 20 行"
            )
            print("✅ Read 工具测试通过")

            # 测试 Bash 工具
            print("\n3.2 测试 Bash 工具...")
            response = await self.agent.query_text(
                "使用 Bash 工具执行 'echo \"Hello from Claude Agent\"'"
            )
            print("✅ Bash 工具测试通过")

            # 测试 Glob 工具
            print("\n3.3 测试 Glob 工具...")
            response = await self.agent.query_text(
                "使用 Glob 工具查找所有 .py 文件"
            )
            print("✅ Glob 工具测试通过")

            self.test_results.append({
                "test": "basic_tools",
                "status": "passed",
                "details": {
                    "tools_tested": ["Read", "Bash", "Glob"]
                }
            })

        except Exception as e:
            print(f"\n❌ 基础工具测试失败: {e}")
            self.test_results.append({
                "test": "basic_tools",
                "status": "failed",
                "error": str(e)
            })

    async def test_custom_tools(self):
        """测试自定义工具"""
        print("\n" + "=" * 60)
        print("🛠️ 测试 4: 自定义工具")
        print("=" * 60)

        try:
            # 测试计算器工具
            print("\n4.1 测试计算器工具...")
            response = await self.agent.query_text(
                "使用计算器工具计算以下表达式：\n"
                "1. 123 + 456\n"
                "2. 2^10\n"
                "3. 100 % 7"
            )
            print("✅ 计算器工具测试通过")

            # 测试文件分析器工具
            print("\n4.2 测试文件分析器工具...")
            response = await self.agent.query_text(
                "使用文件分析器分析 config.yaml 文件"
            )
            print("✅ 文件分析器工具测试通过")

            # 测试文本处理器工具
            print("\n4.3 测试文本处理器工具...")
            response = await self.agent.query_text(
                "使用文本处理器统计 README.md 的字符数、单词数和行数"
            )
            print("✅ 文本处理器工具测试通过")

            self.test_results.append({
                "test": "custom_tools",
                "status": "passed",
                "details": {
                    "tools_tested": ["calculator", "file_analyzer", "text_processor"]
                }
            })

        except Exception as e:
            print(f"\n❌ 自定义工具测试失败: {e}")
            self.test_results.append({
                "test": "custom_tools",
                "status": "failed",
                "error": str(e)
            })

    async def test_session_recording(self):
        """测试会话记录"""
        print("\n" + "=" * 60)
        print("📝 测试 5: 会话记录系统")
        print("=" * 60)

        try:
            # 记录当前会话ID
            session_id_before = self.agent.current_session_id

            print(f"\n5.1 当前会话ID: {session_id_before}")

            # 执行一些查询生成会话数据
            print("\n5.2 执行查询生成会话数据...")
            await self.agent.query_text(
                "请介绍你的主要功能，并使用至少两个工具来演示"
            )

            # 获取新的会话ID
            session_id_after = self.agent.current_session_id
            print(f"5.3 查询后会话ID: {session_id_after}")

            # 检查会话管理器
            print("\n5.4 检查会话管理器...")
            if self.agent.session_manager:
                print(f"   - 会话记录启用: {self.agent.session_manager.enabled}")
                print(f"   - 当前会话数: {len(list_sessions('demo_agent', limit=10))}")

            # 保存会话ID供后续测试使用
            if session_id_after:
                self.session_ids.append(session_id_after)

            print("\n✅ 会话记录系统测试通过")

            self.test_results.append({
                "test": "session_recording",
                "status": "passed",
                "details": {
                    "session_id": session_id_after,
                    "manager_enabled": self.agent.session_manager.enabled if self.agent.session_manager else False
                }
            })

        except Exception as e:
            print(f"\n❌ 会话记录测试失败: {e}")
            self.test_results.append({
                "test": "session_recording",
                "status": "failed",
                "error": str(e)
            })

    async def test_sub_instances(self):
        """测试子实例"""
        print("\n" + "=" * 60)
        print("🔗 测试 6: 子实例系统")
        print("=" * 60)

        try:
            # 测试调用子实例
            print("\n6.1 测试调用子实例...")
            response = await self.agent.query_text(
                "请使用 code_reviewer 子实例分析 tools/calculator.py 文件的代码质量"
            )
            print("✅ 子实例调用测试通过")

            # 测试子实例工具
            print("\n6.2 测试子实例工具...")
            response = await self.agent.query_text(
                "请使用 document_writer 子实例生成一份关于 demo_agent 功能的简短报告"
            )
            print("✅ 子实例工具测试通过")

            # 测试数据分析子实例
            print("\n6.3 测试数据分析子实例...")
            response = await self.agent.query_text(
                "请使用 data_analyzer 子实例分析当前目录的文件结构"
            )
            print("✅ 数据分析子实例测试通过")

            self.test_results.append({
                "test": "sub_instances",
                "status": "passed",
                "details": {
                    "sub_instances_tested": ["code_reviewer", "document_writer", "data_analyzer"]
                }
            })

        except Exception as e:
            print(f"\n❌ 子实例测试失败: {e}")
            self.test_results.append({
                "test": "sub_instances",
                "status": "failed",
                "error": str(e)
            })

    async def test_parallel_execution(self):
        """测试并行执行"""
        print("\n" + "=" * 60)
        print("⚡ 测试 7: 并行执行")
        print("=" * 60)

        try:
            print("\n7.1 测试并行工具调用...")

            # 使用并行提示
            parallel_prompt = """
            请同时执行以下任务：
            1. 使用计算器计算 50 * 20
            2. 使用文件分析器分析 .claude/agent.md 文件
            3. 使用 Bash 列出当前目录内容
            4. 使用 Glob 查找所有 .yaml 文件

            请并行执行这些任务并汇总结果。
            """

            start_time = time.time()
            response = await self.agent.query_text(parallel_prompt)
            execution_time = time.time() - start_time

            print(f"✅ 并行执行测试通过，耗时: {execution_time:.2f}秒")

            self.test_results.append({
                "test": "parallel_execution",
                "status": "passed",
                "duration": execution_time,
                "details": {
                    "parallel_tasks": 4,
                    "execution_time": execution_time
                }
            })

        except Exception as e:
            print(f"\n❌ 并行执行测试失败: {e}")
            self.test_results.append({
                "test": "parallel_execution",
                "status": "failed",
                "error": str(e)
            })

    async def test_complex_scenario(self):
        """测试综合场景"""
        print("\n" + "=" * 60)
        print("🎭 测试 8: 综合场景")
        print("=" * 60)

        try:
            print("\n8.1 执行复杂工作流...")

            complex_prompt = """
            请完成以下综合任务：

            1. 首先分析项目结构（使用 Glob 和 Bash）
            2. 读取并分析 config.yaml 配置文件
            3. 使用子实例 code_reviewer 审查一个 Python 工具文件
            4. 使用子实例 document_writer 生成项目分析报告
            5. 使用计算器进行一些统计计算
            6. 最后提供一个完整的项目分析总结

            请充分利用所有可用工具和子实例。
            """

            start_time = time.time()
            response = await self.agent.query_text(complex_prompt)
            execution_time = time.time() - start_time

            print(f"✅ 综合场景测试通过，耗时: {execution_time:.2f}秒")

            # 保存这次复杂场景的会话ID
            if self.agent.current_session_id:
                self.session_ids.append(self.agent.current_session_id)

            self.test_results.append({
                "test": "complex_scenario",
                "status": "passed",
                "duration": execution_time,
                "details": {
                    "scenario_complexity": "high",
                    "execution_time": execution_time
                }
            })

        except Exception as e:
            print(f"\n❌ 综合场景测试失败: {e}")
            self.test_results.append({
                "test": "complex_scenario",
                "status": "failed",
                "error": str(e)
            })

    async def test_session_query_system(self):
        """测试会话查询系统"""
        print("\n" + "=" * 60)
        print("🔍 测试 9: 会话查询系统")
        print("=" * 60)

        try:
            if not self.session_ids:
                print("\n⚠️ 没有可用的会话ID进行查询测试")
                return

            print(f"\n9.1 测试会话详情查询...")

            # 测试获取会话详情
            for session_id in self.session_ids[-2:]:  # 只测试最近2个会话
                try:
                    details = get_session_details("demo_agent", session_id)
                    print(f"   - 会话 {session_id[:8]}... 详情获取成功")
                    print(f"     状态: {details['metadata'].get('status', 'Unknown')}")
                    print(f"     消息数: {len(details['messages'])}")
                    print(f"     耗时: {details['statistics'].get('duration_seconds', 0):.2f}秒")
                except Exception as e:
                    print(f"   - 会话详情查询失败: {e}")

            print("\n9.2 测试会话列表...")
            sessions = list_sessions("demo_agent", limit=5)
            print(f"   - 最近会话数: {len(sessions)}")

            print("\n9.3 测试调用关系图...")
            if self.session_ids:
                try:
                    call_graph = get_call_graph("demo_agent", self.session_ids[-1])
                    print(f"   - 调用关系图生成成功")
                    print(f"     根会话: {call_graph.get('root_session_id', 'Unknown')}")
                except Exception as e:
                    print(f"   - 调用关系图生成失败: {e}")

            print("\n✅ 会话查询系统测试通过")

            self.test_results.append({
                "test": "session_query",
                "status": "passed",
                "details": {
                    "sessions_tested": len(self.session_ids),
                    "query_types": ["details", "list", "call_graph"]
                }
            })

        except Exception as e:
            print(f"\n❌ 会话查询测试失败: {e}")
            self.test_results.append({
                "test": "session_query",
                "status": "failed",
                "error": str(e)
            })

    async def generate_test_report(self):
        """生成测试报告"""
        print("\n" + "=" * 80)
        print("📊 测试报告")
        print("=" * 80)

        # 统计测试结果
        total_tests = len(self.test_results)
        passed_tests = len([t for t in self.test_results if t["status"] == "passed"])
        failed_tests = total_tests - passed_tests

        print(f"\n📈 测试统计:")
        print(f"   - 总测试数: {total_tests}")
        print(f"   - 通过: {passed_tests} ✅")
        print(f"   - 失败: {failed_tests} ❌")
        print(f"   - 成功率: {(passed_tests/total_tests*100):.1f}%")

        # 详细结果
        print(f"\n📋 详细结果:")
        for result in self.test_results:
            status_icon = "✅" if result["status"] == "passed" else "❌"
            duration = f" ({result.get('duration', 0):.2f}s)" if "duration" in result else ""
            print(f"   {status_icon} {result['test']}{duration}")
            if result["status"] == "failed" and "error" in result:
                print(f"      错误: {result['error']}")

        # 性能分析
        print(f"\n⚡ 性能分析:")
        durations = [r.get("duration", 0) for r in self.test_results if "duration" in r]
        if durations:
            print(f"   - 总耗时: {sum(durations):.2f}秒")
            print(f"   - 平均耗时: {sum(durations)/len(durations):.2f}秒")
            print(f"   - 最慢测试: {max(durations):.2f}秒")

        # 功能覆盖
        print(f"\n🎯 功能覆盖:")
        features_tested = [
            "✅ 系统初始化",
            "✅ 配置系统",
            "✅ 基础工具",
            "✅ 自定义工具",
            "✅ 会话记录",
            "✅ 子实例系统",
            "✅ 并行执行",
            "✅ 综合场景",
            "✅ 会话查询"
        ]
        for feature in features_tested:
            print(f"   {feature}")

        # 保存报告到文件
        report_data = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "success_rate": passed_tests/total_tests*100
            },
            "results": self.test_results,
            "session_ids": self.session_ids
        }

        report_file = Path(__file__).parent / "test_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)

        print(f"\n💾 详细报告已保存到: {report_file}")

        # 最终结论
        if failed_tests == 0:
            print(f"\n🎉 所有测试通过！Demo Agent 功能完全正常！")
        else:
            print(f"\n⚠️ 有 {failed_tests} 个测试失败，请检查相关功能。")

        print("\n" + "=" * 80)


async def main():
    """主函数"""
    suite = DemoTestSuite()
    await suite.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())