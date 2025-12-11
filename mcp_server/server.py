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
import os
from typing import Optional
from mcp.server.fastmcp import FastMCP

# 远程 RAG API 地址
RAG_API_BASE = os.environ.get("RAG_API_BASE", "https://rag.litxczv.shop")

# MCP 认证凭据（从环境变量读取，或使用默认值）
MCP_USERNAME = os.environ.get("RAG_MCP_USERNAME", "admin")
MCP_PASSWORD = os.environ.get("RAG_MCP_PASSWORD", "admin123")

# 初始化 MCP Server
mcp = FastMCP("RAG Knowledge Base")

# 全局 token 缓存
_auth_token: Optional[str] = None


def get_auth_token() -> str:
    """获取认证 token，如果没有则登录获取"""
    global _auth_token
    if _auth_token:
        return _auth_token

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{RAG_API_BASE}/admin/api/auth/login",
                json={"username": MCP_USERNAME, "password": MCP_PASSWORD}
            )
            response.raise_for_status()
            data = response.json()
            _auth_token = data.get("access_token")
            return _auth_token
    except Exception as e:
        raise Exception(f"认证失败: {str(e)}")


def get_auth_headers() -> dict:
    """获取认证请求头"""
    token = get_auth_token()
    return {
        "Authorization": f"Bearer {token}",
        "X-MCP-Client": "true"  # 标识这是来自 MCP 的调用
    }


@mcp.tool()
def query(question: str, top_k: int = 5, group_names: Optional[str] = None) -> str:
    """
    RAG 问答:基于知识库回答问题

    Args:
        question: 要询问的问题
        top_k: 检索的相关文档数量,默认5
        group_names: 可选的分组名称,多个用逗号分隔,如"fm,项目A",限定在指定分组中检索

    Returns:
        包含答案和来源的回复
    """
    try:
        headers = get_auth_headers()

        # 解析分组名称
        groups = [g.strip() for g in group_names.split(",")] if group_names else None

        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{RAG_API_BASE}/query",
                json={"question": question, "top_k": top_k, "group_names": groups},
                headers=headers
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
def search(query_text: str, top_k: int = 5, group_names: Optional[str] = None) -> str:
    """
    向量检索:搜索知识库中的相关内容

    Args:
        query_text: 搜索查询文本
        top_k: 返回结果数量,默认5
        group_names: 可选的分组名称,多个用逗号分隔,如"fm,项目A",限定在指定分组中检索

    Returns:
        匹配的知识条目列表
    """
    try:
        headers = get_auth_headers()

        # 解析分组名称
        groups = [g.strip() for g in group_names.split(",")] if group_names else None

        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{RAG_API_BASE}/search",
                json={"query": query_text, "top_k": top_k, "group_names": groups},
                headers=headers
            )
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])

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
def add_knowledge(content: str, title: Optional[str] = None, category: str = "general", group_names: Optional[str] = None) -> str:
    """
    添加知识:将新知识添加到知识库,AI 会自动提取关键信息

    Args:
        content: 知识内容（项目经历、技术笔记、学习心得等）
        title: 可选的标题,不提供则由 AI 自动生成
        category: 分类,可选值:project（项目）、skill（技能）、experience（经历）、note（笔记）、general（通用）
        group_names: 可选的分组名称,多个用逗号分隔,如"fm,项目A"

    Returns:
        添加结果和提取的关键信息
    """
    try:
        headers = get_auth_headers()

        # 解析分组名称
        groups = [g.strip() for g in group_names.split(",")] if group_names else None

        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{RAG_API_BASE}/add_knowledge",
                json={
                    "content": content,
                    "title": title,
                    "category": category,
                    "group_names": groups
                },
                headers=headers
            )
            response.raise_for_status()
            result = response.json()

        output = "## 知识添加成功\n\n"
        output += f"**标题**: {result.get('title', '未命名')}\n\n"
        output += f"**摘要**: {result.get('summary', '')}\n\n"
        output += f"**关键词**: {', '.join(result.get('keywords', []))}\n\n"
        output += f"**技术栈**: {', '.join(result.get('tech_stack', []))}\n\n"
        output += f"**分类**: {result.get('category', category)}\n\n"
        if groups:
            output += f"**已添加到分组**: {', '.join(groups)}\n\n"
        output += f"**ID**: `{result.get('id', 'unknown')}`\n"

        return output

    except Exception as e:
        return f"## 错误\n\n添加知识失败: {str(e)}"


def main():
    """MCP Server 入口函数，供 uvx 调用"""
    mcp.run()


if __name__ == "__main__":
    main()
