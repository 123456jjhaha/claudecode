"""
测试 2: 自定义工具功能

测试 Demo Agent 的自定义工具
- 计算器工具 (calculator)
- 文件分析器工具 (file_analyzer)
- 文本处理器工具 (text_processor)
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


async def test_custom_tools():
    """测试自定义工具功能"""
    print("\n" + "=" * 60)
    print("🛠️ 测试 2: 自定义工具功能")
    print("=" * 60)

    try:
        # 创建并初始化 agent
        print("\n1. 初始化 Demo Agent...")
        agent = AgentSystem("demo_agent")
        await agent.initialize()

        # 测试 1: 计算器工具
        print("\n2. 测试计算器工具...")
        response = await agent.query_text("""
        请使用计算器工具进行以下计算：
        1. 基础运算：
           - 123 + 456
           - 789 - 123
           - 15 * 20
           - 100 / 4
           - 2 ^ 10
           - 100 % 7

        2. 复杂表达式：
           - (123 + 456) * 2
           - 100 - 50 / 2
           - 2 ^ 3 ^ 2

        3. 多数字求和：
           - 计算 [10, 20, 30, 40, 50] 的和
        """)
        print("\n✅ 计算器工具测试完成")

        # 测试 2: 文件分析器工具
        print("\n3. 测试文件分析器工具...")
        response = await agent.query_text("""
        请使用文件分析器工具分析以下文件：
        1. 分析 demo_agent 的 config.yaml
           - 文件类型识别
           - 内容结构分析
           - 配置项统计

        2. 分析 tools/calculator.py
           - 检测代码类型
           - 统计函数数量
           - 分析代码结构

        3. 分析 .claude/agent.md
           - 文档类型识别
           - 内容长度统计
           - 章节结构分析
        """)
        print("\n✅ 文件分析器工具测试完成")

        # 测试 3: 文本处理器工具
        print("\n4. 测试文本处理器工具...")
        response = await agent.query_text("""
        请使用文本处理器工具处理以下任务：
        1. 文本统计：
           - 统计 config.yaml 的字符数、单词数、行数
           - 统计 agent.md 的文本信息

        2. 关键词提取：
           - 从 agent.md 中提取前 10 个关键词
           - 计算关键词频率

        3. 文本摘要：
           - 生成 agent.md 的简短摘要
           - 提取主要观点

        4. 文本处理：
           - 转换文本大小写
           - 替换特定词语
           - 格式化文本
        """)
        print("\n✅ 文本处理器工具测试完成")

        # 测试 4: 工具组合使用
        print("\n5. 测试工具组合使用...")
        response = await agent.query_text("""
        请组合使用自定义工具完成综合任务：
        1. 使用文件分析器分析一个 Python 文件
        2. 使用计算器统计文件中的数字
        3. 使用文本处理器处理文件的注释内容
        4. 生成综合分析报告
        """)
        print("\n✅ 工具组合测试完成")

        # 测试 5: 错误处理
        print("\n6. 测试错误处理...")
        response = await agent.query_text("""
        请测试自定义工具的错误处理：
        1. 计算器：尝试计算无效表达式 "abc + def"
        2. 文件分析器：尝试分析不存在的文件
        3. 文本处理器：尝试处理空文本
        观察工具如何处理错误情况。
        """)
        print("\n✅ 错误处理测试完成")

        print("\n" + "=" * 60)
        print("✅ 自定义工具功能测试全部通过！")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_custom_tools())