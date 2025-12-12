"""
LangChain 问答链
"""
from typing import List, Dict, Generator, Optional

from retriever.hybrid_search import HybridSearch
from retriever.semantic_cache import SemanticCache
from utils.llm import get_llm_client
from utils.logger import logger
from .conversation_summarizer import ConversationSummarizer

# 上下文限制配置
MAX_CONTEXT_CHARS = 8000  # 最大上下文字符数（约 4000 tokens）
MAX_SINGLE_CONTENT_CHARS = 2000  # 单条内容最大字符数


class QAChatChain:
    """问答对话链"""

    def __init__(self, enable_cache: bool = True, enable_summarization: bool = True):
        self.llm = get_llm_client()
        self.retriever = HybridSearch()
        self.conversation_history = []

        # 对话摘要相关
        self.enable_summarization = enable_summarization
        self.conversation_summary: Optional[str] = None  # 早期对话摘要
        self.summarizer = None
        if enable_summarization:
            try:
                self.summarizer = ConversationSummarizer(self.llm)
                logger.info("对话摘要压缩已启用")
            except Exception as e:
                logger.warning(f"对话摘要初始化失败: {e}")
                self.enable_summarization = False

        # 初始化语义缓存
        self.enable_cache = enable_cache
        self.semantic_cache = None
        if enable_cache:
            try:
                self.semantic_cache = SemanticCache()
                logger.info("语义缓存已启用")
            except Exception as e:
                logger.warning(f"语义缓存初始化失败，将禁用缓存: {e}")
                self.enable_cache = False

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

    def _maybe_compress_history(self) -> None:
        """检查并在必要时压缩对话历史"""
        if not self.enable_summarization or not self.summarizer:
            return

        if self.summarizer.should_summarize(self.conversation_history):
            result = self.summarizer.compress_history(
                self.conversation_history,
                self.conversation_summary
            )
            if result["compressed"]:
                self.conversation_summary = result["summary"]
                self.conversation_history = result["recent_messages"]
                logger.info(f"对话历史已压缩，摘要长度: {len(self.conversation_summary)} 字符")

    def _build_messages_with_history(self, prompt: str, use_history: bool) -> List[Dict]:
        """
        构建包含历史对话的消息列表

        Args:
            prompt: 当前的提示词（包含上下文和问题）
            use_history: 是否使用对话历史

        Returns:
            消息列表
        """
        messages = []

        if use_history and self.conversation_history:
            # 检查是否需要压缩
            self._maybe_compress_history()

            # 如果有摘要，添加到消息中
            if self.enable_summarization and self.conversation_summary:
                messages = self.summarizer.build_messages_with_summary(
                    self.conversation_summary,
                    self.conversation_history,
                    prompt
                )
            else:
                # 没有摘要时，使用最近的对话历史
                for msg in self.conversation_history[-6:]:  # 保留最近 6 轮
                    messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })
                messages.append({"role": "user", "content": prompt})
        else:
            messages.append({"role": "user", "content": prompt})

        return messages

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
        group_ids: List[int] = None,
        user_id: int = None,  # 新增：用户ID，用于多用户知识隔离
        use_history: bool = True,
        use_reranker: bool = None,
        use_cache: bool = True
    ) -> Dict:
        """
        执行问答

        Args:
            question: 问题
            top_k: 检索结果数量
            filters: 过滤条件
            group_ids: 知识分组ID列表，只在指定分组中检索
            user_id: 当前用户ID，用于多用户知识隔离（只检索用户私有+公开知识）
            use_history: 是否使用对话历史
            use_reranker: 是否使用 Reranker（None 时使用配置默认值）
            use_cache: 是否使用语义缓存

        Returns:
            包含答案和检索结果的字典
        """
        # 1. 检查语义缓存（支持分组过滤和用户过滤）
        cache_key = question
        if group_ids:
            # 将分组信息加入缓存键，确保不同分组的查询不会混淆
            cache_key = f"{question}||groups:{','.join(str(g) for g in sorted(group_ids))}"
        if user_id:
            # 将用户ID加入缓存键，确保不同用户的查询不会混淆
            cache_key = f"{cache_key}||user:{user_id}"

        if use_cache and self.semantic_cache:
            cached = self.semantic_cache.get(cache_key)
            if cached:
                logger.info(f"语义缓存命中: {question[:50]}..." + (f" [分组: {group_ids}]" if group_ids else "") + (f" [用户: {user_id}]" if user_id else ""))
                return {
                    "answer": cached["answer"],
                    "sources": cached.get("sources", []),
                    "retrieved_count": cached.get("retrieved_count", 0),
                    "from_cache": True,
                    "cache_similarity": cached.get("similarity", 0.0)
                }

        # 2. 检索相关文档（传入 user_id 进行权限过滤）
        logger.info(f"检索问题: {question}" + (f"，分组过滤: {group_ids}" if group_ids else "") + (f"，用户过滤: {user_id}" if user_id else ""))
        results = self.retriever.search(
            question,
            top_k=top_k,
            filters=filters,
            group_ids=group_ids,
            user_id=user_id,  # 传入用户ID
            use_reranker=use_reranker
        )

        if not results:
            return {
                "answer": "抱歉，我没有找到相关的信息。",
                "sources": [],
                "retrieved_count": 0,
                "from_cache": False
            }

        # 格式化上下文
        context = self._format_context(results)

        # 构建提示词
        prompt = self._build_prompt(question, context)

        # 调用 LLM
        try:
            # 构建消息列表（包含对话摘要处理）
            messages = self._build_messages_with_history(prompt, use_history)


            # 生成回答
            llm_response = self.llm.invoke(messages)
            answer = llm_response.content

            # 保存对话历史
            if use_history:
                self.conversation_history.append({"role": "user", "content": question})
                self.conversation_history.append({"role": "assistant", "content": answer})

            # 构建响应
            sources = [
                {
                    "file_path": r.get("file_path", ""),
                    "score": r.get("rerank_score", r.get("score", 0.0)),
                    "preview": r.get("content", "")[:200] + "...",
                    "content": r.get("content", "")  # 保留完整内容用于高亮匹配
                }
                for r in results
            ]

            # 引用高亮
            highlights = None
            try:
                from utils.reference_highlighter import find_reference_highlights
                highlight_result = find_reference_highlights(answer, sources)
                highlights = {
                    "matches": highlight_result["matches"],
                    "highlighted_answer": highlight_result["highlighted_answer"],
                    "source_citations": highlight_result["source_citations"]
                }
            except Exception as e:
                logger.warning(f"引用高亮处理失败: {e}")

            response = {
                "answer": answer,
                "sources": sources,
                "retrieved_count": len(results),
                "from_cache": False,
                "highlights": highlights,
                "usage": {
                    "input_tokens": llm_response.input_tokens,
                    "output_tokens": llm_response.output_tokens,
                    "total_tokens": llm_response.total_tokens
                }
            }

            # 3. 存入语义缓存（使用相同的缓存键）
            if use_cache and self.semantic_cache:
                self.semantic_cache.set(cache_key, response)

            return response

        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            return {
                "answer": f"生成回答时出错: {str(e)}",
                "sources": [],
                "retrieved_count": 0,
                "from_cache": False
            }

    def clear_history(self):
        """清空对话历史和摘要"""
        self.conversation_history = []
        self.conversation_summary = None
        logger.info("对话历史和摘要已清空")

    def get_conversation_stats(self) -> Dict:
        """
        获取对话状态统计

        Returns:
            包含对话历史统计信息的字典
        """
        history_turns = len(self.conversation_history) // 2
        history_chars = sum(len(msg["content"]) for msg in self.conversation_history)
        summary_chars = len(self.conversation_summary) if self.conversation_summary else 0

        return {
            "history_turns": history_turns,
            "history_messages": len(self.conversation_history),
            "history_chars": history_chars,
            "has_summary": self.conversation_summary is not None,
            "summary_chars": summary_chars,
            "summarization_enabled": self.enable_summarization,
            "cache_enabled": self.enable_cache
        }

    def query_stream(
        self,
        question: str,
        top_k: int = 5,
        filters: Dict = None,
        group_ids: List[int] = None,
        use_history: bool = True,
        use_reranker: bool = None
    ) -> Generator[Dict, None, None]:
        """
        流式执行问答

        Args:
            question: 问题
            top_k: 检索结果数量
            filters: 过滤条件
            group_ids: 知识分组ID列表，只在指定分组中检索
            use_history: 是否使用对话历史
            use_reranker: 是否使用 Reranker

        Yields:
            包含 type 和 data 的字典:
            - {"type": "sources", "data": [...]}  检索结果
            - {"type": "chunk", "data": "..."}    答案片段
            - {"type": "done", "data": "..."}     完整答案
        """
        # 检查语义缓存（支持分组过滤）
        cache_key = question
        if group_ids:
            cache_key = f"{question}||groups:{','.join(str(g) for g in sorted(group_ids))}"

        if self.semantic_cache:
            cached = self.semantic_cache.get(cache_key)
            if cached:
                logger.info(f"语义缓存命中: {question[:50]}..." + (f" [分组: {group_ids}]" if group_ids else ""))
                yield {"type": "sources", "data": cached.get("sources", [])}
                # 模拟流式输出缓存的答案
                answer = cached["answer"]
                for i in range(0, len(answer), 20):
                    yield {"type": "chunk", "data": answer[i:i+20]}
                yield {"type": "done", "data": answer}
                return

        # 检索相关文档
        logger.info(f"流式检索问题: {question}" + (f"，分组过滤: {group_ids}" if group_ids else ""))
        results = self.retriever.search(
            question,
            top_k=top_k,
            filters=filters,
            group_ids=group_ids,
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
            # 构建消息列表（包含对话摘要处理）
            messages = self._build_messages_with_history(prompt, use_history)

            # 流式生成回答
            full_answer = ""
            for chunk in self.llm.invoke_stream(messages):
                full_answer += chunk
                yield {"type": "chunk", "data": chunk}

            # 保存对话历史
            if use_history:
                self.conversation_history.append({"role": "user", "content": question})
                self.conversation_history.append({"role": "assistant", "content": full_answer})

            # 存入语义缓存（使用相同的缓存键）
            if self.semantic_cache and full_answer:
                try:
                    self.semantic_cache.set(cache_key, full_answer, sources)
                except Exception as cache_err:
                    logger.warning(f"语义缓存存储失败: {cache_err}")

            yield {"type": "done", "data": full_answer}

        except Exception as e:
            logger.error(f"LLM 流式调用失败: {e}")
            error_msg = f"生成回答时出错: {str(e)}"
            yield {"type": "chunk", "data": error_msg}
            yield {"type": "done", "data": error_msg}
