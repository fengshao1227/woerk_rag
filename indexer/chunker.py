"""
文本切分工具
"""
from typing import List, Dict
import re
from langchain_text_splitters import RecursiveCharacterTextSplitter
from config import CHUNK_SIZE, CHUNK_OVERLAP


class CodeChunker:
    """代码切分器"""
    
    def __init__(self, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
    def chunk_code(self, code: str, file_path: str, language: str = "php") -> List[Dict]:
        """
        切分代码文件
        
        Args:
            code: 代码内容
            file_path: 文件路径
            language: 编程语言
            
        Returns:
            切分后的代码块列表
        """
        chunks = []
        
        # 按函数/类切分
        if language == "php":
            pattern = r'(?:(?:public|private|protected|static)\s+)?(?:function\s+\w+|class\s+\w+|trait\s+\w+|interface\s+\w+)'
        elif language == "javascript":
            pattern = r'(?:function\s+\w+|class\s+\w+|const\s+\w+\s*=|export\s+(?:default\s+)?(?:function|class|const))'
        else:
            pattern = r'(?:function|class|def|class)\s+\w+'
        
        matches = list(re.finditer(pattern, code, re.MULTILINE))
        
        if not matches:
            # 如果没有找到函数/类，使用通用切分
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                separators=["\n\n", "\n", " ", ""]
            )
            splits = text_splitter.split_text(code)
            for i, split in enumerate(splits):
                chunks.append({
                    "content": split,
                    "file_path": file_path,
                    "language": language,
                    "chunk_index": i,
                    "type": "code"
                })
            return chunks
        
        # 按函数/类边界切分
        for i, match in enumerate(matches):
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(code)
            
            chunk_content = code[start:end].strip()
            if len(chunk_content) > self.chunk_size:
                # 如果单个函数太长，进一步切分
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=self.chunk_size,
                    chunk_overlap=self.chunk_overlap,
                    separators=["\n\n", "\n", " ", ""]
                )
                sub_splits = text_splitter.split_text(chunk_content)
                for j, sub_split in enumerate(sub_splits):
                    chunks.append({
                        "content": sub_split,
                        "file_path": file_path,
                        "language": language,
                        "chunk_index": len(chunks),
                        "type": "code",
                        "symbol": match.group().strip()
                    })
            else:
                chunks.append({
                    "content": chunk_content,
                    "file_path": file_path,
                    "language": language,
                    "chunk_index": len(chunks),
                    "type": "code",
                    "symbol": match.group().strip()
                })
        
        return chunks


class DocumentChunker:
    """文档切分器"""
    
    def __init__(self, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n## ", "\n\n# ", "\n\n", "\n", " ", ""]
        )
    
    def chunk_document(self, content: str, file_path: str, doc_type: str = "markdown") -> List[Dict]:
        """
        切分文档
        
        Args:
            content: 文档内容
            file_path: 文件路径
            doc_type: 文档类型
            
        Returns:
            切分后的文档块列表
        """
        # 提取标题层级
        lines = content.split('\n')
        current_heading = None
        heading_level = 0
        
        chunks = []
        current_section = []
        
        for line in lines:
            # 检测 Markdown 标题
            if line.startswith('#'):
                # 保存当前章节
                if current_section:
                    section_text = '\n'.join(current_section)
                    if len(section_text.strip()) > 0:
                        # 如果章节太长，进一步切分
                        if len(section_text) > self.chunk_size:
                            splits = self.text_splitter.split_text(section_text)
                            for i, split in enumerate(splits):
                                chunks.append({
                                    "content": split,
                                    "file_path": file_path,
                                    "doc_type": doc_type,
                                    "chunk_index": len(chunks),
                                    "type": "document",
                                    "heading": current_heading,
                                    "heading_level": heading_level
                                })
                        else:
                            chunks.append({
                                "content": section_text,
                                "file_path": file_path,
                                "doc_type": doc_type,
                                "chunk_index": len(chunks),
                                "type": "document",
                                "heading": current_heading,
                                "heading_level": heading_level
                            })
                
                # 更新当前标题
                current_heading = line.strip()
                heading_level = len(line) - len(line.lstrip('#'))
                current_section = [line]
            else:
                current_section.append(line)
        
        # 处理最后一个章节
        if current_section:
            section_text = '\n'.join(current_section)
            if len(section_text.strip()) > 0:
                if len(section_text) > self.chunk_size:
                    splits = self.text_splitter.split_text(section_text)
                    for i, split in enumerate(splits):
                        chunks.append({
                            "content": split,
                            "file_path": file_path,
                            "doc_type": doc_type,
                            "chunk_index": len(chunks),
                            "type": "document",
                            "heading": current_heading,
                            "heading_level": heading_level
                        })
                else:
                    chunks.append({
                        "content": section_text,
                        "file_path": file_path,
                        "doc_type": doc_type,
                        "chunk_index": len(chunks),
                        "type": "document",
                        "heading": current_heading,
                        "heading_level": heading_level
                    })
        
        # 如果没有找到标题，使用通用切分
        if not chunks:
            splits = self.text_splitter.split_text(content)
            for i, split in enumerate(splits):
                chunks.append({
                    "content": split,
                    "file_path": file_path,
                    "doc_type": doc_type,
                    "chunk_index": i,
                    "type": "document"
                })
        
        return chunks
