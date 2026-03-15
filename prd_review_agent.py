"""
prd_review_agent.py — PRD 评审智能体

在 PRD 生成后、原型制作前运行。
系统性检查 PRD 的完整性、逻辑一致性和场景覆盖度，
输出结构化评审报告供人工确认和原型 agent 参考。

核心评审维度：
  1. 结构完整性    — 背景/目标/角色/边界/异常是否齐全
  2. 逻辑一致性    — 前提/触发/结果/可逆性是否自洽
  3. 流程闭环      — 每个流程是否有出口，每个操作是否有反馈
  4. 场景穷举      — MECE 状态枚举，空态/异常/并发是否覆盖
  5. 多角色协同    — 跨角色流程（审批、通知、等待态）是否完整
"""

import json
import os
from agent import run_agent


def _get_model() -> str:
    use_openrouter = bool(os.environ.get("OPENROUTER_API_KEY"))
    return "anthropic/claude-sonnet-4-6" if use_openrouter else "claude-sonnet-4-6"


PRD_REVIEW_SYSTEM = """你是一位资深的需求评审专家，擅长在 PRD 变成原型之前找出所有逻辑漏洞和遗漏场景。

你的任务是对 PRD 进行五个维度的系统性评审，并产出结构化评审报告。

---

## 评审维度一：结构完整性

检查 PRD 是否包含以下要素：
- 背景与目标（为什么做？成功指标是什么？）
- 用户角色（每个角色的权限边界）
- 功能范围（明确的 in scope / out of scope）
- 异常与边界条件（数据为空、网络失败、权限不足时的处理）
- 依赖关系（外部系统、接口、团队依赖）

评分标准：缺失任意一项记为 critical issue。

---

## 评审维度二：逻辑一致性

对每条用户故事用以下框架拷问：
1. 前提条件：这个操作发生之前，系统/用户需要满足什么状态？PRD 有没有描述？
2. 触发条件：什么情况下会触发这个功能？
3. 结果状态：操作完成后，系统和用户分别处于什么状态？是否明确？
4. 可逆性：这个操作可以撤销吗？如果不能，是否有二次确认机制？

评分标准：任何故事缺少"结果状态"描述，记为 major issue。

---

## 评审维度三：流程闭环检查

对每个业务流程检查：
- 所有判断节点（条件分支）是否两条路都有出口？
- 有没有"死路"——用户进入某个状态后无法继续也无法退出？
- 用户完成操作后，是否有明确的结果反馈（成功/失败提示）？
- 数据从哪来？写到哪去？谁会感知到变化？

---

## 评审维度四：场景穷举（MECE）

对 PRD 中每个核心业务对象（如：订单、申请单、用户等），穷举其所有状态：
- 例如订单：待付款 / 已付款 / 配送中 / 已完成 / 已取消 / 退款中 / 已退款
- 对每种状态检查：PRD 是否描述了这个状态下的 UI 和可操作动作？

必检清单：
□ 列表页：数据为空时怎么显示？
□ 列表页：数据量超大（10000条）怎么处理？
□ 表单页：字段填写错误的提示？必填项校验？
□ 文字字段：内容超长时截断还是换行？
□ 图片字段：图片不存在时显示什么？
□ 异步操作：等待中/处理中如何显示？
□ 网络错误：操作失败时如何恢复？
□ 并发操作：两个人同时编辑同一条数据？
□ 用户中途退出：草稿保存？数据丢失？

---

## 评审维度五：多角色协同

如果 PRD 涉及多个角色（如审批流、通知流）：
- 每一步的"发起者"和"接收者"是否都定义了行为？
- 等待状态（等待审批、等待对方确认）是否有视觉状态描述？
- 通知/消息的触发时机和内容是否明确？
- 超时未处理时系统行为是什么？

---

## 输出要求

调用 save_prd_review 工具保存评审结果，格式严格按工具 schema 输出。

评审等级定义：
- critical：缺失会导致产品无法上线或用户数据错误
- major：影响核心功能体验，必须在原型阶段修复
- minor：体验细节，可在后续迭代处理

最终给出 overall_assessment（overall, ready_for_prototype, critical_count, major_count, minor_count）。

如果 critical_count > 0，建议在 recommendation 字段写明"建议修订 PRD 后再生成原型"。
"""


PRD_REVIEW_TOOLS = [
    {
        "name": "save_prd_review",
        "description": "保存 PRD 评审报告",
        "input_schema": {
            "type": "object",
            "properties": {
                "structural_issues": {
                    "type": "array",
                    "description": "结构完整性问题",
                    "items": {
                        "type": "object",
                        "properties": {
                            "severity": {"type": "string", "enum": ["critical", "major", "minor"]},
                            "dimension": {"type": "string", "description": "评审维度"},
                            "issue": {"type": "string", "description": "问题描述"},
                            "location": {"type": "string", "description": "在 PRD 中的位置（如用户故事 ID 或章节）"},
                            "suggestion": {"type": "string", "description": "修复建议"}
                        },
                        "required": ["severity", "dimension", "issue", "suggestion"]
                    }
                },
                "missing_scenarios": {
                    "type": "array",
                    "description": "遗漏的场景（空状态/异常/边界/并发等）",
                    "items": {
                        "type": "object",
                        "properties": {
                            "object": {"type": "string", "description": "涉及的业务对象，如'订单'"},
                            "scenario": {"type": "string", "description": "遗漏的场景描述"},
                            "severity": {"type": "string", "enum": ["critical", "major", "minor"]},
                            "suggested_handling": {"type": "string", "description": "建议的处理方式"}
                        },
                        "required": ["object", "scenario", "severity", "suggested_handling"]
                    }
                },
                "closure_gaps": {
                    "type": "array",
                    "description": "流程闭环问题（死路/无出口/无反馈）",
                    "items": {
                        "type": "object",
                        "properties": {
                            "flow": {"type": "string", "description": "涉及的流程名称"},
                            "gap": {"type": "string", "description": "闭环漏洞描述"},
                            "severity": {"type": "string", "enum": ["critical", "major", "minor"]}
                        },
                        "required": ["flow", "gap", "severity"]
                    }
                },
                "multi_role_gaps": {
                    "type": "array",
                    "description": "多角色协同问题",
                    "items": {
                        "type": "object",
                        "properties": {
                            "roles_involved": {"type": "array", "items": {"type": "string"}},
                            "gap": {"type": "string"},
                            "severity": {"type": "string", "enum": ["critical", "major", "minor"]}
                        },
                        "required": ["roles_involved", "gap", "severity"]
                    }
                },
                "overall_assessment": {
                    "type": "object",
                    "properties": {
                        "ready_for_prototype": {
                            "type": "boolean",
                            "description": "是否可以直接进入原型阶段"
                        },
                        "critical_count": {"type": "integer"},
                        "major_count": {"type": "integer"},
                        "minor_count": {"type": "integer"},
                        "summary": {
                            "type": "string",
                            "description": "100字以内的整体评价"
                        },
                        "recommendation": {
                            "type": "string",
                            "description": "给原型 agent 的重点提示（哪些场景一定要在原型中体现）"
                        }
                    },
                    "required": ["ready_for_prototype", "critical_count", "major_count", "minor_count", "summary", "recommendation"]
                }
            },
            "required": ["structural_issues", "missing_scenarios", "closure_gaps", "overall_assessment"]
        }
    }
]


def run_prd_review(prd_document: str, interview_notes: dict) -> dict:
    """
    运行 PRD 评审智能体。

    参数：
        prd_document    完整的 PRD Markdown 文档
        interview_notes 原始访谈笔记（用于对照检验）

    返回：
        结构化评审报告 dict
    """
    review_result = {}

    def handler(tool_name: str, tool_input: dict) -> str:
        if tool_name == "save_prd_review":
            review_result.update(tool_input)
            return json.dumps({"success": True})
        return json.dumps({"error": "unknown tool"})

    roles_summary = ", ".join(
        r.get("role", "") for r in interview_notes.get("user_roles", [])
    )
    requirements_summary = "\n".join(
        f"- [{r.get('priority')}] {r.get('feature')}"
        for r in interview_notes.get("requirements", [])
    )

    initial_msg = f"""请对以下 PRD 进行系统性评审。

## 背景信息（来自访谈笔记）
用户角色：{roles_summary}
核心需求：
{requirements_summary}

## 待评审 PRD

{prd_document}

---

请按五个评审维度逐一检查，完成后调用 save_prd_review 保存评审结果。
重点关注：空状态处理、异常流程、流程出口、多角色等待态。
""".strip()

    print("\n  [PRD评审智能体] 评审中...")

    run_agent(
        agent_name="prd_review",
        system_prompt=PRD_REVIEW_SYSTEM,
        tools=PRD_REVIEW_TOOLS,
        tool_handler=handler,
        initial_message=initial_msg,
        model=_get_model(),
        max_tokens=4096,
        temperature=0.1,
    )

    assessment = review_result.get("overall_assessment", {})
    critical = assessment.get("critical_count", 0)
    major = assessment.get("major_count", 0)
    minor = assessment.get("minor_count", 0)
    print(f"  [PRD评审智能体] 发现问题：{critical} 个 critical / {major} 个 major / {minor} 个 minor")

    return review_result


def format_review_report(review: dict) -> str:
    """将评审结果格式化为可读报告，用于 HITL 展示"""
    lines = []
    assessment = review.get("overall_assessment", {})

    lines.append(f"整体评价：{assessment.get('summary', '')}")
    lines.append(
        f"问题统计：Critical {assessment.get('critical_count', 0)} / "
        f"Major {assessment.get('major_count', 0)} / "
        f"Minor {assessment.get('minor_count', 0)}"
    )
    lines.append(
        f"是否可进入原型：{'✅ 是' if assessment.get('ready_for_prototype') else '⚠️  建议先修订 PRD'}"
    )

    structural = review.get("structural_issues", [])
    if structural:
        lines.append(f"\n── 结构问题（{len(structural)} 条）──")
        for item in structural:
            lines.append(
                f"  [{item['severity'].upper()}] {item['issue']}\n"
                f"    → {item['suggestion']}"
            )

    scenarios = review.get("missing_scenarios", [])
    if scenarios:
        lines.append(f"\n── 遗漏场景（{len(scenarios)} 条）──")
        for item in scenarios:
            lines.append(
                f"  [{item['severity'].upper()}] [{item['object']}] {item['scenario']}\n"
                f"    → {item['suggested_handling']}"
            )

    closures = review.get("closure_gaps", [])
    if closures:
        lines.append(f"\n── 闭环漏洞（{len(closures)} 条）──")
        for item in closures:
            lines.append(f"  [{item['severity'].upper()}] [{item['flow']}] {item['gap']}")

    multi_role = review.get("multi_role_gaps", [])
    if multi_role:
        lines.append(f"\n── 多角色协同问题（{len(multi_role)} 条）──")
        for item in multi_role:
            roles = " + ".join(item.get("roles_involved", []))
            lines.append(f"  [{item['severity'].upper()}] [{roles}] {item['gap']}")

    if assessment.get("recommendation"):
        lines.append(f"\n给原型 agent 的提示：\n  {assessment['recommendation']}")

    return "\n".join(lines)
