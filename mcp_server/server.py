"""
RAG 知识库 MCP Server (远程 API 版本)

通过 HTTPS 调用远程 RAG API 服务

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
import httpx
from typing import Optional
from mcp.server.fastmcp import FastMCP

# 远程 RAG API 地址
RAG_API_BASE = "https://rag.litxczv.shop"

# 初始化 MCP Server
mcp = FastMCP("RAG Knowledge Base")


@mcp.tool()
def query(question: str, top_k: int = 5) -> str:
    """
    RAG 问答:基于知识库回答问题

    Args:
        question: 要询问的问题
        top_k: 检索的相关文档数量,默认5

    Returns:
        包含答案和来源的回复
    """
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{RAG_API_BASE}/query",
                json={"question": question, "top_k": top_k}
            )
            response.raise_for_status()
            result = response.json()

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

    except Exception as e:
        return f"## 错误\n\n调用 RAG API 失败: {str(e)}"


@mcp.tool()
def search(query_text: str, top_k: int = 5) -> str:
    """
    向量检索:搜索知识库中的相关内容

    Args:
        query_text: 搜索查询文本
        top_k: 返回结果数量,默认5

    Returns:
        匹配的知识条目列表
    """
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{RAG_API_BASE}/search",
                json={"query": query_text, "top_k": top_k}
            )
            response.raise_for_status()
            results = response.json()

        if not results:
            return "未找到相关内容"

        output = f"## 搜索结果（共 {len(results)} 条）\n\n"

        for i, item in enumerate(results, 1):
            content = item.get("content", "")
            file_path = item.get("file_path", "未知")
            score = item.get("score", 0)
            title = item.get("title", "")

            preview = content[:300] + "..." if len(content) > 300 else content

            output += f"### {i}. {title or file_path}\n"
            output += f"- **来源**: `{file_path}`\n"
            output += f"- **相似度**: {score:.3f}\n"
            output += f"- **内容预览**:\n```\n{preview}\n```\n\n"

        return output

    except Exception as e:
        return f"## 错误\n\n调用 RAG API 失败: {str(e)}"


@mcp.tool()
def add_knowledge(content: str, title: Optional[str] = None, category: str = "general") -> str:
    """
    添加知识:将新知识添加到知识库,AI 会自动提取关键信息

    Args:
        content: 知识内容（项目经历、技术笔记、学习心得等）
        title: 可选的标题,不提供则由 AI 自动生成
        category: 分类,可选值:project（项目）、skill（技能）、experience（经历）、note（笔记）、general（通用）

    Returns:
        添加结果和提取的关键信息
    """
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{RAG_API_BASE}/add_knowledge",
                json={
                    "content": content,
                    "title": title,
                    "category": category
                }
            )
            response.raise_for_status()
            result = response.json()

        output = "## 知识添加成功\n\n"
        output += f"**标题**: {result.get('title', '未命名')}\n\n"
        output += f"**摘要**: {result.get('summary', '')}\n\n"
        output += f"**关键词**: {', '.join(result.get('keywords', []))}\n\n"
        output += f"**技术栈**: {', '.join(result.get('tech_stack', []))}\n\n"
        output += f"**分类**: {result.get('category', category)}\n\n"
        output += f"**ID**: `{result.get('id', 'unknown')}`\n"

        return output

    except Exception as e:
        return f"## 错误\n\n添加知识失败: {str(e)}"


def main():
    """MCP Server 入口函数，供 uvx 调用"""
    mcp.run()


if __name__ == "__main__":
    main()
