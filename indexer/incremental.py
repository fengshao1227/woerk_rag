"""
增量索引模块 - 基于文件哈希的变更检测，避免重复索引
"""
import os
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime

from utils.logger import logger


class IncrementalIndexer:
    """增量索引管理器 - 跟踪文件变更，只索引新增或修改的文件"""

    def __init__(self, index_state_path: str = "data/index_state.json"):
        """
        初始化增量索引器

        Args:
            index_state_path: 索引状态文件路径
        """
        self.index_state_path = Path(index_state_path)
        self.index_state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state: Dict[str, Dict] = self._load_state()

    def _load_state(self) -> Dict[str, Dict]:
        """加载索引状态"""
        if self.index_state_path.exists():
            try:
                with open(self.index_state_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"加载索引状态失败: {e}")
        return {"files": {}, "last_full_index": None}

    def _save_state(self):
        """保存索引状态"""
        try:
            with open(self.index_state_path, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存索引状态失败: {e}")

    @staticmethod
    def _compute_file_hash(file_path: str) -> str:
        """计算文件内容哈希"""
        hasher = hashlib.md5()
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception as e:
            logger.warning(f"计算文件哈希失败 {file_path}: {e}")
            return ""

    @staticmethod
    def _get_file_mtime(file_path: str) -> float:
        """获取文件修改时间"""
        try:
            return os.path.getmtime(file_path)
        except Exception:
            return 0.0

    def get_changed_files(
        self,
        file_paths: List[str],
        force_reindex: bool = False
    ) -> Tuple[List[str], List[str], List[str]]:
        """
        检测文件变更，返回需要索引的文件列表

        Args:
            file_paths: 待检查的文件路径列表
            force_reindex: 是否强制重新索引所有文件

        Returns:
            Tuple[新增文件, 修改文件, 删除文件]
        """
        if force_reindex:
            return file_paths, [], []

        current_files = set(file_paths)
        indexed_files = set(self.state.get("files", {}).keys())

        # 新增文件
        new_files = list(current_files - indexed_files)

        # 删除文件
        deleted_files = list(indexed_files - current_files)

        # 修改文件（检查哈希变化）
        modified_files = []
        for file_path in current_files & indexed_files:
            file_info = self.state["files"].get(file_path, {})
            old_hash = file_info.get("hash", "")
            old_mtime = file_info.get("mtime", 0)

            # 先检查修改时间（快速判断）
            current_mtime = self._get_file_mtime(file_path)
            if current_mtime != old_mtime:
                # 修改时间变化，再检查哈希
                current_hash = self._compute_file_hash(file_path)
                if current_hash != old_hash:
                    modified_files.append(file_path)

        logger.info(
            f"增量索引检测: 新增 {len(new_files)}, "
            f"修改 {len(modified_files)}, 删除 {len(deleted_files)}"
        )

        return new_files, modified_files, deleted_files

    def mark_indexed(self, file_path: str, qdrant_ids: List[str] = None):
        """
        标记文件已索引

        Args:
            file_path: 文件路径
            qdrant_ids: 该文件在 Qdrant 中的 point IDs
        """
        self.state.setdefault("files", {})[file_path] = {
            "hash": self._compute_file_hash(file_path),
            "mtime": self._get_file_mtime(file_path),
            "indexed_at": datetime.now().isoformat(),
            "qdrant_ids": qdrant_ids or []
        }
        self._save_state()

    def mark_deleted(self, file_path: str) -> List[str]:
        """
        标记文件已删除，返回需要从 Qdrant 删除的 IDs

        Args:
            file_path: 文件路径

        Returns:
            该文件对应的 Qdrant point IDs
        """
        file_info = self.state.get("files", {}).pop(file_path, {})
        self._save_state()
        return file_info.get("qdrant_ids", [])

    def get_qdrant_ids(self, file_path: str) -> List[str]:
        """获取文件对应的 Qdrant point IDs"""
        return self.state.get("files", {}).get(file_path, {}).get("qdrant_ids", [])

    def clear_state(self):
        """清空索引状态"""
        self.state = {"files": {}, "last_full_index": None}
        self._save_state()
        logger.info("索引状态已清空")

    def get_stats(self) -> Dict:
        """获取索引统计信息"""
        files = self.state.get("files", {})
        return {
            "total_files": len(files),
            "last_full_index": self.state.get("last_full_index"),
            "total_qdrant_ids": sum(
                len(f.get("qdrant_ids", [])) for f in files.values()
            )
        }

    def mark_full_index_complete(self):
        """标记全量索引完成"""
        self.state["last_full_index"] = datetime.now().isoformat()
        self._save_state()


# 全局实例
_incremental_indexer: Optional[IncrementalIndexer] = None


def get_incremental_indexer() -> IncrementalIndexer:
    """获取增量索引器单例"""
    global _incremental_indexer
    if _incremental_indexer is None:
        _incremental_indexer = IncrementalIndexer()
    return _incremental_indexer
