"""
代码索引器
"""
import os
from pathlib import Path
from typing import List, Dict
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
import hashlib

from config import (
    PROJECT_ROOT, CODE_PATTERNS, IGNORE_PATTERNS,
    QDRANT_HOST, QDRANT_PORT, QDRANT_API_KEY, QDRANT_COLLECTION_NAME, QDRANT_USE_HTTPS
)
from utils.embeddings import EmbeddingModel
from utils.logger import logger
from .chunker import CodeChunker


class CodeIndexer:
    """代码索引器"""
    
    def __init__(self):
        self.embedding_model = EmbeddingModel()
        self.chunker = CodeChunker()
        # 使用 URL 模式连接 Qdrant（明确指定 HTTP/HTTPS）
        protocol = "https" if QDRANT_USE_HTTPS else "http"
        url = f"{protocol}://{QDRANT_HOST}:{QDRANT_PORT}"
        self.qdrant_client = QdrantClient(
            url=url,
            api_key=QDRANT_API_KEY if QDRANT_API_KEY else None
        )
        self.collection_name = QDRANT_COLLECTION_NAME
        self._ensure_collection()
    
    def _ensure_collection(self):
        """确保集合存在"""
        collections = self.qdrant_client.get_collections().collections
        collection_names = [c.name for c in collections]
        
        if self.collection_name not in collection_names:
            embedding_dim = self.embedding_model.get_embedding_dim()
            self.qdrant_client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=embedding_dim,
                    distance=Distance.COSINE
                )
            )
            logger.info(f"创建集合: {self.collection_name}")
    
    def _should_ignore(self, file_path: Path) -> bool:
        """判断文件是否应该被忽略"""
        path_str = str(file_path)
        for pattern in IGNORE_PATTERNS:
            pattern = pattern.strip().rstrip('/')
            if pattern in path_str or path_str.startswith(pattern):
                return True
        return False
    
    def _get_language(self, file_path: Path) -> str:
        """根据文件扩展名判断语言"""
        ext = file_path.suffix.lower()
        lang_map = {
            '.php': 'php',
            '.js': 'javascript',
            '.vue': 'javascript',
            '.ts': 'typescript',
            '.py': 'python',
            '.java': 'java',
            '.go': 'go',
            '.rs': 'rust',
        }
        return lang_map.get(ext, 'unknown')
    
    def _find_code_files(self, root_path: Path) -> List[Path]:
        """查找所有代码文件"""
        code_files = []
        
        for pattern in CODE_PATTERNS:
            pattern = pattern.strip()
            for file_path in root_path.rglob(pattern):
                if file_path.is_file() and not self._should_ignore(file_path):
                    code_files.append(file_path)
        
        return code_files
    
    def _generate_id(self, file_path: str, chunk_index: int) -> str:
        """生成唯一ID"""
        content = f"{file_path}:{chunk_index}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def index_file(self, file_path: Path) -> int:
        """
        索引单个文件
        
        Returns:
            索引的块数量
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            logger.warning(f"无法读取文件（编码问题）: {file_path}")
            return 0
        except Exception as e:
            logger.error(f"读取文件失败: {file_path}, 错误: {e}")
            return 0
        
        if not content.strip():
            return 0
        
        language = self._get_language(file_path)
        chunks = self.chunker.chunk_code(content, str(file_path), language)
        
        if not chunks:
            return 0
        
        # 生成嵌入
        texts = [chunk["content"] for chunk in chunks]
        embeddings = self.embedding_model.encode(texts, show_progress_bar=False)
        
        # 准备点数据
        points = []
        for i, chunk in enumerate(chunks):
            chunk_id = self._generate_id(str(file_path), chunk["chunk_index"])
            
            payload = {
                "content": chunk["content"],
                "file_path": str(file_path),
                "type": "code",
                "language": language,
                "chunk_index": chunk["chunk_index"],
            }
            
            if "symbol" in chunk:
                payload["symbol"] = chunk["symbol"]
            
            points.append(
                PointStruct(
                    id=chunk_id,
                    vector=embeddings[i].tolist(),
                    payload=payload
                )
            )
        
        # 批量上传到 Qdrant
        self.qdrant_client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        
        logger.info(f"索引文件: {file_path} ({len(chunks)} 块)")
        return len(chunks)
    
    def index_directory(self, root_path: Path = None) -> Dict[str, int]:
        """
        索引整个目录
        
        Returns:
            统计信息
        """
        if root_path is None:
            root_path = PROJECT_ROOT
        
        root_path = Path(root_path)
        if not root_path.exists():
            logger.error(f"目录不存在: {root_path}")
            return {"files": 0, "chunks": 0, "errors": 0}
        
        code_files = self._find_code_files(root_path)
        logger.info(f"找到 {len(code_files)} 个代码文件")
        
        stats = {"files": 0, "chunks": 0, "errors": 0}
        
        for file_path in code_files:
            try:
                chunks_count = self.index_file(file_path)
                stats["files"] += 1
                stats["chunks"] += chunks_count
            except Exception as e:
                logger.error(f"索引文件失败: {file_path}, 错误: {e}")
                stats["errors"] += 1
        
        logger.info(f"索引完成: {stats}")
        return stats


if __name__ == "__main__":
    indexer = CodeIndexer()
    stats = indexer.index_directory()
    print(f"索引统计: {stats}")
