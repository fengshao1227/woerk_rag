"""
多模态索引模块 - 支持图片、表格等非文本内容的索引

提供 OCR、视觉模型描述、表格结构化提取等能力
"""

from .indexer import MultimodalIndexer, ImageProcessor, TableExtractor

__all__ = [
    'MultimodalIndexer',
    'ImageProcessor',
    'TableExtractor'
]
