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
from admin.models import KnowledgeEntry, KnowledgeGroup, KnowledgeTask
from admin.database import SessionLocal
from admin.usage_logger import log_llm_usage, estimate_tokens

# 导入定时索引调度器
from utils.scheduler import get_scheduler, start_scheduler, stop_scheduler

# 导入任务队列
from utils.task_queue import get_task_queue, KnowledgeTaskPayload

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
async def startup_event() -> None:
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

        # 启动定时索引调度器
        try:
            start_scheduler()
        except Exception as scheduler_err:
            logger.warning(f"定时索引调度器启动失败（非致命）: {scheduler_err}")

        # 启动知识添加任务队列
        try:
            task_queue = get_task_queue(max_workers=3)
            task_queue.set_dependencies(
                llm_client=llm_client,
                embedding_model=embedding_model,
                qdrant_client=qdrant_client,
                collection_name=QDRANT_COLLECTION_NAME
            )
            await task_queue.start_workers()
            logger.info("知识添加任务队列启动成功")
        except Exception as queue_err:
            logger.warning(f"任务队列启动失败（非致命）: {queue_err}")

        logger.info("RAG API 服务启动成功")
    except Exception as e:
        logger.error(f"RAG API 服务启动失败: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """服务关闭时清理资源"""
    try:
        stop_scheduler()

        # 停止任务队列
        try:
            task_queue = get_task_queue()
            await task_queue.stop_workers()
            logger.info("知识添加任务队列已停止")
        except Exception as queue_err:
            logger.warning(f"停止任务队列时出错: {queue_err}")

        logger.info("RAG API 服务已关闭")
    except Exception as e:
        logger.error(f"关闭服务时出错: {e}")


class QueryRequest(BaseModel):
    """查询请求"""
    question: str
    top_k: int = 5
    filters: Optional[Dict] = None
    group_ids: Optional[List[int]] = None  # 知识分组ID列表，只在指定分组中检索
    group_names: Optional[List[str]] = None  # 知识分组名称列表（优先于group_ids）
    use_history: bool = True


class QueryResponse(BaseModel):
    """查询响应"""
    answer: str
    sources: List[Dict]
    retrieved_count: int
    from_cache: Optional[bool] = False
    highlights: Optional[Dict] = None  # 引用高亮信息
    usage: Optional[Dict] = None  # token 使用情况


class SearchRequest(BaseModel):
    """搜索请求"""
    query: str
    top_k: int = 5
    filters: Optional[Dict] = None
    group_ids: Optional[List[int]] = None  # 知识分组ID列表，只在指定分组中检索
    group_names: Optional[List[str]] = None  # 知识分组名称列表（优先于group_ids）
    score_threshold: float = 0.0


class AddKnowledgeRequest(BaseModel):
    """添加知识请求"""
    content: str
    title: Optional[str] = None
    category: Optional[str] = "general"  # 分类：project, skill, experience, note 等
    group_names: Optional[List[str]] = None  # 添加后自动加入这些分组


class AddKnowledgeResponse(BaseModel):
    """添加知识响应"""
    success: bool
    message: str
    task_id: Optional[str] = None  # 异步任务 ID
    status: Optional[str] = None   # pending/processing/completed/failed
    extracted_info: Optional[Dict] = None  # 同步模式才返回
    result_id: Optional[str] = None  # 成功后的 qdrant_id


def resolve_group_ids(group_ids: Optional[List[int]], group_names: Optional[List[str]]) -> Optional[List[int]]:
    """
    解析分组参数，group_names 优先于 group_ids
    返回有效的分组ID列表，如果分组不存在则忽略
    """
    if group_names:
        db = SessionLocal()
        try:
            groups = db.query(KnowledgeGroup).filter(
                KnowledgeGroup.name.in_(group_names),
                KnowledgeGroup.is_active == True
            ).all()
            if groups:
                return [g.id for g in groups]
            else:
                logger.warning(f"未找到匹配的分组: {group_names}")
                return None
        finally:
            db.close()
    return group_ids


@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest, http_request: Request, current_user = Depends(get_current_user)):
    """问答接口（需要登录）"""
    import time
    start_time = time.time()

    # 检测是否来自 MCP 客户端
    is_mcp = http_request.headers.get("X-MCP-Client") == "true"
    request_type = "mcp" if is_mcp else "query"

    # 解析分组参数（group_names 优先）
    effective_group_ids = resolve_group_ids(request.group_ids, request.group_names)

    try:
        result = qa_chain.query(
            question=request.question,
            top_k=request.top_k,
            filters=request.filters,
            group_ids=effective_group_ids,
            use_history=request.use_history
        )

        # 记录审计日志（使用上游返回的真实 token 数据）
        total_time = time.time() - start_time
        answer_text = result.get("answer", "")
        usage = result.get("usage", {})
        log_llm_usage(
            request_type=request_type,
            question=request.question,
            answer=answer_text,
            user_id=current_user.id,
            username=current_user.username,
            prompt_tokens=usage.get("input_tokens", 0),
            completion_tokens=usage.get("output_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
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

    # 解析分组参数（group_names 优先）
    effective_group_ids = resolve_group_ids(request.group_ids, request.group_names)

    def generate():
        nonlocal collected_answer
        try:
            for event in qa_chain.query_stream(
                question=request.question,
                top_k=request.top_k,
                filters=request.filters,
                group_ids=effective_group_ids,
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

    # 解析分组参数（group_names 优先）
    effective_group_ids = resolve_group_ids(request.group_ids, request.group_names)

    try:
        # 使用 qa_chain 的 retriever（HybridSearch）支持分组过滤
        results = qa_chain.retriever.search(
            query=request.query,
            top_k=request.top_k,
            filters=request.filters,
            group_ids=effective_group_ids,
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
    """添加知识到知识库（异步队列模式，需要登录）

    请求会立即返回 task_id，后台异步处理。
    使用 GET /add_knowledge/status/{task_id} 查询处理状态。
    """
    try:
        # 生成任务 ID
        task_id = hashlib.md5(
            f"{request.content}:{datetime.now().isoformat()}:{current_user.id}".encode()
        ).hexdigest()

        # 创建任务记录（状态：pending）
        with SessionLocal() as db:
            task = KnowledgeTask(
                id=task_id,
                status='pending',
                content=request.content,
                title=request.title,
                category=request.category or 'general',
                group_names=request.group_names,
                user_id=current_user.id,
                username=current_user.username
            )
            db.add(task)
            db.commit()

        # 构建任务载荷并入队
        payload = KnowledgeTaskPayload(
            task_id=task_id,
            content=request.content,
            title=request.title,
            category=request.category or 'general',
            group_names=request.group_names,
            user_id=current_user.id,
            username=current_user.username
        )

        task_queue = get_task_queue()
        await task_queue.enqueue(payload)

        logger.info(f"知识添加任务已入队: {task_id}")

        return AddKnowledgeResponse(
            success=True,
            message="任务已提交，正在后台处理",
            task_id=task_id,
            status="pending"
        )

    except Exception as e:
        logger.error(f"添加知识任务入队失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/add_knowledge/status/{task_id}", response_model=AddKnowledgeResponse)
async def get_add_knowledge_status(task_id: str, current_user = Depends(get_current_user)):
    """查询知识添加任务状态（需要登录）"""
    try:
        with SessionLocal() as db:
            task = db.query(KnowledgeTask).filter(KnowledgeTask.id == task_id).first()

            if not task:
                raise HTTPException(status_code=404, detail="任务不存在")

            # 权限检查：只能查看自己的任务（admin 可查看所有）
            if task.user_id != current_user.id and current_user.role != 'admin':
                raise HTTPException(status_code=403, detail="无权查看此任务")

            # 构建响应
            if task.status == 'completed':
                return AddKnowledgeResponse(
                    success=True,
                    message="知识添加成功！",
                    task_id=task_id,
                    status=task.status,
                    result_id=task.result_id
                )
            elif task.status == 'failed':
                return AddKnowledgeResponse(
                    success=False,
                    message=f"处理失败: {task.error_message}",
                    task_id=task_id,
                    status=task.status
                )
            else:
                return AddKnowledgeResponse(
                    success=True,
                    message=f"任务{task.status}中...",
                    task_id=task_id,
                    status=task.status
                )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询任务状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/add_knowledge/tasks")
async def list_add_knowledge_tasks(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    current_user = Depends(get_current_user)
):
    """列出用户的知识添加任务（需要登录）"""
    try:
        with SessionLocal() as db:
            query = db.query(KnowledgeTask)

            # 非管理员只能看自己的任务
            if current_user.role != 'admin':
                query = query.filter(KnowledgeTask.user_id == current_user.id)

            # 状态过滤
            if status:
                query = query.filter(KnowledgeTask.status == status)

            # 分页
            total = query.count()
            tasks = query.order_by(KnowledgeTask.created_at.desc()).offset(
                (page - 1) * page_size
            ).limit(page_size).all()

            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "tasks": [
                    {
                        "task_id": t.id,
                        "status": t.status,
                        "title": t.title,
                        "category": t.category,
                        "result_id": t.result_id,
                        "error_message": t.error_message,
                        "created_at": t.created_at.isoformat() if t.created_at else None,
                        "updated_at": t.updated_at.isoformat() if t.updated_at else None
                    }
                    for t in tasks
                ]
            }

    except Exception as e:
        logger.error(f"列出任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok", "service": "RAG API"}


# ===================== MCP 卡密验证 =====================

from admin.models import MCPApiKey

@app.post("/mcp/verify")
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


# ===================== 调度器管理 API =====================

@app.get("/admin/api/scheduler/status")
async def scheduler_status(current_user = Depends(get_current_user)):
    """
    获取定时索引调度器状态（需要登录）

    返回调度器的运行状态、配置信息和最近一次执行结果。
    """
    try:
        scheduler = get_scheduler()
        return scheduler.get_status()
    except Exception as e:
        logger.error(f"获取调度器状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/api/scheduler/trigger")
async def scheduler_trigger(current_user = Depends(get_current_user)):
    """
    手动触发一次增量索引（需要登录）

    立即执行一次增量索引任务，无需等待定时器。
    如果当前有索引任务正在执行，将返回错误。
    """
    try:
        scheduler = get_scheduler()
        result = scheduler.trigger_now()
        return result
    except Exception as e:
        logger.error(f"触发索引失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/api/scheduler/start")
async def scheduler_start(current_user = Depends(get_current_user)):
    """
    启动定时索引调度器（需要登录）

    如果调度器已在运行，将返回警告信息。
    """
    try:
        scheduler = get_scheduler()
        scheduler.start()
        return {"success": True, "message": "调度器已启动"}
    except Exception as e:
        logger.error(f"启动调度器失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/api/scheduler/stop")
async def scheduler_stop(current_user = Depends(get_current_user)):
    """
    停止定时索引调度器（需要登录）

    停止后需要手动启动才能恢复定时索引。
    """
    try:
        scheduler = get_scheduler()
        scheduler.stop()
        return {"success": True, "message": "调度器已停止"}
    except Exception as e:
        logger.error(f"停止调度器失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class UpdateIntervalRequest(BaseModel):
    """更新间隔请求"""
    minutes: int


@app.post("/admin/api/scheduler/interval")
async def scheduler_update_interval(
    request: UpdateIntervalRequest,
    current_user = Depends(get_current_user)
):
    """
    更新索引间隔时间（需要登录）

    动态调整定时索引的执行间隔，无需重启服务。

    Args:
        minutes: 新的间隔时间（分钟），必须 >= 1
    """
    if request.minutes < 1:
        raise HTTPException(status_code=400, detail="间隔必须大于等于 1 分钟")

    try:
        scheduler = get_scheduler()
        scheduler.update_interval(request.minutes)
        return {"success": True, "message": f"索引间隔已更新为 {request.minutes} 分钟"}
    except Exception as e:
        logger.error(f"更新索引间隔失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
