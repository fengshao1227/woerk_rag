"""
嵌入模型工具 - 支持本地模型和 API 调用
"""
import os
import numpy as np
from typing import List, Union
import httpx

from utils.logger import logger


class APIEmbeddingModel:
    """API 嵌入模型（OpenAI 格式）"""

    def __init__(self, api_key: str, base_url: str, model: str = "text-embedding-3-small"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._dim = None
        logger.info(f"使用 API 嵌入模型: {model} @ {base_url}")

    def encode(
        self,
        texts: Union[str, List[str]],
        batch_size: int = 32,
        show_progress_bar: bool = False
    ) -> np.ndarray:
        """调用 API 生成嵌入向量"""
        if isinstance(texts, str):
            texts = [texts]

        all_embeddings = []

        # 分批处理
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            embeddings = self._call_api(batch)
            all_embeddings.extend(embeddings)

        result = np.array(all_embeddings, dtype=np.float32)
        # 归一化
        norms = np.linalg.norm(result, axis=1, keepdims=True)
        result = result / np.maximum(norms, 1e-9)

        return result

    def _call_api(self, texts: List[str]) -> List[List[float]]:
        """调用 OpenAI 格式 Embedding API"""
        url = f"{self.base_url}/v1/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.model,
            "input": texts
        }

        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(url, json=data, headers=headers)
                response.raise_for_status()
                result = response.json()

                # 按 index 排序（API 可能不按顺序返回）
                embeddings_data = sorted(result["data"], key=lambda x: x["index"])
                embeddings = [item["embedding"] for item in embeddings_data]

                # 记录维度
                if self._dim is None and embeddings:
                    self._dim = len(embeddings[0])
                    logger.info(f"API 嵌入维度: {self._dim}")

                return embeddings

        except Exception as e:
            logger.error(f"API 嵌入调用失败: {e}")
            raise

    def get_embedding_dim(self) -> int:
        """获取嵌入维度"""
        if self._dim is None:
            # 调用一次获取维度
            self.encode("test")
        return self._dim or 1536  # OpenAI 默认维度


class LocalEmbeddingModel:
    """本地嵌入模型（SentenceTransformer）"""

    def __init__(self, model_name: str, device: str = "cpu"):
        from sentence_transformers import SentenceTransformer
        import torch

        actual_device = "cuda" if torch.cuda.is_available() and device == "cuda" else "cpu"
        self._model = SentenceTransformer(model_name, device=actual_device)
        logger.info(f"加载本地嵌入模型: {model_name} (设备: {actual_device})")

    def encode(
        self,
        texts: Union[str, List[str]],
        batch_size: int = 32,
        show_progress_bar: bool = False
    ) -> np.ndarray:
        """生成嵌入向量"""
        if isinstance(texts, str):
            texts = [texts]
        return self._model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress_bar,
            normalize_embeddings=True
        )

    def get_embedding_dim(self) -> int:
        """获取嵌入维度"""
        return self._model.get_sentence_embedding_dimension()


class EmbeddingModel:
    """嵌入模型单例（自动选择 API 或本地）"""
    _instance = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._model is None:
            self._model = self._create_model()

    def _create_model(self):
        """根据配置创建嵌入模型"""
        from config import (
            EMBEDDING_PROVIDER, EMBEDDING_MODEL, EMBEDDING_DEVICE,
            EMBEDDING_API_KEY, EMBEDDING_API_BASE
        )

        if EMBEDDING_PROVIDER == "api":
            if not EMBEDDING_API_KEY:
                raise ValueError("使用 API 嵌入时必须设置 EMBEDDING_API_KEY")
            return APIEmbeddingModel(
                api_key=EMBEDDING_API_KEY,
                base_url=EMBEDDING_API_BASE,
                model=EMBEDDING_MODEL
            )
        else:
            return LocalEmbeddingModel(
                model_name=EMBEDDING_MODEL,
                device=EMBEDDING_DEVICE
            )

    @property
    def model(self):
        return self._model

    def encode(self, texts, batch_size=32, show_progress_bar=False):
        """生成嵌入向量"""
        return self._model.encode(texts, batch_size=batch_size, show_progress_bar=show_progress_bar)

    def get_embedding_dim(self):
        """获取嵌入维度"""
        return self._model.get_embedding_dim()


def get_embedding_model():
    """获取嵌入模型实例"""
    return EmbeddingModel()
