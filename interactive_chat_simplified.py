#!/usr/bin/env python3
"""
交互式 Claude Agent 对话程序 (简化版)

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
from typing import Optional, Dict, Any, Callable

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src import AgentSystem
from src.session import MessageBus, SessionQuery
from src.session.utils import SessionContext


class MessageFormatter:
    """消息格式化工具类"""

    @staticmethod
    def format_content_block(block: Dict, prefix: str = "   ") -> str:
        """格式化内容块"""
        block_type = block.get('type')

        if block_type == 'text':
            text = block.get('text', '')
            if text:
                return MessageFormatter._format_long_text(text, prefix)

        elif block_type == 'tool_use':
            tool_name = block.get('name', 'unknown')
            tool_input = block.get('input', {})
            lines = [f"\n🔧 [工具调用] {tool_name}"]
            if tool_input:
                args_str = MessageFormatter._format_tool_args(tool_input)
                lines.append(f"{prefix}📋 参数: {args_str}")
            return '\n'.join(lines)

        elif block_type == 'tool_result':
            content = block.get('content', '')
            is_error = block.get('is_error', False)
            status_icon = "❌" if is_error else "✅"
            lines = [f"\n{status_icon} [工具结果] {'执行失败' if is_error else '执行完成'}"]
            if content:
                preview = MessageFormatter._truncate_content(content, 200)
                lines.append(f"{prefix}📄 结果: {preview}")
            return '\n'.join(lines)

        return ""

    @staticmethod
    def _format_long_text(text: str, prefix: str) -> str:
        """格式化长文本"""
        if len(text) <= 300:
            return f"{prefix}{text}"

        lines = []
        sentences = text.split('\n')
        current_line = ""

        for sentence in sentences:
            if len(current_line + sentence) > 300:
                if current_line:
                    lines.append(f"{prefix}{current_line.strip()}")
                current_line = sentence + "\n"
            else:
                current_line += sentence + "\n"

        if current_line:
            lines.append(f"{prefix}{current_line.strip()}")

        return '\n'.join(lines)

    @staticmethod
    def _format_tool_args(tool_input: Dict) -> str:
        """格式化工具参数"""
        if isinstance(tool_input, dict):
            return ", ".join([f"{k}={v}" for k, v in tool_input.items() if len(str(v)) < 50])
        return str(tool_input)

    @staticmethod
    def _truncate_content(content: str, max_length: int) -> str:
        """截断内容"""
        if isinstance(content, str) and len(content) > max_length:
            return content[:max_length] + "..."
        return str(content)


class MessageHandler:
    """消息处理器"""

    def create_parent_handler(self) -> Callable:
        """创建父实例消息处理器"""
        async def on_parent_message(msg):
            msg_type = msg.get('message_type', 'unknown')

            if msg_type == 'UserMessage':
                content = msg.get('data', {}).get('content', '')
                print(f"\n👤 [用户输入]: {content}")

            elif msg_type == 'AssistantMessage':
                print(f"\n🤖 [AI回复]:")
                content_blocks = msg.get('data', {}).get('content', [])
                for block in content_blocks:
                    formatted = MessageFormatter.format_content_block(block)
                    if formatted:
                        print(formatted)

            elif msg_type == 'ResultMessage':
                self._handle_result_message(msg, "")

            elif msg_type == 'SystemMessage':
                self._handle_system_message(msg)

            else:
                print(f"\n📨 [主Agent] 消息类型: {msg_type}")

        return on_parent_message

    def create_child_handler(self) -> Callable:
        """创建子实例消息处理器"""
        async def on_child_message(child_id: str, instance: str, msg):
            msg_type = msg.get('message_type', 'unknown')
            prefix = "      "  # 子实例消息缩进

            if msg_type == 'UserMessage':
                content = msg.get('data', {}).get('content', '')
                print(f"\n👤 [子实例-{instance} 用户输入]: {content}")

            elif msg_type == 'AssistantMessage':
                print(f"\n🤖 [子实例-{instance} AI回复]:")
                content_blocks = msg.get('data', {}).get('content', [])
                for block in content_blocks:
                    formatted = MessageFormatter.format_content_block(block, prefix)
                    if formatted:
                        print(formatted)

            elif msg_type == 'ResultMessage':
                self._handle_result_message(msg, f"[子实例-{instance}] ", prefix)

            elif msg_type == 'SystemMessage':
                self._handle_system_message(msg, f"[子实例-{instance}] ")

            else:
                print(f"\n📨 [子实例-{instance}] 消息类型: {msg_type}")

        return on_child_message

    def _handle_result_message(self, msg: Dict, instance_prefix: str, prefix: str = ""):
        """处理结果消息"""
        data = msg.get('data', {})
        result = data.get('result', '')
        is_error = data.get('is_error', False)
        duration_ms = data.get('duration_ms', 0)

        print(f"\n🏁 {instance_prefix}会话结束 {'执行失败' if is_error else '执行完成'}")
        print(f"{prefix}⏱️ 耗时: {duration_ms}ms")

        if result and not is_error:
            preview = MessageFormatter._truncate_content(result, 200)
            print(f"{prefix}📄 最终结果: {preview}")
        elif is_error:
            print(f"{prefix}❌ 错误: {result}")

    def _handle_system_message(self, msg: Dict, instance_prefix: str = ""):
        """处理系统消息"""
        data = msg.get('data', {})
        subtype = data.get('subtype', 'unknown')

        if subtype == 'sub_instance_started':
            child_instance = data.get('instance_name', 'unknown')
            print(f"\n🔔 {instance_prefix}系统] 子实例启动: {child_instance}")
        else:
            print(f"\n📋 {instance_prefix}系统] {subtype}")

    def create_child_started_handler(self) -> Callable:
        """创建子实例启动处理器"""
        async def on_child_started(child_id: str, instance: str):
            print(f"\n🔔 [系统] 子实例启动: {instance}")
            print(f"   🆔 子会话ID: {child_id}")

        return on_child_started


class SessionManager:
    """会话管理器"""

    def __init__(self, query: SessionQuery):
        self.query = query

    async def get_session_list(self, limit: int = 10) -> Optional[list]:
        """获取会话列表"""
        try:
            sessions = self.query.list_sessions(limit=limit)
            if not sessions:
                print("📭 暂无会话记录")
                return None

            print(f"\n📋 最近的会话列表:")
            print("-" * 80)
            print(f"{'会话ID':<25} {'状态':<10} {'开始时间':<20} {'消息数':<8} {'最后消息'}")
            print("-" * 80)

            for session in sessions:
                session_info = await self._format_session_info(session)
                print(session_info)

            print("-" * 80)
            print("💡 提示: 复制完整的会话ID来继续特定对话")
            return sessions

        except Exception as e:
            print(f"❌ 获取会话列表失败: {e}")
            return None

    async def _format_session_info(self, session: Dict) -> str:
        """格式化会话信息"""
        session_id = session.get('session_id', 'unknown')
        status = session.get('status', 'unknown')
        start_time = session.get('start_time', 'unknown')

        # 获取消息数量
        message_count = await self._get_message_count(session_id)

        # 获取最后消息预览
        last_preview = await self._get_last_message_preview(session_id)

        # 截断显示
        short_id = session_id[:22] + "..." if len(session_id) > 25 else session_id
        start_time_short = start_time[:16] if len(start_time) > 16 else start_time

        return f"{short_id:<25} {status:<10} {start_time_short:<20} {message_count:<8} {last_preview}"

    async def _get_message_count(self, session_id: str) -> int:
        """获取消息数量"""
        try:
            details = self.query.get_session_details(session_id, include_messages=True)
            if details:
                messages = details.get('messages', [])
                count = 0
                for msg in messages:
                    # 检查是否为用户或助手消息
                    if msg.get('role') in ['user', 'assistant']:
                        count += 1
                    # 检旧格式消息类型
                    elif msg.get('message_type') in ['UserMessage', 'AssistantMessage']:
                        count += 1
                return count
        except:
            pass
        return 0

    async def _get_last_message_preview(self, session_id: str) -> str:
        """获取最后消息预览"""
        try:
            details = self.query.get_session_details(session_id, include_messages=True)
            if details:
                last_message = self._extract_last_user_assistant_message(details.get('messages', []))
                if last_message:
                    content = last_message.get('content', '')
                    role = last_message.get('role', '')[:1].upper()
                    if len(content) > 40:
                        content = content[:40] + "..."
                    content = content.replace('\n', ' ')
                    return f"{role}: {content}"
        except:
            pass
        return "N/A"

    @staticmethod
    def _extract_last_user_assistant_message(messages: list) -> Optional[Dict]:
        """提取最后一条用户或助手消息（统一的消息提取逻辑）"""
        for msg in reversed(messages):
            if msg.get('role') in ['user', 'assistant']:
                return msg
            elif msg.get('message_type') == 'UserMessage':
                return {
                    'role': 'user',
                    'content': msg.get('data', {}).get('content', ''),
                    'timestamp': msg.get('timestamp', '')
                }
            elif msg.get('message_type') == 'AssistantMessage':
                content_data = msg.get('data', {}).get('content', [])
                content = ''
                if content_data and isinstance(content_data, list):
                    text_items = [item.get('text', '') for item in content_data if item.get('type') == 'text']
                    content = '\n'.join(text_items)

                return {
                    'role': 'assistant',
                    'content': content,
                    'timestamp': msg.get('timestamp', '')
                }
        return None


class FileHandler:
    """文件处理器"""

    @staticmethod
    async def read_file_as_input(file_path: str) -> Optional[str]:
        """读取文件内容作为对话输入"""
        try:
            if not os.path.isabs(file_path):
                file_path = os.path.join(os.getcwd(), file_path)

            if not os.path.exists(file_path):
                print(f"❌ 文件不存在: {file_path}")
                return None

            if not os.path.isfile(file_path):
                print(f"❌ 路径不是文件: {file_path}")
                return None

            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if not content.strip():
                print(f"⚠️ 文件为空: {file_path}")
                return None

            print(f"✅ 成功读取文件: {file_path} ({len(content)} 字符)")
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


class InteractiveChat:
    """交互式对话管理器 (简化版)"""

    def __init__(self, instance_name: str = "prompt_writer"):
        self.instance_name = instance_name
        self.message_bus = None
        self.agent = None
        self.query = None
        self.current_session_id = None
        self.last_query = None
        self.last_result = None

        # 组件
        self.message_handler = MessageHandler()
        self.session_manager = None

    async def initialize(self):
        """初始化系统"""
        print("🚀 正在初始化 Claude Agent System...")

        self.message_bus = MessageBus.from_config()
        await self.message_bus.connect()
        print("✅ 消息总线连接成功")

        self.agent = AgentSystem(self.instance_name, message_bus=self.message_bus)
        await self.agent.initialize()
        print(f"✅ {self.instance_name} 初始化完成")

        self.query = SessionQuery(self.instance_name, message_bus=self.message_bus)
        self.session_manager = SessionManager(self.query)
        print("✅ 对话系统准备就绪")

    async def start_realtime_subscription(self, session_id: str):
        """启动实时消息订阅"""
        print(f"📡 开始订阅实时消息: {session_id}")

        try:
            # 确保query对象已正确初始化
            if not self.query:
                print(f"❌ SessionQuery对象未初始化")
                return

            await self.query.subscribe(
                session_id=session_id,
                on_parent_message=self.message_handler.create_parent_handler(),
                on_child_message=self.message_handler.create_child_handler(),
                on_child_started=self.message_handler.create_child_started_handler()
            )
            print(f"✅ 订阅方法调用成功，会话ID: {session_id}")
        except Exception as e:
            print(f"❌ 订阅失败: {e}")
            import traceback
            traceback.print_exc()
            raise

    async def process_query(self, query_text: str, resume_session_id: Optional[str] = None):
        """处理查询请求"""
        print("\n" + "="*60)
        print("🤔 AI正在思考...")
        print("="*60)

        # 清理之前的订阅
        if self.query:
            await self.query.stop()
            await asyncio.sleep(0.1)

        # 🎯 统一处理：先启动查询任务，再等待session_id并建立订阅
        query_task = asyncio.create_task(
            self.agent.query_text(query_text, resume_session_id=resume_session_id)
        )

        # 🎯 完全统一：无论新对话还是继续对话，都使用完全相同的逻辑
        # 统一等待SessionContext被QueryStreamManager设置
        await asyncio.sleep(0.1)  # 给QueryStreamManager.initialize()一点启动时间

        for attempt in range(20):
            await asyncio.sleep(0.1)
            current_session = SessionContext.get_current_session()

            # 调试信息
            print(f"🔍 尝试 {attempt + 1}/20: SessionContext={current_session}, 传入的resume_session_id={resume_session_id}")

            if current_session:
                session_id = current_session
                if resume_session_id:
                    print(f"🔄 继续会话: {session_id}")
                else:
                    print(f"🆕 新会话创建: {session_id}")
                break

        # 建立订阅 - 统一的订阅逻辑
        if session_id:
            self.current_session_id = session_id
            print(f"🔧 准备建立订阅，会话ID: {session_id}")

            # 创建新的SessionQuery实例
            self.query = SessionQuery(self.instance_name, message_bus=self.message_bus)
            print(f"🔧 SessionQuery实例已创建")

            # 等待一小段时间确保session已完全初始化
            await asyncio.sleep(0.2)

            await self.start_realtime_subscription(session_id)
            print(f"📡 已订阅实时消息: {session_id}")
        else:
            print("❌ 未能获取会话ID，无法订阅实时消息")
            print(f"🔍 调试信息: resume_session_id={resume_session_id}")
            # 再次检查SessionContext
            final_check = SessionContext.get_current_session()
            print(f"🔍 最终检查SessionContext: {final_check}")

        try:
            result = await query_task
            print("\n" + "="*60)
            print(f"✅ 查询完成！")
            print(f"📋 会话ID: {result.session_id}")
            print(f"💡 回复长度: {len(result.result) if result.result else 0} 字符")
            if result.result:
                print(f"📝 回复内容:\n{result.result}")
            print("="*60)

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
        print("1. 继续当前对话")
        print("2. 开始新对话")
        print("3. 查看会话信息")
        print("4. 继续指定会话")
        print("5. 重新运行最后一个查询")
        print("6. 退出程序")
        print("-"*40)
        print("💡 提示: 直接按回车继续当前对话")

        while True:
            choice = input("请输入选择 (1-6，默认为1): ").strip()
            if not choice:
                return '1'
            if choice in ['1', '2', '3', '4', '5', '6']:
                return choice
            print("⚠️ 无效选择，请输入 1-6 或直接回车")

    async def show_session_info(self):
        """显示当前会话信息"""
        if not self.current_session_id:
            print("📭 当前没有活跃会话")
            return

        print(f"\n📊 当前会话信息:")
        print(f"会话ID: {self.current_session_id}")

        try:
            details = self.query.get_session_details(self.current_session_id, include_messages=True)
            if details:
                print(f"状态: {details.get('status', 'unknown')}")
                print(f"开始时间: {details.get('start_time', 'unknown')}")
                print(f"消息数量: {len(details.get('messages', []))}")

                messages = details.get('messages', [])
                if messages:
                    print("\n📜 最近的消息:")
                    for msg in messages[-3:]:
                        role = msg.get('role', 'unknown')
                        content = msg.get('content', '')
                        if len(content) > 50:
                            content = content[:50] + "..."
                        print(f"  {role}: {content}")
        except Exception as e:
            print(f"❌ 获取会话信息失败: {e}")

    def show_help(self):
        """显示帮助信息"""
        print("\n" + "="*50)
        print("📚 可用命令:")
        print("  help    - 显示此帮助信息")
        print("  info    - 查看当前会话信息")
        print("  read    - 读取文件内容并作为对话输入")
        print("  clear   - 清空屏幕")
        print("  exit    - 退出程序")
        print("\n🔄 继续对话功能:")
        print("  选项 1  - 继续当前对话（默认）")
        print("  选项 4  - 通过会话ID继续指定会话")
        print("="*50)

    async def show_welcome_menu(self) -> Optional[str]:
        """显示欢迎菜单"""
        print("\n" + "="*50)
        print("🎉 Claude Agent 交互式对话程序")
        print("="*50)
        print("请选择您想要进行的操作：")
        print("1. 开始新对话")
        print("2. 继续指定会话")
        print("3. 查看最近会话列表")
        print("4. 查看帮助信息")
        print("5. 退出程序")
        print("-"*50)

        while True:
            choice = input("请输入选择 (1-5): ").strip()

            if choice == '1':
                print("\n" + "="*60)
                print("📊 新对话已开始，请输入您的问题：")
                print("="*60)
                return None
            elif choice == '2':
                return await self.resume_session_by_id()
            elif choice == '3':
                await self.session_manager.get_session_list()
                return await self.show_welcome_menu()
            elif choice == '4':
                self.show_help()
                return await self.show_welcome_menu()
            elif choice == '5':
                print("👋 再见！")
                sys.exit(0)
            else:
                print("⚠️ 无效选择，请输入 1-5")

    async def resume_session_by_id(self) -> Optional[str]:
        """通过会话ID继续对话"""
        print("\n🔍 继续指定会话")
        print("💡 提示: 输入 'list' 查看最近的会话列表")

        while True:
            session_id = input("请输入会话ID (或 'list' 查看列表, 'cancel' 取消): ").strip()

            if session_id.lower() == 'cancel':
                return None
            elif session_id.lower() == 'list':
                await self.session_manager.get_session_list()
                continue
            elif not session_id:
                print("❌ 会话ID不能为空")
                continue

            # 验证会话并显示最后消息
            if await self._validate_and_show_session(session_id):
                confirm = input("\n是否继续此会话？(y/N): ").strip().lower()
                if confirm in ['y', 'yes']:
                    return session_id
                else:
                    continue

    async def _validate_and_show_session(self, session_id: str) -> bool:
        """验证并显示会话信息"""
        try:
            details = self.query.get_session_details(session_id, include_messages=True)
            if not details:
                print(f"❌ 会话不存在: {session_id}")
                return False

            print(f"✅ 找到会话: {session_id}")

            # 显示最后一条消息
            last_message = self._get_last_user_assistant_message(details.get('messages', []))

            if last_message:
                print("\n📜 该会话的最后一条消息:")
                print(f"👤 [{last_message['role'].upper()}] {last_message.get('timestamp', '')}")
                print("-" * 60)

                content = last_message.get('content', '')
                if content:
                    # 智能换行显示，保持良好格式
                    print(f"   {content}")
                else:
                    print("   [消息内容为空]")

                print("-" * 60)
            else:
                print("📭 该会话暂无消息记录")

            return True

        except Exception as e:
            print(f"❌ 验证会话时出错: {e}")
            return False

    def _get_last_user_assistant_message(self, messages: list) -> Optional[Dict]:
        """获取最后一条用户或助手消息"""
        return SessionManager._extract_last_user_assistant_message(messages)

    async def handle_user_input(self, user_input: str) -> bool:
        """处理用户输入，返回是否继续主循环"""
        user_input = user_input.strip()

        # 处理特殊命令
        if user_input.lower() in ['exit', 'quit', '退出']:
            return False
        elif user_input.lower() == 'help':
            self.show_help()
            return True
        elif user_input.lower() == 'clear':
            os.system('cls' if os.name == 'nt' else 'clear')
            return True
        elif user_input.lower() == 'info':
            await self.show_session_info()
            return True
        elif user_input.lower().startswith('read '):
            await self._handle_read_command(user_input)
            return True
        elif user_input.lower() == 'read':
            print("❌ 请指定文件路径。用法: read 文件路径")
            return True

        # 处理查询
        await self._handle_query(user_input)
        return await self._handle_post_query_actions()

    async def _handle_read_command(self, user_input: str):
        """处理read命令"""
        file_path = user_input[5:].strip()
        if not file_path:
            print("❌ 请指定文件路径。用法: read 文件路径")
            return

        file_content = await FileHandler.read_file_as_input(file_path)
        if file_content:
            await self._handle_query(file_content)
            await self._handle_post_query_actions()

    async def _handle_query(self, query_text: str):
        """处理查询"""
        self.last_query = query_text
        result = await self.process_query(query_text, self.current_session_id)

        if result:
            self.last_result = result
            self.current_session_id = result.session_id

    async def _handle_post_query_actions(self) -> bool:
        """处理查询后的操作，返回是否继续主循环"""
        choice = await self.ask_for_action()

        if choice == '1':
            # 继续当前对话
            print("📝 继续当前对话...")
            return True
        elif choice == '2':
            # 开始新对话
            print("🆕 开始新对话...")
            self.current_session_id = None
            print("\n" + "="*60)
            print("📊 新对话已开始，请输入您的问题：")
            print("="*60)
            return True
        elif choice == '3':
            # 查看会话信息
            await self.show_session_info()
            return True
        elif choice == '4':
            # 继续指定会话
            return await self._handle_resume_session()
        elif choice == '5':
            # 重新运行最后一个查询
            await self._handle_rerun_last_query()
            return True
        elif choice == '6':
            # 退出程序
            return False

        return True

    async def _handle_resume_session(self) -> bool:
        """处理继续指定会话"""
        resume_session_id = await self.resume_session_by_id()
        if resume_session_id:
            print(f"🔄 切换到会话: {resume_session_id}")
            print("📝 请输入您的新消息继续对话:")
            print("💡 提示: 直接输入消息即可继续此会话")

            new_message = input("> ").strip()
            if new_message:
                await self._handle_query(new_message)
                return await self._handle_post_query_actions()
        return True

    async def _handle_rerun_last_query(self):
        """处理重新运行查询"""
        if self.last_query:
            print(f"🔄 重新运行查询: {self.last_query}")
            result = await self.process_query(self.last_query, self.current_session_id)
            if result:
                self.current_session_id = result.session_id
        else:
            print("📭 没有可重新运行的查询")

    async def run(self):
        """运行主对话循环"""
        try:
            await self.initialize()

            # 显示欢迎菜单
            initial_session_id = await self.show_welcome_menu()
            self.current_session_id = initial_session_id

            while True:
                if self.current_session_id:
                    print(f"\n🏷️  当前会话: {self.current_session_id}")

                print("\n💭 请输入您的问题:")
                print("💡 提示: 输入 'help' 查看可用命令")
                user_input = input("> ").strip()

                if not user_input:
                    continue

                should_continue = await self.handle_user_input(user_input)
                if not should_continue:
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
    instance_name = sys.argv[1] if len(sys.argv) > 1 else "prompt_writer"
    chat = InteractiveChat(instance_name)
    await chat.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 程序已退出")