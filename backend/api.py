"""
FastAPI 服务入口
提供知识图谱的 REST API 接口，支持实体和关系的增删改查、搜索、统计等。

@author aceFelix
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from knowledge_graph import KnowledgeGraph
from models import RelationType

# 初始化 FastAPI 应用
app = FastAPI(
    title="AceFelix 个人知识图谱",
    description="个人知识图谱 API - 支持实体和关系的增删改查与 3D 可视化",
    version="0.1.0",
)

# 跨域支持（前端运行在 5173 端口）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化知识图谱引擎
DATA_PATH = Path(__file__).parent / "data" / "graph.json"
kg = KnowledgeGraph(str(DATA_PATH))


# ------------------------------------------------------------------ #
# 请求模型
# ------------------------------------------------------------------ #

class EntityCreate(BaseModel):
    """创建实体的请求体"""

    name: str
    type: str
    properties: Optional[Dict[str, Any]] = {}
    color: Optional[str] = None  # 自定义颜色，None 时使用类型默认色
    size: Optional[float] = None  # 自定义大小，None 时按连接数自动计算


class EntityUpdate(BaseModel):
    """更新实体的请求体"""

    name: Optional[str] = None
    type: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None
    color: Optional[str] = None  # 传入空串清除自定义颜色，回退类型默认色
    size: Optional[float] = None  # 传入 0 清除自定义大小，回退自动计算


class RelationCreate(BaseModel):
    """创建关系的请求体"""

    source: str
    target: str
    type: str
    properties: Optional[Dict[str, Any]] = {}


class RelationUpdate(BaseModel):
    """更新关系的请求体"""

    source: Optional[str] = None  # 新源实体 ID（可选）
    target: Optional[str] = None  # 新目标实体 ID（可选）
    type: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None


# ------------------------------------------------------------------ #
# 元数据接口
# ------------------------------------------------------------------ #

@app.get("/api/meta")
def get_meta() -> Dict[str, Any]:
    """
    获取元数据：实体类型、关系类型、颜色映射
    供前端渲染使用（实体类型为动态类型表）
    """
    types = kg.list_types()
    return {
        "entity_types": list(types.keys()),
        "relation_types": [r.value for r in RelationType],
        "entity_colors": types,
    }


# ------------------------------------------------------------------ #
# 实体类型管理接口
# ------------------------------------------------------------------ #

class TypeCreate(BaseModel):
    """新增实体类型的请求体"""

    name: str
    color: str = "#888888"


class TypeUpdate(BaseModel):
    """修改实体类型的请求体（改色 / 改名）"""

    color: Optional[str] = None
    new_name: Optional[str] = None


@app.get("/api/types")
def list_types() -> Dict[str, str]:
    """列出全部实体类型（name -> color）"""
    return kg.list_types()


@app.post("/api/types")
def create_type(body: TypeCreate) -> Dict[str, str]:
    """新增实体类型"""
    try:
        kg.add_type(body.name, body.color)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"name": body.name.strip(), "color": body.color}


@app.put("/api/types/{name}")
def update_type(name: str, body: TypeUpdate) -> Dict[str, str]:
    """修改实体类型：改颜色和/或重命名（重命名会级联更新实体）"""
    try:
        if body.new_name is not None:
            kg.rename_type(name, body.new_name)
            name = body.new_name.strip()
        if body.color is not None:
            kg.update_type(name, body.color)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"name": name, "color": kg.list_types()[name]}


@app.delete("/api/types/{name}")
def delete_type(name: str) -> Dict[str, str]:
    """删除实体类型（有实体使用时拒绝）"""
    try:
        kg.delete_type(name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"deleted": name}


# ------------------------------------------------------------------ #
# 实体接口
# ------------------------------------------------------------------ #

@app.get("/api/entities")
def list_entities(type: Optional[str] = None) -> List[Dict[str, Any]]:
    """列出所有实体，可通过 ?type= 过滤"""
    entities = kg.list_entities(type_filter=type)
    return [e.to_dict() for e in entities]


@app.get("/api/entities/{entity_id}")
def get_entity(entity_id: str) -> Dict[str, Any]:
    """获取单个实体"""
    entity = kg.get_entity(entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="实体不存在")
    return entity.to_dict()


@app.post("/api/entities")
def create_entity(body: EntityCreate) -> Dict[str, Any]:
    """创建实体"""
    entity = kg.add_entity(
        name=body.name,
        type=body.type,
        properties=body.properties,
        color=body.color,
        size=body.size,
    )
    return entity.to_dict()


@app.put("/api/entities/{entity_id}")
def update_entity(entity_id: str, body: EntityUpdate) -> Dict[str, Any]:
    """更新实体"""
    entity = kg.update_entity(
        entity_id=entity_id,
        name=body.name,
        type=body.type,
        properties=body.properties,
        color=body.color,
        size=body.size,
    )
    if not entity:
        raise HTTPException(status_code=404, detail="实体不存在")
    return entity.to_dict()


@app.delete("/api/entities/{entity_id}")
def delete_entity(entity_id: str) -> Dict[str, str]:
    """删除实体（级联删除关联关系）"""
    success = kg.delete_entity(entity_id)
    if not success:
        raise HTTPException(status_code=404, detail="实体不存在")
    return {"message": "删除成功"}


# ------------------------------------------------------------------ #
# 关系接口
# ------------------------------------------------------------------ #

@app.get("/api/relations")
def list_relations(type: Optional[str] = None) -> List[Dict[str, Any]]:
    """列出所有关系，可通过 ?type= 过滤"""
    relations = kg.list_relations(type_filter=type)
    return [r.to_dict() for r in relations]


@app.post("/api/relations")
def create_relation(body: RelationCreate) -> Dict[str, Any]:
    """创建关系"""
    relation = kg.add_relation(
        source=body.source,
        target=body.target,
        type=body.type,
        properties=body.properties,
    )
    if not relation:
        raise HTTPException(status_code=400, detail="源实体或目标实体不存在")
    return relation.to_dict()


@app.put("/api/relations/{relation_id}")
def update_relation(relation_id: str, body: RelationUpdate) -> Dict[str, Any]:
    """更新关系（可修改源/目标实体、类型、属性）"""
    try:
        relation = kg.update_relation(
            relation_id=relation_id,
            source=body.source,
            target=body.target,
            type=body.type,
            properties=body.properties,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not relation:
        raise HTTPException(status_code=404, detail="关系不存在")
    return relation.to_dict()


@app.delete("/api/relations/{relation_id}")
def delete_relation(relation_id: str) -> Dict[str, str]:
    """删除关系"""
    success = kg.delete_relation(relation_id)
    if not success:
        raise HTTPException(status_code=404, detail="关系不存在")
    return {"message": "删除成功"}


# ------------------------------------------------------------------ #
# 图谱查询接口
# ------------------------------------------------------------------ #

@app.get("/api/graph")
def get_full_graph() -> Dict[str, Any]:
    """获取完整图谱数据（前端 3D 可视化使用）"""
    return kg.to_dict()


@app.get("/api/graph/neighbors/{entity_id}")
def get_neighbors(entity_id: str, degree: int = 1) -> Dict[str, Any]:
    """获取实体的邻居子图"""
    if not kg.get_entity(entity_id):
        raise HTTPException(status_code=404, detail="实体不存在")
    return kg.get_neighbors(entity_id, degree=degree)


@app.get("/api/search")
def search_entities(q: str) -> List[Dict[str, Any]]:
    """搜索实体"""
    if not q:
        return []
    results = kg.search(q)
    return [e.to_dict() for e in results]


@app.get("/api/stats")
def get_stats() -> Dict[str, Any]:
    """获取图谱统计信息"""
    return kg.get_stats()


# ------------------------------------------------------------------ #
# 启动入口
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8800)
