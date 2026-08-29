"""
MCP Server 单元测试
覆盖只读工具的正常路径与写工具的错误/成功路径，
以及 ingest_text 抽取工具（P2 链路）的预览/写入/报错/拦截四路径。
写工具成功路径使用临时数据文件，不污染真实图谱。

运行: python backend/tests/test_mcp_server.py  （或 python -m unittest discover）

@author aceFelix
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# 测试在 tests/ 下，把 backend 根目录加入搜索路径以导入 app 包与入口脚本。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import mcp_server
from app import ingest
from app.knowledge_graph import KnowledgeGraph


class McpServerTest(unittest.TestCase):
    """MCP Server 工具测试基类（真实数据只读）"""

    def test_tools_registered(self):
        """13 个工具已注册（含 P2 新增的 ingest_text）"""
        tools = mcp_server.mcp._tool_manager._tools
        expected = {
            "add_entity", "add_relation", "common_neighbors", "find_paths",
            "get_entity", "get_neighbors", "get_profile", "get_stats",
            "ingest_text",
            "list_entities", "list_relation_types", "list_types", "search_entity",
        }
        self.assertEqual(set(tools.keys()), expected)

    def test_get_profile(self):
        """画像摘要：包含 person 且能解析为 JSON"""
        result = mcp_server.get_profile()
        data = json.loads(result)
        self.assertIn("person", data)
        self.assertIsNotNone(data["person"])
        self.assertIn("connections", data)

    def test_search_entity(self):
        """搜索"Python"能命中至少一个结果"""
        result = json.loads(mcp_server.search_entity("Python"))
        self.assertGreaterEqual(len(result["results"]), 1)
        self.assertEqual(result["results"][0]["name"], "Python")

    def test_get_entity_not_found(self):
        """不存在的实体返回 error"""
        result = json.loads(mcp_server.get_entity("no-such-id"))
        self.assertIn("error", result)

    def test_get_stats(self):
        """统计信息包含实体数与关系数"""
        result = json.loads(mcp_server.get_stats())
        self.assertIn("total_entities", result)
        self.assertIn("total_relations", result)

    def test_list_types(self):
        """类型表包含默认的 Person / Skill"""
        result = json.loads(mcp_server.list_types())
        self.assertIn("Person", result)
        self.assertIn("Skill", result)

    def test_list_relation_types(self):
        """关系类型表包含 HAS_SKILL"""
        result = json.loads(mcp_server.list_relation_types())
        self.assertIn("HAS_SKILL", result)

    def test_add_entity_invalid_type(self):
        """新增实体使用未注册类型 → 返回 error，不写数据"""
        result = json.loads(mcp_server.add_entity("测试", "NotExistType"))
        self.assertIn("error", result)

    def test_add_relation_missing_entity(self):
        """新增关系源实体不存在 → 返回 error"""
        result = json.loads(mcp_server.add_relation("no-such-id", "no-such-id", "HAS_SKILL"))
        self.assertIn("error", result)

    def test_add_entity_success_isolated(self):
        """写工具成功路径：使用临时空图谱，不触碰真实数据"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 空图谱自带默认类型表（Skill / HAS_SKILL 已内置）
            tmp_kg = KnowledgeGraph(str(Path(tmpdir) / "graph.json"))
            with mock.patch.object(mcp_server, "kg", tmp_kg):
                result = json.loads(mcp_server.add_entity("临时技能", "Skill", {"level": "1"}))
                self.assertTrue(result["ok"])
                self.assertEqual(result["name"], "临时技能")
                # 新增关系（自环，仅验证成功路径可用）
                rel = json.loads(
                    mcp_server.add_relation(result["id"], result["id"], "HAS_SKILL")
                )
                self.assertTrue(rel["ok"])


class McpIngestToolTest(unittest.TestCase):
    """ingest_text MCP 工具测试（P2 链路：Agent 触发抽取 / 画像回写）
    全部用临时图谱 + mock LLM，不碰真实数据、不发真实请求"""

    # 模拟 LLM 返回的三元组（人物 + 技能 + 关系）
    _PAYLOAD = {
        "entities": [
            {"name": "张三", "type": "Person", "description": "测试人物"},
            {"name": "Rust", "type": "Skill"},
        ],
        "relations": [
            {"source": "张三", "target": "Rust", "type": "HAS_SKILL"},
        ],
    }

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.kg = KnowledgeGraph(str(Path(self._tmpdir.name) / "graph.json"))
        # 把模块级 kg 换成临时图谱（与写工具测试同样的隔离手法）
        self._kg_patch = mock.patch.object(mcp_server, "kg", self.kg)
        self._kg_patch.start()

    def tearDown(self):
        self._kg_patch.stop()
        self._tmpdir.cleanup()

    def test_dry_run_preview_no_write(self):
        """dry_run 预览：返回抽取明细但不落库"""
        with mock.patch.object(ingest, "call_llm",
                               return_value=json.dumps(self._PAYLOAD, ensure_ascii=False)):
            result = json.loads(mcp_server.ingest_text("张三是一名后端工程师，擅长 Rust 系统开发", dry_run=True))
        self.assertTrue(result["dry_run"])
        self.assertEqual(len(result["created_entities"]), 2)
        self.assertEqual(len(result["created_relations"]), 1)
        self.assertEqual(len(self.kg.list_entities()), 0)  # 预览不写入

    def test_confirm_write(self):
        """dry_run=False 正式写入：实体与关系落库，来源标记正确"""
        with mock.patch.object(ingest, "call_llm",
                               return_value=json.dumps(self._PAYLOAD, ensure_ascii=False)):
            result = json.loads(
                mcp_server.ingest_text("张三是一名后端工程师，擅长 Rust 系统开发", dry_run=False, source="agent")
            )
        self.assertEqual(len(result["created_entities"]), 2)
        entities = self.kg.list_entities()
        self.assertEqual(len(entities), 2)
        person = next(e for e in entities if e.name == "张三")
        self.assertEqual(person.properties.get("source"), "agent")

    def test_density_gate_rejects_without_llm(self):
        """低密度文本被闸 ④ 拦截，不调 LLM、零写入"""
        with mock.patch.object(ingest, "call_llm") as llm:
            result = json.loads(mcp_server.ingest_text("你好", dry_run=False))
            llm.assert_not_called()
        self.assertIn("rejected", result["gate"])
        self.assertEqual(len(self.kg.list_entities()), 0)

    def test_llm_error_returns_error_json(self):
        """IngestError 不中断 MCP 会话，返回 error + hint"""
        with mock.patch.object(ingest, "call_llm",
                               side_effect=ingest.IngestError("LLM 调用失败")):
            result = json.loads(mcp_server.ingest_text("张三是一名后端工程师，擅长 Rust 系统开发", dry_run=True))
        self.assertIn("error", result)
        self.assertIn("hint", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
