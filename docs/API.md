# AceFelix 知识图谱 · API 文档

> Base URL：`http://127.0.0.1:8800`
> 全部接口返回 JSON；FastAPI 自动生成交互式文档：`http://127.0.0.1:8800/docs`

## 1. 约定

### 1.1 通用错误格式

```json
{ "detail": "错误描述" }
```

### 1.2 错误码

| HTTP | 含义 | 典型场景 |
|---|---|---|
| 400 | 参数/业务校验失败 | 类型已存在、类型在使用中、格式错误 |
| 404 | 资源不存在 | 实体/关系 ID 无效 |
| 409 | 乐观锁冲突 | 提交的 `if_version` 不等于当前 `version` |
| 422 | 请求体校验失败 | 缺字段、字段类型错误 |

---

## 2. 元数据

### GET /api/meta

获取实体类型、关系类型、颜色映射与数据版本号。

**响应**

```json
{
  "entity_types": ["Person", "Skill"],
  "relation_types": ["HAS_SKILL", "KNOWS"],
  "relation_type_labels": { "HAS_SKILL": "掌握技能" },
  "entity_colors": { "Person": "#ff6b6b" },
  "version": 17
}
```

---

## 3. 实体类型管理

### GET /api/types

列出全部实体类型（名称 → 颜色）。

```json
{ "Person": "#ff6b6b", "Skill": "#4ecdc4" }
```

### POST /api/types

新增类型。

**请求**

```json
{ "name": "Language", "color": "#54a0ff" }
```

**失败**：400 `{"detail": "类型已存在: Language"}`

### PUT /api/types/{name}

改色 / 改名（可同时）。

**请求**

```json
{ "color": "#eb4d4b" }
```

```json
{ "new_name": "Language" }
```

> 改名会**级联更新**所有使用该类型的实体。`name` 需 URL 编码。

### DELETE /api/types/{name}

删除类型。

**失败**：400 `{"detail": "类型正在被 3 个实体使用，无法删除"}`（有实体在使用时拒绝）

---

## 4. 关系类型管理

### GET /api/relation-types

```json
{ "HAS_SKILL": "掌握技能" }
```

### POST /api/relation-types

**请求**

```json
{ "name": "OWNS", "label": "拥有" }
```

### PUT /api/relation-types/{name}

改标签 / 改名。

**请求**

```json
{ "label": "掌握" }
```

### DELETE /api/relation-types/{name}

有关系的类型在使用时拒绝（400）。

---

## 5. 实体接口

### GET /api/entities

列出全部实体，`?type=` 可选过滤。

### GET /api/entities/{id}

获取单个实体。

### POST /api/entities

创建实体。

**请求**

```json
{
  "name": "Python",
  "type": "Skill",
  "properties": { "level": "advanced" },
  "color": "#4ecdc4"
}
```

- `properties` / `color` 可选
- `color` 留空 = 使用类型默认色

### PUT /api/entities/{id}

更新实体。

**请求**

```json
{
  "name": "Python 3",
  "type": "Skill",
  "properties": { "level": "advanced", "logo": "http://127.0.0.1:8800/uploads/xx.png" },
  "color": "",
  "if_version": 16
}
```

- 所有字段可选；`color: ""` 清除自定义色
- `properties` 为**整体替换**（非合并）
- `if_version` 可选，不匹配返回 **409**

**409 示例**

```json
{ "detail": "数据已被其他页面或程序修改，请刷新后重试" }
```

### DELETE /api/entities/{id}

删除实体，**级联删除**所有关联关系。

---

## 6. 关系接口

### GET /api/relations

列出全部关系，`?type=` 可选过滤。

### GET /api/relations/{id}

获取单个关系。

### POST /api/relations

**请求**

```json
{
  "source": "1e2b0a7e-...",
  "target": "3f5c...",
  "type": "HAS_SKILL",
  "properties": {}
}
```

**失败**：400 `{"detail": "源实体或目标实体不存在"}` 或 `{"detail": "未注册的关系类型: XXX"}`

### PUT /api/relations/{id}

**请求**

```json
{
  "source": "新源id",
  "target": "新目标id",
  "type": "USES",
  "properties": {},
  "if_version": 16
}
```

> 端点变化时后端会重建图边。

### DELETE /api/relations/{id}

删除关系。

---

## 7. 图谱查询

### GET /api/graph

返回完整图谱（3D 渲染用）：

```json
{
  "entities": [ { "id": "...", "name": "...", "type": "...", "color": "...", "size": null } ],
  "relations": [ { "id": "...", "source": "...", "target": "...", "type": "..." } ]
}
```

### GET /api/graph/neighbors/{id}?degree=1

邻居子图。`degree` 默认 1（直接邻居），2 = 二度邻居。

```json
{
  "entities": [],
  "relations": []
}
```

### GET /api/graph/paths?source={id}&target={id}&max_hops=3&max_paths=10

查询两实体间关联路径（无向视角，按跳数从短到长）。

**响应**

```json
{
  "source": "A-id",
  "target": "B-id",
  "paths": [
    {
      "nodes": ["A-id", "C-id", "B-id"],
      "relations": ["r1", "r2"],
      "length": 2,
      "node_names": ["A", "C", "B"],
      "relation_types": ["USES", "PART_OF"]
    }
  ]
}
```

- `max_hops` 范围 1~4（超出会被钳制）
- **失败**：400 `{"detail": "起点或终点实体不存在"}` / `{"detail": "起点和终点不能相同"}`

### GET /api/graph/common?entity={id}&other={id}

共同邻居。

**响应**

```json
{
  "a": { "...": "实体A" },
  "b": { "...": "实体B" },
  "common": [ { "...": "实体C" } ],
  "common_count": 1
}
```

### GET /api/search?q={关键词}

搜索实体（名称 + 属性值模糊匹配）。

```json
[ { "id": "...", "name": "Python", "type": "Skill" } ]
```

### GET /api/stats

```json
{
  "total_entities": 26,
  "total_relations": 41,
  "entity_types": { "Person": 3 },
  "relation_types": { "HAS_SKILL": 5 }
}
```

---

## 8. 文件上传

### POST /api/upload

上传图片（multipart/form-data，字段名 `file`）。

```bash
curl -X POST http://127.0.0.1:8800/api/upload \
  -F "file=@./logo.png"
```

**响应**

```json
{ "url": "/uploads/3f2a9c1e8b7d4f5e9a1b2c3d4e5f6a7b.png" }
```

访问图片：`http://127.0.0.1:8800/uploads/{filename}`

**失败**：400 `{"detail": "仅支持图片文件"}`（MIME 非图片类型）

---

## 9. 静态资源

| 路径 | 说明 |
|---|---|
| `/uploads/{filename}` | 上传的图片文件 |
| `/docs` | FastAPI Swagger UI |
| `/redoc` | ReDoc 文档 |
