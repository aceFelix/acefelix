# AceFelix 个人知识图谱

[![CI](https://github.com/aceFelix/acefelix/actions/workflows/ci.yml/badge.svg)](https://github.com/aceFelix/acefelix/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Node](https://img.shields.io/badge/Node.js-20-339933?logo=nodedotjs&logoColor=white)](https://nodejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Vue](https://img.shields.io/badge/Vue.js-3-42b883?logo=vuedotjs&logoColor=white)](https://vuejs.org/)
[![MCP](https://img.shields.io/badge/MCP-Server-5c6bc0)](https://modelcontextprotocol.io/)

基于手动维护数据的个人知识图谱系统，支持实体和关系的增删改查、图结构查询，并提供宇宙银河主题的 3D 可视化展示。

## 功能特性

- **知识图谱核心**：NetworkX 图引擎 + JSON 持久化，支持实体/关系增删改查
- **3D 可视化**：基于 3d-force-graph（Three.js）的力导向 3D 图，节点为程序化生成的**真实行星**（气态云带/风暴斑或海陆/环形山，带大气辉光与缓慢自转），背景含星空、银河旋臂、星云、黑洞
- **动态类型**：实体类型与关系类型支持增删改查、改色、改名（级联更新）、中文标签，删除有保护
- **图查询**：邻居子图、两点间关联路径、共同邻居、搜索
- **交互模式**：单击高亮一跳关系、聚焦两跳深挖、路径查询、一键重置
- **实体管理**：列表展示、类型过滤、名称搜索、增删改查，属性支持**图片 URL 与本地上传**
- **数据保护**：乐观锁防并发覆盖，每次保存自动滚动备份（保留 20 份），原子写入防损坏
- **统计信息**：实体数、关系数、类型分布
- **Agent 接入**：MCP Server 将图谱以标准协议暴露给任意 AI Agent（jarvis、Claude Desktop 等），Agent 可查询画像、搜索实体、探索关联，经确认后新增实体/关系

## 项目结构

```
acefelix/
├── backend/                  # Python 后端
│   ├── api.py                # FastAPI REST 服务（含图片上传、静态资源）
│   ├── mcp_server.py         # MCP Server（Agent 接入，stdio）
│   ├── knowledge_graph.py    # 知识图谱核心引擎（CRUD + 查询 + 持久化）
│   ├── models.py             # 实体/关系数据模型
│   ├── seed.py               # 种子数据初始化脚本
│   ├── requirements.txt
│   ├── data/
│   │   ├── graph.json        # 图谱数据文件
│   │   └── backups/          # 滚动备份（保留 20 份）
│   └── uploads/              # 上传的图片文件
├── skills/
│   └── acefelix-knowledge/   # jarvis Skill（图谱使用指引，复制到 ~/.jarvis/skills/）
├── frontend/                 # Vue3 前端
│   ├── src/
│   │   ├── App.vue           # 主界面（三栏布局 + 右侧详情）
│   │   ├── api/index.js      # API 请求封装
│   │   ├── config/graph.config.js  # 3D 与宇宙主题参数
│   │   └── components/
│   │       ├── Graph3D.vue            # 3D 可视化（星球/星空/银河/黑洞/星云）
│   │       ├── EntityPanel.vue        # 实体管理面板（含图片属性）
│   │       ├── RelationPanel.vue      # 关系管理面板
│   │       ├── TypeManager.vue        # 实体类型管理
│   │       ├── RelationTypeManager.vue # 关系类型管理
│   │       └── StatsBar.vue           # 统计栏组件
│   └── package.json
├── docs/                     # 项目文档
│   ├── ARCHITECTURE.md       # 架构文档
│   ├── TECHNICAL.md          # 技术文档
│   ├── API.md                # REST API 参考
│   ├── DEPLOYMENT.md         # 部署与运维
│   └── fixlogs/              # 修复复盘文档
├── .github/workflows/ci.yml  # GitHub Actions CI（后端测试 + 前端构建）
└── start.bat                 # Windows 一键启动
```

## 快速开始

> 完整步骤见 [docs/DEPLOYMENT.md](./docs/DEPLOYMENT.md)。

### 环境要求

- Python 3.9+
- Node.js 16+
- npm 或 yarn

### 1. 启动后端

```bash
cd backend
python -m pip install -r requirements.txt
python seed.py          # 首次运行初始化种子数据（已有数据会跳过）
python api.py           # 启动 API 服务，监听 http://127.0.0.1:8800
```

> Windows 下若环境异常，请显式指定 `PYTHONPATH=<项目根目录>` 再 `python -m uvicorn api:app --reload --host 127.0.0.1 --port 8800`。

### 2. 启动前端

```bash
cd frontend
npm install
npm run dev             # 启动开发服务器 http://127.0.0.1:5173
```

浏览器打开 **http://127.0.0.1:5173/** 即可使用。

### 3. 启动 MCP Server（Agent 接入）

```bash
cd backend
python mcp_server.py          # 启动 MCP Server，通过 stdio 供 Agent 调用
```

> 无需单独启动，jarvis 等 Agent 客户端会在需要时自动拉起本进程。

### 4. 快速上手

- 左侧面板管理实体与关系，⚙ 按钮可管理类型
- 编辑实体时可在「图片属性」粘贴图片 URL 或上传本地图片
- 点击 3D 节点查看详情（属性中的图片自动渲染）；工具条提供「聚焦」「路径」「重置」
- 右上角搜索框可全文搜索实体

## API 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /api/meta | 类型/颜色/版本元数据 |
| GET | /api/types | 实体类型列表 |
| POST/PUT/DELETE | /api/types(/name) | 实体类型增改删 |
| GET | /api/relation-types | 关系类型列表 |
| POST/PUT/DELETE | /api/relation-types(/name) | 关系类型增改删 |
| GET/POST | /api/entities(/id) | 实体查询/新增 |
| PUT/DELETE | /api/entities/{id} | 实体更新/删除（级联删关系） |
| GET/POST | /api/relations(/id) | 关系查询/新增 |
| PUT/DELETE | /api/relations/{id} | 关系更新/删除 |
| GET | /api/graph | 完整图谱（3D 渲染用） |
| GET | /api/graph/neighbors/{id} | 邻居子图（degree 可选） |
| GET | /api/graph/paths | 两实体间关联路径 |
| GET | /api/graph/common | 两实体共同邻居 |
| GET | /api/search?q= | 搜索实体 |
| GET | /api/stats | 图谱统计 |
| POST | /api/upload | 上传图片 |

完整请求/响应示例见 [docs/API.md](./docs/API.md)，FastAPI 交互文档见 `http://127.0.0.1:8800/docs`。

## Agent 接入

图谱通过 **MCP Server**（[backend/mcp_server.py](./backend/mcp_server.py)）暴露给 AI Agent，
任何支持 MCP 协议的客户端（jarvis、Claude Desktop、Cursor 等）都能接入。

### jarvis 接入

1. 在 `~/.jarvis/mcp.json` 的 `mcpServers` 中添加：

```json
"acefelix-knowledge": {
  "command": "python",
  "args": ["<项目绝对路径>/backend/mcp_server.py"]
}
```

2. 安装 Skill（让 jarvis 知道何时/如何用图谱）：

```bash
cp -r skills/acefelix-knowledge ~/.jarvis/skills/
```

3. 重启 jarvis，即可通过 `mcp__acefelix-knowledge__*` 工具查询/维护图谱。

### 其他 Agent

在客户端 MCP 配置中注册同一启动命令即可，工具清单：

| 工具 | 类型 | 说明 |
|---|---|---|
| `get_profile` | 只读 | 人物画像摘要（了解用户优先调用） |
| `search_entity` / `get_entity` / `list_entities` | 只读 | 实体搜索与详情 |
| `get_neighbors` / `find_paths` / `common_neighbors` | 只读 | 图结构查询 |
| `get_stats` / `list_types` / `list_relation_types` | 只读 | 统计与类型表 |
| `add_entity` / `add_relation` | 写入 | 新增实体/关系（客户端默认需用户确认） |

> 数据文件 `backend/data/graph.json` 为本地个人数据，不入库；clone 后运行 `python seed.py` 生成初始图谱。

## 未来规划

> 完整升级计划书（技术选型与实现思路）见 [docs/plans/upgrade-plan.md](./docs/plans/upgrade-plan.md)

- [x] 与 JARVIS 联动，让 JARVIS 更懂用户（MCP Server 接入已完成）
- [ ] P1 GraphRAG 自动抽取：从聊天记录/文档中自动抽取实体关系
- [ ] P2 画像双向同步：会话提炼结果回写图谱，图谱画像注入系统提示
- [ ] P3 语义检索：embedding 语义搜索替代关键词匹配
- [ ] P4 关联推荐：相似实体与潜在兴趣推荐
- [ ] P5 数据量增大后迁移 SQLite / Kùzu / Neo4j

## License

[MIT](./LICENSE) © 2026 aceFelix
