#!/usr/bin/env python3
"""
测试 demo_agent 调用子实例的完整流程

这个测试将验证：
1. demo_agent 能否正确调用 file_analyzer_agent
2. demo_agent 能否正确调用 syntax_checker_agent
3. 子实例的工具是否正常工作
4. 会话记录是否正确生成
"""

import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src import AgentSystem

def create_test_files():
    """创建测试文件"""
    test_dir = project_root / "test_files"
    test_dir.mkdir(exist_ok=True)

    # 创建一个 Python 测试文件
    python_file = test_dir / "example.py"
    python_content = '''#!/usr/bin/env python3
"""
示例 Python 文件 - 用于测试文件分析和语法检查
"""

import os
import sys
import json
from typing import Dict, Any, List

def calculate_sum(a: int, b: int) -> int:
    """计算两个整数的和"""
    return a + b

class DataProcessor:
    """数据处理器类"""

    def __init__(self, name: str):
        self.name = name
        self.data = []

    def add_data(self, item: Any) -> None:
        """添加数据项"""
        self.data.append(item)

    def process_data(self) -> Dict[str, Any]:
        """处理数据并返回结果"""
        return {
            "name": self.name,
            "count": len(self.data),
            "items": self.data
        }

def main():
    """主函数"""
    processor = DataProcessor("test")

    # 添加一些测试数据
    for i in range(5):
        processor.add_data(f"item_{i}")

    # 处理数据
    result = processor.process_data()
    print(f"处理结果: {result}")

    # 计算一些值
    sum_result = calculate_sum(10, 20)
    print(f"10 + 20 = {sum_result}")

if __name__ == "__main__":
    main()
'''

    with open(python_file, 'w', encoding='utf-8') as f:
        f.write(python_content)

    # 创建一个 JSON 测试文件
    json_file = test_dir / "config.json"
    json_content = '''{
    "app": {
        "name": "Test Application",
        "version": "1.0.0",
        "debug": true,
        "settings": {
            "timeout": 30,
            "retries": 3,
            "features": ["auth", "logging", "cache"]
        }
    },
    "database": {
        "host": "localhost",
        "port": 5432,
        "name": "testdb",
        "credentials": {
            "username": "admin",
            "password": "secret"
        }
    }
}'''

    with open(json_file, 'w', encoding='utf-8') as f:
        f.write(json_content)

    # 创建一个有语法错误的 Python 文件
    bad_python_file = test_dir / "syntax_error.py"
    bad_python_content = '''#!/usr/bin/env python3
"""
有语法错误的 Python 文件
"""

import os
import sys

def broken_function(
    """缺少函数参数，会导致语法错误"""
    print("This function has a syntax error")
    # 缺少 return 语句和闭合的括号

class IncompleteClass
    """缺少冒号，会导致语法错误"""
    def __init__(self):
        self.value = 42

    def method_with_error(self)
        """方法定义缺少冒号"""
        print("Missing colon")

if __name__ == "__main__"
    """if 语句也缺少冒号"""
    broken_function()
'''

    with open(bad_python_file, 'w', encoding='utf-8') as f:
        f.write(bad_python_content)

    return {
        "python_file": str(python_file),
        "json_file": str(json_file),
        "bad_python_file": str(bad_python_file)
    }

async def test_file_analyzer_subinstance(agent: AgentSystem, test_files: dict):
    """测试文件分析子实例"""
    print("\n" + "="*50)
    print("🔍 测试文件分析子实例")
    print("="*50)

    # 测试文件类型检测
    prompt = f"""
请使用 file_analyzer 子实例分析以下文件：
1. 检测文件类型和基本信息：{test_files['python_file']}
2. 分析内容结构：{test_files['json_file']}
3. 提取元数据信息：{test_files['python_file']}

请详细展示每个文件的分析结果。
"""

    print(f"\n📝 发送请求: {prompt[:100]}...")

    try:
        result = await agent.query_text(prompt)
        print(f"\n✅ 文件分析结果:")
        print("-" * 40)
        print(result.result[:1000] + "..." if len(result.result) > 1000 else result.result)
        print(f"\n📊 会话 ID: {result.session_id}")
        return result.session_id
    except Exception as e:
        print(f"❌ 文件分析失败: {e}")
        return None

async def test_syntax_checker_subinstance(agent: AgentSystem, test_files: dict):
    """测试语法检查子实例"""
    print("\n" + "="*50)
    print("🔧 测试语法检查子实例")
    print("="*50)

    # 测试语法检查
    prompt = f"""
请使用 syntax_checker 子实例检查以下文件的语法：
1. 正常的 Python 文件：{test_files['python_file']}
2. 有语法错误的 Python 文件：{test_files['bad_python_file']}

请展示每个文件的语法检查结果，包括错误位置和修复建议。
"""

    print(f"\n📝 发送请求: {prompt[:100]}...")

    try:
        result = await agent.query_text(prompt)
        print(f"\n✅ 语法检查结果:")
        print("-" * 40)
        print(result.result[:1000] + "..." if len(result.result) > 1000 else result.result)
        print(f"\n📊 会话 ID: {result.session_id}")
        return result.session_id
    except Exception as e:
        print(f"❌ 语法检查失败: {e}")
        return None

async def test_combined_workflow(agent: AgentSystem, test_files: dict):
    """测试组合工作流"""
    print("\n" + "="*50)
    print("🔄 测试组合工作流")
    print("="*50)

    prompt = f"""
请执行以下分析流程：

1. 首先使用 file_analyzer 子实例分析文件：{test_files['json_file']}
2. 然后使用 syntax_checker 子实例验证该文件的 JSON 格式
3. 最后综合两个子实例的分析结果，给出一个完整的文件评估报告

请确保分析结果的准确性和完整性。
"""

    print(f"\n📝 发送组合请求...")

    try:
        result = await agent.query_text(prompt)
        print(f"\n✅ 组合分析结果:")
        print("-" * 40)
        print(result.result[:1500] + "..." if len(result.result) > 1500 else result.result)
        print(f"\n📊 会话 ID: {result.session_id}")
        return result.session_id
    except Exception as e:
        print(f"❌ 组合分析失败: {e}")
        return None

def check_session_records(agent_name: str):
    """检查会话记录"""
    print("\n" + "="*50)
    print("📁 检查会话记录")
    print("="*50)

    instances_dir = project_root / "instances" / agent_name / "sessions"

    if instances_dir.exists():
        sessions = list(instances_dir.glob("*"))
        print(f"\n📊 找到 {len(sessions)} 个会话记录:")

        for session_dir in sorted(sessions)[-3:]:  # 显示最新的3个会话
            if session_dir.is_dir():
                print(f"\n📂 会话: {session_dir.name}")

                # 检查 metadata.json
                metadata_file = session_dir / "metadata.json"
                if metadata_file.exists():
                    import json
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    print(f"   - 开始时间: {metadata.get('start_time', 'N/A')}")
                    print(f"   - 消息数: {metadata.get('message_count', 'N/A')}")
                    print(f"   - 子会话数: {metadata.get('subsession_count', 'N/A')}")

                # 检查 messages.jsonl
                messages_file = session_dir / "messages.jsonl"
                if messages_file.exists():
                    with open(messages_file, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                    print(f"   - 消息行数: {len(lines)}")

                # 检查子会话
                subsessions_dir = session_dir / "subsessions"
                if subsessions_dir.exists():
                    subsessions = list(subsessions_dir.glob("*"))
                    print(f"   - 子会话: {len(subsessions)} 个")
                    for subsession in subsessions:
                        if subsession.is_dir():
                            print(f"     * {subsession.name}")
    else:
        print(f"\n❌ 未找到会话记录目录: {instances_dir}")

async def main():
    """主测试函数"""
    print("开始测试子实例调用流程")
    print("="*60)

    # 创建测试文件
    print("\n📁 创建测试文件...")
    test_files = create_test_files()
    print("✅ 测试文件创建完成")

    # 初始化 demo_agent
    print("\n🔧 初始化 demo_agent...")
    agent = AgentSystem("demo_agent",instances_root="C:/Users/Lenovo/Desktop/test2/claudecode/instances")

    try:
        await agent.initialize()
        print("✅ demo_agent 初始化成功")
        print(f"   - 工具数量: {agent.tools_count}")
        print(f"   - 子实例数量: {agent.sub_instances_count}")

        # 测试文件分析子实例
        file_session_id = await test_file_analyzer_subinstance(agent, test_files)

        # 测试语法检查子实例
        syntax_session_id = await test_syntax_checker_subinstance(agent, test_files)

        # 测试组合工作流
        combined_session_id = await test_combined_workflow(agent, test_files)

        # 检查会话记录
        check_session_records("demo_agent")
        check_session_records("file_analyzer_agent")
        check_session_records("syntax_checker_agent")

        # 总结
        print("\n" + "="*60)
        print("📊 测试总结")
        print("="*60)
        print(f"✅ 文件分析会话 ID: {file_session_id or '失败'}")
        print(f"✅ 语法检查会话 ID: {syntax_session_id or '失败'}")
        print(f"✅ 组合分析会话 ID: {combined_session_id or '失败'}")

        if file_session_id and syntax_session_id and combined_session_id:
            print("\n🎉 所有测试通过！子实例调用流程正常工作。")
        else:
            print("\n⚠️ 部分测试失败，请检查错误信息。")

    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # 清理资源
        print("\n🧹 清理资源...")
        agent.cleanup()
        print("✅ 清理完成")

if __name__ == "__main__":
    # 设置事件循环策略（Windows 兼容性）
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    # 运行测试
    asyncio.run(main())