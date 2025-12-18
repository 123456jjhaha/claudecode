"""
实例工具函数

提供实例相关的通用工具函数：
- 实例名称推断
- 工具名称解析
- 实例路径管理
"""

from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def infer_instance_name(session_id: str, instances_root: Optional[Path] = None) -> Optional[str]:
    """
    从 session_id 推断所属的实例名称

    通过遍历所有实例的 sessions 目录，查找包含该 session_id 的实例。

    Args:
        session_id: 会话 ID
        instances_root: 实例根目录（默认为当前目录下的 instances/）

    Returns:
        实例名称，如果找不到则返回 None

    Example:
        >>> infer_instance_name("20251216T103000_1234_abcd1234")
        "demo_agent"
    """
    if instances_root is None:
        instances_root = Path.cwd() / "instances"

    instances_root = Path(instances_root)

    if not instances_root.exists():
        logger.warning(f"实例根目录不存在: {instances_root}")
        return None

    # 遍历所有实例目录
    for instance_dir in instances_root.iterdir():
        if not instance_dir.is_dir():
            continue

        # 检查该实例的 sessions 目录
        sessions_dir = instance_dir / "sessions"
        if not sessions_dir.exists():
            continue

        # 检查是否存在该 session_id 的目录
        session_dir = sessions_dir / session_id
        if session_dir.exists():
            return instance_dir.name

    logger.warning(f"无法推断 session_id {session_id} 的实例名称")
    return None


def extract_instance_from_tool_name(
    tool_name: str,
    instances_root: Optional[Path] = None
) -> Optional[str]:
    """
    从子实例工具名称中提取实例名称

    子实例工具的命名格式：mcp__custom_tools__sub_claude_{instance_alias}
    此函数提取 instance_alias 并尝试推断实际的实例名称。

    Args:
        tool_name: 工具名称，例如 "mcp__custom_tools__sub_claude_file_analyzer"
        instances_root: 实例根目录（默认为当前目录下的 instances/）

    Returns:
        实例名称，例如 "file_analyzer_agent"，找不到则返回 None

    Example:
        >>> extract_instance_from_tool_name("mcp__custom_tools__sub_claude_file_analyzer")
        "file_analyzer_agent"
    """
    if not tool_name or "sub_claude_" not in tool_name:
        return None

    # 提取 sub_claude_ 后的部分
    parts = tool_name.split("sub_claude_")
    if len(parts) < 2:
        return None

    instance_alias = parts[1]

    # 设置实例根目录
    if instances_root is None:
        instances_root = Path.cwd() / "instances"

    instances_root = Path(instances_root)

    # 尝试几种常见的命名模式
    possible_names = [
        f"{instance_alias}_agent",
        f"{instance_alias}",
        f"{instance_alias}_instance"
    ]

    for name in possible_names:
        instance_path = instances_root / name
        if instance_path.exists():
            return name

    logger.warning(f"无法从工具名称 {tool_name} 推断实例名称")
    return None


def get_instance_path(
    instance_name: str,
    instances_root: Optional[Path] = None
) -> Path:
    """
    获取实例目录路径

    Args:
        instance_name: 实例名称
        instances_root: 实例根目录（默认为当前目录下的 instances/）

    Returns:
        实例目录路径

    Raises:
        FileNotFoundError: 实例目录不存在

    Example:
        >>> get_instance_path("demo_agent")
        Path("instances/demo_agent")
    """
    if instances_root is None:
        instances_root = Path.cwd() / "instances"

    instance_path = Path(instances_root) / instance_name

    if not instance_path.exists():
        raise FileNotFoundError(f"实例目录不存在: {instance_path}")

    return instance_path


def validate_instance_structure(instance_path: Path) -> bool:
    """
    验证实例目录结构是否完整

    Args:
        instance_path: 实例目录路径

    Returns:
        True 如果结构完整，否则 False

    Example:
        >>> validate_instance_structure(Path("instances/demo_agent"))
        True
    """
    required_files = ["config.yaml"]
    required_dirs = ["sessions"]

    # 检查必需文件
    for file_name in required_files:
        file_path = instance_path / file_name
        if not file_path.exists():
            logger.warning(f"实例 {instance_path.name} 缺少必需文件: {file_name}")
            return False

    # 检查必需目录（sessions 目录会自动创建，所以只警告不返回 False）
    for dir_name in required_dirs:
        dir_path = instance_path / dir_name
        if not dir_path.exists():
            logger.info(f"实例 {instance_path.name} 缺少目录 {dir_name}，将自动创建")

    return True


def list_all_instances(instances_root: Optional[Path] = None) -> list[str]:
    """
    列出所有实例名称

    Args:
        instances_root: 实例根目录（默认为当前目录下的 instances/）

    Returns:
        实例名称列表

    Example:
        >>> list_all_instances()
        ["demo_agent", "file_analyzer_agent", "syntax_checker_agent"]
    """
    if instances_root is None:
        instances_root = Path.cwd() / "instances"

    instances_root = Path(instances_root)

    if not instances_root.exists():
        logger.warning(f"实例根目录不存在: {instances_root}")
        return []

    instances = []
    for item in instances_root.iterdir():
        if item.is_dir():
            # 验证是否是有效的实例目录（至少有 config.yaml）
            if (item / "config.yaml").exists():
                instances.append(item.name)

    return sorted(instances)
