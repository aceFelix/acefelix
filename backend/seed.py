"""
种子数据初始化脚本
基于用户真实画像数据初始化知识图谱。

@author aceFelix
"""

from __future__ import annotations

import sys
from pathlib import Path

# 添加当前目录到 path，方便直接运行
sys.path.insert(0, str(Path(__file__).parent))

from knowledge_graph import KnowledgeGraph
from models import EntityType, RelationType


def seed_data(kg: KnowledgeGraph) -> None:
    """
    向知识图谱中注入初始种子数据
    包含用户本人、技能、知识、项目、工具、兴趣等实体及其关联关系

    @param kg: KnowledgeGraph 实例
    """

    # 如果已有数据则跳过
    if kg.list_entities():
        print("图谱已有数据，跳过种子数据初始化")
        return

    # ------------------------------------------------------------------ #
    # 实体：人物
    # ------------------------------------------------------------------ #
    acefelix = kg.add_entity("许发明 (aceFelix)", EntityType.PERSON.value, {
        "role": "全栈开发者",
        "github": "acefelix",
    })

    # ------------------------------------------------------------------ #
    # 实体：技能
    # ------------------------------------------------------------------ #
    skill_python = kg.add_entity("Python", EntityType.SKILL.value, {"proficiency": "高级", "years": 5})
    skill_java = kg.add_entity("Java", EntityType.SKILL.value, {"proficiency": "中级", "years": 3})
    skill_vue = kg.add_entity("Vue 3", EntityType.SKILL.value, {"proficiency": "中级", "years": 2})
    skill_springboot = kg.add_entity("Spring Boot", EntityType.SKILL.value, {"proficiency": "中级", "years": 3})
    skill_vite = kg.add_entity("Vite", EntityType.SKILL.value, {"proficiency": "中级", "years": 2})
    skill_maven = kg.add_entity("Maven", EntityType.SKILL.value, {"proficiency": "中级", "years": 3})

    # ------------------------------------------------------------------ #
    # 实体：知识领域
    # ------------------------------------------------------------------ #
    know_ai_agent = kg.add_entity("AI Agent", EntityType.KNOWLEDGE.value, {"description": "智能体架构与开发"})
    know_kg = kg.add_entity("知识图谱", EntityType.KNOWLEDGE.value, {"description": "图结构知识表示"})
    know_graphrag = kg.add_entity("GraphRAG", EntityType.KNOWLEDGE.value, {"description": "图增强检索生成"})
    know_rag = kg.add_entity("RAG", EntityType.KNOWLEDGE.value, {"description": "检索增强生成"})
    know_llm = kg.add_entity("大语言模型", EntityType.KNOWLEDGE.value, {"description": "LLM 原理与应用"})

    # ------------------------------------------------------------------ #
    # 实体：项目
    # ------------------------------------------------------------------ #
    proj_jarvis = kg.add_entity("J.A.R.V.I.S", EntityType.PROJECT.value, {
        "description": "个人 AI 助手，支持语音交互、工具调用、多模型切换",
        "status": "开发中",
        "tech_stack": "Python, Vue, FastAPI",
    })
    proj_bitinn = kg.add_entity("bitinn", EntityType.PROJECT.value, {
        "description": "业务系统",
        "status": "开发中",
        "tech_stack": "Spring Boot, Vue",
    })

    # ------------------------------------------------------------------ #
    # 实体：工具
    # ------------------------------------------------------------------ #
    tool_vscode = kg.add_entity("VS Code", EntityType.TOOL.value, {"type": "编辑器"})
    tool_git = kg.add_entity("Git", EntityType.TOOL.value, {"type": "版本控制"})
    tool_docker = kg.add_entity("Docker", EntityType.TOOL.value, {"type": "容器"})
    tool_mongodb = kg.add_entity("MongoDB", EntityType.TOOL.value, {"type": "数据库"})
    tool_mysql = kg.add_entity("MySQL", EntityType.TOOL.value, {"type": "数据库"})

    # ------------------------------------------------------------------ #
    # 实体：兴趣
    # ------------------------------------------------------------------ #
    interest_opensource = kg.add_entity("开源项目", EntityType.INTEREST.value, {})
    interest_ai = kg.add_entity("AI 探索", EntityType.INTEREST.value, {})
    interest_game = kg.add_entity("游戏", EntityType.INTEREST.value, {})

    # ------------------------------------------------------------------ #
    # 实体：任务
    # ------------------------------------------------------------------ #
    task_m2 = kg.add_entity("M2 阶段开发", EntityType.TASK.value, {"status": "进行中"})
    task_kg = kg.add_entity("个人知识图谱搭建", EntityType.TASK.value, {"status": "进行中"})

    # ------------------------------------------------------------------ #
    # 实体：目标
    # ------------------------------------------------------------------ #
    goal_personal_assistant = kg.add_entity("打造个性化 AI 助手", EntityType.GOAL.value, {"timeline": "2026"})

    # ------------------------------------------------------------------ #
    # 关系：人物 -> 技能
    # ------------------------------------------------------------------ #
    kg.add_relation(acefelix.id, skill_python.id, RelationType.HAS_SKILL.value)
    kg.add_relation(acefelix.id, skill_java.id, RelationType.HAS_SKILL.value)
    kg.add_relation(acefelix.id, skill_vue.id, RelationType.HAS_SKILL.value)
    kg.add_relation(acefelix.id, skill_springboot.id, RelationType.HAS_SKILL.value)
    kg.add_relation(acefelix.id, skill_vite.id, RelationType.HAS_SKILL.value)
    kg.add_relation(acefelix.id, skill_maven.id, RelationType.HAS_SKILL.value)

    # ------------------------------------------------------------------ #
    # 关系：人物 -> 知识
    # ------------------------------------------------------------------ #
    kg.add_relation(acefelix.id, know_ai_agent.id, RelationType.KNOWS.value)
    kg.add_relation(acefelix.id, know_kg.id, RelationType.KNOWS.value)
    kg.add_relation(acefelix.id, know_graphrag.id, RelationType.KNOWS.value)
    kg.add_relation(acefelix.id, know_rag.id, RelationType.KNOWS.value)
    kg.add_relation(acefelix.id, know_llm.id, RelationType.KNOWS.value)

    # ------------------------------------------------------------------ #
    # 关系：人物 -> 项目
    # ------------------------------------------------------------------ #
    kg.add_relation(acefelix.id, proj_jarvis.id, RelationType.WORKS_ON.value)
    kg.add_relation(acefelix.id, proj_bitinn.id, RelationType.WORKS_ON.value)

    # ------------------------------------------------------------------ #
    # 关系：人物 -> 工具
    # ------------------------------------------------------------------ #
    kg.add_relation(acefelix.id, tool_vscode.id, RelationType.USES.value)
    kg.add_relation(acefelix.id, tool_git.id, RelationType.USES.value)
    kg.add_relation(acefelix.id, tool_docker.id, RelationType.USES.value)
    kg.add_relation(acefelix.id, tool_mongodb.id, RelationType.USES.value)
    kg.add_relation(acefelix.id, tool_mysql.id, RelationType.USES.value)

    # ------------------------------------------------------------------ #
    # 关系：人物 -> 兴趣
    # ------------------------------------------------------------------ #
    kg.add_relation(acefelix.id, interest_opensource.id, RelationType.INTERESTED_IN.value)
    kg.add_relation(acefelix.id, interest_ai.id, RelationType.INTERESTED_IN.value)
    kg.add_relation(acefelix.id, interest_game.id, RelationType.INTERESTED_IN.value)

    # ------------------------------------------------------------------ #
    # 关系：人物 -> 任务
    # ------------------------------------------------------------------ #
    kg.add_relation(acefelix.id, task_m2.id, RelationType.DOING.value)
    kg.add_relation(acefelix.id, task_kg.id, RelationType.DOING.value)

    # ------------------------------------------------------------------ #
    # 关系：人物 -> 目标
    # ------------------------------------------------------------------ #
    kg.add_relation(acefelix.id, goal_personal_assistant.id, RelationType.RELATED_TO.value)

    # ------------------------------------------------------------------ #
    # 关系：项目 <-> 技能
    # ------------------------------------------------------------------ #
    kg.add_relation(proj_jarvis.id, skill_python.id, RelationType.RELATED_TO.value)
    kg.add_relation(proj_jarvis.id, skill_vue.id, RelationType.RELATED_TO.value)
    kg.add_relation(proj_bitinn.id, skill_springboot.id, RelationType.RELATED_TO.value)
    kg.add_relation(proj_bitinn.id, skill_vue.id, RelationType.RELATED_TO.value)

    # ------------------------------------------------------------------ #
    # 关系：项目 -> 知识
    # ------------------------------------------------------------------ #
    kg.add_relation(proj_jarvis.id, know_ai_agent.id, RelationType.RELATED_TO.value)
    kg.add_relation(proj_jarvis.id, know_llm.id, RelationType.RELATED_TO.value)
    kg.add_relation(task_kg.id, know_kg.id, RelationType.RELATED_TO.value)
    kg.add_relation(task_kg.id, know_graphrag.id, RelationType.RELATED_TO.value)

    # ------------------------------------------------------------------ #
    # 关系：知识之间的依赖
    # ------------------------------------------------------------------ #
    kg.add_relation(know_graphrag.id, know_rag.id, RelationType.DEPENDS_ON.value)
    kg.add_relation(know_graphrag.id, know_kg.id, RelationType.DEPENDS_ON.value)
    kg.add_relation(know_rag.id, know_llm.id, RelationType.DEPENDS_ON.value)
    kg.add_relation(know_ai_agent.id, know_llm.id, RelationType.RELATED_TO.value)

    # ------------------------------------------------------------------ #
    # 关系：任务 -> 目标
    # ------------------------------------------------------------------ #
    kg.add_relation(task_kg.id, goal_personal_assistant.id, RelationType.LEADS_TO.value)
    kg.add_relation(proj_jarvis.id, goal_personal_assistant.id, RelationType.LEADS_TO.value)

    # ------------------------------------------------------------------ #
    # 关系：技能之间相似
    # ------------------------------------------------------------------ #
    kg.add_relation(skill_vue.id, skill_vite.id, RelationType.SIMILAR_TO.value)
    kg.add_relation(skill_java.id, skill_springboot.id, RelationType.RELATED_TO.value)

    print(f"种子数据初始化完成！")
    print(f"  实体数: {len(kg.list_entities())}")
    print(f"  关系数: {len(kg.list_relations())}")


if __name__ == "__main__":
    data_path = Path(__file__).parent / "data" / "graph.json"
    kg = KnowledgeGraph(str(data_path))
    seed_data(kg)
