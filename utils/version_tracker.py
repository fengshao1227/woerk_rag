"""
版本追踪工具类 - 知识库版本管理
支持全量快照保存和回滚
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
import json

from admin.database import SessionLocal
from admin.models import KnowledgeVersion, KnowledgeEntry
from utils.logger import logger


class VersionTracker:
    """知识版本追踪器"""

    @staticmethod
    def create_version(
        qdrant_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        change_type: str = "create",
        changed_by: Optional[str] = None,
        change_reason: Optional[str] = None
    ) -> Optional[KnowledgeVersion]:
        """
        创建新版本快照

        Args:
            qdrant_id: Qdrant 中的文档 ID
            content: 完整内容快照
            metadata: 元数据（title, category, keywords 等）
            change_type: 变更类型 (create/update/delete)
            changed_by: 操作者
            change_reason: 变更原因

        Returns:
            创建的版本记录
        """
        db = SessionLocal()
        try:
            # 获取当前最新版本号
            latest = db.query(KnowledgeVersion).filter(
                KnowledgeVersion.qdrant_id == qdrant_id
            ).order_by(KnowledgeVersion.version.desc()).first()

            new_version = (latest.version + 1) if latest else 1

            # 创建版本记录
            version_record = KnowledgeVersion(
                qdrant_id=qdrant_id,
                version=new_version,
                content=content,
                metadata=metadata,
                change_type=change_type,
                changed_by=changed_by,
                change_reason=change_reason
            )

            db.add(version_record)
            db.commit()
            db.refresh(version_record)

            logger.info(f"创建版本: {qdrant_id} v{new_version} ({change_type})")
            return version_record

        except Exception as e:
            db.rollback()
            logger.error(f"创建版本失败: {e}")
            return None
        finally:
            db.close()

    @staticmethod
    def get_versions(
        qdrant_id: str,
        limit: int = 50
    ) -> List[KnowledgeVersion]:
        """
        获取版本历史

        Args:
            qdrant_id: Qdrant 中的文档 ID
            limit: 最大返回数量

        Returns:
            版本列表（按版本号降序）
        """
        db = SessionLocal()
        try:
            versions = db.query(KnowledgeVersion).filter(
                KnowledgeVersion.qdrant_id == qdrant_id
            ).order_by(
                KnowledgeVersion.version.desc()
            ).limit(limit).all()
            return versions
        finally:
            db.close()

    @staticmethod
    def get_version_detail(
        qdrant_id: str,
        version: int
    ) -> Optional[KnowledgeVersion]:
        """
        获取指定版本详情

        Args:
            qdrant_id: Qdrant 中的文档 ID
            version: 版本号

        Returns:
            版本记录
        """
        db = SessionLocal()
        try:
            return db.query(KnowledgeVersion).filter(
                KnowledgeVersion.qdrant_id == qdrant_id,
                KnowledgeVersion.version == version
            ).first()
        finally:
            db.close()

    @staticmethod
    def get_latest_version(qdrant_id: str) -> Optional[KnowledgeVersion]:
        """获取最新版本"""
        db = SessionLocal()
        try:
            return db.query(KnowledgeVersion).filter(
                KnowledgeVersion.qdrant_id == qdrant_id
            ).order_by(KnowledgeVersion.version.desc()).first()
        finally:
            db.close()

    @staticmethod
    def rollback_to_version(
        qdrant_id: str,
        target_version: int,
        changed_by: Optional[str] = None,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        回滚到指定版本

        Args:
            qdrant_id: Qdrant 中的文档 ID
            target_version: 目标版本号
            changed_by: 操作者
            reason: 回滚原因

        Returns:
            回滚结果（包含成功状态和新版本信息）
        """
        db = SessionLocal()
        try:
            # 获取目标版本
            target = db.query(KnowledgeVersion).filter(
                KnowledgeVersion.qdrant_id == qdrant_id,
                KnowledgeVersion.version == target_version
            ).first()

            if not target:
                return {
                    "success": False,
                    "error": f"目标版本 {target_version} 不存在"
                }

            # 获取当前最新版本号
            latest = db.query(KnowledgeVersion).filter(
                KnowledgeVersion.qdrant_id == qdrant_id
            ).order_by(KnowledgeVersion.version.desc()).first()

            if latest and latest.version == target_version:
                return {
                    "success": False,
                    "error": "当前已是目标版本"
                }

            new_version = (latest.version + 1) if latest else 1

            # 创建回滚版本记录
            rollback_record = KnowledgeVersion(
                qdrant_id=qdrant_id,
                version=new_version,
                content=target.content,
                metadata=target.metadata,
                change_type="update",
                changed_by=changed_by,
                change_reason=reason or f"回滚到版本 {target_version}"
            )

            db.add(rollback_record)

            # 更新 KnowledgeEntry（MySQL 索引）
            entry = db.query(KnowledgeEntry).filter(
                KnowledgeEntry.qdrant_id == qdrant_id
            ).first()

            if entry and target.metadata:
                metadata = target.metadata if isinstance(target.metadata, dict) else {}
                entry.title = metadata.get("title", entry.title)
                entry.category = metadata.get("category", entry.category)
                entry.summary = metadata.get("summary", entry.summary)
                entry.keywords = metadata.get("keywords", entry.keywords)
                entry.tech_stack = metadata.get("tech_stack", entry.tech_stack)
                entry.content_preview = target.content[:500] if target.content else None

            db.commit()

            logger.info(f"回滚成功: {qdrant_id} 从 v{latest.version if latest else 0} 回滚到 v{target_version} (新版本: v{new_version})")

            return {
                "success": True,
                "old_version": latest.version if latest else 0,
                "target_version": target_version,
                "new_version": new_version,
                "message": f"已回滚到版本 {target_version}"
            }

        except Exception as e:
            db.rollback()
            logger.error(f"回滚失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
        finally:
            db.close()

    @staticmethod
    def compare_versions(
        qdrant_id: str,
        version1: int,
        version2: int
    ) -> Optional[Dict[str, Any]]:
        """
        比较两个版本的差异

        Args:
            qdrant_id: Qdrant 中的文档 ID
            version1: 第一个版本号
            version2: 第二个版本号

        Returns:
            差异信息
        """
        db = SessionLocal()
        try:
            v1 = db.query(KnowledgeVersion).filter(
                KnowledgeVersion.qdrant_id == qdrant_id,
                KnowledgeVersion.version == version1
            ).first()

            v2 = db.query(KnowledgeVersion).filter(
                KnowledgeVersion.qdrant_id == qdrant_id,
                KnowledgeVersion.version == version2
            ).first()

            if not v1 or not v2:
                return None

            # 简单的差异比较
            content_changed = v1.content != v2.content
            metadata_changed = v1.metadata != v2.metadata

            return {
                "version1": {
                    "version": v1.version,
                    "change_type": v1.change_type,
                    "created_at": v1.created_at.isoformat() if v1.created_at else None,
                    "content_length": len(v1.content) if v1.content else 0
                },
                "version2": {
                    "version": v2.version,
                    "change_type": v2.change_type,
                    "created_at": v2.created_at.isoformat() if v2.created_at else None,
                    "content_length": len(v2.content) if v2.content else 0
                },
                "content_changed": content_changed,
                "metadata_changed": metadata_changed,
                "content_diff_size": abs(
                    (len(v1.content) if v1.content else 0) -
                    (len(v2.content) if v2.content else 0)
                )
            }

        finally:
            db.close()


# 便捷函数
def track_knowledge_change(
    qdrant_id: str,
    content: str,
    metadata: Optional[Dict] = None,
    change_type: str = "update",
    user: Optional[str] = None,
    reason: Optional[str] = None
) -> bool:
    """
    追踪知识变更的便捷函数

    在知识更新操作中调用此函数来记录版本历史
    """
    version = VersionTracker.create_version(
        qdrant_id=qdrant_id,
        content=content,
        metadata=metadata,
        change_type=change_type,
        changed_by=user,
        change_reason=reason
    )
    return version is not None
