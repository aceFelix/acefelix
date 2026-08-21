"""
知识图谱核心引擎
基于 NetworkX 构建图结构，支持实体和关系的增删改查，
使用 JSON 文件持久化存储。

@author aceFelix
"""

from __future__ import annotations

import json
import os
import re
import shutil
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import networkx as nx

from models import ENTITY_COLORS, RELATION_LABELS, Entity, EntityType, Relation, RelationType


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
        # 实体类型表：name -> color（动态，持久化于 graph.json）
        # 默认用 models.ENTITY_COLORS 的 10 种内置类型
        self._types: Dict[str, str] = dict(ENTITY_COLORS)
        # 关系类型表：name -> 中文标签（动态，持久化于 graph.json）
        self._relation_types: Dict[str, str] = dict(RELATION_LABELS)
        # 数据版本号（乐观锁）：每次保存 +1，客户端编辑时携带，不匹配即冲突
        self._version: int = 1
        # 写锁：串行化并发写操作（FastAPI sync handler 在线程池中并发执行）
        self._write_lock = threading.Lock()
        self.load()

    @property
    def version(self) -> int:
        """当前数据版本号（乐观锁用）"""
        return self._version

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

        # 加载实体类型表（旧数据无 types 字段时保留默认 10 种）
        saved_types = data.get("types")
        if isinstance(saved_types, dict) and saved_types:
            self._types = dict(saved_types)

        # 加载关系类型表（旧数据无 relation_types 字段时保留默认 12 种）
        saved_rel_types = data.get("relation_types")
        if isinstance(saved_rel_types, dict) and saved_rel_types:
            self._relation_types = dict(saved_rel_types)

        # 加载数据版本号（旧数据无 version 时从 1 开始）
        self._version = int(data.get("version", 1))

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
        """
        将图谱数据持久化到 JSON 文件
        - 写锁串行化并发保存；版本号 +1（乐观锁）
        - 保存前自动备份到 data/backups/，滚动保留最近 20 份（同秒覆盖）
        - 优先"写临时文件 + 原子替换"（写入中断不损坏既有数据）；
          若运行环境的安全组件拦截 rename 类操作，降级为直接写入
        """
        with self._write_lock:
            self._backup()
            self._version += 1
            self.data_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "entities": [e.to_dict() for e in self._entities.values()],
                "relations": [r.to_dict() for r in self._relations.values()],
                "types": self._types,
                "relation_types": self._relation_types,
                "version": self._version,
            }
            tmp_path = self.data_path.with_suffix(".json.tmp")
            try:
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_path, self.data_path)
            except PermissionError:
                # 环境拦截 rename：降级直接写入
                with open(self.data_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                try:
                    tmp_path.unlink(missing_ok=True)
                except OSError:
                    pass

    def _backup(self, keep: int = 20) -> None:
        """
        保存前备份当前数据文件；备份失败不阻塞主流程
        @param keep: 滚动保留的备份份数
        """
        try:
            if not self.data_path.exists():
                return
            backup_dir = self.data_path.parent / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            shutil.copy2(self.data_path, backup_dir / f"graph_{stamp}.json")
            # 滚动清理：按文件名排序（含时间戳），删除最旧的
            backups = sorted(
                p for p in backup_dir.glob("graph_*.json")
                if re.fullmatch(r"graph_\d{8}_\d{6}\.json", p.name)
            )
            for old in backups[:-keep]:
                try:
                    old.unlink()
                except OSError:
                    pass  # 环境拦截删除时跳过，不阻塞
        except OSError:
            pass  # 备份是尽力而为，失败不影响保存

    # ------------------------------------------------------------------ #
    # 实体类型管理（动态，持久化于 graph.json 的 types 字段）
    # ------------------------------------------------------------------ #

    def list_types(self) -> Dict[str, str]:
        """返回全部实体类型（name -> color）"""
        return dict(self._types)

    def add_type(self, name: str, color: str) -> None:
        """新增实体类型"""
        name = (name or "").strip()
        if not name:
            raise ValueError("类型名称不能为空")
        if name in self._types:
            raise ValueError(f"类型已存在: {name}")
        self._types[name] = color
        self.save()

    def update_type(self, name: str, color: str) -> None:
        """修改类型颜色"""
        if name not in self._types:
            raise ValueError(f"类型不存在: {name}")
        self._types[name] = color
        self.save()

    def rename_type(self, old_name: str, new_name: str) -> None:
        """
        重命名类型，并级联更新所有使用该类型的实体
        """
        new_name = (new_name or "").strip()
        if old_name not in self._types:
            raise ValueError(f"类型不存在: {old_name}")
        if not new_name:
            raise ValueError("新名称不能为空")
        if new_name == old_name:
            return
        if new_name in self._types:
            raise ValueError(f"类型已存在: {new_name}")

        self._types[new_name] = self._types.pop(old_name)
        for entity in self._entities.values():
            if entity.type == old_name:
                entity.type = new_name
                entity.updated_at = datetime.now().isoformat()
                if entity.id in self.graph:
                    self.graph.nodes[entity.id]["type"] = new_name
        self.save()

    def delete_type(self, name: str) -> None:
        """
        删除类型；若有实体正在使用则拒绝（fail-closed）
        """
        if name not in self._types:
            raise ValueError(f"类型不存在: {name}")
        in_use = sum(1 for e in self._entities.values() if e.type == name)
        if in_use:
            raise ValueError(f"类型正在被 {in_use} 个实体使用，无法删除")
        del self._types[name]
        self.save()

    def _validate_type(self, type: str) -> None:
        """校验实体类型已注册"""
        if type not in self._types:
            raise ValueError(f"未注册的实体类型: {type}")

    # ------------------------------------------------------------------ #
    # 关系类型管理（动态，持久化于 graph.json 的 relation_types 字段）
    # ------------------------------------------------------------------ #

    def list_relation_types(self) -> Dict[str, str]:
        """返回全部关系类型（name -> 中文标签）"""
        return dict(self._relation_types)

    def add_relation_type(self, name: str, label: str) -> None:
        """新增关系类型"""
        name = (name or "").strip()
        if not name:
            raise ValueError("类型代码不能为空")
        if name in self._relation_types:
            raise ValueError(f"类型已存在: {name}")
        self._relation_types[name] = (label or "").strip() or name
        self.save()

    def update_relation_type(self, name: str, label: str) -> None:
        """修改关系类型的中文标签"""
        if name not in self._relation_types:
            raise ValueError(f"类型不存在: {name}")
        self._relation_types[name] = (label or "").strip() or name
        self.save()

    def rename_relation_type(self, old_name: str, new_name: str) -> None:
        """
        重命名关系类型，并级联更新所有使用该类型的关系
        """
        new_name = (new_name or "").strip()
        if old_name not in self._relation_types:
            raise ValueError(f"类型不存在: {old_name}")
        if not new_name:
            raise ValueError("新名称不能为空")
        if new_name == old_name:
            return
        if new_name in self._relation_types:
            raise ValueError(f"类型已存在: {new_name}")

        self._relation_types[new_name] = self._relation_types.pop(old_name)
        for relation in self._relations.values():
            if relation.type == old_name:
                relation.type = new_name
                relation.updated_at = datetime.now().isoformat()
        # 同步更新图边
        for _, _, edge_data in self.graph.edges(data=True):
            if edge_data.get("type") == old_name:
                edge_data["type"] = new_name
        self.save()

    def delete_relation_type(self, name: str) -> None:
        """
        删除关系类型；若有关联正在使用则拒绝（fail-closed）
        """
        if name not in self._relation_types:
            raise ValueError(f"类型不存在: {name}")
        in_use = sum(1 for r in self._relations.values() if r.type == name)
        if in_use:
            raise ValueError(f"类型正在被 {in_use} 条关系使用，无法删除")
        del self._relation_types[name]
        self.save()

    def _validate_relation_type(self, type: str) -> None:
        """校验关系类型已注册"""
        if type not in self._relation_types:
            raise ValueError(f"未注册的关系类型: {type}")

    # ------------------------------------------------------------------ #
    # 实体 CRUD
    # ------------------------------------------------------------------ #

    def add_entity(
        self,
        name: str,
        type: str,
        properties: Optional[Dict[str, Any]] = None,
        color: Optional[str] = None,
    ) -> Entity:
        """
        添加实体

        @param name: 实体名称
        @param type: 实体类型
        @param properties: 实体属性字典
        @param color: 自定义颜色（可选，None 时使用类型默认色）
        @return 创建的 Entity 对象
        """
        self._validate_type(type)
        entity_id = str(uuid.uuid4())
        entity = Entity(
            id=entity_id,
            name=name,
            type=type,
            properties=properties or {},
            color=color,
        )
        self._entities[entity_id] = entity
        self.graph.add_node(
            entity_id,
            name=name,
            type=type,
            properties=entity.properties,
            color=color,
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
    ) -> Optional[Entity]:
        """
        更新实体

        @param entity_id: 实体 ID
        @param name: 新名称（可选）
        @param type: 新类型（可选）
        @param properties: 新属性（可选，整体替换）
        @param color: 新颜色（可选，传入 None 不清除，传入空串清除）
        @return 更新后的 Entity，不存在则返回 None
        """
        entity = self._entities.get(entity_id)
        if not entity:
            return None

        if name is not None:
            entity.name = name
        if type is not None:
            self._validate_type(type)
            entity.type = type
        if properties is not None:
            entity.properties = properties
        if color is not None:
            # 空字符串视为清除自定义颜色，回退到类型默认色
            entity.color = color or None
        entity.updated_at = datetime.now().isoformat()

        # 同步更新图节点
        if entity_id in self.graph:
            self.graph.nodes[entity_id]["name"] = entity.name
            self.graph.nodes[entity_id]["type"] = entity.type
            self.graph.nodes[entity_id]["properties"] = entity.properties
            self.graph.nodes[entity_id]["color"] = entity.color

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
        self._validate_relation_type(type)

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
        source: Optional[str] = None,
        target: Optional[str] = None,
        type: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
    ) -> Optional[Relation]:
        """
        更新关系

        @param relation_id: 关系 ID
        @param source: 新源实体 ID（可选）
        @param target: 新目标实体 ID（可选）
        @param type: 新关系类型（可选）
        @param properties: 新属性（可选，整体替换）
        @return 更新后的 Relation，关系不存在返回 None；新端点不存在抛 ValueError
        """
        relation = self._relations.get(relation_id)
        if not relation:
            return None

        new_source = source if source is not None else relation.source
        new_target = target if target is not None else relation.target
        if new_source not in self._entities or new_target not in self._entities:
            raise ValueError("源实体或目标实体不存在")

        old_source, old_target = relation.source, relation.target
        relation.source = new_source
        relation.target = new_target
        if type is not None:
            self._validate_relation_type(type)
            relation.type = type
        if properties is not None:
            relation.properties = properties
        relation.updated_at = datetime.now().isoformat()

        # 同步更新图边：端点变化时重建边，否则原位更新
        if self.graph.has_edge(old_source, old_target):
            self.graph.remove_edge(old_source, old_target)
        self.graph.add_edge(
            relation.source,
            relation.target,
            id=relation.id,
            type=relation.type,
            properties=relation.properties,
        )

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
