# AceFelix 知识图谱 · 后端

FastAPI REST 服务 + MCP Server + LLM 抽取管线，按职责分目录组织。

## 目录结构

```
backend/
├── api.py                 # 入口：FastAPI REST 服务（:8800）
├── mcp_server.py          # 入口：MCP Server（jarvis 通过 stdio 接入）
├── requirements.txt       # Python 依赖
├── app/                   # 核心包（数据模型 / 存储引擎 / 抽取管线）
│   ├── __init__.py
│   ├── models.py          # 实体/关系数据模型与类型枚举
│   ├── knowledge_graph.py # 图谱存储引擎（JSON 落盘 + 备份 + 线程锁）
│   └── ingest.py          # 会话/文本 → 图谱的 LLM 抽取管线
├── config/                # 配置文件
│   ├── ingest.toml.example# 抽取模型配置模板（真实配置不入库）
│   └── ingest.toml        # 本地实际配置（含 API Key，已被 .gitignore 排除）
├── scripts/               # 辅助脚本
│   └── seed.py            # 示例数据初始化（首次运行时生成初始图谱）
├── tests/                 # 单元测试（LLM 调用全部 mock）
│   ├── test_ingest.py     # 抽取管线测试（五道防噪闸 + 查重）
│   └── test_mcp_server.py # MCP Server 工具测试
├── data/                  # 运行时数据（不入库，clone 后运行 seed.py 生成）
│   ├── graph.json         # 图谱主数据
│   └── backups/           # 自动滚动备份（最多 20 份）
├── uploads/               # 前端上传的图片（不入库）
├── logs/                  # 运行日志（不入库）
└── scratch/               # 本地调试残留文件（不入库，可随手清理）
```

## 常用命令

```powershell
cd acefelix/backend

# 启动 REST 服务（前端 :5173 依赖）
python api.py

# MCP Server 由 jarvis 的 mcp.json 按绝对路径拉起，一般无需手动启动

# 初始化示例数据
python scripts/seed.py

# 运行单测
python -m unittest discover tests
```

## 路径约定

- 核心模块统一从 `app` 包导入（`from app.knowledge_graph import KnowledgeGraph`）。
- 配置文件固定读 `backend/config/ingest.toml`，与运行目录无关（由 `__file__` 定位）。
- 数据文件由入口脚本（`api.py` / `mcp_server.py` / `scripts/seed.py`）以自身位置定位到 `backend/data/graph.json`，不依赖当前工作目录。

@author aceFelix
