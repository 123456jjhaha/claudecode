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
import json
from pathlib import Path
from typing import Optional, Dict, Any, Callable

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src import AgentSystem
from src.session import MessageBus, SessionQuery
from src.session.utils import SessionContext


class MessageFormatter:
    """消息格式化工具类 - 简化输出，更友好的用户体验"""

    @staticmethod
    def format_content_block(block: Dict, prefix: str = "   ") -> str:
        """格式化内容块 - 简化版本"""
        block_type = block.get('type')

        if block_type == 'text':
            text = block.get('text', '')
            if text:
                return MessageFormatter._format_text_content(text, prefix)

        elif block_type == 'tool_use':
            # 简化工具调用显示
            tool_name = block.get('name', 'unknown')
            return f"\n🔧 正在使用: {MessageFormatter._format_tool_name(tool_name)}"

        elif block_type == 'tool_result':
            # 简化工具结果显示
            content = block.get('content', '')
            is_error = block.get('is_error', False)

            if is_error:
                return f"\n❌ 操作失败: {MessageFormatter._extract_error_message(content)}"
            else:
                # 成功时只显示关键信息
                preview = MessageFormatter._extract_success_preview(content)
                if preview:
                    return f"\n✅ {preview}"
                return "\n✅ 操作完成"

        return ""

    @staticmethod
    def _format_text_content(text: str, prefix: str) -> str:
        """格式化文本内容 - 自动换行，保持可读性"""
        if not text.strip():
            return ""

        # 清理文本
        text = text.strip()

        # 如果文本较短，直接返回
        if len(text) <= 200:
            return f"{prefix}{text}"

        # 长文本分段显示，保持良好格式
        lines = []
        paragraphs = text.split('\n\n')

        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue

            # 如果段落太长，按句子分割
            if len(paragraph) > 300:
                sentences = paragraph.split('。')
                current_line = f"{prefix}"

                for sentence in sentences:
                    sentence = sentence.strip()
                    if not sentence:
                        continue

                    if len(current_line) + len(sentence) > 280:
                        if current_line != prefix:
                            lines.append(current_line)
                        current_line = f"{prefix}{sentence}。"
                    else:
                        current_line += f"{sentence}。"

                if current_line != prefix:
                    lines.append(current_line)
            else:
                lines.append(f"{prefix}{paragraph}")

        return '\n'.join(lines)

    @staticmethod
    def _format_tool_name(tool_name: str) -> str:
        """格式化工具名称 - 显示更友好的名称"""
        # 移除常见前缀
        if tool_name.startswith('mcp__'):
            parts = tool_name.split('__')
            if len(parts) >= 3:
                return f"{parts[1].replace('_', ' ').title()} - {parts[2].replace('_', ' ').title()}"

        # 替换下划线为空格，首字母大写
        return tool_name.replace('_', ' ').title()

    @staticmethod
    def _extract_error_message(content: str) -> str:
        """提取错误信息的关键部分"""
        if isinstance(content, dict):
            return content.get('message', str(content))

        if isinstance(content, str):
            # 尝试提取有用信息
            lines = content.split('\n')
            for line in lines:
                if 'error' in line.lower() or 'failed' in line.lower():
                    return line.strip()
            return content[:100] + "..." if len(content) > 100 else content

        return str(content)[:100]

    @staticmethod
    def _extract_success_preview(content: str) -> str:
        """提取成功结果的预览"""
        if not content:
            return ""

        if isinstance(content, dict):
            # 尝试提取最有用的信息
            if 'result' in content:
                return MessageFormatter._extract_success_preview(content['result'])
            if 'data' in content:
                return MessageFormatter._extract_success_preview(content['data'])
            if 'message' in content:
                return content['message']
            return "操作成功完成"

        if isinstance(content, str):
            # 清理和截断
            content = content.strip()
            if not content:
                return ""

            # 移除多余的空白和换行
            content = ' '.join(content.split())

            # 智能截断
            if len(content) <= 80:
                return content
            elif len(content) <= 200:
                return content + "..."
            else:
                # 尝试在句子边界截断
                sentences = content.split('。')
                if sentences:
                    first_sentence = sentences[0].strip()
                    if len(first_sentence) > 20:
                        return first_sentence + "..."
                return content[:80] + "..."

        return ""

    @staticmethod
    def _format_tool_args(tool_input: Dict) -> str:
        """格式化工具参数 - 简化显示"""
        if not isinstance(tool_input, dict):
            return str(tool_input)

        # 只显示重要参数，隐藏敏感信息
        important_keys = ['query', 'text', 'content', 'path', 'file_path', 'url']
        result_parts = []

        for key, value in tool_input.items():
            if any(important in key.lower() for important in important_keys):
                value_str = str(value)
                if len(value_str) > 50:
                    value_str = value_str[:50] + "..."
                result_parts.append(f"{key}: {value_str}")

        if result_parts:
            return ", ".join(result_parts)
        elif len(tool_input) <= 3:
            # 如果参数不多，显示所有
            return ", ".join([f"{k}: {str(v)[:30]}" for k, v in list(tool_input.items())[:2]])
        else:
            return f"{len(tool_input)} 个参数"

    @staticmethod
    def _truncate_content(content: str, max_length: int) -> str:
        """截断内容 - 智能截断"""
        if not isinstance(content, str):
            return str(content)[:max_length]

        if len(content) <= max_length:
            return content

        # 尝试在单词边界截断
        truncated = content[:max_length]
        last_space = truncated.rfind(' ')
        if last_space > max_length * 0.8:  # 如果最后一个空字位置不太靠前
            truncated = truncated[:last_space]

        return truncated + "..."

    @staticmethod
    def _format_user_message(content: str) -> str:
        """格式化用户消息 - 处理工具结果等复杂内容"""
        if not content:
            return ""

        # 尝试解析为JSON，如果是工具结果列表
        try:
            if content.startswith('[') and content.endswith(']'):
                tool_results = json.loads(content)
                if isinstance(tool_results, list):
                    return MessageFormatter._format_tool_results_for_user(tool_results)
        except (json.JSONDecodeError, Exception):
            pass

        # 如果不是工具结果，直接返回
        return content

    @staticmethod
    def _format_tool_results_for_user(tool_results: list) -> str:
        """为用户格式化工具结果列表"""
        if not tool_results:
            return ""

        formatted_parts = []

        for result in tool_results:
            if not isinstance(result, dict):
                continue

            result_type = result.get('type')
            content = result.get('content')

            if result_type == 'tool_result' and content:
                # 提取有用的文本内容
                text_content = MessageFormatter._extract_text_from_tool_result(content)
                if text_content:
                    formatted_parts.append(text_content)

        # 如果有多个结果，用换行连接
        if formatted_parts:
            return '\n'.join(formatted_parts)

        # 如果无法解析，返回简单的描述
        return f"[工具执行完成，返回了 {len(tool_results)} 个结果]"

    @staticmethod
    def _extract_text_from_tool_result(content) -> str:
        """从工具结果中提取文本内容"""
        if isinstance(content, str):
            return MessageFormatter._extract_text_from_json_string(content)

        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get('type') == 'text':
                    text_parts.append(MessageFormatter._extract_text_from_json_string(item.get('text', '')))
                elif isinstance(item, str):
                    text_parts.append(item[:100] + "..." if len(item) > 100 else item)
            return '\n'.join(text_parts) if text_parts else ""

        if isinstance(content, dict):
            # 尝试提取有用的字段
            useful_fields = ['result', 'data', 'message', 'text', 'content']
            for field in useful_fields:
                if field in content:
                    value = content[field]
                    if isinstance(value, str):
                        return MessageFormatter._extract_text_from_json_string(value)
                    elif isinstance(value, (list, dict)):
                        return str(value)[:100] + "..." if len(str(value)) > 100 else str(value)

        return str(content)[:100] + "..." if len(str(content)) > 100 else str(content)

    @staticmethod
    def _extract_text_from_json_string(json_str: str) -> str:
        """从JSON字符串中提取有用的文本"""
        try:
            data = json.loads(json_str)

            # 如果包含搜索结果，提取关键信息
            if isinstance(data, dict):
                # 处理地理位置搜索结果
                if 'pois' in data:
                    pois = data.get('pois', [])
                    if pois:
                        # 显示前几个POI的名称
                        poi_names = [poi.get('name', '') for poi in pois[:3] if poi.get('name')]
                        if poi_names:
                            result = f"找到 {len(pois)} 个地点，包括: {', '.join(poi_names)}"
                            if len(pois) > 3:
                                result += f" 等{len(pois)}个结果"
                            return result

                # 处理文本搜索结果
                if 'results' in data:
                    results = data.get('results', [])
                    if results:
                        # 显示前几个结果的标题
                        titles = [r.get('title', '') for r in results[:3] if r.get('title')]
                        if titles:
                            result = f"找到 {len(results)} 个结果，包括: {', '.join(titles)}"
                            if len(results) > 3:
                                result += f" 等{len(results)}个结果"
                            return result

                # 检查其他有用字段
                useful_fields = ['text', 'content', 'message', 'summary', 'result']
                for field in useful_fields:
                    if field in data and isinstance(data[field], str):
                        text = data[field]
                        if len(text) <= 150:
                            return text
                        else:
                            return text[:150] + "..."

                # 如果没有找到合适的字段，返回简化的描述
                return "[搜索结果已获取]"

            return str(data)[:100] + "..." if len(str(data)) > 100 else str(data)

        except (json.JSONDecodeError, Exception):
            # 如果不是JSON，直接返回截断的文本
            text = json_str.strip()
            if len(text) <= 150:
                return text
            else:
                # 尝试在句子边界截断
                for separator in ['。', '！', '？', '.', '!', '?', '\n']:
                    pos = text.rfind(separator, 0, 150)
                    if pos > 50:  # 确保截断位置不太靠前
                        return text[:pos+1]
                return text[:150] + "..."


class MessageHandler:
    """消息处理器 - 简化输出"""

    def create_parent_handler(self) -> Callable:
        """创建父实例消息处理器"""
        async def on_parent_message(msg):
            msg_type = msg.get('message_type', 'unknown')

            if msg_type == 'UserMessage':
                content = msg.get('data', {}).get('content', '')
                formatted_content = MessageFormatter._format_user_message(content)
                print(f"\n👤 你: {formatted_content}")

            elif msg_type == 'AssistantMessage':
                print(f"\n🤖 AI回复:")
                content_blocks = msg.get('data', {}).get('content', [])
                for block in content_blocks:
                    formatted = MessageFormatter.format_content_block(block)
                    if formatted:
                        print(formatted)

            elif msg_type == 'ResultMessage':
                self._handle_result_message(msg, "")

            elif msg_type == 'SystemMessage':
                self._handle_system_message(msg)

        return on_parent_message

    def create_child_handler(self) -> Callable:
        """创建子实例消息处理器"""
        async def on_child_message(child_id: str, instance: str, msg):
            msg_type = msg.get('message_type', 'unknown')
            instance_name = MessageFormatter._format_tool_name(instance)

            if msg_type == 'UserMessage':
                content = msg.get('data', {}).get('content', '')
                formatted_content = MessageFormatter._format_user_message(content)
                print(f"\n   👤 [{instance_name}] 用户: {formatted_content}")

            elif msg_type == 'AssistantMessage':
                print(f"\n   🤖 [{instance_name}] 回复:")
                content_blocks = msg.get('data', {}).get('content', [])
                for block in content_blocks:
                    formatted = MessageFormatter.format_content_block(block, "   ")
                    if formatted:
                        print(formatted)

            elif msg_type == 'ResultMessage':
                self._handle_result_message(msg, f"[{instance_name}] ", "   ")

            elif msg_type == 'SystemMessage':
                self._handle_system_message(msg, f"[{instance_name}] ")

        return on_child_message

    def _handle_result_message(self, msg: Dict, instance_prefix: str, prefix: str = ""):
        """处理结果消息 - 简化显示"""
        data = msg.get('data', {})
        result = data.get('result', '')
        is_error = data.get('is_error', False)
        duration_ms = data.get('duration_ms', 0)

        if is_error:
            print(f"\n{prefix}❌ {instance_prefix} 执行失败")
            error_msg = MessageFormatter._extract_error_message(result)
            if error_msg:
                print(f"{prefix}   {error_msg}")
        else:
            # 成功时简化显示
            if duration_ms > 1000:  # 超过1秒才显示时间
                print(f"\n{prefix}✅ {instance_prefix} 完成 (用时 {duration_ms//1000}.{(duration_ms%1000)//100}秒)")
            else:
                print(f"\n{prefix}✅ {instance_prefix} 完成")

    def _handle_system_message(self, msg: Dict, instance_prefix: str = ""):
        """处理系统消息 - 只显示重要信息"""
        data = msg.get('data', {})
        subtype = data.get('subtype', 'unknown')

        # 只显示重要的系统消息
        if subtype == 'sub_instance_started':
            child_instance = data.get('instance_name', 'unknown')
            instance_name = MessageFormatter._format_tool_name(child_instance)
            print(f"\n🔔 启动助手: {instance_name}")
        # 其他系统消息不显示，避免干扰用户

    def create_child_started_handler(self) -> Callable:
        """创建子实例启动处理器"""
        async def on_child_started(child_id: str, instance: str):
            instance_name = MessageFormatter._format_tool_name(instance)
            print(f"   🆔 会话ID: {child_id}")

        return on_child_started


class SessionManager:
    """会话管理器"""

    def __init__(self, query: SessionQuery):
        self.query = query

    async def get_session_list(self, limit: int = 10) -> Optional[list]:
        """获取会话列表 - 简化显示"""
        try:
            sessions = self.query.list_sessions(limit=limit)
            if not sessions:
                print("📭 暂无会话记录")
                return None

            print(f"\n📋 最近的会话:")
            print("=" * 60)

            for idx, session in enumerate(sessions, 1):
                session_info = await self._format_session_info(session, idx)
                print(session_info)
                print("-" * 60)

            print(f"💡 提示: 使用完整的会话ID继续对话")
            return sessions

        except Exception as e:
            print(f"❌ 获取会话列表失败: {e}")
            return None

    async def _format_session_info(self, session: Dict, idx: int) -> str:
        """格式化会话信息 - 更友好的显示"""
        session_id = session.get('session_id', 'unknown')
        status = session.get('status', 'unknown')
        start_time = session.get('start_time', 'unknown')

        # 获取消息数量
        message_count = await self._get_message_count(session_id)

        # 获取最后消息预览
        last_preview = await self._get_last_message_preview(session_id)

        # 格式化状态显示
        status_icon = "🟢" if status == "completed" else "🟡" if status == "running" else "⚪"

        # 格式化时间显示
        try:
            # 尝试解析时间并格式化为更友好的格式
            if len(start_time) > 10:
                date_part = start_time[:10]
                time_part = start_time[11:16] if len(start_time) > 16 else ""
                time_str = f"{date_part} {time_part}".strip()
            else:
                time_str = start_time
        except:
            time_str = start_time

        # 构建会话信息
        lines = []
        lines.append(f"{idx}. {status_icon} 会话ID: {session_id}")
        lines.append(f"   时间: {time_str} | 消息数: {message_count}")

        if last_preview and last_preview != "N/A":
            lines.append(f"   最后消息: {last_preview}")

        return '\n'.join(lines)

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
        try:
            if not self.query:
                return

            await self.query.subscribe(
                session_id=session_id,
                on_parent_message=self.message_handler.create_parent_handler(),
                on_child_message=self.message_handler.create_child_handler(),
                on_child_started=self.message_handler.create_child_started_handler()
            )
        except Exception:
            # 静默处理订阅错误，不干扰用户体验
            pass

    async def process_query(self, query_text: str, resume_session_id: Optional[str] = None):
        """处理查询请求 - 简化输出"""
        # 简化进度显示
        if resume_session_id:
            print(f"\n🔄 继续对话...")
        else:
            print(f"\n💭 AI正在思考...")

        # 清理之前的订阅
        if self.query:
            await self.query.stop()
            await asyncio.sleep(0.1)

        # 启动查询任务
        query_task = asyncio.create_task(
            self.agent.query_text(query_text, resume_session_id=resume_session_id)
        )

        # 等待会话创建
        await asyncio.sleep(0.1)
        session_id = None

        for attempt in range(30):  # 增加尝试次数
            await asyncio.sleep(0.1)
            current_session = SessionContext.get_current_session()

            if current_session:
                session_id = current_session
                break

        # 建立订阅
        if session_id:
            self.current_session_id = session_id
            self.query = SessionQuery(self.instance_name, message_bus=self.message_bus)
            await asyncio.sleep(0.2)
            await self.start_realtime_subscription(session_id)

        try:
            result = await query_task

            # 简化结果显示
            if result:
                self.current_session_id = result.session_id
                # 不在这里显示结果，因为实时消息已经显示了
                if not session_id:  # 如果没有实时订阅，才显示最终结果
                    print(f"\n📝 回复:\n{result.result}")
            else:
                print("\n❌ 查询失败")

            return result

        except Exception as e:
            print(f"\n❌ 出错了: {str(e)[:100]}")
            return None

    async def ask_for_action(self) -> str:
        """询问用户下一步操作"""
        print("\n" + "─" * 40)
        print("接下来想要做什么？")
        print("1️⃣  继续当前对话")
        print("2️⃣  开始新对话")
        print("3️⃣  查看会话信息")
        print("4️⃣  继续之前的会话")
        print("5️⃣  重新运行上一次查询")
        print("6️⃣  退出")
        print("─" * 40)
        print("💡 直接按回车继续当前对话")

        while True:
            choice = input("请选择 (1-6，默认1): ").strip()
            if not choice:
                return '1'
            if choice in ['1', '2', '3', '4', '5', '6']:
                return choice
            print("⚠️ 请输入 1-6 之间的数字")

    async def show_session_info(self):
        """显示当前会话信息"""
        if not self.current_session_id:
            print("📭 当前没有会话")
            return

        print(f"\n📊 当前会话:")
        print(f"ID: {self.current_session_id}")

        try:
            details = self.query.get_session_details(self.current_session_id, include_messages=True)
            if details:
                status = details.get('status', 'unknown')
                status_icon = "🟢" if status == "completed" else "🟡" if status == "running" else "⚪"
                print(f"状态: {status_icon} {status}")

                start_time = details.get('start_time', 'unknown')
                if len(start_time) > 10:
                    time_str = f"{start_time[:10]} {start_time[11:16]}"
                    print(f"时间: {time_str}")

                messages = details.get('messages', [])
                print(f"消息: {len(messages)} 条")

                # 显示最后一条消息
                last_msg = self._get_last_user_assistant_message(messages)
                if last_msg:
                    role = "👤 你" if last_msg['role'] == 'user' else "🤖 AI"
                    content = last_msg.get('content', '')
                    if len(content) > 60:
                        content = content[:60] + "..."
                    print(f"最后: {role}: {content}")

        except Exception as e:
            print(f"⚠️ 无法获取详细信息")

    def show_help(self):
        """显示帮助信息"""
        print("\n" + "💡 快捷命令")
        print("─" * 30)
        print("help     - 显示帮助")
        print("info     - 查看当前会话")
        print("read 文件 - 读取文件内容")
        print("clear    - 清空屏幕")
        print("exit     - 退出程序")
        print("\n💭 对话")
        print("─" * 30)
        print("直接输入内容即可开始对话")
        print("按回车默认继续当前对话")

    async def show_welcome_menu(self) -> Optional[str]:
        """显示欢迎菜单"""
        print("\n" + "🎨" * 20)
        print("  欢迎使用 Claude Agent")
        print("🎨" * 20)

        print("\n今天想做点什么？")
        print("1️⃣  开始新对话")
        print("2️⃣  继续之前的会话")
        print("3️⃣  查看会话记录")
        print("4️⃣  帮助")
        print("5️⃣  退出")
        print("─" * 30)

        while True:
            choice = input("请选择 (1-5): ").strip()

            if choice == '1':
                print("\n✨ 新对话已开始")
                print("💬 请输入您的问题：")
                return None
            elif choice == '2':
                return await self.resume_session_by_id()
            elif choice == '3':
                await self.session_manager.get_session_list()
                return await self.show_welcome_menu()
            elif choice == '4':
                self.show_help()
                input("\n按回车继续...")
                return await self.show_welcome_menu()
            elif choice == '5':
                print("\n👋 再见！")
                sys.exit(0)
            else:
                print("⚠️ 请输入 1-5")

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
                    print(f"\n📌 当前会话: {self.current_session_id[:20]}...")

                print("\n💬 请输入内容（输入 help 查看命令）:")
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
    instance_name = sys.argv[1] if len(sys.argv) > 1 else "search_master_agent"
    chat = InteractiveChat(instance_name)
    await chat.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 程序已退出")