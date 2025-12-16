"""
Agent 系统主类

整合所有组件，提供统一的接口
"""

from pathlib import Path
from typing import Any, AsyncIterator, Optional, List, Dict
from functools import wraps
from datetime import datetime
from dataclasses import dataclass
from claude_agent_sdk import query, ClaudeAgentOptions, SystemMessage, UserMessage

from .config_manager import ConfigManager, merge_mcp_configs
from .tool_manager import ToolManager
from .sub_instance_adapter import create_sub_instance_tools
from .error_handling import AgentSystemError
from .logging_config import get_logger
from .session import QueryStreamManager, SessionManager

logger = get_logger(__name__)


@dataclass
class QueryResult:
    """
    查询结果对象

    Attributes:
        result: 查询结果文本
        session_id: 会话 ID（如果启用了会话记录）
    """
    result: str
    session_id: Optional[str] = None


class QueryStream:
    """
    查询流对象

    封装异步迭代器和 session_id，支持流式访问消息
    """

    def __init__(self, iterator: AsyncIterator[Any], session_id: Optional[str] = None):
        self._iterator = iterator
        self.session_id = session_id

    def __aiter__(self):
        return self._iterator.__aiter__()

    async def __anext__(self):
        return await self._iterator.__anext__()


def require_initialized(func):
    """装饰器：确保系统已初始化"""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self._initialized:
            raise AgentSystemError("系统未初始化，请先调用 initialize()")
        return func(self, *args, **kwargs)
    return wrapper


class AgentSystem:
    """Claude Agent 系统"""

    def __init__(
        self,
        instance_name: str,
        instances_root: Path | None = None
    ):
        """
        初始化 Agent 系统

        Args:
            instance_name: 实例名称或实例目录路径
            instances_root: 实例根目录（默认为当前目录下的 instances/）
        Raises:
            AgentSystemError: 初始化失败
        """

        # 实例目录
        if Path(instance_name).exists():
            # 如果是目录路径，直接使用
            self.instance_path = Path(instance_name)
        else:
            # 否则，从 instances_root 中查找
            if instances_root is None:
                instances_root = Path.cwd() / "instances"

            self.instance_path = Path(instances_root) / instance_name

        if not self.instance_path.exists():
            raise AgentSystemError(f"实例目录不存在: {self.instance_path}")

        self.instances_root = self.instance_path.parent

        logger.info(f"初始化 Agent 系统: {self.instance_path}")

        # 组件
        self.config_loader: ConfigManager | None = None
        self.tool_manager: ToolManager | None = None
        self.sub_instance_tools: list = None

        # 会话管理
        self.session_manager: SessionManager | None = None

        # 配置和选项
        self._config: dict | None = None
        self._options: ClaudeAgentOptions | None = None

        # 初始化状态
        self._initialized = False

    async def initialize(self) -> None:
        """
        初始化系统（加载配置、工具和子实例）

        Raises:
            AgentSystemError: 初始化失败
        """
        if self._initialized:
            logger.warning("系统已初始化，跳过")
            return

        logger.info("开始初始化系统")

        try:
            # 1. 加载配置
            logger.info("加载配置...")
            self.config_loader = ConfigManager(self.instance_path)
            self._config = self.config_loader.load_config()
            options_dict = self.config_loader.get_claude_options_dict()

            # 2. 发现本地工具（只发现，用于统计）
            logger.info("发现本地工具...")
            self.tool_manager = ToolManager(self.instance_path)
            self.tool_manager.discover_tools()

            # 3. 发现子实例（只发现，用于统计）
            logger.info("发现子实例...")
            sub_instances_config = options_dict.get("_sub_instances_config", {})

            # 保存会话记录配置（需要在创建 options 前提取）
            session_recording_config = options_dict.get("_session_recording_config", {})

            # 创建子实例工具（只用于统计数量）
            if sub_instances_config:
                logger.info(f"发现 {len(sub_instances_config)} 个子实例配置")
                self.sub_instance_tools = create_sub_instance_tools(
                    sub_instances_config,
                    self.instances_root
                )
            else:
                self.sub_instance_tools = []

            # 4. 启动 MCP 服务器（传递 instance_path，服务器自己负责加载所有工具）
            logger.info("启动 MCP 服务器...")
            custom_tools_server = None
            if self.tool_manager.tools_count > 0 or sub_instances_config:
                custom_tools_server = self.tool_manager.start_mcp_server("custom_tools")

            # 6. 加载和合并 MCP 服务器配置
            logger.info("合并 MCP 服务器配置...")

            # 6.1 读取 .mcp.json 文件中的外部 MCP 服务器配置
            external_mcp_servers = self.config_loader.load_mcp_config()

            # 6.2 准备内部 MCP 服务器配置
            internal_mcp_servers = {}
            if custom_tools_server is not None:
                internal_mcp_servers["custom_tools"] = custom_tools_server

            # 6.3 合并所有 MCP 服务器配置
            all_mcp_servers = merge_mcp_configs(internal_mcp_servers, external_mcp_servers)

            # 7. 展开工具权限配置中的通配符
            logger.info("处理工具权限配置...")
            all_mcp_tool_names = self.tool_manager.collect_all_mcp_tool_names(self.sub_instance_tools)
            self.tool_manager.expand_tool_permissions(options_dict, all_mcp_tool_names)

            # 8. 生成最终的 ClaudeAgentOptions
            logger.info("生成 ClaudeAgentOptions...")

            # 移除内部使用的自定义字段
            options_dict.pop("_sub_instances_config", None)
            options_dict.pop("_session_recording_config", None)

            # 设置完整的 MCP 服务器配置
            if all_mcp_servers:
                options_dict["mcp_servers"] = all_mcp_servers
                logger.info(f"配置了 {len(all_mcp_servers)} 个 MCP 服务器")

            # 9. 创建会话管理器
            logger.info("初始化会话记录...")
            self.session_manager = SessionManager(
                instance_path=self.instance_path,
                config=session_recording_config
            )

            # 10. 创建 ClaudeAgentOptions
            self._options = ClaudeAgentOptions(**options_dict)

            self._initialized = True
            logger.info("系统初始化完成")

        except Exception as e:
            logger.error(f"初始化失败: {e}")
            raise AgentSystemError(f"初始化失败: {e}")

  
  
    async def query(
        self,
        prompt: str,
        record_session: bool = True,
        resume_session_id: Optional[str] = None,
        parent_session_id: Optional[str] = None
    ) -> QueryStream:
        """
        执行查询（支持会话记录和 resume）

        Args:
            prompt: 查询提示词
            record_session: 是否记录会话到文件
            resume_session_id: 要恢复的会话 ID（我们的本地 session_id）
            parent_session_id: 父会话 ID（用于子实例调用时建立父子关系）
                **重要**：MCP 子实例调用时必须传递此参数

        Returns:
            QueryStream 对象（可迭代，包含 session_id）
        """
        require_initialized(self)

        logger.info(f"执行查询... (record_session={record_session}, resume={resume_session_id}, parent={parent_session_id})")

        try:
            # 准备查询选项
            query_options = self._options
            # 如果有 resume_session_id，需要提取Claude的session_id并恢复会话
            if resume_session_id:
                claude_session_id = self.session_manager.get_claude_session_id(resume_session_id)
                if claude_session_id:
                    query_options.resume = claude_session_id
                    logger.info(f"恢复Claude会话: {claude_session_id} (本地session: {resume_session_id})")
                else:
                    logger.warning(f"未找到Claude session_id for local session: {resume_session_id}")

            # 执行查询
            stream = query(
                prompt=prompt,
                options=query_options
            )
            # 创建查询流管理器
            stream_manager = QueryStreamManager(
                stream=stream,
                session_manager=self.session_manager,
                record_session=record_session,
                prompt=prompt,
                resume_session_id=resume_session_id,
                parent_session_id=parent_session_id  # 传递父会话 ID
            )

            # 初始化 session（创建或恢复会话）
            await stream_manager.initialize()

            # 创建 QueryStream 包装器
            query_stream = QueryStream(
                iterator=stream_manager,
                session_id=stream_manager.session_id
            )

            return query_stream

        except Exception as e:
            logger.error(f"查询失败: {e}")
            raise AgentSystemError(f"查询失败: {e}")

    @require_initialized
    async def query_text(
        self,
        prompt: str,
        record_session: bool = True,
        resume_session_id: Optional[str] = None,
        parent_session_id: Optional[str] = None
    ) -> QueryResult:
        """
        执行查询并返回结果

        Args:
            prompt: 查询提示词
            record_session: 是否记录会话到文件
            resume_session_id: 要恢复的会话 ID
            parent_session_id: 父会话 ID（用于子实例调用）

        Returns:
            QueryResult 对象（包含结果和 session_id）
        """
        stream = await self.query(
            prompt=prompt,
            record_session=record_session,
            resume_session_id=resume_session_id,
            parent_session_id=parent_session_id
        )

        # 收集所有消息，构建结果
        result_parts = []
        async for message in stream:
            # 处理消息内容
            message_type = type(message).__name__

            if message_type == "ResultMessage":
                # 最终结果
                result_parts.append(message.result if hasattr(message, "result") else str(message))
            elif hasattr(message, "text"):
                # 文本消息
                result_parts.append(message.text)
            elif hasattr(message, "content"):
                # 内容块
                if isinstance(message.content, list):
                    for block in message.content:
                        if hasattr(block, "text"):
                            result_parts.append(block.text)

        # 组合结果
        result_text = "\n".join(result_parts) if result_parts else ""

        return QueryResult(
            result=result_text,
            session_id=stream.session_id
        )

  
    @property
    @require_initialized
    def agent_name(self) -> str:
        """获取 agent 名称"""
        return self._config["agent"]["name"]

    @property
    @require_initialized
    def agent_description(self) -> str | None:
        """获取 agent 描述"""
        return self._config["agent"].get("description")

    @property
    def tools_count(self) -> int:
        """获取工具数量"""
        if self.tool_manager is None:
            return 0
        return self.tool_manager.tools_count

    @property
    def sub_instances_count(self) -> int:
        """获取子实例数量"""
        if self.sub_instance_tools is None:
            return 0
        return len(self.sub_instance_tools)

    def cleanup(self):
        """
        清理资源，停止 MCP 服务器进程

        应该在应用程序关闭时调用
        """
        if not self._initialized:
            return

        logger.info("清理 AgentSystem 资源...")

        # 停止工具 MCP 服务器
        if self.tool_manager is not None:
            try:
                self.tool_manager.stop_mcp_server()
            except Exception as e:
                logger.error(f"停止工具 MCP 服务器失败: {e}")

        # 停止会话管理器
        if self.session_manager is not None:
            try:
                self.session_manager.cleanup()
            except Exception as e:
                logger.error(f"清理会话管理器失败: {e}")

        logger.info("AgentSystem 资源清理完成")

    def __del__(self):
        """析构函数，确保资源被清理"""
        try:
            self.cleanup()
        except Exception:
            # 防止析构函数中的异常
            pass

    def __repr__(self) -> str:
        """字符串表示"""
        if self._initialized:
            return (
                f"AgentSystem(name='{self.agent_name}', "
                f"tools={self.tools_count}, "
                f"sub_instances={self.sub_instances_count})"
            )
        else:
            return f"AgentSystem(path='{self.instance_path}', initialized=False)"