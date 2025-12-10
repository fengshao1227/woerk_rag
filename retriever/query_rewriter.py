"""
Query 改写器：生成多个查询变体以提高检索召回率
支持 Multi-Query 和 HyDE 两种策略
"""
from typing import List, Optional
import json
import re

from utils.llm import get_llm_client, BaseLLM
from utils.logger import logger


class QueryRewriter:
    """Query 改写基类"""

    def rewrite(self, query: str) -> List[str]:
        """
        改写查询，返回查询变体列表

        Args:
            query: 原始查询

        Returns:
            包含原始查询和变体的列表
        """
        raise NotImplementedError


class MultiQueryRewriter(QueryRewriter):
    """
    Multi-Query 改写器

    生成多个查询变体，从不同角度描述同一问题，
    扩大检索召回范围。
    """

    def __init__(self, llm: Optional[BaseLLM] = None, num_variants: int = 3):
        """
        初始化 Multi-Query 改写器

        Args:
            llm: LLM 客户端，为 None 时自动获取
            num_variants: 生成的变体数量
        """
        self.llm = llm
        self.num_variants = num_variants
        self._llm_initialized = False

    def _get_llm(self) -> BaseLLM:
        """懒加载 LLM"""
        if self.llm is None and not self._llm_initialized:
            try:
                self.llm = get_llm_client()
                self._llm_initialized = True
            except Exception as e:
                logger.warning(f"无法初始化 LLM: {e}，将使用原始查询")
                self._llm_initialized = True
        return self.llm

    def rewrite(self, query: str) -> List[str]:
        """
        生成多个查询变体

        Args:
            query: 原始查询

        Returns:
            包含原始查询和变体的列表
        """
        llm = self._get_llm()
        if llm is None:
            return [query]

        prompt = f"""你是一个搜索查询优化专家。请为以下用户问题生成 {self.num_variants} 个不同角度的查询变体，
用于在知识库中检索相关信息。

原始问题：{query}

要求：
1. 每个变体应从不同角度描述同一问题
2. 变体应保持与原问题相同的语义意图
3. 可以使用同义词、换种表达方式、或聚焦问题的不同方面
4. 变体应简洁明了，适合用于搜索

请直接返回 JSON 数组格式，不要其他内容：
["变体1", "变体2", "变体3"]"""

        try:
            messages = [{"role": "user", "content": prompt}]
            llm_response = llm.invoke(messages)
            response_text = llm_response.content

            # 提取 JSON 数组
            json_match = re.search(r'\[[\s\S]*?\]', response_text)
            if json_match:
                variants = json.loads(json_match.group())
                if isinstance(variants, list) and len(variants) > 0:
                    logger.info(f"Query 改写成功: {query} -> {variants}")
                    return [query] + variants[:self.num_variants]

            logger.warning(f"无法解析 LLM 响应: {response_text}")
            return [query]

        except Exception as e:
            logger.error(f"Query 改写失败: {e}")
            return [query]


class HyDERewriter(QueryRewriter):
    """
    HyDE (Hypothetical Document Embeddings) 改写器

    生成假设性答案文档，用其向量进行检索。
    适用于问答场景，可以提高语义匹配度。
    """

    def __init__(self, llm: Optional[BaseLLM] = None):
        """
        初始化 HyDE 改写器

        Args:
            llm: LLM 客户端，为 None 时自动获取
        """
        self.llm = llm
        self._llm_initialized = False

    def _get_llm(self) -> BaseLLM:
        """懒加载 LLM"""
        if self.llm is None and not self._llm_initialized:
            try:
                self.llm = get_llm_client()
                self._llm_initialized = True
            except Exception as e:
                logger.warning(f"无法初始化 LLM: {e}")
                self._llm_initialized = True
        return self.llm

    def rewrite(self, query: str) -> List[str]:
        """
        生成假设性答案文档

        Args:
            query: 原始查询

        Returns:
            包含原始查询和假设性答案的列表
        """
        llm = self._get_llm()
        if llm is None:
            return [query]

        prompt = f"""请为以下问题写一段可能的答案（假设你知道答案）。
这段答案将用于在知识库中检索相关文档。

问题：{query}

请直接写出答案，不要有任何前缀或解释："""

        try:
            messages = [{"role": "user", "content": prompt}]
            llm_response = llm.invoke(messages)
            hypothetical_answer = llm_response.content

            if hypothetical_answer and len(hypothetical_answer.strip()) > 10:
                logger.info(f"HyDE 改写成功: {query[:50]}...")
                return [query, hypothetical_answer.strip()]

            return [query]

        except Exception as e:
            logger.error(f"HyDE 改写失败: {e}")
            return [query]


def get_query_rewriter(strategy: str = "multi_query", **kwargs) -> QueryRewriter:
    """
    获取 Query 改写器

    Args:
        strategy: 改写策略，可选 "multi_query" 或 "hyde"
        **kwargs: 传递给改写器的参数

    Returns:
        QueryRewriter 实例
    """
    if strategy == "hyde":
        return HyDERewriter(**kwargs)
    else:
        return MultiQueryRewriter(**kwargs)
