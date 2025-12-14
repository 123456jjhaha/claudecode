"""
MCP 服务器进程管理器

负责启动、管理和关闭 MCP 服务器子进程。
"""

import atexit
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# 处理相对导入问题
try:
    from ..logging_config import get_logger
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from logging_config import get_logger

logger = get_logger(__name__)


class ProcessManager:
    """MCP 服务器进程管理器"""

    def __init__(self, instance_path: Path):
        """
        初始化进程管理器

        Args:
            instance_path: 实例目录路径
        """
        self.instance_path = Path(instance_path)
        self._process: Optional[subprocess.Popen] = None
        self._server_config: Optional[Dict[str, Any]] = None

        # 注册退出处理器
        atexit.register(self.shutdown)

    def start_server(self) -> Dict[str, Any]:
        """
        启动 MCP 服务器进程

        Returns:
            MCP 服务器配置字典（stdio 格式）
        """
        if self._process is not None:
            logger.warning("MCP 服务器已经运行")
            return self._server_config

        logger.info(f"启动 MCP 服务器进程，实例: {self.instance_path.name}")

        try:
            # 构建服务器启动命令
            server_script = Path(__file__).parent / "server.py"
            cmd = [sys.executable, str(server_script), "--instance-path", str(self.instance_path)]

            # 启动子进程
            self._process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=0,
                # 不继承文件描述符
                close_fds=True
            )

            # 检查进程是否启动成功
            time.sleep(0.1)
            if self._process.poll() is not None:
                # 进程已退出
                stderr = self._process.stderr.read() if self._process.stderr else ""
                raise RuntimeError(f"MCP 服务器启动失败: {stderr}")

            # 创建 stdio 配置
            self._server_config = {
                "type": "stdio",
                "command": sys.executable,
                "args": [str(server_script), "--instance-path", str(self.instance_path)],
                "env": {
                    "PYTHONPATH": str(Path(__file__).parent.parent.parent)
                }
            }

            logger.info(f"MCP 服务器启动成功，PID: {self._process.pid}")
            return self._server_config

        except Exception as e:
            logger.error(f"启动 MCP 服务器失败: {e}")
            self._process = None
            raise

    def start_custom_server(self, cmd: list, server_name: str = "custom") -> Dict[str, Any]:
        """
        启动自定义 MCP 服务器进程

        Args:
            cmd: 启动命令列表
            server_name: 服务器名称（用于日志）

        Returns:
            MCP 服务器配置字典（stdio 格式）
        """
        if self._process is not None:
            logger.warning(f"{server_name} MCP 服务器已经运行")
            return self._server_config

        logger.info(f"启动 {server_name} MCP 服务器进程")

        try:
            # 启动子进程
            self._process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=0,
                # 不继承文件描述符
                close_fds=True
            )

            # 检查进程是否启动成功
            time.sleep(0.1)
            if self._process.poll() is not None:
                # 进程已退出
                stderr = self._process.stderr.read() if self._process.stderr else ""
                raise RuntimeError(f"{server_name} MCP 服务器启动失败: {stderr}")

            # 创建 stdio 配置
            self._server_config = {
                "type": "stdio",
                "command": cmd[0],
                "args": cmd[1:],
                "env": {
                    "PYTHONPATH": str(Path(__file__).parent.parent.parent)
                }
            }

            logger.info(f"{server_name} MCP 服务器启动成功，PID: {self._process.pid}")
            return self._server_config

        except Exception as e:
            logger.error(f"启动 {server_name} MCP 服务器失败: {e}")
            self._process = None
            raise

    def shutdown(self):
        """关闭 MCP 服务器进程"""
        if self._process is None:
            return

        logger.info("关闭 MCP 服务器进程")

        try:
            # 尝试优雅关闭
            if self._process.poll() is None:
                # 发送 SIGTERM
                self._process.terminate()
                self._process.wait(timeout=5)
                logger.info("MCP 服务器已优雅关闭")
        except subprocess.TimeoutExpired:
            # 强制关闭
            logger.warning("强制关闭 MCP 服务器")
            self._process.kill()
            self._process.wait()
        except Exception as e:
            logger.error(f"关闭 MCP 服务器时出错: {e}")
        finally:
            self._process = None
            self._server_config = None

    def is_running(self) -> bool:
        """
        检查服务器是否运行中

        Returns:
            True 如果服务器运行中
        """
        if self._process is None:
            return False

        # 检查进程状态
        return self._process.poll() is None

    def get_server_config(self) -> Optional[Dict[str, Any]]:
        """
        获取服务器配置

        Returns:
            MCP 服务器配置字典
        """
        return self._server_config.copy() if self._server_config else None

    def restart_server(self) -> Dict[str, Any]:
        """
        重启 MCP 服务器

        Returns:
            新的服务器配置
        """
        logger.info("重启 MCP 服务器")
        self.shutdown()
        return self.start_server()

    def __del__(self):
        """析构函数，确保进程被清理"""
        self.shutdown()


class ProcessManagerRegistry:
    """进程管理器注册表，管理多个实例的进程"""

    _instance = None
    _managers: Dict[str, ProcessManager] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_manager(cls, instance_path: Path) -> ProcessManager:
        """
        获取指定实例的进程管理器

        Args:
            instance_path: 实例目录路径

        Returns:
            ProcessManager 实例
        """
        instance_key = str(instance_path.resolve())

        if instance_key not in cls._managers:
            cls._managers[instance_key] = ProcessManager(instance_path)

        return cls._managers[instance_key]

    @classmethod
    def shutdown_all(cls):
        """关闭所有管理的进程"""
        logger.info(f"关闭 {len(cls._managers)} 个 MCP 服务器进程")
        for manager in cls._managers.values():
            manager.shutdown()
        cls._managers.clear()

    @classmethod
    def restart_all(cls):
        """重启所有管理的进程"""
        logger.info(f"重启 {len(cls._managers)} 个 MCP 服务器进程")
        for manager in cls._managers.values():
            if manager.is_running():
                manager.restart_server()


# 注册全局退出处理器
atexit.register(ProcessManagerRegistry.shutdown_all)