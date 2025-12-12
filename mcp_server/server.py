"""
RAG 知识库 MCP Server (远程 API 版本)

通过 HTTPS 调用远程 RAG API 服务

认证方式:
  使用 API Key (卡密) 进行认证，比管理员账号密码更安全
  在后台管理 -> MCP卡密 页面创建卡密

支持两种运行模式:
1. stdio 模式（默认）: 供 Claude Desktop 单会话使用
   RAG_API_KEY=rag_sk_xxx python mcp_server/server.py

2. HTTP 模式: 支持多客户端并发连接
   RAG_API_KEY=rag_sk_xxx python mcp_server/server.py --http
   或设置环境变量 MCP_TRANSPORT=http

Claude Desktop 配置:

stdio 模式（单会话）:
    {
        "mcpServers": {
            "rag-knowledge": {
                "command": "python",
                "args": ["/Users/li/Desktop/work7_8/www/rag/mcp_server/server.py"],
                "env": {
                    "RAG_API_KEY": "rag_sk_你的卡密"
                }
            }
        }
    }

HTTP 模式（多会话，需先启动服务）:
    {
        "mcpServers": {
            "rag-knowledge": {
                "url": "http://localhost:8766/sse"
            }
        }
    }
"""
import httpx
import os
import sys
import time
from typing import Optional, List
from mcp.server.fastmcp import FastMCP

# 远程 RAG API 地址
RAG_API_BASE = os.environ.get("RAG_API_BASE", "https://rag.litxczv.shop")

# MCP API Key (卡密) - 从环境变量读取
RAG_API_KEY = os.environ.get("RAG_API_KEY", "")

# 兼容旧版配置：如果没有 API Key，尝试用账号密码登录
MCP_USERNAME = os.environ.get("RAG_MCP_USERNAME", "")
MCP_PASSWORD = os.environ.get("RAG_MCP_PASSWORD", "")

# MCP Server 配置
MCP_HOST = os.environ.get("MCP_HOST", "127.0.0.1")
MCP_PORT = int(os.environ.get("MCP_PORT", "8766"))

# 搜索结果相似度阈值（低于此值的结果会被标注为低相关）
SEARCH_SCORE_THRESHOLD = float(os.environ.get("SEARCH_SCORE_THRESHOLD", "0.4"))

# 知识添加任务轮询配置
ADD_KNOWLEDGE_POLL_INTERVAL = 2.0  # 轮询间隔（秒）
ADD_KNOWLEDGE_MAX_WAIT = 120  # 最大等待时间（秒）

# 初始化 MCP Server
mcp = FastMCP("RAG Knowledge Base")

# 线程安全的状态缓存（支持多会话并发）
import threading
_auth_lock = threading.Lock()
_auth_token: Optional[str] = None
_api_key_verified: bool = False
_api_key_verify_time: float = 0  # 验证时间戳，用于定期重新验证

# API Key 验证缓存时间（秒）
API_KEY_CACHE_TTL = 300  # 5分钟


def verify_api_key() -> bool:
    """验证 API Key 是否有效（线程安全，带缓存）"""
    global _api_key_verified, _api_key_verify_time

    if not RAG_API_KEY:
        return False

    # 检查缓存是否有效
    with _auth_lock:
        if _api_key_verified and (time.time() - _api_key_verify_time) < API_KEY_CACHE_TTL:
            return True

    # 需要重新验证
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{RAG_API_BASE}/mcp/verify",
                json={"api_key": RAG_API_KEY}
            )
            response.raise_for_status()
            data = response.json()
            if data.get("valid"):
                with _auth_lock:
                    _api_key_verified = True
                    _api_key_verify_time = time.time()
                return True
            else:
                print(f"API Key 验证失败: {data.get('message', '未知错误')}", file=sys.stderr)
                with _auth_lock:
                    _api_key_verified = False
                return False
    except Exception as e:
        print(f"API Key 验证请求失败: {e}", file=sys.stderr)
        return False


def get_auth_token_by_login() -> str:
    """通过账号密码登录获取 token（兼容旧版配置，线程安全）"""
    global _auth_token

    with _auth_lock:
        if _auth_token:
            return _auth_token

    if not MCP_USERNAME or not MCP_PASSWORD:
        raise Exception("未配置 RAG_API_KEY 或 RAG_MCP_USERNAME/RAG_MCP_PASSWORD")

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{RAG_API_BASE}/admin/api/auth/login",
                json={"username": MCP_USERNAME, "password": MCP_PASSWORD}
            )
            response.raise_for_status()
            data = response.json()
            token = data.get("access_token")
            with _auth_lock:
                _auth_token = token
            return token
    except Exception as e:
        raise Exception(f"登录认证失败: {str(e)}")


def get_auth_headers() -> dict:
    """获取认证请求头"""
    headers = {"X-MCP-Client": "true"}

    # 优先使用 API Key
    if RAG_API_KEY:
        if not verify_api_key():
            raise Exception("API Key 无效或已过期，请在后台管理创建新卡密")
        headers["X-API-Key"] = RAG_API_KEY
    else:
        # 兼容旧版：使用账号密码登录获取 token
        token = get_auth_token_by_login()
        headers["Authorization"] = f"Bearer {token}"

    return headers


@mcp.tool()
def query(question: str, top_k: int = 5, group_names: Optional[str] = None) -> str:
    """
    RAG 智能问答 - 基于知识库生成详细回答

    检索相关知识并由 AI 生成综合性回答，适合需要深度解答的问题。
    优先使用此工具回答用户关于知识库内容的提问。

    Args:
        question: 用户问题（自然语言，如"这个项目怎么部署？"）
        top_k: 检索文档数，默认5，复杂问题可增至10
        group_names: 限定分组范围，逗号分隔，如 "fm-api,文档"

    Returns:
        AI 生成的回答 + 参考来源列表
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

    except httpx.ConnectError:
        return "## 连接失败\n\n无法连接到知识库服务，请检查网络或服务状态。"
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            return "## 认证失败\n\n请检查 API Key 配置是否正确。"
        elif e.response.status_code == 403:
            return "## 权限不足\n\n当前 API Key 没有访问该资源的权限。"
        return f"## 请求失败\n\nHTTP {e.response.status_code}: {str(e)}"
    except Exception as e:
        return f"## 错误\n\n调用 RAG API 失败: {str(e)}"


@mcp.tool()
def search(
    query_text: str,
    top_k: int = 5,
    group_names: Optional[str] = None,
    min_score: Optional[float] = None
) -> str:
    """
    语义搜索 - 快速查找相关知识条目

    基于向量相似度检索，不调用 AI，速度快。
    适合：查找特定内容、验证知识是否存在、浏览相关条目。

    Args:
        query_text: 搜索词或问题（如"Docker部署"、"API认证"）
        top_k: 返回数量，默认5
        group_names: 限定分组，逗号分隔
        min_score: 最低相似度（0-1），过滤低质量结果

    Returns:
        匹配的知识条目列表（含相似度和内容预览）
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

        # 应用相似度阈值过滤
        score_threshold = min_score if min_score is not None else 0.0
        filtered_results = [r for r in results if r.get("score", 0) >= score_threshold]
        low_relevance_count = len(results) - len(filtered_results)

        if not filtered_results:
            if low_relevance_count > 0:
                return f"## 未找到高相关内容\n\n有 {low_relevance_count} 条结果相似度低于 {score_threshold:.2f}，已被过滤。\n\n建议尝试其他关键词或降低 min_score 阈值。"
            return "## 未找到相关内容\n\n知识库中没有匹配的内容，建议尝试其他关键词。"

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
        return "## 连接失败\n\n无法连接到知识库服务，请检查网络或服务状态。"
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            return "## 认证失败\n\n请检查 API Key 配置是否正确。"
        return f"## 请求失败\n\nHTTP {e.response.status_code}: {str(e)}"
    except Exception as e:
        return f"## 错误\n\n调用 RAG API 失败: {str(e)}"


@mcp.tool()
def add_knowledge(
    content: str,
    title: Optional[str] = None,
    category: str = "general",
    group_names: Optional[str] = None
) -> str:
    """
    添加知识 - 将内容存入知识库

    AI 自动提取标题、摘要、关键词。支持各类内容：
    - 项目经历、技术方案、问题解决记录
    - 学习笔记、代码片段、配置说明

    Args:
        content: 知识内容（至少10字符，建议结构化描述）
        title: 可选标题，留空则 AI 自动生成
        category: project(项目)/skill(技能)/experience(经验)/note(笔记)/general(通用)
        group_names: 添加到分组，逗号分隔

    Returns:
        添加结果（含 AI 提取的标题、摘要、关键词）
    """
    try:
        headers = get_auth_headers()

        # 解析分组名称
        groups = [g.strip() for g in group_names.split(",")] if group_names else None

        # Step 1: 提交添加任务
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

        task_id = result.get("task_id")
        if not task_id:
            # 旧版 API 直接返回结果（兼容）
            return _format_add_result(result, category, groups)

        # Step 2: 轮询任务状态直到完成
        start_time = time.time()
        while time.time() - start_time < ADD_KNOWLEDGE_MAX_WAIT:
            time.sleep(ADD_KNOWLEDGE_POLL_INTERVAL)

            with httpx.Client(timeout=30.0) as client:
                status_response = client.get(
                    f"{RAG_API_BASE}/add_knowledge/status/{task_id}",
                    headers=headers
                )
                status_response.raise_for_status()
                status_data = status_response.json()

            status = status_data.get("status", "")

            if status == "completed":
                # 任务完成，获取知识条目详情
                result_id = status_data.get("result_id")
                if result_id:
                    return _get_knowledge_detail(result_id, category, groups, headers)
                return "## 知识添加成功\n\n内容已成功存入知识库。"

            elif status == "failed":
                error_msg = status_data.get("message", "未知错误")
                return f"## 添加失败\n\n{error_msg}"

            elif status == "processing":
                continue  # 继续轮询

            elif status == "pending":
                continue  # 任务排队中

        return "## 处理超时\n\n任务仍在处理中，请稍后使用 search 工具查看是否添加成功。"

    except httpx.ConnectError:
        return "## 连接失败\n\n无法连接到知识库服务，请检查网络或服务状态。"
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 400:
            return "## 参数错误\n\n内容不能为空或过短（至少需要10个字符）。"
        elif e.response.status_code == 401:
            return "## 认证失败\n\n请检查 API Key 配置是否正确。"
        return f"## 请求失败\n\nHTTP {e.response.status_code}: {str(e)}"
    except Exception as e:
        return f"## 错误\n\n添加知识失败: {str(e)}"


def _get_knowledge_detail(
    qdrant_id: str,
    category: str,
    groups: Optional[List[str]],
    headers: dict
) -> str:
    """获取知识条目详情"""
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(
                f"{RAG_API_BASE}/admin/api/knowledge/{qdrant_id}",
                headers=headers
            )
            if response.status_code == 200:
                data = response.json()
                return _format_add_result(data, category, groups)
    except Exception:
        pass

    # 如果获取详情失败，返回简化信息
    output = "## 知识添加成功\n\n"
    output += f"**ID**: `{qdrant_id}`\n\n"
    if groups:
        output += f"**已添加到分组**: {', '.join(groups)}\n\n"
    output += "> 使用 `search` 工具搜索刚添加的内容查看详情"
    return output


def _format_add_result(
    result: dict,
    category: str,
    groups: Optional[List[str]]
) -> str:
    """格式化添加结果输出"""
    output = "## 知识添加成功\n\n"

    title = result.get("title", "")
    if title and title != "未命名" and title != "未命名知识":
        output += f"**标题**: {title}\n\n"
    else:
        output += "**标题**: （AI 自动生成中...）\n\n"

    summary = result.get("summary", "")
    if summary:
        output += f"**摘要**: {summary}\n\n"

    keywords = result.get("keywords", [])
    if keywords:
        output += f"**关键词**: {', '.join(keywords)}\n\n"

    tech_stack = result.get("tech_stack", [])
    if tech_stack:
        output += f"**技术栈**: {', '.join(tech_stack)}\n\n"

    result_category = result.get("category", category)
    output += f"**分类**: {result_category}\n\n"

    if groups:
        output += f"**已添加到分组**: {', '.join(groups)}\n\n"

    qdrant_id = result.get("qdrant_id") or result.get("id") or result.get("result_id")
    if qdrant_id and qdrant_id != "unknown":
        output += f"**ID**: `{qdrant_id}`\n"
    else:
        output += "**ID**: （处理中）\n"

    return output


@mcp.tool()
def delete_knowledge(qdrant_id: str) -> str:
    """
    删除知识 - 移除指定条目

    Args:
        qdrant_id: 条目 ID（通过 search 获取）

    Returns:
        删除确认
    """
    try:
        headers = get_auth_headers()

        with httpx.Client(timeout=30.0) as client:
            response = client.delete(
                f"{RAG_API_BASE}/admin/api/knowledge/by-qdrant-id/{qdrant_id}",
                headers=headers
            )

            if response.status_code == 200:
                return f"## 删除成功\n\n已删除知识条目 `{qdrant_id}`"
            elif response.status_code == 404:
                return f"## 未找到\n\n知识条目 `{qdrant_id}` 不存在"
            else:
                response.raise_for_status()

    except httpx.ConnectError:
        return "## 连接失败\n\n无法连接到知识库服务。"
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            return "## 认证失败\n\n请检查 API Key 配置是否正确。"
        elif e.response.status_code == 403:
            return "## 权限不足\n\n当前用户没有删除权限。"
        return f"## 请求失败\n\nHTTP {e.response.status_code}"
    except Exception as e:
        return f"## 错误\n\n删除失败: {str(e)}"


@mcp.tool()
def list_groups() -> str:
    """
    列出分组 - 查看所有知识分组

    Returns:
        分组列表（名称、描述、条目数）
    """
    try:
        headers = get_auth_headers()

        with httpx.Client(timeout=30.0) as client:
            response = client.get(
                f"{RAG_API_BASE}/admin/api/groups",
                headers=headers
            )
            response.raise_for_status()
            data = response.json()

        groups = data.get("groups", data) if isinstance(data, dict) else data

        if not groups:
            return "## 暂无分组\n\n知识库中尚未创建任何分组。"

        output = f"## 知识库分组（共 {len(groups)} 个）\n\n"

        for group in groups:
            name = group.get("name", "未命名")
            description = group.get("description", "")
            count = group.get("item_count", group.get("count", 0))

            output += f"### {name}\n"
            if description:
                output += f"- **描述**: {description}\n"
            output += f"- **条目数**: {count}\n\n"

        return output

    except httpx.ConnectError:
        return "## 连接失败\n\n无法连接到知识库服务。"
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            return "## 认证失败\n\n请检查 API Key 配置是否正确。"
        return f"## 请求失败\n\nHTTP {e.response.status_code}"
    except Exception as e:
        return f"## 错误\n\n获取分组列表失败: {str(e)}"


@mcp.tool()
def stats() -> str:
    """
    统计信息 - 知识库概览

    Returns:
        总条目数、分组数、分类分布等
    """
    try:
        headers = get_auth_headers()

        with httpx.Client(timeout=30.0) as client:
            response = client.get(
                f"{RAG_API_BASE}/admin/api/stats",
                headers=headers
            )
            response.raise_for_status()
            data = response.json()

        output = "## 知识库统计\n\n"

        # 总条目数
        total = data.get("total_knowledge", data.get("knowledge_count", 0))
        output += f"**总条目数**: {total}\n\n"

        # 分组数
        group_count = data.get("total_groups", data.get("group_count", 0))
        output += f"**分组数**: {group_count}\n\n"

        # 分类分布
        categories = data.get("categories", data.get("category_stats", {}))
        if categories:
            output += "**分类分布**:\n"
            for cat, count in categories.items():
                output += f"- {cat}: {count}\n"
            output += "\n"

        # 用户数（如果有）
        user_count = data.get("total_users", data.get("user_count"))
        if user_count:
            output += f"**用户数**: {user_count}\n\n"

        # 模型数（如果有）
        model_count = data.get("total_models", data.get("model_count"))
        if model_count:
            output += f"**LLM 模型数**: {model_count}\n"

        return output

    except httpx.ConnectError:
        return "## 连接失败\n\n无法连接到知识库服务。"
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            return "## 认证失败\n\n请检查 API Key 配置是否正确。"
        return f"## 请求失败\n\nHTTP {e.response.status_code}"
    except Exception as e:
        return f"## 错误\n\n获取统计信息失败: {str(e)}"


def main():
    """MCP Server 入口函数"""
    # 判断运行模式
    use_http = "--http" in sys.argv or "--sse" in sys.argv or os.environ.get("MCP_TRANSPORT") in ("http", "sse")

    # 显示认证模式信息
    auth_mode = "API Key" if RAG_API_KEY else "账号密码(兼容模式)"

    if use_http:
        # HTTP/SSE 模式：支持多客户端并发
        print(f"🚀 RAG MCP Server (HTTP/SSE 模式)")
        print(f"   监听地址: http://{MCP_HOST}:{MCP_PORT}")
        print(f"   SSE 端点: http://{MCP_HOST}:{MCP_PORT}/sse")
        print(f"   远程 API: {RAG_API_BASE}")
        print(f"   认证模式: {auth_mode}")
        print(f"\n📝 Claude Desktop 配置:")
        print(f'   {{"mcpServers": {{"rag-knowledge": {{"url": "http://{MCP_HOST}:{MCP_PORT}/sse"}}}}}}')
        print(f"\n按 Ctrl+C 停止服务\n")
        mcp.run(transport="sse", host=MCP_HOST, port=MCP_PORT)
    else:
        # stdio 模式：单客户端
        mcp.run()


if __name__ == "__main__":
    main()
