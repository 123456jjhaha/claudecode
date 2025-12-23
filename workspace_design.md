# 工作目录隔离系统设计文档（简化版）

## 1. 问题分析

### 1.1 当前问题

**核心问题**：所有 session 共享同一个工作目录，导致：
- ✗ 多个并发 session 的文件操作相互污染
- ✗ 无法隔离不同 session 的临时文件
- ✗ session 结束后无法清理工作文件
- ✗ 难以追踪某个 session 产生的所有文件

**当前实现**（在 `config_manager.py:376-380`）：
```python
# 工作目录
if "cwd" in self._config:
    options["cwd"] = str(self.resolve_path(self._config["cwd"]))
else:
    options["cwd"] = str(self.instance_path)
```

所有 session 都使用相同的 `cwd`，没有隔离机制。

### 1.2 设计目标

1. ✓ 为每个 session 创建独立的工作目录
2. ✓ 通过 system prompt 告知 Claude 其专属工作目录
3. ✓ 在 config.yaml 中简单配置即可启用
4. ✓ 支持手动清理过期工作目录
5. ✓ **保持简单**：不引入复杂的权限、共享目录等功能

---

## 2. 设计方案

### 2.1 工作目录架构

#### 目录结构（固定方案）

```
instances/{instance_name}/
├── config.yaml
├── .claude/
├── tools/
└── sessions/                          # 会话记录目录（已存在）
    └── {session_id}/                  # 每个会话的目录
        ├── messages.jsonl             # 会话消息（已存在）
        ├── metadata.json              # 会话元数据（已存在）
        └── workspace/                 # 🌟 新增：会话工作空间
            ├── .workspace_info.json   # 工作空间元数据
            └── ...                    # Claude 创建的所有文件
```

#### 设计原则

1. **简单性**：固定目录结构，无需选择
2. **隔离性**：每个 session 有独立的工作目录
3. **可追溯性**：工作目录与 session_id 绑定，易于查找
4. **可管理性**：支持手动清理过期工作目录

### 2.2 配置文件（简化版）

#### config.yaml 新增配置项

```yaml
# ==================== 工作目录配置 ====================
# 工作空间强制启用，为每个 session 自动创建独立的工作目录
workspace:
  # 目录管理
  auto_create: true               # 是否自动创建工作目录（建议 true）
  retention_days: 30              # 保留天数（用于手动清理工具参考）

  # System Prompt 注入
  init_message: true              # 是否在 system prompt 中告知工作目录
  init_message_template: |        # 自定义消息模板（可选）
    ## Your Workspace

    Your dedicated workspace directory is: `{workspace_path}`

    - This is YOUR isolated workspace for this conversation
    - All files you create should go here unless explicitly directed otherwise
    - The workspace will be preserved for {retention_days} days

  # 工作目录大小限制
  max_size_mb: 500                # 单个工作目录最大大小（MB）
  warn_size_mb: 400               # 警告阈值（MB）
```

#### 配置说明

**核心配置项**：
- `auto_create`: 是否自动创建工作目录（默认 true）
- `init_message`: 是否在 system prompt 中告知 Claude（默认 true）

**可选配置项**：
- `init_message_template`: 自定义 system prompt 消息模板
- `retention_days`: 工作目录保留天数（仅供清理工具参考）
- `max_size_mb`, `warn_size_mb`: 大小限制（可选）

### 2.3 工作目录生命周期

#### 创建流程

```
1. AgentSystem.query_text() 调用
   ↓
2. SessionManager.create_session() 创建 session
   ↓
3. WorkspaceManager.create_workspace(session_id)
   ↓
4. 创建目录：sessions/{session_id}/workspace/
   ↓
5. 写入元数据：.workspace_info.json
   ↓
6. 设置 cwd = workspace_path
   ↓
7. 在 system prompt 中注入工作目录信息
   ↓
8. Claude 开始工作（知道自己的工作目录）
```

#### 清理流程（仅手动）

```
1. 运行清理脚本/CLI 命令
   ↓
2. WorkspaceManager.cleanup_old_workspaces(retention_days)
   ↓
3. 扫描所有工作目录的 .workspace_info.json
   ↓
4. 删除超过 retention_days 的目录
   ↓
5. 生成清理报告
```

**重要**：
- ✗ 不支持自动清理（避免误删）
- ✓ 只支持手动运行清理工具
- ✓ 清理前可以预览将要删除的内容

### 2.4 告知 Claude 工作目录的机制

#### System Prompt 注入（唯一方案）

在 `config_manager.py` 的 `get_claude_options_dict()` 中：

```python
# 加载原始 system_prompt
system_prompt = self.load_prompt_file(...)

# 如果启用了 workspace
if workspace_config.get("enabled") and workspace_config.get("init_message"):
    workspace_info = workspace_manager.get_workspace_info_message(session_id)
    # 在 system_prompt 前面注入工作目录信息
    system_prompt = f"{workspace_info}\n\n---\n\n{system_prompt}"

options["system_prompt"] = system_prompt
options["cwd"] = str(workspace_path)  # 设置工作目录
```

**优点**：
- ✓ 简单直接，Claude 一开始就知道工作目录
- ✓ 不依赖复杂的 hook 或环境变量
- ✓ 对 Claude 完全透明

---

## 3. 实现细节

### 3.1 新增模块：`workspace_manager.py`

#### 文件位置
```
src/
└── workspace/
    ├── __init__.py
    └── workspace_manager.py      # 工作空间管理器
```

#### WorkspaceManager 类设计（简化版）

```python
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

            logger.info(f"创建工作目录: {workspace_path}")

        return workspace_path

    def get_workspace_path(self, session_id: str) -> Optional[Path]:
        """获取 session 的工作目录路径"""
        if not self.enabled:
            return None

        return self.instance_path / "sessions" / session_id / "workspace"

    def cleanup_old_workspaces(self, retention_days: Optional[int] = None) -> Dict[str, Any]:
        """
        清理过期的工作目录（手动调用）

        Args:
            retention_days: 保留天数（None 则使用配置值）

        Returns:
            清理报告
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

    def _get_default_template(self) -> str:
        """默认的工作目录信息模板"""
        return """## Your Workspace

Your dedicated workspace directory is: `{workspace_path}`

- This is YOUR isolated workspace for this conversation
- All files you create should go here unless explicitly directed otherwise
- The workspace will be preserved for {retention_days} days
"""

    def check_workspace_size(self, session_id: str) -> Dict[str, Any]:
        """
        检查工作目录大小

        Returns:
            {"size_mb": float, "exceeded": bool, "warn": bool}
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
```

### 3.2 修改 `config_manager.py`

#### 添加 workspace 配置验证

```python
class ConfigManager:
    # 在类定义中添加
    WORKSPACE_FIELDS = {
        "enabled": (bool, False),
        "auto_create": (bool, False),
        "retention_days": (int, False),
        "init_message": (bool, False),
        "init_message_template": (str, False),
        "max_size_mb": (int, False),
        "warn_size_mb": (int, False),
    }

    def validate_config(self, config: dict[str, Any]) -> None:
        """验证配置字典"""
        # ... 原有代码 ...

        # 验证 workspace 配置
        if "workspace" in config:
            self._validate_workspace(config["workspace"])

    def _validate_workspace(self, workspace_config: dict[str, Any]) -> None:
        """验证 workspace 配置"""
        for field, (expected_type, _) in self.WORKSPACE_FIELDS.items():
            if field in workspace_config:
                value = workspace_config[field]
                if not isinstance(value, expected_type):
                    raise ConfigValidationError(
                        f"类型错误，期望 {expected_type.__name__}，实际为 {type(value).__name__}",
                        field=f"workspace.{field}"
                    )

        # 验证数值范围
        if "retention_days" in workspace_config:
            if workspace_config["retention_days"] < 1:
                raise ConfigValidationError(
                    "retention_days 必须大于 0",
                    field="workspace.retention_days"
                )

        if "max_size_mb" in workspace_config:
            if workspace_config["max_size_mb"] < 1:
                raise ConfigValidationError(
                    "max_size_mb 必须大于 0",
                    field="workspace.max_size_mb"
                )
```

#### 修改 `get_claude_options_dict()` 方法

```python
@require_config_loaded
def get_claude_options_dict(
    self,
    session_id: Optional[str] = None,
    workspace_manager: Optional["WorkspaceManager"] = None
) -> dict[str, Any]:
    """
    生成 ClaudeAgentOptions 参数字典

    Args:
        session_id: 会话 ID（用于工作目录）
        workspace_manager: 工作空间管理器（可选）

    Returns:
        ClaudeAgentOptions 参数字典
    """
    try:
        options = {}

        # 基础配置
        options["model"] = self._config.get("model")

        # 系统提示词
        prompt_loaded = False
        prompt_file_names = [
            self._config.get("system_prompt_file"),
            "agent.md",
            ".claude/agent.md",
            "system_prompt.md",
            "agent_prompt.md",
        ]

        prompt_file_names = [name for name in prompt_file_names if name]

        for prompt_file in prompt_file_names:
            try:
                system_prompt = self.load_prompt_file(prompt_file)
                prompt_loaded = True
                logger.debug(f"成功加载系统提示词文件: {prompt_file}")
                break
            except Exception as e:
                logger.debug(f"无法加载提示词文件 {prompt_file}: {e}")
                continue

        if not prompt_loaded:
            system_prompt = self._get_default_system_prompt()
            logger.info("使用默认系统提示词")

        # 🌟 新增：工作目录配置
        if workspace_manager and workspace_manager.enabled and session_id:
            # 创建工作目录
            workspace_path = workspace_manager.create_workspace(session_id)

            if workspace_path:
                # 设置 cwd 为工作目录
                options["cwd"] = str(workspace_path)

                # 在 system_prompt 中注入工作目录信息
                if workspace_manager.config.get("init_message", True):
                    workspace_info = workspace_manager.get_workspace_info_message(session_id)
                    # 在原始 system_prompt 前面添加工作目录信息
                    system_prompt = f"{workspace_info}\n\n---\n\n{system_prompt}"
                    logger.debug("已注入工作目录信息到 system prompt")
        else:
            # 原有逻辑：使用配置的 cwd 或实例目录
            if "cwd" in self._config:
                options["cwd"] = str(self.resolve_path(self._config["cwd"]))
            else:
                options["cwd"] = str(self.instance_path)

        # 设置 system_prompt
        options["system_prompt"] = system_prompt

        # 工具配置
        if "tools" in self._config:
            tools_config = self._config["tools"]
            if "allowed" in tools_config:
                options["allowed_tools"] = tools_config["allowed"]
            if "disallowed" in tools_config:
                options["disallowed_tools"] = tools_config["disallowed"]

        # 子实例配置
        if "sub_claude_instances" in self._config:
            options["_sub_instances_config"] = self._config["sub_claude_instances"]

        # 高级配置
        if "advanced" in self._config:
            advanced = self._config["advanced"]

            if "permission_mode" in advanced:
                options["permission_mode"] = advanced["permission_mode"]

            if "max_turns" in advanced:
                options["max_turns"] = advanced["max_turns"]

            if "setting_sources" in advanced:
                options["setting_sources"] = advanced["setting_sources"]

            if "env" in advanced:
                options["env"] = advanced["env"]

            if "add_dirs" in advanced:
                options["add_dirs"] = [
                    str(self.resolve_path(d)) for d in advanced["add_dirs"]
                ]

        # 会话记录配置
        if "session_recording" in self._config:
            options["_session_recording_config"] = self._config["session_recording"]

        logger.debug("成功生成 ClaudeAgentOptions 参数")
        return options

    except Exception as e:
        if isinstance(e, ConfigError):
            raise
        raise ConfigError(f"转换配置失败: {e}")
```

### 3.3 修改 `agent_system.py`

#### 添加 WorkspaceManager 集成

```python
class AgentSystem:
    """Claude Agent 系统"""

    def __init__(
        self,
        instance_name: str,
        instances_root: Path | None = None,
        message_bus: Optional["MessageBus"] = None
    ):
        # ... 原有代码 ...

        # 🌟 新增：工作空间管理器
        self.workspace_manager: Optional["WorkspaceManager"] = None

    async def initialize(self) -> None:
        """初始化系统"""
        # ... 原有代码 ...

        # 🌟 新增：初始化工作空间管理器
        workspace_config = self.config_manager.config.get("workspace", {})
        if workspace_config.get("enabled", False):
            from .workspace import WorkspaceManager
            self.workspace_manager = WorkspaceManager(
                self.instance_path,
                workspace_config
            )
            logger.info("工作空间管理器已启用")

    async def query_text(
        self,
        prompt: str,
        resume_session_id: Optional[str] = None
    ) -> QueryResult:
        """执行查询（文本模式）"""
        # ... 创建 session ...

        # 🌟 修改：传递 session_id 和 workspace_manager 给 config_manager
        claude_options_dict = self.config_manager.get_claude_options_dict(
            session_id=session_id,
            workspace_manager=self.workspace_manager
        )

        # ... 原有代码 ...
```

### 3.4 清理工具

#### CLI 脚本：`scripts/cleanup_workspaces.py`

```python
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

    config_mgr = ConfigManager(instance_path)
    config_mgr.load_config()

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

    # 执行清理
    if not args.dry_run:
        report = workspace_mgr.cleanup_old_workspaces(retention_days)
    else:
        # 预览模式：仅扫描，不删除
        # TODO: 实现预览功能
        report = {"scanned": 0, "deleted": 0, "failed": 0, "total_size_mb": 0.0}

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
```

---

## 4. 使用示例

### 4.1 基础配置

**config.yaml**：
```yaml
agent:
  name: "demo_agent"
  description: "演示实例"

model: "claude-sonnet-4-5"
system_prompt_file: ".claude/agent.md"

# 工作目录配置（可选，使用默认值即可）
workspace:
  auto_create: true            # 自动创建
  init_message: true           # 在 system prompt 中告知
  retention_days: 30           # 保留 30 天
```

**效果**：
- 系统自动为每个 session 在 `sessions/{session_id}/workspace/` 创建独立目录
- Claude 会在对话开始时知道自己的工作目录
- 工作目录保留 30 天（需手动清理）

### 4.2 自定义消息模板

**config.yaml**：
```yaml
workspace:
  init_message: true
  init_message_template: |
    # 🎯 你的专属工作空间

    **工作目录**: `{workspace_path}`

    请将所有临时文件和输出文件保存到这个目录。
    此工作空间将保留 {retention_days} 天。
```

### 4.3 代码使用

```python
import asyncio
from src import AgentSystem

async def main():
    # 创建 Agent（自动启用工作空间）
    agent = AgentSystem("demo_agent")
    await agent.initialize()

    # 执行查询
    result = await agent.query_text(
        "请在你的工作目录创建一个 hello.txt 文件，内容为 'Hello World'"
    )

    print(f"Session ID: {result.session_id}")

    # 查看工作目录
    if agent.workspace_manager:
        workspace_path = agent.workspace_manager.get_workspace_path(result.session_id)
        print(f"工作目录: {workspace_path}")

        # 检查文件
        hello_file = workspace_path / "hello.txt"
        if hello_file.exists():
            print(f"✓ 文件已创建: {hello_file.read_text()}")

    agent.cleanup()

asyncio.run(main())
```

### 4.4 清理工作目录

```bash
# 预览将要删除的内容
python scripts/cleanup_workspaces.py demo_agent --dry-run

# 清理超过 30 天的工作目录（使用配置值）
python scripts/cleanup_workspaces.py demo_agent

# 清理超过 7 天的工作目录（覆盖配置）
python scripts/cleanup_workspaces.py demo_agent --days=7
```

---

## 5. 文件变更清单

### 5.1 新增文件

```
src/workspace/
├── __init__.py                          # 导出 WorkspaceManager
└── workspace_manager.py                 # 工作空间管理器（约 200 行）

scripts/
└── cleanup_workspaces.py                # 清理工具（约 80 行）

docs/
└── workspace-guide.md                   # 工作空间使用指南
```

### 5.2 修改文件

```
src/config_manager.py
- 添加 WORKSPACE_FIELDS 验证规则（7 个字段）
- 添加 _validate_workspace() 方法（约 20 行）
- 修改 get_claude_options_dict() 方法签名（添加 2 个参数）
- 修改 get_claude_options_dict() 实现（添加约 15 行）

src/agent_system.py
- 添加 workspace_manager 属性（1 行）
- 修改 initialize() 方法（添加约 8 行）
- 修改 query_text() 方法（修改 1 行参数）

instances/demo_agent/config.yaml
- 添加 workspace 配置示例（约 10 行）

CLAUDE.md
- 更新核心特性说明
- 更新项目结构
- 添加工作空间文档链接
```

### 5.3 文档更新

```
docs/workspace-guide.md (新增)
- 功能介绍
- 配置指南
- 使用示例
- 清理工具说明
- FAQ

CLAUDE.md (更新)
- 在核心特性中添加工作空间隔离
- 在项目结构中添加 workspace 模块
- 在文档索引中添加工作空间指南
```

---

## 6. 测试计划

### 6.1 单元测试

```python
# tests/test_workspace_manager.py

import pytest
from pathlib import Path
from src.workspace import WorkspaceManager

def test_create_workspace():
    """测试创建工作目录"""
    config = {
        "enabled": True,
        "auto_create": True
    }

    instance_path = Path("tests/fixtures/test_instance")
    manager = WorkspaceManager(instance_path, config)

    session_id = "20251221T120000_1000_abc123"
    workspace_path = manager.create_workspace(session_id)

    assert workspace_path is not None
    assert workspace_path.exists()
    assert workspace_path == instance_path / "sessions" / session_id / "workspace"
    assert (workspace_path / ".workspace_info.json").exists()

def test_workspace_disabled():
    """测试未启用时的行为"""
    config = {"enabled": False}
    manager = WorkspaceManager(Path("test"), config)

    workspace_path = manager.create_workspace("session_123")
    assert workspace_path is None

def test_get_workspace_info_message():
    """测试工作目录信息消息生成"""
    config = {
        "enabled": True,
        "retention_days": 30
    }

    manager = WorkspaceManager(Path("test"), config)
    message = manager.get_workspace_info_message("session_123")

    assert "Your Workspace" in message
    assert "session_123/workspace" in message
    assert "30 days" in message
```

### 6.2 集成测试

```python
# tests/integration/test_workspace_integration.py

import asyncio
import pytest
from src import AgentSystem

@pytest.mark.asyncio
async def test_workspace_integration():
    """测试工作空间完整流程"""
    agent = AgentSystem("test_instance")
    await agent.initialize()

    # 验证工作空间管理器已启用
    assert agent.workspace_manager is not None
    assert agent.workspace_manager.enabled

    # 执行查询
    result = await agent.query_text("在工作目录创建 test.txt")

    # 验证工作目录
    workspace_path = agent.workspace_manager.get_workspace_path(result.session_id)
    assert workspace_path.exists()
    assert workspace_path.name == "workspace"

    agent.cleanup()
```

---

## 7. 默认行为

### 7.1 自动启用

工作空间系统是**强制启用**的：
- ✓ 系统启动时自动初始化 WorkspaceManager
- ✓ 每个 session 自动创建独立的工作目录：`sessions/{session_id}/workspace/`
- ✓ 自动在 system prompt 中告知 Claude 工作目录位置
- ✓ 如果未配置 `workspace` 字段，使用默认配置

### 7.2 默认配置

未配置 `workspace` 时，使用以下默认值：
```yaml
workspace:
  enabled: true              # 强制启用
  auto_create: true          # 自动创建
  init_message: true         # 告知 Claude
  retention_days: 30         # 保留 30 天
  max_size_mb: 500           # 最大 500MB
  warn_size_mb: 400          # 警告阈值 400MB
```

---

## 8. 总结

### 8.1 核心价值

1. **隔离性**：每个 session 有独立工作空间，避免污染
2. **简单性**：固定目录结构，强制启用，配置简单
3. **可追溯性**：工作目录与 session_id 绑定，易于查找
4. **安全性**：不支持自动清理，避免误删
5. **自动化**：系统自动创建和管理，无需手动配置

### 8.2 设计优势

- ✓ 配置项精简到 5 个核心选项
- ✓ 代码复杂度低，易于维护
- ✓ 无需处理权限、共享目录等复杂逻辑
- ✓ 强制启用，避免配置混乱
- ✓ 固定目录结构，易于理解

### 8.3 未来扩展

如果未来需要，可以考虑：
1. 工作目录模板（预置文件）
2. 工作目录快照和恢复
3. Web UI 中展示工作目录内容
4. 更智能的清理策略

---

**设计完成时间**：2025-12-21
**版本**：2.0（简化版）
**状态**：待审阅
