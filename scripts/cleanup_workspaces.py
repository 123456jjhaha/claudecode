"""
工作空间清理工具

用法:
    python scripts/cleanup_workspaces.py <instance_name> [--dry-run] [--days=30]
"""

import sys
import argparse
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config_manager import ConfigManager
from src.workspace import WorkspaceManager
from src.logging_config import get_logger

logger = get_logger(__name__)


def main():
    parser = argparse.ArgumentParser(description="清理过期的工作目录")
    parser.add_argument("instance_name", help="实例名称")
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不实际删除")
    parser.add_argument("--days", type=int, help="保留天数（覆盖配置）")

    args = parser.parse_args()

    # 加载实例配置
    instance_path = Path("instances") / args.instance_name
    if not instance_path.exists():
        print(f"错误: 实例不存在: {instance_path}")
        sys.exit(1)

    try:
        config_mgr = ConfigManager(instance_path)
        config_mgr.load_config()
    except Exception as e:
        print(f"错误: 加载配置失败: {e}")
        sys.exit(1)

    workspace_config = config_mgr.config.get("workspace", {})
    if not workspace_config.get("enabled"):
        print(f"实例 {args.instance_name} 未启用工作空间")
        sys.exit(0)

    # 创建工作空间管理器
    workspace_mgr = WorkspaceManager(instance_path, workspace_config)

    # 确定保留天数
    retention_days = args.days or workspace_config.get("retention_days", 30)

    print(f"=" * 60)
    print(f"工作空间清理工具")
    print(f"=" * 60)
    print(f"实例: {args.instance_name}")
    print(f"保留天数: {retention_days}")
    print(f"模式: {'预览' if args.dry_run else '执行'}")
    print(f"=" * 60)
    print()

    if args.dry_run:
        print("⚠️  预览模式：不会实际删除任何文件")
        print()
        # TODO: 实现真正的预览功能
        print("预览功能尚未实现")
        sys.exit(0)

    # 执行清理
    try:
        report = workspace_mgr.cleanup_old_workspaces(retention_days)
    except Exception as e:
        print(f"错误: 清理失败: {e}")
        logger.error(f"清理失败: {e}", exc_info=True)
        sys.exit(1)

    # 输出报告
    print("清理完成！")
    print()
    print(f"扫描: {report['scanned']} 个工作目录")
    print(f"删除: {report['deleted']} 个")
    print(f"失败: {report['failed']} 个")
    print(f"释放空间: {report['total_size_mb']:.2f} MB")

    if report.get("deleted_sessions"):
        print()
        print("已删除的会话:")
        for item in report["deleted_sessions"]:
            print(f"  - {item['session_id']} (年龄: {item['age_days']} 天, 大小: {item['size_mb']:.2f} MB)")


if __name__ == "__main__":
    main()
