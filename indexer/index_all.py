"""
索引所有数据（代码+文档）
支持增量索引模式，只索引变更的文件
"""
import sys
import argparse
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from indexer.code_indexer import CodeIndexer
from indexer.doc_indexer import DocumentIndexer
from indexer.incremental import IncrementalIndexManager
from utils.logger import logger


def main():
    """索引所有数据"""
    parser = argparse.ArgumentParser(description="索引代码和文档")
    parser.add_argument("--full", action="store_true", help="强制全量索引")
    parser.add_argument("--incremental", action="store_true", default=True, help="增量索引（默认）")
    parser.add_argument("--code-dir", type=str, help="代码目录路径")
    parser.add_argument("--doc-dir", type=str, help="文档目录路径")
    args = parser.parse_args()

    incremental_mode = not args.full

    logger.info("开始索引所有数据...")
    logger.info(f"索引模式: {'增量' if incremental_mode else '全量'}")

    # 初始化增量索引管理器
    incremental_manager = IncrementalIndexManager() if incremental_mode else None

    # 索引代码
    logger.info("=" * 50)
    logger.info("开始索引代码库...")
    code_indexer = CodeIndexer()

    if incremental_mode and incremental_manager:
        # 增量索引：只索引变更的文件
        code_dir = Path(args.code_dir) if args.code_dir else Path(code_indexer.code_dir)
        changed_files = incremental_manager.get_changed_files(code_dir, "code")

        if changed_files:
            logger.info(f"检测到 {len(changed_files)} 个变更的代码文件")
            code_stats = {"files": 0, "chunks": 0, "errors": 0, "skipped": 0}
            for file_path in changed_files:
                try:
                    result = code_indexer.index_file(file_path)
                    if result:
                        code_stats["files"] += 1
                        code_stats["chunks"] += result.get("chunks", 0)
                        # 更新文件哈希
                        incremental_manager.update_file_hash(file_path, "code")
                except Exception as e:
                    logger.error(f"索引文件失败 {file_path}: {e}")
                    code_stats["errors"] += 1
            # 保存索引状态
            incremental_manager.save_index()
        else:
            logger.info("代码库无变更，跳过索引")
            code_stats = {"files": 0, "chunks": 0, "errors": 0, "skipped": 1}
    else:
        code_stats = code_indexer.index_directory()

    logger.info(f"代码索引完成: {code_stats}")

    # 索引文档
    logger.info("=" * 50)
    logger.info("开始索引文档...")
    doc_indexer = DocumentIndexer()

    if incremental_mode and incremental_manager:
        # 增量索引：只索引变更的文件
        doc_dir = Path(args.doc_dir) if args.doc_dir else Path(doc_indexer.docs_dir)
        changed_files = incremental_manager.get_changed_files(doc_dir, "document")

        if changed_files:
            logger.info(f"检测到 {len(changed_files)} 个变更的文档文件")
            doc_stats = {"files": 0, "chunks": 0, "errors": 0, "skipped": 0}
            for file_path in changed_files:
                try:
                    result = doc_indexer.index_file(file_path)
                    if result:
                        doc_stats["files"] += 1
                        doc_stats["chunks"] += result.get("chunks", 0)
                        # 更新文件哈希
                        incremental_manager.update_file_hash(file_path, "document")
                except Exception as e:
                    logger.error(f"索引文件失败 {file_path}: {e}")
                    doc_stats["errors"] += 1
            # 保存索引状态
            incremental_manager.save_index()
        else:
            logger.info("文档库无变更，跳过索引")
            doc_stats = {"files": 0, "chunks": 0, "errors": 0, "skipped": 1}
    else:
        doc_stats = doc_indexer.index_directory()

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
