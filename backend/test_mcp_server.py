"""
MCP Server 单元测试
覆盖只读工具的正常路径与写工具的错误/成功路径。
写工具成功路径使用临时数据文件，不污染真实图谱。

运行: python backend/test_mcp_server.py  （或 python -m unittest discover）

@author aceFelix
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent))

import mcp_server
from knowledge_graph import KnowledgeGraph


class McpServerTest(unittest.TestCase):
    """MCP Server 工具测试基类（真实数据只读）"""

    def test_tools_registered(self):
        """12 个工具已注册"""
        tools = mcp_server.mcp._tool_manager._tools
        expected = {
            "add_entity", "add_relation", "common_neighbors", "find_paths",
            "get_entity", "get_neighbors", "get_profile", "get_stats",
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
