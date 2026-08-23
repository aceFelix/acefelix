"""
AceFelix 知识图谱 MCP Server

通过 MCP (Model Context Protocol) 标准协议，将个人知识图谱以"工具"形式
暴露给任意 AI Agent（jarvis、Claude Desktop 等）。Agent 只需在客户端
配置本 server 的启动命令，即可查询画像、搜索实体、探索关联路径，
甚至经确认后新增实体/关系，让 Agent 更了解 aceFelix。

本模块基于官方 mcp SDK 的 FastMCP 实现，复用 knowledge_graph.KnowledgeGraph
引擎（与 api.py 共用同一 data/graph.json 数据文件），以 stdio transport
与客户端进程通信。

@author aceFelix
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from knowledge_graph import KnowledgeGraph

# 与 api.py 共用同一数据文件（clone 后先运行 python seed.py 生成）
DATA_PATH = Path(__file__).parent / "data" / "graph.json"
kg = KnowledgeGraph(str(DATA_PATH))

# MCP Server 实例：instructions 会在客户端连接时展示给模型，指导其如何用图
mcp = FastMCP(
    "acefelix-knowledge",
    instructions=(
        "这是 aceFelix 的个人知识图谱，存储了他的身份背景、技能、知识领域、"
        "项目、工具、兴趣、任务与目标及其相互关系。查询用户信息时优先使用 "
        "get_profile 获取画像摘要；需要了解具体实体或关系时使用 search_entity、"
        "get_neighbors、find_paths。新增知识（实体/关系）前先通过 list_types / "
        "list_relation_types 确认类型存在。"
    ),
)


def _dumps(obj: Any) -> str:
    """JSON 序列化工具函数（保留中文，缩进便于阅读）"""
    return json.dumps(obj, ensure_ascii=False, indent=2)


def _person_entity() -> Optional[Any]:
    """找到代表"本人"的 Person 类型实体（通常只有 1 个）"""
    for e in kg.list_entities():
        if e.type == "Person":
            return e
    return None


# ------------------------------------------------------------------ #
# 只读工具：画像 / 查询
# ------------------------------------------------------------------ #

@mcp.tool()
def get_profile(max_items: int = 15) -> str:
    """获取 aceFelix 的人物画像摘要。

    以 Person 实体为中心，聚合其一跳关系（技能/知识/项目/工具/兴趣/任务/目标），
    返回紧凑 JSON。Agent 需要"了解用户"时调用本工具。
    """
    person = _person_entity()
    if not person:
        return _dumps({"person": None, "note": "图谱中暂无 Person 类型实体"})

    sub = kg.get_neighbors(person.id, degree=1)
    names = {e["id"]: e["name"] for e in sub["entities"]}
    items: List[Dict[str, Any]] = []
    for r in sub["relations"]:
        # 只收集以本人为端点的边（排除"反向"的边，避免重复）
        if r["source"] == person.id:
            other_id, direction = r["target"], "->"
        elif r["target"] == person.id:
            other_id, direction = r["source"], "<-"
        else:
            continue
        items.append({
            "relation": r["type"],
            "direction": direction,
            "entity": names.get(other_id, other_id),
        })
    items = items[:max_items]

    return _dumps({
        "person": {"id": person.id, "name": person.name, "properties": person.properties},
        "connections": items,
        "hint": "如需某个实体的更多详情，用 search_entity 或 get_entity 查询",
    })


@mcp.tool()
def search_entity(query: str, limit: int = 10) -> str:
    """按关键词搜索实体（匹配名称或属性值），返回实体列表 JSON。"""
    results = kg.search(query)[:limit]
    return _dumps({"query": query, "results": [e.to_dict() for e in results]})


@mcp.tool()
def get_entity(entity_id: str) -> str:
    """根据实体 ID 获取实体详情（含属性、类型、颜色）。ID 可用 search_entity 查询。"""
    entity = kg.get_entity(entity_id)
    if not entity:
        return _dumps({"error": f"实体不存在: {entity_id}"})
    return _dumps(entity.to_dict())


@mcp.tool()
def list_entities(type: Optional[str] = None, limit: int = 50) -> str:
    """列出全部实体，可按类型过滤（type 为可选参数，如 Person/Skill/Project）。"""
    entities = kg.list_entities(type_filter=type)[:limit]
    return _dumps({"type": type, "count": len(entities),
                   "entities": [e.to_dict() for e in entities]})


@mcp.tool()
def get_neighbors(entity_id: str, degree: int = 1) -> str:
    """获取某实体的邻居子图（degree=1 直接邻居，degree=2 二度邻居），返回实体与关系。"""
    if not kg.get_entity(entity_id):
        return _dumps({"error": f"实体不存在: {entity_id}"})
    return _dumps(kg.get_neighbors(entity_id, degree=degree))


@mcp.tool()
def find_paths(source: str, target: str, max_hops: int = 3, max_paths: int = 10) -> str:
    """查询两个实体之间的关联路径（按跳数从短到长），source/target 为实体 ID。"""
    try:
        return _dumps(kg.find_paths(source, target, max_hops=max_hops, max_paths=max_paths))
    except ValueError as e:
        return _dumps({"error": str(e)})


@mcp.tool()
def common_neighbors(entity: str, other: str) -> str:
    """查询两个实体的共同邻居（找出它们之间的共同点），entity/other 为实体 ID。"""
    try:
        return _dumps(kg.common_neighbors(entity, other))
    except ValueError as e:
        return _dumps({"error": str(e)})


@mcp.tool()
def get_stats() -> str:
    """获取图谱统计信息（实体数、关系数、类型分布）。"""
    return _dumps(kg.get_stats())


@mcp.tool()
def list_types() -> str:
    """列出全部实体类型（name -> 颜色）。新增实体前先确认类型存在。"""
    return _dumps(kg.list_types())


@mcp.tool()
def list_relation_types() -> str:
    """列出全部关系类型（代码 -> 中文标签）。新增关系前先确认类型存在。"""
    return _dumps(kg.list_relation_types())


# ------------------------------------------------------------------ #
# 写工具：由 Agent 维护图谱（客户端侧默认需用户确认）
# ------------------------------------------------------------------ #

@mcp.tool()
def add_entity(
    name: str,
    type: str,
    properties: Optional[Dict[str, Any]] = None,
    color: Optional[str] = None,
) -> str:
    """新增一个实体（节点），如新技能、新项目、新知识。type 需为已注册的实体类型
    （用 list_types 查看）；properties 为键值属性，如 {"proficiency": "高级"}。"""
    try:
        entity = kg.add_entity(name=name, type=type, properties=properties, color=color)
    except ValueError as e:
        return _dumps({"error": str(e)})
    return _dumps({"ok": True, "id": entity.id, "name": entity.name, "type": entity.type})


@mcp.tool()
def add_relation(
    source: str,
    target: str,
    type: str,
    properties: Optional[Dict[str, Any]] = None,
) -> str:
    """新增一条关系（边），连接两个实体。type 需为已注册的关系类型
    （用 list_relation_types 查看）；source/target 为实体 ID。"""
    try:
        relation = kg.add_relation(source=source, target=target, type=type, properties=properties)
    except ValueError as e:
        return _dumps({"error": str(e)})
    if not relation:
        return _dumps({"error": "源实体或目标实体不存在"})
    return _dumps({"ok": True, "id": relation.id, "source": source, "target": target, "type": type})


if __name__ == "__main__":
    # 以 stdio transport 运行：jarvis 等客户端通过子进程 stdio 与之通信
    mcp.run(transport="stdio")
