# AceFelix 个人知识图谱

基于手动维护数据的个人知识图谱系统，支持实体和关系的增删改查，并提供 3D 可视化展示。

## 功能特性

- **知识图谱核心**：NetworkX 图引擎 + JSON 持久化，支持实体/关系增删改查
- **3D 可视化**：基于 3d-force-graph（Three.js）的力导向 3D 图，节点按类型着色，支持拖拽旋转、缩放、点击查看详情
- **实体管理**：左侧面板支持实体的列表展示、按类型过滤、名称搜索、新增/编辑/删除
- **关系管理**：左侧面板支持关系的列表展示、按类型过滤、新增/编辑/删除
- **统计信息**：底部统计栏展示实体数、关系数、类型分布

## 实体类型

| 类型 | 说明 | 颜色 |
|---|---|---|
| Person | 人物 | 红 |
| Skill | 技能 | 青 |
| Knowledge | 知识领域 | 蓝 |
| Interest | 兴趣爱好 | 黄 |
| Project | 项目 | 紫 |
| Task | 任务 | 粉 |
| Tool | 工具 | 深紫 |
| Education | 教育背景 | 绿 |
| Goal | 目标 | 橙 |
| Event | 事件 | 浅黄 |

## 关系类型

HAS_SKILL（掌握技能）、KNOWS（了解知识）、INTERESTED_IN（感兴趣）、WORKS_ON（参与项目）、DOING（正在做）、USES（使用工具）、STUDIED_AT（就读于）、RELATED_TO（相关）、DEPENDS_ON（依赖于）、PART_OF（属于）、LEADS_TO（通向）、SIMILAR_TO（相似）

## 项目结构

```
acefelix/
├── backend/                  # Python 后端
│   ├── models.py             # 实体/关系数据模型定义
│   ├── knowledge_graph.py    # 知识图谱核心引擎（CRUD + JSON 持久化）
│   ├── api.py                # FastAPI REST 服务
│   ├── seed.py               # 种子数据初始化脚本
│   ├── requirements.txt      # Python 依赖
│   └── data/graph.json       # 图谱数据文件
├── frontend/                 # Vue3 前端
│   ├── src/
│   │   ├── App.vue           # 主界面
│   │   ├── api/index.js      # API 请求封装
│   │   └── components/
│   │       ├── Graph3D.vue       # 3D 可视化组件
│   │       ├── EntityPanel.vue   # 实体管理面板
│   │       ├── RelationPanel.vue # 关系管理面板
│   │       └── StatsBar.vue      # 统计栏组件
│   ├── package.json
│   └── vite.config.js
└── docs/
    └── fixlogs/              # 修复复盘文档
```

## 快速开始

### 环境要求

- Python 3.9+
- Node.js 16+
- npm 或 yarn

### 1. 启动后端

```powershell
cd acefelix/backend
python -m pip install -r requirements.txt
python seed.py          # 首次运行初始化种子数据（已有数据会跳过）
python api.py           # 启动 API 服务，监听 http://127.0.0.1:8800
```

### 2. 启动前端

```powershell
cd acefelix/frontend
npm install
npm run dev             # 启动开发服务器 http://localhost:5173
```

浏览器打开 http://localhost:5173 即可使用。

## API 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /api/meta | 获取实体/关系类型元数据 |
| GET | /api/entities | 列出实体（可按 type 过滤） |
| POST | /api/entities | 创建实体 |
| GET | /api/entities/{id} | 获取实体 |
| PUT | /api/entities/{id} | 更新实体 |
| DELETE | /api/entities/{id} | 删除实体（级联删除关系） |
| GET | /api/relations | 列出关系 |
| POST | /api/relations | 创建关系 |
| PUT | /api/relations/{id} | 更新关系 |
| DELETE | /api/relations/{id} | 删除关系 |
| GET | /api/graph | 获取完整图谱数据（3D 渲染用） |
| GET | /api/graph/neighbors/{id} | 获取实体邻居子图 |
| GET | /api/search?q= | 搜索实体 |
| GET | /api/stats | 获取图谱统计 |

## 未来规划

- [ ] 与 JARVIS 联动，让 JARVIS 更懂用户
- [ ] GraphRAG 自动抽取：从聊天记录/文档中自动抽取实体关系
- [ ] 数据量增大后迁移 SQLite / Neo4j
