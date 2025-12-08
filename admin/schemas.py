"""
Pydantic 数据模式
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


# ============================================================
# 认证相关
# ============================================================
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================
# LLM供应商相关
# ============================================================
class ProviderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    api_format: str = Field(..., pattern="^(anthropic|openai)$")
    api_key: str = Field(..., min_length=1)
    base_url: Optional[str] = None
    is_active: bool = True
    is_default: bool = False
    request_timeout: int = Field(default=120, ge=10, le=600)
    max_concurrent: int = Field(default=10, ge=1, le=100)
    monthly_budget: Optional[Decimal] = None


class ProviderUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    api_format: Optional[str] = Field(None, pattern="^(anthropic|openai)$")
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
    request_timeout: Optional[int] = Field(None, ge=10, le=600)
    max_concurrent: Optional[int] = Field(None, ge=1, le=100)
    monthly_budget: Optional[Decimal] = None


class ProviderResponse(BaseModel):
    id: int
    name: str
    api_format: str
    api_key_masked: str  # 脱敏后的API Key
    base_url: Optional[str]
    is_active: bool
    is_default: bool
    request_timeout: int
    max_concurrent: int
    monthly_budget: Optional[Decimal]
    current_usage: Decimal
    created_at: datetime
    updated_at: datetime
    models_count: int = 0

    class Config:
        from_attributes = True


# ============================================================
# LLM模型相关
# ============================================================
class ModelCreate(BaseModel):
    provider_id: int
    model_id: str = Field(..., min_length=1, max_length=100)
    display_name: str = Field(..., min_length=1, max_length=100)
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=4096, ge=1, le=200000)
    system_prompt: Optional[str] = None
    is_active: bool = True
    is_default: bool = False


class ModelUpdate(BaseModel):
    provider_id: Optional[int] = None
    model_id: Optional[str] = Field(None, min_length=1, max_length=100)
    display_name: Optional[str] = Field(None, min_length=1, max_length=100)
    temperature: Optional[float] = Field(None, ge=0, le=2)
    max_tokens: Optional[int] = Field(None, ge=1, le=200000)
    system_prompt: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None


class ModelResponse(BaseModel):
    id: int
    provider_id: int
    provider_name: str = ""
    model_id: str
    display_name: str
    temperature: float
    max_tokens: int
    system_prompt: Optional[str]
    is_active: bool
    is_default: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================
# 知识库相关
# ============================================================
class KnowledgeUpdate(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    summary: Optional[str] = None
    keywords: Optional[List[str]] = None
    tech_stack: Optional[List[str]] = None


class KnowledgeResponse(BaseModel):
    id: int
    qdrant_id: str
    title: Optional[str]
    category: str
    summary: Optional[str]
    keywords: Optional[List[str]]
    tech_stack: Optional[List[str]]
    content_preview: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class KnowledgeListResponse(BaseModel):
    items: List[KnowledgeResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class KnowledgeDetailResponse(BaseModel):
    """知识条目详情（包含完整内容）"""
    id: int
    qdrant_id: str
    title: Optional[str]
    category: str
    summary: Optional[str]
    keywords: Optional[List[str]]
    tech_stack: Optional[List[str]]
    content: Optional[str] = None  # 完整内容（从Qdrant获取）
    content_preview: Optional[str]
    created_at: datetime
    updated_at: datetime


class KnowledgeImportRequest(BaseModel):
    entries: List[dict]  # 批量导入的条目


# ============================================================
# 通用响应
# ============================================================
class MessageResponse(BaseModel):
    message: str
    success: bool = True


class StatsResponse(BaseModel):
    total_knowledge: int
    total_providers: int
    total_models: int
    active_models: int
    categories: dict


# ============================================================
# LLM使用量统计相关
# ============================================================
class UsageLogResponse(BaseModel):
    id: int
    model_id: int
    model_name: str = ""
    provider_id: int
    provider_name: str = ""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float
    request_time: float
    status: str
    error_message: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class UsageStatsResponse(BaseModel):
    total_requests: int
    success_requests: int
    error_requests: int
    total_tokens: int
    total_cost: float
    avg_request_time: float
    by_model: List[dict]
    by_provider: List[dict]
    daily_stats: List[dict]


class TestModelRequest(BaseModel):
    model_id: int
    prompt: str
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


class TestModelResponse(BaseModel):
    success: bool
    response: Optional[str] = None
    error: Optional[str] = None
    usage: dict
    request_time: float
