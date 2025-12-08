"""
Reranker 模块：交叉编码重排（支持批处理和缓存）
"""
from typing import List, Dict, Optional, Tuple
import threading
import hashlib
import time
from collections import OrderedDict

from utils.logger import logger


class LRUCache:
    """带 TTL 的 LRU 缓存"""

    def __init__(self, max_size: int = 100, ttl: int = 300):
        self.max_size = max_size
        self.ttl = ttl
        self.cache: OrderedDict[str, Tuple[float, any]] = OrderedDict()
        self.lock = threading.Lock()

    def _generate_key(self, query: str, doc_ids: List[str]) -> str:
        """生成缓存键"""
        content = f"{query}::{','.join(sorted(doc_ids))}"
        return hashlib.md5(content.encode()).hexdigest()

    def get(self, query: str, doc_ids: List[str]) -> Optional[List[Dict]]:
        """获取缓存"""
        key = self._generate_key(query, doc_ids)
        with self.lock:
            if key not in self.cache:
                return None

            timestamp, value = self.cache[key]
            # 检查是否过期
            if time.time() - timestamp > self.ttl:
                del self.cache[key]
                return None

            # 移到末尾（最近使用）
            self.cache.move_to_end(key)
            return value

    def set(self, query: str, doc_ids: List[str], value: List[Dict]):
        """设置缓存"""
        key = self._generate_key(query, doc_ids)
        with self.lock:
            # 如果已存在，先删除
            if key in self.cache:
                del self.cache[key]
            # 如果超过最大容量，删除最旧的
            while len(self.cache) >= self.max_size:
                self.cache.popitem(last=False)
            # 添加新条目
            self.cache[key] = (time.time(), value)

    def clear(self):
        """清空缓存"""
        with self.lock:
            self.cache.clear()


class BaseReranker:
    """Reranker 基类"""

    def rerank(self, query: str, docs: List[Dict], top_k: int) -> List[Dict]:
        raise NotImplementedError


class CrossEncoderReranker(BaseReranker):
    """交叉编码重排器（懒加载、线程安全、批处理、缓存、自动降级）"""

    def __init__(self):
        self._model = None
        self._tokenizer = None
        self._lock = threading.Lock()
        self._load_failed = False
        self._cache: Optional[LRUCache] = None

    def _get_cache(self) -> LRUCache:
        """懒加载缓存"""
        if self._cache is None:
            from config import RERANKER_CACHE_SIZE, RERANKER_CACHE_TTL
            self._cache = LRUCache(max_size=RERANKER_CACHE_SIZE, ttl=RERANKER_CACHE_TTL)
        return self._cache

    def _lazy_load(self):
        """懒加载模型（首次调用时加载）"""
        if self._model is not None or self._load_failed:
            return

        with self._lock:
            if self._model is not None or self._load_failed:
                return

            try:
                from config import RERANKER_MODEL_NAME, RERANKER_DEVICE

                logger.info(f"正在加载 Reranker 模型: {RERANKER_MODEL_NAME}")

                from transformers import AutoTokenizer, AutoModelForSequenceClassification
                import torch

                self._tokenizer = AutoTokenizer.from_pretrained(RERANKER_MODEL_NAME)
                self._model = AutoModelForSequenceClassification.from_pretrained(
                    RERANKER_MODEL_NAME
                )

                # 移动到指定设备
                device = RERANKER_DEVICE
                if device == "cuda" and not torch.cuda.is_available():
                    logger.warning("CUDA 不可用，回退到 CPU")
                    device = "cpu"

                self._model = self._model.to(device)
                self._model.eval()

                logger.info(f"Reranker 模型加载完成: {RERANKER_MODEL_NAME} on {device}")

            except Exception as e:
                logger.error(f"Reranker 模型加载失败: {e}")
                self._load_failed = True
                raise

    def _compute_scores_batch(self, query: str, contents: List[str]) -> List[float]:
        """批量计算重排分数"""
        import torch
        from config import RERANKER_MAX_LENGTH, RERANKER_BATCH_SIZE

        all_scores = []
        num_docs = len(contents)

        # 分批处理
        for i in range(0, num_docs, RERANKER_BATCH_SIZE):
            batch_contents = contents[i:i + RERANKER_BATCH_SIZE]
            batch_size = len(batch_contents)

            # 构建查询-文档对
            query_list = [query] * batch_size
            doc_list = batch_contents

            # Tokenize
            inputs = self._tokenizer(
                query_list,
                doc_list,
                max_length=RERANKER_MAX_LENGTH,
                padding=True,
                truncation=True,
                return_tensors="pt"
            )

            # 移动到模型所在设备
            inputs = {k: v.to(self._model.device) for k, v in inputs.items()}

            # 推理
            with torch.no_grad():
                outputs = self._model(**inputs)
                if outputs.logits.shape[-1] == 1:
                    batch_scores = outputs.logits.squeeze(-1).tolist()
                else:
                    batch_scores = torch.softmax(outputs.logits, dim=-1)[:, 1].tolist()

            # 确保是列表
            if not isinstance(batch_scores, list):
                batch_scores = [batch_scores]

            all_scores.extend(batch_scores)

        return all_scores

    def rerank(self, query: str, docs: List[Dict], top_k: int) -> List[Dict]:
        """
        对文档进行重排（支持批处理和缓存）

        Args:
            query: 查询文本
            docs: 候选文档列表
            top_k: 返回数量

        Returns:
            重排后的文档列表（包含 rerank_score 字段）
        """
        if not docs:
            return docs

        # 生成文档 ID 列表用于缓存
        doc_ids = []
        for doc in docs:
            doc_id = doc.get("id") or doc.get("file_path", "") + ":" + str(doc.get("chunk_index", 0))
            doc_ids.append(doc_id)

        # 检查缓存
        cache = self._get_cache()
        cached_result = cache.get(query, doc_ids)
        if cached_result is not None:
            logger.debug(f"Reranker 缓存命中: query={query[:50]}...")
            return cached_result[:top_k]

        # 尝试加载模型
        try:
            self._lazy_load()
        except Exception:
            logger.warning("Reranker 加载失败，使用原排序")
            return docs[:top_k]

        if self._load_failed:
            return docs[:top_k]

        try:
            # 提取文档内容
            contents = [doc.get("content", "") for doc in docs]

            # 批量计算分数
            scores = self._compute_scores_batch(query, contents)

            # 组装结果并排序
            reranked = []
            for doc, score in zip(docs, scores):
                new_doc = {**doc, "rerank_score": float(score)}
                reranked.append(new_doc)

            reranked.sort(key=lambda x: x["rerank_score"], reverse=True)

            # 存入缓存
            cache.set(query, doc_ids, reranked)

            logger.debug(f"Reranker 重排完成: {len(docs)} 文档, 批处理")
            return reranked[:top_k]

        except Exception as e:
            logger.error(f"Reranker 推理失败，使用原排序: {e}")
            return docs[:top_k]

    def clear_cache(self):
        """清空缓存"""
        if self._cache:
            self._cache.clear()
            logger.info("Reranker 缓存已清空")


# 全局单例
_reranker_instance = None
_reranker_lock = threading.Lock()


def get_reranker() -> CrossEncoderReranker:
    """获取 Reranker 单例"""
    global _reranker_instance

    if _reranker_instance is None:
        with _reranker_lock:
            if _reranker_instance is None:
                _reranker_instance = CrossEncoderReranker()

    return _reranker_instance
