"""
会话树构建器 - 递归构建父子会话关系树
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

from .session_query import get_session_details

logger = logging.getLogger(__name__)


class SessionTreeBuilder:
    """
    会话树构建器

    功能：
    - 递归查询并构建父子会话关系树
    - 支持控制最大递归深度
    - 可选是否包含消息内容
    """

    def __init__(
        self,
        instances_root: Optional[Path] = None
    ):
        """
        初始化会话树构建器

        Args:
            instances_root: 实例根目录（默认为当前目录下的 instances/）
        """
        self.instances_root = instances_root or Path.cwd() / "instances"

    async def build_tree(
        self,
        session_id: str,
        instance_name: Optional[str] = None,
        include_messages: bool = True,
        max_depth: int = 10
    ) -> Dict[str, Any]:
        """
        递归构建会话树

        Args:
            session_id: 会话 ID
            instance_name: 实例名称（可选，如果不提供则自动推断）
            include_messages: 是否包含消息内容
            max_depth: 最大递归深度

        Returns:
            会话树字典，格式：
            {
                "session_id": "xxx",
                "instance_name": "demo_agent",
                "depth": 0,
                "metadata": {...},
                "statistics": {...},
                "messages": [...],  # 可选
                "subsessions": [
                    {
                        "session_id": "yyy",
                        "instance_name": "child_agent",
                        "depth": 1,
                        "messages": [...],
                        "subsessions": [...]
                    }
                ]
            }

        Raises:
            Exception: 构建失败
        """
        # 推断实例名称（如果未提供）
        if instance_name is None:
            instance_name = self._infer_instance_name(session_id)

        if instance_name is None:
            raise ValueError(f"无法推断会话 {session_id} 的实例名称，请手动指定")

        # 1. 获取会话详情
        try:
            details = get_session_details(
                instance_name=instance_name,
                session_id=session_id,
                instances_root=self.instances_root,
                include_messages=include_messages
            )
        except Exception as e:
            logger.error(f"获取会话详情失败 {session_id}: {e}")
            raise

        # 2. 构建当前节点
        tree_node = {
            "session_id": session_id,
            "instance_name": details["metadata"]["instance_name"],
            "depth": details["metadata"].get("depth", 0),
            "metadata": details["metadata"],
            "statistics": details["statistics"],
            "subsessions": []
        }

        # 可选：包含消息
        if include_messages:
            tree_node["messages"] = details.get("messages", [])

        # 3. 递归构建子会话树
        if max_depth > 0 and details.get("subsessions"):
            for subsess_info in details["subsessions"]:
                child_session_id = subsess_info.get("session_id")
                if not child_session_id:
                    continue

                # 从工具名称推断子实例名称
                tool_name = subsess_info.get("tool_name", "")
                child_instance_name = self._extract_instance_name_from_tool(tool_name)

                if child_instance_name:
                    try:
                        child_tree = await self.build_tree(
                            session_id=child_session_id,
                            instance_name=child_instance_name,
                            include_messages=include_messages,
                            max_depth=max_depth - 1
                        )
                        tree_node["subsessions"].append(child_tree)
                    except Exception as e:
                        logger.warning(f"构建子会话树失败 {child_session_id}: {e}")
                        # 添加错误节点
                        tree_node["subsessions"].append({
                            "session_id": child_session_id,
                            "instance_name": child_instance_name,
                            "error": str(e)
                        })
                else:
                    logger.warning(f"无法从工具名称 {tool_name} 推断实例名称")

        return tree_node

    def _infer_instance_name(self, session_id: str) -> Optional[str]:
        """
        从所有实例中查找包含该 session_id 的实例

        Args:
            session_id: 会话 ID

        Returns:
            实例名称，如果找不到则返回 None
        """
        if not self.instances_root.exists():
            return None

        for instance_dir in self.instances_root.iterdir():
            if not instance_dir.is_dir():
                continue

            sessions_dir = instance_dir / "sessions"
            if not sessions_dir.exists():
                continue

            session_dir = sessions_dir / session_id
            if session_dir.exists():
                return instance_dir.name

        return None

    def _extract_instance_name_from_tool(self, tool_name: str) -> Optional[str]:
        """
        从子实例工具名称中提取实例名称

        Args:
            tool_name: 工具名称，例如 "mcp__custom_tools__sub_claude_file_analyzer"

        Returns:
            实例名称，例如 "file_analyzer_agent"
        """
        # 工具名称格式：mcp__custom_tools__sub_claude_{instance_alias}
        if not tool_name or "sub_claude_" not in tool_name:
            return None

        # 提取 sub_claude_ 后的部分
        parts = tool_name.split("sub_claude_")
        if len(parts) < 2:
            return None

        instance_alias = parts[1]

        # 从配置中查找对应的实例名称
        # 简化处理：假设实例名称就是 {instance_alias}_agent
        # 实际应该从配置文件中查找，但这里我们先尝试推断

        # 尝试几种常见的命名模式
        possible_names = [
            f"{instance_alias}_agent",
            f"{instance_alias}",
            f"{instance_alias}_instance"
        ]

        for name in possible_names:
            instance_path = self.instances_root / name
            if instance_path.exists():
                return name

        logger.warning(f"无法推断实例名称，工具名称：{tool_name}")
        return None

    def flatten_tree(self, tree: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        将树形结构展平为列表

        Args:
            tree: 会话树

        Returns:
            会话列表（按深度优先顺序）
        """
        result = []

        def traverse(node: Dict[str, Any]):
            # 提取节点信息（不包含 subsessions）
            node_info = {k: v for k, v in node.items() if k != "subsessions"}
            result.append(node_info)

            # 递归遍历子节点
            for child in node.get("subsessions", []):
                traverse(child)

        traverse(tree)
        return result
