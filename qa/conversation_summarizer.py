"""
对话历史摘要压缩模块

当对话历史过长时，自动生成摘要压缩早期对话，
保留最近几轮完整对话 + 早期对话摘要。
"""

from typing import List, Dict, Optional
from utils.llm import get_llm_client
from utils.logger import logger
from config import (
    CONVERSATION_MAX_HISTORY_TURNS,
    CONVERSATION_KEEP_RECENT_TURNS,
    CONVERSATION_MAX_SUMMARY_CHARS
)


# 从配置文件读取
MAX_HISTORY_TURNS = CONVERSATION_MAX_HISTORY_TURNS
KEEP_RECENT_TURNS = CONVERSATION_KEEP_RECENT_TURNS
MAX_SUMMARY_CHARS = CONVERSATION_MAX_SUMMARY_CHARS


SUMMARIZE_PROMPT = """将以下对话历史压缩为结构化摘要，便于后续对话参考。

## 摘要要求
1. **核心信息**：提取讨论主题、关键结论、重要决策
2. **上下文保留**：保留对后续对话有帮助的背景信息
3. **第三人称**：使用"用户询问了..."、"助手解释了..."等描述
4. **精炼表达**：控制在 200-400 字，去除寒暄和重复内容
5. **时序清晰**：按讨论顺序组织，重要话题可分点列出

## 对话历史
{conversation}

## 结构化摘要
"""


class ConversationSummarizer:
    """对话历史摘要压缩器"""

    def __init__(self, llm_client=None):
        """
        初始化摘要器

        Args:
            llm_client: LLM 客户端实例，若不提供则自动创建
        """
        self.llm = llm_client or get_llm_client()
        self._summary_cache = {}  # 缓存已生成的摘要

    def should_summarize(self, history: List[Dict]) -> bool:
        """
        判断是否需要进行摘要压缩

        Args:
            history: 对话历史列表

        Returns:
            是否需要摘要
        """
        # 计算轮数（每两条消息为一轮）
        turns = len(history) // 2
        return turns > MAX_HISTORY_TURNS

    def _format_conversation(self, messages: List[Dict]) -> str:
        """格式化对话为文本"""
        lines = []
        for msg in messages:
            role = "用户" if msg["role"] == "user" else "助手"
            content = msg["content"]
            # 截断过长的单条消息
            if len(content) > 500:
                content = content[:250] + "...[已截断]..." + content[-250:]
            lines.append(f"{role}: {content}")
        return "\n\n".join(lines)

    def _generate_summary(self, messages: List[Dict]) -> str:
        """
        调用 LLM 生成对话摘要

        Args:
            messages: 需要摘要的消息列表

        Returns:
            摘要文本
        """
        conversation_text = self._format_conversation(messages)
        prompt = SUMMARIZE_PROMPT.format(conversation=conversation_text)

        try:
            summary = self.llm.invoke([{"role": "user", "content": prompt}])
            # 截断过长的摘要
            if len(summary) > MAX_SUMMARY_CHARS:
                summary = summary[:MAX_SUMMARY_CHARS] + "..."
            return summary.strip()
        except Exception as e:
            logger.error(f"生成对话摘要失败: {e}")
            # 降级：返回简单的截断摘要
            return self._fallback_summary(messages)

    def _fallback_summary(self, messages: List[Dict]) -> str:
        """降级摘要方案（不调用 LLM）"""
        topics = []
        for msg in messages:
            if msg["role"] == "user":
                # 提取用户问题的前 50 字符
                content = msg["content"][:50]
                if len(msg["content"]) > 50:
                    content += "..."
                topics.append(f"- {content}")

        if topics:
            return f"早期对话涉及以下主题:\n" + "\n".join(topics[:5])
        return "（早期对话已压缩）"

    def compress_history(
        self,
        history: List[Dict],
        existing_summary: Optional[str] = None
    ) -> Dict:
        """
        压缩对话历史

        Args:
            history: 完整的对话历史列表
            existing_summary: 已有的早期摘要（增量摘要时使用）

        Returns:
            {
                "summary": str,           # 早期对话摘要
                "recent_messages": List,  # 保留的最近消息
                "compressed": bool        # 是否进行了压缩
            }
        """
        if not self.should_summarize(history):
            return {
                "summary": existing_summary,
                "recent_messages": history,
                "compressed": False
            }

        # 分割：早期消息 + 最近消息
        recent_count = KEEP_RECENT_TURNS * 2  # 每轮 2 条消息
        early_messages = history[:-recent_count]
        recent_messages = history[-recent_count:]

        # 生成早期对话摘要
        if existing_summary:
            # 增量摘要：将已有摘要作为上下文
            combined_context = [
                {"role": "system", "content": f"之前的对话摘要: {existing_summary}"}
            ] + early_messages
            summary = self._generate_summary(combined_context)
        else:
            summary = self._generate_summary(early_messages)

        logger.info(f"对话历史已压缩: {len(history)} 条 -> 摘要 + {len(recent_messages)} 条")

        return {
            "summary": summary,
            "recent_messages": recent_messages,
            "compressed": True
        }

    def build_messages_with_summary(
        self,
        summary: Optional[str],
        recent_messages: List[Dict],
        current_prompt: str
    ) -> List[Dict]:
        """
        构建包含摘要的消息列表

        Args:
            summary: 早期对话摘要
            recent_messages: 最近的对话消息
            current_prompt: 当前的用户提示

        Returns:
            用于 LLM 调用的消息列表
        """
        messages = []

        # 添加摘要作为系统上下文
        if summary:
            messages.append({
                "role": "system",
                "content": f"以下是之前对话的摘要，请在回答时考虑这些上下文：\n\n{summary}"
            })

        # 添加最近的对话
        for msg in recent_messages:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })

        # 添加当前问题
        messages.append({"role": "user", "content": current_prompt})

        return messages


def get_conversation_summarizer(llm_client=None) -> ConversationSummarizer:
    """工厂函数：获取对话摘要器实例"""
    return ConversationSummarizer(llm_client)
