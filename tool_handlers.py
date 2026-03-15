"""
tool_handlers.py — 工具处理器

每个智能体有独立的 handler 工厂函数。
handler 通过闭包持有共享 state，实现智能体间数据传递。

替换真实外部系统时只需修改此文件，不需要改 agent.py 或提示词。
"""

import json
from knowledge_base import search_similar_projects


def make_research_handler(state: dict):
    """
    调研智能体工具处理器。
    ask_question 在命令行交互模式下从 stdin 读取输入。
    在 Web 模式下可替换为 WebSocket 或消息队列。
    """
    def handler(tool_name: str, tool_input: dict) -> str:

        # ── 搜索知识库（接入真实向量库）──────────────────
        if tool_name == "search_knowledge_base":
            try:
                results = search_similar_projects(
                    query=tool_input["query"],
                    n_results=3,
                )
                if results["total_projects_in_kb"] == 0:
                    return json.dumps({
                        "message": "知识库暂无历史项目，这是第一个同类项目。",
                        "similar_projects": [],
                        "lessons_learned": [],
                        "requirement_patterns": [],
                    })
                return json.dumps(results)
            except Exception as e:
                return json.dumps({
                    "message": f"知识库查询失败（{e}），继续正常访谈。",
                    "similar_projects": [],
                    "lessons_learned": [],
                })

        # ── 向用户提问 ────────────────────────────────────
        if tool_name == "ask_question":
            question = tool_input["question"]
            print(f"\n[访谈问题] {question}")
            answer = input("回答 > ").strip()
            return json.dumps({"question": question, "answer": answer})

        # ── 保存访谈笔记 ──────────────────────────────────
        if tool_name == "save_interview_notes":
            state["interview_notes"] = tool_input
            return json.dumps({"success": True})

        return json.dumps({"error": f"未知工具: {tool_name}"})

    return handler


def make_document_handler(state: dict):
    """文档智能体工具处理器"""
    def handler(tool_name: str, tool_input: dict) -> str:

        if tool_name == "get_interview_notes":
            notes = state.get("interview_notes")
            if not notes:
                return json.dumps({"error": "访谈笔记尚未生成"})
            return json.dumps(notes)

        if tool_name == "search_prd_templates":
            try:
                results = search_similar_projects(
                    query=tool_input.get("project_type", ""),
                    n_results=2,
                )
                return json.dumps({
                    "similar_projects": results.get("similar_projects", []),
                    "default_template": {
                        "name": "SaaS B端标准模板",
                        "sections": ["背景", "用户故事", "NFR", "MoSCoW", "开放问题"]
                    }
                })
            except Exception:
                return json.dumps({
                    "templates": [
                        {"name": "SaaS B端标准模板",
                         "sections": ["背景", "用户故事", "NFR", "MoSCoW"]}
                    ]
                })

        if tool_name == "save_prd":
            state["prd_document"] = tool_input["prd_markdown"]
            state["prd_metadata"] = tool_input.get("metadata", {})
            return json.dumps({"success": True})

        return json.dumps({"error": f"未知工具: {tool_name}"})

    return handler


def make_prototype_handler(state: dict):
    """原型智能体工具处理器"""
    def handler(tool_name: str, tool_input: dict) -> str:

        if tool_name == "get_prd":
            prd = state.get("prd_document")
            if not prd:
                return json.dumps({"error": "PRD 尚未生成"})
            return json.dumps({"prd": prd})

        if tool_name == "save_prototype":
            state["prototype_html"] = tool_input["html"]
            return json.dumps({"success": True})

        return json.dumps({"error": f"未知工具: {tool_name}"})

    return handler


def make_prototype_handler_v2(state: dict):
    """原型智能体工具处理器（v2 含闭环检查）"""
    def handler(tool_name: str, tool_input: dict) -> str:

        if tool_name == "get_prd":
            prd = state.get("prd_document")
            if not prd:
                return json.dumps({"error": "PRD 尚未生成"})
            review = state.get("prd_review", {})
            return json.dumps({
                "prd": prd,
                "prd_review_report": {
                    "missing_scenarios": review.get("missing_scenarios", []),
                    "closure_gaps": review.get("closure_gaps", []),
                    "multi_role_gaps": review.get("multi_role_gaps", []),
                    "prototype_notes": review.get("overall_assessment", {}).get(
                        "recommendation", "无特殊提示"
                    ),
                }
            })

        if tool_name == "check_closure":
            review = state.get("prd_review", {})
            expected_scenarios = [
                s.get("scenario", "")
                for s in review.get("missing_scenarios", [])
                if s.get("severity") in ("critical", "major")
            ]
            coverage = tool_input.get("missing_scenarios_coverage", [])
            uncovered = [
                s for s in expected_scenarios
                if not any(
                    c.get("covered") and s in c.get("scenario", "")
                    for c in coverage
                )
            ]
            pages = tool_input.get("pages", [])
            dead_ends = [p["page_name"] for p in pages if not p.get("exit_to")]
            passed = len(uncovered) == 0 and len(dead_ends) == 0
            state["closure_check"] = {
                "passed": passed,
                "uncovered_scenarios": uncovered,
                "dead_end_pages": dead_ends,
            }
            return json.dumps({
                "passed": passed,
                "uncovered_critical_scenarios": uncovered,
                "dead_end_pages": dead_ends,
                "message": (
                    "✅ 闭环检查通过，可以保存原型。" if passed
                    else f"⚠️  闭环检查未通过：{len(uncovered)} 个场景未覆盖，{len(dead_ends)} 个页面无出口。请修复后重新检查。"
                )
            })

        if tool_name == "save_prototype":
            if not tool_input.get("closure_verified", False):
                return json.dumps({
                    "error": "必须先调用 check_closure 并确认通过，再保存原型。请将 closure_verified 设为 true。"
                })
            state["prototype_html"] = tool_input["html"]
            state["prototype_pages"] = tool_input.get("pages", [])
            return json.dumps({"success": True})

        return json.dumps({"error": f"未知工具: {tool_name}"})

    return handler
