"""
代码质量分析器工具 - 深度分析代码质量和复杂度
"""

from claude_agent_sdk import tool
from typing import Dict, Any, List
import re
import ast
from collections import defaultdict

@tool(
    name="analyze_code",
    description="深度分析代码质量，包括复杂度、耦合度、可维护性等指标",
    input_schema={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "要分析的文件路径"
            },
            "metrics": {
                "type": "array",
                "items": {"type": "string"},
                "description": "要分析的质量指标列表（可选，默认分析所有指标）"
            }
        },
        "required": ["file_path"]
    }
)
async def analyze_code(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    执行代码质量分析

    Args:
        args: 包含文件路径和分析指标的字典

    Returns:
        分析结果和质量报告
    """
    file_path = args.get("file_path", "")
    metrics = args.get("metrics", ["all"])

    try:
        # 读取并解析文件
        with open(file_path, 'r', encoding='utf-8') as f:
            code = f.read()

        tree = ast.parse(code)

        analysis_result = {
            "file_path": file_path,
            "metrics": {},
            "issues": [],
            "suggestions": []
        }

        # 1. 圈复杂度分析
        if "all" in metrics or "complexity" in metrics:
            complexity_result = analyze_complexity(tree)
            analysis_result["metrics"]["complexity"] = complexity_result

            # 检查高复杂度函数
            for func_name, complexity in complexity_result["functions"].items():
                if complexity > 10:
                    analysis_result["issues"].append({
                        "type": "high_complexity",
                        "severity": "warning",
                        "target": func_name,
                        "value": complexity,
                        "message": f"函数 '{func_name}' 的圈复杂度过高 ({complexity})",
                        "suggestion": "考虑将函数拆分为更小的函数"
                    })

        # 2. 函数长度分析
        if "all" in metrics or "function_length" in metrics:
            length_result = analyze_function_length(tree, code)
            analysis_result["metrics"]["function_length"] = length_result

            for func_name, length in length_result["functions"].items():
                if length > 50:
                    analysis_result["issues"].append({
                        "type": "long_function",
                        "severity": "warning",
                        "target": func_name,
                        "value": length,
                        "message": f"函数 '{func_name}' 过长 ({length}行)",
                        "suggestion": "考虑将长函数拆分成多个小函数"
                    })

        # 3. 重复代码检测
        if "all" in metrics or "duplication" in metrics:
            duplication_result = detect_code_duplication(code)
            analysis_result["metrics"]["duplication"] = duplication_result

            if duplication_result["duplicated_lines"] > 0:
                analysis_result["issues"].append({
                    "type": "code_duplication",
                    "severity": "info",
                    "value": duplication_result["duplicated_lines"],
                    "message": f"发现 {duplication_result['duplicated_lines']} 行重复代码",
                    "suggestion": "考虑提取公共函数或类"
                })

        # 4. 注释覆盖率
        if "all" in metrics or "comment_coverage" in metrics:
            comment_result = analyze_comments(tree, code)
            analysis_result["metrics"]["comments"] = comment_result

            if comment_result["coverage"] < 30:
                analysis_result["issues"].append({
                    "type": "low_comment_coverage",
                    "severity": "info",
                    "value": comment_result["coverage"],
                    "message": f"注释覆盖率较低 ({comment_result['coverage']:.1f}%)",
                    "suggestion": "增加注释以提高代码可读性"
                })

        # 5. 依赖分析
        if "all" in metrics or "dependencies" in metrics:
            dep_result = analyze_dependencies(tree)
            analysis_result["metrics"]["dependencies"] = dep_result

            if len(dep_result["external_imports"]) > 10:
                analysis_result["issues"].append({
                    "type": "many_dependencies",
                    "severity": "warning",
                    "value": len(dep_result["external_imports"]),
                    "message": f"外部依赖过多 ({len(dep_result['external_imports'])}个)",
                    "suggestion": "评估是否所有依赖都是必要的"
                })

        # 生成质量评分
        quality_score = calculate_quality_score(analysis_result)
        analysis_result["metrics"]["quality_score"] = quality_score

        # 生成报告
        report_lines = [
            f"## 代码质量分析报告",
            f"**文件**: {file_path}",
            f"**质量评分**: {quality_score}/100",
            f"**发现的问题**: {len(analysis_result['issues'])}",
            "",
        ]

        # 添加指标摘要
        report_lines.append("### 📊 质量指标")
        for metric_name, metric_data in analysis_result["metrics"].items():
            if metric_name == "quality_score":
                continue
            report_lines.append(f"- **{metric_name}**: {format_metric(metric_data)}")

        # 添加问题列表
        if analysis_result["issues"]:
            report_lines.append("\n### 🔍 发现的问题")
            for issue in analysis_result["issues"][:10]:  # 限制显示数量
                severity_emoji = {
                    "error": "🚨",
                    "warning": "⚠️",
                    "info": "💡"
                }.get(issue["severity"], "•")

                report_lines.append(
                    f"{severity_emoji} {issue['message']}\n"
                    f"   💡 建议: {issue['suggestion']}\n"
                )

        # 添加改进建议
        report_lines.append("\n### 💡 改进建议")
        if quality_score >= 80:
            report_lines.append("✅ 代码质量良好！继续保持。")
        elif quality_score >= 60:
            report_lines.append("⚠️ 代码质量尚可，但有一些可以改进的地方。")
        else:
            report_lines.append("🚨 代码质量需要改进，建议优先处理标记为warning和error的问题。")

        return {
            "content": [{
                "type": "text",
                "text": "\n".join(report_lines)
            }],
            "analysis": analysis_result
        }

    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"❌ 分析过程中发生错误: {str(e)}"
            }],
            "error": str(e)
        }

def analyze_complexity(tree: ast.AST) -> Dict[str, Any]:
    """分析代码的圈复杂度"""
    complexities = {}

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            complexity = 1  # 基础复杂度
            for child in ast.walk(node):
                if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor)):
                    complexity += 1
                elif isinstance(child, ast.ExceptHandler):
                    complexity += 1
                elif isinstance(child, ast.With, ast.AsyncWith):
                    complexity += 1
                elif isinstance(child, ast.BoolOp):
                    complexity += len(child.values) - 1
            complexities[node.name] = complexity

    return {
        "functions": complexities,
        "max_complexity": max(complexities.values()) if complexities else 0,
        "avg_complexity": sum(complexities.values()) / len(complexities) if complexities else 0
    }

def analyze_function_length(tree: ast.AST, code: str) -> Dict[str, Any]:
    """分析函数长度"""
    lengths = {}

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # 计算函数行数（不包括文档字符串）
            start_line = node.lineno
            end_line = node.end_lineno if hasattr(node, 'end_lineno') else start_line
            length = end_line - start_line + 1
            lengths[node.name] = length

    return {
        "functions": lengths,
        "max_length": max(lengths.values()) if lengths else 0,
        "avg_length": sum(lengths.values()) / len(lengths) if lengths else 0
    }

def detect_code_duplication(code: str) -> Dict[str, Any]:
    """检测重复代码（简化版）"""
    lines = code.split('\n')
    duplicated_lines = 0
    line_hashes = defaultdict(list)

    for i, line in enumerate(lines):
        # 忽略空行和只包含空格的行
        if line.strip():
            # 简单的行标准化（去除空格）
            normalized = ' '.join(line.split())
            line_hashes[normalized].append(i)

    # 统计重复行
    for hash_line, positions in line_hashes.items():
        if len(positions) > 1:
            duplicated_lines += len(positions) - 1

    return {
        "duplicated_lines": duplicated_lines,
        "duplication_rate": (duplicated_lines / len(lines) * 100) if lines else 0
    }

def analyze_comments(tree: ast.AST, code: str) -> Dict[str, Any]:
    """分析注释覆盖率"""
    lines = code.split('\n')
    comment_lines = 0
    code_lines = 0

    for line in lines:
        stripped = line.strip()
        if stripped:
            if stripped.startswith('#'):
                comment_lines += 1
            elif not stripped.startswith('"""') and not stripped.startswith("'''"):
                code_lines += 1

    # 计算文档字符串
    docstring_count = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if ast.get_docstring(node):
                docstring_count += 1

    total_items = sum(1 for node in ast.walk(tree)
                     if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)))

    return {
        "comment_lines": comment_lines,
        "code_lines": code_lines,
        "docstrings": docstring_count,
        "total_items": total_items,
        "coverage": (comment_lines + docstring_count * 3) / code_lines * 100 if code_lines > 0 else 0
    }

def analyze_dependencies(tree: ast.AST) -> Dict[str, Any]:
    """分析依赖关系"""
    imports = set()
    from_imports = defaultdict(set)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                from_imports[node.module].update(
                    alias.name for alias in node.names
                )

    # 区分标准库和外部依赖
    stdlib_modules = {
        'os', 'sys', 'json', 'datetime', 'collections', 'itertools',
        'functools', 'operator', 're', 'math', 'random', 'time'
    }

    external_imports = [imp for imp in imports if imp not in stdlib_modules]
    external_from_imports = {k: v for k, v in from_imports.items()
                            if k and k.split('.')[0] not in stdlib_modules}

    return {
        "imports": list(imports),
        "from_imports": dict(from_imports),
        "external_imports": external_imports,
        "external_from_imports": external_from_imports,
        "total_dependencies": len(external_imports) + len(external_from_imports)
    }

def calculate_quality_score(analysis_result: Dict[str, Any]) -> int:
    """计算质量评分"""
    base_score = 100

    # 根据问题扣分
    for issue in analysis_result["issues"]:
        if issue["severity"] == "error":
            base_score -= 10
        elif issue["severity"] == "warning":
            base_score -= 5
        elif issue["severity"] == "info":
            base_score -= 2

    # 根据复杂度调整
    if "complexity" in analysis_result["metrics"]:
        max_complexity = analysis_result["metrics"]["complexity"]["max_complexity"]
        if max_complexity > 15:
            base_score -= 15
        elif max_complexity > 10:
            base_score -= 10
        elif max_complexity > 5:
            base_score -= 5

    # 确保评分在0-100之间
    return max(0, min(100, base_score))

def format_metric(metric_data: Any) -> str:
    """格式化指标数据"""
    if isinstance(metric_data, dict):
        if "max_complexity" in metric_data:
            return f"平均复杂度: {metric_data['avg_complexity']:.1f}, 最大: {metric_data['max_complexity']}"
        elif "max_length" in metric_data:
            return f"平均长度: {metric_data['avg_length']:.1f}行, 最大: {metric_data['max_length']}行"
        elif "coverage" in metric_data:
            return f"覆盖率: {metric_data['coverage']:.1f}%"
        elif "total_dependencies" in metric_data:
            return f"总依赖数: {metric_data['total_dependencies']}"
    return str(metric_data)