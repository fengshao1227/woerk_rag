"""
SQLAlchemy 数据模型
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DECIMAL, Enum, ForeignKey, TIMESTAMP, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from admin.database import Base


class User(Base):
    """用户表"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum('admin', 'user'), default='user')
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


class LLMProvider(Base):
    """LLM供应商表"""
    __tablename__ = "llm_providers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    api_format = Column(Enum('anthropic', 'openai'), nullable=False)
    api_key = Column(String(500), nullable=False)
    base_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    request_timeout = Column(Integer, default=120)
    max_concurrent = Column(Integer, default=10)
    monthly_budget = Column(DECIMAL(10, 2), nullable=True)
    current_usage = Column(DECIMAL(10, 2), default=0)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    # 关联模型
    models = relationship("LLMModel", back_populates="provider", cascade="all, delete-orphan")


class LLMModel(Base):
    """LLM模型表"""
    __tablename__ = "llm_models"

    id = Column(Integer, primary_key=True, index=True)
    provider_id = Column(Integer, ForeignKey("llm_providers.id", ondelete="CASCADE"), nullable=False)
    model_id = Column(String(100), nullable=False)
    display_name = Column(String(100), nullable=False)
    temperature = Column(DECIMAL(3, 2), default=0.70)
    max_tokens = Column(Integer, default=4096)
    system_prompt = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    # 关联供应商
    provider = relationship("LLMProvider", back_populates="models")


class KnowledgeEntry(Base):
    """知识条目索引表"""
    __tablename__ = "knowledge_entries"

    id = Column(Integer, primary_key=True, index=True)
    qdrant_id = Column(String(64), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=True)
    category = Column(String(50), default='general', index=True)
    summary = Column(Text, nullable=True)
    keywords = Column(JSON, nullable=True)
    tech_stack = Column(JSON, nullable=True)
    content_preview = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now(), index=True)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


class LLMUsageLog(Base):
    """LLM使用记录表 - 完整审计日志"""
    __tablename__ = "llm_usage_logs"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("llm_models.id", ondelete="SET NULL"), nullable=True, index=True)
    provider_id = Column(Integer, ForeignKey("llm_providers.id", ondelete="SET NULL"), nullable=True, index=True)

    # 用户信息
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    username = Column(String(50), nullable=True)  # 冗余存储，防止用户删除后丢失

    # 请求类型
    request_type = Column(Enum('query', 'search', 'test', 'add_knowledge', 'other'), default='query', index=True)

    # 请求内容（用于审计和调试）
    question = Column(Text, nullable=True)  # 用户问题
    answer_preview = Column(Text, nullable=True)  # 回答预览（前500字）

    # Token 统计
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    cost = Column(DECIMAL(10, 4), default=0)

    # 性能指标
    request_time = Column(DECIMAL(10, 3), default=0)  # LLM 请求耗时
    total_time = Column(DECIMAL(10, 3), default=0)  # 总耗时（含检索）

    # 检索信息
    retrieval_count = Column(Integer, default=0)  # 检索到的文档数
    rerank_used = Column(Boolean, default=False)  # 是否使用了重排

    # 状态
    status = Column(Enum('success', 'error'), default='success')
    error_message = Column(Text, nullable=True)

    # 客户端信息
    client_ip = Column(String(50), nullable=True)
    user_agent = Column(String(500), nullable=True)

    created_at = Column(TIMESTAMP, server_default=func.now(), index=True)

    # 关联
    model = relationship("LLMModel")
    provider = relationship("LLMProvider")
    user = relationship("User")
