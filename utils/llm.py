"""
LLM 抽象层：支持 Anthropic 与 OpenAI 格式的第三方 API
使用 curl_cffi 绕过 Cloudflare 保护
支持流式输出 (SSE)
"""
from typing import List, Dict, Optional, AsyncGenerator, Generator
from abc import ABC, abstractmethod
import json

from utils.logger import logger


class LLMResponse:
    """LLM 响应封装类"""

    def __init__(self, content: str, usage: Optional[Dict[str, int]] = None):
        self.content = content
        self.usage = usage or {"input_tokens": 0, "output_tokens": 0}

    @property
    def input_tokens(self) -> int:
        return self.usage.get("input_tokens", 0)

    @property
    def output_tokens(self) -> int:
        return self.usage.get("output_tokens", 0)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def __str__(self) -> str:
        """兼容旧代码，直接转字符串返回 content"""
        return self.content


class BaseLLM(ABC):
    """LLM 基类"""

    @abstractmethod
    def invoke(self, messages: List[Dict[str, str]]) -> LLMResponse:
        """
        调用 LLM 生成回复

        Args:
            messages: 消息列表，格式为 [{"role": "user/assistant", "content": "..."}]

        Returns:
            LLMResponse 对象，包含 content 和 usage 信息
        """
        pass

    @abstractmethod
    def invoke_stream(self, messages: List[Dict[str, str]]) -> Generator[str, None, None]:
        """
        流式调用 LLM 生成回复

        Args:
            messages: 消息列表，格式为 [{"role": "user/assistant", "content": "..."}]

        Yields:
            生成的文本片段
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

    def invoke(self, messages: List[Dict[str, str]], max_retries: int = 3) -> LLMResponse:
        """调用 Anthropic 格式 API，带重试机制"""
        import time
        import random

        try:
            from curl_cffi import requests as cffi_requests
        except ImportError:
            logger.warning("curl_cffi 未安装，使用标准 requests")
            import requests as cffi_requests

        url = f"{self.base_url.rstrip('/')}/v1/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
        }
        api_messages = [{"role": msg["role"], "content": msg["content"]} for msg in messages]
        data = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": api_messages
        }

        last_error = None
        for attempt in range(max_retries):
            try:
                # 随机选择浏览器指纹，增加绕过 WAF 成功率
                fingerprints = ["chrome120", "chrome119", "chrome110", "edge101", "safari15_5"]
                fingerprint = random.choice(fingerprints)

                response = cffi_requests.post(
                    url,
                    headers=headers,
                    json=data,
                    timeout=120,
                    impersonate=fingerprint
                )

                # 检查是否被 WAF 拦截（返回 HTML 而不是 JSON）
                if response.status_code != 200:
                    response_text = response.text
                    if "<!doctype html>" in response_text.lower() or "bunker" in response_text.lower():
                        logger.warning(f"请求被 WAF 拦截 (尝试 {attempt + 1}/{max_retries})，切换指纹重试...")
                        last_error = Exception(f"API 被 WAF 拦截: {response.status_code}")
                        time.sleep(1 + random.random())  # 随机延迟 1-2 秒
                        continue
                    raise Exception(f"API 错误: {response.status_code} - {response_text}")

                result = response.json()

                # 解析 usage 信息 (Anthropic 格式)
                usage = {"input_tokens": 0, "output_tokens": 0}
                if "usage" in result:
                    usage["input_tokens"] = result["usage"].get("input_tokens", 0)
                    usage["output_tokens"] = result["usage"].get("output_tokens", 0)

                # 解析响应内容 - 兼容多种格式
                content_text = ""
                if "content" in result:
                    content = result["content"]
                    # Anthropic 标准格式: content 是列表
                    if isinstance(content, list) and len(content) > 0:
                        first_item = content[0]
                        if isinstance(first_item, dict) and "text" in first_item:
                            content_text = first_item["text"]
                        elif isinstance(first_item, str):
                            content_text = first_item
                        else:
                            content_text = str(first_item)
                    # content 直接是字符串
                    elif isinstance(content, str):
                        content_text = content
                elif "error" in result:
                    raise Exception(f"API 错误: {result['error']}")
                else:
                    content_text = str(result)

                return LLMResponse(content=content_text, usage=usage)

            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    logger.warning(f"请求失败 (尝试 {attempt + 1}/{max_retries}): {e}，重试中...")
                    time.sleep(1 + random.random())
                    continue
                raise

        # 所有重试都失败
        if last_error:
            logger.error(f"AnthropicLLM 调用失败（已重试 {max_retries} 次）: {last_error}")
            raise last_error

    def invoke_stream(self, messages: List[Dict[str, str]], max_retries: int = 3) -> Generator[str, None, None]:
        """流式调用 Anthropic 格式 API"""
        import time
        import random

        try:
            from curl_cffi import requests as cffi_requests
        except ImportError:
            logger.warning("curl_cffi 未安装，使用标准 requests")
            import requests as cffi_requests

        url = f"{self.base_url.rstrip('/')}/v1/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/event-stream",
        }
        api_messages = [{"role": msg["role"], "content": msg["content"]} for msg in messages]
        data = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": api_messages,
            "stream": True
        }

        last_error = None
        for attempt in range(max_retries):
            try:
                fingerprints = ["chrome120", "chrome119", "chrome110", "edge101", "safari15_5"]
                fingerprint = random.choice(fingerprints)

                response = cffi_requests.post(
                    url,
                    headers=headers,
                    json=data,
                    timeout=120,
                    impersonate=fingerprint,
                    stream=True
                )

                if response.status_code != 200:
                    response_text = response.text
                    if "<!doctype html>" in response_text.lower() or "bunker" in response_text.lower():
                        logger.warning(f"流式请求被 WAF 拦截 (尝试 {attempt + 1}/{max_retries})，重试...")
                        last_error = Exception(f"API 被 WAF 拦截: {response.status_code}")
                        time.sleep(1 + random.random())
                        continue
                    raise Exception(f"API 错误: {response.status_code} - {response_text}")

                # 解析 SSE 流
                for line in response.iter_lines():
                    if not line:
                        continue
                    line_str = line.decode('utf-8') if isinstance(line, bytes) else line
                    if line_str.startswith('data: '):
                        data_str = line_str[6:]
                        if data_str == '[DONE]':
                            break
                        try:
                            chunk_data = json.loads(data_str)
                            # Anthropic 流式格式
                            if chunk_data.get("type") == "content_block_delta":
                                delta = chunk_data.get("delta", {})
                                text = delta.get("text", "")
                                if text:
                                    yield text
                        except json.JSONDecodeError:
                            continue
                return

            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    logger.warning(f"流式请求失败 (尝试 {attempt + 1}/{max_retries}): {e}，重试中...")
                    time.sleep(1 + random.random())
                    continue
                raise

        if last_error:
            logger.error(f"AnthropicLLM 流式调用失败（已重试 {max_retries} 次）: {last_error}")
            raise last_error


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

    def invoke(self, messages: List[Dict[str, str]], max_retries: int = 3) -> LLMResponse:
        """调用 OpenAI 格式 API，带重试机制"""
        import time
        import random

        try:
            from curl_cffi import requests as cffi_requests
        except ImportError:
            logger.warning("curl_cffi 未安装，使用标准 requests")
            import requests as cffi_requests

        # 构建请求 URL
        base = self.base_url.rstrip('/')
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

        last_error = None
        for attempt in range(max_retries):
            try:
                # 随机选择浏览器指纹
                fingerprints = ["chrome120", "chrome119", "chrome110", "edge101", "safari15_5"]
                fingerprint = random.choice(fingerprints)

                response = cffi_requests.post(
                    url,
                    headers=headers,
                    json=data,
                    timeout=120,
                    impersonate=fingerprint
                )

                # 检查是否被 WAF 或内容审核拦截
                if response.status_code != 200:
                    response_text = response.text
                    # WAF 拦截或内容审核拦截，可以重试
                    if any(x in response_text.lower() for x in ["<!doctype html>", "bunker", "moderation", "blocked"]):
                        logger.warning(f"请求被拦截 (尝试 {attempt + 1}/{max_retries})，重试中...")
                        last_error = Exception(f"API 被拦截: {response.status_code}")
                        time.sleep(1 + random.random())
                        continue
                    raise Exception(f"API 错误: {response.status_code} - {response_text}")

                result = response.json()

                # 解析 usage 信息 (OpenAI 格式: prompt_tokens, completion_tokens)
                usage = {"input_tokens": 0, "output_tokens": 0}
                if "usage" in result:
                    usage["input_tokens"] = result["usage"].get("prompt_tokens", 0)
                    usage["output_tokens"] = result["usage"].get("completion_tokens", 0)

                # 兼容不同的返回格式
                content_text = ""
                if isinstance(result, str):
                    content_text = result
                elif isinstance(result, dict):
                    if "choices" in result and len(result["choices"]) > 0:
                        choice = result["choices"][0]
                        if "message" in choice:
                            content = choice["message"].get("content", "")
                            if isinstance(content, list) and len(content) > 0:
                                first_item = content[0]
                                if isinstance(first_item, dict) and "text" in first_item:
                                    content_text = first_item["text"]
                                else:
                                    content_text = str(first_item)
                            else:
                                content_text = content if isinstance(content, str) else str(content)
                        elif "text" in choice:
                            content_text = choice["text"]
                    elif "content" in result:
                        content = result["content"]
                        if isinstance(content, list) and len(content) > 0:
                            first_item = content[0]
                            if isinstance(first_item, dict) and "text" in first_item:
                                content_text = first_item["text"]
                            else:
                                content_text = str(first_item)
                        else:
                            content_text = content if isinstance(content, str) else str(content)
                    elif "text" in result:
                        content_text = result["text"]
                    elif "error" in result:
                        raise Exception(f"API 错误: {result['error']}")
                    else:
                        content_text = str(result)

                return LLMResponse(content=content_text, usage=usage)

            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    logger.warning(f"请求失败 (尝试 {attempt + 1}/{max_retries}): {e}，重试中...")
                    time.sleep(1 + random.random())
                    continue
                raise

        # 所有重试都失败
        if last_error:
            logger.error(f"OpenAILLM 调用失败（已重试 {max_retries} 次）: {last_error}")
            raise last_error

    def invoke_stream(self, messages: List[Dict[str, str]], max_retries: int = 3) -> Generator[str, None, None]:
        """流式调用 OpenAI 格式 API"""
        import time
        import random

        try:
            from curl_cffi import requests as cffi_requests
        except ImportError:
            logger.warning("curl_cffi 未安装，使用标准 requests")
            import requests as cffi_requests

        base = self.base_url.rstrip('/')
        if not base.endswith('/v1'):
            base = f"{base}/v1"
        url = f"{base}/chat/completions"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/event-stream",
        }
        data = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": True
        }

        last_error = None
        for attempt in range(max_retries):
            try:
                fingerprints = ["chrome120", "chrome119", "chrome110", "edge101", "safari15_5"]
                fingerprint = random.choice(fingerprints)

                response = cffi_requests.post(
                    url,
                    headers=headers,
                    json=data,
                    timeout=120,
                    impersonate=fingerprint,
                    stream=True
                )

                if response.status_code != 200:
                    response_text = response.text
                    if any(x in response_text.lower() for x in ["<!doctype html>", "bunker", "moderation", "blocked"]):
                        logger.warning(f"流式请求被拦截 (尝试 {attempt + 1}/{max_retries})，重试...")
                        last_error = Exception(f"API 被拦截: {response.status_code}")
                        time.sleep(1 + random.random())
                        continue
                    raise Exception(f"API 错误: {response.status_code} - {response_text}")

                # 解析 SSE 流
                for line in response.iter_lines():
                    if not line:
                        continue
                    line_str = line.decode('utf-8') if isinstance(line, bytes) else line
                    if line_str.startswith('data: '):
                        data_str = line_str[6:]
                        if data_str == '[DONE]':
                            break
                        try:
                            chunk_data = json.loads(data_str)
                            # OpenAI 流式格式
                            choices = chunk_data.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            continue
                return

            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    logger.warning(f"流式请求失败 (尝试 {attempt + 1}/{max_retries}): {e}，重试中...")
                    time.sleep(1 + random.random())
                    continue
                raise

        if last_error:
            logger.error(f"OpenAILLM 流式调用失败（已重试 {max_retries} 次）: {last_error}")
            raise last_error


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
