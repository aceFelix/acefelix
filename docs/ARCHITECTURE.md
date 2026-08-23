# AceFelix 知识图谱 · 架构文档

> 版本：0.1.0 ｜ 更新日期：2026-08-22

## 1. 系统概述

AceFelix 是一个**个人知识图谱系统**，帮助个人以图结构组织「人物 / 技能 / 项目 / 知识」等信息，并提供 3D 可视化浏览、实体/关系管理、图结构查询能力。

系统采用**前后端分离**架构：

- **后端**：Python + FastAPI + NetworkX，面向图的领域模型，JSON 文件持久化
- **前端**：Vue 3 + Vite + 3d-force-graph（Three.js），SPA 单页应用
- **Agent 接入**：MCP Server（`mcp_server.py`）以标准协议向 jarvis 等 AI Agent 暴露图谱查询/维护能力

数据层当前使用 **JSON 文件 + 乐观锁 + 滚动备份**，满足单用户个人场景；数据量增大后可平滑迁移到 SQLite / Kùzu / Neo4j（见 [TECHNICAL.md](./TECHNICAL.md#8-演进路线)）。

```
┌─────────────────────────────────────────────────────────┐
│                      浏览器 (SPA)                        │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Vue 3 应用                                        │  │
│  │  ├── App.vue            布局 / 状态 / 路由          │  │
│  │  ├── EntityPanel.vue    实体管理面板（CRUD）        │  │
│  │  ├── RelationPanel.vue  关系管理面板（CRUD）        │  │
│  │  ├── Graph3D.vue        3D 图 + 宇宙主题渲染        │  │
│  │  ├── TypeManager.vue    实体类型管理                │  │
│  │  ├── RelationTypeManager.vue  关系类型管理          │  │
│  │  └── StatsBar.vue       统计信息栏                  │  │
│  └───────────────────────────┬───────────────────────┘  │
│              HTTP (REST JSON, port 8800)                │
└──────────────────────────────┬──────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────┐
│                    FastAPI 后端                          │
│  ┌───────────────────────────────────────────────────┐  │
│  │ api.py            路由层（REST + 上传 + 静态资源）   │  │
│  │ knowledge_graph.py 核心引擎（图模型 / CRUD / 查询） │  │
│  │ models.py          数据模型（Entity / Relation）    │  │
│  │ seed.py            种子数据初始化                   │  │
│  └──────────────────────────┬────────────────────────┘  │
│              ┌──────────────┼──────────────┐            │
│              ▼              ▼              ▼            │
│       graph.json       backups/        uploads/         │
│       (主数据)      (滚动备份×20)    (图片文件)          │
└─────────────────────────────────────────────────────────┘
         │  共享 KnowledgeGraph 引擎（同一 data 文件）
         ▼
┌─────────────────────────────────────────────────────────┐
│              MCP Server (mcp_server.py)                  │
│  stdio transport · 只读工具 + 写工具(需确认)             │
└─────────────────────────────────────────────────────────┘
         ▲
         │ MCP 协议 (stdio JSON-RPC)
┌────────┴─────────────────────────────────────────────────┐
│            AI Agent（jarvis / Claude Desktop / ...）      │
│  通过 mcp__acefelix-knowledge__* 工具查询/维护图谱        │
└──────────────────────────────────────────────────────────┘
```

## 2. 技术栈

| 层次 | 技术 | 版本 | 说明 |
|---|---|---|---|
| 后端框架 | FastAPI | >= 0.110 | REST API，自动生成 OpenAPI 文档 |
| 后端服务器 | Uvicorn | >= 0.29 | ASGI 服务器 |
| 图引擎 | NetworkX | >= 3.2 | 内存图模型，提供遍历/路径算法 |
| 数据校验 | Pydantic | >= 2.0 | 请求/响应模型 |
| 文件上传 | python-multipart | >= 0.0.12 | `UploadFile` 依赖 |
| Agent 接入 | mcp | >= 1.0 | MCP SDK（FastMCP，stdio transport） |
| 前端框架 | Vue 3 | ^3.4 | 组合式 API |
| 构建工具 | Vite | ^5.4 | 开发服务器 + 生产构建 |
| 3D 渲染 | 3d-force-graph | ^1.73 | 力导向 3D 图（基于 Three.js） |
| 3D 底层 | three | ^0.185 | WebGL 渲染引擎 |

## 3. 模块职责

### 3.1 后端

| 模块 | 职责 | 关键点 |
|---|---|---|
| `models.py` | 数据模型 | `Entity` / `Relation` dataclass，`EntityType` / `RelationType` 枚举，默认颜色/标签映射 |
| `knowledge_graph.py` | 核心引擎 | 封装 `nx.DiGraph`；实体/关系 CRUD；动态类型表；图查询；JSON 持久化 + 乐观锁 + 备份 |
| `api.py` | 路由层 | REST 端点；类型管理；图查询接口；`/api/upload` 图片上传；`/uploads` 静态资源挂载 |
| `mcp_server.py` | Agent 接入 | FastMCP stdio server；画像/搜索/图查询只读工具 + 新增实体/关系写工具（客户端侧默认需确认） |
| `seed.py` | 数据初始化 | 首次运行时填充示例数据（已有数据跳过） |
| `requirements.txt` | 依赖清单 | Python 运行依赖 |

### 3.2 前端

| 模块 | 职责 | 关键点 |
|---|---|---|
| `App.vue` | 应用壳 | 三栏布局（左面板 / 中央 3D / 右侧详情）；状态协调；搜索 |
| `Graph3D.vue` | 3D 可视化 | 力导向图；星球节点；星空/银河/黑洞/星云背景；聚焦/路径/重置交互 |
| `EntityPanel.vue` | 实体管理 | 列表/过滤/搜索；新增编辑弹窗（含图片属性）；选中/悬停名称着色 |
| `RelationPanel.vue` | 关系管理 | 关系列表 CRUD，中文标签显示 |
| `TypeManager.vue` | 实体类型管理 | 增删改查，改色/改名级联，删除保护 |
| `RelationTypeManager.vue` | 关系类型管理 | 增删改查，中文标签，删除保护 |
| `StatsBar.vue` | 统计栏 | 实体数 / 关系数 / 类型分布 |
| `api/index.js` | API 封装 | REST 调用 + `FormData` 文件上传 |
| `config/graph.config.js` | 3D/主题配置 | 节点半径、斥力、相机、宇宙天体参数集中可调 |
| `style.css` | 全局样式 | 银河深空配色、毛玻璃面板 |

## 4. 数据流

### 4.1 读取链路（初始化）

```
App.vue init()
  ├─ api.getMeta()          → /api/meta   → 类型表 / 颜色映射 / 版本号
  ├─ api.getEntities()      → /api/entities
  ├─ graphRef.loadGraph()   → /api/graph  → Graph3D 力导向渲染
  └─ statsRef.loadStats()   → /api/stats
```

### 4.2 写入链路（编辑实体）

```
EntityPanel.submitForm()
  → PUT /api/entities/{id} { if_version: graphVersion }
      ├─ api.py 校验 if_version == kg.version，否则 409
      ├─ knowledge_graph.update_entity()  修改内存模型
      ├─ knowledge_graph.save()           备份 → 写临时文件 → 原子替换
      └─ 前端 emit('refresh')  → 重新拉取全量数据刷新
```

### 4.3 图交互链路（3D 图）

```
点击节点
  ├─ 默认：高亮一跳邻域，打开右侧详情面板
  ├─ 聚焦模式：高亮两跳邻域
  ├─ 路径模式：选起点 → 选终点 → GET /api/graph/paths → 高亮路径 + 面板展示
  └─ 重置：清除全部高亮
```

### 4.4 MCP 查询链路（Agent 接入）

```
AI Agent 决定查询图谱
  → jarvis 拉起 mcp_server.py 子进程（stdio JSON-RPC）
  → session.call_tool("get_profile") 等
  → mcp_server.py 调用共享 KnowledgeGraph 引擎（同一 data/graph.json）
  → 结果 JSON 返回给 Agent，Agent 提炼后回答用户
```

## 5. 关键设计决策

| 决策 | 方案 | 理由 |
|---|---|---|
| 存储选型 | JSON 文件 | 单用户、数据量小；零运维；人类可读 |
| 并发控制 | 乐观锁（version 字段） | 避免多标签页/多端覆盖写；FastAPI sync handler 线程池下用写锁串行化 |
| 写入安全 | 写临时文件 + `os.replace` 原子替换 | 中断不损坏既有数据；环境拦截 rename 时降级直接写 |
| 数据保护 | 每次保存前滚动备份 20 份 | 误操作可回溯 |
| 类型体系 | 动态类型表（存入 graph.json） | 用户可自定义实体/关系类型与中文标签，不再写死 |
| 图片存储 | `uploads/` 独立目录 + URL 引用 | 避免 base64 塞进 JSON 撑爆数据文件 |
| 3D 主题 | 程序化生成（Canvas 纹理 + Three.js 图元） | 无需美术资源，参数化可调 |

## 6. 目录结构

```
acefelix/
├── backend/
│   ├── api.py                  # FastAPI 路由 + 上传 + 静态挂载
│   ├── mcp_server.py           # MCP Server（Agent 接入）
│   ├── knowledge_graph.py      # 图核心引擎
│   ├── models.py               # 数据模型
│   ├── seed.py                 # 种子数据
│   ├── requirements.txt
│   ├── data/
│   │   ├── graph.json          # 主数据文件（本地数据，不入库）
│   │   └── backups/            # 滚动备份（保留 20 份）
│   └── uploads/                # 上传的图片文件
├── skills/
│   └── acefelix-knowledge/     # jarvis Skill（图谱使用指引）
├── frontend/
│   ├── src/
│   │   ├── App.vue
│   │   ├── main.js
│   │   ├── style.css
│   │   ├── api/index.js
│   │   ├── config/graph.config.js
│   │   └── components/
│   │       ├── Graph3D.vue
│   │       ├── EntityPanel.vue
│   │       ├── RelationPanel.vue
│   │       ├── TypeManager.vue
│   │       ├── RelationTypeManager.vue
│   │       └── StatsBar.vue
│   ├── package.json
│   └── vite.config.js
├── docs/
│   ├── ARCHITECTURE.md         # 本文档
│   ├── TECHNICAL.md            # 技术实现细节
│   ├── API.md                  # REST API 参考
│   ├── DEPLOYMENT.md           # 部署与运维
│   └── fixlogs/                # 历史问题复盘
├── start.bat                   # Windows 一键启动
└── README.md
```

## 7. 扩展点

1. **数据层替换**：`KnowledgeGraph` 是唯一数据访问入口，替换其实现（SQLite/Kùzu）即可，API 层与 MCP 层均无需改动。
2. **3D 配置**：`graph.config.js` 集中了节点、力导向、宇宙天体的全部参数，调参不碰代码。
3. **新增查询**：在 `knowledge_graph.py` 增加查询方法 + `api.py` 暴露端点 + 前端调用；如需 Agent 可用，同步在 `mcp_server.py` 注册 MCP 工具。
4. **GraphRAG 自动抽取**：可新增抽取服务，写实体/关系时复用现有乐观锁与备份机制。
5. **Agent 画像同步**：MCP 的 `get_profile` 为单向读取；后续可做会话提炼结果回写图谱、图谱画像注入 Agent 系统提示。
