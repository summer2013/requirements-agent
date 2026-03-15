"""
review_agent.py — 复盘智能体

每个项目完成后自动运行，对比访谈笔记和最终 PRD，
提炼经验教训，写回知识库，形成自我进化闭环。

调用方式：
    result = run_review(
        project_name="供应链平台",
        interview_notes=notes_dict,
        prd_document=prd_text,
    )
    # result 包含 lessons_learned 和 missed_requirements
"""

import json
import os
from agent import run_agent

def _get_model() -> str:
    use_openrouter = bool(os.environ.get("OPENROUTER_API_KEY"))
    return "anthropic/claude-sonnet-4-6" if use_openrouter else "claude-sonnet-4-6"

REVIEW_SYSTEM = """你是一位经验丰富的产品顾问，专门做项目复盘。

你的任务是对比一个项目的【访谈笔记】和【最终PRD】，找出：
1. 访谈阶段遗漏了哪些重要需求（在PRD里出现但访谈没提到）
2. 下次做类似项目，访谈时应该主动问哪些问题
3. 这类项目有哪些规律性的需求容易被用户忽略

输出要求：
- lessons_learned：3-5 条可操作的经验，每条一句话
- missed_requirements：这次遗漏的需求列表
- interview_tips：针对同类项目的访谈问题建议

格式：严格输出 JSON，不要有任何多余文字。"""

REVIEW_TOOLS = [
    {
        "name": "save_review",
        "description": "保存复盘结果",
        "input_schema": {
            "type": "object",
            "properties": {
                "lessons_learned": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "可操作的经验教训，每条一句话"
                },
                "missed_requirements": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "本次访谈遗漏的需求"
                },
                "interview_tips": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "针对同类项目的访谈问题建议"
                },
                "project_type_tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "项目标签，例如：['内部工具', '零售', 'B端', '自动化']"
                }
            },
            "required": ["lessons_learned", "missed_requirements", "interview_tips"]
        }
    }
]


def run_review(
    project_name: str,
    industry: str,
    project_type: str,
    interview_notes: dict,
    prd_document: str,
) -> dict:
    """
    运行复盘智能体，返回提炼出的经验。

    参数：
        project_name    项目名称
        industry        行业
        project_type    项目类型
        interview_notes 结构化访谈笔记
        prd_document    最终 PRD 文本

    返回：
        {
            "lessons_learned": [...],
            "missed_requirements": [...],
            "interview_tips": [...],
            "project_type_tags": [...]
        }
    """
    review_result = {}

    def handler(tool_name: str, tool_input: dict) -> str:
        if tool_name == "save_review":
            review_result.update(tool_input)
            return json.dumps({"success": True})
        return json.dumps({"error": "unknown tool"})

    initial_msg = f"""
请对以下项目进行复盘：

项目名称：{project_name}
行业：{industry}
类型：{project_type}

【访谈笔记】
{json.dumps(interview_notes, ensure_ascii=False, indent=2)}

【最终 PRD 文档（节选关键部分）】
{prd_document[:3000]}{"..." if len(prd_document) > 3000 else ""}

请分析：
1. PRD 中出现但访谈笔记没有明确覆盖的需求有哪些？
2. 针对"{project_type}"类项目，下次访谈应该主动问哪些问题？
3. 提炼 3-5 条可操作的经验教训。

完成后调用 save_review 工具保存结果。
""".strip()

    print("\n  [复盘智能体] 分析中...")

    run_agent(
        agent_name="review",
        system_prompt=REVIEW_SYSTEM,
        tools=REVIEW_TOOLS,
        tool_handler=handler,
        initial_message=initial_msg,
        model=_get_model(),
        max_tokens=2048,
        temperature=0.2,
    )

    if review_result:
        print(f"  [复盘智能体] 提炼 {len(review_result.get('lessons_learned', []))} 条经验")

    return review_result
