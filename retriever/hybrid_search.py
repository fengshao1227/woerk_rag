"""
混合检索（向量 + 关键词 + Reranker）
"""
from typing import List, Dict, Optional
import sqlite3
from pathlib import Path

from retriever.vector_store import VectorStore
from config import TOP_K, BASE_DIR, RERANKER_ENABLE, RERANKER_TOP_K_MULTIPLIER
from utils.logger import logger


class HybridSearch:
    """混合检索器（支持 Reranker 重排）"""

    def __init__(self):
        self.vector_store = VectorStore()
        self.db_path = BASE_DIR / "rag.db"
        self._reranker = None
        self._init_keyword_index()

    def _get_reranker(self):
        """懒加载 Reranker"""
        if self._reranker is None and RERANKER_ENABLE:
            from retriever.reranker import get_reranker
            self._reranker = get_reranker()
        return self._reranker

    def _init_keyword_index(self):
        """初始化关键词索引数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 创建表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS keyword_index (
                id TEXT PRIMARY KEY,
                content TEXT,
                file_path TEXT,
                type TEXT,
                metadata TEXT
            )
        """)

        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS keyword_index_fts USING fts5(
                content,
                file_path,
                type,
                content='keyword_index',
                content_rowid='rowid'
            )
        """)

        conn.commit()
        conn.close()
        logger.info("关键词索引数据库初始化完成")

    def _keyword_search(self, query: str, top_k: int = TOP_K) -> List[Dict]:
        """关键词检索（使用 SQLite FTS5）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # FTS5 搜索
            cursor.execute("""
                SELECT
                    ki.id,
                    ki.content,
                    ki.file_path,
                    ki.type,
                    ki.metadata,
                    rank
                FROM keyword_index_fts kf
                JOIN keyword_index ki ON kf.rowid = ki.rowid
                WHERE keyword_index_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (query, top_k))

            results = []
            for row in cursor.fetchall():
                results.append({
                    "id": row[0],
                    "content": row[1],
                    "file_path": row[2],
                    "type": row[3],
                    "metadata": row[4],
                    "score": 1.0 / (abs(row[5]) + 1)  # 简单的分数转换
                })

            return results

        except Exception as e:
            logger.error(f"关键词检索失败: {e}")
            return []
        finally:
            conn.close()

    def search(
        self,
        query: str,
        top_k: int = TOP_K,
        filters: Optional[Dict] = None,
        use_hybrid: bool = True,
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3,
        use_reranker: bool = None,
    ) -> List[Dict]:
        """
        混合检索（可选 Reranker 重排）

        Args:
            query: 查询文本
            top_k: 返回结果数量
            filters: 过滤条件
            use_hybrid: 是否使用混合检索
            vector_weight: 向量检索权重
            keyword_weight: 关键词检索权重
            use_reranker: 是否使用 Reranker（None 时使用配置默认值）

        Returns:
            检索结果列表
        """
        # 确定是否使用 Reranker
        if use_reranker is None:
            use_reranker = RERANKER_ENABLE

        # 计算候选数量（Reranker 需要更多候选）
        candidate_k = top_k * RERANKER_TOP_K_MULTIPLIER if use_reranker else top_k

        if not use_hybrid:
            # 仅使用向量检索
            results = self.vector_store.search(query, candidate_k, filters)
        else:
            # 向量检索
            vector_results = self.vector_store.search(query, candidate_k, filters)

            # 关键词检索
            keyword_results = self._keyword_search(query, candidate_k)

            # 合并结果
            result_map = {}

            # 添加向量检索结果
            for result in vector_results:
                result_id = result.get("id") or result.get("file_path", "") + ":" + str(result.get("chunk_index", 0))
                result_map[result_id] = {
                    **result,
                    "vector_score": result.get("score", 0.0) * vector_weight,
                    "keyword_score": 0.0
                }

            # 添加关键词检索结果
            for result in keyword_results:
                result_id = result.get("id")
                if result_id in result_map:
                    result_map[result_id]["keyword_score"] = result.get("score", 0.0) * keyword_weight
                else:
                    result_map[result_id] = {
                        **result,
                        "vector_score": 0.0,
                        "keyword_score": result.get("score", 0.0) * keyword_weight
                    }

            # 计算综合分数并排序
            results = []
            for result_id, result in result_map.items():
                combined_score = result.get("vector_score", 0.0) + result.get("keyword_score", 0.0)
                result["score"] = combined_score
                results.append(result)

            # 按分数排序
            results.sort(key=lambda x: x["score"], reverse=True)

        # Reranker 重排
        if use_reranker:
            reranker = self._get_reranker()
            if reranker:
                logger.info(f"使用 Reranker 对 {len(results)} 个候选进行重排")
                results = reranker.rerank(query, results, top_k)
                return results

        # 返回 top_k
        return results[:top_k]
