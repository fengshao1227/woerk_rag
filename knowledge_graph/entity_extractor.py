"""
知识图谱 - 实体抽取器
使用 LLM 从文本中抽取实体和关系
"""

import json
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from utils.logger import logger


@dataclass
class Entity:
    """实体"""
    name: str
    type: str  # PERSON, ORG, TECH, CONCEPT, LOCATION, EVENT, etc.
    properties: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "properties": self.properties
        }


@dataclass
class Relation:
    """关系"""
    source: str  # 源实体名称
    target: str  # 目标实体名称
    relation_type: str  # 关系类型
    properties: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "relation_type": self.relation_type,
            "properties": self.properties
        }


@dataclass
class ExtractionResult:
    """抽取结果"""
    entities: List[Entity]
    relations: List[Relation]
    source_text: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class EntityExtractor:
    """
    实体关系抽取器
    使用 LLM 从文本中抽取实体和关系
    """

    # 实体类型定义
    ENTITY_TYPES = [
        "PERSON",      # 人物
        "ORG",         # 组织/公司
        "TECH",        # 技术/框架/库
        "CONCEPT",     # 概念/术语
        "LOCATION",    # 地点
        "EVENT",       # 事件
        "PRODUCT",     # 产品
        "CODE",        # 代码元素（函数、类、模块）
    ]

    # 关系类型定义
    RELATION_TYPES = [
        "USES",           # 使用
        "IMPLEMENTS",     # 实现
        "EXTENDS",        # 继承/扩展
        "DEPENDS_ON",     # 依赖
        "CONTAINS",       # 包含
        "BELONGS_TO",     # 属于
        "CREATED_BY",     # 创建者
        "RELATED_TO",     # 相关
        "CALLS",          # 调用
        "RETURNS",        # 返回
        "PART_OF",        # 部分
        "SIMILAR_TO",     # 相似
    ]

    EXTRACTION_PROMPT = """你是一个专业的知识图谱实体关系抽取专家。请从以下文本中抽取实体和关系。

## 实体类型
- PERSON: 人物
- ORG: 组织/公司
- TECH: 技术/框架/库
- CONCEPT: 概念/术语
- LOCATION: 地点
- EVENT: 事件
- PRODUCT: 产品
- CODE: 代码元素（函数、类、模块）

## 关系类型
- USES: 使用
- IMPLEMENTS: 实现
- EXTENDS: 继承/扩展
- DEPENDS_ON: 依赖
- CONTAINS: 包含
- BELONGS_TO: 属于
- CREATED_BY: 创建者
- RELATED_TO: 相关
- CALLS: 调用
- RETURNS: 返回
- PART_OF: 部分
- SIMILAR_TO: 相似

## 输入文本
{text}

## 输出格式
请以 JSON 格式输出，包含 entities 和 relations 两个数组：
```json
{{
  "entities": [
    {{"name": "实体名称", "type": "实体类型", "properties": {{"description": "简短描述"}}}}
  ],
  "relations": [
    {{"source": "源实体名称", "target": "目标实体名称", "relation_type": "关系类型"}}
  ]
}}
```

注意：
1. 只抽取文本中明确提到的实体和关系
2. 实体名称要规范化（如 "Python" 而不是 "python语言"）
3. 关系必须在已抽取的实体之间建立
4. 每个实体只出现一次，避免重复

请输出 JSON："""

    def __init__(self, llm_client=None):
        """
        初始化实体抽取器

        Args:
            llm_client: LLM 客户端，如果为 None 则延迟初始化
        """
        self._llm_client = llm_client

    @property
    def llm_client(self):
        """延迟初始化 LLM 客户端"""
        if self._llm_client is None:
            from utils.llm import get_llm_client
            self._llm_client = get_llm_client()
        return self._llm_client

    def extract(self, text: str, max_length: int = 4000) -> ExtractionResult:
        """
        从文本中抽取实体和关系

        Args:
            text: 输入文本
            max_length: 文本最大长度，超过则截断

        Returns:
            ExtractionResult: 抽取结果
        """
        # 截断过长文本
        if len(text) > max_length:
            text = text[:max_length] + "..."

        # 构建 prompt
        prompt = self.EXTRACTION_PROMPT.format(text=text)

        try:
            # 调用 LLM
            response = self.llm_client.generate(prompt)

            # 解析 JSON 响应
            entities, relations = self._parse_response(response)

            return ExtractionResult(
                entities=entities,
                relations=relations,
                source_text=text,
                metadata={"model": "llm"}
            )

        except Exception as e:
            logger.error(f"实体抽取失败: {e}")
            return ExtractionResult(
                entities=[],
                relations=[],
                source_text=text,
                metadata={"error": str(e)}
            )

    def extract_batch(self, texts: List[str], max_length: int = 4000) -> List[ExtractionResult]:
        """
        批量抽取实体和关系

        Args:
            texts: 文本列表
            max_length: 每个文本的最大长度

        Returns:
            List[ExtractionResult]: 抽取结果列表
        """
        results = []
        for text in texts:
            result = self.extract(text, max_length)
            results.append(result)
        return results

    def _parse_response(self, response: str) -> Tuple[List[Entity], List[Relation]]:
        """
        解析 LLM 响应

        Args:
            response: LLM 响应文本

        Returns:
            Tuple[List[Entity], List[Relation]]: 实体和关系列表
        """
        entities = []
        relations = []

        try:
            # 尝试提取 JSON
            json_match = re.search(r'\{[\s\S]*\}', response)
            if not json_match:
                logger.warning("响应中未找到 JSON")
                return entities, relations

            json_str = json_match.group()
            data = json.loads(json_str)

            # 解析实体
            entity_names = set()
            for e in data.get("entities", []):
                if not e.get("name") or not e.get("type"):
                    continue

                # 规范化实体类型
                entity_type = e["type"].upper()
                if entity_type not in self.ENTITY_TYPES:
                    entity_type = "CONCEPT"

                entity = Entity(
                    name=e["name"],
                    type=entity_type,
                    properties=e.get("properties", {})
                )
                entities.append(entity)
                entity_names.add(e["name"])

            # 解析关系
            for r in data.get("relations", []):
                source = r.get("source")
                target = r.get("target")
                relation_type = r.get("relation_type", "").upper()

                # 验证关系的源和目标实体存在
                if not source or not target:
                    continue
                if source not in entity_names or target not in entity_names:
                    continue

                # 规范化关系类型
                if relation_type not in self.RELATION_TYPES:
                    relation_type = "RELATED_TO"

                relation = Relation(
                    source=source,
                    target=target,
                    relation_type=relation_type,
                    properties=r.get("properties", {})
                )
                relations.append(relation)

        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}")
        except Exception as e:
            logger.error(f"响应解析失败: {e}")

        return entities, relations

    def merge_results(self, results: List[ExtractionResult]) -> ExtractionResult:
        """
        合并多个抽取结果，去重并建立跨文档关系

        Args:
            results: 抽取结果列表

        Returns:
            ExtractionResult: 合并后的结果
        """
        entity_map: Dict[str, Entity] = {}
        relation_set: set = set()
        relations: List[Relation] = []

        for result in results:
            # 合并实体（按名称去重）
            for entity in result.entities:
                key = entity.name.lower()
                if key not in entity_map:
                    entity_map[key] = entity
                else:
                    # 合并属性
                    existing = entity_map[key]
                    existing.properties.update(entity.properties)

            # 合并关系（去重）
            for relation in result.relations:
                key = (relation.source.lower(), relation.target.lower(), relation.relation_type)
                if key not in relation_set:
                    relation_set.add(key)
                    relations.append(relation)

        return ExtractionResult(
            entities=list(entity_map.values()),
            relations=relations,
            source_text="[merged]",
            metadata={"merged_count": len(results)}
        )


# 简化的基于规则的实体抽取（不依赖 LLM）
class RuleBasedExtractor:
    """
    基于规则的实体抽取器
    用于快速抽取常见的技术实体，不依赖 LLM
    """

    # 常见技术关键词
    TECH_KEYWORDS = {
        "python", "javascript", "typescript", "java", "go", "rust", "c++",
        "react", "vue", "angular", "svelte", "next.js", "nuxt",
        "fastapi", "flask", "django", "express", "spring",
        "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
        "docker", "kubernetes", "aws", "gcp", "azure",
        "langchain", "openai", "anthropic", "claude", "gpt",
        "qdrant", "pinecone", "weaviate", "milvus",
    }

    # 代码模式
    CODE_PATTERNS = [
        r'\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b',  # CamelCase 类名
        r'\b([a-z_]+)\(\)',  # 函数调用
        r'`([^`]+)`',  # 代码块
    ]

    def extract(self, text: str) -> ExtractionResult:
        """
        基于规则抽取实体

        Args:
            text: 输入文本

        Returns:
            ExtractionResult: 抽取结果
        """
        entities = []
        entity_names = set()

        text_lower = text.lower()

        # 抽取技术关键词
        for keyword in self.TECH_KEYWORDS:
            if keyword in text_lower:
                if keyword not in entity_names:
                    entities.append(Entity(
                        name=keyword.title() if keyword.islower() else keyword,
                        type="TECH",
                        properties={"source": "rule"}
                    ))
                    entity_names.add(keyword)

        # 抽取代码元素
        for pattern in self.CODE_PATTERNS:
            matches = re.findall(pattern, text)
            for match in matches:
                if match.lower() not in entity_names and len(match) > 2:
                    entities.append(Entity(
                        name=match,
                        type="CODE",
                        properties={"source": "rule"}
                    ))
                    entity_names.add(match.lower())

        return ExtractionResult(
            entities=entities,
            relations=[],  # 规则抽取不建立关系
            source_text=text,
            metadata={"extractor": "rule_based"}
        )
