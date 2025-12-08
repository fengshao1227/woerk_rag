"""
索引所有数据（代码+文档）
"""
import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from indexer.code_indexer import CodeIndexer
from indexer.doc_indexer import DocumentIndexer
from utils.logger import logger


def main():
    """索引所有数据"""
    logger.info("开始索引所有数据...")
    
    # 索引代码
    logger.info("=" * 50)
    logger.info("开始索引代码库...")
    code_indexer = CodeIndexer()
    code_stats = code_indexer.index_directory()
    logger.info(f"代码索引完成: {code_stats}")
    
    # 索引文档
    logger.info("=" * 50)
    logger.info("开始索引文档...")
    doc_indexer = DocumentIndexer()
    doc_stats = doc_indexer.index_directory()
    logger.info(f"文档索引完成: {doc_stats}")
    
    # 汇总统计
    logger.info("=" * 50)
    total_stats = {
        "total_files": code_stats["files"] + doc_stats["files"],
        "total_chunks": code_stats["chunks"] + doc_stats["chunks"],
        "total_errors": code_stats["errors"] + doc_stats["errors"],
        "code_files": code_stats["files"],
        "code_chunks": code_stats["chunks"],
        "doc_files": doc_stats["files"],
        "doc_chunks": doc_stats["chunks"],
    }
    logger.info(f"索引完成！总统计: {total_stats}")


if __name__ == "__main__":
    main()
