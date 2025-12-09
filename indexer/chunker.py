"""
文本切分工具 - 支持 Contextual Chunking（上下文感知切分）
"""
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
import re
from langchain_text_splitters import RecursiveCharacterTextSplitter
from config import (
    CHUNK_SIZE, CHUNK_OVERLAP,
    CONTEXT_PREFIX_ENABLE, CONTEXT_PREFIX_MAX_LEN, CONTEXT_INJECT_TO_CONTENT
)


@dataclass
class HeadingContext:
    """标题上下文，用于维护标题层级栈"""
    level: int
    title: str
    raw: str  # 原始标题行（如 "## 安装指南"）


@dataclass
class DocumentContext:
    """文档上下文，维护切分过程中的状态"""
    file_path: str
    file_name: str
    file_title: Optional[str] = None  # 文档首标题
    heading_stack: List[HeadingContext] = field(default_factory=list)

    def update_heading(self, level: int, title: str, raw: str):
        """更新标题栈：遇到同级或更高级标题时弹出"""
        # 弹出同级或更低级别的标题
        while self.heading_stack and self.heading_stack[-1].level >= level:
            self.heading_stack.pop()
        # 压入新标题
        self.heading_stack.append(HeadingContext(level=level, title=title, raw=raw))
        # 设置文档首标题
        if self.file_title is None and level == 1:
            self.file_title = title

    def get_heading_hierarchy(self) -> List[str]:
        """获取完整的标题层级列表"""
        return [h.raw for h in self.heading_stack]

    def build_context_prefix(self) -> str:
        """构建面包屑路径前缀"""
        parts = [self.file_name]
        for h in self.heading_stack:
            parts.append(h.title)
        prefix = " > ".join(parts)
        # 截断过长的前缀
        if len(prefix) > CONTEXT_PREFIX_MAX_LEN:
            prefix = prefix[:CONTEXT_PREFIX_MAX_LEN - 3] + "..."
        return prefix


@dataclass
class CodeContext:
    """代码上下文"""
    file_path: str
    file_name: str
    language: str
    file_docstring: Optional[str] = None  # 文件级 docstring
    current_class: Optional[str] = None   # 当前所在类
    class_docstring: Optional[str] = None # 类 docstring

    def build_context_prefix(self, symbol: str = None) -> str:
        """构建代码上下文前缀"""
        parts = [self.file_name]
        if self.current_class:
            parts.append(self.current_class)
        if symbol:
            # 提取符号名（去掉修饰符）
            symbol_name = self._extract_symbol_name(symbol)
            if symbol_name and symbol_name != self.current_class:
                parts.append(symbol_name)
        prefix = " > ".join(parts)
        if len(prefix) > CONTEXT_PREFIX_MAX_LEN:
            prefix = prefix[:CONTEXT_PREFIX_MAX_LEN - 3] + "..."
        return prefix

    def _extract_symbol_name(self, symbol: str) -> str:
        """从符号字符串中提取名称"""
        # 匹配 function/class/def 后的名称
        match = re.search(r'(?:function|class|def|trait|interface)\s+(\w+)', symbol)
        if match:
            return match.group(1)
        # 匹配 const name =
        match = re.search(r'const\s+(\w+)', symbol)
        if match:
            return match.group(1)
        return symbol.strip()


class CodeChunker:
    """代码切分器 - 支持上下文感知"""

    def __init__(self, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def _extract_file_docstring(self, code: str, language: str) -> Optional[str]:
        """提取文件级 docstring/注释"""
        lines = code.split('\n')
        docstring_lines = []

        if language == "python":
            # Python: 查找三引号 docstring
            in_docstring = False
            for line in lines[:20]:  # 只检查前 20 行
                stripped = line.strip()
                if not in_docstring:
                    if stripped.startswith('"""') or stripped.startswith("'''"):
                        in_docstring = True
                        quote = stripped[:3]
                        if stripped.endswith(quote) and len(stripped) > 6:
                            # 单行 docstring
                            return stripped[3:-3].strip()
                        docstring_lines.append(stripped[3:])
                    elif stripped.startswith('#'):
                        docstring_lines.append(stripped[1:].strip())
                    elif stripped and not stripped.startswith('import') and not stripped.startswith('from'):
                        break
                else:
                    if stripped.endswith(quote):
                        docstring_lines.append(stripped[:-3])
                        break
                    docstring_lines.append(stripped)
        else:
            # 其他语言: 查找文件开头的注释块
            for line in lines[:15]:
                stripped = line.strip()
                if stripped.startswith('//'):
                    docstring_lines.append(stripped[2:].strip())
                elif stripped.startswith('/*'):
                    docstring_lines.append(stripped[2:].strip())
                elif stripped.startswith('*'):
                    docstring_lines.append(stripped[1:].strip())
                elif stripped.startswith('#'):
                    docstring_lines.append(stripped[1:].strip())
                elif stripped.endswith('*/'):
                    docstring_lines.append(stripped[:-2].strip())
                    break
                elif stripped and not stripped.startswith('<?'):
                    break

        if docstring_lines:
            docstring = ' '.join(docstring_lines).strip()
            # 限制长度
            if len(docstring) > 200:
                docstring = docstring[:197] + "..."
            return docstring
        return None

    def _detect_class_context(self, code: str, position: int, language: str) -> Tuple[Optional[str], Optional[str]]:
        """检测当前位置是否在类内，返回 (类名, 类docstring)"""
        # 查找位置之前最近的类定义
        code_before = code[:position]

        if language == "python":
            pattern = r'class\s+(\w+)[^:]*:'
        elif language in ("javascript", "typescript"):
            pattern = r'class\s+(\w+)'
        elif language == "php":
            pattern = r'class\s+(\w+)'
        else:
            pattern = r'class\s+(\w+)'

        matches = list(re.finditer(pattern, code_before))
        if matches:
            last_match = matches[-1]
            class_name = last_match.group(1)

            # 简单的类 docstring 提取（类定义后的注释）
            class_end = last_match.end()
            remaining = code[class_end:class_end + 500]

            # 查找类后的 docstring
            docstring_match = re.search(r'"""(.+?)"""', remaining, re.DOTALL)
            if docstring_match:
                docstring = docstring_match.group(1).strip()
                if len(docstring) > 100:
                    docstring = docstring[:97] + "..."
                return class_name, docstring

            return class_name, None

        return None, None

    def chunk_code(self, code: str, file_path: str, language: str = "python") -> List[Dict]:
        """
        切分代码文件（支持上下文感知）

        Args:
            code: 代码内容
            file_path: 文件路径
            language: 编程语言

        Returns:
            切分后的代码块列表，每个块包含上下文信息
        """
        import os
        file_name = os.path.basename(file_path)

        # 初始化代码上下文
        context = CodeContext(
            file_path=file_path,
            file_name=file_name,
            language=language,
            file_docstring=self._extract_file_docstring(code, language)
        )

        chunks = []

        # 按函数/类切分
        if language == "php":
            pattern = r'(?:(?:public|private|protected|static)\s+)?(?:function\s+\w+|class\s+\w+|trait\s+\w+|interface\s+\w+)'
        elif language in ("javascript", "typescript"):
            pattern = r'(?:function\s+\w+|class\s+\w+|const\s+\w+\s*=|export\s+(?:default\s+)?(?:function|class|const))'
        elif language == "python":
            pattern = r'(?:def\s+\w+|class\s+\w+)'
        else:
            pattern = r'(?:function|class|def)\s+\w+'

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
                chunk = self._create_code_chunk(
                    content=split,
                    context=context,
                    chunk_index=i,
                    symbol=None
                )
                chunks.append(chunk)
            return chunks

        # 按函数/类边界切分
        for i, match in enumerate(matches):
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(code)

            chunk_content = code[start:end].strip()
            symbol = match.group().strip()

            # 检测类上下文
            class_name, class_doc = self._detect_class_context(code, start, language)
            context.current_class = class_name
            context.class_docstring = class_doc

            if len(chunk_content) > self.chunk_size:
                # 如果单个函数太长，进一步切分
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=self.chunk_size,
                    chunk_overlap=self.chunk_overlap,
                    separators=["\n\n", "\n", " ", ""]
                )
                sub_splits = text_splitter.split_text(chunk_content)
                for j, sub_split in enumerate(sub_splits):
                    chunk = self._create_code_chunk(
                        content=sub_split,
                        context=context,
                        chunk_index=len(chunks),
                        symbol=symbol
                    )
                    chunks.append(chunk)
            else:
                chunk = self._create_code_chunk(
                    content=chunk_content,
                    context=context,
                    chunk_index=len(chunks),
                    symbol=symbol
                )
                chunks.append(chunk)

        return chunks

    def _create_code_chunk(self, content: str, context: CodeContext,
                           chunk_index: int, symbol: str = None) -> Dict:
        """创建代码 chunk，包含上下文信息"""
        context_prefix = context.build_context_prefix(symbol)

        # 是否注入上下文到内容
        if CONTEXT_PREFIX_ENABLE and CONTEXT_INJECT_TO_CONTENT:
            enhanced_content = f"[代码: {context_prefix}]\n\n{content}"
        else:
            enhanced_content = content

        chunk = {
            "content": enhanced_content,
            "file_path": context.file_path,
            "language": context.language,
            "chunk_index": chunk_index,
            "type": "code",
        }

        # 添加上下文元数据
        if CONTEXT_PREFIX_ENABLE:
            chunk["context_prefix"] = context_prefix
            if context.file_docstring:
                chunk["file_docstring"] = context.file_docstring
            if context.current_class:
                chunk["class_context"] = context.current_class
                if context.class_docstring:
                    chunk["class_docstring"] = context.class_docstring

        if symbol:
            chunk["symbol"] = symbol

        return chunk


class DocumentChunker:
    """文档切分器 - 支持上下文感知"""

    def __init__(self, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n## ", "\n\n# ", "\n\n", "\n", " ", ""]
        )

    def _parse_heading(self, line: str) -> Tuple[int, str]:
        """解析标题行，返回 (级别, 标题文本)"""
        if not line.startswith('#'):
            return 0, ""

        # 计算 # 的数量
        level = 0
        for char in line:
            if char == '#':
                level += 1
            else:
                break

        # 提取标题文本
        title = line[level:].strip()
        return level, title

    def chunk_document(self, content: str, file_path: str, doc_type: str = "markdown") -> List[Dict]:
        """
        切分文档（支持上下文感知）

        Args:
            content: 文档内容
            file_path: 文件路径
            doc_type: 文档类型

        Returns:
            切分后的文档块列表，每个块包含上下文信息
        """
        import os
        file_name = os.path.basename(file_path)

        # 初始化文档上下文
        context = DocumentContext(
            file_path=file_path,
            file_name=file_name
        )

        lines = content.split('\n')
        chunks = []
        current_section = []
        current_heading = None
        current_level = 0

        for line in lines:
            # 检测 Markdown 标题
            if line.startswith('#'):
                # 保存当前章节
                if current_section:
                    section_chunks = self._process_section(
                        section_lines=current_section,
                        context=context,
                        heading=current_heading,
                        heading_level=current_level,
                        file_path=file_path,
                        doc_type=doc_type,
                        base_index=len(chunks)
                    )
                    chunks.extend(section_chunks)

                # 解析新标题
                level, title = self._parse_heading(line)
                if level > 0:
                    # 更新标题栈
                    context.update_heading(level, title, line.strip())
                    current_heading = line.strip()
                    current_level = level
                    current_section = [line]
                else:
                    current_section.append(line)
            else:
                current_section.append(line)

        # 处理最后一个章节
        if current_section:
            section_chunks = self._process_section(
                section_lines=current_section,
                context=context,
                heading=current_heading,
                heading_level=current_level,
                file_path=file_path,
                doc_type=doc_type,
                base_index=len(chunks)
            )
            chunks.extend(section_chunks)

        # 如果没有找到任何 chunk，使用通用切分
        if not chunks:
            splits = self.text_splitter.split_text(content)
            for i, split in enumerate(splits):
                chunk = self._create_doc_chunk(
                    content=split,
                    context=context,
                    chunk_index=i,
                    file_path=file_path,
                    doc_type=doc_type,
                    heading=None,
                    heading_level=0
                )
                chunks.append(chunk)

        return chunks

    def _process_section(self, section_lines: List[str], context: DocumentContext,
                         heading: str, heading_level: int, file_path: str,
                         doc_type: str, base_index: int) -> List[Dict]:
        """处理单个章节，返回 chunk 列表"""
        section_text = '\n'.join(section_lines)

        if len(section_text.strip()) == 0:
            return []

        chunks = []

        if len(section_text) > self.chunk_size:
            # 章节太长，需要进一步切分
            splits = self.text_splitter.split_text(section_text)
            for i, split in enumerate(splits):
                chunk = self._create_doc_chunk(
                    content=split,
                    context=context,
                    chunk_index=base_index + i,
                    file_path=file_path,
                    doc_type=doc_type,
                    heading=heading,
                    heading_level=heading_level
                )
                chunks.append(chunk)
        else:
            chunk = self._create_doc_chunk(
                content=section_text,
                context=context,
                chunk_index=base_index,
                file_path=file_path,
                doc_type=doc_type,
                heading=heading,
                heading_level=heading_level
            )
            chunks.append(chunk)

        return chunks

    def _create_doc_chunk(self, content: str, context: DocumentContext,
                          chunk_index: int, file_path: str, doc_type: str,
                          heading: str, heading_level: int) -> Dict:
        """创建文档 chunk，包含上下文信息"""
        context_prefix = context.build_context_prefix()
        heading_hierarchy = context.get_heading_hierarchy()

        # 是否注入上下文到内容
        if CONTEXT_PREFIX_ENABLE and CONTEXT_INJECT_TO_CONTENT and context_prefix:
            enhanced_content = f"[{context_prefix}]\n\n{content}"
        else:
            enhanced_content = content

        chunk = {
            "content": enhanced_content,
            "file_path": file_path,
            "doc_type": doc_type,
            "chunk_index": chunk_index,
            "type": "document",
        }

        # 添加标题信息
        if heading:
            chunk["heading"] = heading
        if heading_level > 0:
            chunk["heading_level"] = heading_level

        # 添加上下文元数据
        if CONTEXT_PREFIX_ENABLE:
            chunk["context_prefix"] = context_prefix
            if heading_hierarchy:
                chunk["heading_hierarchy"] = heading_hierarchy
            if context.file_title:
                chunk["file_title"] = context.file_title

        return chunk
