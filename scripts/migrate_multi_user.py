#!/usr/bin/env python3
"""
多用户知识隔离数据迁移脚本

功能：
1. 修改 MySQL 表结构（添加 user_id, is_public 字段）
2. 更新现有数据（归属 admin 用户，设为公开）
3. 更新 Qdrant payload（添加 user_id, is_public）

用法：
    python scripts/migrate_multi_user.py
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from admin.database import engine, SessionLocal
from admin.models import KnowledgeEntry, KnowledgeGroup, User, KnowledgeTask
from qdrant_client import QdrantClient
from config import QDRANT_HOST, QDRANT_PORT, QDRANT_API_KEY, QDRANT_COLLECTION_NAME, QDRANT_USE_HTTPS
from sqlalchemy import text
from utils.logger import logger


def migrate_mysql():
    """修改 MySQL 表结构"""
    logger.info("=" * 50)
    logger.info("开始 MySQL 表结构迁移...")
    logger.info("=" * 50)

    with engine.connect() as conn:
        # 1. knowledge_entries 表
        logger.info("[1/3] 迁移 knowledge_entries 表...")
        try:
            # 检查列是否存在
            result = conn.execute(text("""
                SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = 'knowledge_entries'
                AND COLUMN_NAME = 'user_id'
            """))
            if result.fetchone() is None:
                conn.execute(text("""
                    ALTER TABLE knowledge_entries
                    ADD COLUMN user_id INT DEFAULT 1,
                    ADD COLUMN is_public BOOLEAN DEFAULT TRUE
                """))
                conn.execute(text("""
                    CREATE INDEX idx_ke_user_id ON knowledge_entries(user_id)
                """))
                conn.execute(text("""
                    CREATE INDEX idx_ke_is_public ON knowledge_entries(is_public)
                """))
                logger.info("  ✓ knowledge_entries 表结构更新完成")
            else:
                logger.info("  ✓ knowledge_entries 已有 user_id 字段，跳过")
        except Exception as e:
            logger.warning(f"  ! knowledge_entries 迁移异常: {e}")

        # 2. knowledge_groups 表
        logger.info("[2/3] 迁移 knowledge_groups 表...")
        try:
            result = conn.execute(text("""
                SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = 'knowledge_groups'
                AND COLUMN_NAME = 'user_id'
            """))
            if result.fetchone() is None:
                conn.execute(text("""
                    ALTER TABLE knowledge_groups
                    ADD COLUMN user_id INT DEFAULT 1,
                    ADD COLUMN is_public BOOLEAN DEFAULT TRUE
                """))
                conn.execute(text("""
                    CREATE INDEX idx_kg_user_id ON knowledge_groups(user_id)
                """))
                logger.info("  ✓ knowledge_groups 表结构更新完成")
            else:
                logger.info("  ✓ knowledge_groups 已有 user_id 字段，跳过")
        except Exception as e:
            logger.warning(f"  ! knowledge_groups 迁移异常: {e}")

        # 3. knowledge_tasks 表
        logger.info("[3/3] 迁移 knowledge_tasks 表...")
        try:
            result = conn.execute(text("""
                SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = 'knowledge_tasks'
                AND COLUMN_NAME = 'is_public'
            """))
            if result.fetchone() is None:
                conn.execute(text("""
                    ALTER TABLE knowledge_tasks
                    ADD COLUMN is_public BOOLEAN DEFAULT FALSE
                """))
                logger.info("  ✓ knowledge_tasks 表结构更新完成")
            else:
                logger.info("  ✓ knowledge_tasks 已有 is_public 字段，跳过")
        except Exception as e:
            logger.warning(f"  ! knowledge_tasks 迁移异常: {e}")

        conn.commit()

    logger.info("MySQL 表结构迁移完成")


def migrate_existing_data():
    """更新现有数据归属"""
    logger.info("=" * 50)
    logger.info("更新现有数据归属...")
    logger.info("=" * 50)

    db = SessionLocal()
    try:
        # 获取 admin 用户 ID
        admin = db.query(User).filter(User.username == "admin").first()
        admin_id = admin.id if admin else 1
        logger.info(f"Admin 用户 ID: {admin_id}")

        # 更新 knowledge_entries（使用原生 SQL 更安全）
        result = db.execute(text("""
            UPDATE knowledge_entries
            SET user_id = :admin_id, is_public = TRUE
            WHERE user_id IS NULL OR user_id = 0
        """), {"admin_id": admin_id})
        logger.info(f"  ✓ 更新了 {result.rowcount} 条知识条目")

        # 更新 knowledge_groups
        result = db.execute(text("""
            UPDATE knowledge_groups
            SET user_id = :admin_id, is_public = TRUE
            WHERE user_id IS NULL OR user_id = 0
        """), {"admin_id": admin_id})
        logger.info(f"  ✓ 更新了 {result.rowcount} 个知识分组")

        db.commit()
    except Exception as e:
        logger.error(f"更新数据归属失败: {e}")
        db.rollback()
        raise
    finally:
        db.close()

    logger.info("现有数据归属更新完成")


def migrate_qdrant():
    """更新 Qdrant payload"""
    logger.info("=" * 50)
    logger.info("开始 Qdrant payload 迁移...")
    logger.info("=" * 50)

    # 连接 Qdrant
    protocol = "https" if QDRANT_USE_HTTPS else "http"
    url = f"{protocol}://{QDRANT_HOST}:{QDRANT_PORT}"
    logger.info(f"连接 Qdrant: {url}")

    client = QdrantClient(url=url, api_key=QDRANT_API_KEY if QDRANT_API_KEY else None)

    # 获取 admin 用户 ID
    db = SessionLocal()
    admin = db.query(User).filter(User.username == "admin").first()
    admin_id = admin.id if admin else 1
    db.close()

    # 检查 collection 是否存在
    try:
        collection_info = client.get_collection(QDRANT_COLLECTION_NAME)
        total_points = collection_info.points_count
        logger.info(f"Collection: {QDRANT_COLLECTION_NAME}, 共 {total_points} 个 points")
    except Exception as e:
        logger.warning(f"Collection 不存在或无法访问: {e}")
        return

    # 滚动获取所有 points
    offset = None
    batch_size = 100
    total_updated = 0
    total_skipped = 0

    while True:
        result = client.scroll(
            collection_name=QDRANT_COLLECTION_NAME,
            limit=batch_size,
            offset=offset,
            with_payload=True,
            with_vectors=False
        )

        points = result[0]
        if not points:
            break

        # 批量更新 payload
        points_to_update = []
        for point in points:
            # 跳过已有 user_id 的
            if point.payload and "user_id" in point.payload:
                total_skipped += 1
                continue

            points_to_update.append(point.id)

        # 批量更新
        if points_to_update:
            client.set_payload(
                collection_name=QDRANT_COLLECTION_NAME,
                payload={
                    "user_id": admin_id,
                    "is_public": True
                },
                points=points_to_update
            )
            total_updated += len(points_to_update)

        offset = result[1]  # 下一页 offset
        if offset is None:
            break

        if total_updated > 0 and total_updated % 500 == 0:
            logger.info(f"  进度: 已更新 {total_updated} 个 points...")

    logger.info(f"  ✓ Qdrant 迁移完成: 更新 {total_updated} 个, 跳过 {total_skipped} 个")


def verify_migration():
    """验证迁移结果"""
    logger.info("=" * 50)
    logger.info("验证迁移结果...")
    logger.info("=" * 50)

    db = SessionLocal()
    try:
        # 验证 MySQL
        total_entries = db.query(KnowledgeEntry).count()
        entries_with_user = db.query(KnowledgeEntry).filter(
            KnowledgeEntry.user_id.isnot(None)
        ).count()
        logger.info(f"  MySQL knowledge_entries: {entries_with_user}/{total_entries} 有 user_id")

        total_groups = db.query(KnowledgeGroup).count()
        groups_with_user = db.query(KnowledgeGroup).filter(
            KnowledgeGroup.user_id.isnot(None)
        ).count()
        logger.info(f"  MySQL knowledge_groups: {groups_with_user}/{total_groups} 有 user_id")

    finally:
        db.close()

    # 验证 Qdrant
    protocol = "https" if QDRANT_USE_HTTPS else "http"
    url = f"{protocol}://{QDRANT_HOST}:{QDRANT_PORT}"
    client = QdrantClient(url=url, api_key=QDRANT_API_KEY if QDRANT_API_KEY else None)

    try:
        # 抽样检查
        result = client.scroll(
            collection_name=QDRANT_COLLECTION_NAME,
            limit=10,
            with_payload=True,
            with_vectors=False
        )
        points = result[0]
        has_user_id = sum(1 for p in points if p.payload and "user_id" in p.payload)
        logger.info(f"  Qdrant 抽样检查: {has_user_id}/{len(points)} 有 user_id")
    except Exception as e:
        logger.warning(f"  Qdrant 验证失败: {e}")

    logger.info("验证完成")


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("       多用户知识隔离数据迁移")
    logger.info("=" * 60)
    logger.info("")

    try:
        # 1. MySQL 表结构
        migrate_mysql()
        logger.info("")

        # 2. 现有数据归属
        migrate_existing_data()
        logger.info("")

        # 3. Qdrant payload
        migrate_qdrant()
        logger.info("")

        # 4. 验证
        verify_migration()
        logger.info("")

        logger.info("=" * 60)
        logger.info("       迁移全部完成！")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"迁移失败: {e}")
        raise


if __name__ == "__main__":
    main()
