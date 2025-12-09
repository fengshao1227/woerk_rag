"""
索引所有数据（代码+文档）
支持增量索引模式，只索引变更的文件
"""
import sys
import argparse
from pathlib import Path
from typing import List

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import PROJECT_ROOT, CODE_PATTERNS, IGNORE_PATTERNS
from indexer.code_indexer import CodeIndexer
from indexer.doc_indexer import DocumentIndexer
from indexer.incremental import IncrementalIndexer, get_incremental_indexer
from utils.logger import logger


def find_code_files(root_path: Path) -> List[str]:
    """查找所有代码文件"""
    code_files = []
    for pattern in CODE_PATTERNS:
        pattern = pattern.strip()
        for file_path in root_path.rglob(pattern):
            if file_path.is_file():
                path_str = str(file_path)
                # 检查忽略模式
                should_ignore = False
                for ignore in IGNORE_PATTERNS:
                    ignore = ignore.strip().rstrip('/')
                    if ignore in path_str:
                        should_ignore = True
                        break
                if not should_ignore:
                    code_files.append(path_str)
    return code_files


def find_doc_files(root_path: Path) -> List[str]:
    """查找所有文档文件"""
    doc_files = []
    patterns = ['*.md', '*.txt', '*.html', '*.htm', '*.pdf', '*.docx', '*.doc']
    for pattern in patterns:
        for file_path in root_path.rglob(pattern):
            if file_path.is_file():
                path_str = str(file_path)
                # 检查忽略模式
                should_ignore = False
                for ignore in IGNORE_PATTERNS:
                    ignore = ignore.strip().rstrip('/')
                    if ignore in path_str:
                        should_ignore = True
                        break
                if not should_ignore:
                    doc_files.append(path_str)
    return doc_files


def main():
    """索引所有数据"""
    parser = argparse.ArgumentParser(description="索引代码和文档")
    parser.add_argument("--full", action="store_true", help="强制全量索引")
    parser.add_argument("--incremental", "-i", action="store_true", default=True, help="增量索引（默认）")
    parser.add_argument("--code-dir", type=str, help="代码目录路径")
    parser.add_argument("--doc-dir", type=str, help="文档目录路径")
    parser.add_argument("--clear-state", action="store_true", help="清空索引状态后重新索引")
    parser.add_argument("--stats", action="store_true", help="显示索引统计信息")
    args = parser.parse_args()

    # 获取增量索引器
    incremental_indexer = get_incremental_indexer()

    # 显示统计信息
    if args.stats:
        stats = incremental_indexer.get_stats()
        print(f"索引统计信息:")
        print(f"  已索引文件数: {stats['total_files']}")
        print(f"  Qdrant 点数: {stats['total_qdrant_ids']}")
        print(f"  上次全量索引: {stats['last_full_index'] or '从未'}")
        return

    # 清空状态
    if args.clear_state:
        incremental_indexer.clear_state()
        logger.info("索引状态已清空")

    incremental_mode = not args.full

    logger.info("开始索引所有数据...")
    logger.info(f"索引模式: {'增量' if incremental_mode else '全量'}")

    # 确定目录
    code_dir = Path(args.code_dir) if args.code_dir else PROJECT_ROOT
    doc_dir = Path(args.doc_dir) if args.doc_dir else PROJECT_ROOT

    # ===================== 索引代码 =====================
    logger.info("=" * 50)
    logger.info("开始索引代码库...")
    code_indexer = CodeIndexer()

    # 查找所有代码文件
    all_code_files = find_code_files(code_dir)
    logger.info(f"找到 {len(all_code_files)} 个代码文件")

    if incremental_mode:
        # 增量索引：检测变更
        new_files, modified_files, deleted_files = incremental_indexer.get_changed_files(
            all_code_files, force_reindex=args.full
        )
        files_to_index = new_files + modified_files

        if files_to_index:
            logger.info(f"需要索引: 新增 {len(new_files)}, 修改 {len(modified_files)}")
            code_stats = {"files": 0, "chunks": 0, "errors": 0, "new": len(new_files), "modified": len(modified_files)}

            for file_path in files_to_index:
                try:
                    chunks_count = code_indexer.index_file(Path(file_path))
                    if chunks_count > 0:
                        code_stats["files"] += 1
                        code_stats["chunks"] += chunks_count
                        # 标记已索引
                        incremental_indexer.mark_indexed(file_path)
                except Exception as e:
                    logger.error(f"索引文件失败 {file_path}: {e}")
                    code_stats["errors"] += 1

            # 处理删除的文件
            for file_path in deleted_files:
                qdrant_ids = incremental_indexer.mark_deleted(file_path)
                if qdrant_ids:
                    logger.info(f"文件已删除，清理索引: {file_path}")
                    # TODO: 从 Qdrant 删除对应的点
        else:
            logger.info("代码库无变更，跳过索引")
            code_stats = {"files": 0, "chunks": 0, "errors": 0, "skipped": True}
    else:
        # 全量索引
        code_stats = code_indexer.index_directory(code_dir)
        # 标记所有文件已索引
        for file_path in all_code_files:
            incremental_indexer.mark_indexed(file_path)
        incremental_indexer.mark_full_index_complete()

    logger.info(f"代码索引完成: {code_stats}")

    # ===================== 索引文档 =====================
    logger.info("=" * 50)
    logger.info("开始索引文档...")
    doc_indexer = DocumentIndexer()

    # 查找所有文档文件
    all_doc_files = find_doc_files(doc_dir)
    logger.info(f"找到 {len(all_doc_files)} 个文档文件")

    if incremental_mode:
        # 增量索引：检测变更
        new_files, modified_files, deleted_files = incremental_indexer.get_changed_files(
            all_doc_files, force_reindex=args.full
        )
        files_to_index = new_files + modified_files

        if files_to_index:
            logger.info(f"需要索引: 新增 {len(new_files)}, 修改 {len(modified_files)}")
            doc_stats = {"files": 0, "chunks": 0, "errors": 0, "new": len(new_files), "modified": len(modified_files)}

            for file_path in files_to_index:
                try:
                    chunks_count = doc_indexer.index_file(Path(file_path))
                    if chunks_count > 0:
                        doc_stats["files"] += 1
                        doc_stats["chunks"] += chunks_count
                        # 标记已索引
                        incremental_indexer.mark_indexed(file_path)
                except Exception as e:
                    logger.error(f"索引文件失败 {file_path}: {e}")
                    doc_stats["errors"] += 1

            # 处理删除的文件
            for file_path in deleted_files:
                qdrant_ids = incremental_indexer.mark_deleted(file_path)
                if qdrant_ids:
                    logger.info(f"文件已删除，清理索引: {file_path}")
        else:
            logger.info("文档库无变更，跳过索引")
            doc_stats = {"files": 0, "chunks": 0, "errors": 0, "skipped": True}
    else:
        # 全量索引
        doc_stats = doc_indexer.index_directory(doc_dir)
        # 标记所有文件已索引
        for file_path in all_doc_files:
            incremental_indexer.mark_indexed(file_path)

    logger.info(f"文档索引完成: {doc_stats}")

    # 汇总统计
    logger.info("=" * 50)
    total_stats = {
        "total_files": code_stats.get("files", 0) + doc_stats.get("files", 0),
        "total_chunks": code_stats.get("chunks", 0) + doc_stats.get("chunks", 0),
        "total_errors": code_stats.get("errors", 0) + doc_stats.get("errors", 0),
        "code_files": code_stats.get("files", 0),
        "code_chunks": code_stats.get("chunks", 0),
        "doc_files": doc_stats.get("files", 0),
        "doc_chunks": doc_stats.get("chunks", 0),
        "mode": "incremental" if incremental_mode else "full",
    }
    logger.info(f"索引完成！总统计: {total_stats}")


if __name__ == "__main__":
    main()
