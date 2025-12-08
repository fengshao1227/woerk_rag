"""
向量检索
"""
from typing import List, Dict, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

from config import QDRANT_HOST, QDRANT_PORT, QDRANT_API_KEY, QDRANT_COLLECTION_NAME, QDRANT_USE_HTTPS, TOP_K
from utils.embeddings import EmbeddingModel
from utils.logger import logger


class VectorStore:
    """向量存储检索器"""
    
    def __init__(self):
        self.embedding_model = EmbeddingModel()
        # 使用 URL 模式连接 Qdrant（明确指定 HTTP/HTTPS）
        protocol = "https" if QDRANT_USE_HTTPS else "http"
        url = f"{protocol}://{QDRANT_HOST}:{QDRANT_PORT}"
        self.qdrant_client = QdrantClient(
            url=url,
            api_key=QDRANT_API_KEY if QDRANT_API_KEY else None
        )
        self.collection_name = QDRANT_COLLECTION_NAME
    
    def search(
        self,
        query: str,
        top_k: int = TOP_K,
        filters: Optional[Dict] = None,
        score_threshold: float = 0.0
    ) -> List[Dict]:
        """
        向量检索
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            filters: 过滤条件，如 {"type": "code", "language": "php"}
            score_threshold: 相似度阈值
            
        Returns:
            检索结果列表
        """
        # 生成查询向量
        query_vector = self.embedding_model.encode([query])[0].tolist()
        
        # 构建过滤条件
        qdrant_filter = None
        if filters:
            conditions = []
            for key, value in filters.items():
                conditions.append(
                    FieldCondition(key=key, match=MatchValue(value=value))
                )
            if conditions:
                qdrant_filter = Filter(must=conditions)
        
        # 执行检索
        try:
            results = self.qdrant_client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=top_k,
                query_filter=qdrant_filter,
                score_threshold=score_threshold
            )

            # 格式化结果
            formatted_results = []
            for result in results.points:
                formatted_results.append({
                    "content": result.payload.get("content", ""),
                    "file_path": result.payload.get("file_path", ""),
                    "type": result.payload.get("type", ""),
                    "score": result.score,
                    "metadata": {
                        k: v for k, v in result.payload.items()
                        if k not in ["content", "file_path", "type"]
                    }
                })
            
            logger.debug(f"检索到 {len(formatted_results)} 个结果")
            return formatted_results
            
        except Exception as e:
            logger.error(f"向量检索失败: {e}")
            return []
