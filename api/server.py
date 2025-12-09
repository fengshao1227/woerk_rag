"""
FastAPI 服务
"""
from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
import sys
import json
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


@app.on_event("startup")
async def startup_event():
    """启动时初始化"""
    global qa_chain, vector_store, llm_client, embedding_model, qdrant_client
    try:
        qa_chain = QAChatChain()
        vector_store = VectorStore()
        llm_client = get_llm_client()
        embedding_model = EmbeddingModel()

        # 初始化 Qdrant 客户端
        protocol = "https" if QDRANT_USE_HTTPS else "http"
        url = f"{protocol}://{QDRANT_HOST}:{QDRANT_PORT}"
        qdrant_client = QdrantClient(url=url, api_key=QDRANT_API_KEY if QDRANT_API_KEY else None)

        logger.info("RAG API 服务启动成功")
    except Exception as e:
        logger.error(f"RAG API 服务启动失败: {e}")
        raise


class QueryRequest(BaseModel):
    """查询请求"""
    question: str
    top_k: int = 5
    filters: Optional[Dict] = None
    use_history: bool = True


class QueryResponse(BaseModel):
    """查询响应"""
    answer: str
    sources: List[Dict]
    retrieved_count: int


class SearchRequest(BaseModel):
    """搜索请求"""
    query: str
    top_k: int = 5
    filters: Optional[Dict] = None
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
async def query(request: QueryRequest, current_user: dict = Depends(get_current_user)):
    """问答接口（需要登录）"""
    try:
        result = qa_chain.query(
            question=request.question,
            top_k=request.top_k,
            filters=request.filters,
            use_history=request.use_history
        )
        return QueryResponse(**result)
    except Exception as e:
        logger.error(f"查询失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query/stream")
async def query_stream(request: QueryRequest, current_user: dict = Depends(get_current_user)):
    """流式问答接口 (SSE)（需要登录）"""
    def generate():
        try:
            for event in qa_chain.query_stream(
                question=request.question,
                top_k=request.top_k,
                filters=request.filters,
                use_history=request.use_history
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"流式查询失败: {e}")
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
async def search(request: SearchRequest, current_user: dict = Depends(get_current_user)):
    """向量检索接口（需要登录）"""
    try:
        results = vector_store.search(
            query=request.query,
            top_k=request.top_k,
            filters=request.filters,
            score_threshold=request.score_threshold
        )
        return {"results": results, "count": len(results)}
    except Exception as e:
        logger.error(f"检索失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/clear-history")
async def clear_history(current_user: dict = Depends(get_current_user)):
    """清空对话历史（需要登录）"""
    try:
        qa_chain.clear_history()
        return {"message": "对话历史已清空"}
    except Exception as e:
        logger.error(f"清空历史失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/add_knowledge", response_model=AddKnowledgeResponse)
async def add_knowledge(request: AddKnowledgeRequest, current_user: dict = Depends(get_current_user)):
    """添加知识到知识库（需要登录）"""
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

        logger.info(f"添加知识成功: {extracted_info.get('title', '未命名')}")

        return AddKnowledgeResponse(
            success=True,
            message="知识添加成功！",
            extracted_info=extracted_info
        )

    except Exception as e:
        logger.error(f"添加知识失败: {e}")
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
