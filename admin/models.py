"""
SQLAlchemy 数据模型
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DECIMAL, Enum, ForeignKey, TIMESTAMP, JSON, UniqueConstraint, Index
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
    request_type = Column(Enum('query', 'query_stream', 'search', 'test', 'add_knowledge', 'agent', 'mcp', 'other'), default='query', index=True)

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


class KnowledgeGroup(Base):
    """知识分组表 - 支持按项目/主题组织知识"""
    __tablename__ = "knowledge_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)
    color = Column(String(20), default='#1890ff')  # 用于前端显示的颜色
    icon = Column(String(50), default='folder')  # 图标名称
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    # 关联分组项
    items = relationship("KnowledgeGroupItem", back_populates="group", cascade="all, delete-orphan")


class KnowledgeGroupItem(Base):
    """知识分组关联表 - 多对多关系"""
    __tablename__ = "knowledge_group_items"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("knowledge_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    qdrant_id = Column(String(64), nullable=False, index=True)  # 关联 Qdrant 中的知识点
    created_at = Column(TIMESTAMP, server_default=func.now())

    # 关联分组
    group = relationship("KnowledgeGroup", back_populates="items")

    # 联合唯一约束：同一知识不能重复加入同一分组
    __table_args__ = (
        UniqueConstraint('group_id', 'qdrant_id', name='uq_group_qdrant'),
        {'mysql_charset': 'utf8mb4'},
    )


class KnowledgeVersion(Base):
    """知识版本历史表 - 全量快照模式"""
    __tablename__ = "knowledge_versions"

    id = Column(Integer, primary_key=True, index=True)
    qdrant_id = Column(String(64), nullable=False, index=True)  # 关联 Qdrant 中的知识点
    version = Column(Integer, nullable=False, default=1)  # 版本号
    content = Column(Text, nullable=False)  # 完整内容快照
    version_metadata = Column(JSON, nullable=True)  # 元数据快照 (避免与 Base.metadata 冲突)
    change_type = Column(Enum('create', 'update', 'delete'), default='create')  # 变更类型
    changed_by = Column(String(50), nullable=True)  # 操作人
    change_reason = Column(String(255), nullable=True)  # 变更原因
    created_at = Column(TIMESTAMP, server_default=func.now(), index=True)

    # 联合索引：加速按知识ID查询版本历史
    __table_args__ = (
        {'mysql_charset': 'utf8mb4'},
    )


class EmbeddingProvider(Base):
    """嵌入模型供应商表"""
    __tablename__ = "embedding_providers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)

    # API配置
    api_base_url = Column(String(500), nullable=False)
    api_key = Column(String(500), nullable=False)
    model_name = Column(String(100), nullable=False)

    # 配置参数
    embedding_dim = Column(Integer, default=1024)
    max_batch_size = Column(Integer, default=32)
    request_timeout = Column(Integer, default=30)

    # 状态管理
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False, index=True)

    # 监控统计
    monthly_budget = Column(DECIMAL(10, 2), nullable=True)
    current_usage = Column(DECIMAL(10, 2), default=0)

    # 时间戳
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


class KnowledgeTask(Base):
    """知识添加任务表（异步队列）"""
    __tablename__ = "knowledge_tasks"

    id = Column(String(32), primary_key=True)  # MD5 hash
    status = Column(
        Enum('pending', 'processing', 'completed', 'failed'),
        default='pending',
        index=True
    )

    # 任务内容
    content = Column(Text, nullable=False)
    title = Column(String(255), nullable=True)
    category = Column(String(50), default='general')
    group_names = Column(JSON, nullable=True)  # 分组列表

    # 处理结果
    result_id = Column(String(64), nullable=True)  # 成功后的 qdrant_id
    error_message = Column(Text, nullable=True)  # 失败原因

    # 用户关联
    user_id = Column(Integer, nullable=True, index=True)
    username = Column(String(50), nullable=True)

    # 时间戳
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_status_created', 'status', 'created_at'),
        {'mysql_charset': 'utf8mb4'},
    )
