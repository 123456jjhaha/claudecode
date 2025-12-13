"""
代码风格检查器工具 - 检查代码风格和规范
"""

from claude_agent_sdk import tool
from typing import Dict, Any, List
import re
import os

@tool(
    name="lint_check",
    description="检查代码文件的风格问题，包括PEP8、命名规范、代码长度等",
    input_schema={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "要检查的文件路径"
            },
            "rules": {
                "type": "array",
                "items": {"type": "string"},
                "description": "要应用的检查规则列表（可选，默认应用所有规则）"
            }
        },
        "required": ["file_path"]
    }
)
async def lint_check(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    执行代码风格检查

    Args:
        args: 包含文件路径和可选规则的字典

    Returns:
        检查结果和问题列表
    """
    file_path = args.get("file_path", "")
    rules = args.get("rules", ["all"])

    issues = []

    try:
        # 读取文件
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # 检查规则
        for i, line in enumerate(lines, 1):
            # 移除行尾的换行符
            line_content = line.rstrip('\n\r')

            # 1. 检查行长度（PEP8: 79字符）
            if len(line_content) > 79 and ("all" in rules or "line_length" in rules):
                issues.append({
                    "line": i,
                    "rule": "line_length",
                    "severity": "warning",
                    "message": f"行过长 ({len(line_content)} > 79字符)",
                    "suggestion": "考虑将长行拆分为多行"
                })

            # 2. 检查尾随空格
            if line_content != line.rstrip() and ("all" in rules or "trailing_whitespace" in rules):
                issues.append({
                    "line": i,
                    "rule": "trailing_whitespace",
                    "severity": "error",
                    "message": "行尾有多余空格",
                    "suggestion": "删除行尾空格"
                })

            # 3. 检查制表符（应该使用空格）
            if '\t' in line and ("all" in rules or "tabs" in rules):
                issues.append({
                    "line": i,
                    "rule": "tabs",
                    "severity": "error",
                    "message": "使用了制表符(Tab)，应该使用空格",
                    "suggestion": "将Tab替换为4个空格"
                })

        # 4. 检查函数命名规范
        if "all" in rules or "naming" in rules:
            for i, line in enumerate(lines, 1):
                # 检查函数名
                func_match = re.search(r'def\s+([a-zA-Z_][a-zA-Z0-9_]*)', line)
                if func_match:
                    func_name = func_match.group(1)
                    if not re.match(r'^[a-z_][a-z0-9_]*$', func_name):
                        issues.append({
                            "line": i,
                            "rule": "function_naming",
                            "severity": "warning",
                            "message": f"函数名 '{func_name}' 不符合snake_case规范",
                            "suggestion": f"建议改为: {to_snake_case(func_name)}"
                        })

        # 5. 检查类命名规范
        if "all" in rules or "naming" in rules:
            for i, line in enumerate(lines, 1):
                # 检查类名
                class_match = re.search(r'class\s+([a-zA-Z_][a-zA-Z0-9_]*)', line)
                if class_match:
                    class_name = class_match.group(1)
                    if not re.match(r'^[A-Z][a-zA-Z0-9]*$', class_name):
                        issues.append({
                            "line": i,
                            "rule": "class_naming",
                            "severity": "warning",
                            "message": f"类名 '{class_name}' 不符合PascalCase规范",
                            "suggestion": f"建议改为: {to_pascal_case(class_name)}"
                        })

        # 统计结果
        error_count = sum(1 for issue in issues if issue["severity"] == "error")
        warning_count = sum(1 for issue in issues if issue["severity"] == "warning")

        # 生成报告
        report_lines = [
            f"## 代码风格检查报告",
            f"**文件**: {file_path}",
            f"**总问题数**: {len(issues)} (错误: {error_count}, 警告: {warning_count})",
            "",
        ]

        if issues:
            report_lines.append("### 发现的问题")
            for issue in issues[:10]:  # 只显示前10个问题
                emoji = "🚨" if issue["severity"] == "error" else "⚠️"
                report_lines.append(
                    f"{emoji} **第{issue['line']}行**: {issue['message']}\n"
                    f"   💡 建议: {issue['suggestion']}\n"
                )
        else:
            report_lines.append("✅ 恭喜！未发现明显的风格问题。")

        result = {
            "content": [{
                "type": "text",
                "text": "\n".join(report_lines)
            }],
            "summary": {
                "total_issues": len(issues),
                "errors": error_count,
                "warnings": warning_count,
                "file_path": file_path
            },
            "issues": issues
        }

        return result

    except FileNotFoundError:
        return {
            "content": [{
                "type": "text",
                "text": f"❌ 错误: 找不到文件 {file_path}"
            }],
            "error": "file_not_found"
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"❌ 检查过程中发生错误: {str(e)}"
            }],
            "error": str(e)
        }

def to_snake_case(name: str) -> str:
    """将驼峰式命名转换为下划线式"""
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

def to_pascal_case(name: str) -> str:
    """将下划线式命名转换为驼峰式"""
    return ''.join(word.capitalize() for word in name.split('_'))