"""
知识图谱核心引擎
基于 NetworkX 构建图结构，支持实体和关系的增删改查，
使用 JSON 文件持久化存储。

@author aceFelix
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import networkx as nx

from models import Entity, EntityType, Relation, RelationType


class KnowledgeGraph:
    """
    知识图谱管理器
    封装 NetworkX 有向图，提供实体和关系的 CRUD 操作，
    并支持 JSON 文件的加载与持久化。

    @author aceFelix
    """

    def __init__(self, data_path: str = "data/graph.json"):
        """
        初始化知识图谱

        @param data_path: JSON 数据文件路径
        """
        self.data_path = Path(data_path)
        self.graph = nx.DiGraph()
        self._entities: Dict[str, Entity] = {}  # id -> Entity
        self._relations: Dict[str, Relation] = {}  # id -> Relation
        self.load()

    # ------------------------------------------------------------------ #
    # 持久化
    # ------------------------------------------------------------------ #

    def load(self) -> None:
        """从 JSON 文件加载图谱数据"""
        if not self.data_path.exists():
            self.data_path.parent.mkdir(parents=True, exist_ok=True)
            self.save()
            return

        with open(self.data_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 加载实体
        for ent_data in data.get("entities", []):
            entity = Entity.from_dict(ent_data)
            self._entities[entity.id] = entity
            self.graph.add_node(
                entity.id,
                name=entity.name,
                type=entity.type,
                properties=entity.properties,
                color=entity.color,
                size=entity.size,
            )

        # 加载关系
        for rel_data in data.get("relations", []):
            relation = Relation.from_dict(rel_data)
            if relation.source in self._entities and relation.target in self._entities:
                self._relations[relation.id] = relation
                self.graph.add_edge(
                    relation.source,
                    relation.target,
                    id=relation.id,
                    type=relation.type,
                    properties=relation.properties,
                )

    def save(self) -> None:
        """将图谱数据持久化到 JSON 文件"""
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "entities": [e.to_dict() for e in self._entities.values()],
            "relations": [r.to_dict() for r in self._relations.values()],
        }
        with open(self.data_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------ #
    # 实体 CRUD
    # ------------------------------------------------------------------ #

    def add_entity(
        self,
        name: str,
        type: str,
        properties: Optional[Dict[str, Any]] = None,
        color: Optional[str] = None,
        size: Optional[float] = None,
    ) -> Entity:
        """
        添加实体

        @param name: 实体名称
        @param type: 实体类型（EntityType 枚举值）
        @param properties: 实体属性字典
        @param color: 自定义颜色（可选，None 时使用类型默认色）
        @param size: 自定义大小（可选，None 时按连接数自动计算）
        @return 创建的 Entity 对象
        """
        entity_id = str(uuid.uuid4())
        entity = Entity(
            id=entity_id,
            name=name,
            type=type,
            properties=properties or {},
            color=color,
            size=size,
        )
        self._entities[entity_id] = entity
        self.graph.add_node(
            entity_id,
            name=name,
            type=type,
            properties=entity.properties,
            color=color,
            size=size,
        )
        self.save()
        return entity

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """根据 ID 获取实体"""
        return self._entities.get(entity_id)

    def list_entities(self, type_filter: Optional[str] = None) -> List[Entity]:
        """
        列出所有实体，可按类型过滤

        @param type_filter: 实体类型过滤（可选）
        @return 实体列表
        """
        entities = list(self._entities.values())
        if type_filter:
            entities = [e for e in entities if e.type == type_filter]
        return entities

    def update_entity(
        self,
        entity_id: str,
        name: Optional[str] = None,
        type: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
        color: Optional[str] = None,
        size: Optional[float] = None,
    ) -> Optional[Entity]:
        """
        更新实体

        @param entity_id: 实体 ID
        @param name: 新名称（可选）
        @param type: 新类型（可选）
        @param properties: 新属性（可选，整体替换）
        @param color: 新颜色（可选，传入 None 不清除，传入空串清除）
        @param size: 新大小（可选，传入 None 不清除，传入 0 清除）
        @return 更新后的 Entity，不存在则返回 None
        """
        entity = self._entities.get(entity_id)
        if not entity:
            return None

        if name is not None:
            entity.name = name
        if type is not None:
            entity.type = type
        if properties is not None:
            entity.properties = properties
        if color is not None:
            # 空字符串视为清除自定义颜色，回退到类型默认色
            entity.color = color or None
        if size is not None:
            # 0 或空视为清除自定义大小，回退自动计算
            entity.size = size if size > 0 else None
        entity.updated_at = datetime.now().isoformat()

        # 同步更新图节点
        if entity_id in self.graph:
            self.graph.nodes[entity_id]["name"] = entity.name
            self.graph.nodes[entity_id]["type"] = entity.type
            self.graph.nodes[entity_id]["properties"] = entity.properties
            self.graph.nodes[entity_id]["color"] = entity.color
            self.graph.nodes[entity_id]["size"] = entity.size

        self.save()
        return entity

    def delete_entity(self, entity_id: str) -> bool:
        """
        删除实体（级联删除关联的关系）

        @param entity_id: 实体 ID
        @return 是否删除成功
        """
        if entity_id not in self._entities:
            return False

        # 级联删除关联的关系
        relations_to_remove = [
            rid
            for rid, rel in self._relations.items()
            if rel.source == entity_id or rel.target == entity_id
        ]
        for rid in relations_to_remove:
            del self._relations[rid]

        del self._entities[entity_id]
        if entity_id in self.graph:
            self.graph.remove_node(entity_id)

        self.save()
        return True

    # ------------------------------------------------------------------ #
    # 关系 CRUD
    # ------------------------------------------------------------------ #

    def add_relation(
        self,
        source: str,
        target: str,
        type: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> Optional[Relation]:
        """
        添加关系

        @param source: 源实体 ID
        @param target: 目标实体 ID
        @param type: 关系类型（RelationType 枚举值）
        @param properties: 关系属性
        @return 创建的 Relation，源/目标不存在则返回 None
        """
        if source not in self._entities or target not in self._entities:
            return None

        relation_id = str(uuid.uuid4())
        relation = Relation(
            id=relation_id,
            source=source,
            target=target,
            type=type,
            properties=properties or {},
        )
        self._relations[relation_id] = relation
        self.graph.add_edge(
            source,
            target,
            id=relation_id,
            type=type,
            properties=relation.properties,
        )
        self.save()
        return relation

    def get_relation(self, relation_id: str) -> Optional[Relation]:
        """根据 ID 获取关系"""
        return self._relations.get(relation_id)

    def list_relations(self, type_filter: Optional[str] = None) -> List[Relation]:
        """列出所有关系，可按类型过滤"""
        relations = list(self._relations.values())
        if type_filter:
            relations = [r for r in relations if r.type == type_filter]
        return relations

    def update_relation(
        self,
        relation_id: str,
        type: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
    ) -> Optional[Relation]:
        """更新关系"""
        relation = self._relations.get(relation_id)
        if not relation:
            return None

        if type is not None:
            relation.type = type
        if properties is not None:
            relation.properties = properties
        relation.updated_at = datetime.now().isoformat()

        # 同步更新图边
        if relation.source in self.graph and relation.target in self.graph:
            edge_data = self.graph.edges[relation.source, relation.target]
            edge_data["type"] = relation.type
            edge_data["properties"] = relation.properties

        self.save()
        return relation

    def delete_relation(self, relation_id: str) -> bool:
        """删除关系"""
        relation = self._relations.get(relation_id)
        if not relation:
            return False

        del self._relations[relation_id]
        if relation.source in self.graph and relation.target in self.graph:
            if self.graph.has_edge(relation.source, relation.target):
                self.graph.remove_edge(relation.source, relation.target)

        self.save()
        return True

    # ------------------------------------------------------------------ #
    # 查询
    # ------------------------------------------------------------------ #

    def get_neighbors(self, entity_id: str, degree: int = 1) -> Dict[str, Any]:
        """
        获取实体的邻居子图

        @param entity_id: 中心实体 ID
        @param degree: 查询度数（1=直接邻居，2=二度邻居）
        @return 子图的实体和关系
        """
        if entity_id not in self._entities:
            return {"entities": [], "relations": []}

        # 使用 NetworkX 的 ego_graph 获取邻域子图
        sub_graph = nx.ego_graph(self.graph.to_undirected(), entity_id, radius=degree)
        node_ids = set(sub_graph.nodes())

        entities = [self._entities[nid] for nid in node_ids if nid in self._entities]
        relations = [
            r
            for r in self._relations.values()
            if r.source in node_ids and r.target in node_ids
        ]

        return {
            "entities": [e.to_dict() for e in entities],
            "relations": [r.to_dict() for r in relations],
        }

    def search(self, query: str) -> List[Entity]:
        """
        全文搜索实体（按名称模糊匹配）

        @param query: 搜索关键词
        @return 匹配的实体列表
        """
        query_lower = query.lower()
        return [
            e
            for e in self._entities.values()
            if query_lower in e.name.lower()
            or any(query_lower in str(v).lower() for v in e.properties.values())
        ]

    def get_stats(self) -> Dict[str, Any]:
        """获取图谱统计信息"""
        type_counts: Dict[str, int] = {}
        for entity in self._entities.values():
            type_counts[entity.type] = type_counts.get(entity.type, 0) + 1

        relation_type_counts: Dict[str, int] = {}
        for relation in self._relations.values():
            relation_type_counts[relation.type] = (
                relation_type_counts.get(relation.type, 0) + 1
            )

        return {
            "total_entities": len(self._entities),
            "total_relations": len(self._relations),
            "entity_types": type_counts,
            "relation_types": relation_type_counts,
        }

    def to_dict(self) -> Dict[str, Any]:
        """导出完整图谱数据"""
        return {
            "entities": [e.to_dict() for e in self._entities.values()],
            "relations": [r.to_dict() for r in self._relations.values()],
        }
