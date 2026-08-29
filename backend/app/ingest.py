"""
GraphRAG 自动抽取管线（P1 版块）
文本 → 信息密度预检 → LLM 三元组抽取 → 查重/类型白名单 → 写入 KnowledgeGraph。

内置五道防噪闸（详见 docs/plans/upgrade-plan.md 3.4 节）：
  ① 入口闸：本管线只被显式调用（REST /api/ingest、MCP 工具、批量脚本），
     绝不挂在聊天实时链路上；
  ② 价值判断闸：抽取 prompt 内置预判，寒暄/情绪/琐事/纯问答返回空三元组；
  ③ 类型白名单闸：实体类型必须命中图谱现有类型表，否则进"待确认"清单不写入；
  ④ 信息密度闸：过短文本/纯疑问句在调用 LLM 之前直接跳过（省 token）；
  ⑤ 人工闸：支持 dry_run 预览，写入复用 KnowledgeGraph 的自动备份可回滚。

LLM 走 OpenAI 兼容协议（默认 DashScope 兼容端点），仅用标准库 urllib，零新依赖。
配置优先级：环境变量 > backend/config/ingest.toml > 内置默认值。

@author aceFelix
"""

from __future__ import annotations

import json
import os
import re
import tomllib
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ------------------------------------------------------------------ #
# 常量与默认配置
# ------------------------------------------------------------------ #

# 信息密度闸：低于该字符数的文本直接跳过（不浪费 LLM 调用）
MIN_TEXT_CHARS = 12
# 送入 LLM 的文本上限（超长截断，参考 profile_refiner 的限额做法）
DEFAULT_MAX_CHARS = 8000

# 抽取模型默认配置（独立便宜模型；留空 api_key 时回退环境变量）
DEFAULT_LLM_CONFIG: Dict[str, Any] = {
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "model": "qwen-flash",
    "api_key": "",
    # 指定从哪个环境变量读取 api_key（留空时依次回退 DASHSCOPE_API_KEY / OPENAI_API_KEY）
    "api_key_env": "",
    "temperature": 0.1,
    "timeout": 60,
    "max_chars": DEFAULT_MAX_CHARS,
}

# 配置文件路径（可选存在；含密钥，已在 .gitignore 中排除）。
# 目录重构后配置统一放 backend/config/，本文件在 app/ 下，故取上两级目录。
CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "ingest.toml"


class IngestError(RuntimeError):
    """抽取管线可预期错误（配置缺失 / LLM 调用失败 / 响应解析失败）"""


# ------------------------------------------------------------------ #
# 配置加载
# ------------------------------------------------------------------ #

def load_llm_config() -> Dict[str, Any]:
    """
    加载抽取模型配置。
    优先级：环境变量（INGEST_*）> backend/config/ingest.toml 的 [ingest] 段 > 内置默认值。
    api_key 额外回退到 DASHSCOPE_API_KEY / OPENAI_API_KEY 环境变量。
    """
    cfg = dict(DEFAULT_LLM_CONFIG)

    # 1) toml 配置文件（可选）
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "rb") as f:
                data = tomllib.load(f)
            section = data.get("ingest", {})
            for key in cfg:
                if key in section:
                    cfg[key] = section[key]
        except (tomllib.TOMLDecodeError, OSError) as e:
            raise IngestError(f"ingest.toml 解析失败: {e}")

    # 2) 环境变量覆盖（部署/临时切换模型时用）
    env_map = {
        "INGEST_BASE_URL": "base_url",
        "INGEST_MODEL": "model",
        "INGEST_API_KEY": "api_key",
    }
    for env_key, cfg_key in env_map.items():
        value = os.environ.get(env_key, "").strip()
        if value:
            cfg[cfg_key] = value

    # 3) api_key 回退链：配置值 > api_key_env 指定的环境变量 > DASHSCOPE_API_KEY > OPENAI_API_KEY
    if not cfg.get("api_key"):
        key_env = str(cfg.get("api_key_env", "") or "").strip()
        if key_env:
            cfg["api_key"] = os.environ.get(key_env, "")
        if not cfg.get("api_key"):
            cfg["api_key"] = os.environ.get("DASHSCOPE_API_KEY", "") or os.environ.get(
                "OPENAI_API_KEY", ""
            )
    return cfg


# ------------------------------------------------------------------ #
# LLM 调用（OpenAI 兼容协议，标准库实现）
# ------------------------------------------------------------------ #

def call_llm(system_prompt: str, user_prompt: str, cfg: Dict[str, Any]) -> str:
    """
    调用 OpenAI 兼容的 chat completions 接口，返回模型文本响应。

    @param system_prompt: 系统提示词
    @param user_prompt: 用户提示词（待抽取文本）
    @param cfg: load_llm_config() 返回的配置
    @raises IngestError: api_key 缺失、网络错误或响应格式异常
    """
    if not cfg.get("api_key"):
        raise IngestError(
            "抽取模型 api_key 未配置：请设置环境变量 DASHSCOPE_API_KEY，"
            "或在 backend/config/ingest.toml 的 [ingest] 段配置 api_key"
        )

    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    payload = {
        "model": cfg["model"],
        "temperature": cfg.get("temperature", 0.1),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg['api_key']}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=cfg.get("timeout", 60)) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return body["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        # 透出厂商返回的具体原因（如欠费/模型不存在/限流），便于定位
        try:
            detail = e.read().decode("utf-8")[:500]
        except OSError:
            detail = str(e)
        raise IngestError(f"LLM 抽取调用失败 (HTTP {e.code}): {detail}")
    except (urllib.error.URLError, KeyError, IndexError, json.JSONDecodeError, TimeoutError) as e:
        raise IngestError(f"LLM 抽取调用失败: {e}")


# ------------------------------------------------------------------ #
# 防噪闸 ④：信息密度预检（LLM 调用前的硬规则）
# ------------------------------------------------------------------ #

def density_check(text: str) -> Tuple[bool, str]:
    """
    信息密度硬规则预检，拦截低价值文本以节省 LLM 调用。

    @return (是否放行, 拒绝原因)；放行时原因为空串
    """
    stripped = text.strip()
    if len(stripped) < MIN_TEXT_CHARS:
        return False, f"文本过短（少于 {MIN_TEXT_CHARS} 字符）"

    # 纯疑问句判定：按句子切分后全部以问号结尾（寒暄式提问无知识含量）
    sentences = [s.strip() for s in re.split(r"[。！!；;\n]+", stripped) if s.strip()]
    if sentences and all(s.rstrip().endswith(("?", "？")) for s in sentences):
        return False, "纯疑问句，无可沉淀的知识陈述"
    return True, ""


# ------------------------------------------------------------------ #
# 抽取 prompt 构造与响应解析
# ------------------------------------------------------------------ #

def build_system_prompt(entity_types: List[str], relation_types: List[str]) -> str:
    """
    构造抽取系统提示词。
    动态注入图谱当前的实体类型白名单与关系类型白名单（类型表是动态的，
    不能硬编码），并内置价值预判规则与负例示范（防噪闸 ②③）。
    """
    return f"""你是个人知识图谱的三元组抽取引擎。阅读用户给出的文本，抽取值得长期沉淀的实体与关系。

【第一步：价值预判】（必须先做）
若文本属于以下任一类，直接输出空结果 {{"entities": [], "relations": []}}：
- 寒暄、问候、客套话（如"你好""早上好""谢谢"）
- 情绪表达、闲聊吐槽（如"今天好累""哈哈太好笑了"）
- 日常琐事、天气、吃饭等无长期价值的话题
- 纯粹的提问/求助，且文本本身不含事实性知识
示例：输入"今天天气不错，我们出去走走吧？" → 输出 {{"entities": [], "relations": []}}

【第二步：抽取规则】（通过价值预判后执行）
1. 实体 type 只能从白名单中选择：{json.dumps(entity_types, ensure_ascii=False)}
   无法归入任何类型的实体一律丢弃，不要自造类型；
2. 关系 type 只能从白名单中选择：{json.dumps(relation_types, ensure_ascii=False)}
   方向遵循语义（如"小明掌握Python" → source=小明, target=Python, type=HAS_SKILL）；
3. 关系的 source/target 必须是本次输出的实体名或上下文中明确的实体名；
4. 宁缺毋滥：只抽取明确陈述的事实，不推测、不脑补；每个实体可附简短 description。

【输出格式】只输出一个 JSON 对象，不要任何其他文字、注释或 markdown 代码块：
{{"entities": [{{"name": "实体名", "type": "类型", "description": "可选的简短说明"}}],
 "relations": [{{"source": "实体名", "target": "实体名", "type": "关系类型"}}]}}"""


def parse_llm_json(raw: str) -> Dict[str, Any]:
    """
    从 LLM 响应中稳健地解析出抽取结果。
    容错处理：剥离 markdown 代码围栏，截取首个 { 到末尾 } 的子串。

    @raises IngestError: 响应无法解析为合法 JSON
    """
    text = raw.strip()
    # 剥离可能的 ```json ... ``` 围栏
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    # 截取 JSON 对象主体（兼容模型在前后附加解释文字的情况）
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise IngestError("LLM 响应中未找到 JSON 对象")
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError as e:
        raise IngestError(f"LLM 响应 JSON 解析失败: {e}")
    # 结构兜底：缺字段补空列表
    entities = data.get("entities")
    relations = data.get("relations")
    return {
        "entities": entities if isinstance(entities, list) else [],
        "relations": relations if isinstance(relations, list) else [],
    }


# ------------------------------------------------------------------ #
# 名称归一化与查重
# ------------------------------------------------------------------ #

def normalize_name(name: str) -> str:
    """实体名归一化：去首尾空白、压缩内部空白、统一小写（查重用）"""
    return re.sub(r"\s+", " ", (name or "").strip()).casefold()


def _existing_name_index(kg) -> Dict[str, str]:
    """构建 归一化名 -> 实体ID 索引（实体查重用）"""
    return {normalize_name(e.name): e.id for e in kg.list_entities()}


# ------------------------------------------------------------------ #
# 主管线
# ------------------------------------------------------------------ #

def session_to_text(data: Any) -> str:
    """
    将 jarvis 会话记录（messages 数组）转成可抽取的纯文本。
    兼容两种结构：顶层为数组，或 {"messages": [...]}。

    @raises IngestError: 结构无法识别
    """
    messages = data.get("messages") if isinstance(data, dict) else data
    if not isinstance(messages, list):
        raise IngestError("会话数据格式无法识别：需要 messages 数组")
    lines = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = str(msg.get("role", "")).strip()
        content = str(msg.get("content", "")).strip()
        if content:
            lines.append(f"{role}: {content}" if role else content)
    return "\n".join(lines)


def ingest_text(
    kg,
    text: str,
    dry_run: bool = False,
    source: str = "text",
    llm_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    抽取管线主入口：文本 → 密度预检 → LLM 抽取 → 查重/白名单 → 写入。

    @param kg: KnowledgeGraph 实例（唯一数据访问入口）
    @param text: 待抽取文本
    @param dry_run: True 时只返回预览，不写入任何数据（防噪闸 ⑤）
    @param source: 来源标记（text / file / session），写入实体属性溯源
    @param llm_config: 注入配置（测试用），None 时自动加载
    @return 抽取结果摘要（含 created/skipped/pending 明细与最新版本号）
    @raises IngestError: 配置缺失、LLM 调用失败或响应无法解析
    """
    result: Dict[str, Any] = {
        "dry_run": dry_run,
        "gate": "passed",
        "created_entities": [],
        "created_relations": [],
        "skipped_duplicate_entities": [],
        "skipped_duplicate_relations": [],
        "pending_review": [],
        "skipped_relations": [],
    }

    # 闸 ④：信息密度硬规则（不过则不调 LLM，直接返回）
    ok, reason = density_check(text)
    if not ok:
        result["gate"] = f"rejected: {reason}"
        result["version"] = kg.version
        return result

    cfg = llm_config or load_llm_config()
    # 文本截取限额（超长截断，控制 token 成本）
    truncated = text.strip()[: int(cfg.get("max_chars", DEFAULT_MAX_CHARS))]

    # 闸 ②③：LLM 抽取（prompt 内置价值预判 + 类型白名单）
    system_prompt = build_system_prompt(
        list(kg.list_types().keys()), list(kg.list_relation_types().keys())
    )
    raw = call_llm(system_prompt, truncated, cfg)
    extracted = parse_llm_json(raw)

    # 价值预判返回空结果：闲聊等无知识含量文本到此为止，零写入
    if not extracted["entities"] and not extracted["relations"]:
        result["gate"] = "rejected: 价值预判为空（无值得沉淀的知识）"
        result["version"] = kg.version
        return result

    # ---- 实体查重与类型白名单 ----
    name_index = _existing_name_index(kg)
    # 本次批次的 归一化名 -> 实体ID（含新建的，供关系解析与批内查重）
    batch_index: Dict[str, str] = {}
    # 本次批次计划新建的实体（dry_run 时不落库）
    new_entities: List[Dict[str, Any]] = []
    # 待确认清单：类型不在白名单的实体（不写入，由人工裁决）
    valid_types = set(kg.list_types().keys())

    for ent in extracted["entities"]:
        if not isinstance(ent, dict):
            continue
        name = str(ent.get("name", "")).strip()
        ent_type = str(ent.get("type", "")).strip()
        if not name:
            continue
        norm = normalize_name(name)

        # 闸 ③：类型白名单，无法归类进"待确认"清单
        if ent_type not in valid_types:
            result["pending_review"].append(
                {"name": name, "type": ent_type or "(未给出)",
                 "reason": "实体类型不在白名单内"}
            )
            continue

        # 查重：命中现有实体或本批次已收录 → 复用，不重复建节点
        if norm in name_index:
            batch_index[norm] = name_index[norm]
            result["skipped_duplicate_entities"].append(name)
            continue
        if norm in batch_index:
            result["skipped_duplicate_entities"].append(name)
            continue

        if dry_run:
            # 预览模式用占位 ID，仅供关系解析与前端展示；同步登记预览明细后继续下一个实体（不落库）
            batch_index[norm] = f"dry-run:{norm}"
            new_entities.append({"name": name, "type": ent_type})
            result["created_entities"].append({"name": name, "type": ent_type})
            continue

        properties: Dict[str, Any] = {"source": source}
        description = str(ent.get("description", "")).strip()
        if description:
            properties["description"] = description
        created = kg.add_entity(name=name, type=ent_type, properties=properties)
        batch_index[norm] = created.id
        new_entities.append({"name": name, "type": ent_type})
        result["created_entities"].append({"name": name, "type": ent_type})

    # ---- 关系解析、查重与写入 ----
    valid_rel_types = set(kg.list_relation_types().keys())
    # 现有关系指纹集合：(源, 目标, 类型)
    existing_rel_keys = {
        (r.source, r.target, r.type) for r in kg.list_relations()
    }

    def resolve_endpoint(ref: str) -> Optional[str]:
        """关系端点解析：按名称在 现有实体 + 本批次新建 中查 ID"""
        if not ref:
            return None
        return batch_index.get(normalize_name(str(ref).strip()))

    for rel in extracted["relations"]:
        if not isinstance(rel, dict):
            continue
        rel_type = str(rel.get("type", "")).strip()
        source_id = resolve_endpoint(rel.get("source", ""))
        target_id = resolve_endpoint(rel.get("target", ""))

        if rel_type not in valid_rel_types:
            result["skipped_relations"].append(
                {"source": rel.get("source"), "target": rel.get("target"),
                 "type": rel_type, "reason": "关系类型不在白名单内"}
            )
            continue
        if not source_id or not target_id or source_id == target_id:
            result["skipped_relations"].append(
                {"source": rel.get("source"), "target": rel.get("target"),
                 "type": rel_type, "reason": "端点实体不存在、未入库或为自环"}
            )
            continue

        rel_key = (source_id, target_id, rel_type)
        if rel_key in existing_rel_keys:
            result["skipped_duplicate_relations"].append(
                {"source": rel.get("source"), "target": rel.get("target"), "type": rel_type}
            )
            continue

        if not dry_run:
            kg.add_relation(source=source_id, target=target_id, type=rel_type)
        existing_rel_keys.add(rel_key)
        result["created_relations"].append(
            {"source": rel.get("source"), "target": rel.get("target"), "type": rel_type}
        )

    result["version"] = kg.version
    return result
