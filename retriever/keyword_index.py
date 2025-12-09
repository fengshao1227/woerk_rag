"""
关键词索引管理器
使用 SQLite FTS5 实现高效的全文检索
"""

import sqlite3
import os
import re
import jieba
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from utils.logger import logger


class KeywordIndexManager:
    """关键词索引管理器 - 基于 SQLite FTS5"""

    def __init__(self, db_path: str = None):
        """
        初始化关键词索引管理器

        Args:
            db_path: SQLite 数据库路径，默认为 data/keyword_index.db
        """
        if db_path is None:
            # 默认路径
            base_dir = Path(__file__).parent.parent
            data_dir = base_dir / "data"
            data_dir.mkdir(exist_ok=True)
            db_path = str(data_dir / "keyword_index.db")

        self.db_path = db_path
        self._init_database()
        logger.info(f"关键词索引管理器初始化完成: {db_path}")

    def _init_database(self):
        """初始化数据库和 FTS5 表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 创建 FTS5 虚拟表用于全文检索
        # 使用 porter tokenizer 支持词干提取
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS keyword_index USING fts5(
                doc_id,
                content,
                title,
                category,
                file_path,
                tokenize='porter unicode61'
            )
        """)

        # 创建元数据表，存储文档的额外信息
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS doc_metadata (
                doc_id TEXT PRIMARY KEY,
                qdrant_id TEXT,
                file_path TEXT,
                title TEXT,
                category TEXT,
                chunk_index INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 创建索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_metadata_qdrant_id
            ON doc_metadata(qdrant_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_metadata_file_path
            ON doc_metadata(file_path)
        """)

        conn.commit()
        conn.close()

    def _tokenize_chinese(self, text: str) -> str:
        """
        对中文文本进行分词处理

        Args:
            text: 原始文本

        Returns:
            分词后的文本（空格分隔）
        """
        # 使用 jieba 分词
        words = jieba.cut(text, cut_all=False)
        return " ".join(words)

    def _preprocess_content(self, content: str) -> str:
        """
        预处理内容用于索引

        Args:
            content: 原始内容

        Returns:
            处理后的内容
        """
        if not content:
            return ""

        # 检测是否包含中文
        has_chinese = bool(re.search(r'[\u4e00-\u9fff]', content))

        if has_chinese:
            # 中文内容进行分词
            return self._tokenize_chinese(content)
        else:
            # 英文内容直接返回（FTS5 会自动处理）
            return content

    def add_document(
        self,
        doc_id: str,
        content: str,
        title: str = "",
        category: str = "general",
        file_path: str = "",
        qdrant_id: str = None,
        chunk_index: int = 0
    ) -> bool:
        """
        添加文档到关键词索引

        Args:
            doc_id: 文档唯一标识
            content: 文档内容
            title: 文档标题
            category: 文档分类
            file_path: 文件路径
            qdrant_id: Qdrant 中的 point ID
            chunk_index: 分块索引

        Returns:
            是否添加成功
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 预处理内容
            processed_content = self._preprocess_content(content)
            processed_title = self._preprocess_content(title)

            # 先删除已存在的文档（更新场景）
            cursor.execute("DELETE FROM keyword_index WHERE doc_id = ?", (doc_id,))
            cursor.execute("DELETE FROM doc_metadata WHERE doc_id = ?", (doc_id,))

            # 插入 FTS5 索引
            cursor.execute("""
                INSERT INTO keyword_index (doc_id, content, title, category, file_path)
                VALUES (?, ?, ?, ?, ?)
            """, (doc_id, processed_content, processed_title, category, file_path))

            # 插入元数据
            cursor.execute("""
                INSERT INTO doc_metadata (doc_id, qdrant_id, file_path, title, category, chunk_index)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (doc_id, qdrant_id or doc_id, file_path, title, category, chunk_index))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            logger.error(f"添加关键词索引失败: {e}")
            return False

    def add_documents_batch(self, documents: List[Dict[str, Any]]) -> int:
        """
        批量添加文档到关键词索引

        Args:
            documents: 文档列表，每个文档包含 doc_id, content, title, category, file_path 等字段

        Returns:
            成功添加的文档数量
        """
        if not documents:
            return 0

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            success_count = 0

            for doc in documents:
                try:
                    doc_id = doc.get("doc_id") or doc.get("id")
                    content = doc.get("content", "")
                    title = doc.get("title", "")
                    category = doc.get("category", "general")
                    file_path = doc.get("file_path", "")
                    qdrant_id = doc.get("qdrant_id", doc_id)
                    chunk_index = doc.get("chunk_index", 0)

                    if not doc_id:
                        continue

                    # 预处理内容
                    processed_content = self._preprocess_content(content)
                    processed_title = self._preprocess_content(title)

                    # 删除已存在的
                    cursor.execute("DELETE FROM keyword_index WHERE doc_id = ?", (doc_id,))
                    cursor.execute("DELETE FROM doc_metadata WHERE doc_id = ?", (doc_id,))

                    # 插入 FTS5 索引
                    cursor.execute("""
                        INSERT INTO keyword_index (doc_id, content, title, category, file_path)
                        VALUES (?, ?, ?, ?, ?)
                    """, (doc_id, processed_content, processed_title, category, file_path))

                    # 插入元数据
                    cursor.execute("""
                        INSERT INTO doc_metadata (doc_id, qdrant_id, file_path, title, category, chunk_index)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (doc_id, qdrant_id, file_path, title, category, chunk_index))

                    success_count += 1

                except Exception as e:
                    logger.warning(f"添加文档 {doc.get('doc_id')} 失败: {e}")
                    continue

            conn.commit()
            conn.close()

            logger.info(f"批量添加关键词索引完成: {success_count}/{len(documents)}")
            return success_count

        except Exception as e:
            logger.error(f"批量添加关键词索引失败: {e}")
            return 0

    def search(
        self,
        query: str,
        limit: int = 10,
        category: str = None
    ) -> List[Dict[str, Any]]:
        """
        关键词检索

        Args:
            query: 查询文本
            limit: 返回结果数量
            category: 可选的分类过滤

        Returns:
            匹配的文档列表，包含 doc_id, score, title, file_path 等
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 预处理查询
            processed_query = self._preprocess_content(query)

            # 构建 FTS5 查询
            # 使用 BM25 评分
            if category:
                cursor.execute("""
                    SELECT
                        k.doc_id,
                        bm25(keyword_index) as score,
                        k.title,
                        k.file_path,
                        k.category,
                        m.qdrant_id,
                        m.chunk_index
                    FROM keyword_index k
                    LEFT JOIN doc_metadata m ON k.doc_id = m.doc_id
                    WHERE keyword_index MATCH ? AND k.category = ?
                    ORDER BY score
                    LIMIT ?
                """, (processed_query, category, limit))
            else:
                cursor.execute("""
                    SELECT
                        k.doc_id,
                        bm25(keyword_index) as score,
                        k.title,
                        k.file_path,
                        k.category,
                        m.qdrant_id,
                        m.chunk_index
                    FROM keyword_index k
                    LEFT JOIN doc_metadata m ON k.doc_id = m.doc_id
                    WHERE keyword_index MATCH ?
                    ORDER BY score
                    LIMIT ?
                """, (processed_query, limit))

            results = []
            for row in cursor.fetchall():
                results.append({
                    "doc_id": row[0],
                    "score": abs(row[1]),  # BM25 返回负分，取绝对值
                    "title": row[2],
                    "file_path": row[3],
                    "category": row[4],
                    "qdrant_id": row[5],
                    "chunk_index": row[6]
                })

            conn.close()
            return results

        except Exception as e:
            logger.error(f"关键词检索失败: {e}")
            return []

    def delete_document(self, doc_id: str) -> bool:
        """
        删除文档

        Args:
            doc_id: 文档 ID

        Returns:
            是否删除成功
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("DELETE FROM keyword_index WHERE doc_id = ?", (doc_id,))
            cursor.execute("DELETE FROM doc_metadata WHERE doc_id = ?", (doc_id,))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            logger.error(f"删除关键词索引失败: {e}")
            return False

    def delete_by_qdrant_id(self, qdrant_id: str) -> bool:
        """
        根据 Qdrant ID 删除文档

        Args:
            qdrant_id: Qdrant point ID

        Returns:
            是否删除成功
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 先查找 doc_id
            cursor.execute("SELECT doc_id FROM doc_metadata WHERE qdrant_id = ?", (qdrant_id,))
            rows = cursor.fetchall()

            for row in rows:
                doc_id = row[0]
                cursor.execute("DELETE FROM keyword_index WHERE doc_id = ?", (doc_id,))
                cursor.execute("DELETE FROM doc_metadata WHERE doc_id = ?", (doc_id,))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            logger.error(f"根据 Qdrant ID 删除关键词索引失败: {e}")
            return False

    def delete_by_file_path(self, file_path: str) -> int:
        """
        根据文件路径删除所有相关文档

        Args:
            file_path: 文件路径

        Returns:
            删除的文档数量
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 先查找所有相关 doc_id
            cursor.execute("SELECT doc_id FROM doc_metadata WHERE file_path = ?", (file_path,))
            rows = cursor.fetchall()

            count = 0
            for row in rows:
                doc_id = row[0]
                cursor.execute("DELETE FROM keyword_index WHERE doc_id = ?", (doc_id,))
                cursor.execute("DELETE FROM doc_metadata WHERE doc_id = ?", (doc_id,))
                count += 1

            conn.commit()
            conn.close()

            logger.info(f"删除文件 {file_path} 的关键词索引: {count} 条")
            return count

        except Exception as e:
            logger.error(f"根据文件路径删除关键词索引失败: {e}")
            return 0

    def get_stats(self) -> Dict[str, Any]:
        """
        获取索引统计信息

        Returns:
            统计信息字典
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 总文档数
            cursor.execute("SELECT COUNT(*) FROM doc_metadata")
            total_docs = cursor.fetchone()[0]

            # 按分类统计
            cursor.execute("""
                SELECT category, COUNT(*)
                FROM doc_metadata
                GROUP BY category
            """)
            category_stats = {row[0]: row[1] for row in cursor.fetchall()}

            # 按文件统计
            cursor.execute("SELECT COUNT(DISTINCT file_path) FROM doc_metadata")
            total_files = cursor.fetchone()[0]

            conn.close()

            return {
                "total_documents": total_docs,
                "total_files": total_files,
                "by_category": category_stats
            }

        except Exception as e:
            logger.error(f"获取关键词索引统计失败: {e}")
            return {"total_documents": 0, "total_files": 0, "by_category": {}}

    def clear_all(self) -> bool:
        """
        清空所有索引

        Returns:
            是否成功
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("DELETE FROM keyword_index")
            cursor.execute("DELETE FROM doc_metadata")

            conn.commit()
            conn.close()

            logger.info("关键词索引已清空")
            return True

        except Exception as e:
            logger.error(f"清空关键词索引失败: {e}")
            return False


# 全局单例
_keyword_index_manager: Optional[KeywordIndexManager] = None


def get_keyword_index_manager() -> KeywordIndexManager:
    """获取关键词索引管理器单例"""
    global _keyword_index_manager
    if _keyword_index_manager is None:
        _keyword_index_manager = KeywordIndexManager()
    return _keyword_index_manager
