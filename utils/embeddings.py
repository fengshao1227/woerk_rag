"""
嵌入模型工具
"""
from sentence_transformers import SentenceTransformer
import torch
from config import EMBEDDING_MODEL, EMBEDDING_DEVICE


class EmbeddingModel:
    """嵌入模型单例"""
    _instance = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._model is None:
            device = "cuda" if torch.cuda.is_available() and EMBEDDING_DEVICE == "cuda" else "cpu"
            self._model = SentenceTransformer(EMBEDDING_MODEL, device=device)
            print(f"加载嵌入模型: {EMBEDDING_MODEL} (设备: {device})")

    @property
    def model(self):
        return self._model

    def encode(self, texts, batch_size=32, show_progress_bar=False):
        """生成嵌入向量"""
        if isinstance(texts, str):
            texts = [texts]
        return self._model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress_bar,
            normalize_embeddings=True
        )

    def get_embedding_dim(self):
        """获取嵌入维度"""
        return self._model.get_sentence_embedding_dimension()


def get_embedding_model():
    """获取嵌入模型实例"""
    return EmbeddingModel().model
