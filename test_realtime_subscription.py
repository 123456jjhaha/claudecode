#!/usr/bin/env python3
"""
实时消息订阅测试

测试流程：
1. 启动demo_agent并订阅实时消息
2. 发送一个会触发file_analyzer_agent的查询
3. 实时接收并打印所有消息
4. 验证子Agent的消息能否实时传递到主查询过程
"""

import asyncio
import sys
import os
from pathlib import Path

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src import AgentSystem
from src.session import MessageBus, SessionQuery
from src.session.utils import SessionContext


async def test_realtime_subscription():
    """测试实时消息订阅"""
    print("开始实时消息订阅测试...")

    # 创建消息总线
    message_bus = MessageBus.from_config()
    await message_bus.connect()
    print("消息总线连接成功")

    try:
        # 创建主Agent
        agent = AgentSystem("demo_agent", message_bus=message_bus)
        await agent.initialize()
        print("demo_agent 初始化完成")

        # 创建一个待分析的测试文件
        test_file = Path("test_analysis.txt")
        test_content = """这是一个测试文件，用于演示实时消息订阅功能。

文件内容包含：
1. 一些示例文本
2. 用于分析的数据
3. 测试子Agent调用

这个文件将被file_analyzer_agent分析，
让我们观察实时消息传递效果！"""

        test_file.write_text(test_content.strip(), encoding='utf-8')
        print(f"创建测试文件: {test_file}")

        # 启动查询任务（后台运行）
        query_text = f"""请调用file_analyzer子实例来分析文件 '{test_file}' 的内容。
我需要看到：
1. 文件的基本信息
2. 内容摘要
3. 关键信息提取

请确保使用子实例完成这个任务，这样我们就能测试实时消息传递了。"""

        print("启动查询任务（将调用子实例）...")
        query_task = asyncio.create_task(agent.query_text(query_text))

        # 等待session创建
        await asyncio.sleep(1.0)

        # 获取session_id并开始订阅
        session_id = SessionContext.get_current_session()

        if session_id:
            print(f"开始订阅会话消息: {session_id}")

            # 创建SessionQuery实例
            query = SessionQuery("demo_agent", message_bus=message_bus)

            # 开始订阅（自动追踪子实例）
            await query.subscribe(
                session_id=session_id,
                on_parent_message=lambda msg: print(f"[主Agent] {msg}"),
                on_child_message=lambda child_id, instance, msg: print(f"[子Agent-{instance}] {msg}"),
                on_child_started=lambda child_id, instance: print(f"[系统] 子实例启动: {instance}")
            )

            print("实时订阅已启动，正在监听消息...")

            try:
                # 等待查询完成
                result = await query_task
                print(f"查询完成！会话ID: {result.session_id}")

                # 等待一下确保所有消息都被接收
                await asyncio.sleep(2.0)

            finally:
                await query.stop()
                print("停止订阅")
        else:
            print("未获取到session_id，无法订阅")
            result = await query_task

        # 清理测试文件
        if test_file.exists():
            test_file.unlink()
            print(f"清理测试文件: {test_file}")

        return result

    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        # 清理资源
        print("清理资源...")
        try:
            if 'agent' in locals():
                agent.cleanup()
            await message_bus.close()
            print("资源清理完成")
        except Exception as e:
            print(f"清理资源时出错: {e}")


if __name__ == "__main__":
    asyncio.run(test_realtime_subscription())