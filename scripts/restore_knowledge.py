"""
从 MySQL 恢复知识库到 Qdrant
使用新的 API 嵌入模型重新生成向量
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import mysql.connector
import uuid
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

from config import (
    QDRANT_HOST, QDRANT_PORT, QDRANT_API_KEY,
    QDRANT_COLLECTION_NAME, QDRANT_USE_HTTPS
)
from utils.embeddings import get_embedding_model
from utils.logger import logger


def get_mysql_connection():
    """获取 MySQL 连接"""
    return mysql.connector.connect(
        host='103.96.72.4',
        user='root',
        password='Your_Very_Strong_Password_123!',
        database='rag_admin'
    )


def restore_knowledge():
    """从 MySQL 恢复知识到 Qdrant"""

    # 初始化嵌入模型
    logger.info("初始化嵌入模型...")
    embedding_model = get_embedding_model()
    dim = embedding_model.get_embedding_dim()
    logger.info(f"嵌入模型维度: {dim}")

    # 初始化 Qdrant 客户端
    protocol = "https" if QDRANT_USE_HTTPS else "http"
    url = f"{protocol}://{QDRANT_HOST}:{QDRANT_PORT}"
    qdrant_client = QdrantClient(url=url, api_key=QDRANT_API_KEY if QDRANT_API_KEY else None)

    # 从 MySQL 读取知识条目
    logger.info("从 MySQL 读取知识条目...")
    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute('''
        SELECT id, qdrant_id, title, category, summary, keywords,
               tech_stack, content_preview, created_at
        FROM knowledge_entries
        ORDER BY id
    ''')
    entries = cursor.fetchall()
    logger.info(f"共找到 {len(entries)} 条知识记录")

    if not entries:
        logger.warning("没有找到知识记录")
        return

    # 批量处理
    batch_size = 10
    success_count = 0

    for i in range(0, len(entries), batch_size):
        batch = entries[i:i+batch_size]

        # 准备文本和元数据
        texts = []
        metadatas = []

        for entry in batch:
            content = entry['content_preview'] or ''
            if not content.strip():
                continue

            texts.append(content)
            metadatas.append({
                'mysql_id': entry['id'],
                'title': entry['title'] or '',
                'category': entry['category'] or 'general',
                'summary': entry['summary'] or '',
                'keywords': entry['keywords'] if entry['keywords'] else [],
                'tech_stack': entry['tech_stack'] if entry['tech_stack'] else [],
                'created_at': str(entry['created_at']) if entry['created_at'] else '',
                'file_path': f"knowledge/{entry['qdrant_id'][:8]}",
                'type': 'knowledge'
            })

        if not texts:
            continue

        # 生成嵌入向量
        logger.info(f"处理批次 {i//batch_size + 1}: {len(texts)} 条记录")
        try:
            embeddings = embedding_model.encode(texts)

            # 创建 Qdrant points
            points = []
            for j, (embedding, metadata) in enumerate(zip(embeddings, metadatas)):
                point_id = str(uuid.uuid4())
                points.append(PointStruct(
                    id=point_id,
                    vector=embedding.tolist(),
                    payload={
                        'content': texts[j],
                        **metadata
                    }
                ))

            # 写入 Qdrant
            qdrant_client.upsert(
                collection_name=QDRANT_COLLECTION_NAME,
                points=points
            )

            success_count += len(points)
            logger.info(f"成功写入 {len(points)} 条记录")

            # 更新 MySQL 中的 qdrant_id
            for point, entry in zip(points, batch):
                if entry['content_preview']:
                    cursor.execute(
                        'UPDATE knowledge_entries SET qdrant_id = %s WHERE id = %s',
                        (point.id, entry['id'])
                    )
            conn.commit()

        except Exception as e:
            logger.error(f"处理批次失败: {e}")
            continue

    conn.close()
    logger.info(f"恢复完成！共成功恢复 {success_count} 条知识")

    # 验证
    collection_info = qdrant_client.get_collection(QDRANT_COLLECTION_NAME)
    logger.info(f"Qdrant collection 当前有 {collection_info.points_count} 条记录")


if __name__ == '__main__':
    restore_knowledge()
