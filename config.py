"""
RAG 系统配置管理
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 项目根目录
BASE_DIR = Path(__file__).parent

# ============================================================
# LLM 配置（支持 Anthropic / OpenAI 格式的第三方 API）
# ============================================================
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic").lower()  # anthropic / openai
LLM_MODEL = os.getenv("LLM_MODEL", "claude-3-5-haiku-20241022")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))

# Anthropic 格式配置（支持第三方 API）
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_API_BASE = os.getenv("ANTHROPIC_API_BASE", "")  # 留空使用官方地址
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-20241022")  # 向后兼容

# OpenAI 格式配置（支持第三方 API）
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "")  # 留空使用官方地址

# ============================================================
# Qdrant 向量数据库配置
# ============================================================
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")  # 远程 Qdrant 认证密钥
QDRANT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "knowledge_base")
QDRANT_USE_HTTPS = os.getenv("QDRANT_USE_HTTPS", "false").lower() in ("1", "true", "yes")

# ============================================================
# 项目路径配置
# ============================================================
PROJECT_ROOT = Path(os.getenv("PROJECT_ROOT", str(BASE_DIR.parent)))
CODE_PATTERNS = os.getenv("CODE_PATTERNS", "*.php,*.js,*.vue,*.md").split(",")
IGNORE_PATTERNS = os.getenv("IGNORE_PATTERNS", "node_modules/**,vendor/**,storage/**,.git/**").split(",")

# ============================================================
# 嵌入模型配置
# ============================================================
# EMBEDDING_PROVIDER: "local" 使用本地模型, "api" 使用 OpenAI 格式 API
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "local")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")  # 本地: 模型名, API: 模型ID
EMBEDDING_DEVICE = os.getenv("EMBEDDING_DEVICE", "cpu")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))  # BGE-M3: 1024, OpenAI: 1536/3072

# API 嵌入配置（当 EMBEDDING_PROVIDER=api 时使用）
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", "")
EMBEDDING_API_BASE = os.getenv("EMBEDDING_API_BASE", "https://api.openai.com")  # 支持第三方

# ============================================================
# 检索配置
# ============================================================
TOP_K = int(os.getenv("TOP_K", "5"))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "512"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))

# ============================================================
# Reranker 重排配置
# ============================================================
RERANKER_ENABLE = os.getenv("RERANKER_ENABLE", "1").lower() in ("1", "true", "yes")
RERANKER_MODEL_NAME = os.getenv("RERANKER_MODEL_NAME", "BAAI/bge-reranker-base")
RERANKER_DEVICE = os.getenv("RERANKER_DEVICE", "cpu")
RERANKER_TOP_K_MULTIPLIER = int(os.getenv("RERANKER_TOP_K_MULTIPLIER", "3"))
RERANKER_MAX_LENGTH = int(os.getenv("RERANKER_MAX_LENGTH", "512"))
RERANKER_BATCH_SIZE = int(os.getenv("RERANKER_BATCH_SIZE", "8"))  # 批处理大小
RERANKER_CACHE_SIZE = int(os.getenv("RERANKER_CACHE_SIZE", "100"))  # 缓存条目数
RERANKER_CACHE_TTL = int(os.getenv("RERANKER_CACHE_TTL", "300"))  # 缓存过期时间（秒）

# ============================================================
# Query 改写配置
# ============================================================
QUERY_REWRITE_ENABLE = os.getenv("QUERY_REWRITE_ENABLE", "1").lower() in ("1", "true", "yes")
QUERY_REWRITE_STRATEGY = os.getenv("QUERY_REWRITE_STRATEGY", "multi_query")  # multi_query / hyde
QUERY_REWRITE_NUM_VARIANTS = int(os.getenv("QUERY_REWRITE_NUM_VARIANTS", "3"))

# ============================================================
# 向量索引优化配置
# ============================================================
VECTOR_OPTIMIZE_ON_STARTUP = os.getenv("VECTOR_OPTIMIZE_ON_STARTUP", "1").lower() in ("1", "true", "yes")
VECTOR_OPTIMIZE_PROFILE = os.getenv("VECTOR_OPTIMIZE_PROFILE", "balanced")  # default, high_recall, fast_search, balanced
VECTOR_WARMUP_QUERIES = int(os.getenv("VECTOR_WARMUP_QUERIES", "50"))

# ============================================================
# Contextual Chunking 配置（上下文感知切分）
# ============================================================
CONTEXT_PREFIX_ENABLE = os.getenv("CONTEXT_PREFIX_ENABLE", "1").lower() in ("1", "true", "yes")
CONTEXT_PREFIX_MAX_LEN = int(os.getenv("CONTEXT_PREFIX_MAX_LEN", "100"))  # 前缀最大长度
CONTEXT_INJECT_TO_CONTENT = os.getenv("CONTEXT_INJECT_TO_CONTENT", "1").lower() in ("1", "true", "yes")  # 是否注入到内容

# ============================================================
# 对话摘要压缩配置
# ============================================================
CONVERSATION_SUMMARIZE_ENABLE = os.getenv("CONVERSATION_SUMMARIZE_ENABLE", "1").lower() in ("1", "true", "yes")
CONVERSATION_MAX_HISTORY_TURNS = int(os.getenv("CONVERSATION_MAX_HISTORY_TURNS", "10"))  # 超过此轮数触发摘要
CONVERSATION_KEEP_RECENT_TURNS = int(os.getenv("CONVERSATION_KEEP_RECENT_TURNS", "4"))  # 保留最近 N 轮完整对话
CONVERSATION_MAX_SUMMARY_CHARS = int(os.getenv("CONVERSATION_MAX_SUMMARY_CHARS", "1000"))  # 摘要最大字符数

# ============================================================
# 日志配置
# ============================================================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "rag.log"

# 确保日志目录存在
LOG_DIR.mkdir(exist_ok=True)

# ============================================================
# 配置验证
# ============================================================
def validate_config():
    """验证必需配置"""
    if LLM_PROVIDER == "anthropic" and not ANTHROPIC_API_KEY:
        raise ValueError("使用 Anthropic 格式时，ANTHROPIC_API_KEY 必须配置")
    if LLM_PROVIDER == "openai" and not OPENAI_API_KEY:
        raise ValueError("使用 OpenAI 格式时，OPENAI_API_KEY 必须配置")

# 延迟验证（在实际使用时验证，避免导入时报错）
