#!/usr/bin/env python3
"""
测试跨进程 session_id 传递机制
"""

import os
import subprocess
import sys
from pathlib import Path

# 添加 src 目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.session.utils import SessionContext

def test_parent_process():
    """父进程：写入 session_id"""
    print(f"=== 父进程 (PID={os.getpid()}) ===")

    # 模拟父进程写入 session_id
    session_id = "test_session_12345"
    instance_path = "instances/demo_agent"

    SessionContext.set_current_session(session_id, instance_path)
    print(f"[OK] Parent wrote session_id: {session_id}")

    # 验证父进程可以读取
    read_session_id = SessionContext.get_current_session()
    print(f"[OK] Parent read session_id: {read_session_id}")
    assert read_session_id == session_id, "Parent failed to read"

    # 启动子进程
    print("\nStarting child process...")
    python_exe = sys.executable
    result = subprocess.run(
        [python_exe, __file__, "child"],
        capture_output=True
    )

    print(f"\nChild process returncode: {result.returncode}")

    if result.returncode == 0:
        print("[OK] Child process succeeded")
    else:
        print("[FAIL] Child process failed")
        return False

    # 清理
    SessionContext.clear_current_session()
    print("\n[OK] Test passed!")
    return True

def test_child_process():
    """子进程：读取 session_id"""
    print(f"=== Child process (PID={os.getpid()}) ===")

    # 尝试读取父进程写入的 session_id
    session_id = SessionContext.get_current_session()

    if session_id:
        print(f"[OK] Child successfully read session_id: {session_id}")
        return True
    else:
        print("[FAIL] Child cannot read session_id")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "child":
        # 子进程模式
        success = test_child_process()
        sys.exit(0 if success else 1)
    else:
        # 父进程模式
        success = test_parent_process()
        sys.exit(0 if success else 1)
