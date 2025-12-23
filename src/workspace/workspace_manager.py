"""
工作空间管理器

管理 session 级别的独立工作目录，实现以下功能：
- 为每个 session 创建独立的工作目录
- 生成工作目录信息消息（用于 system prompt 注入）
- 清理过期的工作目录
- 监控工作目录大小
"""

from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import json
import shutil

from ..logging_config import get_logger

logger = get_logger(__name__)


class WorkspaceManager:
    """工作空间管理器 - 管理 session 级别的独立工作目录"""

    def __init__(self, instance_path: Path, workspace_config: Dict[str, Any]):
        """
        初始化工作空间管理器

        Args:
            instance_path: 实例目录
            workspace_config: workspace 配置（来自 config.yaml）
        """
        self.instance_path = instance_path
        self.config = workspace_config
        self.enabled = workspace_config.get("enabled", False)

    def create_workspace(self, session_id: str) -> Optional[Path]:
        """
        为 session 创建工作目录

        Args:
            session_id: 会话 ID

        Returns:
            工作目录路径，如果未启用则返回 None
        """
        if not self.enabled:
            return None

        # 固定路径：sessions/{session_id}/workspace/
        workspace_path = self.instance_path / "sessions" / session_id / "workspace"

        # 创建目录
        if self.config.get("auto_create", True):
            workspace_path.mkdir(parents=True, exist_ok=True)

            # 写入元数据
            metadata = {
                "session_id": session_id,
                "created_at": datetime.now().isoformat(),
                "retention_days": self.config.get("retention_days", 30),
                "max_size_mb": self.config.get("max_size_mb", 500)
            }

            metadata_file = workspace_path / ".workspace_info.json"
            with open(metadata_file, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)

            # 🌟 复制 .claude 目录下的所有文件到工作空间
            claude_dir = self.instance_path / ".claude"
            if claude_dir.exists():
                self._copy_claude_directory(claude_dir, workspace_path)

            logger.info(f"创建工作目录: {workspace_path}")

        return workspace_path

    def get_workspace_path(self, session_id: str) -> Optional[Path]:
        """
        获取 session 的工作目录路径

        Args:
            session_id: 会话 ID

        Returns:
            工作目录路径，如果未启用则返回 None
        """
        if not self.enabled:
            return None

        return self.instance_path / "sessions" / session_id / "workspace"

    def cleanup_old_workspaces(self, retention_days: Optional[int] = None) -> Dict[str, Any]:
        """
        清理过期的工作目录（手动调用）

        Args:
            retention_days: 保留天数（None 则使用配置值）

        Returns:
            清理报告，包含以下字段：
                - scanned: 扫描的工作目录数量
                - deleted: 删除的工作目录数量
                - failed: 删除失败的数量
                - total_size_mb: 释放的总空间（MB）
                - deleted_sessions: 已删除的会话列表
        """
        if retention_days is None:
            retention_days = self.config.get("retention_days", 30)

        report = {
            "scanned": 0,
            "deleted": 0,
            "failed": 0,
            "total_size_mb": 0.0,
            "deleted_sessions": []
        }

        sessions_dir = self.instance_path / "sessions"
        if not sessions_dir.exists():
            return report

        # 扫描所有 session 目录
        for session_dir in sessions_dir.iterdir():
            if not session_dir.is_dir():
                continue

            workspace_dir = session_dir / "workspace"
            if not workspace_dir.exists():
                continue

            report["scanned"] += 1

            # 检查元数据
            metadata_file = workspace_dir / ".workspace_info.json"
            if not metadata_file.exists():
                logger.warning(f"工作目录缺少元数据文件: {workspace_dir}")
                continue

            try:
                with open(metadata_file, "r", encoding="utf-8") as f:
                    metadata = json.load(f)

                created_at = datetime.fromisoformat(metadata["created_at"])
                age_days = (datetime.now() - created_at).days

                if age_days > retention_days:
                    # 计算大小
                    size_bytes = sum(
                        f.stat().st_size
                        for f in workspace_dir.rglob("*")
                        if f.is_file()
                    )
                    size_mb = size_bytes / (1024 * 1024)

                    # 删除工作目录
                    shutil.rmtree(workspace_dir)
                    logger.info(f"已删除过期工作目录: {workspace_dir} ({size_mb:.2f} MB)")

                    report["deleted"] += 1
                    report["total_size_mb"] += size_mb
                    report["deleted_sessions"].append({
                        "session_id": session_dir.name,
                        "age_days": age_days,
                        "size_mb": size_mb
                    })

            except Exception as e:
                logger.error(f"处理工作目录失败 {workspace_dir}: {e}")
                report["failed"] += 1

        return report

    def get_workspace_info_message(self, session_id: str) -> str:
        """
        生成工作目录信息消息（用于 system prompt 注入）

        Args:
            session_id: 会话 ID

        Returns:
            工作目录信息消息
        """
        if not self.enabled:
            return ""

        workspace_path = self.get_workspace_path(session_id)

        # 使用自定义模板或默认模板
        template = self.config.get("init_message_template")
        if not template:
            template = self._get_default_template()

        # 填充模板
        message = template.format(
            workspace_path=workspace_path,
            retention_days=self.config.get("retention_days", 30)
        )

        return message

    def _copy_claude_directory(self, source_dir: Path, dest_dir: Path) -> None:
        """
        复制 .claude 目录下的所有文件到工作空间

        Args:
            source_dir: 源目录 (.claude)
            dest_dir: 目标目录 (workspace)
        """
        try:
            import shutil

            # 创建目标目录中的 .claude 子目录
            claude_dest_dir = dest_dir / ".claude"
            claude_dest_dir.mkdir(exist_ok=True)

            # 递归复制所有文件和子目录
            for item in source_dir.iterdir():
                if item.is_file():
                    # 复制文件
                    shutil.copy2(item, claude_dest_dir / item.name)
                elif item.is_dir():
                    # 复制整个目录
                    shutil.copytree(item, claude_dest_dir / item.name, dirs_exist_ok=True)

            logger.debug(f"已复制 .claude 目录到工作空间: {claude_dest_dir}")

        except Exception as e:
            logger.warning(f"复制 .claude 目录失败: {e}")
            # 不抛出异常，只是记录警告

    def _get_default_template(self) -> str:
        """默认的工作目录信息模板"""
        return """## Your Workspace

Your dedicated workspace directory is: `{workspace_path}`

- This is YOUR isolated workspace for this conversation
- All files you create should go here unless explicitly directed otherwise
- The workspace will be preserved for {retention_days} days
- The `.claude/` directory has been copied to your workspace with Claude Code configurations
"""

    def check_workspace_size(self, session_id: str) -> Dict[str, Any]:
        """
        检查工作目录大小

        Args:
            session_id: 会话 ID

        Returns:
            字典，包含以下字段：
                - size_mb: 当前大小（MB）
                - exceeded: 是否超过最大限制
                - warn: 是否超过警告阈值
        """
        workspace_path = self.get_workspace_path(session_id)
        if not workspace_path or not workspace_path.exists():
            return {"size_mb": 0.0, "exceeded": False, "warn": False}

        # 计算大小
        size_bytes = sum(
            f.stat().st_size
            for f in workspace_path.rglob("*")
            if f.is_file()
        )
        size_mb = size_bytes / (1024 * 1024)

        max_size = self.config.get("max_size_mb", 500)
        warn_size = self.config.get("warn_size_mb", 400)

        return {
            "size_mb": size_mb,
            "exceeded": size_mb > max_size,
            "warn": size_mb > warn_size
        }
