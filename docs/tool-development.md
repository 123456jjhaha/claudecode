# 工具开发指南

本文档详细说明了如何为 Claude Agent System 开发自定义工具。

## 目录

- [工具概述](#工具概述)
- [快速开始](#快速开始)
- [工具开发规范](#工具开发规范)
- [工具命名规则](#工具命名规则)
- [工具类型](#工具类型)
- [高级功能](#高级功能)
- [最佳实践](#最佳实践)
- [调试技巧](#调试技巧)
- [示例工具](#示例工具)

## 工具概述

Claude Agent System 采用零样板代码的工具设计理念。您只需要在 `tools/` 目录下编写异步函数，系统会自动发现并注册为 MCP 工具。

### 核心特性

- **零样板代码**：无需装饰器，直接写异步函数
- **自动发现**：扫描 `tools/` 目录，自动注册工具
- **类型支持**：完整的类型注解支持
- **文档驱动**：使用文档字符串作为工具描述
- **错误处理**：内置异常处理机制

## 快速开始

### 创建第一个工具

1. 在实例目录下创建 `tools/` 文件夹：
   ```
   instances/demo_agent/
   └── tools/
       └── calculator.py
   ```

2. 编写工具代码：
   ```python
   # instances/demo_agent/tools/calculator.py

   async def add(a: float, b: float) -> dict:
       """
       计算两个数字的和

       Args:
           a: 第一个数字
           b: 第二个数字

       Returns:
           包含计算结果的字典
       """
       result = a + b
       return {
           "operation": "add",
           "operands": [a, b],
           "result": result
       }
   ```

3. 重启 Agent，工具会自动注册为 `calculator__add`

### 使用工具

```python
import asyncio
from src import AgentSystem

async def main():
    agent = AgentSystem("demo_agent")
    await agent.initialize()

    # Claude 会自动决定何时使用工具
    result = await agent.query_text("请计算 123 + 456")
    print(result.result)

    agent.cleanup()

asyncio.run(main())
```

## 工具开发规范

### 函数签名要求

1. **必须是异步函数**：
   ```python
   async def my_function(param1: str, param2: int = 10) -> dict:
   ```

2. **必须有类型注解**：
   ```python
   async def process_data(data: List[Dict[str, Any]]) -> Dict[str, Any]:
   ```

3. **推荐返回字典**：
   ```python
   return {
       "status": "success",
       "result": processed_data,
       "metadata": {...}
   }
   ```

### 文档字符串规范

使用 Google 风格的文档字符串：

```python
async def analyze_text(
    text: str,
    language: str = "en",
    include_sentiment: bool = False
) -> Dict[str, Any]:
    """分析文本内容

    这个工具可以分析文本的语言、情感、关键实体等。

    Args:
        text: 要分析的文本内容
        language: 文本语言代码，默认为英语
        include_sentiment: 是否包含情感分析

    Returns:
        包含分析结果的字典，格式如下：
        {
            "language": "检测到的语言",
            "sentiment": "情感分数（可选）",
            "entities": ["实体列表"],
            "keywords": ["关键词列表"]
        }

    Raises:
        ValueError: 当文本为空时
        RuntimeError: 当分析服务不可用时

    Example:
        >>> result = await analyze_text("Hello world!", include_sentiment=True)
        >>> print(result["language"])
        'en'
    """
```

## 工具命名规则

### 自动命名机制

- **文件名**：`calculator.py`
- **函数名**：`add`
- **工具名**：`calculator__add`
- **完整 MCP 名称**：`mcp__custom_tools__calculator__add`

### 命名最佳实践

1. **文件名要有意义**：
   - ✅ `file_analyzer.py`
   - ❌ `tools1.py`

2. **函数名要描述性**：
   - ✅ `extract_keywords`
   - ❌ `process`

3. **避免特殊字符**：
   - ✅ 使用字母、数字、下划线
   - ❌ 避免空格、连字符

### 权限配置

在 `config.yaml` 中配置工具权限：

```yaml
tools:
  allowed:
    - "mcp__custom_tools__calculator__*"      # 允许所有 calculator 工具
    - "mcp__custom_tools__file_analyzer_*"    # 允许所有文件分析工具
    - "mcp__custom_tools__text_analyzer__extract_keywords"  # 允许特定工具
```

## 工具类型

### 1. 简单计算工具

```python
# instances/demo_agent/tools/math.py

async def calculate_area(shape: str, dimensions: Dict[str, float]) -> dict:
    """
    计算几何图形的面积

    Args:
        shape: 图形类型（circle, rectangle, triangle）
        dimensions: 包含必要尺寸的字典

    Returns:
        包含面积计算结果的字典
    """
    shape = shape.lower()

    if shape == "circle":
        radius = dimensions.get("radius", 0)
        area = 3.14159 * radius ** 2
    elif shape == "rectangle":
        width = dimensions.get("width", 0)
        height = dimensions.get("height", 0)
        area = width * height
    elif shape == "triangle":
        base = dimensions.get("base", 0)
        height = dimensions.get("height", 0)
        area = 0.5 * base * height
    else:
        raise ValueError(f"不支持的图形类型: {shape}")

    return {
        "shape": shape,
        "area": area,
        "dimensions": dimensions
    }
```

### 2. 文件操作工具

```python
# instances/demo_agent/tools/file_utils.py

import os
import json
from pathlib import Path
from typing import List, Dict, Any

async def read_json_file(file_path: str) -> Dict[str, Any]:
    """
    读取 JSON 文件内容

    Args:
        file_path: JSON 文件的路径

    Returns:
        解析后的 JSON 数据

    Raises:
        FileNotFoundError: 文件不存在
        json.JSONDecodeError: JSON 格式错误
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    if not path.suffix.lower() == ".json":
        raise ValueError(f"不是 JSON 文件: {file_path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return {
        "file_path": str(path),
        "size": path.stat().st_size,
        "data": data
    }

async def list_directory_contents(
    directory: str,
    include_hidden: bool = False,
    pattern: str = "*"
) -> Dict[str, List[str]]:
    """
    列出目录内容

    Args:
        directory: 目录路径
        include_hidden: 是否包含隐藏文件
        pattern: 文件匹配模式（支持通配符）

    Returns:
        包含文件和子目录列表的字典
    """
    path = Path(directory)

    if not path.exists():
        raise FileNotFoundError(f"目录不存在: {directory}")

    if not path.is_dir():
        raise ValueError(f"不是目录: {directory}")

    files = []
    directories = []

    for item in path.glob(pattern):
        if not include_hidden and item.name.startswith("."):
            continue

        if item.is_file():
            files.append(item.name)
        elif item.is_dir():
            directories.append(item.name)

    return {
        "directory": str(path),
        "files": sorted(files),
        "directories": sorted(directories),
        "total_items": len(files) + len(directories)
    }
```

### 3. API 调用工具

```python
# instances/demo_agent/tools/weather.py

import aiohttp
from typing import Dict, Any, Optional

async def get_weather(
    city: str,
    country_code: Optional[str] = None,
    units: str = "metric"
) -> Dict[str, Any]:
    """
    获取指定城市的天气信息

    Args:
        city: 城市名称
        country_code: 国家代码（可选，如 US, CN）
        units: 单位系统（metric, imperial, kelvin）

    Returns:
        包含天气信息的字典
    """
    # 注意：这只是一个示例，实际使用需要 API key
    api_key = os.getenv("WEATHER_API_KEY")
    if not api_key:
        raise ValueError("需要设置 WEATHER_API_KEY 环境变量")

    # 构建查询字符串
    location = city
    if country_code:
        location = f"{city},{country_code}"

    url = f"http://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": location,
        "appid": api_key,
        "units": units
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()

                    # 提取关键信息
                    weather = {
                        "city": data["name"],
                        "country": data["sys"]["country"],
                        "temperature": data["main"]["temp"],
                        "feels_like": data["main"]["feels_like"],
                        "humidity": data["main"]["humidity"],
                        "pressure": data["main"]["pressure"],
                        "description": data["weather"][0]["description"],
                        "units": units
                    }

                    return {
                        "success": True,
                        "weather": weather,
                        "raw_data": data  # 保留原始数据供调试
                    }
                else:
                    error_data = await response.json()
                    return {
                        "success": False,
                        "error": error_data.get("message", "未知错误"),
                        "status_code": response.status
                    }

        except aiohttp.ClientError as e:
            return {
                "success": False,
                "error": f"网络请求失败: {str(e)}"
            }
```

### 4. 数据处理工具

```python
# instances/demo_agent/tools/data_processor.py

import pandas as pd
import numpy as np
from typing import List, Dict, Any, Union

async def analyze_csv_data(
    file_path: str,
    columns: Optional[List[str]] = None,
    operation: str = "summary"
) -> Dict[str, Any]:
    """
    分析 CSV 数据文件

    Args:
        file_path: CSV 文件路径
        columns: 要分析的列名列表（可选）
        operation: 分析类型（summary, describe, correlation）

    Returns:
        包含分析结果的字典
    """
    try:
        # 读取 CSV 文件
        df = pd.read_csv(file_path)

        # 如果指定了列，只分析这些列
        if columns:
            df = df[columns]

        result = {
            "file_path": file_path,
            "shape": df.shape,
            "columns": df.columns.tolist(),
            "dtypes": df.dtypes.to_dict()
        }

        if operation == "summary":
            result["summary"] = df.describe().to_dict()
        elif operation == "describe":
            result["description"] = {
                "missing_values": df.isnull().sum().to_dict(),
                "unique_counts": df.nunique().to_dict()
            }
        elif operation == "correlation":
            # 只计算数值列的相关性
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            if len(numeric_cols) > 1:
                result["correlation"] = df[numeric_cols].corr().to_dict()
            else:
                result["correlation"] = "需要至少两个数值列"

        return result

    except Exception as e:
        return {
            "error": f"分析失败: {str(e)}",
            "file_path": file_path
        }

async def generate_report(
    data: Dict[str, Any],
    format: str = "markdown"
) -> str:
    """
    根据数据生成报告

    Args:
        data: 要报告的数据
        format: 报告格式（markdown, json, html）

    Returns:
        格式化的报告字符串
    """
    if format == "markdown":
        report = "# 数据分析报告\n\n"

        if "file_path" in data:
            report += f"**文件路径**: {data['file_path']}\n\n"

        if "shape" in data:
            rows, cols = data["shape"]
            report += f"**数据维度**: {rows} 行 × {cols} 列\n\n"

        if "summary" in data:
            report += "## 统计摘要\n\n"
            report += "| 列名 | 平均值 | 标准差 | 最小值 | 最大值 |\n"
            report += "|------|--------|--------|--------|--------|\n"

            for col, stats in data["summary"].items():
                if isinstance(stats, dict) and "mean" in stats:
                    report += f"| {col} | {stats.get('mean', 'N/A'):.2f} | "
                    report += f"{stats.get('std', 'N/A'):.2f} | "
                    report += f"{stats.get('min', 'N/A'):.2f} | "
                    report += f"{stats.get('max', 'N/A'):.2f} |\n"

        return report

    elif format == "json":
        return json.dumps(data, indent=2, ensure_ascii=False)

    elif format == "html":
        # 简单的 HTML 格式
        html = "<html><body><h1>数据分析报告</h1>"
        html += f"<p>文件: {data.get('file_path', 'N/A')}</p>"
        if "shape" in data:
            html += f"<p>维度: {data['shape'][0]} 行 × {data['shape'][1]} 列</p>"
        html += "</body></html>"
        return html

    else:
        raise ValueError(f"不支持的格式: {format}")
```

## 高级功能

### 1. 工具链调用

工具可以调用其他工具：

```python
# instances/demo_agent/tools/advanced_analyzer.py

from .file_utils import read_json_file
from .data_processor import analyze_csv_data

async def analyze_project_report(
    project_dir: str
) -> Dict[str, Any]:
    """
    分析项目目录中的报告文件

    Args:
        project_dir: 项目目录路径

    Returns:
        综合分析结果
    """
    # 查找报告文件
    report_path = Path(project_dir) / "report.json"
    csv_path = Path(project_dir) / "data.csv"

    results = {
        "project_dir": project_dir,
        "findings": {}
    }

    # 调用其他工具
    if report_path.exists():
        report_data = await read_json_file(str(report_path))
        results["findings"]["report"] = report_data

    if csv_path.exists():
        csv_analysis = await analyze_csv_data(str(csv_path))
        results["findings"]["data"] = csv_analysis

    return results
```

### 2. 异步文件操作

```python
import aiofiles
from pathlib import Path

async def process_large_file(
    file_path: str,
    chunk_size: int = 1024
) -> Dict[str, Any]:
    """
    异步处理大文件

    Args:
        file_path: 文件路径
        chunk_size: 每次读取的块大小（KB）

    Returns:
        处理统计信息
    """
    path = Path(file_path)
    total_size = path.stat().st_size
    processed = 0
    line_count = 0

    async with aiofiles.open(path, "r", encoding="utf-8") as f:
        async for line in f:
            processed += len(line.encode())
            line_count += 1

            # 这里可以添加实际的行处理逻辑
            # processed_line = await process_line(line)

            if processed % (chunk_size * 1024) == 0:
                print(f"已处理: {processed / total_size * 100:.1f}%")

    return {
        "file_path": str(path),
        "total_size": total_size,
        "processed": processed,
        "line_count": line_count,
        "status": "completed"
    }
```

### 3. 缓存机制

```python
import asyncio
from functools import wraps
from typing import Any, Callable

def cache_result(ttl: int = 300):
    """简单的内存缓存装饰器"""
    def decorator(func: Callable) -> Callable:
        cache = {}

        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # 生成缓存键
            cache_key = str(args) + str(sorted(kwargs.items()))

            # 检查缓存
            if cache_key in cache:
                result, timestamp = cache[cache_key]
                if asyncio.get_event_loop().time() - timestamp < ttl:
                    return result

            # 执行函数
            result = await func(*args, **kwargs)

            # 存入缓存
            cache[cache_key] = (result, asyncio.get_event_loop().time())

            return result

        return wrapper
    return decorator

async def fetch_expensive_data(query: str) -> Dict[str, Any]:
    """
    获取耗时数据（带缓存）

    Args:
        query: 查询参数

    Returns:
        查询结果
    """
    # 模拟耗时操作
    await asyncio.sleep(2)

    return {
        "query": query,
        "data": f"结果数据 for {query}",
        "timestamp": asyncio.get_event_loop().time()
    }

# 使用缓存
fetch_expensive_data_cached = cache_result(ttl=60)(fetch_expensive_data)
```

## 最佳实践

### 1. 错误处理

```python
async def robust_tool(param: str) -> Dict[str, Any]:
    """
    错误处理示例
    """
    try:
        # 验证输入
        if not param:
            raise ValueError("参数不能为空")

        # 执行操作
        result = await some_operation(param)

        return {
            "success": True,
            "result": result
        }

    except ValueError as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": "ValidationError"
        }
    except Exception as e:
        # 记录错误日志
        logger.error(f"工具执行失败: {e}", exc_info=True)

        return {
            "success": False,
            "error": "内部错误",
            "error_type": "InternalError"
        }
```

### 2. 输入验证

```python
from typing import Any, Dict
import re

async def validated_tool(
    email: str,
    age: int,
    options: Dict[str, Any]
) -> Dict[str, Any]:
    """
    输入验证示例
    """
    # 邮箱格式验证
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        raise ValueError("邮箱格式不正确")

    # 年龄范围验证
    if not 0 < age < 150:
        raise ValueError("年龄必须在 0-150 之间")

    # 选项验证
    required_options = ["format", "include_metadata"]
    for opt in required_options:
        if opt not in options:
            raise ValueError(f"缺少必需选项: {opt}")

    # 执行操作
    return process_validated_input(email, age, options)
```

### 3. 性能优化

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

async def batch_process(items: List[str]) -> List[Dict[str, Any]]:
    """
    批量处理示例
    """
    # 使用线程池执行 CPU 密集型任务
    with ThreadPoolExecutor(max_workers=4) as executor:
        loop = asyncio.get_event_loop()

        # 并发处理
        tasks = []
        for item in items:
            task = loop.run_in_executor(
                executor,
                cpu_intensive_task,
                item
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理异常
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "item": items[i],
                    "error": str(result)
                })
            else:
                processed_results.append(result)

        return processed_results
```

## 调试技巧

### 1. 日志记录

```python
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def debug_tool(data: Any) -> Dict[str, Any]:
    """
    调试示例
    """
    logger.info(f"开始处理数据: {type(data)}")
    logger.debug(f"数据详情: {data}")

    try:
        result = process_data(data)
        logger.info(f"处理成功: {len(result)} 项")
        return result
    except Exception as e:
        logger.error(f"处理失败: {e}", exc_info=True)
        raise
```

### 2. 测试工具

```python
# 在工具文件末尾添加测试代码
if __name__ == "__main__":
    import asyncio

    async def test_tool():
        """测试工具功能"""
        test_cases = [
            {"input": "test", "expected": "result"},
            {"input": "", "expected": "error"}
        ]

        for case in test_cases:
            print(f"测试输入: {case['input']}")
            try:
                result = await your_tool(case['input'])
                print(f"结果: {result}")
            except Exception as e:
                print(f"错误: {e}")

    asyncio.run(test_tool())
```

### 3. 性能分析

```python
import time
from functools import wraps

def measure_time(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.time()
        result = await func(*args, **kwargs)
        end = time.time()

        print(f"{func.__name__} 执行时间: {end - start:.2f} 秒")
        return result
    return wrapper

@measure_time
async def performance_sensitive_tool(data: Any) -> Dict[str, Any]:
    """
    性能敏感的工具
    """
    # 执行操作
    return process_data(data)
```

## 示例工具集合

### 完整的工具示例项目

```
instances/demo_agent/tools/
├── __init__.py          # 可选：工具包初始化
├── calculator.py        # 数学计算工具
├── file_utils.py        # 文件操作工具
├── web_scraper.py       # 网页抓取工具
├── data_analyzer.py     # 数据分析工具
├── api_client.py        # API 客户端工具
└── report_generator.py  # 报告生成工具
```

每个工具文件都应该专注于单一职责，保持代码的模块化和可维护性。