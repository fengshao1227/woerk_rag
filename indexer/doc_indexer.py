"""
文档索引器
"""
from pathlib import Path
from typing import List, Dict
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, CollectionStatus
import hashlib
import markdown
from bs4 import BeautifulSoup

from config import (
    PROJECT_ROOT, IGNORE_PATTERNS,
    QDRANT_HOST, QDRANT_PORT, QDRANT_API_KEY, QDRANT_COLLECTION_NAME, QDRANT_USE_HTTPS
)
from utils.embeddings import EmbeddingModel
from utils.logger import logger
from .chunker import DocumentChunker


class DocumentIndexer:
    """文档索引器"""
    
    def __init__(self):
        self.embedding_model = EmbeddingModel()
        self.chunker = DocumentChunker()
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
    
    def _get_doc_type(self, file_path: Path) -> str:
        """根据文件扩展名判断文档类型"""
        ext = file_path.suffix.lower()
        type_map = {
            '.md': 'markdown',
            '.txt': 'text',
            '.html': 'html',
            '.htm': 'html',
        }
        return type_map.get(ext, 'text')
    
    def _read_markdown(self, file_path: Path) -> str:
        """读取 Markdown 文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"读取 Markdown 文件失败: {file_path}, 错误: {e}")
            return ""
    
    def _read_html(self, file_path: Path) -> str:
        """读取 HTML 文件并提取文本"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                html = f.read()
            soup = BeautifulSoup(html, 'html.parser')
            # 移除脚本和样式
            for script in soup(["script", "style"]):
                script.decompose()
            return soup.get_text()
        except Exception as e:
            logger.error(f"读取 HTML 文件失败: {file_path}, 错误: {e}")
            return ""
    
    def _read_text(self, file_path: Path) -> str:
        """读取纯文本文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"读取文本文件失败: {file_path}, 错误: {e}")
            return ""
    
    def _read_document(self, file_path: Path) -> str:
        """读取文档内容"""
        doc_type = self._get_doc_type(file_path)
        
        if doc_type == 'markdown':
            return self._read_markdown(file_path)
        elif doc_type == 'html':
            return self._read_html(file_path)
        else:
            return self._read_text(file_path)
    
    def _find_doc_files(self, root_path: Path) -> List[Path]:
        """查找所有文档文件"""
        doc_files = []
        patterns = ['*.md', '*.txt', '*.html', '*.htm']
        
        for pattern in patterns:
            for file_path in root_path.rglob(pattern):
                if file_path.is_file() and not self._should_ignore(file_path):
                    doc_files.append(file_path)
        
        return doc_files
    
    def _generate_id(self, file_path: str, chunk_index: int) -> str:
        """生成唯一ID"""
        content = f"doc:{file_path}:{chunk_index}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def index_file(self, file_path: Path) -> int:
        """
        索引单个文档文件
        
        Returns:
            索引的块数量
        """
        content = self._read_document(file_path)
        
        if not content.strip():
            return 0
        
        doc_type = self._get_doc_type(file_path)
        chunks = self.chunker.chunk_document(content, str(file_path), doc_type)
        
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
                "type": "document",
                "doc_type": doc_type,
                "chunk_index": chunk["chunk_index"],
            }
            
            if "heading" in chunk:
                payload["heading"] = chunk["heading"]
            if "heading_level" in chunk:
                payload["heading_level"] = chunk["heading_level"]
            
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
        
        logger.info(f"索引文档: {file_path} ({len(chunks)} 块)")
        return len(chunks)
    
    def index_directory(self, root_path: Path = None) -> Dict[str, int]:
        """
        索引整个目录的文档
        
        Returns:
            统计信息
        """
        if root_path is None:
            root_path = PROJECT_ROOT
        
        root_path = Path(root_path)
        if not root_path.exists():
            logger.error(f"目录不存在: {root_path}")
            return {"files": 0, "chunks": 0, "errors": 0}
        
        doc_files = self._find_doc_files(root_path)
        logger.info(f"找到 {len(doc_files)} 个文档文件")
        
        stats = {"files": 0, "chunks": 0, "errors": 0}
        
        for file_path in doc_files:
            try:
                chunks_count = self.index_file(file_path)
                stats["files"] += 1
                stats["chunks"] += chunks_count
            except Exception as e:
                logger.error(f"索引文档失败: {file_path}, 错误: {e}")
                stats["errors"] += 1
        
        logger.info(f"文档索引完成: {stats}")
        return stats


if __name__ == "__main__":
    indexer = DocumentIndexer()
    stats = indexer.index_directory()
    print(f"文档索引统计: {stats}")
