"""
RAG 知识库 MCP Server

使用方法：
    python mcp_server/server.py

Claude Desktop 配置：
    {
        "mcpServers": {
            "rag-knowledge": {
                "command": "python",
                "args": ["/Users/li/Desktop/work7_8/www/rag/mcp_server/server.py"]
            }
        }
    }
"""
import sys
from pathlib import Path
from typing import Optional
import json
import re
import hashlib
from datetime import datetime

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server.fastmcp import FastMCP

# 初始化 MCP Server
mcp = FastMCP("RAG Knowledge Base")

# 全局实例（延迟初始化）
_qa_chain = None
_vector_store = None
_llm_client = None
_embedding_model = None
_qdrant_client = None


def _get_qa_chain():
    """获取 QAChatChain 实例"""
    global _qa_chain
    if _qa_chain is None:
        from qa.chain import QAChatChain
        _qa_chain = QAChatChain()
    return _qa_chain


def _get_vector_store():
    """获取 VectorStore 实例"""
    global _vector_store
    if _vector_store is None:
        from retriever.vector_store import VectorStore
        _vector_store = VectorStore()
    return _vector_store


def _get_llm_client():
    """获取 LLM 客户端"""
    global _llm_client
    if _llm_client is None:
        from utils.llm import get_llm_client
        _llm_client = get_llm_client()
    return _llm_client


def _get_embedding_model():
    """获取嵌入模型"""
    global _embedding_model
    if _embedding_model is None:
        from utils.embeddings import EmbeddingModel
        _embedding_model = EmbeddingModel()
    return _embedding_model


def _get_qdrant_client():
    """获取 Qdrant 客户端"""
    global _qdrant_client
    if _qdrant_client is None:
        from qdrant_client import QdrantClient
        from config import QDRANT_HOST, QDRANT_PORT, QDRANT_API_KEY, QDRANT_USE_HTTPS
        protocol = "https" if QDRANT_USE_HTTPS else "http"
        url = f"{protocol}://{QDRANT_HOST}:{QDRANT_PORT}"
        _qdrant_client = QdrantClient(url=url, api_key=QDRANT_API_KEY if QDRANT_API_KEY else None)
    return _qdrant_client


@mcp.tool()
def query(question: str, top_k: int = 5) -> str:
    """
    RAG 问答：基于知识库回答问题

    Args:
        question: 要询问的问题
        top_k: 检索的相关文档数量，默认5

    Returns:
        包含答案和来源的回复
    """
    qa_chain = _get_qa_chain()

    result = qa_chain.query(
        question=question,
        top_k=top_k,
        use_history=False  # MCP 调用不使用历史
    )

    # 格式化输出
    answer = result.get("answer", "无法生成回答")
    sources = result.get("sources", [])

    output = f"## 回答\n\n{answer}\n\n"

    if sources:
        output += "## 参考来源\n\n"
        for i, src in enumerate(sources, 1):
            file_path = src.get("file_path", "未知")
            score = src.get("score", 0)
            output += f"{i}. `{file_path}` (相似度: {score:.3f})\n"

    return output


@mcp.tool()
def search(query_text: str, top_k: int = 5) -> str:
    """
    向量检索：搜索知识库中的相关内容

    Args:
        query_text: 搜索查询文本
        top_k: 返回结果数量，默认5

    Returns:
        匹配的知识条目列表
    """
    vector_store = _get_vector_store()

    results = vector_store.search(
        query=query_text,
        top_k=top_k
    )

    if not results:
        return "未找到相关内容"

    output = f"## 搜索结果（共 {len(results)} 条）\n\n"

    for i, item in enumerate(results, 1):
        content = item.get("content", "")
        file_path = item.get("file_path", "未知")
        score = item.get("score", 0)
        title = item.get("title", "")

        # 截取内容预览
        preview = content[:300] + "..." if len(content) > 300 else content

        output += f"### {i}. {title or file_path}\n"
        output += f"- **来源**: `{file_path}`\n"
        output += f"- **相似度**: {score:.3f}\n"
        output += f"- **内容预览**:\n```\n{preview}\n```\n\n"

    return output


@mcp.tool()
def add_knowledge(content: str, title: Optional[str] = None, category: str = "general") -> str:
    """
    添加知识：将新知识添加到知识库，AI 会自动提取关键信息

    Args:
        content: 知识内容（项目经历、技术笔记、学习心得等）
        title: 可选的标题，不提供则由 AI 自动生成
        category: 分类，可选值：project（项目）、skill（技能）、experience（经历）、note（笔记）、general（通用）

    Returns:
        添加结果和提取的关键信息
    """
    from qdrant_client.models import PointStruct
    from config import QDRANT_COLLECTION_NAME

    llm_client = _get_llm_client()
    embedding_model = _get_embedding_model()
    qdrant_client = _get_qdrant_client()

    # 1. 用 LLM 提取关键信息
    extract_prompt = f"""请分析以下内容，提取关键信息并返回 JSON 格式：

内容：
{content}

请返回以下格式的 JSON（只返回 JSON，不要其他内容）：
{{
    "title": "简洁的标题（如果用户没提供）",
    "summary": "50字以内的摘要",
    "keywords": ["关键词1", "关键词2", "关键词3"],
    "tech_stack": ["涉及的技术栈"],
    "type": "类型（project/skill/experience/note/other）"
}}
"""
    messages = [{"role": "user", "content": extract_prompt}]
    llm_response = llm_client.invoke(messages)

    # 解析 LLM 返回的 JSON
    json_match = re.search(r'\{[\s\S]*\}', llm_response)
    if json_match:
        extracted_info = json.loads(json_match.group())
    else:
        extracted_info = {
            "title": title or "未命名知识",
            "summary": content[:100],
            "keywords": [],
            "tech_stack": [],
            "type": category
        }

    # 2. 构建增强后的内容用于索引
    enhanced_content = f"""# {extracted_info.get('title', title or '知识条目')}

## 摘要
{extracted_info.get('summary', '')}

## 关键词
{', '.join(extracted_info.get('keywords', []))}

## 技术栈
{', '.join(extracted_info.get('tech_stack', []))}

## 详细内容
{content}
"""

    # 3. 生成嵌入向量
    embeddings = embedding_model.encode([enhanced_content])

    # 4. 生成唯一 ID
    content_hash = hashlib.md5(f"{content}:{datetime.now().isoformat()}".encode()).hexdigest()

    # 5. 存储到 Qdrant
    point = PointStruct(
        id=content_hash,
        vector=embeddings[0].tolist(),
        payload={
            "content": enhanced_content,
            "original_content": content,
            "title": extracted_info.get('title', title),
            "summary": extracted_info.get('summary', ''),
            "keywords": extracted_info.get('keywords', []),
            "tech_stack": extracted_info.get('tech_stack', []),
            "type": "knowledge",
            "category": extracted_info.get('type', category),
            "created_at": datetime.now().isoformat(),
            "file_path": f"knowledge/{content_hash[:8]}"
        }
    )

    qdrant_client.upsert(
        collection_name=QDRANT_COLLECTION_NAME,
        points=[point]
    )

    # 格式化输出
    output = "## 知识添加成功\n\n"
    output += f"**标题**: {extracted_info.get('title', '未命名')}\n\n"
    output += f"**摘要**: {extracted_info.get('summary', '')}\n\n"
    output += f"**关键词**: {', '.join(extracted_info.get('keywords', []))}\n\n"
    output += f"**技术栈**: {', '.join(extracted_info.get('tech_stack', []))}\n\n"
    output += f"**分类**: {extracted_info.get('type', category)}\n\n"
    output += f"**ID**: `{content_hash[:8]}`\n"

    return output


if __name__ == "__main__":
    mcp.run()
