"""
FastAPI 服务入口
提供知识图谱的 REST API 接口，支持实体和关系的增删改查、搜索、统计等。

@author aceFelix
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import uuid
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ingest import IngestError, ingest_text, session_to_text
from knowledge_graph import KnowledgeGraph

# 初始化 FastAPI 应用
app = FastAPI(
    title="AceFelix 个人知识图谱",
    description="个人知识图谱 API - 支持实体和关系的增删改查与 3D 可视化",
    version="0.1.0",
)


def _cors_origins() -> List[str]:
    """
    计算 CORS 允许来源：
    - 默认：本地开发地址（Vite 5173）
    - 部署：通过环境变量 ALLOWED_ORIGINS 覆盖（逗号分隔，如
      "https://kg.pages.dev,https://kg.example.com"）
    """
    raw = os.environ.get("ALLOWED_ORIGINS", "")
    if raw.strip():
        return [o.strip() for o in raw.split(",") if o.strip()]
    return ["http://localhost:5173", "http://127.0.0.1:5173"]


# 跨域支持（本地默认放行 5173；生产环境用 ALLOWED_ORIGINS 指定前端域名）
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化知识图谱引擎
DATA_PATH = Path(__file__).parent / "data" / "graph.json"
kg = KnowledgeGraph(str(DATA_PATH))

# 上传文件存储目录（实体属性图片）
UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
# 挂载静态文件服务，前端可通过 /uploads/{filename} 访问上传的图片
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


# ------------------------------------------------------------------ #
# 请求模型
# ------------------------------------------------------------------ #

class EntityCreate(BaseModel):
    """创建实体的请求体"""

    name: str
    type: str
    properties: Optional[Dict[str, Any]] = {}
    color: Optional[str] = None  # 自定义颜色，None 时使用类型默认色


class EntityUpdate(BaseModel):
    """更新实体的请求体"""

    name: Optional[str] = None
    type: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None
    color: Optional[str] = None  # 传入空串清除自定义颜色，回退类型默认色
    if_version: Optional[int] = None  # 乐观锁：表单打开时的数据版本，不匹配返回 409


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
    if_version: Optional[int] = None  # 乐观锁：表单打开时的数据版本，不匹配返回 409


# ------------------------------------------------------------------ #
# 元数据接口
# ------------------------------------------------------------------ #

@app.get("/api/meta")
def get_meta() -> Dict[str, Any]:
    """
    获取元数据：实体类型、关系类型、颜色映射
    供前端渲染使用（实体类型与关系类型均为动态类型表）
    """
    types = kg.list_types()
    rel_types = kg.list_relation_types()
    return {
        "entity_types": list(types.keys()),
        "relation_types": list(rel_types.keys()),
        "relation_type_labels": rel_types,
        "entity_colors": types,
        "version": kg.version,
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
# 关系类型管理接口
# ------------------------------------------------------------------ #

class RelationTypeCreate(BaseModel):
    """新增关系类型的请求体"""

    name: str          # 类型代码（如 HAS_SKILL，建议大写下划线）
    label: str = ""    # 中文标签（界面显示用）


class RelationTypeUpdate(BaseModel):
    """修改关系类型的请求体（改标签 / 改名）"""

    label: Optional[str] = None
    new_name: Optional[str] = None


@app.get("/api/relation-types")
def list_relation_types() -> Dict[str, str]:
    """列出全部关系类型（name -> 中文标签）"""
    return kg.list_relation_types()


@app.post("/api/relation-types")
def create_relation_type(body: RelationTypeCreate) -> Dict[str, str]:
    """新增关系类型"""
    try:
        kg.add_relation_type(body.name, body.label)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"name": body.name.strip(), "label": (body.label or "").strip() or body.name.strip()}


@app.put("/api/relation-types/{name}")
def update_relation_type(name: str, body: RelationTypeUpdate) -> Dict[str, str]:
    """修改关系类型：改中文标签和/或重命名（重命名会级联更新关系）"""
    try:
        if body.new_name is not None:
            kg.rename_relation_type(name, body.new_name)
            name = body.new_name.strip()
        if body.label is not None:
            kg.update_relation_type(name, body.label)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"name": name, "label": kg.list_relation_types()[name]}


@app.delete("/api/relation-types/{name}")
def delete_relation_type(name: str) -> Dict[str, str]:
    """删除关系类型（有关系使用时拒绝）"""
    try:
        kg.delete_relation_type(name)
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
    )
    return entity.to_dict()


@app.put("/api/entities/{entity_id}")
def update_entity(entity_id: str, body: EntityUpdate) -> Dict[str, Any]:
    """更新实体（可携带 if_version 做并发冲突检测）"""
    if body.if_version is not None and body.if_version != kg.version:
        raise HTTPException(
            status_code=409,
            detail="数据已被其他页面或程序修改，请刷新后重试",
        )
    entity = kg.update_entity(
        entity_id=entity_id,
        name=body.name,
        type=body.type,
        properties=body.properties,
        color=body.color,
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
    try:
        relation = kg.add_relation(
            source=body.source,
            target=body.target,
            type=body.type,
            properties=body.properties,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not relation:
        raise HTTPException(status_code=400, detail="源实体或目标实体不存在")
    return relation.to_dict()


@app.put("/api/relations/{relation_id}")
def update_relation(relation_id: str, body: RelationUpdate) -> Dict[str, Any]:
    """更新关系（可修改源/目标实体、类型、属性；可携带 if_version 做并发冲突检测）"""
    if body.if_version is not None and body.if_version != kg.version:
        raise HTTPException(
            status_code=409,
            detail="数据已被其他页面或程序修改，请刷新后重试",
        )
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


@app.get("/api/graph/paths")
def find_paths(
    source: str, target: str, max_hops: int = 3, max_paths: int = 10
) -> Dict[str, Any]:
    """查询两个实体之间的关联路径（无向视角，按跳数从短到长）"""
    try:
        return kg.find_paths(source, target, max_hops=max_hops, max_paths=max_paths)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/graph/common")
def common_neighbors(entity: str, other: str) -> Dict[str, Any]:
    """查询两个实体的共同邻居"""
    try:
        return kg.common_neighbors(entity, other)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


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
# 知识抽取接口（P1 GraphRAG：文本 → 三元组 → 查重 → 写入）
# ------------------------------------------------------------------ #

class IngestRequest(BaseModel):
    """文本抽取入库的请求体"""

    text: str  # 待抽取文本（聊天记录片段/文档内容）
    dry_run: bool = False  # True 时只返回预览，不写入图谱（防噪人工闸）
    source: str = "text"  # 来源标记（写入实体属性溯源）
    as_session: bool = False  # True 时把 text 按会话 JSON（messages 数组）解析


# 上传抽取的文件大小上限（2MB，个人文本场景足够）
INGEST_FILE_MAX_BYTES = 2 * 1024 * 1024


@app.post("/api/ingest")
def ingest(body: IngestRequest) -> Dict[str, Any]:
    """
    从文本自动抽取实体与关系写入图谱（GraphRAG）。
    内置五道防噪闸：密度预检/价值预判/类型白名单/查重，闲聊文本零写入；
    dry_run=true 返回预览供人工确认后再正式写入。
    """
    text = body.text or ""
    # 会话 JSON 模式：把 messages 数组转成 "role: content" 逐行文本
    if body.as_session:
        try:
            text = session_to_text(json.loads(text))
        except (json.JSONDecodeError, IngestError) as e:
            raise HTTPException(status_code=400, detail=f"会话 JSON 解析失败: {e}")
    try:
        return ingest_text(kg, text, dry_run=body.dry_run, source=body.source)
    except IngestError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/api/ingest/file")
def ingest_file(
    file: UploadFile = File(...),
    dry_run: bool = Form(False),
    as_session: bool = Form(False),
) -> Dict[str, Any]:
    """
    上传 .txt/.md/.json 文件抽取入库。
    as_session=true 时按 jarvis 会话记录（messages 数组）解析；
    其余情况按纯文本处理。仅接受文本类文件，上限 2MB。
    """
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in (".txt", ".md", ".json"):
        raise HTTPException(status_code=400, detail="仅支持 .txt / .md / .json 文件")
    raw = file.file.read()
    if len(raw) > INGEST_FILE_MAX_BYTES:
        raise HTTPException(status_code=400, detail="文件超过 2MB 上限")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="文件不是 UTF-8 编码文本")

    if as_session or suffix == ".json":
        # JSON 文件优先按会话结构解析，解析失败再退回纯文本
        try:
            text = session_to_text(json.loads(text))
        except (json.JSONDecodeError, IngestError):
            pass
    try:
        return ingest_text(kg, text, dry_run=dry_run, source="file")
    except IngestError as e:
        raise HTTPException(status_code=502, detail=str(e))


# ------------------------------------------------------------------ #
# 文件上传接口
# ------------------------------------------------------------------ #

@app.post("/api/upload")
def upload_file(file: UploadFile = File(...)) -> Dict[str, str]:
    """上传图片并返回访问 URL，供实体属性引用"""
    # 简单校验 MIME 类型，只允许图片
    if file.content_type not in ("image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp", "image/svg+xml"):
        raise HTTPException(status_code=400, detail="仅支持图片文件")
    # 生成唯一文件名
    ext = Path(file.filename).suffix.lower() or ".png"
    filename = f"{uuid.uuid4().hex}{ext}"
    save_path = UPLOAD_DIR / filename
    with save_path.open("wb") as f:
        f.write(file.file.read())
    return {"url": f"/uploads/{filename}"}


# ------------------------------------------------------------------ #
# 启动入口
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8800)
