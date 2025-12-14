#!/usr/bin/env python3
"""
有语法错误的 Python 文件
"""

import os
import sys

def broken_function(
    """缺少函数参数，会导致语法错误"""
    print("This function has a syntax error")
    # 缺少 return 语句和闭合的括号

class IncompleteClass
    """缺少冒号，会导致语法错误"""
    def __init__(self):
        self.value = 42

    def method_with_error(self)
        """方法定义缺少冒号"""
        print("Missing colon")

if __name__ == "__main__"
    """if 语句也缺少冒号"""
    broken_function()
