"""
文本处理器 - 演示文本处理和分析功能
"""

from claude_agent_sdk import tool
from typing import Dict, Any, List
import re
from collections import Counter

@tool(
    name="count_words",
    description="统计文本的单词数、行数、字符数等信息",
    input_schema={
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "要分析的文本内容"
            },
            "file_path": {
                "type": "string",
                "description": "文件路径（可选，如果提供则从文件读取文本）"
            }
        }
    }
)
async def count_words(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    统计文本的基本信息

    Args:
        args: 包含 text 或 file_path 的字典

    Returns:
        文本统计结果
    """
    text = args.get("text", "")
    file_path = args.get("file_path")

    # 如果提供了文件路径，从文件读取
    if file_path and not text:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
        except Exception as e:
            return {
                "content": [{
                    "type": "text",
                    "text": f"读取文件失败: {str(e)}"
                }],
                "error": str(e)
            }

    if not text:
        return {
            "content": [{
                "type": "text",
                "text": "错误: 没有提供文本内容"
            }],
            "error": "No text provided"
        }

    # 基础统计
    lines = text.splitlines()
    words = text.split()
    characters = len(text)
    characters_no_spaces = len(text.replace(" ", ""))

    # 更详细的单词统计
    word_count = len(words)
    line_count = len(lines)
    non_empty_lines = len([line for line in lines if line.strip()])

    # 句子统计（简单判断）
    sentences = re.split(r'[.!?]+', text)
    sentence_count = len([s for s in sentences if s.strip()])

    # 段落统计
    paragraphs = re.split(r'\n\n+', text)
    paragraph_count = len([p for p in paragraphs if p.strip()])

    # 平均值计算
    avg_words_per_sentence = word_count / sentence_count if sentence_count > 0 else 0
    avg_chars_per_word = characters_no_spaces / word_count if word_count > 0 else 0

    result_text = f"""📊 文本统计结果

基础信息:
- 字符数: {characters:,}
- 字符数（不含空格）: {characters_no_spaces:,}
- 单词数: {word_count:,}
- 行数: {line_count:,}
- 非空行数: {non_empty_lines:,}
- 句子数: {sentence_count:,}
- 段落数: {paragraph_count:,}

平均值:
- 平均每句单词数: {avg_words_per_sentence:.1f}
- 平均每单词字符数: {avg_chars_per_word:.1f}"""

    return {
        "content": [{
            "type": "text",
            "text": result_text
        }],
        "statistics": {
            "characters": characters,
            "characters_no_spaces": characters_no_spaces,
            "word_count": word_count,
            "line_count": line_count,
            "non_empty_lines": non_empty_lines,
            "sentence_count": sentence_count,
            "paragraph_count": paragraph_count,
            "avg_words_per_sentence": avg_words_per_sentence,
            "avg_chars_per_word": avg_chars_per_word
        }
    }

@tool(
    name="extract_keywords",
    description="从文本中提取关键词和短语",
    input_schema={
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "要分析的文本内容"
            },
            "max_keywords": {
                "type": "integer",
                "description": "最大关键词数量",
                "default": 20
            },
            "min_word_length": {
                "type": "integer",
                "description": "最小单词长度",
                "default": 3
            }
        },
        "required": ["text"]
    }
)
async def extract_keywords(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    提取文本关键词

    Args:
        args: 包含 text 和可选参数的字典

    Returns:
        关键词提取结果
    """
    text = args.get("text", "")
    max_keywords = args.get("max_keywords", 20)
    min_word_length = args.get("min_word_length", 3)

    if not text:
        return {
            "content": [{
                "type": "text",
                "text": "错误: 没有提供文本内容"
            }],
            "error": "No text provided"
        }

    # 转换为小写并提取单词
    words = re.findall(r'\b\w+\b', text.lower())

    # 过滤短词和常见停用词
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'can', 'this', 'that', 'these', 'those',
        'i', 'you', 'he', 'she', 'it', 'we', 'they', 'what', 'which', 'who',
        'when', 'where', 'why', 'how', 'not', 'no', 'yes', 'so', 'if', 'then'
    }

    filtered_words = [
        word for word in words
        if len(word) >= min_word_length and word not in stop_words
    ]

    # 统计词频
    word_freq = Counter(filtered_words)

    # 提取短语（2个词的组合）
    phrases = []
    for i in range(len(words) - 1):
        if (len(words[i]) >= min_word_length and len(words[i+1]) >= min_word_length and
            words[i] not in stop_words and words[i+1] not in stop_words):
            phrases.append(f"{words[i]} {words[i+1]}")

    phrase_freq = Counter(phrases)

    # 获取最常见的关键词和短语
    top_words = word_freq.most_common(max_keywords)
    top_phrases = phrase_freq.most_common(max_keywords // 2)

    # 格式化结果
    result_text = "🔑 关键词提取结果\n\n"

    if top_words:
        result_text += "📝 高频词汇:\n"
        for word, freq in top_words[:15]:
            result_text += f"- {word}: {freq} 次\n"

    if top_phrases:
        result_text += "\n🔗 常见短语:\n"
        for phrase, freq in top_phrases[:10]:
            result_text += f"- '{phrase}': {freq} 次\n"

    # 文本特征
    total_words = len(filtered_words)
    unique_words = len(word_freq)
    diversity = unique_words / total_words if total_words > 0 else 0

    result_text += f"\n📈 文本特征:\n"
    result_text += f"- 总词数（过滤后）: {total_words:,}\n"
    result_text += f"- 唯一词数: {unique_words:,}\n"
    result_text += f"- 词汇多样性: {diversity:.2f} (越高越丰富)\n"

    return {
        "content": [{
            "type": "text",
            "text": result_text
        }],
        "keywords": {
            "top_words": top_words,
            "top_phrases": top_phrases,
            "total_words": total_words,
            "unique_words": unique_words,
            "diversity": diversity
        }
    }