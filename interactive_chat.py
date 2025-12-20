#!/usr/bin/env python3
"""
交互式 Claude Agent 对话程序

支持持续对话，可以：
- 继续当前对话
- 开始新的对话
- 实时查看消息流
- 自动追踪子实例消息
"""

import asyncio
import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src import AgentSystem
from src.session import MessageBus, SessionQuery
from src.session.utils import SessionContext


class InteractiveChat:
    """交互式对话管理器"""

    def __init__(self, instance_name: str = "prompt_writer"):
        self.instance_name = instance_name
        self.message_bus = None
        self.agent = None
        self.current_session_id = None
        self.query = None
        self.message_queue = asyncio.Queue()
        self.last_query = None
        self.last_result = None

    async def initialize(self):
        """初始化系统"""
        print("🚀 正在初始化 Claude Agent System...")

        # 创建消息总线
        self.message_bus = MessageBus.from_config()
        await self.message_bus.connect()
        print("✅ 消息总线连接成功")

        # 创建主Agent
        self.agent = AgentSystem(self.instance_name, message_bus=self.message_bus)
        await self.agent.initialize()
        print(f"✅ {self.instance_name} 初始化完成")

        # 创建SessionQuery实例
        self.query = SessionQuery(self.instance_name, message_bus=self.message_bus)
        print("✅ 对话系统准备就绪")

    async def start_realtime_subscription(self, session_id: str):
        """启动实时消息订阅"""
        print(f"📡 开始订阅实时消息: {session_id}")

        async def on_parent_message(msg):
            """处理主Agent消息"""
            msg_type = msg.get('message_type', 'unknown')
            timestamp = msg.get('timestamp', '')

            if msg_type == 'UserMessage':
                content = msg.get('data', {}).get('content', '')
                print(f"\n👤 [用户输入]: {content}")

            elif msg_type == 'AssistantMessage':
                content_blocks = msg.get('data', {}).get('content', [])
                print(f"\n🤖 [AI回复]:")

                # 处理内容块
                for block in content_blocks:
                    block_type = block.get('type')

                    if block_type == 'text':
                        text = block.get('text', '')
                        if text:
                            # 分段显示长内容，提高可读性
                            if len(text) > 300:
                                sentences = text.split('\n')
                                current_line = ""
                                for sentence in sentences:
                                    if len(current_line + sentence) > 300:
                                        if current_line:
                                            print(f"   {current_line.strip()}")
                                        current_line = sentence + "\n"
                                    else:
                                        current_line += sentence + "\n"
                                if current_line:
                                    print(f"   {current_line.strip()}")
                            else:
                                print(f"   {text}")

                    elif block_type == 'tool_use':
                        tool_name = block.get('name', 'unknown')
                        tool_input = block.get('input', {})
                        print(f"\n🔧 [工具调用] {tool_name}")
                        if tool_input:
                            # 格式化参数显示
                            if isinstance(tool_input, dict):
                                args_str = ", ".join([f"{k}={v}" for k, v in tool_input.items() if len(str(v)) < 50])
                                print(f"   📋 参数: {args_str}")
                            else:
                                print(f"   📋 参数: {tool_input}")

                    elif block_type == 'tool_result':
                        content = block.get('content', '')
                        is_error = block.get('is_error', False)
                        status_icon = "❌" if is_error else "✅"
                        print(f"\n{status_icon} [工具结果] {'执行失败' if is_error else '执行完成'}")
                        if content and isinstance(content, str):
                            if len(content) > 200:
                                print(f"   📄 结果: {content[:200]}...")
                            else:
                                print(f"   📄 结果: {content}")
                        elif content:
                            print(f"   📄 结果: {content}")

            elif msg_type == 'ResultMessage':
                data = msg.get('data', {})
                result = data.get('result', '')
                is_error = data.get('is_error', False)
                duration_ms = data.get('duration_ms', 0)

                print(f"\n🏁 [会话结束] {'执行失败' if is_error else '执行完成'}")
                print(f"   ⏱️ 耗时: {duration_ms}ms")
                if result and not is_error:
                    if len(result) > 200:
                        print(f"   📄 最终结果: {result[:200]}...")
                    else:
                        print(f"   📄 最终结果: {result}")
                elif is_error:
                    print(f"   ❌ 错误: {result}")

            elif msg_type == 'SystemMessage':
                data = msg.get('data', {})
                subtype = data.get('subtype', 'unknown')
                if subtype == 'sub_instance_started':
                    child_instance = data.get('instance_name', 'unknown')
                    print(f"\n🔔 [系统] 子实例启动: {child_instance}")
                else:
                    print(f"\n📋 [系统] {subtype}")

            else:
                print(f"\n📨 [主Agent] 消息类型: {msg_type}")
                # 调试时可以取消下面的注释来查看完整的消息结构
                # print(f"   详情: {str(msg)[:200]}...")

        async def on_child_message(child_id: str, instance: str, msg):
            """处理子实例消息"""
            msg_type = msg.get('message_type', 'unknown')
            timestamp = msg.get('timestamp', '')

            if msg_type == 'UserMessage':
                content = msg.get('data', {}).get('content', '')
                print(f"\n👤 [子实例-{instance} 用户输入]: {content}")

            elif msg_type == 'AssistantMessage':
                content_blocks = msg.get('data', {}).get('content', [])
                print(f"\n🤖 [子实例-{instance} AI回复]:")

                # 处理内容块
                for block in content_blocks:
                    block_type = block.get('type')

                    if block_type == 'text':
                        text = block.get('text', '')
                        if text:
                            # 分段显示长内容，提高可读性
                            if len(text) > 300:
                                sentences = text.split('\n')
                                current_line = ""
                                for sentence in sentences:
                                    if len(current_line + sentence) > 300:
                                        if current_line:
                                            print(f"      {current_line.strip()}")
                                        current_line = sentence + "\n"
                                    else:
                                        current_line += sentence + "\n"
                                if current_line:
                                    print(f"      {current_line.strip()}")
                            else:
                                print(f"      {text}")

                    elif block_type == 'tool_use':
                        tool_name = block.get('name', 'unknown')
                        tool_input = block.get('input', {})
                        print(f"\n🔧 [子实例-{instance} 工具调用] {tool_name}")
                        if tool_input:
                            if isinstance(tool_input, dict):
                                args_str = ", ".join([f"{k}={v}" for k, v in tool_input.items() if len(str(v)) < 50])
                                print(f"         📋 参数: {args_str}")
                            else:
                                print(f"         📋 参数: {tool_input}")

                    elif block_type == 'tool_result':
                        content = block.get('content', '')
                        is_error = block.get('is_error', False)
                        status_icon = "❌" if is_error else "✅"
                        print(f"\n{status_icon} [子实例-{instance} 工具结果] {'执行失败' if is_error else '执行完成'}")
                        if content and isinstance(content, str):
                            if len(content) > 200:
                                print(f"         📄 结果: {content[:200]}...")
                            else:
                                print(f"         📄 结果: {content}")
                        elif content:
                            print(f"         📄 结果: {content}")

            elif msg_type == 'ResultMessage':
                data = msg.get('data', {})
                result = data.get('result', '')
                is_error = data.get('is_error', False)
                duration_ms = data.get('duration_ms', 0)

                print(f"\n🏁 [子实例-{instance} 会话结束] {'执行失败' if is_error else '执行完成'}")
                print(f"         ⏱️ 耗时: {duration_ms}ms")
                if result and not is_error:
                    if len(result) > 200:
                        print(f"         📄 最终结果: {result[:200]}...")
                    else:
                        print(f"         📄 最终结果: {result}")
                elif is_error:
                    print(f"         ❌ 错误: {result}")

            elif msg_type == 'SystemMessage':
                data = msg.get('data', {})
                subtype = data.get('subtype', 'unknown')
                if subtype == 'sub_instance_started':
                    child_instance = data.get('instance_name', 'unknown')
                    print(f"\n🔔 [子实例-{instance} 系统] 子实例启动: {child_instance}")
                else:
                    print(f"\n📋 [子实例-{instance} 系统] {subtype}")

            else:
                print(f"\n📨 [子实例-{instance}] 消息类型: {msg_type}")
                # 调试时可以取消下面的注释来查看完整的消息结构
                # print(f"      详情: {str(msg)[:200]}...")

        async def on_child_started(child_id: str, instance: str):
            """子实例启动通知"""
            print(f"\n🔔 [系统] 子实例启动: {instance}")
            print(f"   🆔 子会话ID: {child_id}")

        # 开始订阅
        await self.query.subscribe(
            session_id=session_id,
            on_parent_message=on_parent_message,
            on_child_message=on_child_message,
            on_child_started=on_child_started
        )

    async def process_query(self, query_text: str, resume_session_id: Optional[str] = None):
        """处理查询请求"""
        print("\n" + "="*60)
        print("🤔 AI正在思考...")
        print("="*60)

        # 清理之前的订阅（如果有）
        if self.query:
            await self.query.stop()
            self.query = None

        # 等待一小段时间确保清理完成
        await asyncio.sleep(0.1)

        # 启动查询任务
        query_task = asyncio.create_task(
            self.agent.query_text(query_text, resume_session_id=resume_session_id)
        )

        # 获取 session_id
        session_id = None

        # 如果是 resume，直接使用已有的 session_id
        if resume_session_id:
            session_id = resume_session_id
            print(f"🔄 继续会话: {session_id}")
        else:
            # 新会话：等待session创建，使用更长的等待时间并多次尝试
            for attempt in range(10):  # 最多尝试10次，每次间隔100ms
                await asyncio.sleep(0.1)
                session_id = SessionContext.get_current_session()
                if session_id:
                    print(f"🆕 新会话创建: {session_id}")
                    break

        if session_id:
            self.current_session_id = session_id

            # 创建新的SessionQuery实例
            self.query = SessionQuery(self.instance_name, message_bus=self.message_bus)

            # 立即开始订阅（在查询可能还在运行时）
            await self.start_realtime_subscription(session_id)
            print(f"📡 已订阅实时消息: {session_id}")
        else:
            print("⚠️ 未能获取会话ID，无法订阅实时消息")

        try:
            # 等待查询完成
            result = await query_task
            print("\n" + "="*60)
            print(f"✅ 查询完成！")
            print(f"📋 会话ID: {result.session_id}")
            print(f"💡 回复长度: {len(result.result) if result.result else 0} 字符")
            if result.result:
                print(f"📝 回复内容:\n{result.result}")
            print("="*60)

            # 确保订阅的session_id和实际返回的session_id一致
            if result.session_id != session_id:
                print(f"⚠️ Session ID不匹配: 订阅={session_id}, 实际={result.session_id}")

            return result

        except Exception as e:
            print(f"❌ 查询失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def ask_for_action(self) -> str:
        """询问用户下一步操作"""
        print("\n" + "-"*40)
        print("请选择下一步操作：")
        print("1. 继续当前对话 (默认)")
        print("2. 开始新对话")
        print("3. 查看会话信息")
        print("4. 重新运行最后一个查询")
        print("5. 退出程序")
        print("-"*40)
        print("💡 提示: 直接按回车继续当前对话")

        while True:
            choice = input("请输入选择 (1-5，默认为1): ").strip()
            if not choice:  # 默认继续对话
                return '1'
            if choice in ['1', '2', '3', '4', '5']:
                return choice
            print("⚠️ 无效选择，请输入 1-5 或直接回车")

    async def show_session_info(self):
        """显示当前会话信息"""
        if not self.current_session_id:
            print("📭 当前没有活跃会话")
            return

        print("\n📊 当前会话信息:")
        print(f"会话ID: {self.current_session_id}")

        try:
            # 获取会话详情
            details = await self.query.get_session_details(self.current_session_id)
            if details:
                print(f"状态: {details.get('status', 'unknown')}")
                print(f"开始时间: {details.get('start_time', 'unknown')}")
                print(f"消息数量: {len(details.get('messages', []))}")

                # 显示最近的消息
                messages = details.get('messages', [])
                if messages:
                    print("\n📜 最近的消息:")
                    for msg in messages[-3:]:  # 显示最近3条消息
                        role = msg.get('role', 'unknown')
                        content = msg.get('content', '')
                        if len(content) > 50:
                            content = content[:50] + "..."
                        print(f"  {role}: {content}")
        except Exception as e:
            print(f"❌ 获取会话信息失败: {e}")

    async def read_file_content(self, file_path: str) -> str:
        """读取文件内容（用于显示）"""
        try:
            # 支持相对路径和绝对路径
            if not os.path.isabs(file_path):
                file_path = os.path.join(os.getcwd(), file_path)

            # 检查文件是否存在
            if not os.path.exists(file_path):
                return f"❌ 文件不存在: {file_path}"

            # 检查是否为文件
            if not os.path.isfile(file_path):
                return f"❌ 路径不是文件: {file_path}"

            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            return f"📄 文件内容 ({file_path}):\n{'-'*40}\n{content}\n{'-'*40}"

        except UnicodeDecodeError:
            return f"❌ 文件编码错误，无法读取: {file_path}"
        except PermissionError:
            return f"❌ 权限不足，无法读取: {file_path}"
        except Exception as e:
            return f"❌ 读取文件时出错: {file_path}, 错误: {e}"

    async def read_file_content_as_input(self, file_path: str) -> Optional[str]:
        """读取文件内容（作为对话输入）"""
        try:
            # 支持相对路径和绝对路径
            if not os.path.isabs(file_path):
                file_path = os.path.join(os.getcwd(), file_path)

            # 检查文件是否存在
            if not os.path.exists(file_path):
                print(f"❌ 文件不存在: {file_path}")
                return None

            # 检查是否为文件
            if not os.path.isfile(file_path):
                print(f"❌ 路径不是文件: {file_path}")
                return None

            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if not content.strip():
                print(f"⚠️ 文件为空: {file_path}")
                return None

            print(f"✅ 成功读取文件: {file_path} ({len(content)} 字符)")
            # 添加文件路径信息，让AI知道内容来源
            return f"请分析以下文件内容（文件路径: {file_path}）：\n\n{content}"

        except UnicodeDecodeError:
            print(f"❌ 文件编码错误，无法读取: {file_path}")
            return None
        except PermissionError:
            print(f"❌ 权限不足，无法读取: {file_path}")
            return None
        except Exception as e:
            print(f"❌ 读取文件时出错: {file_path}, 错误: {e}")
            return None

    def show_help(self):
        """显示帮助信息"""
        print("\n" + "="*50)
        print("📚 可用命令:")
        print("  help    - 显示此帮助信息")
        print("  info    - 查看当前会话信息")
        print("  read    - 读取文件内容并作为对话输入 (用法: read 文件路径)")
        print("  clear   - 清空屏幕")
        print("  exit    - 退出程序")
        print("\n💡 提示:")
        print("  - 'read' 命令会将文件内容发送给AI进行分析")
        print("  - 支持相对路径和绝对路径")
        print("  - 会自动添加文件路径信息供AI参考")
        print("="*50)

    async def run(self):
        """运行主对话循环"""
        print("🎉 Claude Agent 交互式对话程序")
        print("💡 输入您的问题，AI将实时回复")
        print("🔄 支持继续对话和开始新对话")
        print("⚡ 实时显示所有AI处理过程")

        try:
            await self.initialize()

            # 欢迎消息
            print("\n" + "="*60)
            print("🎊 欢迎使用 Claude Agent 交互式对话！")
            print("📝 请输入您的第一个问题开始对话：")
            print("="*60)

            while True:
                # 获取用户输入
                if self.current_session_id:
                    print(f"\n🏷️  当前会话: {self.current_session_id}")

                print("\n💭 请输入您的问题:")
                print("💡 提示: 输入 'help' 查看可用命令")
                user_input = input("> ").strip()

                if not user_input:
                    continue

                # 处理特殊命令
                if user_input.lower() in ['exit', 'quit', '退出']:
                    break
                elif user_input.lower() == 'help':
                    self.show_help()
                    continue
                elif user_input.lower() == 'clear':
                    os.system('cls' if os.name == 'nt' else 'clear')
                    continue
                elif user_input.lower() == 'info':
                    await self.show_session_info()
                    continue
                elif user_input.lower().startswith('read '):
                    # 处理读取文件命令
                    file_path = user_input[5:].strip()  # 移除 'read ' 前缀
                    if not file_path:
                        print("❌ 请指定文件路径。用法: read 文件路径")
                        continue

                    # 读取文件内容
                    file_content = await self.read_file_content_as_input(file_path)
                    if file_content:
                        # 将文件内容作为对话输入处理
                        print(f"📄 已读取文件内容，将作为对话输入处理...")
                        result = await self.process_query(file_content, self.current_session_id)
                        if result:
                            self.last_result = result
                            self.current_session_id = result.session_id

                            # 询问下一步操作
                            choice = await self.ask_for_action()

                            if choice == '1':
                                # 继续当前对话
                                print("📝 继续当前对话...")
                                continue
                            elif choice == '2':
                                # 开始新对话
                                print("🆕 开始新对话...")
                                self.current_session_id = None
                                print("\n" + "="*60)
                                print("📊 新对话已开始，请输入您的问题：")
                                print("="*60)
                            elif choice == '3':
                                # 查看会话信息
                                await self.show_session_info()
                                continue
                            elif choice == '4':
                                # 重新运行最后一个查询
                                if self.last_query:
                                    print(f"🔄 重新运行查询: {self.last_query}")
                                    result = await self.process_query(self.last_query, self.current_session_id)
                                    if result:
                                        self.current_session_id = result.session_id
                                else:
                                    print("📭 没有可重新运行的查询")
                                continue
                            elif choice == '5':
                                # 退出程序
                                print("👋 再见！")
                                break
                    continue
                elif user_input.lower() == 'read':
                    print("❌ 请指定文件路径。用法: read 文件路径")
                    continue

                # 处理查询
                self.last_query = user_input
                result = await self.process_query(user_input, self.current_session_id)

                if result:
                    self.last_result = result
                    self.current_session_id = result.session_id

                    # 询问下一步操作
                    choice = await self.ask_for_action()

                    if choice == '1':
                        # 继续当前对话
                        print("📝 继续当前对话...")
                        continue
                    elif choice == '2':
                        # 开始新对话
                        print("🆕 开始新对话...")
                        self.current_session_id = None
                        print("\n" + "="*60)
                        print("📊 新对话已开始，请输入您的问题：")
                        print("="*60)
                    elif choice == '3':
                        # 查看会话信息
                        await self.show_session_info()
                        continue
                    elif choice == '4':
                        # 重新运行最后一个查询
                        if self.last_query:
                            print(f"🔄 重新运行查询: {self.last_query}")
                            result = await self.process_query(self.last_query, self.current_session_id)
                            if result:
                                self.current_session_id = result.session_id
                        else:
                            print("📭 没有可重新运行的查询")
                        continue
                    elif choice == '5':
                        # 退出程序
                        print("👋 再见！")
                        break

        except KeyboardInterrupt:
            print("\n👋 用户中断，再见！")
        except Exception as e:
            print(f"❌ 程序错误: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await self.cleanup()

    async def cleanup(self):
        """清理资源"""
        print("\n🧹 正在清理资源...")
        try:
            if self.query:
                await self.query.stop()
            if self.agent:
                self.agent.cleanup()
            if self.message_bus:
                await self.message_bus.close()
            print("✅ 资源清理完成")
        except Exception as e:
            print(f"⚠️ 清理资源时出错: {e}")


async def main():
    """主函数"""
    # 可以通过命令行参数指定实例名称
    instance_name = sys.argv[1] if len(sys.argv) > 1 else "prompt_writer"

    chat = InteractiveChat(instance_name)
    await chat.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 程序已退出")