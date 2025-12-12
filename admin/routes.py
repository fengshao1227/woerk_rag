"""
后台管理 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import timedelta

from admin.database import get_db
from admin.models import User, LLMProvider, LLMModel, KnowledgeEntry, LLMUsageLog, KnowledgeGroup, KnowledgeGroupItem, KnowledgeVersion, EmbeddingProvider, MCPApiKey, GroupShare
from admin.schemas import (
    LoginRequest, TokenResponse, UserResponse,
    ProviderCreate, ProviderUpdate, ProviderResponse,
    ModelCreate, ModelUpdate, ModelResponse,
    KnowledgeUpdate, KnowledgeResponse, KnowledgeListResponse, KnowledgeDetailResponse,
    MessageResponse, StatsResponse,
    UsageLogResponse, UsageStatsResponse, TestModelRequest, TestModelResponse,
    TestCaseCreate, TestCaseUpdate, TestCaseResponse,
    EvalRunRequest, EvalRunResponse, EvalSummaryResponse, EvalResultResponse,
    RetrievalMetrics, AnswerMetrics, CacheStatsResponse,
    KnowledgeGroupCreate, KnowledgeGroupUpdate, KnowledgeGroupResponse, KnowledgeGroupListResponse,
    GroupItemsRequest, GroupItemResponse,
    KnowledgeVersionResponse, KnowledgeVersionDetailResponse, KnowledgeVersionListResponse,
    RollbackRequest, RollbackResponse,
    RemoteModelItem, RemoteModelsResponse, BalanceResponse, BatchModelCreate, BatchModelResponse,
    EmbeddingProviderCreate, EmbeddingProviderUpdate, EmbeddingProviderResponse, TestEmbeddingRequest,
    MCPApiKeyCreate, MCPApiKeyUpdate, MCPApiKeyResponse, MCPApiKeyListResponse,
    GroupShareCreate, GroupShareUpdate, GroupShareResponse, GroupShareListResponse, UserSimpleResponse,
    UserCreate, UserUpdate, UserListResponse
)
from admin.auth import (
    authenticate_user, create_access_token, get_current_user,
    get_password_hash, ACCESS_TOKEN_EXPIRE_HOURS
)
import time
from datetime import datetime, timedelta
from utils.logger import logger

router = APIRouter(prefix="/admin/api", tags=["admin"])


# ============================================================
# 工具函数
# ============================================================
def mask_api_key(api_key: str) -> str:
    """脱敏 API Key"""
    if len(api_key) <= 8:
        return "****"
    return api_key[:4] + "****" + api_key[-4:]


# ============================================================
# 认证接口
# ============================================================
@router.post("/auth/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """用户登录"""
    user = authenticate_user(db, request.username, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )

    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    )

    return TokenResponse(
        access_token=access_token,
        user=UserResponse.model_validate(user)
    )


@router.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return UserResponse.model_validate(current_user)


@router.post("/auth/change-password", response_model=MessageResponse)
async def change_password(
    old_password: str,
    new_password: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """修改密码"""
    from admin.auth import verify_password
    if not verify_password(old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="原密码错误")

    current_user.password_hash = get_password_hash(new_password)
    db.commit()
    return MessageResponse(message="密码修改成功")


# ============================================================
# 仪表盘统计
# ============================================================
@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取统计数据"""
    total_knowledge = db.query(func.count(KnowledgeEntry.id)).scalar() or 0
    total_providers = db.query(func.count(LLMProvider.id)).scalar() or 0
    total_models = db.query(func.count(LLMModel.id)).scalar() or 0
    active_models = db.query(func.count(LLMModel.id)).filter(LLMModel.is_active == True).scalar() or 0

    # 按分类统计知识条目
    category_stats = db.query(
        KnowledgeEntry.category,
        func.count(KnowledgeEntry.id)
    ).group_by(KnowledgeEntry.category).all()

    categories = {cat: count for cat, count in category_stats}

    return StatsResponse(
        total_knowledge=total_knowledge,
        total_providers=total_providers,
        total_models=total_models,
        active_models=active_models,
        categories=categories
    )


# ============================================================
# 供应商管理
# ============================================================
@router.get("/providers", response_model=List[ProviderResponse])
async def list_providers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取供应商列表（使用子查询优化，避免 N+1 查询）"""
    # 子查询：统计每个供应商的模型数量
    models_count_subq = db.query(
        LLMModel.provider_id,
        func.count(LLMModel.id).label('models_count')
    ).group_by(LLMModel.provider_id).subquery()

    # 使用 LEFT JOIN 一次性获取所有数据
    rows = db.query(
        LLMProvider,
        func.coalesce(models_count_subq.c.models_count, 0).label('models_count')
    ).outerjoin(
        models_count_subq, LLMProvider.id == models_count_subq.c.provider_id
    ).order_by(LLMProvider.id.desc()).all()

    result = []
    for p, models_count in rows:
        result.append(ProviderResponse(
            id=p.id,
            name=p.name,
            api_format=p.api_format,
            api_key_masked=mask_api_key(p.api_key),
            base_url=p.base_url,
            is_active=p.is_active,
            is_default=p.is_default,
            request_timeout=p.request_timeout,
            max_concurrent=p.max_concurrent,
            monthly_budget=p.monthly_budget,
            current_usage=p.current_usage,
            created_at=p.created_at,
            updated_at=p.updated_at,
            models_count=models_count
        ))
    return result


@router.post("/providers", response_model=ProviderResponse)
async def create_provider(
    data: ProviderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建供应商"""
    # 如果设为默认，先取消其他默认
    if data.is_default:
        db.query(LLMProvider).update({LLMProvider.is_default: False})

    provider = LLMProvider(**data.model_dump())
    db.add(provider)
    db.commit()
    db.refresh(provider)

    return ProviderResponse(
        id=provider.id,
        name=provider.name,
        api_format=provider.api_format,
        api_key_masked=mask_api_key(provider.api_key),
        base_url=provider.base_url,
        is_active=provider.is_active,
        is_default=provider.is_default,
        request_timeout=provider.request_timeout,
        max_concurrent=provider.max_concurrent,
        monthly_budget=provider.monthly_budget,
        current_usage=provider.current_usage,
        created_at=provider.created_at,
        updated_at=provider.updated_at,
        models_count=0
    )


@router.get("/providers/{provider_id}", response_model=ProviderResponse)
async def get_provider(
    provider_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取供应商详情"""
    provider = db.query(LLMProvider).filter(LLMProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="供应商不存在")

    models_count = db.query(func.count(LLMModel.id)).filter(LLMModel.provider_id == provider.id).scalar() or 0

    return ProviderResponse(
        id=provider.id,
        name=provider.name,
        api_format=provider.api_format,
        api_key_masked=mask_api_key(provider.api_key),
        base_url=provider.base_url,
        is_active=provider.is_active,
        is_default=provider.is_default,
        request_timeout=provider.request_timeout,
        max_concurrent=provider.max_concurrent,
        monthly_budget=provider.monthly_budget,
        current_usage=provider.current_usage,
        created_at=provider.created_at,
        updated_at=provider.updated_at,
        models_count=models_count
    )


@router.put("/providers/{provider_id}", response_model=ProviderResponse)
async def update_provider(
    provider_id: int,
    data: ProviderUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新供应商"""
    provider = db.query(LLMProvider).filter(LLMProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="供应商不存在")

    update_data = data.model_dump(exclude_unset=True)

    # 如果设为默认，先取消其他默认
    if update_data.get("is_default"):
        db.query(LLMProvider).filter(LLMProvider.id != provider_id).update({LLMProvider.is_default: False})

    for key, value in update_data.items():
        setattr(provider, key, value)

    db.commit()
    db.refresh(provider)

    models_count = db.query(func.count(LLMModel.id)).filter(LLMModel.provider_id == provider.id).scalar() or 0

    return ProviderResponse(
        id=provider.id,
        name=provider.name,
        api_format=provider.api_format,
        api_key_masked=mask_api_key(provider.api_key),
        base_url=provider.base_url,
        is_active=provider.is_active,
        is_default=provider.is_default,
        request_timeout=provider.request_timeout,
        max_concurrent=provider.max_concurrent,
        monthly_budget=provider.monthly_budget,
        current_usage=provider.current_usage,
        created_at=provider.created_at,
        updated_at=provider.updated_at,
        models_count=models_count
    )


@router.delete("/providers/{provider_id}", response_model=MessageResponse)
async def delete_provider(
    provider_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除供应商"""
    provider = db.query(LLMProvider).filter(LLMProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="供应商不存在")

    db.delete(provider)
    db.commit()
    return MessageResponse(message="供应商已删除")


@router.get("/providers/{provider_id}/remote-models", response_model=RemoteModelsResponse)
async def get_remote_models(
    provider_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取供应商的远程模型列表（仅支持 OpenAI 格式）"""
    import httpx

    provider = db.query(LLMProvider).filter(LLMProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="供应商不存在")

    if provider.api_format != "openai":
        raise HTTPException(status_code=400, detail="仅支持 OpenAI 格式的供应商获取模型列表")

    # 构建 API URL
    base_url = provider.base_url.rstrip('/') if provider.base_url else "https://api.openai.com"
    models_url = f"{base_url}/v1/models"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                models_url,
                headers={"Authorization": f"Bearer {provider.api_key}"}
            )
            response.raise_for_status()
            data = response.json()

            # 解析模型列表
            models = []
            raw_models = data.get("data", [])
            for m in raw_models:
                models.append(RemoteModelItem(
                    id=m.get("id", ""),
                    object=m.get("object", "model"),
                    created=m.get("created"),
                    owned_by=m.get("owned_by")
                ))

            # 按模型ID排序
            models.sort(key=lambda x: x.id)

            return RemoteModelsResponse(
                models=models,
                total=len(models),
                provider_id=provider.id,
                provider_name=provider.name
            )
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"获取模型列表失败: {e.response.text[:200]}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取模型列表失败: {str(e)}")


@router.get("/providers/{provider_id}/balance", response_model=BalanceResponse)
async def get_provider_balance(
    provider_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取供应商余额（仅支持 OpenAI 格式，兼容多种中转服务）"""
    import httpx

    provider = db.query(LLMProvider).filter(LLMProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="供应商不存在")

    if provider.api_format != "openai":
        return BalanceResponse(error="仅支持 OpenAI 格式的供应商查询余额")

    base_url = provider.base_url.rstrip('/') if provider.base_url else "https://api.openai.com"
    headers = {"Authorization": f"Bearer {provider.api_key}"}

    # 尝试多种余额接口（兼容不同的中转服务）
    balance_endpoints = [
        "/v1/dashboard/billing/subscription",
        "/dashboard/billing/subscription",
        "/v1/dashboard/billing/credit_grants",
        "/dashboard/billing/credit_grants",
    ]

    async with httpx.AsyncClient(timeout=15.0) as client:
        for endpoint in balance_endpoints:
            try:
                url = f"{base_url}{endpoint}"
                response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    data = response.json()

                    # 解析不同格式的响应
                    balance = None
                    used = None
                    total = None
                    expires_at = None

                    # subscription 格式
                    if "hard_limit_usd" in data:
                        total = data.get("hard_limit_usd")
                        used = data.get("soft_limit_usd", 0)
                        balance = total - used if total else None
                    # credit_grants 格式
                    elif "total_granted" in data:
                        total = data.get("total_granted")
                        used = data.get("total_used")
                        balance = data.get("total_available")
                        grants = data.get("grants", {}).get("data", [])
                        if grants:
                            expires_at = grants[0].get("expires_at")
                            if expires_at:
                                from datetime import datetime
                                expires_at = datetime.fromtimestamp(expires_at).isoformat()
                    # 通用格式（一些中转服务）
                    elif "balance" in data:
                        balance = data.get("balance")
                        used = data.get("used", data.get("usage"))
                        total = data.get("total", data.get("limit"))

                    return BalanceResponse(
                        balance=balance,
                        used=used,
                        total=total,
                        expires_at=expires_at,
                        raw_response=data
                    )
            except Exception:
                continue

        # 所有端点都失败
        return BalanceResponse(error="无法获取余额信息，该供应商可能不支持余额查询接口")


@router.post("/providers/{provider_id}/models/batch", response_model=BatchModelResponse)
async def batch_create_models(
    provider_id: int,
    data: BatchModelCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """批量创建模型"""
    provider = db.query(LLMProvider).filter(LLMProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="供应商不存在")

    # 获取该供应商下已存在的模型ID
    existing_model_ids = set(
        m.model_id for m in db.query(LLMModel.model_id).filter(LLMModel.provider_id == provider_id).all()
    )

    created_count = 0
    skipped_count = 0
    skipped_models = []

    for model_item in data.models:
        if model_item.model_id in existing_model_ids:
            skipped_count += 1
            skipped_models.append(model_item.model_id)
            continue

        new_model = LLMModel(
            provider_id=provider_id,
            model_id=model_item.model_id,
            display_name=model_item.display_name,
            temperature=model_item.temperature,
            max_tokens=model_item.max_tokens,
            is_active=True,
            is_default=False
        )
        db.add(new_model)
        created_count += 1

    db.commit()

    return BatchModelResponse(
        success=True,
        created_count=created_count,
        skipped_count=skipped_count,
        skipped_models=skipped_models,
        message=f"成功添加 {created_count} 个模型" + (f"，跳过 {skipped_count} 个已存在的模型" if skipped_count > 0 else "")
    )


# ============================================================
# 模型管理
# ============================================================
@router.get("/models", response_model=List[ModelResponse])
async def list_models(
    provider_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取模型列表（使用 JOIN 优化，避免 N+1 查询）"""
    # 使用 LEFT JOIN 一次性获取模型和供应商名称
    query = db.query(
        LLMModel,
        LLMProvider.name.label('provider_name')
    ).outerjoin(
        LLMProvider, LLMModel.provider_id == LLMProvider.id
    )

    if provider_id:
        query = query.filter(LLMModel.provider_id == provider_id)

    rows = query.order_by(LLMModel.id.desc()).all()

    result = []
    for m, provider_name in rows:
        result.append(ModelResponse(
            id=m.id,
            provider_id=m.provider_id,
            provider_name=provider_name or "",
            model_id=m.model_id,
            display_name=m.display_name,
            temperature=float(m.temperature),
            max_tokens=m.max_tokens,
            system_prompt=m.system_prompt,
            is_active=m.is_active,
            is_default=m.is_default,
            created_at=m.created_at,
            updated_at=m.updated_at
        ))
    return result


@router.post("/models", response_model=ModelResponse)
async def create_model(
    data: ModelCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建模型"""
    # 验证供应商存在
    provider = db.query(LLMProvider).filter(LLMProvider.id == data.provider_id).first()
    if not provider:
        raise HTTPException(status_code=400, detail="供应商不存在")

    # 如果设为默认，先取消其他默认
    if data.is_default:
        db.query(LLMModel).update({LLMModel.is_default: False})

    model = LLMModel(**data.model_dump())
    db.add(model)
    db.commit()
    db.refresh(model)

    return ModelResponse(
        id=model.id,
        provider_id=model.provider_id,
        provider_name=provider.name,
        model_id=model.model_id,
        display_name=model.display_name,
        temperature=float(model.temperature),
        max_tokens=model.max_tokens,
        system_prompt=model.system_prompt,
        is_active=model.is_active,
        is_default=model.is_default,
        created_at=model.created_at,
        updated_at=model.updated_at
    )


@router.get("/models/{model_id}", response_model=ModelResponse)
async def get_model(
    model_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取模型详情"""
    model = db.query(LLMModel).filter(LLMModel.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")

    provider = db.query(LLMProvider).filter(LLMProvider.id == model.provider_id).first()

    return ModelResponse(
        id=model.id,
        provider_id=model.provider_id,
        provider_name=provider.name if provider else "",
        model_id=model.model_id,
        display_name=model.display_name,
        temperature=float(model.temperature),
        max_tokens=model.max_tokens,
        system_prompt=model.system_prompt,
        is_active=model.is_active,
        is_default=model.is_default,
        created_at=model.created_at,
        updated_at=model.updated_at
    )


@router.put("/models/{model_id}", response_model=ModelResponse)
async def update_model(
    model_id: int,
    data: ModelUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新模型"""
    model = db.query(LLMModel).filter(LLMModel.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")

    update_data = data.model_dump(exclude_unset=True)

    # 如果设为默认，先取消其他默认
    if update_data.get("is_default"):
        db.query(LLMModel).filter(LLMModel.id != model_id).update({LLMModel.is_default: False})

    for key, value in update_data.items():
        setattr(model, key, value)

    db.commit()
    db.refresh(model)

    provider = db.query(LLMProvider).filter(LLMProvider.id == model.provider_id).first()

    return ModelResponse(
        id=model.id,
        provider_id=model.provider_id,
        provider_name=provider.name if provider else "",
        model_id=model.model_id,
        display_name=model.display_name,
        temperature=float(model.temperature),
        max_tokens=model.max_tokens,
        system_prompt=model.system_prompt,
        is_active=model.is_active,
        is_default=model.is_default,
        created_at=model.created_at,
        updated_at=model.updated_at
    )


@router.delete("/models/{model_id}", response_model=MessageResponse)
async def delete_model(
    model_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除模型"""
    model = db.query(LLMModel).filter(LLMModel.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")

    db.delete(model)
    db.commit()
    return MessageResponse(message="模型已删除")


@router.post("/models/{model_id}/set-default", response_model=MessageResponse)
async def set_default_model(
    model_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """设置默认模型"""
    model = db.query(LLMModel).filter(LLMModel.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")

    # 取消其他默认
    db.query(LLMModel).update({LLMModel.is_default: False})
    model.is_default = True
    db.commit()

    return MessageResponse(message=f"已将 {model.display_name} 设为默认模型")


# ============================================================
# 知识库管理
# ============================================================
@router.get("/knowledge", response_model=KnowledgeListResponse)
async def list_knowledge(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    search: Optional[str] = None,
    group_id: Optional[int] = Query(None, description="分组ID，0表示未分组，不传表示全部"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取知识条目列表，支持按分组筛选和用户权限过滤

    权限规则（知识可见性由分组决定）：
    1. 管理员可看全部
    2. 普通用户可看：
       - 自己创建的分组中的知识
       - 公开分组中的知识
       - 共享给自己的分组中的知识
       - 自己创建的未分组知识
    """
    from sqlalchemy import or_, and_

    query = db.query(KnowledgeEntry)

    # 用户权限过滤
    if current_user.role != "admin":
        # 1. 获取用户自己创建的分组ID
        my_group_ids = db.query(KnowledgeGroup.id).filter(
            KnowledgeGroup.user_id == current_user.id
        ).all()
        my_group_ids = [g[0] for g in my_group_ids]

        # 2. 获取公开分组ID
        public_group_ids = db.query(KnowledgeGroup.id).filter(
            KnowledgeGroup.is_public == True
        ).all()
        public_group_ids = [g[0] for g in public_group_ids]

        # 3. 获取共享给当前用户的分组ID
        shared_group_ids = db.query(GroupShare.group_id).filter(
            GroupShare.shared_with_user_id == current_user.id
        ).all()
        shared_group_ids = [g[0] for g in shared_group_ids]

        # 合并所有可访问的分组ID
        accessible_group_ids = list(set(my_group_ids + public_group_ids + shared_group_ids))

        # 4. 获取这些分组中的知识 qdrant_id
        accessible_qdrant_ids = []
        if accessible_group_ids:
            items = db.query(KnowledgeGroupItem.qdrant_id).filter(
                KnowledgeGroupItem.group_id.in_(accessible_group_ids)
            ).all()
            accessible_qdrant_ids = [item[0] for item in items]

        # 5. 获取所有已分组的 qdrant_id（用于判断未分组知识）
        all_grouped_qdrant_ids = db.query(KnowledgeGroupItem.qdrant_id).distinct().all()
        all_grouped_qdrant_ids = [item[0] for item in all_grouped_qdrant_ids]

        # 过滤条件：在可访问分组中 OR (未分组且是自己创建的)
        if accessible_qdrant_ids:
            query = query.filter(
                or_(
                    KnowledgeEntry.qdrant_id.in_(accessible_qdrant_ids),
                    and_(
                        ~KnowledgeEntry.qdrant_id.in_(all_grouped_qdrant_ids) if all_grouped_qdrant_ids else True,
                        KnowledgeEntry.user_id == current_user.id
                    )
                )
            )
        else:
            # 没有可访问分组，只能看自己创建的未分组知识
            if all_grouped_qdrant_ids:
                query = query.filter(
                    and_(
                        ~KnowledgeEntry.qdrant_id.in_(all_grouped_qdrant_ids),
                        KnowledgeEntry.user_id == current_user.id
                    )
                )
            else:
                query = query.filter(KnowledgeEntry.user_id == current_user.id)

    # 分组筛选
    if group_id is not None:
        if group_id == 0:
            # 未分组：查找所有不在 KnowledgeGroupItem 中的知识
            grouped_qdrant_ids = db.query(KnowledgeGroupItem.qdrant_id).distinct().subquery()
            query = query.filter(~KnowledgeEntry.qdrant_id.in_(grouped_qdrant_ids))
        else:
            # 指定分组：查找在该分组中的知识
            group_qdrant_ids = db.query(KnowledgeGroupItem.qdrant_id).filter(
                KnowledgeGroupItem.group_id == group_id
            ).subquery()
            query = query.filter(KnowledgeEntry.qdrant_id.in_(group_qdrant_ids))

    if category:
        query = query.filter(KnowledgeEntry.category == category)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (KnowledgeEntry.title.like(search_term)) |
            (KnowledgeEntry.summary.like(search_term)) |
            (KnowledgeEntry.content_preview.like(search_term))
        )

    total = query.count()
    total_pages = (total + page_size - 1) // page_size

    items = query.order_by(KnowledgeEntry.created_at.desc()) \
        .offset((page - 1) * page_size) \
        .limit(page_size) \
        .all()

    # 构建响应，添加 username 字段和 groups 字段
    # 批量获取所有知识的分组信息
    item_qdrant_ids = [item.qdrant_id for item in items if item.qdrant_id]
    qdrant_to_groups = {}
    qdrant_to_group_ids = {}  # qdrant_id -> [group_id, ...]
    if item_qdrant_ids:
        group_items = db.query(KnowledgeGroupItem).filter(
            KnowledgeGroupItem.qdrant_id.in_(item_qdrant_ids)
        ).all()
        group_ids = list(set([gi.group_id for gi in group_items]))
        groups_map = {}
        if group_ids:
            groups = db.query(KnowledgeGroup).filter(KnowledgeGroup.id.in_(group_ids)).all()
            for g in groups:
                groups_map[g.id] = {"id": g.id, "name": g.name, "is_public": g.is_public, "user_id": g.user_id}
        for gi in group_items:
            if gi.qdrant_id not in qdrant_to_groups:
                qdrant_to_groups[gi.qdrant_id] = []
                qdrant_to_group_ids[gi.qdrant_id] = []
            if gi.group_id in groups_map:
                qdrant_to_groups[gi.qdrant_id].append(groups_map[gi.group_id])
                qdrant_to_group_ids[gi.qdrant_id].append(gi.group_id)

    # 获取当前用户有 write 权限的共享分组
    user_write_group_ids = set()
    if current_user.role != "admin":
        shared_writes = db.query(GroupShare.group_id).filter(
            GroupShare.shared_with_user_id == current_user.id,
            GroupShare.permission == 'write'
        ).all()
        user_write_group_ids = {s[0] for s in shared_writes}

    knowledge_items = []
    for item in items:
        # 获取该知识所属的分组列表
        item_groups = qdrant_to_groups.get(item.qdrant_id, [])
        item_group_ids = qdrant_to_group_ids.get(item.qdrant_id, [])

        # 判断用户是否可以编辑该知识
        # 规则：管理员可编辑所有，普通用户可编辑：1.自己创建的 2.自己分组内的 3.有write权限的共享分组内的
        can_edit = False
        if current_user.role == "admin":
            can_edit = True
        elif item.user_id == current_user.id:
            # 自己创建的知识
            can_edit = True
        else:
            # 检查知识所属分组：用户自己的分组 或 有 write 权限的共享分组
            for grp in item_groups:
                if grp.get("user_id") == current_user.id:
                    can_edit = True
                    break
            if not can_edit:
                for gid in item_group_ids:
                    if gid in user_write_group_ids:
                        can_edit = True
                        break

        item_dict = {
            "id": item.id,
            "qdrant_id": item.qdrant_id,
            "title": item.title,
            "category": item.category,
            "summary": item.summary,
            "keywords": item.keywords,
            "tech_stack": item.tech_stack,
            "content_preview": item.content_preview,
            "user_id": item.user_id,
            "is_public": item.is_public if item.is_public is not None else True,
            "username": item.user.username if item.user else None,
            "groups": item_groups,  # 新增：分组列表
            "can_edit": can_edit,  # 新增：是否可编辑
            "created_at": item.created_at,
            "updated_at": item.updated_at
        }
        knowledge_items.append(KnowledgeResponse(**item_dict))

    return KnowledgeListResponse(
        items=knowledge_items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/knowledge/{knowledge_id}", response_model=KnowledgeDetailResponse)
async def get_knowledge(
    knowledge_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取知识条目详情（包含完整内容）"""
    entry = db.query(KnowledgeEntry).filter(KnowledgeEntry.id == knowledge_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="知识条目不存在")

    # 从 Qdrant 获取完整内容
    content = None
    try:
        from qdrant_client import QdrantClient
        from config import QDRANT_HOST, QDRANT_PORT, QDRANT_API_KEY, QDRANT_COLLECTION_NAME, QDRANT_USE_HTTPS

        protocol = "https" if QDRANT_USE_HTTPS else "http"
        url = f"{protocol}://{QDRANT_HOST}:{QDRANT_PORT}"
        client = QdrantClient(url=url, api_key=QDRANT_API_KEY if QDRANT_API_KEY else None)

        # 通过 qdrant_id 获取完整内容
        points = client.retrieve(
            collection_name=QDRANT_COLLECTION_NAME,
            ids=[entry.qdrant_id],
            with_payload=True,
            with_vectors=False
        )
        if points:
            content = points[0].payload.get('content') or points[0].payload.get('original_content')
    except Exception as e:
        # 获取失败时使用 content_preview
        content = entry.content_preview

    return KnowledgeDetailResponse(
        id=entry.id,
        qdrant_id=entry.qdrant_id,
        title=entry.title,
        category=entry.category,
        summary=entry.summary,
        keywords=entry.keywords,
        tech_stack=entry.tech_stack,
        content=content,
        content_preview=entry.content_preview,
        created_at=entry.created_at,
        updated_at=entry.updated_at
    )


@router.put("/knowledge/{knowledge_id}", response_model=KnowledgeResponse)
async def update_knowledge(
    knowledge_id: int,
    data: KnowledgeUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新知识条目元数据，需要权限检查"""
    entry = db.query(KnowledgeEntry).filter(KnowledgeEntry.id == knowledge_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="知识条目不存在")

    # 权限检查：管理员可修改所有，普通用户只能修改自己的
    if current_user.role != "admin" and entry.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权修改他人的知识条目")

    # 更新前先保存旧状态用于版本追踪
    old_metadata = {
        "title": entry.title,
        "category": entry.category,
        "summary": entry.summary,
        "keywords": entry.keywords,
        "tech_stack": entry.tech_stack
    }

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(entry, key, value)

    db.commit()
    db.refresh(entry)

    # 创建版本记录
    try:
        from utils.version_tracker import track_knowledge_change
        new_metadata = {
            "title": entry.title,
            "category": entry.category,
            "summary": entry.summary,
            "keywords": entry.keywords,
            "tech_stack": entry.tech_stack
        }
        track_knowledge_change(
            qdrant_id=entry.qdrant_id,
            content=entry.content_preview or "",
            metadata=new_metadata,
            change_type="update",
            user=current_user.username,
            reason=f"更新元数据: {list(update_data.keys())}"
        )
    except Exception as e:
        logger.warning(f"版本追踪失败: {e}")

    return KnowledgeResponse.model_validate(entry)


@router.delete("/knowledge/{knowledge_id}", response_model=MessageResponse)
async def delete_knowledge(
    knowledge_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除知识条目（级联删除 MySQL + Qdrant），需要权限检查"""
    entry = db.query(KnowledgeEntry).filter(KnowledgeEntry.id == knowledge_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="知识条目不存在")

    # 权限检查：管理员可删除所有，普通用户只能删除自己的
    if current_user.role != "admin" and entry.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权删除他人的知识条目")

    qdrant_id = entry.qdrant_id

    # 0. 创建删除版本记录（用于可能的恢复）
    try:
        from utils.version_tracker import track_knowledge_change
        metadata = {
            "title": entry.title,
            "category": entry.category,
            "summary": entry.summary,
            "keywords": entry.keywords,
            "tech_stack": entry.tech_stack
        }
        track_knowledge_change(
            qdrant_id=qdrant_id,
            content=entry.content_preview or "",
            metadata=metadata,
            change_type="delete",
            user=current_user.username,
            reason="删除知识条目"
        )
    except Exception as e:
        logger.warning(f"版本追踪失败: {e}")

    # 1. 从 Qdrant 删除向量
    qdrant_delete_failed = False
    try:
        from qdrant_client import QdrantClient
        from config import QDRANT_HOST, QDRANT_PORT, QDRANT_API_KEY, QDRANT_COLLECTION_NAME

        client = QdrantClient(
            host=QDRANT_HOST,
            port=QDRANT_PORT,
            api_key=QDRANT_API_KEY if QDRANT_API_KEY else None
        )

        # 按 qdrant_id 删除
        client.delete(
            collection_name=QDRANT_COLLECTION_NAME,
            points_selector={"points": [qdrant_id]}
        )
        logger.info(f"已从 Qdrant 删除向量: {qdrant_id}")
    except Exception as e:
        logger.error(f"从 Qdrant 删除向量失败: {e}")
        qdrant_delete_failed = True

    # 2. 从 MySQL 删除
    db.delete(entry)
    db.commit()

    # 返回适当的消息
    if qdrant_delete_failed:
        return MessageResponse(message="知识条目已从索引删除，但向量数据删除失败（可能需要手动清理）")
    return MessageResponse(message="知识条目已删除")


@router.get("/knowledge/export/all")
async def export_knowledge(
    category: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """导出知识条目"""
    query = db.query(KnowledgeEntry)
    if category:
        query = query.filter(KnowledgeEntry.category == category)

    entries = query.all()

    return {
        "count": len(entries),
        "entries": [
            {
                "qdrant_id": e.qdrant_id,
                "title": e.title,
                "category": e.category,
                "summary": e.summary,
                "keywords": e.keywords,
                "tech_stack": e.tech_stack,
                "content_preview": e.content_preview,
                "created_at": e.created_at.isoformat() if e.created_at else None
            }
            for e in entries
        ]
    }

# ============================================================
# LLM使用量统计
# ============================================================
@router.get("/usage/logs", response_model=List[UsageLogResponse])
async def list_usage_logs(
    model_id: Optional[int] = None,
    provider_id: Optional[int] = None,
    status: Optional[str] = None,
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取使用记录列表（使用 JOIN 优化，避免 N+1 查询）"""
    # 使用 LEFT JOIN 一次性获取所有数据，避免 N+1 查询问题
    query = db.query(
        LLMUsageLog,
        LLMModel.display_name.label('model_name'),
        LLMProvider.name.label('provider_name')
    ).outerjoin(
        LLMModel, LLMUsageLog.model_id == LLMModel.id
    ).outerjoin(
        LLMProvider, LLMUsageLog.provider_id == LLMProvider.id
    )

    # 时间过滤
    start_date = datetime.now() - timedelta(days=days)
    query = query.filter(LLMUsageLog.created_at >= start_date)

    if model_id:
        query = query.filter(LLMUsageLog.model_id == model_id)
    if provider_id:
        query = query.filter(LLMUsageLog.provider_id == provider_id)
    if status:
        query = query.filter(LLMUsageLog.status == status)

    rows = query.order_by(LLMUsageLog.created_at.desc()).limit(limit).all()

    result = []
    for log, model_name, provider_name in rows:
        result.append(UsageLogResponse(
            id=log.id,
            model_id=log.model_id,
            model_name=model_name or "",
            provider_id=log.provider_id,
            provider_name=provider_name or "",
            prompt_tokens=log.prompt_tokens or 0,
            completion_tokens=log.completion_tokens or 0,
            total_tokens=log.total_tokens or 0,
            cost=float(log.cost) if log.cost else 0,
            request_time=float(log.request_time) if log.request_time else 0,
            status=log.status or "success",
            error_message=log.error_message,
            created_at=log.created_at
        ))

    return result


@router.get("/usage/stats", response_model=UsageStatsResponse)
async def get_usage_stats(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取使用统计"""
    start_date = datetime.now() - timedelta(days=days)
    
    # 总体统计
    total_requests = db.query(func.count(LLMUsageLog.id)).filter(
        LLMUsageLog.created_at >= start_date
    ).scalar() or 0
    
    success_requests = db.query(func.count(LLMUsageLog.id)).filter(
        LLMUsageLog.created_at >= start_date,
        LLMUsageLog.status == 'success'
    ).scalar() or 0
    
    error_requests = total_requests - success_requests
    
    total_tokens = db.query(func.sum(LLMUsageLog.total_tokens)).filter(
        LLMUsageLog.created_at >= start_date
    ).scalar() or 0
    
    total_cost = db.query(func.sum(LLMUsageLog.cost)).filter(
        LLMUsageLog.created_at >= start_date
    ).scalar() or 0
    
    avg_request_time = db.query(func.avg(LLMUsageLog.request_time)).filter(
        LLMUsageLog.created_at >= start_date,
        LLMUsageLog.status == 'success'
    ).scalar() or 0
    
    # 按模型统计
    by_model = db.query(
        LLMModel.display_name,
        func.count(LLMUsageLog.id).label('count'),
        func.sum(LLMUsageLog.total_tokens).label('tokens'),
        func.sum(LLMUsageLog.cost).label('cost')
    ).join(LLMModel, LLMUsageLog.model_id == LLMModel.id).filter(
        LLMUsageLog.created_at >= start_date
    ).group_by(LLMModel.display_name).all()
    
    by_model_list = [
        {"name": name, "count": count, "tokens": int(tokens or 0), "cost": float(cost or 0)}
        for name, count, tokens, cost in by_model
    ]
    
    # 按供应商统计
    by_provider = db.query(
        LLMProvider.name,
        func.count(LLMUsageLog.id).label('count'),
        func.sum(LLMUsageLog.total_tokens).label('tokens'),
        func.sum(LLMUsageLog.cost).label('cost')
    ).join(LLMProvider, LLMUsageLog.provider_id == LLMProvider.id).filter(
        LLMUsageLog.created_at >= start_date
    ).group_by(LLMProvider.name).all()
    
    by_provider_list = [
        {"name": name, "count": count, "tokens": int(tokens or 0), "cost": float(cost or 0)}
        for name, count, tokens, cost in by_provider
    ]
    
    # 按天统计
    daily_stats = db.query(
        func.date(LLMUsageLog.created_at).label('date'),
        func.count(LLMUsageLog.id).label('count'),
        func.sum(LLMUsageLog.total_tokens).label('tokens'),
        func.sum(LLMUsageLog.cost).label('cost')
    ).filter(
        LLMUsageLog.created_at >= start_date
    ).group_by(func.date(LLMUsageLog.created_at)).order_by('date').all()
    
    daily_stats_list = [
        {"date": str(date), "count": count, "tokens": int(tokens or 0), "cost": float(cost or 0)}
        for date, count, tokens, cost in daily_stats
    ]
    
    return UsageStatsResponse(
        total_requests=total_requests,
        success_requests=success_requests,
        error_requests=error_requests,
        total_tokens=int(total_tokens),
        total_cost=float(total_cost),
        avg_request_time=float(avg_request_time),
        by_model=by_model_list,
        by_provider=by_provider_list,
        daily_stats=daily_stats_list
    )


# ============================================================
# 模型测试
# ============================================================
@router.post("/models/test", response_model=TestModelResponse)
async def test_model(
    request: TestModelRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """测试模型"""
    model = db.query(LLMModel).filter(LLMModel.id == request.model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")
    
    provider = db.query(LLMProvider).filter(LLMProvider.id == model.provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="供应商不存在")
    
    start_time = time.time()
    
    try:
        # 动态导入LLM客户端
        if provider.api_format == "anthropic":
            from utils.llm import AnthropicLLM
            llm = AnthropicLLM(
                api_key=provider.api_key,
                model=model.model_id,
                base_url=provider.base_url if provider.base_url else None,
                temperature=float(request.temperature if request.temperature is not None else model.temperature),
                max_tokens=request.max_tokens if request.max_tokens is not None else model.max_tokens
            )
        else:
            from utils.llm import OpenAILLM
            llm = OpenAILLM(
                api_key=provider.api_key,
                model=model.model_id,
                base_url=provider.base_url if provider.base_url else None,
                temperature=float(request.temperature if request.temperature is not None else model.temperature),
                max_tokens=request.max_tokens if request.max_tokens is not None else model.max_tokens
            )
        
        # 调用LLM
        messages = [{"role": "user", "content": request.prompt}]
        llm_result = llm.invoke(messages)
        response_text = llm_result.content

        request_time = time.time() - start_time

        # 使用上游返回的真实 token 数据
        prompt_tokens = llm_result.input_tokens
        completion_tokens = llm_result.output_tokens
        total_tokens = llm_result.total_tokens

        # 使用精确的成本计算
        from admin.usage_logger import calculate_cost
        cost = calculate_cost(prompt_tokens, completion_tokens, model.model_id)
        
        # 记录使用日志
        usage_log = LLMUsageLog(
            model_id=model.id,
            provider_id=provider.id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost=cost,
            request_time=request_time,
            status='success'
        )
        db.add(usage_log)
        db.commit()
        
        return TestModelResponse(
            success=True,
            response=response_text,
            usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "cost": cost
            },
            request_time=request_time
        )
        
    except Exception as e:
        request_time = time.time() - start_time

        # 截断错误消息，避免超出数据库字段长度
        error_msg = str(e)
        if len(error_msg) > 1000:
            # 提取关键错误信息
            if "API 错误:" in error_msg:
                # 提取状态码和前200字符
                error_msg = error_msg[:500] + "... [truncated]"
            else:
                error_msg = error_msg[:1000] + "... [truncated]"

        # 记录错误日志
        usage_log = LLMUsageLog(
            model_id=model.id,
            provider_id=provider.id,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            cost=0,
            request_time=request_time,
            status='error',
            error_message=error_msg
        )
        db.add(usage_log)
        db.commit()

        return TestModelResponse(
            success=False,
            error=error_msg,
            usage={},
            request_time=request_time
        )


# ============================================================
# 知识库批量导入
# ============================================================


# ============================================================
# 评估系统 API
# ============================================================
@router.get("/eval/test-cases", response_model=List[TestCaseResponse])
async def list_test_cases(
    category: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """获取测试用例列表"""
    import json
    from pathlib import Path

    test_cases_path = Path(__file__).parent.parent / "eval" / "test_cases.json"

    if not test_cases_path.exists():
        return []

    with open(test_cases_path, 'r', encoding='utf-8') as f:
        test_cases = json.load(f)

    if category:
        test_cases = [tc for tc in test_cases if tc.get("category") == category]

    return [TestCaseResponse(**tc) for tc in test_cases]


@router.post("/eval/test-cases", response_model=TestCaseResponse)
async def create_test_case(
    data: TestCaseCreate,
    current_user: User = Depends(get_current_user)
):
    """创建测试用例"""
    import json
    import uuid
    from pathlib import Path

    test_cases_path = Path(__file__).parent.parent / "eval" / "test_cases.json"

    # 读取现有测试用例
    if test_cases_path.exists():
        with open(test_cases_path, 'r', encoding='utf-8') as f:
            test_cases = json.load(f)
    else:
        test_cases = []

    # 生成新ID
    new_id = f"tc{len(test_cases) + 1:03d}"

    new_case = {
        "id": new_id,
        "question": data.question,
        "expected_files": data.expected_files,
        "expected_keywords": data.expected_keywords,
        "category": data.category
    }

    test_cases.append(new_case)

    # 保存
    with open(test_cases_path, 'w', encoding='utf-8') as f:
        json.dump(test_cases, f, ensure_ascii=False, indent=2)

    return TestCaseResponse(**new_case)


@router.put("/eval/test-cases/{test_case_id}", response_model=TestCaseResponse)
async def update_test_case(
    test_case_id: str,
    data: TestCaseUpdate,
    current_user: User = Depends(get_current_user)
):
    """更新测试用例"""
    import json
    from pathlib import Path

    test_cases_path = Path(__file__).parent.parent / "eval" / "test_cases.json"

    if not test_cases_path.exists():
        raise HTTPException(status_code=404, detail="测试用例文件不存在")

    with open(test_cases_path, 'r', encoding='utf-8') as f:
        test_cases = json.load(f)

    # 查找并更新
    found = False
    for tc in test_cases:
        if tc.get("id") == test_case_id:
            if data.question is not None:
                tc["question"] = data.question
            if data.expected_files is not None:
                tc["expected_files"] = data.expected_files
            if data.expected_keywords is not None:
                tc["expected_keywords"] = data.expected_keywords
            if data.category is not None:
                tc["category"] = data.category
            found = True

            # 保存
            with open(test_cases_path, 'w', encoding='utf-8') as f:
                json.dump(test_cases, f, ensure_ascii=False, indent=2)

            return TestCaseResponse(**tc)

    if not found:
        raise HTTPException(status_code=404, detail="测试用例不存在")


@router.delete("/eval/test-cases/{test_case_id}", response_model=MessageResponse)
async def delete_test_case(
    test_case_id: str,
    current_user: User = Depends(get_current_user)
):
    """删除测试用例"""
    import json
    from pathlib import Path

    test_cases_path = Path(__file__).parent.parent / "eval" / "test_cases.json"

    if not test_cases_path.exists():
        raise HTTPException(status_code=404, detail="测试用例文件不存在")

    with open(test_cases_path, 'r', encoding='utf-8') as f:
        test_cases = json.load(f)

    original_len = len(test_cases)
    test_cases = [tc for tc in test_cases if tc.get("id") != test_case_id]

    if len(test_cases) == original_len:
        raise HTTPException(status_code=404, detail="测试用例不存在")

    with open(test_cases_path, 'w', encoding='utf-8') as f:
        json.dump(test_cases, f, ensure_ascii=False, indent=2)

    return MessageResponse(message="测试用例已删除")


@router.post("/eval/run", response_model=EvalRunResponse)
async def run_evaluation(
    request: EvalRunRequest,
    current_user: User = Depends(get_current_user)
):
    """运行评估"""
    import json
    from pathlib import Path
    from datetime import datetime

    # 加载测试用例
    test_cases_path = Path(__file__).parent.parent / "eval" / "test_cases.json"

    if not test_cases_path.exists():
        raise HTTPException(status_code=404, detail="测试用例文件不存在")

    with open(test_cases_path, 'r', encoding='utf-8') as f:
        all_test_cases = json.load(f)

    # 筛选测试用例
    if request.test_case_ids:
        test_cases = [tc for tc in all_test_cases if tc.get("id") in request.test_case_ids]
    else:
        test_cases = all_test_cases

    if not test_cases:
        raise HTTPException(status_code=400, detail="没有找到有效的测试用例")

    # 初始化评估器组件
    from qa.chain import QAChatChain
    from retriever.vector_store import VectorStore

    qa_chain = QAChatChain(enable_cache=False)  # 评估时禁用缓存
    vector_store = VectorStore()

    results = []

    for test_case in test_cases:
        try:
            question = test_case["question"]

            # 执行检索
            retrieved_results = vector_store.search(question, top_k=request.top_k)

            # 评估检索质量
            expected_files = test_case.get("expected_files", [])
            expected_keywords = test_case.get("expected_keywords", [])

            retrieved_files = [r.get("file_path", "") for r in retrieved_results]
            file_hits = []
            for exp_file in expected_files:
                matched = [f for f in retrieved_files if exp_file in f]
                if matched:
                    file_hits.append({"expected": exp_file, "matched": matched[0]})

            file_recall = len(file_hits) / len(expected_files) if expected_files else 0

            all_content = " ".join([r.get("content", "") for r in retrieved_results])
            keyword_hits_retrieval = [kw for kw in expected_keywords if kw in all_content]
            keyword_coverage_retrieval = len(keyword_hits_retrieval) / len(expected_keywords) if expected_keywords else 0

            retrieval_metrics = RetrievalMetrics(
                file_recall=file_recall,
                file_hits=file_hits,
                keyword_coverage=keyword_coverage_retrieval,
                keyword_hits=keyword_hits_retrieval,
                retrieved_count=len(retrieved_results),
                avg_score=sum(r.get("score", 0) for r in retrieved_results) / len(retrieved_results) if retrieved_results else 0
            )

            # 执行问答
            qa_result = qa_chain.query(question, use_history=False)
            answer = qa_result["answer"]

            # 评估答案质量
            keyword_hits_answer = [kw for kw in expected_keywords if kw in answer]
            keyword_coverage_answer = len(keyword_hits_answer) / len(expected_keywords) if expected_keywords else 0

            refusal_phrases = ["无法找到", "没有找到", "不确定", "无法回答"]
            is_refusal = any(phrase in answer for phrase in refusal_phrases)

            answer_metrics = AnswerMetrics(
                keyword_coverage=keyword_coverage_answer,
                keyword_hits=keyword_hits_answer,
                is_refusal=is_refusal,
                answer_length=len(answer)
            )

            results.append(EvalResultResponse(
                test_case_id=test_case["id"],
                question=question,
                category=test_case.get("category", "unknown"),
                answer=answer,
                sources=qa_result.get("sources", []),
                retrieval_metrics=retrieval_metrics,
                answer_metrics=answer_metrics,
                timestamp=datetime.now().isoformat()
            ))

        except Exception as e:
            results.append(EvalResultResponse(
                test_case_id=test_case["id"],
                question=test_case["question"],
                category=test_case.get("category", "unknown"),
                error=str(e),
                timestamp=datetime.now().isoformat()
            ))

    # 计算汇总指标
    valid_results = [r for r in results if r.error is None]

    summary = EvalSummaryResponse(
        total_cases=len(test_cases),
        successful_cases=len(valid_results),
        failed_cases=len(results) - len(valid_results),
        avg_file_recall=sum(r.retrieval_metrics.file_recall for r in valid_results) / len(valid_results) if valid_results else 0,
        avg_keyword_coverage_retrieval=sum(r.retrieval_metrics.keyword_coverage for r in valid_results) / len(valid_results) if valid_results else 0,
        avg_keyword_coverage_answer=sum(r.answer_metrics.keyword_coverage for r in valid_results) / len(valid_results) if valid_results else 0,
        refusal_rate=sum(1 for r in valid_results if r.answer_metrics.is_refusal) / len(valid_results) if valid_results else 0
    )

    return EvalRunResponse(
        summary=summary,
        results=results,
        timestamp=datetime.now().isoformat()
    )


@router.get("/eval/stats", response_model=EvalSummaryResponse)
async def get_eval_stats(
    current_user: User = Depends(get_current_user)
):
    """获取评估统计（从最近的评估结果文件）"""
    import json
    from pathlib import Path
    import glob

    eval_dir = Path(__file__).parent.parent / "eval"
    result_files = sorted(eval_dir.glob("eval_results_*.json"), reverse=True)

    if not result_files:
        return EvalSummaryResponse(
            total_cases=0,
            successful_cases=0,
            failed_cases=0,
            avg_file_recall=0,
            avg_keyword_coverage_retrieval=0,
            avg_keyword_coverage_answer=0,
            refusal_rate=0
        )

    # 读取最新的结果文件
    with open(result_files[0], 'r', encoding='utf-8') as f:
        data = json.load(f)

    summary = data.get("summary", {})

    return EvalSummaryResponse(
        total_cases=summary.get("total_cases", 0),
        successful_cases=summary.get("successful_cases", 0),
        failed_cases=summary.get("failed_cases", 0),
        avg_file_recall=summary.get("avg_file_recall", 0),
        avg_keyword_coverage_retrieval=summary.get("avg_keyword_coverage_retrieval", 0),
        avg_keyword_coverage_answer=summary.get("avg_keyword_coverage_answer", 0),
        refusal_rate=summary.get("refusal_rate", 0)
    )


# ============================================================
# 语义缓存统计 API
# ============================================================
@router.get("/cache/stats", response_model=CacheStatsResponse)
async def get_cache_stats(
    current_user: User = Depends(get_current_user)
):
    """获取语义缓存统计"""
    try:
        from retriever.semantic_cache import SemanticCache

        cache = SemanticCache()
        stats = cache.get_stats()

        # 解析 hit_rate（可能是字符串格式如 "85.00%"）
        hit_rate = stats.get("hit_rate", 0)
        if isinstance(hit_rate, str):
            hit_rate = float(hit_rate.rstrip('%')) / 100 if '%' in hit_rate else float(hit_rate)

        return CacheStatsResponse(
            total_entries=stats.get("cache_size", 0),
            hit_rate=hit_rate,
            avg_similarity=stats.get("similarity_threshold", 0.92),  # 使用阈值作为参考
            cache_size_mb=0  # Qdrant 不直接提供大小，暂时返回 0
        )
    except Exception as e:
        return CacheStatsResponse(
            total_entries=0,
            hit_rate=0,
            avg_similarity=0,
            cache_size_mb=0
        )


@router.post("/cache/clear", response_model=MessageResponse)
async def clear_cache(
    current_user: User = Depends(get_current_user)
):
    """清空语义缓存"""
    try:
        from retriever.semantic_cache import SemanticCache

        cache = SemanticCache()
        cache.clear()

        return MessageResponse(message="缓存已清空")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清空缓存失败: {str(e)}")


@router.post("/knowledge/import", response_model=MessageResponse)
async def import_knowledge(
    file: bytes = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """批量导入知识条目"""
    try:
        import json
        from qdrant_client import QdrantClient
        from qdrant_client.models import PointStruct
        from utils.embeddings import EmbeddingModel
        from config import QDRANT_HOST, QDRANT_PORT, QDRANT_API_KEY, QDRANT_COLLECTION_NAME, QDRANT_USE_HTTPS
        import hashlib

        # 解析JSON
        try:
            data = json.loads(file.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise HTTPException(status_code=400, detail=f"JSON 解析失败: {str(e)}")

        entries = data.get('entries', [])
        
        if not entries:
            raise HTTPException(status_code=400, detail="没有找到有效的条目")
        
        # 初始化客户端
        protocol = "https" if QDRANT_USE_HTTPS else "http"
        url = f"{protocol}://{QDRANT_HOST}:{QDRANT_PORT}"
        qdrant_client = QdrantClient(url=url, api_key=QDRANT_API_KEY if QDRANT_API_KEY else None)
        embedding_model = EmbeddingModel()
        
        success_count = 0
        error_count = 0
        
        for entry in entries:
            try:
                content = entry.get('content', '')
                title = entry.get('title', '未命名')
                category = entry.get('category', 'general')
                
                if not content:
                    error_count += 1
                    continue
                
                # 生成嵌入
                embeddings = embedding_model.encode([content])
                
                # 生成ID
                content_hash = hashlib.md5(f"{content}:{datetime.now().isoformat()}".encode()).hexdigest()
                
                # 存储到Qdrant
                point = PointStruct(
                    id=content_hash,
                    vector=embeddings[0].tolist(),
                    payload={
                        "content": content,
                        "title": title,
                        "category": category,
                        "type": "knowledge",
                        "created_at": datetime.now().isoformat()
                    }
                )
                
                qdrant_client.upsert(
                    collection_name=QDRANT_COLLECTION_NAME,
                    points=[point]
                )
                
                # 存储到MySQL
                knowledge_entry = KnowledgeEntry(
                    qdrant_id=content_hash,
                    title=title,
                    category=category,
                    summary=entry.get('summary', ''),
                    keywords=entry.get('keywords', []),
                    tech_stack=entry.get('tech_stack', []),
                    content_preview=content[:500]
                )
                db.add(knowledge_entry)
                
                success_count += 1
                
            except Exception as e:
                error_count += 1
                continue
        
        db.commit()
        
        return MessageResponse(
            message=f"导入完成！成功: {success_count}, 失败: {error_count}"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")


# ============================================================
# 知识分组管理
# ============================================================
@router.get("/groups", response_model=KnowledgeGroupListResponse)
async def list_groups(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取知识分组列表，根据用户权限过滤

    权限规则：
    1. 管理员可看全部分组
    2. 普通用户可看：
       - 自己创建的分组
       - 公开分组
       - 共享给自己的分组
    """
    from sqlalchemy import or_

    query = db.query(KnowledgeGroup).filter(KnowledgeGroup.is_active == True)

    # 用户权限过滤
    if current_user.role != "admin":
        # 获取共享给当前用户的分组ID
        shared_group_ids = db.query(GroupShare.group_id).filter(
            GroupShare.shared_with_user_id == current_user.id
        ).all()
        shared_group_ids = [g[0] for g in shared_group_ids]

        query = query.filter(
            or_(
                KnowledgeGroup.user_id == current_user.id,  # 自己创建的
                KnowledgeGroup.is_public == True,  # 公开的
                KnowledgeGroup.id.in_(shared_group_ids) if shared_group_ids else False  # 共享给自己的
            )
        )

    groups = query.order_by(KnowledgeGroup.id.desc()).all()

    # 获取用户有 write 权限的共享分组
    user_write_group_ids = set()
    if current_user.role != "admin":
        shared_writes = db.query(GroupShare.group_id).filter(
            GroupShare.shared_with_user_id == current_user.id,
            GroupShare.permission == 'write'
        ).all()
        user_write_group_ids = {s[0] for s in shared_writes}

    # 计算未分组知识数量
    grouped_qdrant_ids = db.query(KnowledgeGroupItem.qdrant_id).distinct().subquery()
    if current_user.role != "admin":
        # 普通用户只计算自己创建的未分组知识
        ungrouped_count = db.query(func.count(KnowledgeEntry.id)).filter(
            ~KnowledgeEntry.qdrant_id.in_(grouped_qdrant_ids),
            KnowledgeEntry.user_id == current_user.id
        ).scalar() or 0
    else:
        ungrouped_count = db.query(func.count(KnowledgeEntry.id)).filter(
            ~KnowledgeEntry.qdrant_id.in_(grouped_qdrant_ids)
        ).scalar() or 0

    # 虚拟默认分组（未分组）
    now = datetime.now()
    default_group = KnowledgeGroupResponse(
        id=0,
        name="未分组",
        description="未被任何分组引用的知识",
        color="#999999",
        icon="inbox",
        is_active=True,
        is_default=True,
        is_public=True,
        user_id=None,
        can_edit=current_user.role == "admin",  # 只有管理员可管理未分组
        items_count=ungrouped_count,
        created_at=now,
        updated_at=now
    )

    result = [default_group]  # 未分组放在首位
    for g in groups:
        items_count = db.query(func.count(KnowledgeGroupItem.id)).filter(KnowledgeGroupItem.group_id == g.id).scalar() or 0

        # 判断用户是否可以编辑该分组
        # 规则：管理员可编辑所有，普通用户可编辑：1.自己创建的 2.有write权限的共享分组
        can_edit = False
        if current_user.role == "admin":
            can_edit = True
        elif g.user_id == current_user.id:
            can_edit = True
        elif g.id in user_write_group_ids:
            can_edit = True

        result.append(KnowledgeGroupResponse(
            id=g.id,
            name=g.name,
            description=g.description,
            color=g.color,
            icon=g.icon,
            is_active=g.is_active,
            is_default=False,
            is_public=g.is_public,
            user_id=g.user_id,
            can_edit=can_edit,  # 新增：是否可编辑
            items_count=items_count,
            created_at=g.created_at,
            updated_at=g.updated_at
        ))

    return KnowledgeGroupListResponse(items=result, total=len(result))


@router.post("/groups", response_model=KnowledgeGroupResponse)
async def create_group(
    data: KnowledgeGroupCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建知识分组"""
    group = KnowledgeGroup(**data.model_dump(), user_id=current_user.id)
    db.add(group)
    db.commit()
    db.refresh(group)

    return KnowledgeGroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        color=group.color,
        icon=group.icon,
        is_active=group.is_active,
        is_public=group.is_public,
        user_id=group.user_id,
        items_count=0,
        created_at=group.created_at,
        updated_at=group.updated_at
    )


@router.get("/groups/{group_id}", response_model=KnowledgeGroupResponse)
async def get_group(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取分组详情"""
    group = db.query(KnowledgeGroup).filter(KnowledgeGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")

    items_count = db.query(func.count(KnowledgeGroupItem.id)).filter(KnowledgeGroupItem.group_id == group.id).scalar() or 0

    return KnowledgeGroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        color=group.color,
        icon=group.icon,
        is_active=group.is_active,
        is_public=group.is_public,
        user_id=group.user_id,
        items_count=items_count,
        created_at=group.created_at,
        updated_at=group.updated_at
    )


@router.put("/groups/{group_id}", response_model=KnowledgeGroupResponse)
async def update_group(
    group_id: int,
    data: KnowledgeGroupUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新分组"""
    group = db.query(KnowledgeGroup).filter(KnowledgeGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(group, key, value)

    db.commit()
    db.refresh(group)

    items_count = db.query(func.count(KnowledgeGroupItem.id)).filter(KnowledgeGroupItem.group_id == group.id).scalar() or 0

    return KnowledgeGroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        color=group.color,
        icon=group.icon,
        is_active=group.is_active,
        is_public=group.is_public,
        user_id=group.user_id,
        items_count=items_count,
        created_at=group.created_at,
        updated_at=group.updated_at
    )


@router.delete("/groups/{group_id}", response_model=MessageResponse)
async def delete_group(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除分组"""
    group = db.query(KnowledgeGroup).filter(KnowledgeGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")

    db.delete(group)
    db.commit()
    return MessageResponse(message="分组已删除")


@router.get("/groups/{group_id}/items", response_model=List[GroupItemResponse])
async def list_group_items(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取分组内的知识条目，group_id=0 表示未分组"""
    if group_id == 0:
        # 未分组：获取所有不在任何分组中的知识
        grouped_qdrant_ids = db.query(KnowledgeGroupItem.qdrant_id).distinct().subquery()
        entries = db.query(KnowledgeEntry).filter(
            ~KnowledgeEntry.qdrant_id.in_(grouped_qdrant_ids)
        ).all()

        result = []
        for entry in entries:
            result.append(GroupItemResponse(
                id=0,  # 虚拟 ID
                group_id=0,
                qdrant_id=entry.qdrant_id,
                title=entry.title,
                created_at=entry.created_at
            ))
        return result

    # 正常分组
    group = db.query(KnowledgeGroup).filter(KnowledgeGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")

    # 使用 LEFT JOIN 一次性获取分组项和知识条目标题
    rows = db.query(
        KnowledgeGroupItem,
        KnowledgeEntry.title.label('entry_title')
    ).outerjoin(
        KnowledgeEntry, KnowledgeGroupItem.qdrant_id == KnowledgeEntry.qdrant_id
    ).filter(
        KnowledgeGroupItem.group_id == group_id
    ).all()

    result = []
    for item, entry_title in rows:
        result.append(GroupItemResponse(
            id=item.id,
            group_id=item.group_id,
            qdrant_id=item.qdrant_id,
            title=entry_title,
            created_at=item.created_at
        ))

    return result


@router.post("/groups/{group_id}/items", response_model=MessageResponse)
async def add_group_items(
    group_id: int,
    data: GroupItemsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """添加知识条目到分组"""
    group = db.query(KnowledgeGroup).filter(KnowledgeGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")

    added = 0
    skipped = 0
    for qdrant_id in data.qdrant_ids:
        # 检查是否已存在
        existing = db.query(KnowledgeGroupItem).filter(
            KnowledgeGroupItem.group_id == group_id,
            KnowledgeGroupItem.qdrant_id == qdrant_id
        ).first()

        if existing:
            skipped += 1
            continue

        item = KnowledgeGroupItem(group_id=group_id, qdrant_id=qdrant_id)
        db.add(item)
        added += 1

    db.commit()
    return MessageResponse(message=f"已添加 {added} 条，跳过 {skipped} 条（已存在）")


@router.delete("/groups/{group_id}/items", response_model=MessageResponse)
async def remove_group_items(
    group_id: int,
    data: GroupItemsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """从分组移除知识条目"""
    group = db.query(KnowledgeGroup).filter(KnowledgeGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")

    removed = db.query(KnowledgeGroupItem).filter(
        KnowledgeGroupItem.group_id == group_id,
        KnowledgeGroupItem.qdrant_id.in_(data.qdrant_ids)
    ).delete(synchronize_session=False)

    db.commit()
    return MessageResponse(message=f"已移除 {removed} 条")


# ============================================================
# 知识版本追踪
# ============================================================
@router.get("/knowledge/{qdrant_id}/versions", response_model=KnowledgeVersionListResponse)
async def list_knowledge_versions(
    qdrant_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取知识条目的版本历史"""
    versions = db.query(KnowledgeVersion).filter(
        KnowledgeVersion.qdrant_id == qdrant_id
    ).order_by(KnowledgeVersion.version.desc()).all()

    current_version = max([v.version for v in versions]) if versions else 0

    result = []
    for v in versions:
        result.append(KnowledgeVersionResponse(
            id=v.id,
            qdrant_id=v.qdrant_id,
            version=v.version,
            change_type=v.change_type,
            changed_by=v.changed_by,
            change_reason=v.change_reason,
            content_preview=v.content[:200] + "..." if len(v.content) > 200 else v.content,
            created_at=v.created_at
        ))

    return KnowledgeVersionListResponse(
        qdrant_id=qdrant_id,
        current_version=current_version,
        versions=result,
        total=len(result)
    )


@router.get("/knowledge/{qdrant_id}/versions/{version}", response_model=KnowledgeVersionDetailResponse)
async def get_knowledge_version(
    qdrant_id: str,
    version: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取特定版本的详细内容"""
    version_entry = db.query(KnowledgeVersion).filter(
        KnowledgeVersion.qdrant_id == qdrant_id,
        KnowledgeVersion.version == version
    ).first()

    if not version_entry:
        raise HTTPException(status_code=404, detail="版本不存在")

    return KnowledgeVersionDetailResponse(
        id=version_entry.id,
        qdrant_id=version_entry.qdrant_id,
        version=version_entry.version,
        content=version_entry.content,
        metadata=version_entry.metadata,
        change_type=version_entry.change_type,
        changed_by=version_entry.changed_by,
        change_reason=version_entry.change_reason,
        created_at=version_entry.created_at
    )


@router.post("/knowledge/{qdrant_id}/rollback", response_model=RollbackResponse)
async def rollback_knowledge(
    qdrant_id: str,
    data: RollbackRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """回滚知识条目到指定版本"""
    # 获取目标版本
    target_version = db.query(KnowledgeVersion).filter(
        KnowledgeVersion.qdrant_id == qdrant_id,
        KnowledgeVersion.version == data.target_version
    ).first()

    if not target_version:
        raise HTTPException(status_code=404, detail="目标版本不存在")

    # 获取当前最新版本号
    latest_version = db.query(func.max(KnowledgeVersion.version)).filter(
        KnowledgeVersion.qdrant_id == qdrant_id
    ).scalar() or 0

    new_version = latest_version + 1

    try:
        # 1. 更新 Qdrant 中的内容
        from qdrant_client import QdrantClient
        from config import QDRANT_HOST, QDRANT_PORT, QDRANT_API_KEY, QDRANT_COLLECTION_NAME, QDRANT_USE_HTTPS
        from utils.embeddings import EmbeddingModel

        protocol = "https" if QDRANT_USE_HTTPS else "http"
        url = f"{protocol}://{QDRANT_HOST}:{QDRANT_PORT}"
        client = QdrantClient(url=url, api_key=QDRANT_API_KEY if QDRANT_API_KEY else None)

        # 重新计算嵌入
        embedding_model = EmbeddingModel()
        embeddings = embedding_model.encode([target_version.content])

        # 更新向量
        from qdrant_client.models import PointStruct
        client.upsert(
            collection_name=QDRANT_COLLECTION_NAME,
            points=[PointStruct(
                id=qdrant_id,
                vector=embeddings[0].tolist(),
                payload={
                    "content": target_version.content,
                    **(target_version.metadata or {})
                }
            )]
        )

        # 2. 创建新版本记录
        rollback_version = KnowledgeVersion(
            qdrant_id=qdrant_id,
            version=new_version,
            content=target_version.content,
            metadata=target_version.metadata,
            change_type='update',
            changed_by=current_user.username,
            change_reason=data.reason or f"回滚到版本 {data.target_version}"
        )
        db.add(rollback_version)

        # 3. 更新 MySQL 知识条目
        entry = db.query(KnowledgeEntry).filter(KnowledgeEntry.qdrant_id == qdrant_id).first()
        if entry:
            entry.content_preview = target_version.content[:500]

        db.commit()

        return RollbackResponse(
            success=True,
            message=f"已成功回滚到版本 {data.target_version}",
            new_version=new_version,
            qdrant_id=qdrant_id
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"回滚失败: {str(e)}")


# ============================================================
# 嵌入供应商管理
# ============================================================

@router.get("/embedding-providers", response_model=List[EmbeddingProviderResponse])
async def list_embedding_providers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取所有嵌入供应商列表"""
    providers = db.query(EmbeddingProvider).all()

    return [
        EmbeddingProviderResponse(
            id=p.id,
            name=p.name,
            api_base_url=p.api_base_url,
            api_key_masked=mask_api_key(p.api_key),
            model_name=p.model_name,
            embedding_dim=p.embedding_dim,
            max_batch_size=p.max_batch_size,
            request_timeout=p.request_timeout,
            is_active=p.is_active,
            is_default=p.is_default,
            monthly_budget=p.monthly_budget,
            current_usage=float(p.current_usage),
            created_at=p.created_at,
            updated_at=p.updated_at
        )
        for p in providers
    ]


@router.post("/embedding-providers", response_model=EmbeddingProviderResponse)
async def create_embedding_provider(
    provider: EmbeddingProviderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建嵌入供应商"""
    # 检查供应商名称是否已存在
    existing = db.query(EmbeddingProvider).filter(EmbeddingProvider.name == provider.name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"供应商名称 '{provider.name}' 已存在")

    # 创建新供应商
    new_provider = EmbeddingProvider(
        name=provider.name,
        api_base_url=provider.api_base_url,
        api_key=provider.api_key,
        model_name=provider.model_name,
        embedding_dim=provider.embedding_dim,
        max_batch_size=provider.max_batch_size,
        request_timeout=provider.request_timeout,
        monthly_budget=provider.monthly_budget,
        is_active=True,
        is_default=False
    )

    db.add(new_provider)
    db.commit()
    db.refresh(new_provider)

    return EmbeddingProviderResponse(
        id=new_provider.id,
        name=new_provider.name,
        api_base_url=new_provider.api_base_url,
        api_key_masked=mask_api_key(new_provider.api_key),
        model_name=new_provider.model_name,
        embedding_dim=new_provider.embedding_dim,
        max_batch_size=new_provider.max_batch_size,
        request_timeout=new_provider.request_timeout,
        is_active=new_provider.is_active,
        is_default=new_provider.is_default,
        monthly_budget=new_provider.monthly_budget,
        current_usage=float(new_provider.current_usage),
        created_at=new_provider.created_at,
        updated_at=new_provider.updated_at
    )


@router.get("/embedding-providers/{provider_id}", response_model=EmbeddingProviderResponse)
async def get_embedding_provider(
    provider_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取嵌入供应商详情"""
    provider = db.query(EmbeddingProvider).filter(EmbeddingProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="供应商不存在")

    return EmbeddingProviderResponse(
        id=provider.id,
        name=provider.name,
        api_base_url=provider.api_base_url,
        api_key_masked=mask_api_key(provider.api_key),
        model_name=provider.model_name,
        embedding_dim=provider.embedding_dim,
        max_batch_size=provider.max_batch_size,
        request_timeout=provider.request_timeout,
        is_active=provider.is_active,
        is_default=provider.is_default,
        monthly_budget=provider.monthly_budget,
        current_usage=float(provider.current_usage),
        created_at=provider.created_at,
        updated_at=provider.updated_at
    )


@router.put("/embedding-providers/{provider_id}", response_model=EmbeddingProviderResponse)
async def update_embedding_provider(
    provider_id: int,
    provider_update: EmbeddingProviderUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新嵌入供应商"""
    provider = db.query(EmbeddingProvider).filter(EmbeddingProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="供应商不存在")

    # 更新字段
    update_data = provider_update.dict(exclude_unset=True)

    # 特殊处理: 如果 api_key 为空字符串,则不更新(保留原值)
    if 'api_key' in update_data and not update_data['api_key']:
        update_data.pop('api_key')

    for field, value in update_data.items():
        setattr(provider, field, value)

    db.commit()
    db.refresh(provider)

    return EmbeddingProviderResponse(
        id=provider.id,
        name=provider.name,
        api_base_url=provider.api_base_url,
        api_key_masked=mask_api_key(provider.api_key),
        model_name=provider.model_name,
        embedding_dim=provider.embedding_dim,
        max_batch_size=provider.max_batch_size,
        request_timeout=provider.request_timeout,
        is_active=provider.is_active,
        is_default=provider.is_default,
        monthly_budget=provider.monthly_budget,
        current_usage=float(provider.current_usage),
        created_at=provider.created_at,
        updated_at=provider.updated_at
    )


@router.delete("/embedding-providers/{provider_id}")
async def delete_embedding_provider(
    provider_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除嵌入供应商"""
    provider = db.query(EmbeddingProvider).filter(EmbeddingProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="供应商不存在")

    if provider.is_default:
        raise HTTPException(status_code=400, detail="无法删除默认供应商,请先设置其他供应商为默认")

    db.delete(provider)
    db.commit()

    return MessageResponse(message=f"供应商 '{provider.name}' 已删除")


@router.post("/embedding-providers/{provider_id}/set-default")
async def set_default_embedding_provider(
    provider_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """设置默认嵌入供应商"""
    provider = db.query(EmbeddingProvider).filter(EmbeddingProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="供应商不存在")

    # 取消其他供应商的默认标记
    db.query(EmbeddingProvider).update({"is_default": False})

    # 设置当前供应商为默认
    provider.is_default = True
    db.commit()

    # 触发嵌入模型热重载
    try:
        from utils.embeddings import get_embedding_model
        embedding_model = get_embedding_model()
        reloaded = embedding_model.reload()
        if reloaded:
            logger.info(f"已热重载嵌入模型,当前使用: {provider.name}")
    except Exception as e:
        logger.error(f"嵌入模型热重载失败: {e}")

    return MessageResponse(message=f"已将 '{provider.name}' 设置为默认嵌入供应商,无需重启服务")


@router.post("/embedding-providers/{provider_id}/test")
async def test_embedding_provider(
    provider_id: int,
    request: TestEmbeddingRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """测试嵌入供应商"""
    provider = db.query(EmbeddingProvider).filter(EmbeddingProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="供应商不存在")

    try:
        import httpx

        start_time = time.time()

        # 调用嵌入 API
        async with httpx.AsyncClient(timeout=provider.request_timeout) as client:
            response = await client.post(
                f"{provider.api_base_url}/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {provider.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": provider.model_name,
                    "input": request.text
                }
            )
            response.raise_for_status()
            result = response.json()

        elapsed = time.time() - start_time

        # 获取向量
        embedding = result.get("data", [{}])[0].get("embedding", [])

        return {
            "success": True,
            "message": "嵌入测试成功",
            "provider_name": provider.name,
            "model_name": provider.model_name,
            "embedding_dim": len(embedding),
            "request_time": round(elapsed, 3),
            "sample_vector": embedding[:10] if len(embedding) > 10 else embedding
        }

    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=500,
            detail=f"API 请求失败 ({e.response.status_code}): {e.response.text}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"测试失败: {str(e)}")


# ============================================================
# MCP API 卡密管理
# ============================================================
import secrets


def generate_api_key() -> str:
    """生成随机API密钥，格式: rag_sk_xxx"""
    return f"rag_sk_{secrets.token_hex(24)}"


@router.get("/api-keys", response_model=MCPApiKeyListResponse)
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取所有卡密列表"""
    keys = db.query(MCPApiKey).order_by(MCPApiKey.created_at.desc()).all()
    return MCPApiKeyListResponse(
        items=[MCPApiKeyResponse.model_validate(k) for k in keys],
        total=len(keys)
    )


@router.post("/api-keys", response_model=MCPApiKeyResponse)
async def create_api_key(
    data: MCPApiKeyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建新卡密"""
    api_key = MCPApiKey(
        key=generate_api_key(),
        name=data.name,
        expires_at=data.expires_at
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return MCPApiKeyResponse.model_validate(api_key)


@router.get("/api-keys/{key_id}", response_model=MCPApiKeyResponse)
async def get_api_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取卡密详情"""
    api_key = db.query(MCPApiKey).filter(MCPApiKey.id == key_id).first()
    if not api_key:
        raise HTTPException(status_code=404, detail="卡密不存在")
    return MCPApiKeyResponse.model_validate(api_key)


@router.put("/api-keys/{key_id}", response_model=MCPApiKeyResponse)
async def update_api_key(
    key_id: int,
    data: MCPApiKeyUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新卡密"""
    api_key = db.query(MCPApiKey).filter(MCPApiKey.id == key_id).first()
    if not api_key:
        raise HTTPException(status_code=404, detail="卡密不存在")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(api_key, field, value)

    db.commit()
    db.refresh(api_key)
    return MCPApiKeyResponse.model_validate(api_key)


@router.delete("/api-keys/{key_id}", response_model=MessageResponse)
async def delete_api_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除卡密"""
    api_key = db.query(MCPApiKey).filter(MCPApiKey.id == key_id).first()
    if not api_key:
        raise HTTPException(status_code=404, detail="卡密不存在")

    db.delete(api_key)
    db.commit()
    return MessageResponse(message="卡密已删除")


# ============================================================
# 分组共享管理
# ============================================================
@router.get("/users/list", response_model=List[UserSimpleResponse])
async def list_users_for_share(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取可共享的用户列表（排除当前用户）"""
    users = db.query(User).filter(
        User.id != current_user.id,
        User.is_active == True
    ).all()
    return [UserSimpleResponse.model_validate(u) for u in users]


@router.get("/groups/{group_id}/shares", response_model=GroupShareListResponse)
async def list_group_shares(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取分组的共享列表"""
    group = db.query(KnowledgeGroup).filter(KnowledgeGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")

    # 只有分组所有者或管理员可以查看共享列表
    if current_user.role != "admin" and group.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权查看此分组的共享列表")

    shares = db.query(GroupShare).filter(GroupShare.group_id == group_id).all()

    result = []
    for share in shares:
        result.append(GroupShareResponse(
            id=share.id,
            group_id=share.group_id,
            group_name=group.name,
            shared_with_user_id=share.shared_with_user_id,
            shared_with_username=share.shared_with_user.username if share.shared_with_user else "",
            shared_by_user_id=share.shared_by_user_id,
            shared_by_username=share.shared_by_user.username if share.shared_by_user else "",
            permission=share.permission,
            created_at=share.created_at
        ))

    return GroupShareListResponse(items=result, total=len(result))


@router.post("/groups/{group_id}/shares", response_model=GroupShareResponse)
async def create_group_share(
    group_id: int,
    data: GroupShareCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建分组共享"""
    group = db.query(KnowledgeGroup).filter(KnowledgeGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")

    # 只有分组所有者或管理员可以共享
    if current_user.role != "admin" and group.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权共享此分组")

    # 检查目标用户是否存在
    target_user = db.query(User).filter(User.id == data.shared_with_user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="目标用户不存在")

    # 不能共享给自己
    if data.shared_with_user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能共享给自己")

    # 检查是否已存在共享
    existing = db.query(GroupShare).filter(
        GroupShare.group_id == group_id,
        GroupShare.shared_with_user_id == data.shared_with_user_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="已存在对该用户的共享")

    share = GroupShare(
        group_id=group_id,
        shared_with_user_id=data.shared_with_user_id,
        shared_by_user_id=current_user.id,
        permission=data.permission
    )
    db.add(share)
    db.commit()
    db.refresh(share)

    return GroupShareResponse(
        id=share.id,
        group_id=share.group_id,
        group_name=group.name,
        shared_with_user_id=share.shared_with_user_id,
        shared_with_username=target_user.username,
        shared_by_user_id=share.shared_by_user_id,
        shared_by_username=current_user.username,
        permission=share.permission,
        created_at=share.created_at
    )


@router.put("/groups/{group_id}/shares/{share_id}", response_model=GroupShareResponse)
async def update_group_share(
    group_id: int,
    share_id: int,
    data: GroupShareUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新分组共享权限"""
    share = db.query(GroupShare).filter(
        GroupShare.id == share_id,
        GroupShare.group_id == group_id
    ).first()
    if not share:
        raise HTTPException(status_code=404, detail="共享记录不存在")

    group = db.query(KnowledgeGroup).filter(KnowledgeGroup.id == group_id).first()

    # 只有分组所有者或管理员可以修改
    if current_user.role != "admin" and group.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权修改此共享")

    share.permission = data.permission
    db.commit()
    db.refresh(share)

    return GroupShareResponse(
        id=share.id,
        group_id=share.group_id,
        group_name=group.name,
        shared_with_user_id=share.shared_with_user_id,
        shared_with_username=share.shared_with_user.username if share.shared_with_user else "",
        shared_by_user_id=share.shared_by_user_id,
        shared_by_username=share.shared_by_user.username if share.shared_by_user else "",
        permission=share.permission,
        created_at=share.created_at
    )


@router.delete("/groups/{group_id}/shares/{share_id}", response_model=MessageResponse)
async def delete_group_share(
    group_id: int,
    share_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """取消分组共享"""
    share = db.query(GroupShare).filter(
        GroupShare.id == share_id,
        GroupShare.group_id == group_id
    ).first()
    if not share:
        raise HTTPException(status_code=404, detail="共享记录不存在")

    group = db.query(KnowledgeGroup).filter(KnowledgeGroup.id == group_id).first()

    # 只有分组所有者或管理员可以取消共享
    if current_user.role != "admin" and group.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权取消此共享")

    db.delete(share)
    db.commit()
    return MessageResponse(message="已取消共享")


@router.get("/my-shared-groups", response_model=KnowledgeGroupListResponse)
async def list_my_shared_groups(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取共享给我的分组列表"""
    # 查找所有共享给当前用户的分组
    shares = db.query(GroupShare).filter(
        GroupShare.shared_with_user_id == current_user.id
    ).all()

    group_ids = [s.group_id for s in shares]
    if not group_ids:
        return KnowledgeGroupListResponse(items=[], total=0)

    groups = db.query(KnowledgeGroup).filter(
        KnowledgeGroup.id.in_(group_ids),
        KnowledgeGroup.is_active == True
    ).all()

    result = []
    for group in groups:
        items_count = db.query(func.count(KnowledgeGroupItem.id)).filter(
            KnowledgeGroupItem.group_id == group.id
        ).scalar()
        result.append(KnowledgeGroupResponse(
            id=group.id,
            name=group.name,
            description=group.description,
            color=group.color,
            icon=group.icon,
            is_active=group.is_active,
            user_id=group.user_id,
            is_public=group.is_public,
            items_count=items_count or 0,
            created_at=group.created_at,
            updated_at=group.updated_at
        ))

    return KnowledgeGroupListResponse(items=result, total=len(result))


# ============================================================
# 用户管理（仅管理员可用）
# ============================================================
def require_admin(current_user: User = Depends(get_current_user)):
    """要求管理员权限"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return current_user


@router.get("/users", response_model=UserListResponse)
async def list_all_users(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """获取所有用户列表（仅管理员）"""
    users = db.query(User).order_by(User.created_at.desc()).all()
    return UserListResponse(
        items=[UserResponse.model_validate(u) for u in users],
        total=len(users)
    )


@router.post("/users", response_model=UserResponse)
async def create_user(
    data: UserCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """创建新用户（仅管理员）"""
    # 检查用户名是否已存在
    existing = db.query(User).filter(User.username == data.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")

    user = User(
        username=data.username,
        password_hash=get_password_hash(data.password),
        role=data.role,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info(f"管理员 {current_user.username} 创建了用户: {data.username}")
    return UserResponse.model_validate(user)


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user_detail(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """获取用户详情（仅管理员）"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return UserResponse.model_validate(user)


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    data: UserUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """更新用户信息（仅管理员）"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 不允许禁用自己
    if data.is_active is False and user.id == current_user.id:
        raise HTTPException(status_code=400, detail="不能禁用自己的账号")

    # 更新密码
    if data.password:
        user.password_hash = get_password_hash(data.password)

    # 更新角色
    if data.role:
        # 不允许取消自己的管理员权限
        if data.role != "admin" and user.id == current_user.id:
            raise HTTPException(status_code=400, detail="不能取消自己的管理员权限")
        user.role = data.role

    # 更新激活状态
    if data.is_active is not None:
        user.is_active = data.is_active

    db.commit()
    db.refresh(user)

    logger.info(f"管理员 {current_user.username} 更新了用户: {user.username}")
    return UserResponse.model_validate(user)


@router.delete("/users/{user_id}", response_model=MessageResponse)
async def delete_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """删除用户（仅管理员）"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 不允许删除自己
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除自己的账号")

    username = user.username
    db.delete(user)
    db.commit()

    logger.info(f"管理员 {current_user.username} 删除了用户: {username}")
    return MessageResponse(message=f"用户 {username} 已删除")
