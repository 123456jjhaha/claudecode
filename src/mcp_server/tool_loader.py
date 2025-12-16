"""
工具加载器 - 简化版，支持 FastMCP 原生工具格式
"""

import sys
import importlib
import importlib.util
import inspect
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Callable

# 处理相对导入问题
try:
    from ..logging_config import get_logger
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from logging_config import get_logger

logger = get_logger(__name__)


class NativeToolFunction:
    """原生工具函数包装器"""

    def __init__(
        self,
        func: Callable,
        module_name: str,
        original_name: str
    ):
        """
        初始化原生工具函数

        Args:
            func: 工具函数
            module_name: 模块名
            original_name: 原始函数名
        """
        self.func = func
        self.module_name = module_name
        self.original_name = original_name
        self.name = f"{module_name}__{original_name}"

        # 从函数签名获取描述
        self.description = func.__doc__.strip() if func.__doc__ else f"工具函数: {original_name}"

    async def __call__(self, **kwargs) -> Any:
        """
        调用工具函数

        Args:
            **kwargs: 关键字参数

        Returns:
            函数执行结果
        """
        try:
            # 直接调用函数
            if inspect.iscoroutinefunction(self.func):
                return await self.func(**kwargs)
            else:
                return self.func(**kwargs)
        except Exception as e:
            logger.error(f"工具 {self.name} 执行失败: {e}")
            return {
                "error": str(e),
                "error_type": type(e).__name__
            }


class SimpleToolLoader:
    """简化的工具加载器，直接支持 FastMCP 原生格式"""

    def __init__(self, instance_path: Path):
        """
        初始化工具加载器

        Args:
            instance_path: 实例目录路径
        """
        self.instance_path = Path(instance_path)
        self.tools_dir = self.instance_path / "tools"
        self._tools: List[NativeToolFunction] = []

    def discover_tools(self) -> List[NativeToolFunction]:
        """
        发现 tools/ 目录下的所有工具函数

        Returns:
            工具函数列表
        """
        if not self.tools_dir.exists():
            logger.info(f"工具目录不存在: {self.tools_dir}")
            return []

        logger.info(f"扫描工具目录: {self.tools_dir}")

        tools = []

        # 遍历 tools/ 目录下的所有 .py 文件
        for py_file in self.tools_dir.glob("*.py"):
            if py_file.name.startswith("_"):
                continue  # 跳过 __init__.py 等文件

            module_name = py_file.stem
            logger.debug(f"扫描模块: {module_name}")

            try:
                # 动态导入模块
                module = self._import_module(py_file, module_name)

                # 提取工具函数
                module_tools = self._extract_tools_from_module(module, module_name)
                tools.extend(module_tools)

            except Exception as e:
                logger.error(f"加载模块失败 {module_name}: {e}")
                continue

        self._tools = tools
        logger.info(f"发现 {len(tools)} 个工具")

        return tools

    def _import_module(self, py_file: Path, module_name: str) -> Any:
        """动态导入 Python 模块"""
        spec = importlib.util.spec_from_file_location(module_name, py_file)
        if spec is None or spec.loader is None:
            raise ImportError(f"无法加载模块规范: {py_file}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        return module

    def _extract_tools_from_module(self, module: Any, module_name: str) -> List[NativeToolFunction]:
        """
        从模块中提取工具函数

        查找所有异步函数（FastMCP 推荐使用异步函数）
        """
        tools = []

        for name, obj in inspect.getmembers(module):
            # 跳过私有属性、模块和类
            if name.startswith('_') or inspect.ismodule(obj) or inspect.isclass(obj):
                continue

            # 查找异步函数（FastMCP 工具通常是异步的）
            if inspect.isfunction(obj) and inspect.iscoroutinefunction(obj):
                # 跳过明显的非工具函数（如 FastMCP 相关的导入）
                if name in ['FastMCP']:
                    continue

                tool = NativeToolFunction(
                    func=obj,
                    module_name=module_name,
                    original_name=name
                )
                tools.append(tool)
                logger.info(f"发现工具: {module_name}.{name} -> {tool.name}")

        return tools

    def get_tools(self) -> List[NativeToolFunction]:
        """获取已发现的所有工具"""
        return self._tools.copy()

    def get_tool_names(self) -> List[str]:
        """获取所有工具名称列表"""
        return [tool.name for tool in self._tools]


def load_tools_from_instance(instance_path: Path) -> Tuple[List[NativeToolFunction], List[str]]:
    """
    从实例目录加载所有工具

    Args:
        instance_path: 实例目录路径

    Returns:
        (工具函数列表, 工具名称列表)
    """
    loader = SimpleToolLoader(instance_path)
    tools = loader.discover_tools()
    tool_names = loader.get_tool_names()

    return tools, tool_names


def load_sub_instance_tools(instance_path: Path) -> List[Any]:
    """
    从实例配置中加载子实例工具

    Args:
        instance_path: 实例目录路径

    Returns:
        子实例工具列表（SubInstanceTool 对象）
    """
    try:
        # 延迟导入避免循环依赖
        import sys
        from pathlib import Path

        # 添加项目根目录和 src 目录到 sys.path
        project_root = Path(__file__).parent.parent.parent
        src_dir = project_root / "src"

        for path in [str(project_root), str(src_dir)]:
            if path not in sys.path:
                sys.path.insert(0, path)

        # 使用绝对导入
        from src.config_manager import ConfigManager
        from src.sub_instance_adapter import SubInstanceTool

        # 读取配置文件
        config_manager = ConfigManager(instance_path)
        config = config_manager.load_config()

        # 提取子实例配置
        sub_instances_config = config.get("sub_claude_instances", {})

        if not sub_instances_config:
            logger.debug("配置中没有子实例")
            return []

        logger.info(f"发现 {len(sub_instances_config)} 个子实例配置")

        # 获取 instances_root（实例目录的父目录）
        instances_root = instance_path.parent

        # 创建子实例工具
        tools = []
        for instance_name, relative_path in sub_instances_config.items():
            try:
                # 验证实例路径
                sub_instance_path = instances_root / relative_path
                if not sub_instance_path.exists():
                    logger.warning(f"子实例目录不存在: {sub_instance_path}")
                    continue

                # 创建子实例工具
                tool = SubInstanceTool(
                    instance_name=instance_name,
                    instance_path=Path(relative_path),
                    instances_root=instances_root
                )
                tools.append(tool)

                logger.info(f"创建子实例工具: {tool.name}")

            except Exception as e:
                logger.error(f"创建子实例工具失败 {instance_name}: {e}")

        logger.info(f"共创建 {len(tools)} 个子实例工具")
        return tools

    except Exception as e:
        logger.error(f"加载子实例工具失败: {e}")
        return []