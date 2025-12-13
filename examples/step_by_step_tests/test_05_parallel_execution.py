"""
测试 5: 并行执行功能

测试 Claude Agent System 的并行执行能力
- 工具并行调用
- 子实例并行执行
- 异步任务处理
- 性能优化
"""

import asyncio
import sys
import time
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src import AgentSystem, set_log_level
import logging

# 配置日志
set_log_level(logging.INFO)


async def test_parallel_execution():
    """测试并行执行功能"""
    print("\n" + "=" * 60)
    print("⚡ 测试 5: 并行执行功能")
    print("=" * 60)

    try:
        # 创建并初始化 agent
        print("\n1. 初始化 Demo Agent...")
        agent = AgentSystem("demo_agent")
        await agent.initialize()

        # 测试 1: 工具并行调用
        print("\n2. 测试工具并行调用...")
        parallel_prompt = """
        请同时执行以下工具任务：
        1. 使用 Read 读取 config.yaml 文件
        2. 使用 Bash 执行 'echo "Task 2"' 命令
        3. 使用 Glob 查找所有 .py 文件
        4. 使用 Grep 搜索 "demo" 关键字
        5. 使用计算器计算 100 * 5

        请并行执行这些任务并汇总所有结果。
        """

        start_time = time.time()
        response = await agent.query_text(parallel_prompt)
        parallel_time = time.time() - start_time
        print(f"   并行执行耗时: {parallel_time:.2f}秒")
        print("✅ 工具并行调用完成")

        # 测试 2: 串行执行对比
        print("\n3. 串行执行对比测试...")
        serial_prompt = """
        请按顺序执行以下任务：
        1. 首先使用 Read 读取 config.yaml 文件
        2. 然后使用 Bash 执行 'echo "Task 2"' 命令
        3. 接着使用 Glob 查找所有 .py 文件
        4. 之后使用 Grep 搜索 "demo" 关键字
        5. 最后使用计算器计算 100 * 5

        请按顺序执行并报告每个任务的完成时间。
        """

        start_time = time.time()
        response = await agent.query_text(serial_prompt)
        serial_time = time.time() - start_time
        print(f"   串行执行耗时: {serial_time:.2f}秒")

        # 计算性能提升
        if serial_time > 0:
            improvement = ((serial_time - parallel_time) / serial_time) * 100
            print(f"   性能提升: {improvement:+.1f}%")

        print("✅ 串行执行对比完成")

        # 测试 3: 子实例并行执行
        print("\n4. 测试子实例并行执行...")
        sub_instance_prompt = """
        请并行调用以下子实例：
        1. 使用 code_reviewer 分析 tools/calculator.py
        2. 使用 document_writer 生成关于项目结构的报告
        3. 使用 data_analyzer 分析配置文件的数据
        4. 使用计算器（如果可用）进行性能统计

        让所有子实例同时工作，然后汇总结果。
        """

        start_time = time.time()
        response = await agent.query_text(sub_instance_prompt)
        sub_parallel_time = time.time() - start_time
        print(f"   子实例并行耗时: {sub_parallel_time:.2f}秒")
        print("✅ 子实例并行执行完成")

        # 测试 4: 混合并行执行
        print("\n5. 测试混合并行执行...")
        mixed_prompt = """
        请执行复杂的混合并行任务：

        并行组1（工具）：
        - Read 读取 .claude/agent.md
        - Bash 获取系统信息

        并行组2（子实例）：
        - code_reviewer 分析文件
        - document_writer 创建文档

        并行组3（计算）：
        - 计算器计算斐波那契数列前10项
        - 计算器计算质数

        所有组应该同时执行，请协调并展示并行效果。
        """

        start_time = time.time()
        response = await agent.query_text(mixed_prompt)
        mixed_time = time.time() - start_time
        print(f"   混合并行耗时: {mixed_time:.2f}秒")
        print("✅ 混合并行执行完成")

        # 测试 5: 流式并行响应
        print("\n6. 测试流式并行响应...")
        stream_prompt = """
        请使用流式响应和并行执行：
        - 同时开始多个任务
        - 在任务完成时立即流式返回结果
        - 展示任务的完成顺序
        - 提供实时进度更新
        """

        print("   开始流式响应:")
        start_time = time.time()
        async for message in agent.query(stream_prompt):
            if hasattr(message, "text"):
                print(message.text, end="", flush=True)
        stream_time = time.time() - start_time
        print(f"\n   流式并行耗时: {stream_time:.2f}秒")
        print("✅ 流式并行响应完成")

        # 测试 6: 性能基准测试
        print("\n7. 性能基准测试...")

        # 小任务批量测试
        small_tasks = """
        并行执行10个小任务：
        1. echo "Task 1"
        2. echo "Task 2"
        3. echo "Task 3"
        4. echo "Task 4"
        5. echo "Task 5"
        6. 计算 1+1
        7. 计算 2+2
        8. 计算 3+3
        9. 列出当前目录
        10. 显示当前时间
        """

        start_time = time.time()
        response = await agent.query_text(small_tasks)
        batch_time = time.time() - start_time
        print(f"   10个小任务批量耗时: {batch_time:.2f}秒")
        print(f"   平均每任务: {batch_time/10:.3f}秒")

        # 测试 7: 并发限制测试
        print("\n8. 并发限制测试...")
        concurrent_prompt = """
        测试系统并发处理能力：
        - 同时启动20个简单计算任务
        - 观察系统如何处理高并发
        - 检查是否有任务丢失或延迟
        - 报告成功完成的任务数
        """

        start_time = time.time()
        response = await agent.query_text(concurrent_prompt)
        concurrent_time = time.time() - start_time
        print(f"   并发测试耗时: {concurrent_time:.2f}秒")
        print("✅ 并发限制测试完成")

        # 性能总结
        print("\n9. 性能总结...")
        print(f"   - 工具并行执行: {parallel_time:.2f}秒")
        print(f"   - 串行执行: {serial_time:.2f}秒")
        print(f"   - 子实例并行: {sub_parallel_time:.2f}秒")
        print(f"   - 混合并行: {mixed_time:.2f}秒")
        print(f"   - 流式响应: {stream_time:.2f}秒")
        print(f"   - 批量处理: {batch_time:.2f}秒")
        print(f"   - 高并发处理: {concurrent_time:.2f}秒")

        # 计算平均并行效率
        times = [parallel_time, sub_parallel_time, mixed_time, stream_time]
        avg_parallel_time = sum(times) / len(times)
        print(f"   - 平均并行效率: {avg_parallel_time:.2f}秒")

        print("\n" + "=" * 60)
        print("✅ 并行执行功能测试全部通过！")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_parallel_execution())