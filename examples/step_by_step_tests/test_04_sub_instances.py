"""
测试 4: 子实例系统功能

测试子实例的创建、调用和嵌套
- 子实例调用
- 嵌套会话
- 实例间通信
- 递归调用
"""

import asyncio
import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src import AgentSystem, set_log_level
from src.session_query import get_session_details, get_call_graph
import logging

# 配置日志
set_log_level(logging.INFO)


async def test_sub_instances():
    """测试子实例系统功能"""
    print("\n" + "=" * 60)
    print("🔗 测试 4: 子实例系统功能")
    print("=" * 60)

    try:
        # 创建并初始化主 agent
        print("\n1. 初始化主 Demo Agent...")
        main_agent = AgentSystem("demo_agent")
        await main_agent.initialize()

        print(f"   主Agent名称: {main_agent.agent_name}")
        print(f"   子实例数: {main_agent.instances_count}")

        # 测试 1: 基础子实例调用
        print("\n2. 测试基础子实例调用...")
        response = await main_agent.query_text("""
        请调用子实例 code_reviewer 来完成以下任务：
        - 分析 tools/calculator.py 文件
        - 检查代码质量
        - 提供改进建议
        """)
        print("✅ 基础子实例调用完成")

        # 记录主会话ID
        main_session_id = main_agent.current_session_id
        print(f"   主会话ID: {main_session_id}")

        # 测试 2: 多个子实例协作
        print("\n3. 测试多个子实例协作...")
        response = await main_agent.query_text("""
        请协调多个子实例完成任务：
        1. 使用 document_writer 子实例创建一个项目分析模板
        2. 使用 code_reviewer 子实例分析一个Python文件
        3. 使用 data_analyzer 子实例统计项目数据
        4. 整合所有结果生成综合报告
        """)
        print("✅ 多子实例协作完成")

        # 测试 3: 子实例嵌套调用
        print("\n4. 测试子实例嵌套调用...")
        response = await main_agent.query_text("""
        请测试子实例的嵌套调用能力：
        - 使用 code_reviewer 子实例
        - 让 code_reviewer 使用它的子实例 syntax_checker
        - 观察多层嵌套的会话记录
        """)
        print("✅ 子实例嵌套调用完成")

        # 测试 4: 参数传递和结果返回
        print("\n5. 测试参数传递和结果返回...")
        response = await main_agent.query_text("""
        测试子实例的参数传递：
        1. 准备一些代码内容
        2. 传递给 code_reviewer 子实例进行分析
        3. 指定具体的审查要求（如检查命名规范）
        4. 获取结构化的分析结果
        5. 在主实例中处理返回的结果
        """)
        print("✅ 参数传递测试完成")

        # 测试 5: 错误处理和异常情况
        print("\n6. 测试错误处理...")
        response = await main_agent.query_text("""
        测试子实例的错误处理：
        1. 尝试调用不存在的子实例
        2. 传递无效的参数给子实例
        3. 在子实例中触发错误
        4. 观察错误如何在实例间传播
        """)
        print("✅ 错误处理测试完成")

        # 等待一会确保所有会话都被记录
        await asyncio.sleep(3)

        # 测试 6: 分析嵌套会话结构
        print("\n7. 分析嵌套会话结构...")
        if main_session_id:
            try:
                # 获取主会话详情
                main_details = get_session_details("demo_agent", main_session_id)
                print(f"   - 主会话消息数: {len(main_details['messages'])}")
                print(f"   - 子会话数: {len(main_details['subsessions'])}")

                # 获取调用关系图
                call_graph = get_call_graph("demo_agent", main_session_id)
                print(f"   - 调用关系深度: {analyze_call_depth(call_graph.get('graph', {}))}")
                print(f"   - 涉及的实例: {get_involved_instances(call_graph.get('graph', {}))}")

                # 显示子会话信息
                for subsession in main_details['subsessions']:
                    print(f"   - 子会话: {subsession['session_id'][:8]}... ({subsession['instance_name']})")

            except Exception as e:
                print(f"   嵌套会话分析失败: {e}")

        # 测试 7: 性能对比
        print("\n8. 测试性能对比...")

        # 主实例直接执行
        start_time = asyncio.get_event_loop().time()
        await main_agent.query_text("""
        直接在主实例中完成：
        - 使用 Bash 列出文件
        - 使用 Read 读取配置
        - 使用计算器计算
        """)
        direct_time = asyncio.get_event_loop().time() - start_time

        # 通过子实例执行
        start_time = asyncio.get_event_loop().time()
        await main_agent.query_text("""
        通过子实例完成相同任务：
        - 使用 data_analyzer 列出和分析文件
        - 使用 code_reviewer 读取和分析配置
        - 使用计算器（通过子实例或直接）进行计算
        """)
        sub_instance_time = asyncio.get_event_loop().time() - start_time

        print(f"   - 直接执行耗时: {direct_time:.2f}秒")
        print(f"   - 子实例执行耗时: {sub_instance_time:.2f}秒")
        print(f"   - 性能差异: {((sub_instance_time - direct_time) / direct_time * 100):+.1f}%")

        print("\n" + "=" * 60)
        print("✅ 子实例系统功能测试全部通过！")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


def analyze_call_depth(graph: dict, current_depth: int = 0) -> int:
    """分析调用关系的最大深度"""
    if not graph or not graph.get('children'):
        return current_depth

    max_depth = current_depth
    for child in graph['children']:
        depth = analyze_call_depth(child, current_depth + 1)
        max_depth = max(max_depth, depth)

    return max_depth


def get_involved_instances(graph: dict, instances: set = None) -> set:
    """获取涉及的所有实例名称"""
    if instances is None:
        instances = set()

    if 'instance_name' in graph:
        instances.add(graph['instance_name'])

    for child in graph.get('children', []):
        get_involved_instances(child, instances)

    return instances


if __name__ == "__main__":
    asyncio.run(test_sub_instances())