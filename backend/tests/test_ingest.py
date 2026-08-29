"""
知识抽取管线（GraphRAG P1）单元测试
覆盖五道防噪闸与查重逻辑，LLM 调用全部 mock，不产生真实网络请求；
写入路径使用临时图谱文件，不污染真实数据。

运行: python backend/tests/test_ingest.py （或 python -m unittest discover）

@author aceFelix
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# 测试在 tests/ 下，把 backend 根目录加入搜索路径以导入 app 包。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import ingest
from app.knowledge_graph import KnowledgeGraph


def _mock_llm(payload: dict):
    """构造 call_llm 的 mock：返回给定三元组结构的 JSON 字符串"""
    return mock.patch.object(ingest, "call_llm", return_value=json.dumps(payload, ensure_ascii=False))


class IngestPipelineTest(unittest.TestCase):
    """抽取管线测试基类：每个用例独立临时图谱"""

    def setUp(self):
        # 临时空图谱（自带默认 10 种实体类型 / 12 种关系类型）
        self._tmpdir = tempfile.TemporaryDirectory()
        self.kg = KnowledgeGraph(str(Path(self._tmpdir.name) / "graph.json"))

    def tearDown(self):
        self._tmpdir.cleanup()

    # ---------------- 闸 ④：信息密度预检 ---------------- #

    def test_density_gate_short_text(self):
        """过短文本直接拒绝，不调用 LLM，零写入"""
        with mock.patch.object(ingest, "call_llm") as llm:
            result = ingest.ingest_text(self.kg, "你好")
            llm.assert_not_called()
        self.assertIn("rejected", result["gate"])
        self.assertEqual(len(result["created_entities"]), 0)
        self.assertEqual(len(self.kg.list_entities()), 0)

    def test_density_gate_pure_question(self):
        """纯疑问句直接拒绝，不调用 LLM"""
        with mock.patch.object(ingest, "call_llm") as llm:
            result = ingest.ingest_text(self.kg, "今天吃什么好呢？中午吃什么？")
            llm.assert_not_called()
        self.assertIn("rejected", result["gate"])

    # ---------------- 闸 ②：价值预判（闲聊零写入负例） ---------------- #

    def test_chitchat_zero_write(self):
        """验收负例：闲聊文本 → LLM 价值预判返回空 → 零实体写入"""
        empty = {"entities": [], "relations": []}
        with _mock_llm(empty):
            result = ingest.ingest_text(
                self.kg, "哈哈今天真是太开心了，晚上打算去吃顿好的庆祝一下！"
            )
        self.assertIn("价值预判为空", result["gate"])
        self.assertEqual(len(result["created_entities"]), 0)
        self.assertEqual(len(self.kg.list_entities()), 0)
        self.assertEqual(len(self.kg.list_relations()), 0)

    # ---------------- 正常抽取 + 写入 ---------------- #

    def test_normal_extraction_writes(self):
        """含人物/技能/项目关系的文本 → 正确抽取并入库"""
        payload = {
            "entities": [
                {"name": "小明", "type": "Person", "description": "用户朋友"},
                {"name": "Python", "type": "Skill"},
                {"name": "AceFelix", "type": "Project"},
            ],
            "relations": [
                {"source": "小明", "target": "Python", "type": "HAS_SKILL"},
                {"source": "小明", "target": "AceFelix", "type": "WORKS_ON"},
            ],
        }
        with _mock_llm(payload):
            result = ingest.ingest_text(self.kg, "小明擅长 Python，正在参与 AceFelix 项目。")
        self.assertEqual(len(result["created_entities"]), 3)
        self.assertEqual(len(result["created_relations"]), 2)
        self.assertEqual(len(self.kg.list_entities()), 3)
        self.assertEqual(len(self.kg.list_relations()), 2)
        # 溯源属性：新建实体带 source 标记
        names = {e.name: e for e in self.kg.list_entities()}
        self.assertEqual(names["小明"].properties.get("source"), "text")

    def test_dedup_existing_entity(self):
        """实体查重：图谱已有同名实体（大小写/空白差异）不重复建节点"""
        self.kg.add_entity(name="python", type="Skill")
        payload = {
            "entities": [{"name": "  Python ", "type": "Skill"}],
            "relations": [],
        }
        with _mock_llm(payload):
            result = ingest.ingest_text(self.kg, "他一直在深入学习 Python 语言。")
        self.assertEqual(len(result["created_entities"]), 0)
        self.assertEqual(len(result["skipped_duplicate_entities"]), 1)
        self.assertEqual(len(self.kg.list_entities()), 1)

    def test_repeat_ingest_no_duplicates(self):
        """验收：重复输入同一文本不产生重复实体与关系"""
        payload = {
            "entities": [{"name": "张三", "type": "Person"}, {"name": "Go", "type": "Skill"}],
            "relations": [{"source": "张三", "target": "Go", "type": "HAS_SKILL"}],
        }
        text = "张三最近开始学习 Go 语言，进步很快。"
        with _mock_llm(payload):
            first = ingest.ingest_text(self.kg, text)
            second = ingest.ingest_text(self.kg, text)
        self.assertEqual(len(first["created_entities"]), 2)
        self.assertEqual(len(second["created_entities"]), 0)
        self.assertEqual(len(second["created_relations"]), 0)
        self.assertEqual(len(self.kg.list_entities()), 2)
        self.assertEqual(len(self.kg.list_relations()), 1)

    # ---------------- 闸 ⑤：dry_run 预览 ---------------- #

    def test_dry_run_no_write(self):
        """dry_run 模式：返回预览明细但不落库"""
        payload = {
            "entities": [{"name": "李四", "type": "Person"}],
            "relations": [],
        }
        with _mock_llm(payload):
            result = ingest.ingest_text(self.kg, "李四是一名经验丰富的后端工程师，专注分布式系统。", dry_run=True)
        self.assertTrue(result["dry_run"])
        self.assertEqual(len(result["created_entities"]), 1)
        self.assertEqual(len(self.kg.list_entities()), 0)

    def test_dry_run_then_commit(self):
        """dry_run 预览后再正式写入：关系端点可正确解析落库实体"""
        payload = {
            "entities": [{"name": "王五", "type": "Person"}, {"name": "Rust", "type": "Skill"}],
            "relations": [{"source": "王五", "target": "Rust", "type": "HAS_SKILL"}],
        }
        text = "王五掌握 Rust 系统编程技能。"
        with _mock_llm(payload):
            preview = ingest.ingest_text(self.kg, text, dry_run=True)
            committed = ingest.ingest_text(self.kg, text)
        self.assertEqual(len(preview["created_relations"]), 1)
        self.assertEqual(len(committed["created_relations"]), 1)
        self.assertEqual(len(self.kg.list_relations()), 1)

    # ---------------- 闸 ③：类型白名单 ---------------- #

    def test_type_whitelist_pending_review(self):
        """实体类型不在白名单 → 进待确认清单，不写入；关联关系同步跳过"""
        payload = {
            "entities": [{"name": "某神秘物", "type": "AlienType"}],
            "relations": [{"source": "某神秘物", "target": "Python", "type": "HAS_SKILL"}],
        }
        with _mock_llm(payload):
            result = ingest.ingest_text(self.kg, "有人提到了一种叫某神秘物的东西和Python有关。")
        self.assertEqual(len(result["pending_review"]), 1)
        self.assertEqual(result["pending_review"][0]["name"], "某神秘物")
        self.assertEqual(len(result["created_entities"]), 0)
        # 关系端点未入库 → 关系被跳过并说明原因
        self.assertEqual(len(result["skipped_relations"]), 1)
        self.assertEqual(len(self.kg.list_entities()), 0)

    def test_invalid_relation_type_skipped(self):
        """关系类型不在白名单 → 跳过并记录原因，实体正常写入"""
        payload = {
            "entities": [{"name": "赵六", "type": "Person"}],
            "relations": [{"source": "赵六", "target": "赵六", "type": "LOVES"}],
        }
        with _mock_llm(payload):
            result = ingest.ingest_text(self.kg, "赵六非常热爱自己的事业。")
        self.assertEqual(len(result["created_entities"]), 1)
        self.assertEqual(len(result["skipped_relations"]), 1)
        self.assertIn("白名单", result["skipped_relations"][0]["reason"])

    # ---------------- 辅助函数 ---------------- #

    def test_parse_llm_json_with_fences(self):
        """LLM 响应带 markdown 围栏与前后缀文字时仍能解析"""
        raw = '好的，结果如下：\n```json\n{"entities": [], "relations": []}\n```\n希望有帮助。'
        data = ingest.parse_llm_json(raw)
        self.assertEqual(data["entities"], [])
        self.assertEqual(data["relations"], [])

    def test_parse_llm_json_invalid(self):
        """响应无 JSON 对象时抛出 IngestError"""
        with self.assertRaises(ingest.IngestError):
            ingest.parse_llm_json("抱歉，我无法理解这段文本。")

    def test_session_to_text(self):
        """会话 JSON 转文本：兼容顶层数组与 messages 包装两种结构"""
        messages = [
            {"role": "user", "content": "我在学 FastAPI"},
            {"role": "assistant", "content": "FastAPI 是很好的框架"},
        ]
        self.assertIn("user: 我在学 FastAPI", ingest.session_to_text(messages))
        self.assertIn("assistant:", ingest.session_to_text({"messages": messages}))
        with self.assertRaises(ingest.IngestError):
            ingest.session_to_text("不是会话结构")

    def test_llm_config_env_override(self):
        """配置加载：环境变量覆盖默认值，api_key 回退 DASHSCOPE_API_KEY"""
        # 隔离本机真实 ingest.toml，保证用例在任何机器上行为一致
        with mock.patch.object(ingest, "CONFIG_PATH", Path("/nonexistent/ingest.toml")):
            with mock.patch.dict(
                "os.environ",
                {"INGEST_MODEL": "qwen-max", "DASHSCOPE_API_KEY": "test-key"},
                clear=False,
            ):
                cfg = ingest.load_llm_config()
        self.assertEqual(cfg["model"], "qwen-max")
        self.assertEqual(cfg["api_key"], "test-key")

    def test_llm_config_api_key_env(self):
        """api_key_env 机制：按配置指定的环境变量名读取密钥（优先于默认回退链）"""
        with mock.patch.object(ingest, "CONFIG_PATH", Path("/nonexistent/ingest.toml")):
            with mock.patch.dict(
                "os.environ",
                {"DEEPSEEK_API_KEY": "ds-key", "DASHSCOPE_API_KEY": "dash-key"},
                clear=False,
            ):
                with mock.patch.dict(
                    ingest.DEFAULT_LLM_CONFIG, {"api_key_env": "DEEPSEEK_API_KEY"}
                ):
                    cfg = ingest.load_llm_config()
        self.assertEqual(cfg["api_key"], "ds-key")

    def test_call_llm_missing_key(self):
        """api_key 缺失时抛出友好错误而不是裸调网络"""
        with self.assertRaises(ingest.IngestError) as ctx:
            ingest.call_llm("sys", "user", {**ingest.DEFAULT_LLM_CONFIG, "api_key": ""})
        self.assertIn("api_key", str(ctx.exception))

    def test_call_llm_http_error_detail(self):
        """HTTP 错误时透出厂商返回的具体原因（如欠费/模型不存在）"""
        import io
        import urllib.error

        fake_body = b'{"error": {"message": "Arrearage", "code": "Arrearage"}}'
        http_err = urllib.error.HTTPError(
            "http://x", 400, "Bad Request", {}, io.BytesIO(fake_body)
        )
        with mock.patch("urllib.request.urlopen", side_effect=http_err):
            with self.assertRaises(ingest.IngestError) as ctx:
                ingest.call_llm("sys", "user", {**ingest.DEFAULT_LLM_CONFIG, "api_key": "k"})
        self.assertIn("Arrearage", str(ctx.exception))
        self.assertIn("400", str(ctx.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
