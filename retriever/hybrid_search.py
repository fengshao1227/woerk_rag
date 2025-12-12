"""
混合检索（向量 + 关键词 + Reranker + Query改写）
"""
from typing import List, Dict, Optional
import sqlite3
from pathlib import Path

from retriever.vector_store import VectorStore
from config import (
    TOP_K, BASE_DIR, RERANKER_ENABLE, RERANKER_TOP_K_MULTIPLIER,
    QUERY_REWRITE_ENABLE, QUERY_REWRITE_STRATEGY, QUERY_REWRITE_NUM_VARIANTS
)
from utils.logger import logger


def normalize_uuid(uuid_str: str) -> str:
    """
    标准化 UUID 格式，去除连字符，转为小写

    由于历史数据中 qdrant_id 格式不一致（有的带连字符，有的不带），
    统一转换为不带连字符的32字符格式进行比较
    """
    if not uuid_str:
        return ""
    return uuid_str.replace("-", "").lower()


def get_user_accessible_qdrant_ids(user_id: int) -> set:
    """
    获取用户可访问的所有 qdrant_id

    规则（知识可见性由分组决定）:
    1. 用户自己创建的分组中的知识
    2. 公开分组中的知识
    3. 共享给用户的分组中的知识
    4. 用户自己创建的未分组知识

    Args:
        user_id: 当前用户ID

    Returns:
        用户可访问的 qdrant_id 集合（已标准化格式）
    """
    if not user_id:
        return set()

    try:
        from admin.database import SessionLocal
        from admin.models import KnowledgeEntry, GroupShare, KnowledgeGroupItem, KnowledgeGroup

        db = SessionLocal()
        try:
            accessible_ids = set()

            # 1. 获取用户自己创建的分组ID
            my_group_ids = db.query(KnowledgeGroup.id).filter(
                KnowledgeGroup.user_id == user_id
            ).all()
            my_group_ids = [g[0] for g in my_group_ids]

            # 2. 获取公开分组ID
            public_group_ids = db.query(KnowledgeGroup.id).filter(
                KnowledgeGroup.is_public == True
            ).all()
            public_group_ids = [g[0] for g in public_group_ids]

            # 3. 获取共享给当前用户的分组ID
            shared_group_ids = db.query(GroupShare.group_id).filter(
                GroupShare.shared_with_user_id == user_id
            ).all()
            shared_group_ids = [g[0] for g in shared_group_ids]

            # 合并所有可访问的分组ID
            accessible_group_ids = list(set(my_group_ids + public_group_ids + shared_group_ids))

            # 4. 获取这些分组中的知识
            if accessible_group_ids:
                items = db.query(KnowledgeGroupItem.qdrant_id).filter(
                    KnowledgeGroupItem.group_id.in_(accessible_group_ids)
                ).all()
                for item in items:
                    if item[0]:
                        accessible_ids.add(normalize_uuid(item[0]))

            # 5. 获取用户自己创建的未分组知识
            all_grouped_qdrant_ids = db.query(KnowledgeGroupItem.qdrant_id).distinct().all()
            all_grouped_qdrant_ids_set = {normalize_uuid(item[0]) for item in all_grouped_qdrant_ids if item[0]}

            my_ungrouped = db.query(KnowledgeEntry.qdrant_id).filter(
                KnowledgeEntry.user_id == user_id
            ).all()
            for entry in my_ungrouped:
                if entry[0] and normalize_uuid(entry[0]) not in all_grouped_qdrant_ids_set:
                    accessible_ids.add(normalize_uuid(entry[0]))

            return accessible_ids
        finally:
            db.close()
    except Exception as e:
        logger.error(f"获取用户可访问知识失败: {e}")
        return set()


def get_group_qdrant_ids(group_ids: List[int]) -> List[str]:
    """
    根据分组ID列表获取所有关联的qdrant_id

    Args:
        group_ids: 分组ID列表

    Returns:
        该分组下所有知识条目的qdrant_id列表
    """
    if not group_ids:
        return []

    try:
        from admin.database import SessionLocal
        from admin.models import KnowledgeGroupItem

        db = SessionLocal()
        try:
            items = db.query(KnowledgeGroupItem.qdrant_id).filter(
                KnowledgeGroupItem.group_id.in_(group_ids)
            ).all()
            # 标准化 UUID 格式，解决历史数据格式不一致问题
            return [normalize_uuid(item[0]) for item in items]
        finally:
            db.close()
    except Exception as e:
        logger.error(f"获取分组qdrant_ids失败: {e}")
        return []


class HybridSearch:
    """混合检索器（支持 Reranker 重排 + Query 改写 + 高级关键词索引）"""

    def __init__(self):
        self.vector_store = VectorStore()
        self.db_path = BASE_DIR / "rag.db"
        self._reranker = None
        self._query_rewriter = None
        self._keyword_index_manager = None  # 新增：高级关键词索引管理器
        self._init_keyword_index()

    def _get_keyword_index_manager(self):
        """懒加载关键词索引管理器"""
        if self._keyword_index_manager is None:
            try:
                from retriever.keyword_index import KeywordIndexManager
                self._keyword_index_manager = KeywordIndexManager()
                logger.info("高级关键词索引管理器已加载")
            except Exception as e:
                logger.warning(f"关键词索引管理器加载失败: {e}")
        return self._keyword_index_manager

    def _get_reranker(self):
        """懒加载 Reranker"""
        if self._reranker is None and RERANKER_ENABLE:
            from retriever.reranker import get_reranker
            self._reranker = get_reranker()
        return self._reranker

    def _get_query_rewriter(self):
        """懒加载 Query 改写器"""
        if self._query_rewriter is None and QUERY_REWRITE_ENABLE:
            from retriever.query_rewriter import get_query_rewriter
            self._query_rewriter = get_query_rewriter(
                strategy=QUERY_REWRITE_STRATEGY,
                num_variants=QUERY_REWRITE_NUM_VARIANTS
            )
        return self._query_rewriter

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
        """关键词检索（优先使用高级索引管理器）"""
        # 尝试使用高级关键词索引管理器
        keyword_manager = self._get_keyword_index_manager()
        if keyword_manager:
            try:
                results = keyword_manager.search(query, limit=top_k)
                # 转换结果格式
                converted_results = []
                for r in results:
                    converted_results.append({
                        "id": r.get("doc_id") or r.get("qdrant_id"),
                        "content": r.get("content", ""),
                        "file_path": r.get("file_path", ""),
                        "type": r.get("category", "general"),
                        "score": abs(r.get("score", 0.0))  # BM25 分数转换
                    })
                return converted_results
            except Exception as e:
                logger.warning(f"高级关键词检索失败，回退到基础检索: {e}")

        # 回退到基础关键词检索
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
        group_ids: Optional[List[int]] = None,
        user_id: Optional[int] = None,  # 新增：用户ID，用于权限过滤
        use_hybrid: bool = True,
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3,
        use_reranker: bool = None,
        use_query_rewrite: bool = None,
    ) -> List[Dict]:
        """
        混合检索（可选 Reranker 重排 + Query 改写 + 用户权限过滤）

        Args:
            query: 查询文本
            top_k: 返回结果数量
            filters: 过滤条件
            group_ids: 知识分组ID列表，只检索这些分组中的知识
            user_id: 当前用户ID，用于多用户知识隔离（只检索用户私有+公开知识）
            use_hybrid: 是否使用混合检索
            vector_weight: 向量检索权重
            keyword_weight: 关键词检索权重
            use_reranker: 是否使用 Reranker（None 时使用配置默认值）
            use_query_rewrite: 是否使用 Query 改写（None 时使用配置默认值）

        Returns:
            检索结果列表
        """
        # 处理分组过滤
        allowed_qdrant_ids = None
        if group_ids:
            allowed_qdrant_ids = set(get_group_qdrant_ids(group_ids))
            if not allowed_qdrant_ids:
                logger.warning(f"分组 {group_ids} 中没有知识条目")
                return []
            logger.info(f"分组过滤: 限制在 {len(allowed_qdrant_ids)} 个知识条目内检索")

        # 处理用户权限过滤（多用户知识隔离）
        if user_id:
            user_accessible_ids = get_user_accessible_qdrant_ids(user_id)
            if not user_accessible_ids:
                logger.warning(f"用户 {user_id} 没有可访问的知识条目")
                return []
            # 与分组过滤取交集
            if allowed_qdrant_ids:
                allowed_qdrant_ids = allowed_qdrant_ids & user_accessible_ids
                if not allowed_qdrant_ids:
                    logger.warning(f"分组和用户权限交集为空")
                    return []
            else:
                allowed_qdrant_ids = user_accessible_ids
            logger.info(f"用户权限过滤: 限制在 {len(allowed_qdrant_ids)} 个知识条目内检索")

        # 确定是否使用 Reranker
        if use_reranker is None:
            use_reranker = RERANKER_ENABLE

        # 确定是否使用 Query 改写
        if use_query_rewrite is None:
            use_query_rewrite = QUERY_REWRITE_ENABLE

        # Query 改写
        queries = [query]
        if use_query_rewrite:
            query_rewriter = self._get_query_rewriter()
            if query_rewriter:
                queries = query_rewriter.rewrite(query)
                logger.info(f"Query 改写结果: {queries}")

        # 计算候选数量（Reranker 需要更多候选）
        candidate_k = top_k * RERANKER_TOP_K_MULTIPLIER if use_reranker else top_k

        # 多查询检索
        result_map = {}

        for q in queries:
            if not use_hybrid:
                # 仅使用向量检索
                q_results = self.vector_store.search(q, candidate_k, filters)
            else:
                # 向量检索
                vector_results = self.vector_store.search(q, candidate_k, filters)

                # 关键词检索
                keyword_results = self._keyword_search(q, candidate_k)

                # 合并当前查询的结果
                q_results = []

                # 添加向量检索结果
                for result in vector_results:
                    result_id = result.get("id") or result.get("file_path", "") + ":" + str(result.get("chunk_index", 0))
                    if result_id not in result_map:
                        result_map[result_id] = {
                            **result,
                            "vector_score": result.get("score", 0.0) * vector_weight,
                            "keyword_score": 0.0,
                            "query_count": 1
                        }
                    else:
                        result_map[result_id]["vector_score"] = max(
                            result_map[result_id].get("vector_score", 0),
                            result.get("score", 0.0) * vector_weight
                        )
                        result_map[result_id]["query_count"] = result_map[result_id].get("query_count", 0) + 1

                # 添加关键词检索结果
                for result in keyword_results:
                    result_id = result.get("id")
                    if result_id in result_map:
                        result_map[result_id]["keyword_score"] = max(
                            result_map[result_id].get("keyword_score", 0),
                            result.get("score", 0.0) * keyword_weight
                        )
                    else:
                        result_map[result_id] = {
                            **result,
                            "vector_score": 0.0,
                            "keyword_score": result.get("score", 0.0) * keyword_weight,
                            "query_count": 1
                        }

        # 计算综合分数并排序
        results = []
        for result_id, result in result_map.items():
            # 分组过滤：如果指定了分组，只保留分组内的结果
            if allowed_qdrant_ids:
                # result_id 可能是 qdrant_id 或 file_path:chunk_index 格式
                qdrant_id = result.get("id") or result_id.split(":")[0] if ":" in result_id else result_id
                # 标准化 UUID 格式后再比较，解决历史数据格式不一致问题
                if normalize_uuid(qdrant_id) not in allowed_qdrant_ids:
                    continue

            # 多查询命中加分
            query_boost = 1.0 + (result.get("query_count", 1) - 1) * 0.1
            combined_score = (result.get("vector_score", 0.0) + result.get("keyword_score", 0.0)) * query_boost
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
