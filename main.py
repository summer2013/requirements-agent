"""
main.py — 第一层编排器入口

运行方式：
    python main.py --project-name "供应链可视化平台" --brief "项目背景描述..."
    python main.py --interactive   # 交互模式，逐步输入
"""

import argparse
import json
import os
from pathlib import Path
from datetime import datetime

from agent import run_agent
from tools.definitions import RESEARCH_TOOLS, DOCUMENT_TOOLS, PROTOTYPE_TOOLS
from tool_handlers import make_research_handler, make_document_handler, make_prototype_handler
from review_agent import run_review
from knowledge_base import save_project, get_stats


def load_prompt(name: str) -> str:
    path = Path(__file__).parent / "prompts" / "api" / f"{name}_system.txt"
    return path.read_text(encoding="utf-8")


def check_env():
    """启动检查：确认 API Key 已配置"""
    has_anthropic  = bool(os.environ.get("ANTHROPIC_API_KEY"))
    has_openrouter = bool(os.environ.get("OPENROUTER_API_KEY"))
    if not has_anthropic and not has_openrouter:
        print("错误：请先配置 API Key。")
        print("参考 .env.example 文件，配置 ANTHROPIC_API_KEY 或 OPENROUTER_API_KEY。")
        return False
    provider = "OpenRouter" if has_openrouter else "Anthropic"
    print(f"[启动] 使用 {provider} API")
    return True


def hitl_check(title: str, summary: str, data: dict = None) -> tuple[bool, str]:
    """
    人工检查点。
    返回 (approved, feedback)
    """
    print(f"\n{'='*60}")
    print(f"人工检查点：{title}")
    print(f"{'='*60}")
    print(summary)
    if data:
        print("\n详细数据：")
        print(json.dumps(data, ensure_ascii=False, indent=2)[:800] + "...")

    while True:
        choice = input("\n[通过(y) / 需要修订(n)] > ").strip().lower()
        if choice in ("y", "yes", "通过", ""):
            return True, ""
        elif choice in ("n", "no", "修订"):
            feedback = input("请输入修订意见 > ").strip()
            if feedback:
                return False, feedback
            print("修订意见不能为空，请重新输入。")


def run_layer_one(project_name: str, project_brief: str, output_dir: str = "outputs"):
    """运行第一层：需求调研 → PRD → 原型"""

    if not check_env():
        return

    # 模型配置：OpenRouter 需要加 "anthropic/" 前缀
    use_openrouter = bool(os.environ.get("OPENROUTER_API_KEY"))
    MODEL_STRONG = "anthropic/claude-opus-4-5"   if use_openrouter else "claude-opus-4-5"
    MODEL_FAST   = "anthropic/claude-sonnet-4-6" if use_openrouter else "claude-sonnet-4-6"

    # 创建输出目录
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    project_dir = Path(output_dir) / f"{project_name}_{ts}"
    project_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n输出目录：{project_dir}")

    # 共享状态
    state = {
        "project_name": project_name,
        "project_brief": project_brief,
        "interview_notes": None,
        "prd_document": None,
        "prototype_html": None,
    }

    # ── 阶段 1：需求调研 ────────────────────────────────────
    print("\n▶ 阶段 1/3：需求调研")
    research_history = []
    max_revisions = 3

    for attempt in range(max_revisions):
        handler = make_research_handler(state)
        _, research_history = run_agent(
            agent_name="research",
            system_prompt=load_prompt("research"),
            tools=RESEARCH_TOOLS,
            tool_handler=handler,
            initial_message=f"项目名称：{project_name}\n\n项目简介：{project_brief}\n\n请开始需求调研访谈。",
            history=research_history if attempt > 0 else [],
            model=MODEL_STRONG,
            temperature=0.3,
        )

        notes = state.get("interview_notes")
        approved, feedback = hitl_check(
            "访谈笔记确认",
            f"识别角色：{len(notes.get('user_roles', []))} 个\n"
            f"痛点：{len(notes.get('pain_points', []))} 个\n"
            f"需求：{len(notes.get('requirements', []))} 条\n"
            f"置信度：{notes.get('confidence_level', '?')}",
            notes,
        )

        if approved:
            # 保存访谈笔记
            notes_path = project_dir / "interview_notes.json"
            notes_path.write_text(json.dumps(notes, ensure_ascii=False, indent=2))
            print(f"✓ 访谈笔记已保存：{notes_path}")
            break
        else:
            research_history.append({
                "role": "user",
                "content": f"请根据以下意见补充访谈内容：{feedback}"
            })
    else:
        print("✗ 访谈阶段达到最大修订次数，请人工介入。")
        return

    # ── 阶段 2：PRD 文档 ────────────────────────────────────
    print("\n▶ 阶段 2/3：生成 PRD")
    document_history = []

    for attempt in range(max_revisions):
        handler = make_document_handler(state)
        _, document_history = run_agent(
            agent_name="document",
            system_prompt=load_prompt("document"),
            tools=DOCUMENT_TOOLS,
            tool_handler=handler,
            initial_message="请读取访谈笔记并生成完整的 PRD 文档。",
            history=document_history if attempt > 0 else [],
            model=MODEL_FAST,
            max_tokens=8192,
            temperature=0.1,
        )

        prd = state.get("prd_document", "")
        approved, feedback = hitl_check(
            "PRD 评审",
            f"文档长度：{len(prd)} 字\n前 300 字预览：\n{prd[:300]}...",
        )

        if approved:
            prd_path = project_dir / "prd.md"
            prd_path.write_text(prd, encoding="utf-8")
            print(f"✓ PRD 已保存：{prd_path}")
            break
        else:
            document_history.append({
                "role": "user",
                "content": f"请根据以下意见修订 PRD：{feedback}"
            })
    else:
        print("✗ PRD 阶段达到最大修订次数，请人工介入。")
        return

    # ── 阶段 3：HTML 原型 ───────────────────────────────────
    print("\n▶ 阶段 3/3：生成 HTML 原型")
    handler = make_prototype_handler(state)
    run_agent(
        agent_name="prototype",
        system_prompt=load_prompt("prototype"),
        tools=PROTOTYPE_TOOLS,
        tool_handler=handler,
        initial_message="请读取 PRD 并生成完整的单文件 HTML 低保真原型。",
        model=MODEL_FAST,
        max_tokens=16384,
        temperature=0.2,
    )

    html = state.get("prototype_html", "")
    proto_path = project_dir / "prototype.html"
    proto_path.write_text(html, encoding="utf-8")
    print(f"✓ 原型已保存：{proto_path}")

    # ── 阶段 4：复盘 + 写入知识库 ──────────────────────────
    print("\n▶ 阶段 4/4：复盘 & 沉淀知识库")

    # 询问行业和项目类型（用于知识库分类）
    industry   = input("行业标签（例如：零售 / 医疗 / 教育，直接回车跳过）> ").strip() or "通用"
    proj_type  = input("项目类型（例如：内部工具 / SaaS / 移动App，直接回车跳过）> ").strip() or "B端系统"

    # 运行复盘智能体
    review = run_review(
        project_name=project_name,
        industry=industry,
        project_type=proj_type,
        interview_notes=state.get("interview_notes", {}),
        prd_document=state.get("prd_document", ""),
    )

    # 保存复盘结果到本地
    review_path = project_dir / "review.json"
    review_path.write_text(json.dumps(review, ensure_ascii=False, indent=2))
    print(f"✓ 复盘结果已保存：{review_path}")

    # 写入向量知识库
    save_project(
        project_id=ts,
        project_name=project_name,
        industry=industry,
        project_type=proj_type,
        interview_notes=state.get("interview_notes", {}),
        prd_document=state.get("prd_document", ""),
        lessons_learned=review.get("lessons_learned", []),
        common_missed_requirements=review.get("missed_requirements", []),
    )

    # 打印知识库统计
    stats = get_stats()
    print(f"  知识库当前共有 {stats['total_projects']} 个项目")

    # ── 完成 ────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"第一层完成！所有文件已保存到：{project_dir}")
    print(f"  - interview_notes.json  访谈笔记")
    print(f"  - prd.md                PRD 文档")
    print(f"  - prototype.html        可交互原型")
    print(f"  - review.json           复盘经验（已写入知识库）")
    print(f"{'='*60}")
    if review.get("lessons_learned"):
        print("\n本次提炼的经验：")
        for i, l in enumerate(review["lessons_learned"], 1):
            print(f"  {i}. {l}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="需求阶段智能体集群")
    parser.add_argument("--project-name", help="项目名称")
    parser.add_argument("--brief", help="项目简介")
    parser.add_argument("--interactive", action="store_true", help="交互模式")
    args = parser.parse_args()

    if args.interactive or not args.project_name:
        print("=== 需求阶段智能体集群 ===")
        name = input("项目名称 > ").strip()
        brief = input("项目简介（可多行，输入空行结束）>\n")
        lines = [brief]
        while True:
            line = input()
            if not line:
                break
            lines.append(line)
        brief = "\n".join(lines)
    else:
        name = args.project_name
        brief = args.brief

    run_layer_one(name, brief)
