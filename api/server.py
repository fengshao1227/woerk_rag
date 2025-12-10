"""
FastAPI 服务
"""
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
import sys
import json
import time
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from qa.chain import QAChatChain
from retriever.vector_store import VectorStore
from utils.llm import get_llm_client
from utils.embeddings import EmbeddingModel
from utils.logger import logger
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from config import QDRANT_HOST, QDRANT_PORT, QDRANT_API_KEY, QDRANT_COLLECTION_NAME, QDRANT_USE_HTTPS
import hashlib
from datetime import datetime

# 导入后台管理路由和认证
from admin.routes import router as admin_router
from admin.auth import get_current_user
from admin.models import KnowledgeEntry
from admin.database import SessionLocal
from admin.usage_logger import log_llm_usage, estimate_tokens

# 导入 Agent 框架（可选）
AGENT_AVAILABLE = False
try:
    from agent import AgentConfig
    from agent.core import Agent
    from agent.tools import create_default_tool_registry, create_search_tool
    AGENT_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Agent 模块导入失败，相关功能将不可用: {e}")

app = FastAPI(title="RAG API", version="1.0.0")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册后台管理路由
app.include_router(admin_router)

# 静态文件目录
STATIC_DIR = Path(__file__).parent.parent / "static"
ADMIN_STATIC_DIR = Path(__file__).parent.parent / "admin_frontend" / "dist"

# 全局实例
qa_chain = None
vector_store = None
llm_client = None
embedding_model = None
qdrant_client = None
agent_instance = None  # Agent 实例
tool_registry = None   # 工具注册表


class AsyncLLMWrapper:
    """将同步 LLM 客户端包装为异步接口，供 Agent 使用"""

    def __init__(self, llm_client):
        self.llm = llm_client

    async def chat(self, prompt: str) -> dict:
        """异步 chat 方法"""
        import asyncio
        messages = [{"role": "user", "content": prompt}]
        # 在线程池中运行同步方法
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, self.llm.invoke, messages)
        return {"content": response, "usage": {}}


@app.on_event("startup")
async def startup_event():
    """启动时初始化"""
    global qa_chain, vector_store, llm_client, embedding_model, qdrant_client, agent_instance, tool_registry
    try:
        qa_chain = QAChatChain()
        vector_store = VectorStore()
        llm_client = get_llm_client()
        embedding_model = EmbeddingModel()

        # 初始化 Qdrant 客户端
        protocol = "https" if QDRANT_USE_HTTPS else "http"
        url = f"{protocol}://{QDRANT_HOST}:{QDRANT_PORT}"
        qdrant_client = QdrantClient(url=url, api_key=QDRANT_API_KEY if QDRANT_API_KEY else None)

        # 初始化 Agent 框架（如果可用）
        if AGENT_AVAILABLE:
            try:
                tool_registry = create_default_tool_registry(retriever=vector_store)
                tool_registry.register(create_search_tool(vector_store))
                async_llm = AsyncLLMWrapper(llm_client)
                agent_instance = Agent(async_llm, tool_registry, AgentConfig(max_iterations=5, verbose=True))
                logger.info("Agent 框架初始化成功")
            except Exception as agent_err:
                logger.warning(f"Agent 框架初始化失败（非致命）: {agent_err}")

        logger.info("RAG API 服务启动成功")
    except Exception as e:
        logger.error(f"RAG API 服务启动失败: {e}")
        raise


class QueryRequest(BaseModel):
    """查询请求"""
    question: str
    top_k: int = 5
    filters: Optional[Dict] = None
    group_ids: Optional[List[int]] = None  # 知识分组ID列表，只在指定分组中检索
    use_history: bool = True


class QueryResponse(BaseModel):
    """查询响应"""
    answer: str
    sources: List[Dict]
    retrieved_count: int
    from_cache: Optional[bool] = False
    highlights: Optional[Dict] = None  # 引用高亮信息


class SearchRequest(BaseModel):
    """搜索请求"""
    query: str
    top_k: int = 5
    filters: Optional[Dict] = None
    group_ids: Optional[List[int]] = None  # 知识分组ID列表，只在指定分组中检索
    score_threshold: float = 0.0


class AddKnowledgeRequest(BaseModel):
    """添加知识请求"""
    content: str
    title: Optional[str] = None
    category: Optional[str] = "general"  # 分类：project, skill, experience, note 等


class AddKnowledgeResponse(BaseModel):
    """添加知识响应"""
    success: bool
    message: str
    extracted_info: Optional[Dict] = None


@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest, http_request: Request, current_user = Depends(get_current_user)):
    """问答接口（需要登录）"""
    import time
    start_time = time.time()

    # 检测是否来自 MCP 客户端
    is_mcp = http_request.headers.get("X-MCP-Client") == "true"
    request_type = "mcp" if is_mcp else "query"

    try:
        result = qa_chain.query(
            question=request.question,
            top_k=request.top_k,
            filters=request.filters,
            group_ids=request.group_ids,
            use_history=request.use_history
        )

        # 记录审计日志
        total_time = time.time() - start_time
        answer_text = result.get("answer", "")
        log_llm_usage(
            request_type=request_type,
            question=request.question,
            answer=answer_text,
            user_id=current_user.id,
            username=current_user.username,
            prompt_tokens=estimate_tokens(request.question),
            completion_tokens=estimate_tokens(answer_text),
            total_tokens=estimate_tokens(request.question) + estimate_tokens(answer_text),
            total_time=total_time,
            retrieval_count=result.get("retrieved_count", 0),
            status="success",
            client_ip=http_request.client.host if http_request.client else None,
            user_agent=http_request.headers.get("User-Agent")
        )

        return QueryResponse(**result)
    except Exception as e:
        logger.error(f"查询失败: {e}")
        # 记录失败日志
        total_time = time.time() - start_time
        log_llm_usage(
            request_type=request_type,
            question=request.question,
            user_id=current_user.id,
            username=current_user.username,
            total_time=total_time,
            status="error",
            error_message=str(e),
            client_ip=http_request.client.host if http_request.client else None,
            user_agent=http_request.headers.get("User-Agent")
        )
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query/stream")
async def query_stream(request: QueryRequest, current_user = Depends(get_current_user)):
    """流式问答接口 (SSE)（需要登录）"""
    start_time = time.time()
    collected_answer = []

    def generate():
        nonlocal collected_answer
        try:
            for event in qa_chain.query_stream(
                question=request.question,
                top_k=request.top_k,
                filters=request.filters,
                group_ids=request.group_ids,
                use_history=request.use_history
            ):
                # 收集回答内容
                if event.get("type") == "answer":
                    collected_answer.append(event.get("data", ""))
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

            # 流结束后记录日志
            total_time = time.time() - start_time
            answer_text = "".join(collected_answer)
            log_llm_usage(
                request_type="query_stream",
                question=request.question,
                answer=answer_text,
                user_id=current_user.id,
                username=current_user.username,
                prompt_tokens=estimate_tokens(request.question),
                completion_tokens=estimate_tokens(answer_text),
                total_tokens=estimate_tokens(request.question) + estimate_tokens(answer_text),
                total_time=total_time,
                status="success"
            )
        except Exception as e:
            logger.error(f"流式查询失败: {e}")
            # 记录错误日志
            total_time = time.time() - start_time
            log_llm_usage(
                request_type="query_stream",
                question=request.question,
                user_id=current_user.id,
                username=current_user.username,
                total_time=total_time,
                status="error",
                error_message=str(e)
            )
            yield f"data: {json.dumps({'type': 'error', 'data': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # 禁用 Nginx 缓冲
        }
    )


@app.post("/search")
async def search(request: SearchRequest, http_request: Request, current_user = Depends(get_current_user)):
    """向量检索接口（需要登录）"""
    start_time = time.time()
    results = []

    # 检测是否来自 MCP 客户端
    is_mcp = http_request.headers.get("X-MCP-Client") == "true"
    request_type = "mcp" if is_mcp else "search"

    try:
        # 使用 qa_chain 的 retriever（HybridSearch）支持分组过滤
        results = qa_chain.retriever.search(
            query=request.query,
            top_k=request.top_k,
            filters=request.filters,
            group_ids=request.group_ids,
            use_hybrid=True
        )

        # 记录成功日志
        total_time = time.time() - start_time
        log_llm_usage(
            request_type=request_type,
            question=request.query,
            user_id=current_user.id,
            username=current_user.username,
            total_time=total_time,
            retrieval_count=len(results),
            status="success",
            client_ip=http_request.client.host if http_request.client else None,
            user_agent=http_request.headers.get("User-Agent")
        )

        return {"results": results, "count": len(results)}
    except Exception as e:
        logger.error(f"检索失败: {e}")
        # 记录错误日志
        total_time = time.time() - start_time
        log_llm_usage(
            request_type=request_type,
            question=request.query,
            user_id=current_user.id,
            username=current_user.username,
            total_time=total_time,
            status="error",
            error_message=str(e),
            client_ip=http_request.client.host if http_request.client else None,
            user_agent=http_request.headers.get("User-Agent")
        )
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/clear-history")
async def clear_history(current_user = Depends(get_current_user)):
    """清空对话历史（需要登录）"""
    try:
        qa_chain.clear_history()
        return {"message": "对话历史已清空"}
    except Exception as e:
        logger.error(f"清空历史失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class AgentRequest(BaseModel):
    """Agent 请求"""
    question: str
    context: Optional[str] = None
    max_iterations: int = 5


class AgentResponse(BaseModel):
    """Agent 响应"""
    success: bool
    answer: Optional[str] = None
    thought_process: List[Dict] = []
    iterations: int = 0
    error: Optional[str] = None


@app.post("/agent", response_model=AgentResponse)
async def agent_query(request: AgentRequest, current_user = Depends(get_current_user)):
    """
    Agent 智能问答接口（需要登录）

    使用 ReAct 模式的 Agent 进行多步推理，可以调用工具完成复杂任务。
    可用工具：
    - search: 搜索知识库
    - calculator: 数学计算
    - code_executor: 执行 Python 代码
    - datetime: 获取日期时间
    - json: JSON 处理
    """
    if agent_instance is None:
        raise HTTPException(status_code=503, detail="Agent 服务未初始化")

    start_time = time.time()
    try:
        # 更新 Agent 配置
        agent_instance.config.max_iterations = request.max_iterations

        # 执行 Agent
        result = await agent_instance.run(request.question, request.context)

        # 构建思考过程
        thought_process = []
        for ta in result.thought_actions:
            step = {"thought": ta.thought}
            if ta.action:
                step["action"] = ta.action
                step["action_input"] = ta.action_input
            if ta.observation:
                step["observation"] = ta.observation[:500] if len(ta.observation) > 500 else ta.observation
            thought_process.append(step)

        # 记录审计日志
        total_time = time.time() - start_time
        log_llm_usage(
            request_type="agent",
            question=request.question,
            answer=result.answer,
            user_id=current_user.id,
            username=current_user.username,
            prompt_tokens=estimate_tokens(request.question),
            completion_tokens=estimate_tokens(result.answer or ""),
            total_tokens=estimate_tokens(request.question) + estimate_tokens(result.answer or ""),
            total_time=total_time,
            status="success" if result.success else "error",
            error_message=result.error
        )

        return AgentResponse(
            success=result.success,
            answer=result.answer,
            thought_process=thought_process,
            iterations=result.iterations,
            error=result.error
        )

    except Exception as e:
        logger.error(f"Agent 执行失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/add_knowledge", response_model=AddKnowledgeResponse)
async def add_knowledge(request: AddKnowledgeRequest, http_request: Request, current_user = Depends(get_current_user)):
    """添加知识到知识库（需要登录）"""
    # 检测是否来自 MCP 客户端
    is_mcp = http_request.headers.get("X-MCP-Client") == "true"
    request_type = "mcp" if is_mcp else "add_knowledge"

    try:
        # 1. 用 LLM 提取关键信息
        extract_prompt = f"""请分析以下内容，提取关键信息并返回 JSON 格式：

内容：
{request.content}

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
        import json
        import re
        # 提取 JSON 部分
        json_match = re.search(r'\{[\s\S]*\}', llm_response)
        if json_match:
            extracted_info = json.loads(json_match.group())
        else:
            extracted_info = {
                "title": request.title or "未命名知识",
                "summary": request.content[:100],
                "keywords": [],
                "tech_stack": [],
                "type": request.category
            }

        # 2. 构建增强后的内容用于索引
        enhanced_content = f"""# {extracted_info.get('title', request.title or '知识条目')}

## 摘要
{extracted_info.get('summary', '')}

## 关键词
{', '.join(extracted_info.get('keywords', []))}

## 技术栈
{', '.join(extracted_info.get('tech_stack', []))}

## 详细内容
{request.content}
"""

        # 3. 生成嵌入向量
        embeddings = embedding_model.encode([enhanced_content])

        # 4. 生成唯一 ID
        content_hash = hashlib.md5(f"{request.content}:{datetime.now().isoformat()}".encode()).hexdigest()

        # 5. 存储到 Qdrant
        point = PointStruct(
            id=content_hash,
            vector=embeddings[0].tolist(),
            payload={
                "content": enhanced_content,
                "original_content": request.content,
                "title": extracted_info.get('title', request.title),
                "summary": extracted_info.get('summary', ''),
                "keywords": extracted_info.get('keywords', []),
                "tech_stack": extracted_info.get('tech_stack', []),
                "type": "knowledge",
                "category": extracted_info.get('type', request.category),
                "created_at": datetime.now().isoformat(),
                "file_path": f"knowledge/{content_hash[:8]}"
            }
        )

        qdrant_client.upsert(
            collection_name=QDRANT_COLLECTION_NAME,
            points=[point]
        )

        # 6. 同步写入 MySQL（双写 + 审计日志）
        try:
            with SessionLocal() as db:
                # 写入知识条目
                knowledge_entry = KnowledgeEntry(
                    qdrant_id=content_hash,
                    title=extracted_info.get('title', request.title),
                    category=extracted_info.get('type', request.category) or 'general',
                    summary=extracted_info.get('summary', ''),
                    keywords=extracted_info.get('keywords', []),
                    tech_stack=extracted_info.get('tech_stack', []),
                    content_preview=request.content[:500] if request.content else None
                )
                db.add(knowledge_entry)
                db.commit()

                # 写入审计日志（在 MySQL 事务成功后单独记录）
                log_llm_usage(
                    request_type=request_type,
                    question=f"添加知识: {extracted_info.get('title', '未命名')}",
                    answer=llm_response[:500] if llm_response else None,
                    user_id=current_user.id,
                    username=current_user.username,
                    prompt_tokens=estimate_tokens(extract_prompt),
                    completion_tokens=estimate_tokens(llm_response),
                    total_tokens=estimate_tokens(extract_prompt) + estimate_tokens(llm_response),
                    status="success",
                    client_ip=http_request.client.host if http_request.client else None,
                    user_agent=http_request.headers.get("User-Agent")
                )
                logger.info(f"知识条目已同步到 MySQL: {content_hash}")
        except Exception as mysql_err:
            logger.warning(f"MySQL 写入失败（Qdrant 已写入）: {mysql_err}")

        logger.info(f"添加知识成功: {extracted_info.get('title', '未命名')}")

        return AddKnowledgeResponse(
            success=True,
            message="知识添加成功！",
            extracted_info=extracted_info
        )

    except Exception as e:
        logger.error(f"添加知识失败: {e}")
        # 记录失败的审计日志
        log_llm_usage(
            request_type=request_type,
            question=f"添加知识失败: {request.title or '未命名'}",
            user_id=current_user.id if current_user else None,
            username=current_user.username if current_user else None,
            status="error",
            error_message=str(e),
            client_ip=http_request.client.host if http_request.client else None,
            user_agent=http_request.headers.get("User-Agent")
        )
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok", "service": "RAG API"}


@app.get("/")
async def root():
    """重定向到后台管理"""
    return RedirectResponse(url="/admin", status_code=302)


# Admin 前端路由（SPA，需要处理所有子路由）
@app.get("/admin")
@app.get("/admin/{path:path}")
async def admin_spa(path: str = ""):
    """返回 Admin 前端页面"""
    # 如果请求的是静态资源，让静态文件处理器处理
    if path.startswith("assets/"):
        return FileResponse(ADMIN_STATIC_DIR / path)
    # 否则返回 index.html（SPA 路由）
    return FileResponse(ADMIN_STATIC_DIR / "index.html")


# 挂载静态文件（放在最后，避免覆盖 API 路由）
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
