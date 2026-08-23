---
name: acefelix-knowledge
description: aceFelix 个人知识图谱查询与维护专家。掌握他的身份、技能、知识、项目、工具、兴趣、目标等结构化信息，并能按需扩展图谱。
when_to_use: 当用户询问关于 aceFelix 本人（技能、项目、知识、工具、兴趣、目标、任务），或要求把新的知识/经历记录进个人图谱时
trigger_words: acefelix, 知识图谱, 我的技能, 我的项目, 我了解什么, 记录到图谱, 图谱
---

# aceFelix 个人知识图谱

aceFelix 的个人知识图谱（通过 MCP server `acefelix-knowledge` 接入）存储了他的
**身份背景、技能、知识领域、项目、工具、兴趣、任务、目标** 及其相互关系，
是"最了解 aceFelix"的结构化数据源。所有工具前缀为 `mcp__acefelix-knowledge__`。

## 数据模型

- **实体（节点）**：Person / Skill / Knowledge / Interest / Project / Task / Tool / Goal 等类型
- **关系（边）**：HAS_SKILL（掌握技能）、KNOWS（了解知识）、WORKS_ON（参与项目）、
  USES（使用工具）、DOING（正在做）、RELATED_TO（相关）、DEPENDS_ON（依赖于）、
  LEADS_TO（通向）等类型
- 每个实体可带属性（properties），如 `{"proficiency": "高级", "years": 5}`

## 可用工具

### 查询类（优先使用）

| 工具 | 用途 |
|---|---|
| `get_profile` | **最常用**：获取 aceFelix 画像摘要（本人 + 一跳关联），了解用户先调它 |
| `search_entity(query)` | 按关键词搜索实体（名称/属性） |
| `get_entity(id)` | 查单个实体详情 |
| `list_entities(type?)` | 列实体，可按类型过滤 |
| `get_neighbors(id, degree)` | 某实体邻居子图（1/2 度） |
| `find_paths(source, target)` | 两实体间关联路径 |
| `common_neighbors(a, b)` | 两实体共同点 |
| `get_stats` / `list_types` / `list_relation_types` | 统计与类型表 |

### 写入类（新增图谱知识，需用户确认）

| 工具 | 用途 |
|---|---|
| `add_entity(name, type, properties?)` | 新增实体（先 `list_types` 确认类型） |
| `add_relation(source, target, type)` | 新增关系（先 `list_relation_types`） |

## 使用规范

1. **先画像后深挖**：涉及"用户是谁/会什么/在做什么"的问题，先 `get_profile`，
   再按需 `get_entity` / `get_neighbors` 深入。
2. **回答用图谱事实**：当图谱信息与聊天记忆冲突时，以图谱为准并说明来源。
3. **新信息回写图谱**：用户主动告知新的技能/项目/经历（如"我最近在学 X"、
   "我开始做 Y 项目"）时，用 `add_entity` + `add_relation` 记录，保持图谱新鲜。
4. **先查后写**：写入前先 `search_entity` 确认实体不存在，避免重复；类型不存在时
   先提示用户（类型管理目前走 Web 端）。
5. **紧凑输出**：图谱数据可能较大，返回给用户时提炼要点，不要整段倾倒 JSON。
