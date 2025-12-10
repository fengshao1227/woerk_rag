"""
引用高亮工具 - 在回答中高亮显示引用的源内容
"""
import re
from typing import List, Dict, Tuple, Optional
from difflib import SequenceMatcher
from utils.logger import logger


class ReferenceHighlighter:
    """引用高亮处理器"""

    def __init__(self, min_match_length: int = 20, similarity_threshold: float = 0.6):
        """
        初始化高亮器

        Args:
            min_match_length: 最小匹配长度（字符）
            similarity_threshold: 相似度阈值
        """
        self.min_match_length = min_match_length
        self.similarity_threshold = similarity_threshold

    def find_matching_snippets(
        self,
        answer: str,
        sources: List[Dict],
        context_chars: int = 50
    ) -> List[Dict]:
        """
        在回答中查找与源内容匹配的片段

        Args:
            answer: AI 生成的回答
            sources: 检索到的源文档列表
            context_chars: 匹配片段周围的上下文字符数

        Returns:
            匹配结果列表，每个包含：
            - source_index: 源文档索引
            - source_file: 源文件路径
            - matched_text: 匹配的文本
            - answer_start: 在回答中的起始位置
            - answer_end: 在回答中的结束位置
            - source_snippet: 源文档中的相关片段（带上下文）
            - similarity: 相似度分数
        """
        matches = []

        for idx, source in enumerate(sources):
            content = source.get("content", "")
            if not content:
                continue

            source_matches = self._find_source_matches(
                answer, content, idx, source, context_chars
            )
            matches.extend(source_matches)

        # 按在回答中的位置排序
        matches.sort(key=lambda x: x["answer_start"])

        # 去除重叠的匹配
        matches = self._remove_overlapping_matches(matches)

        return matches

    def _find_source_matches(
        self,
        answer: str,
        source_content: str,
        source_index: int,
        source: Dict,
        context_chars: int
    ) -> List[Dict]:
        """在回答和单个源之间查找匹配"""
        matches = []

        # 方法1: 查找直接引用（相同的短语）
        # 将内容分割成句子或段落
        sentences = self._split_into_sentences(source_content)

        for sentence in sentences:
            if len(sentence) < self.min_match_length:
                continue

            # 在回答中查找这个句子
            pos = answer.find(sentence)
            if pos != -1:
                matches.append({
                    "source_index": source_index,
                    "source_file": source.get("file_path", "未知"),
                    "matched_text": sentence,
                    "answer_start": pos,
                    "answer_end": pos + len(sentence),
                    "source_snippet": self._get_snippet_with_context(
                        source_content, source_content.find(sentence), len(sentence), context_chars
                    ),
                    "similarity": 1.0,
                    "match_type": "exact"
                })

        # 方法2: 查找近似匹配（相似的短语）
        answer_sentences = self._split_into_sentences(answer)
        for ans_sent in answer_sentences:
            if len(ans_sent) < self.min_match_length:
                continue

            for src_sent in sentences:
                if len(src_sent) < self.min_match_length:
                    continue

                similarity = self._calculate_similarity(ans_sent, src_sent)
                if similarity >= self.similarity_threshold:
                    pos = answer.find(ans_sent)
                    if pos != -1 and not self._is_already_matched(matches, pos, pos + len(ans_sent)):
                        matches.append({
                            "source_index": source_index,
                            "source_file": source.get("file_path", "未知"),
                            "matched_text": ans_sent,
                            "answer_start": pos,
                            "answer_end": pos + len(ans_sent),
                            "source_snippet": src_sent,
                            "similarity": similarity,
                            "match_type": "similar"
                        })

        return matches

    def _split_into_sentences(self, text: str) -> List[str]:
        """将文本分割成句子"""
        # 按句子结束符分割
        sentences = re.split(r'[。！？\n.!?]', text)
        # 过滤空句子并去除首尾空白
        return [s.strip() for s in sentences if s.strip()]

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """计算两段文本的相似度"""
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()

    def _get_snippet_with_context(
        self,
        full_text: str,
        start: int,
        length: int,
        context_chars: int
    ) -> str:
        """获取带上下文的片段"""
        if start == -1:
            return ""

        # 扩展到上下文
        snippet_start = max(0, start - context_chars)
        snippet_end = min(len(full_text), start + length + context_chars)

        snippet = full_text[snippet_start:snippet_end]

        # 添加省略号
        if snippet_start > 0:
            snippet = "..." + snippet
        if snippet_end < len(full_text):
            snippet = snippet + "..."

        return snippet

    def _is_already_matched(self, matches: List[Dict], start: int, end: int) -> bool:
        """检查这个位置是否已经有匹配"""
        for m in matches:
            if not (end <= m["answer_start"] or start >= m["answer_end"]):
                return True
        return False

    def _remove_overlapping_matches(self, matches: List[Dict]) -> List[Dict]:
        """移除重叠的匹配，保留相似度更高的"""
        if not matches:
            return []

        result = []
        for match in matches:
            is_overlapping = False
            for i, existing in enumerate(result):
                # 检查是否重叠
                if not (match["answer_end"] <= existing["answer_start"] or
                        match["answer_start"] >= existing["answer_end"]):
                    is_overlapping = True
                    # 保留相似度更高的
                    if match["similarity"] > existing["similarity"]:
                        result[i] = match
                    break

            if not is_overlapping:
                result.append(match)

        return result

    def highlight_answer(
        self,
        answer: str,
        matches: List[Dict],
        highlight_format: str = "markdown"
    ) -> str:
        """
        在回答中添加高亮标记

        Args:
            answer: 原始回答
            matches: 匹配结果列表
            highlight_format: 高亮格式 ("markdown", "html", "plain")

        Returns:
            带高亮标记的回答
        """
        if not matches:
            return answer

        # 按位置倒序排列，从后向前替换避免位置偏移
        matches_sorted = sorted(matches, key=lambda x: x["answer_start"], reverse=True)

        result = answer
        for match in matches_sorted:
            start = match["answer_start"]
            end = match["answer_end"]
            text = result[start:end]
            source_idx = match["source_index"] + 1  # 1-based index

            if highlight_format == "markdown":
                highlighted = f"**{text}**[^{source_idx}]"
            elif highlight_format == "html":
                highlighted = f'<mark data-source="{source_idx}">{text}</mark>'
            else:  # plain
                highlighted = f"{text}[{source_idx}]"

            result = result[:start] + highlighted + result[end:]

        return result


def find_reference_highlights(
    answer: str,
    sources: List[Dict],
    min_match_length: int = 20,
    similarity_threshold: float = 0.6
) -> Dict:
    """
    便捷函数：查找回答中的引用高亮

    Args:
        answer: AI 回答
        sources: 源文档列表
        min_match_length: 最小匹配长度
        similarity_threshold: 相似度阈值

    Returns:
        包含高亮信息的字典：
        - matches: 匹配列表
        - highlighted_answer: 带高亮标记的回答
        - source_citations: 每个源的引用次数
    """
    highlighter = ReferenceHighlighter(min_match_length, similarity_threshold)
    matches = highlighter.find_matching_snippets(answer, sources)
    highlighted_answer = highlighter.highlight_answer(answer, matches)

    # 统计每个源的引用次数
    source_citations = {}
    for match in matches:
        idx = match["source_index"]
        source_citations[idx] = source_citations.get(idx, 0) + 1

    return {
        "matches": matches,
        "highlighted_answer": highlighted_answer,
        "source_citations": source_citations
    }
