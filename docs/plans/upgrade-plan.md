# AceFelix 知识图谱升级计划书

> 版本：v1.0 ｜ 日期：2026-08-23
> 定位：个人知识图谱从"手动维护的工具"升级为"越用越懂你的活系统"的实施路线图
> 现状基准：MCP Server + Skill 接入已完成，CRUD/图查询/3D 可视化/数据保护均已就绪

---

## 1. 背景与目标

当前 acefelix 已具备完整的图谱管理、查询与 Agent 接入能力，但数据**全部依赖手动维护**，
查询停留在**关键词匹配**，尚未形成"自动构建 → 语义检索 → 关联推荐 → 与 Agent 记忆联动"的闭环。

本次升级按五个版块分步实施，目标：

1. **让图谱自动生长**：从聊天记录/文档自动抽取实体关系（GraphRAG）
2. **让 Agent 越用越懂你**：图谱画像与 jarvis 记忆双向同步
3. **让检索理解语义**：embedding 语义搜索替代子串匹配
4. **让图谱会推荐**：基于图结构的关联分析
5. **让存储扛得住增长**：数据量增大后平滑迁移

## 2. 总览：优先级与依赖

| 版块 | 优先级 | 依赖 | 价值 |
|---|---|---|---|
| P1 GraphRAG 自动抽取 | ★★★ 先做 | 现有引擎 + LLM | 图谱从"手动维护"变"自动生长" |
| P2 画像双向同步 | ★★★ | P1（部分）+ 现有 MCP | 与 jarvis 形成记忆闭环 |
| P3 语义检索 | ★★ | 独立 | 实体多了之后检索质量的关键 |
| P4 关联推荐 | ★★ | 现有图算法（可独立） | 探索式发现 |
| P5 存储迁移 | ★ | P1-P4 稳定后 | 数据量上限扩展 |

```
依赖链: P1 ──▶ P2
        │
        ├──▶ P3（独立）
        ├──▶ P4（可独立）
        └──▶ P5（最后，承接所有数据）
```

---

## 3. P1 · GraphRAG 自动抽取

### 3.1 目标
从 jarvis 会话记录 / 用户指定的文本文件中自动抽取「实体 + 关系」三元组，
经查重与类型推断后写入图谱，让图谱随对话与文档自动生长。

### 3.2 技术选型

| 方案 | 说明 | 结论 |
|---|---|---|
| **LLM 抽取 + 现有引擎写入** | 用 LLM 抽三元组（JSON），查重后调 `add_entity`/`add_relation` | ✅ 采用：零新依赖，复用现有图引擎与乐观锁 |
| LangChain/LlamaIndex GraphRAG | 框架重、抽象多 | ❌ 个人项目过度设计 |
| Neo4j 原生 GraphRAG | 需先迁移存储（P5） | ⏸ 与 P5 绑定 |

### 3.3 实现思路

```
输入（会话 JSON / 文本文件）
  → 文本截取（限额，参考 profile_refiner 的做法）
  → LLM 抽取: {"entities": [{name, type, properties}], "relations": [{source, target, type}]}
  → 实体查重（名称归一化 + 相似度，避免重复建节点）
  → 类型推断（映射到已有类型表，缺类型时列入"待确认"）
  → 写入 KnowledgeGraph（复用乐观锁 + 备份，可回滚）
```

- **抽取模型**：独立便宜模型配置（`[ingest]` 段，参考 jarvis `[memory.refine]` 模式），留空用主 LLM
- **写权限**：个人项目默认直接写入（保留备份可回滚）；提供 `dry_run` 参数返回预览 JSON 供确认
- **查重策略**：名称精确/归一化匹配为主，必要时加 embedding 相似度（P3 落地后增强）

### 3.4 新增/改动

| 文件 | 说明 |
|---|---|
| `backend/ingest.py`（新） | 抽取管线：文本 → 三元组 → 查重 → 写入 |
| `backend/api.py` | 新增 `POST /api/ingest`（text/file/session） |
| `backend/mcp_server.py` | 可选：`ingest_text` 工具（Agent 触发抽取） |
| `backend/seed.py` | 生成少量"抽取示例"演示数据（可选） |

### 3.5 验收
- 输入一段含人物/技能/项目关系的文本，可自动生成正确三元组并入库
- 重复输入同一文本不产生重复实体
- 抽取失败不影响图谱现有数据（备份可回滚）

---

## 4. P2 · 画像双向同步

### 4.1 目标
- **图谱 → jarvis**：jarvis 启动时将图谱画像注入 system prompt，让 Agent 直接掌握结构化用户信息
- **jarvis → 图谱**：会话提炼出的新画像条目自动转换为图谱实体/关系

### 4.2 技术选型

| 方向 | 方案 | 结论 |
|---|---|---|
| 图谱 → jarvis | jarvis 启动时调用 MCP `get_profile`，合并进 `build_system_prompt` | ✅ 走已就绪的 MCP 协议 |
| jarvis → 图谱 | jarvis `profile_refiner` 提炼后，经 MCP `add_entity`/`add_relation` 回写（用户确认） | ✅ 复用 MCP 写工具 |
| 数据一致性 | 图谱为**唯一事实源**，jarvis profile.json 作为可再生的缓存视图 | ✅ 避免双写冲突 |

### 4.3 实现思路

```
[图谱] ──MCP get_profile──▶ jarvis build_system_prompt（画像段合并）
    ▲                            │
    │                            ▼ 会话结束提炼
    └────MCP add_entity/add_relation（用户确认）── profile_refiner 产物
```

- **jarvis 侧**：新增 `agent/core/extensions/profile_bridge.py`：
  - `load_kg_profile()`：调 MCP `get_profile` 渲染成画像段（token 限额）
  - `sync_to_kg(entry)`：把提炼的 ProfileEntry 映射为实体/关系，调 MCP 写工具
- **冲突处理**：图谱条目优先；jarvis 画像与图谱冲突时以图谱为准（图谱是人工/半自动维护的主数据）
- **开关**：`[profile_bridge] enabled`，避免每轮会话都调 MCP

### 4.4 验收
- jarvis 启动后能说出图谱中结构化信息（技能/项目），无需重新聊天
- jarvis 提炼的新画像可在用户确认后出现在图谱中

---

## 5. P3 · 语义检索

### 5.1 目标
`search()` 从子串匹配升级为 embedding 语义检索，支持"用意思找知识"。

### 5.2 技术选型

| 方案 | 说明 | 结论 |
|---|---|---|
| **DashScope text-embedding API** | 用户已有 DashScope key，精度高、成本极低 | ✅ 首选（联网可用） |
| 本地 embedding（Ollama/sentence-transformers） | 离线、隐私好 | ⭕ 备选（无网环境） |
| SQLite FTS5 | 纯关键词全文索引 | ❌ 仍是词面匹配，不达"语义"目标 |

### 5.3 实现思路

- `backend/embedding.py`：实体向量化（名称 + 类型 + 属性摘要拼接后 embed）
- **存储**：数据量小（万级实体 × 1 个向量），`graph.json` 增 `embedding` 字段即可；
  无需引入向量数据库
- **查询**：query embed → 余弦相似度 top-k（暴力计算，个人量级性能足够）
- **降级**：embedding 服务不可用时回退关键词搜索（保持兼容）

### 5.4 验收
- 搜"写代码用的工具"能召回 VS Code/Git（而非仅字面命中）
- embedding 失败时仍可关键词搜索，不报错

---

## 6. P4 · 关联推荐

### 6.1 目标
基于图结构提供探索式发现：相似实体、可能感兴趣的知识/项目。

### 6.2 技术选型
NetworkX 自带算法即可覆盖个人量级：

| 算法 | 用途 |
|---|---|
| 共同邻居 / Jaccard 相似度 | 相似实体（同技能、同项目） |
| Resource Allocation 指标 | 更敏感的相似度排序 |
| 邻居的邻居（弱连接） | 潜在兴趣推荐（"你了解 A，可能也喜欢与 A 相关的 B"） |

### 6.3 实现思路

- `knowledge_graph.py` 新增：
  - `recommend_similar(entity_id, top_k)` → 相似实体列表
  - `recommend_explore(person_id, top_k)` → 潜在兴趣（一跳邻居的未连接邻居）
- 暴露：REST `GET /api/recommend` + MCP `recommend` 工具
- 前端：3D 图"推荐模式"高亮推荐节点（可选）

### 6.4 验收
- 对"Python"能推荐出同属工具链的相似实体
- 对本人能推荐出尚未关联但相关度高的知识/项目

---

## 7. P5 · 存储迁移

### 7.1 目标
数据量（万级节点以上）或路径查询变慢时，从 JSON 平滑迁移到更强存储。

### 7.2 技术选型

| 方案 | 说明 | 结论 |
|---|---|---|
| SQLite | 无服务、事务完备，替代 JSON 作为文件存储 | ✅ 第一阶段（数据量大但图查询仍可用内存算法） |
| Kùzu | 嵌入式列式图数据库，支持 Cypher，pip 可装 | ⏸ 第二阶段（路径/子图查询成为瓶颈时） |
| Neo4j | 最成熟但需独立服务，个人场景重 | ❌ 暂不考虑 |

### 7.3 实现思路

- **接口不变原则**：`KnowledgeGraph` 是唯一数据访问入口，先抽象出 `Storage` 层
  （`JsonStorage` / `SqliteStorage` / `KuzuStorage`），引擎内部替换实现，REST/MCP 层零改动
- **迁移脚本**：`backend/migrate.py`（graph.json → SQLite/Kùzu，含类型表与关系迁移）
- **内存图保留**：NetworkX 继续承载查询算法，存储层只负责持久化——查询性能不受存储切换影响

### 7.4 验收
- 迁移后全部现有测试通过，前端/MCP 功能不变
- 10 万节点规模下路径查询响应可接受

---

## 8. 里程碑与交付顺序

| 阶段 | 内容 | 交付物 |
|---|---|---|
| M1 | P1 GraphRAG 自动抽取 | `ingest.py` + API + 测试 + 文档 |
| M2 | P2 画像双向同步 | jarvis `profile_bridge` + 图谱写入链路 |
| M3 | P3 语义检索 | `embedding.py` + 搜索升级 + 降级 |
| M4 | P4 关联推荐 | 推荐算法 + API/MCP 暴露 |
| M5 | P5 存储迁移 | Storage 抽象 + 迁移脚本 |

每阶段独立交付：代码 + 单元测试 + 文档更新（README/docs 同步）+ 修复复盘（如涉及）。

## 9. 风险与对策

| 风险 | 对策 |
|---|---|
| LLM 抽取质量不稳定（错抽/漏抽） | 类型白名单 + dry_run 预览 + 备份回滚 |
| embedding 服务不可用 | 关键词搜索降级，不阻塞 |
| 与 jarvis 双写冲突 | 图谱为唯一事实源，画像只读缓存 |
| 迁移后查询回归 | 存储抽象保持接口不变，存量测试全量回归 |
