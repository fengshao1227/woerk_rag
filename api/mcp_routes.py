"""
MCP 集成路由 (Streamable HTTP)

将 MCP Server 集成到 FastAPI 服务中，支持多会话并发。
通过 /mcp 端点提供 MCP 服务。

Claude Desktop 配置:
{
    "mcpServers": {
        "rag-knowledge": {
            "url": "https://rag.litxczv.shop/mcp"
        }
    }
}

注意: 需要在请求头中设置 X-API-Key 进行认证
"""

import httpx
import time
import asyncio
from typing import Optional
from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from starlette.applications import Starlette
from starlette.routing import Mount

from mcp.server.fastmcp import FastMCP

from admin.models import MCPApiKey, KnowledgeGroup, KnowledgeGroupItem, KnowledgeEntry, LLMModel
from admin.database import SessionLocal
from sqlalchemy import func
from utils.logger import logger

# 创建 MCP Server 实例（无状态模式，支持并发）
mcp = FastMCP("RAG Knowledge Base", stateless_http=True, json_response=True)

# 创建路由
router = APIRouter(tags=["MCP"])

# RAG API 基础地址（内部调用）
RAG_API_INTERNAL = "http://127.0.0.1:8000"

# 搜索结果相似度阈值
SEARCH_SCORE_THRESHOLD = 0.4


def verify_api_key_sync(api_key: str) -> Optional[dict]:
    """验证 API Key 并返回用户信息（同步版本）"""
    if not api_key:
        return None

    try:
        with SessionLocal() as db:
            key_record = db.query(MCPApiKey).filter(
                MCPApiKey.key == api_key,
                MCPApiKey.is_active == True
            ).first()

            if not key_record:
                return None

            # 检查过期时间
            if key_record.expires_at and key_record.expires_at < time.time():
                return None

            return {
                "user_id": key_record.user_id,
                "key_id": key_record.id,
                "name": key_record.name
            }
    except Exception as e:
        logger.error(f"验证 API Key 失败: {e}")
        return None


# ===================== MCP 工具定义 =====================

@mcp.tool()
def query(question: str, top_k: int = 5, group_names: Optional[str] = None) -> str:
    """
    RAG 智能问答 - 基于知识库生成详细回答

    根据问题检索相关知识，由 AI 生成综合性回答并标注来源。
    适用于需要详细解答的复杂问题。

    Args:
        question: 要询问的问题（支持自然语言）
        top_k: 检索的相关文档数量，默认5，增大可获取更多上下文
        group_names: 限定检索范围，多个分组用逗号分隔，如 "fm,项目A"

    Returns:
        包含 AI 回答和参考来源的完整响应
    """
    try:
        # 解析分组名称
        groups = [g.strip() for g in group_names.split(",")] if group_names else None

        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{RAG_API_INTERNAL}/query",
                json={"question": question, "top_k": top_k, "group_names": groups},
                headers={"X-MCP-Internal": "true"}
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

    except httpx.ConnectError:
        return "## 连接失败\n\n无法连接到知识库服务。"
    except Exception as e:
        return f"## 错误\n\n调用失败: {str(e)}"


@mcp.tool()
def search(
    query_text: str,
    top_k: int = 5,
    group_names: Optional[str] = None,
    min_score: Optional[float] = None
) -> str:
    """
    语义搜索 - 快速查找知识库中的相关内容

    基于向量相似度匹配，返回最相关的知识条目及相似度分数。
    不调用 AI 生成回答，速度更快。

    Args:
        query_text: 搜索关键词或问题（支持自然语言）
        top_k: 返回结果数量，默认5
        group_names: 限定搜索范围，多个分组用逗号分隔，如 "fm,项目A"
        min_score: 最低相似度阈值（0-1），低于此值的结果不返回

    Returns:
        匹配的知识条目列表，包含相似度分数和内容预览
    """
    try:
        groups = [g.strip() for g in group_names.split(",")] if group_names else None

        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{RAG_API_INTERNAL}/search",
                json={"query": query_text, "top_k": top_k, "group_names": groups},
                headers={"X-MCP-Internal": "true"}
            )
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])

        # 应用相似度阈值过滤
        score_threshold = min_score if min_score is not None else 0.0
        filtered_results = [r for r in results if r.get("score", 0) >= score_threshold]
        low_relevance_count = len(results) - len(filtered_results)

        if not filtered_results:
            if low_relevance_count > 0:
                return f"## 未找到高相关内容\n\n有 {low_relevance_count} 条结果相似度低于 {score_threshold:.2f}，已被过滤。"
            return "## 未找到相关内容\n\n知识库中没有匹配的内容。"

        output = f"## 搜索结果（共 {len(filtered_results)} 条）\n\n"

        for i, item in enumerate(filtered_results, 1):
            content = item.get("content", "")
            file_path = item.get("file_path", "未知")
            score = item.get("score", 0)
            title = item.get("title", "")
            category = item.get("category", "")

            preview = content[:300] + "..." if len(content) > 300 else content

            # 相似度标注
            if score >= 0.7:
                score_label = "🟢 高相关"
            elif score >= 0.5:
                score_label = "🟡 中等相关"
            elif score >= SEARCH_SCORE_THRESHOLD:
                score_label = "🟠 低相关"
            else:
                score_label = "⚪ 边缘相关"

            output += f"### {i}. {title or file_path}\n"
            if category:
                output += f"- **分类**: {category}\n"
            output += f"- **来源**: `{file_path}`\n"
            output += f"- **相似度**: {score:.3f} ({score_label})\n"
            output += f"- **内容预览**:\n```\n{preview}\n```\n\n"

        if low_relevance_count > 0:
            output += f"\n> 💡 另有 {low_relevance_count} 条低相关结果未显示"

        return output

    except httpx.ConnectError:
        return "## 连接失败\n\n无法连接到知识库服务。"
    except Exception as e:
        return f"## 错误\n\n调用失败: {str(e)}"


@mcp.tool()
def add_knowledge(
    content: str,
    title: Optional[str] = None,
    category: str = "general",
    group_names: Optional[str] = None
) -> str:
    """
    添加知识 - 将新内容存入知识库

    AI 会自动提取标题、摘要、关键词和技术栈。
    支持项目经历、技术笔记、学习心得等各类内容。

    Args:
        content: 知识内容（至少10个字符）
        title: 可选标题，不提供则由 AI 自动生成
        category: 分类 - project(项目)/skill(技能)/experience(经历)/note(笔记)/general(通用)
        group_names: 添加到指定分组，多个用逗号分隔，如 "fm,项目A"

    Returns:
        添加结果，包含 AI 提取的标题、摘要、关键词等信息
    """
    try:
        groups = [g.strip() for g in group_names.split(",")] if group_names else None

        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{RAG_API_INTERNAL}/add_knowledge",
                json={
                    "content": content,
                    "title": title,
                    "category": category,
                    "group_names": groups
                },
                headers={"X-MCP-Internal": "true"}
            )
            response.raise_for_status()
            result = response.json()

        task_id = result.get("task_id")
        if task_id:
            # 异步任务，等待完成
            start_time = time.time()
            while time.time() - start_time < 120:
                time.sleep(2)
                with httpx.Client(timeout=30.0) as client:
                    status_response = client.get(
                        f"{RAG_API_INTERNAL}/add_knowledge/status/{task_id}",
                        headers={"X-MCP-Internal": "true"}
                    )
                    status_data = status_response.json()

                status = status_data.get("status", "")
                if status == "completed":
                    return "## 知识添加成功\n\n内容已成功存入知识库。"
                elif status == "failed":
                    return f"## 添加失败\n\n{status_data.get('message', '未知错误')}"

            return "## 处理超时\n\n任务仍在处理中，请稍后查看。"

        # 直接返回结果
        output = "## 知识添加成功\n\n"
        if result.get("title"):
            output += f"**标题**: {result['title']}\n\n"
        if result.get("summary"):
            output += f"**摘要**: {result['summary']}\n\n"
        return output

    except Exception as e:
        return f"## 错误\n\n添加知识失败: {str(e)}"


@mcp.tool()
def list_groups() -> str:
    """
    列出分组 - 查看知识库中所有可用的分组

    Returns:
        分组列表，包含名称、描述和条目数量
    """
    try:
        with SessionLocal() as db:
            # 查询所有活跃的公开分组
            groups = db.query(KnowledgeGroup).filter(
                KnowledgeGroup.is_active == True,
                KnowledgeGroup.is_public == True
            ).order_by(KnowledgeGroup.id.desc()).all()

            if not groups:
                return "## 暂无分组\n\n知识库中尚未创建任何公开分组。"

            output = f"## 知识库分组（共 {len(groups)} 个）\n\n"

            for g in groups:
                # 统计分组内条目数量
                items_count = db.query(func.count(KnowledgeGroupItem.id)).filter(
                    KnowledgeGroupItem.group_id == g.id
                ).scalar() or 0

                output += f"### {g.name}\n"
                if g.description:
                    output += f"- **描述**: {g.description}\n"
                output += f"- **条目数**: {items_count}\n\n"

            return output

    except Exception as e:
        logger.error(f"获取分组列表失败: {e}")
        return f"## 错误\n\n获取分组列表失败: {str(e)}"


@mcp.tool()
def stats() -> str:
    """
    统计信息 - 查看知识库整体统计数据

    Returns:
        知识库总条目数、分组统计、分类分布等信息
    """
    try:
        with SessionLocal() as db:
            # 总条目数
            total_knowledge = db.query(func.count(KnowledgeEntry.id)).scalar() or 0

            # 公开分组数
            total_groups = db.query(func.count(KnowledgeGroup.id)).filter(
                KnowledgeGroup.is_active == True,
                KnowledgeGroup.is_public == True
            ).scalar() or 0

            # 按分类统计
            category_stats = db.query(
                KnowledgeEntry.category,
                func.count(KnowledgeEntry.id)
            ).group_by(KnowledgeEntry.category).all()

            # LLM 模型数
            total_models = db.query(func.count(LLMModel.id)).filter(
                LLMModel.is_active == True
            ).scalar() or 0

        output = "## 知识库统计\n\n"
        output += f"**总条目数**: {total_knowledge}\n\n"
        output += f"**分组数**: {total_groups}\n\n"

        if category_stats:
            output += "**分类分布**:\n"
            for cat, count in category_stats:
                output += f"- {cat or 'unknown'}: {count}\n"
            output += "\n"

        output += f"**LLM 模型数**: {total_models}\n"

        return output

    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        return f"## 错误\n\n获取统计信息失败: {str(e)}"


# ===================== MCP 应用挂载 =====================

def get_mcp_app():
    """获取 MCP Streamable HTTP 应用"""
    return mcp.streamable_http_app()


@router.get("/mcp/health")
async def mcp_health():
    """MCP 服务健康检查"""
    return {
        "status": "ok",
        "service": "MCP Server (Integrated)",
        "transport": "streamable-http",
        "endpoint": "/mcp",
        "tools": ["query", "search", "add_knowledge", "list_groups", "stats"]
    }


from datetime import datetime

@router.post("/mcp/verify")
async def verify_mcp_api_key(request: Request):
    """
    验证 MCP API 卡密（公开端点，无需登录）

    请求体: {"api_key": "rag_sk_xxx"}
    返回: {"valid": true/false, "message": "...", "name": "卡密名称"}
    """
    try:
        body = await request.json()
        api_key = body.get("api_key", "")

        if not api_key:
            return {"valid": False, "message": "缺少 api_key 参数", "name": None}

        db = SessionLocal()
        try:
            key_record = db.query(MCPApiKey).filter(
                MCPApiKey.key == api_key,
                MCPApiKey.is_active == True
            ).first()

            if not key_record:
                return {"valid": False, "message": "无效的卡密", "name": None}

            # 检查过期时间
            if key_record.expires_at and key_record.expires_at < datetime.now():
                return {"valid": False, "message": "卡密已过期", "name": key_record.name}

            # 更新使用统计
            key_record.last_used_at = datetime.now()
            key_record.usage_count += 1
            db.commit()

            return {"valid": True, "message": "验证成功", "name": key_record.name}
        finally:
            db.close()

    except Exception as e:
        logger.error(f"验证卡密失败: {e}")
        return {"valid": False, "message": f"验证失败: {str(e)}", "name": None}
