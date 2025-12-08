"""
LLM 抽象层：支持 Anthropic 与 OpenAI 格式的第三方 API
"""
from typing import List, Dict, Optional
from abc import ABC, abstractmethod

from utils.logger import logger


class BaseLLM(ABC):
    """LLM 基类"""

    @abstractmethod
    def invoke(self, messages: List[Dict[str, str]]) -> str:
        """
        调用 LLM 生成回复

        Args:
            messages: 消息列表，格式为 [{"role": "user/assistant", "content": "..."}]

        Returns:
            生成的回复文本
        """
        pass


class AnthropicLLM(BaseLLM):
    """Anthropic 格式 LLM（支持第三方 API）"""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096
    ):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

        # 使用 anthropic SDK，支持自定义 base_url
        import anthropic
        import httpx

        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url

        # 增加超时时间（默认 60 秒可能不够）
        client_kwargs["timeout"] = httpx.Timeout(120.0, connect=30.0)

        self.client = anthropic.Anthropic(**client_kwargs)
        logger.info(f"AnthropicLLM 初始化: model={model}, base_url={base_url or 'default'}")

    def invoke(self, messages: List[Dict[str, str]]) -> str:
        """调用 Anthropic 格式 API"""
        try:
            # 转换消息格式
            api_messages = []
            for msg in messages:
                api_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })

            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=api_messages
            )

            return response.content[0].text

        except Exception as e:
            logger.error(f"AnthropicLLM 调用失败: {e}")
            raise


class OpenAILLM(BaseLLM):
    """OpenAI 格式 LLM（支持第三方 API）"""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096
    ):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

        # 使用 openai SDK，支持自定义 base_url
        from openai import OpenAI

        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url

        self.client = OpenAI(**client_kwargs)
        logger.info(f"OpenAILLM 初始化: model={model}, base_url={base_url or 'default'}")

    def invoke(self, messages: List[Dict[str, str]]) -> str:
        """调用 OpenAI 格式 API"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"OpenAILLM 调用失败: {e}")
            raise


def get_default_model_from_db():
    """
    从数据库获取默认 LLM 模型配置

    Returns:
        dict: 包含模型和供应商信息的字典，如果没有默认模型则返回 None
    """
    try:
        from admin.database import SessionLocal
        from admin.models import LLMModel, LLMProvider

        db = SessionLocal()
        try:
            # 查找默认模型
            model = db.query(LLMModel).filter(
                LLMModel.is_default == True,
                LLMModel.is_active == True
            ).first()

            if not model:
                return None

            # 获取关联的供应商
            provider = db.query(LLMProvider).filter(
                LLMProvider.id == model.provider_id,
                LLMProvider.is_active == True
            ).first()

            if not provider:
                return None

            return {
                "model_id": model.model_id,
                "temperature": float(model.temperature),
                "max_tokens": model.max_tokens,
                "system_prompt": model.system_prompt,
                "api_format": provider.api_format,
                "api_key": provider.api_key,
                "base_url": provider.base_url
            }
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"从数据库获取默认模型失败: {e}")
        return None


def get_llm_client() -> BaseLLM:
    """
    根据配置获取 LLM 客户端
    优先使用数据库中的默认模型配置，如果没有则使用 .env 配置

    Returns:
        BaseLLM 实例
    """
    # 尝试从数据库获取默认模型
    db_config = get_default_model_from_db()

    if db_config:
        logger.info(f"使用数据库配置的默认模型: {db_config['model_id']}")

        if db_config["api_format"] == "openai":
            return OpenAILLM(
                api_key=db_config["api_key"],
                model=db_config["model_id"],
                base_url=db_config["base_url"] or None,
                temperature=db_config["temperature"],
                max_tokens=db_config["max_tokens"]
            )
        else:
            return AnthropicLLM(
                api_key=db_config["api_key"],
                model=db_config["model_id"],
                base_url=db_config["base_url"] or None,
                temperature=db_config["temperature"],
                max_tokens=db_config["max_tokens"]
            )

    # 回退到 .env 配置
    logger.info("数据库无默认模型，使用 .env 配置")
    from config import (
        LLM_PROVIDER,
        LLM_MODEL,
        LLM_TEMPERATURE,
        LLM_MAX_TOKENS,
        ANTHROPIC_API_KEY,
        ANTHROPIC_API_BASE,
        OPENAI_API_KEY,
        OPENAI_API_BASE,
    )

    provider = LLM_PROVIDER.lower()

    if provider == "openai":
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY 未配置")
        return OpenAILLM(
            api_key=OPENAI_API_KEY,
            model=LLM_MODEL,
            base_url=OPENAI_API_BASE or None,
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS
        )
    else:
        # 默认使用 Anthropic 格式
        if not ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY 未配置")
        return AnthropicLLM(
            api_key=ANTHROPIC_API_KEY,
            model=LLM_MODEL,
            base_url=ANTHROPIC_API_BASE or None,
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS
        )
