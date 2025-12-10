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
    model_id: Optional[int] = None
    model_name: str = ""
    provider_id: Optional[int] = None
    provider_name: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0
    request_time: float = 0
    status: str = "success"
    error_message: Optional[str] = None
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


# ============================================================
# 评估系统相关
# ============================================================
class TestCaseCreate(BaseModel):
    """创建测试用例"""
    question: str = Field(..., min_length=1)
    expected_files: List[str] = Field(default_factory=list)
    expected_keywords: List[str] = Field(default_factory=list)
    category: str = Field(default="general")


class TestCaseUpdate(BaseModel):
    """更新测试用例"""
    question: Optional[str] = None
    expected_files: Optional[List[str]] = None
    expected_keywords: Optional[List[str]] = None
    category: Optional[str] = None


class TestCaseResponse(BaseModel):
    """测试用例响应"""
    id: str
    question: str
    expected_files: List[str]
    expected_keywords: List[str]
    category: str


class RetrievalMetrics(BaseModel):
    """检索质量指标"""
    file_recall: float
    file_hits: List[dict]
    keyword_coverage: float
    keyword_hits: List[str]
    retrieved_count: int
    avg_score: float


class AnswerMetrics(BaseModel):
    """答案质量指标"""
    keyword_coverage: float
    keyword_hits: List[str]
    is_refusal: bool
    answer_length: int


class EvalResultResponse(BaseModel):
    """单个评估结果"""
    test_case_id: str
    question: str
    category: str
    answer: Optional[str] = None
    sources: Optional[List[dict]] = None
    retrieval_metrics: Optional[RetrievalMetrics] = None
    answer_metrics: Optional[AnswerMetrics] = None
    error: Optional[str] = None
    timestamp: str


class EvalSummaryResponse(BaseModel):
    """评估汇总统计"""
    total_cases: int
    successful_cases: int
    failed_cases: int
    avg_file_recall: float
    avg_keyword_coverage_retrieval: float
    avg_keyword_coverage_answer: float
    refusal_rate: float


class EvalRunRequest(BaseModel):
    """运行评估请求"""
    test_case_ids: Optional[List[str]] = None  # 为空则运行所有
    top_k: int = Field(default=5, ge=1, le=20)


class EvalRunResponse(BaseModel):
    """评估运行响应"""
    summary: EvalSummaryResponse
    results: List[EvalResultResponse]
    timestamp: str


class CacheStatsResponse(BaseModel):
    """语义缓存统计"""
    total_entries: int
    hit_rate: float
    avg_similarity: float
    cache_size_mb: float


# ============================================================
# 知识分组相关
# ============================================================
class KnowledgeGroupCreate(BaseModel):
    """创建知识分组"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    color: str = Field(default="#1890ff", pattern="^#[0-9a-fA-F]{6}$")
    icon: str = Field(default="folder", max_length=50)


class KnowledgeGroupUpdate(BaseModel):
    """更新知识分组"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    color: Optional[str] = Field(None, pattern="^#[0-9a-fA-F]{6}$")
    icon: Optional[str] = Field(None, max_length=50)
    is_active: Optional[bool] = None


class KnowledgeGroupResponse(BaseModel):
    """知识分组响应"""
    id: int
    name: str
    description: Optional[str]
    color: str
    icon: str
    is_active: bool
    items_count: int = 0  # 分组内知识条目数量
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class KnowledgeGroupListResponse(BaseModel):
    """知识分组列表响应"""
    items: List[KnowledgeGroupResponse]
    total: int


class GroupItemsRequest(BaseModel):
    """添加/移除分组项请求"""
    qdrant_ids: List[str] = Field(..., min_length=1)


class GroupItemResponse(BaseModel):
    """分组项响应"""
    id: int
    group_id: int
    qdrant_id: str
    title: Optional[str] = None  # 从 KnowledgeEntry 关联获取
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================
# 知识版本追踪相关
# ============================================================
class KnowledgeVersionResponse(BaseModel):
    """知识版本响应"""
    id: int
    qdrant_id: str
    version: int
    change_type: str
    changed_by: Optional[str]
    change_reason: Optional[str]
    content_preview: str = ""  # 内容预览（前200字）
    created_at: datetime

    class Config:
        from_attributes = True


class KnowledgeVersionDetailResponse(BaseModel):
    """知识版本详情（包含完整内容）"""
    id: int
    qdrant_id: str
    version: int
    content: str
    metadata: Optional[dict]
    change_type: str
    changed_by: Optional[str]
    change_reason: Optional[str]
    created_at: datetime


class KnowledgeVersionListResponse(BaseModel):
    """版本历史列表响应"""
    qdrant_id: str
    current_version: int
    versions: List[KnowledgeVersionResponse]
    total: int


class RollbackRequest(BaseModel):
    """回滚请求"""
    target_version: int = Field(..., ge=1)
    reason: Optional[str] = None


class RollbackResponse(BaseModel):
    """回滚响应"""
    success: bool
    message: str
    new_version: int
    qdrant_id: str

