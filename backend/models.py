"""
知识图谱数据模型定义
定义实体类型、关系类型，以及实体和关系的数据结构。

@author aceFelix
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class EntityType(str, Enum):
    """实体类型枚举"""

    PERSON = "Person"            # 人物
    SKILL = "Skill"              # 技能
    KNOWLEDGE = "Knowledge"      # 知识领域
    INTEREST = "Interest"        # 兴趣爱好
    PROJECT = "Project"          # 项目
    TASK = "Task"                # 任务
    TOOL = "Tool"                # 工具
    EDUCATION = "Education"      # 教育背景
    GOAL = "Goal"                # 目标
    EVENT = "Event"              # 事件


class RelationType(str, Enum):
    """关系类型枚举"""

    HAS_SKILL = "HAS_SKILL"            # 掌握技能
    KNOWS = "KNOWS"                    # 了解知识
    INTERESTED_IN = "INTERESTED_IN"    # 感兴趣
    WORKS_ON = "WORKS_ON"              # 参与项目
    DOING = "DOING"                    # 正在做
    USES = "USES"                       # 使用工具
    STUDIED_AT = "STUDIED_AT"          # 就读于
    RELATED_TO = "RELATED_TO"          # 相关
    DEPENDS_ON = "DEPENDS_ON"          # 依赖于
    PART_OF = "PART_OF"                # 属于一部分
    LEADS_TO = "LEADS_TO"              # 导致/通向
    SIMILAR_TO = "SIMILAR_TO"          # 相似


# 实体类型 -> 默认颜色（用于前端 3D 可视化着色）
ENTITY_COLORS: Dict[str, str] = {
    EntityType.PERSON.value: "#ff6b6b",
    EntityType.SKILL.value: "#4ecdc4",
    EntityType.KNOWLEDGE.value: "#45b7d1",
    EntityType.INTEREST.value: "#f9ca24",
    EntityType.PROJECT.value: "#a55eea",
    EntityType.TASK.value: "#fd79a8",
    EntityType.TOOL.value: "#6c5ce7",
    EntityType.EDUCATION.value: "#00b894",
    EntityType.GOAL.value: "#e17055",
    EntityType.EVENT.value: "#fdcb6e",
}


@dataclass
class Entity:
    """
    实体（图节点）
    表示知识图谱中的一个节点，如一个人、一项技能、一个项目等。

    @author aceFelix
    """

    id: str
    name: str
    type: str
    properties: Dict[str, Any] = field(default_factory=dict)
    color: Optional[str] = None  # 自定义颜色（3D 可视化用，None 时使用类型默认色）
    size: Optional[float] = None  # 自定义大小（3D 球体半径，None 时按连接数自动计算）
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "properties": self.properties,
            "color": self.color,
            "size": self.size,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Entity":
        """从字典反序列化"""
        return cls(
            id=data["id"],
            name=data["name"],
            type=data["type"],
            properties=data.get("properties", {}),
            color=data.get("color"),
            size=data.get("size"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
        )


@dataclass
class Relation:
    """
    关系（图边）
    表示两个实体之间的关系，如"掌握技能"、"参与项目"等。

    @author aceFelix
    """

    id: str
    source: str  # 源实体 ID
    target: str  # 目标实体 ID
    type: str
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "id": self.id,
            "source": self.source,
            "target": self.target,
            "type": self.type,
            "properties": self.properties,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Relation":
        """从字典反序列化"""
        return cls(
            id=data["id"],
            source=data["source"],
            target=data["target"],
            type=data["type"],
            properties=data.get("properties", {}),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
        )
