"""
LLM 抽象层：支持 Anthropic 与 OpenAI 格式的第三方 API
使用 curl_cffi 绕过 Cloudflare 保护
"""
from typing import List, Dict, Optional
from abc import ABC, abstractmethod
import json

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
    """Anthropic 格式 LLM（支持第三方 API，使用 curl_cffi 绕过 Cloudflare）"""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url or "https://api.anthropic.com"
        self.temperature = temperature
        self.max_tokens = max_tokens
        logger.info(f"AnthropicLLM 初始化: model={model}, base_url={self.base_url}")

    def invoke(self, messages: List[Dict[str, str]]) -> str:
        """调用 Anthropic 格式 API"""
        try:
            from curl_cffi import requests as cffi_requests
        except ImportError:
            # 如果没有 curl_cffi，回退到普通请求
            logger.warning("curl_cffi 未安装，使用标准 requests")
            import requests as cffi_requests

        try:
            # 构建请求
            url = f"{self.base_url.rstrip('/')}/v1/messages"
            headers = {
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json",
            }

            # 转换消息格式
            api_messages = [{"role": msg["role"], "content": msg["content"]} for msg in messages]

            data = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "messages": api_messages
            }

            # 使用 curl_cffi 发送请求（模拟 Chrome 浏览器指纹）
            response = cffi_requests.post(
                url,
                headers=headers,
                json=data,
                timeout=120,
                impersonate="chrome120"  # 模拟 Chrome 120 的 TLS 指纹
            )

            if response.status_code != 200:
                raise Exception(f"API 错误: {response.status_code} - {response.text}")

            result = response.json()

            # 解析响应 - 兼容多种格式
            if "content" in result:
                content = result["content"]
                # Anthropic 标准格式: content 是列表
                if isinstance(content, list) and len(content) > 0:
                    first_item = content[0]
                    if isinstance(first_item, dict) and "text" in first_item:
                        return first_item["text"]
                    elif isinstance(first_item, str):
                        return first_item
                    else:
                        return str(first_item)
                # content 直接是字符串
                elif isinstance(content, str):
                    return content
            elif "error" in result:
                raise Exception(f"API 错误: {result['error']}")

            return str(result)

        except Exception as e:
            logger.error(f"AnthropicLLM 调用失败: {e}")
            raise


class OpenAILLM(BaseLLM):
    """OpenAI 格式 LLM（支持第三方 API，使用 curl_cffi 绕过 Cloudflare）"""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url or "https://api.openai.com/v1"
        self.temperature = temperature
        self.max_tokens = max_tokens
        logger.info(f"OpenAILLM 初始化: model={model}, base_url={self.base_url}")

    def invoke(self, messages: List[Dict[str, str]]) -> str:
        """调用 OpenAI 格式 API"""
        try:
            from curl_cffi import requests as cffi_requests
        except ImportError:
            # 如果没有 curl_cffi，回退到普通请求
            logger.warning("curl_cffi 未安装，使用标准 requests")
            import requests as cffi_requests

        try:
            # 构建请求 URL
            base = self.base_url.rstrip('/')
            # 如果 base_url 不以 /v1 结尾，添加 /v1
            if not base.endswith('/v1'):
                base = f"{base}/v1"
            url = f"{base}/chat/completions"

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json",
                "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
            }

            data = {
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens
            }

            # 使用 curl_cffi 发送请求（模拟 Chrome 浏览器指纹）
            response = cffi_requests.post(
                url,
                headers=headers,
                json=data,
                timeout=120,
                impersonate="chrome120"  # 模拟 Chrome 120 的 TLS 指纹
            )

            if response.status_code != 200:
                raise Exception(f"API 错误: {response.status_code} - {response.text}")

            result = response.json()

            # 兼容不同的返回格式
            if isinstance(result, str):
                return result
            elif isinstance(result, dict):
                if "choices" in result and len(result["choices"]) > 0:
                    choice = result["choices"][0]
                    if "message" in choice:
                        content = choice["message"].get("content", "")
                        # 处理 content 可能是列表的情况
                        if isinstance(content, list) and len(content) > 0:
                            first_item = content[0]
                            if isinstance(first_item, dict) and "text" in first_item:
                                return first_item["text"]
                            return str(first_item)
                        return content if isinstance(content, str) else str(content)
                    elif "text" in choice:
                        return choice["text"]
                elif "content" in result:
                    content = result["content"]
                    if isinstance(content, list) and len(content) > 0:
                        first_item = content[0]
                        if isinstance(first_item, dict) and "text" in first_item:
                            return first_item["text"]
                        return str(first_item)
                    return content if isinstance(content, str) else str(content)
                elif "text" in result:
                    return result["text"]
                elif "error" in result:
                    raise Exception(f"API 错误: {result['error']}")

            return str(result)

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
