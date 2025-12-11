"""
配置管理单例 - 统一管理所有配置读取
"""
from functools import lru_cache
from typing import Dict, Optional
from config import (
    QDRANT_HOST, QDRANT_PORT, QDRANT_API_KEY,
    QDRANT_COLLECTION_NAME, QDRANT_USE_HTTPS,
    LLM_PROVIDER, LLM_MODEL, ANTHROPIC_API_KEY, ANTHROPIC_API_BASE,
    OPENAI_API_KEY, OPENAI_API_BASE
)


class ConfigManager:
    """
    配置管理单例

    提供统一的配置访问接口,避免在多处重复读取环境变量
    使用 @lru_cache 缓存配置对象,提升性能
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    @lru_cache(maxsize=1)
    def qdrant_config(self) -> Dict[str, any]:
        """Qdrant 向量数据库配置"""
        return {
            'host': QDRANT_HOST,
            'port': QDRANT_PORT,
            'api_key': QDRANT_API_KEY,
            'collection': QDRANT_COLLECTION_NAME,
            'use_https': QDRANT_USE_HTTPS
        }

    @property
    def qdrant_url(self) -> str:
        """Qdrant 连接URL"""
        protocol = "https" if QDRANT_USE_HTTPS else "http"
        return f"{protocol}://{QDRANT_HOST}:{QDRANT_PORT}"

    @property
    @lru_cache(maxsize=1)
    def llm_config(self) -> Dict[str, Optional[str]]:
        """LLM 配置"""
        return {
            'provider': LLM_PROVIDER,
            'model': LLM_MODEL,
            'anthropic_api_key': ANTHROPIC_API_KEY,
            'anthropic_api_base': ANTHROPIC_API_BASE,
            'openai_api_key': OPENAI_API_KEY,
            'openai_api_base': OPENAI_API_BASE
        }


def get_config() -> ConfigManager:
    """获取配置管理器实例"""
    return ConfigManager()
