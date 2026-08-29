"""AceFelix 知识图谱后端核心包。

按职责分层的模块集合（入口脚本留在 backend/ 根目录）：

- models: 实体/关系数据模型与类型枚举
- knowledge_graph: 图谱存储引擎（JSON 落盘 + 备份 + 线程锁）
- ingest: 会话/文本 → 图谱的 LLM 抽取管线

入口层：
- backend/api.py    FastAPI REST 服务（:8800）
- backend/mcp_server.py  MCP Server（jarvis stdio 接入）

@author aceFelix
"""
