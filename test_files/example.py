#!/usr/bin/env python3
"""
示例 Python 文件 - 用于测试文件分析和语法检查
"""

import os
import sys
import json
from typing import Dict, Any, List

def calculate_sum(a: int, b: int) -> int:
    """计算两个整数的和"""
    return a + b

class DataProcessor:
    """数据处理器类"""

    def __init__(self, name: str):
        self.name = name
        self.data = []

    def add_data(self, item: Any) -> None:
        """添加数据项"""
        self.data.append(item)

    def process_data(self) -> Dict[str, Any]:
        """处理数据并返回结果"""
        return {
            "name": self.name,
            "count": len(self.data),
            "items": self.data
        }

def main():
    """主函数"""
    processor = DataProcessor("test")

    # 添加一些测试数据
    for i in range(5):
        processor.add_data(f"item_{i}")

    # 处理数据
    result = processor.process_data()
    print(f"处理结果: {result}")

    # 计算一些值
    sum_result = calculate_sum(10, 20)
    print(f"10 + 20 = {sum_result}")

if __name__ == "__main__":
    main()
