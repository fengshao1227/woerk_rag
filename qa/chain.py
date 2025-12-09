"""
LangChain 问答链
"""
from typing import List, Dict, Generator

from retriever.hybrid_search import HybridSearch
from utils.llm import get_llm_client
from utils.logger import logger

# 上下文限制配置
MAX_CONTEXT_CHARS = 8000  # 最大上下文字符数（约 4000 tokens）
MAX_SINGLE_CONTENT_CHARS = 2000  # 单条内容最大字符数


class QAChatChain:
    """问答对话链"""

    def __init__(self):
        self.llm = get_llm_client()
        self.retriever = HybridSearch()
        self.conversation_history = []

    def _truncate_content(self, content: str, max_chars: int = MAX_SINGLE_CONTENT_CHARS) -> str:
        """截断过长的内容"""
        if len(content) <= max_chars:
            return content
        # 保留前后部分，中间用省略号
        half = max_chars // 2 - 20
        return content[:half] + "\n\n... [内容已截断] ...\n\n" + content[-half:]

    def _format_context(self, results: List[Dict]) -> str:
        """格式化检索结果作为上下文（带长度限制）"""
        context_parts = []
        current_chars = 0

        for i, result in enumerate(results, 1):
            file_path = result.get("file_path", "未知")
            content = result.get("content", "")
            score = result.get("rerank_score", result.get("score", 0.0))

            # 截断单条内容
            content = self._truncate_content(content)

            # 构建当前条目
            entry = (
                f"[参考 {i}] 文件: {file_path}\n"
                f"相似度: {score:.3f}\n"
                f"内容:\n{content}\n"
            )

            # 检查是否超出总长度限制
            if current_chars + len(entry) > MAX_CONTEXT_CHARS:
                logger.info(f"上下文已达上限，已使用 {i-1}/{len(results)} 条结果")
                break

            context_parts.append(entry)
            current_chars += len(entry)

        return "\n".join(context_parts)

    def _build_prompt(self, question: str, context: str) -> str:
        """构建提示词"""
        prompt_template = """你是一个专业的代码和文档助手，基于提供的上下文回答问题。

## 规则
1. 只基于提供的上下文回答问题，不要编造信息
2. 如果上下文中没有相关信息，明确说明"根据提供的上下文，我无法找到相关信息"
3. 回答要准确、简洁、有条理
4. 如果是代码相关问题，提供具体的文件路径和代码片段
5. 如果是文档相关问题，引用具体的文档位置

## 上下文
{context}

## 问题
{question}

## 回答
"""
        return prompt_template.format(context=context, question=question)

    def query(
        self,
        question: str,
        top_k: int = 5,
        filters: Dict = None,
        use_history: bool = True,
        use_reranker: bool = None
    ) -> Dict:
        """
        执行问答

        Args:
            question: 问题
            top_k: 检索结果数量
            filters: 过滤条件
            use_history: 是否使用对话历史
            use_reranker: 是否使用 Reranker（None 时使用配置默认值）

        Returns:
            包含答案和检索结果的字典
        """
        # 检索相关文档
        logger.info(f"检索问题: {question}")
        results = self.retriever.search(
            question,
            top_k=top_k,
            filters=filters,
            use_reranker=use_reranker
        )

        if not results:
            return {
                "answer": "抱歉，我没有找到相关的信息。",
                "sources": [],
                "retrieved_count": 0
            }

        # 格式化上下文
        context = self._format_context(results)

        # 构建提示词
        prompt = self._build_prompt(question, context)

        # 调用 LLM
        try:
            messages = []

            # 添加历史对话（如果启用）
            if use_history and self.conversation_history:
                for msg in self.conversation_history[-6:]:  # 只保留最近6轮
                    messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })

            # 添加当前问题
            messages.append({"role": "user", "content": prompt})

            # 生成回答
            answer = self.llm.invoke(messages)

            # 保存对话历史
            if use_history:
                self.conversation_history.append({"role": "user", "content": question})
                self.conversation_history.append({"role": "assistant", "content": answer})

            return {
                "answer": answer,
                "sources": [
                    {
                        "file_path": r.get("file_path", ""),
                        "score": r.get("rerank_score", r.get("score", 0.0)),
                        "preview": r.get("content", "")[:200] + "..."
                    }
                    for r in results
                ],
                "retrieved_count": len(results)
            }

        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            return {
                "answer": f"生成回答时出错: {str(e)}",
                "sources": [],
                "retrieved_count": 0
            }

    def clear_history(self):
        """清空对话历史"""
        self.conversation_history = []

    def query_stream(
        self,
        question: str,
        top_k: int = 5,
        filters: Dict = None,
        use_history: bool = True,
        use_reranker: bool = None
    ) -> Generator[Dict, None, None]:
        """
        流式执行问答

        Args:
            question: 问题
            top_k: 检索结果数量
            filters: 过滤条件
            use_history: 是否使用对话历史
            use_reranker: 是否使用 Reranker

        Yields:
            包含 type 和 data 的字典:
            - {"type": "sources", "data": [...]}  检索结果
            - {"type": "chunk", "data": "..."}    答案片段
            - {"type": "done", "data": "..."}     完整答案
        """
        # 检索相关文档
        logger.info(f"流式检索问题: {question}")
        results = self.retriever.search(
            question,
            top_k=top_k,
            filters=filters,
            use_reranker=use_reranker
        )

        if not results:
            yield {"type": "sources", "data": []}
            yield {"type": "chunk", "data": "抱歉，我没有找到相关的信息。"}
            yield {"type": "done", "data": "抱歉，我没有找到相关的信息。"}
            return

        # 先返回检索结果
        sources = [
            {
                "file_path": r.get("file_path", ""),
                "score": r.get("rerank_score", r.get("score", 0.0)),
                "preview": r.get("content", "")[:200] + "..."
            }
            for r in results
        ]
        yield {"type": "sources", "data": sources}

        # 格式化上下文
        context = self._format_context(results)

        # 构建提示词
        prompt = self._build_prompt(question, context)

        # 流式调用 LLM
        try:
            messages = []

            # 添加历史对话
            if use_history and self.conversation_history:
                for msg in self.conversation_history[-6:]:
                    messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })

            messages.append({"role": "user", "content": prompt})

            # 流式生成回答
            full_answer = ""
            for chunk in self.llm.invoke_stream(messages):
                full_answer += chunk
                yield {"type": "chunk", "data": chunk}

            # 保存对话历史
            if use_history:
                self.conversation_history.append({"role": "user", "content": question})
                self.conversation_history.append({"role": "assistant", "content": full_answer})

            yield {"type": "done", "data": full_answer}

        except Exception as e:
            logger.error(f"LLM 流式调用失败: {e}")
            error_msg = f"生成回答时出错: {str(e)}"
            yield {"type": "chunk", "data": error_msg}
            yield {"type": "done", "data": error_msg}
