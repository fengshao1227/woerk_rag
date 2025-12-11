"""
语义缓存模块
通过向量相似度匹配历史问答，避免重复调用 LLM
"""

import hashlib
import time
import threading
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, Distance, PointStruct,
    Filter, FieldCondition, MatchValue
)

from utils.logger import logger
from config import (
    QDRANT_HOST, QDRANT_PORT, QDRANT_API_KEY,
    EMBEDDING_DIM
)


@dataclass
class CacheEntry:
    """缓存条目"""
    question: str
    answer: str
    sources: List[Dict[str, Any]]
    created_at: float
    hit_count: int = 0
    last_hit_at: float = None


class SemanticCache:
    """
    语义缓存

    使用向量相似度匹配历史问答，当新问题与缓存问题相似度超过阈值时，
    直接返回缓存的答案，避免重复调用 LLM。

    特性：
    - 基于 Qdrant 向量存储
    - 可配置相似度阈值
    - 支持 TTL 过期
    - 命中统计
    - 后台定时清理（避免阻塞主线程）
    """

    COLLECTION_NAME = "semantic_cache"

    def __init__(
        self,
        embedding_func=None,
        similarity_threshold: float = 0.92,
        ttl_seconds: int = 86400 * 7,  # 默认 7 天
        max_cache_size: int = 10000,
        cleanup_interval: int = 3600  # 清理间隔（秒），默认 1 小时
    ):
        """
        初始化语义缓存

        Args:
            embedding_func: 嵌入函数，接收文本返回向量。若为 None 则自动创建
            similarity_threshold: 相似度阈值，超过此值视为命中
            ttl_seconds: 缓存过期时间（秒）
            max_cache_size: 最大缓存条目数
            cleanup_interval: 后台清理间隔（秒）
        """
        # 如果没有提供 embedding_func，自动创建
        if embedding_func is None:
            from utils.embeddings import EmbeddingModel
            embedding_model = EmbeddingModel()
            self.embedding_func = lambda text: embedding_model.embed(text)
        else:
            self.embedding_func = embedding_func

        self.similarity_threshold = similarity_threshold
        self.ttl_seconds = ttl_seconds
        self.max_cache_size = max_cache_size
        self.cleanup_interval = cleanup_interval

        # 初始化 Qdrant 客户端
        # 判断是否使用 HTTPS
        if QDRANT_HOST.startswith('http://') or QDRANT_HOST.startswith('https://'):
            # 如果 host 包含协议，直接使用 URL 模式
            self.client = QdrantClient(
                url=f"{QDRANT_HOST}:{QDRANT_PORT}" if not QDRANT_HOST.startswith('http') else QDRANT_HOST,
                api_key=QDRANT_API_KEY if QDRANT_API_KEY else None
            )
        else:
            # 否则使用 host/port 模式
            self.client = QdrantClient(
                host=QDRANT_HOST,
                port=QDRANT_PORT,
                api_key=QDRANT_API_KEY if QDRANT_API_KEY else None,
                https=False  # 明确禁用 HTTPS
            )

        self._init_collection()

        # 统计信息
        self.stats = {
            "hits": 0,
            "misses": 0,
            "total_queries": 0
        }

        # 后台清理线程
        self._cleanup_thread: Optional[threading.Thread] = None
        self._stop_cleanup = threading.Event()
        self._start_background_cleanup()

    def _init_collection(self):
        """初始化缓存集合"""
        collections = self.client.get_collections().collections
        exists = any(c.name == self.COLLECTION_NAME for c in collections)

        if not exists:
            self.client.create_collection(
                collection_name=self.COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=EMBEDDING_DIM,
                    distance=Distance.COSINE
                )
            )
            logger.info(f"创建语义缓存集合: {self.COLLECTION_NAME}")

    def _generate_id(self, question: str) -> str:
        """生成缓存 ID"""
        return hashlib.md5(question.encode()).hexdigest()

    def get(self, question: str) -> Optional[CacheEntry]:
        """
        查询缓存

        Args:
            question: 用户问题

        Returns:
            CacheEntry 如果命中，否则 None
        """
        self.stats["total_queries"] += 1

        try:
            # 生成问题向量
            query_vector = self.embedding_func(question)

            # 向量搜索
            results = self.client.search(
                collection_name=self.COLLECTION_NAME,
                query_vector=query_vector,
                limit=1,
                score_threshold=self.similarity_threshold
            )

            if not results:
                self.stats["misses"] += 1
                return None

            result = results[0]
            payload = result.payload

            # 检查 TTL
            created_at = payload.get("created_at", 0)
            if time.time() - created_at > self.ttl_seconds:
                # 缓存过期，删除并返回 None
                self._delete_point(result.id)
                self.stats["misses"] += 1
                logger.debug(f"缓存过期: {question[:50]}...")
                return None

            # 命中，更新统计
            self.stats["hits"] += 1
            self._update_hit_stats(result.id)

            logger.info(f"语义缓存命中 (相似度: {result.score:.4f}): {question[:50]}...")

            return CacheEntry(
                question=payload.get("question", ""),
                answer=payload.get("answer", ""),
                sources=payload.get("sources", []),
                created_at=created_at,
                hit_count=payload.get("hit_count", 0) + 1,
                last_hit_at=time.time()
            )

        except Exception as e:
            logger.error(f"语义缓存查询失败: {e}")
            self.stats["misses"] += 1
            return None

    def set(
        self,
        question: str,
        answer: str,
        sources: List[Dict[str, Any]] = None
    ) -> bool:
        """
        设置缓存

        Args:
            question: 用户问题
            answer: LLM 回答
            sources: 引用来源

        Returns:
            是否成功
        """
        try:
            # 检查缓存大小
            self._check_cache_size()

            # 生成向量
            question_vector = self.embedding_func(question)

            # 生成 ID
            point_id = self._generate_id(question)

            # 存储
            self.client.upsert(
                collection_name=self.COLLECTION_NAME,
                points=[
                    PointStruct(
                        id=point_id,
                        vector=question_vector,
                        payload={
                            "question": question,
                            "answer": answer,
                            "sources": sources or [],
                            "created_at": time.time(),
                            "hit_count": 0,
                            "last_hit_at": None
                        }
                    )
                ]
            )

            logger.debug(f"语义缓存写入: {question[:50]}...")
            return True

        except Exception as e:
            logger.error(f"语义缓存写入失败: {e}")
            return False

    def _update_hit_stats(self, point_id: str):
        """更新命中统计"""
        try:
            # 获取当前 payload
            points = self.client.retrieve(
                collection_name=self.COLLECTION_NAME,
                ids=[point_id]
            )

            if points:
                payload = points[0].payload
                payload["hit_count"] = payload.get("hit_count", 0) + 1
                payload["last_hit_at"] = time.time()

                # 更新 payload
                self.client.set_payload(
                    collection_name=self.COLLECTION_NAME,
                    payload=payload,
                    points=[point_id]
                )
        except Exception as e:
            logger.warning(f"更新缓存命中统计失败: {e}")

    def _delete_point(self, point_id: str):
        """删除缓存点"""
        try:
            self.client.delete(
                collection_name=self.COLLECTION_NAME,
                points_selector=[point_id]
            )
        except Exception as e:
            logger.warning(f"删除缓存点失败: {e}")

    def _check_cache_size(self):
        """检查并清理缓存大小"""
        try:
            info = self.client.get_collection(self.COLLECTION_NAME)
            current_size = info.points_count

            if current_size >= self.max_cache_size:
                # 删除最旧的 10% 缓存
                delete_count = int(self.max_cache_size * 0.1)
                self._cleanup_oldest(delete_count)
                logger.info(f"清理语义缓存: 删除 {delete_count} 条")

        except Exception as e:
            logger.warning(f"检查缓存大小失败: {e}")

    def _cleanup_oldest(self, count: int):
        """清理最旧的缓存"""
        try:
            # 获取所有点并按创建时间排序
            # 注意：这是简化实现，大规模时应使用滚动查询
            results = self.client.scroll(
                collection_name=self.COLLECTION_NAME,
                limit=count * 2,
                with_payload=True
            )

            if results and results[0]:
                points = results[0]
                # 按创建时间排序
                points.sort(key=lambda p: p.payload.get("created_at", 0))
                # 删除最旧的
                ids_to_delete = [p.id for p in points[:count]]
                if ids_to_delete:
                    self.client.delete(
                        collection_name=self.COLLECTION_NAME,
                        points_selector=ids_to_delete
                    )
        except Exception as e:
            logger.warning(f"清理旧缓存失败: {e}")

    def _start_background_cleanup(self):
        """启动后台清理线程"""
        def cleanup_worker():
            logger.info("语义缓存后台清理线程已启动")
            while not self._stop_cleanup.wait(self.cleanup_interval):
                try:
                    self._cleanup_expired()
                    self._check_cache_size()
                except Exception as e:
                    logger.warning(f"后台清理任务失败: {e}")
            logger.info("语义缓存后台清理线程已停止")

        self._cleanup_thread = threading.Thread(
            target=cleanup_worker,
            daemon=True,
            name="semantic-cache-cleanup"
        )
        self._cleanup_thread.start()

    def _cleanup_expired(self):
        """清理过期缓存"""
        try:
            current_time = time.time()
            expired_threshold = current_time - self.ttl_seconds

            # 滚动查询所有点，找出过期的
            offset = None
            expired_ids = []

            while True:
                results = self.client.scroll(
                    collection_name=self.COLLECTION_NAME,
                    limit=100,
                    offset=offset,
                    with_payload=True
                )

                points, next_offset = results
                if not points:
                    break

                for point in points:
                    created_at = point.payload.get("created_at", 0)
                    if created_at < expired_threshold:
                        expired_ids.append(point.id)

                if next_offset is None:
                    break
                offset = next_offset

            # 批量删除过期缓存
            if expired_ids:
                self.client.delete(
                    collection_name=self.COLLECTION_NAME,
                    points_selector=expired_ids
                )
                logger.info(f"清理过期缓存: 删除 {len(expired_ids)} 条")

        except Exception as e:
            logger.warning(f"清理过期缓存失败: {e}")

    def stop_cleanup(self):
        """停止后台清理线程"""
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._stop_cleanup.set()
            self._cleanup_thread.join(timeout=5)
            logger.info("语义缓存后台清理线程已停止")

    def clear(self):
        """清空缓存"""
        try:
            self.client.delete_collection(self.COLLECTION_NAME)
            self._init_collection()
            self.stats = {"hits": 0, "misses": 0, "total_queries": 0}
            logger.info("语义缓存已清空")
        except Exception as e:
            logger.error(f"清空语义缓存失败: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        hit_rate = 0
        if self.stats["total_queries"] > 0:
            hit_rate = self.stats["hits"] / self.stats["total_queries"]

        try:
            info = self.client.get_collection(self.COLLECTION_NAME)
            cache_size = info.points_count
        except:
            cache_size = 0

        return {
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "total_queries": self.stats["total_queries"],
            "hit_rate": f"{hit_rate:.2%}",
            "cache_size": cache_size,
            "max_cache_size": self.max_cache_size,
            "similarity_threshold": self.similarity_threshold,
            "ttl_seconds": self.ttl_seconds
        }


# 全局缓存实例（延迟初始化）
_cache_instance: Optional[SemanticCache] = None


def get_semantic_cache(embedding_func=None) -> Optional[SemanticCache]:
    """
    获取语义缓存实例

    Args:
        embedding_func: 嵌入函数（首次调用时必须提供）

    Returns:
        SemanticCache 实例
    """
    global _cache_instance

    if _cache_instance is None and embedding_func is not None:
        _cache_instance = SemanticCache(embedding_func)

    return _cache_instance
