"""
知识图谱存储模块
支持 NetworkX（轻量级）和 Neo4j（生产级）两种后端
"""

import json
import pickle
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict

import networkx as nx

from utils.logger import logger


@dataclass
class Entity:
    """实体节点"""
    id: str
    name: str
    type: str
    properties: Dict[str, Any] = field(default_factory=dict)
    source_chunks: List[str] = field(default_factory=list)  # 来源文档块ID


@dataclass
class Relation:
    """关系边"""
    source_id: str
    target_id: str
    relation_type: str
    properties: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0


class GraphStore:
    """
    知识图谱存储
    使用 NetworkX 作为轻量级图存储后端
    """

    def __init__(
        self,
        storage_path: str = "./data/knowledge_graph",
        graph_name: str = "default"
    ):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.graph_name = graph_name
        self.graph_file = self.storage_path / f"{graph_name}.gpickle"
        self.metadata_file = self.storage_path / f"{graph_name}_metadata.json"

        # 初始化图
        self.graph: nx.DiGraph = nx.DiGraph()

        # 实体索引（按类型）
        self.entity_index: Dict[str, Set[str]] = defaultdict(set)

        # 名称到ID的映射
        self.name_to_id: Dict[str, str] = {}

        # 加载已有图
        self._load_graph()

        logger.info(f"GraphStore 初始化完成: {self.graph.number_of_nodes()} 节点, {self.graph.number_of_edges()} 边")

    def _load_graph(self):
        """加载已有图"""
        if self.graph_file.exists():
            try:
                with open(self.graph_file, 'rb') as f:
                    self.graph = pickle.load(f)

                # 重建索引
                self._rebuild_index()
                logger.info(f"加载图谱: {self.graph_file}")
            except Exception as e:
                logger.error(f"加载图谱失败: {e}")
                self.graph = nx.DiGraph()

    def _save_graph(self):
        """保存图到文件"""
        try:
            with open(self.graph_file, 'wb') as f:
                pickle.dump(self.graph, f)

            # 保存元数据
            metadata = {
                "node_count": self.graph.number_of_nodes(),
                "edge_count": self.graph.number_of_edges(),
                "entity_types": {k: len(v) for k, v in self.entity_index.items()}
            }
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"保存图谱失败: {e}")

    def _rebuild_index(self):
        """重建实体索引"""
        self.entity_index.clear()
        self.name_to_id.clear()

        for node_id, data in self.graph.nodes(data=True):
            entity_type = data.get('type', 'unknown')
            self.entity_index[entity_type].add(node_id)

            name = data.get('name', '')
            if name:
                self.name_to_id[name.lower()] = node_id

    def add_entity(self, entity: Entity) -> str:
        """
        添加实体节点

        Args:
            entity: 实体对象

        Returns:
            实体ID
        """
        # 检查是否已存在同名实体
        existing_id = self.name_to_id.get(entity.name.lower())
        if existing_id:
            # 合并属性和来源
            existing_data = self.graph.nodes[existing_id]
            existing_data['properties'].update(entity.properties)
            existing_data['source_chunks'].extend(entity.source_chunks)
            existing_data['source_chunks'] = list(set(existing_data['source_chunks']))
            return existing_id

        # 添加新节点
        self.graph.add_node(
            entity.id,
            name=entity.name,
            type=entity.type,
            properties=entity.properties,
            source_chunks=entity.source_chunks
        )

        # 更新索引
        self.entity_index[entity.type].add(entity.id)
        self.name_to_id[entity.name.lower()] = entity.id

        return entity.id

    def add_relation(self, relation: Relation) -> bool:
        """
        添加关系边

        Args:
            relation: 关系对象

        Returns:
            是否成功添加
        """
        # 检查节点是否存在
        if relation.source_id not in self.graph:
            logger.warning(f"源节点不存在: {relation.source_id}")
            return False
        if relation.target_id not in self.graph:
            logger.warning(f"目标节点不存在: {relation.target_id}")
            return False

        # 添加边
        self.graph.add_edge(
            relation.source_id,
            relation.target_id,
            relation_type=relation.relation_type,
            properties=relation.properties,
            confidence=relation.confidence
        )

        return True

    def add_entities_and_relations(
        self,
        entities: List[Entity],
        relations: List[Relation]
    ) -> Tuple[int, int]:
        """
        批量添加实体和关系

        Args:
            entities: 实体列表
            relations: 关系列表

        Returns:
            (添加的实体数, 添加的关系数)
        """
        entity_count = 0
        relation_count = 0

        # 添加实体
        for entity in entities:
            self.add_entity(entity)
            entity_count += 1

        # 添加关系
        for relation in relations:
            if self.add_relation(relation):
                relation_count += 1

        # 保存
        self._save_graph()

        logger.info(f"添加 {entity_count} 个实体, {relation_count} 条关系")
        return entity_count, relation_count

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """获取实体"""
        if entity_id not in self.graph:
            return None

        data = self.graph.nodes[entity_id]
        return Entity(
            id=entity_id,
            name=data.get('name', ''),
            type=data.get('type', ''),
            properties=data.get('properties', {}),
            source_chunks=data.get('source_chunks', [])
        )

    def get_entity_by_name(self, name: str) -> Optional[Entity]:
        """通过名称获取实体"""
        entity_id = self.name_to_id.get(name.lower())
        if entity_id:
            return self.get_entity(entity_id)
        return None

    def get_entities_by_type(self, entity_type: str) -> List[Entity]:
        """获取指定类型的所有实体"""
        entity_ids = self.entity_index.get(entity_type, set())
        return [self.get_entity(eid) for eid in entity_ids if self.get_entity(eid)]

    def get_neighbors(
        self,
        entity_id: str,
        direction: str = "both",
        relation_types: Optional[List[str]] = None,
        max_depth: int = 1
    ) -> List[Tuple[Entity, str, Entity]]:
        """
        获取实体的邻居节点

        Args:
            entity_id: 实体ID
            direction: 方向 (in/out/both)
            relation_types: 过滤的关系类型
            max_depth: 最大深度

        Returns:
            [(源实体, 关系类型, 目标实体), ...]
        """
        if entity_id not in self.graph:
            return []

        results = []
        visited = {entity_id}
        current_level = [entity_id]

        for depth in range(max_depth):
            next_level = []

            for node_id in current_level:
                # 出边
                if direction in ("out", "both"):
                    for _, target, data in self.graph.out_edges(node_id, data=True):
                        rel_type = data.get('relation_type', '')
                        if relation_types and rel_type not in relation_types:
                            continue

                        source_entity = self.get_entity(node_id)
                        target_entity = self.get_entity(target)
                        if source_entity and target_entity:
                            results.append((source_entity, rel_type, target_entity))

                        if target not in visited:
                            visited.add(target)
                            next_level.append(target)

                # 入边
                if direction in ("in", "both"):
                    for source, _, data in self.graph.in_edges(node_id, data=True):
                        rel_type = data.get('relation_type', '')
                        if relation_types and rel_type not in relation_types:
                            continue

                        source_entity = self.get_entity(source)
                        target_entity = self.get_entity(node_id)
                        if source_entity and target_entity:
                            results.append((source_entity, rel_type, target_entity))

                        if source not in visited:
                            visited.add(source)
                            next_level.append(source)

            current_level = next_level

        return results

    def get_subgraph(
        self,
        entity_ids: List[str],
        max_depth: int = 1
    ) -> 'GraphStore':
        """
        获取子图

        Args:
            entity_ids: 中心实体ID列表
            max_depth: 扩展深度

        Returns:
            子图 GraphStore
        """
        # 收集所有相关节点
        all_nodes = set(entity_ids)
        current_level = set(entity_ids)

        for _ in range(max_depth):
            next_level = set()
            for node_id in current_level:
                if node_id in self.graph:
                    # 出边邻居
                    next_level.update(self.graph.successors(node_id))
                    # 入边邻居
                    next_level.update(self.graph.predecessors(node_id))

            next_level -= all_nodes
            all_nodes.update(next_level)
            current_level = next_level

        # 创建子图
        subgraph = GraphStore(
            storage_path=str(self.storage_path),
            graph_name=f"{self.graph_name}_subgraph"
        )
        subgraph.graph = self.graph.subgraph(all_nodes).copy()
        subgraph._rebuild_index()

        return subgraph

    def search_entities(
        self,
        query: str,
        entity_types: Optional[List[str]] = None,
        limit: int = 10
    ) -> List[Entity]:
        """
        搜索实体（简单的名称匹配）

        Args:
            query: 搜索词
            entity_types: 过滤的实体类型
            limit: 返回数量限制

        Returns:
            匹配的实体列表
        """
        query_lower = query.lower()
        results = []

        for node_id, data in self.graph.nodes(data=True):
            if entity_types and data.get('type') not in entity_types:
                continue

            name = data.get('name', '').lower()
            if query_lower in name:
                entity = self.get_entity(node_id)
                if entity:
                    results.append(entity)
                    if len(results) >= limit:
                        break

        return results

    def get_statistics(self) -> Dict[str, Any]:
        """获取图谱统计信息"""
        return {
            "node_count": self.graph.number_of_nodes(),
            "edge_count": self.graph.number_of_edges(),
            "entity_types": {k: len(v) for k, v in self.entity_index.items()},
            "density": nx.density(self.graph) if self.graph.number_of_nodes() > 0 else 0,
            "is_connected": nx.is_weakly_connected(self.graph) if self.graph.number_of_nodes() > 0 else True
        }

    def clear(self):
        """清空图谱"""
        self.graph.clear()
        self.entity_index.clear()
        self.name_to_id.clear()
        self._save_graph()
        logger.info("图谱已清空")

    def export_to_json(self, output_path: str) -> str:
        """导出图谱为 JSON 格式"""
        data = {
            "nodes": [],
            "edges": []
        }

        for node_id, node_data in self.graph.nodes(data=True):
            data["nodes"].append({
                "id": node_id,
                **node_data
            })

        for source, target, edge_data in self.graph.edges(data=True):
            data["edges"].append({
                "source": source,
                "target": target,
                **edge_data
            })

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"图谱已导出: {output_path}")
        return output_path
