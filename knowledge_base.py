"""
knowledge_base.py — 长期记忆模块

使用 Chroma 向量数据库存储和检索历史项目知识。
本地运行，无需任何云服务，数据存在 ./kb_data 目录。

依赖：pip install chromadb anthropic

数据结构：
  每个历史项目存储三类文档：
  1. project_summary  项目概览（用于搜索相似项目）
  2. lessons_learned  经验教训（用于提升访谈质量）
  3. requirements_patterns  需求规律（用于避免遗漏）
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional

try:
    import chromadb
    from chromadb.utils import embedding_functions
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False


# ─── 初始化 ────────────────────────────────────────────────
KB_DIR = Path(__file__).parent / "kb_data"
KB_DIR.mkdir(exist_ok=True)


def _get_client():
    """获取 Chroma 客户端（懒加载）"""
    if not CHROMA_AVAILABLE:
        raise ImportError(
            "请先安装 chromadb：pip install chromadb\n"
            "如暂不安装，知识库功能会降级为文件搜索模式。"
        )
    return chromadb.PersistentClient(path=str(KB_DIR))


def _get_collections():
    """获取三个集合"""
    client = _get_client()
    # 使用 Chroma 内置的轻量 embedding（无需 OpenAI Key）
    ef = embedding_functions.DefaultEmbeddingFunction()
    return {
        "summaries": client.get_or_create_collection(
            "project_summaries", embedding_function=ef
        ),
        "lessons": client.get_or_create_collection(
            "lessons_learned", embedding_function=ef
        ),
        "patterns": client.get_or_create_collection(
            "requirements_patterns", embedding_function=ef
        ),
    }


# ─── 写入：项目完成后调用 ──────────────────────────────────
def save_project(
    project_id: str,
    project_name: str,
    industry: str,
    project_type: str,
    interview_notes: dict,
    prd_document: str,
    lessons_learned: list[str],
    common_missed_requirements: list[str],
):
    """
    将项目知识存入向量数据库。
    在 main.py 的 run_layer_one 末尾调用。
    """
    cols = _get_collections()
    metadata = {
        "project_id": project_id,
        "project_name": project_name,
        "industry": industry,
        "project_type": project_type,
        "date": datetime.now().isoformat(),
    }

    # 1. 项目概览（供"搜索相似项目"使用）
    summary_text = f"""
项目名称：{project_name}
行业：{industry}
类型：{project_type}
用户角色：{", ".join(r["role"] for r in interview_notes.get("user_roles", []))}
核心痛点：{"; ".join(p["pain"] for p in interview_notes.get("pain_points", []))}
需求摘要：{interview_notes.get("summary", "")}
""".strip()

    cols["summaries"].upsert(
        ids=[project_id],
        documents=[summary_text],
        metadatas=[metadata],
    )

    # 2. 经验教训（供"提升访谈质量"使用）
    if lessons_learned:
        lessons_text = "\n".join(f"- {l}" for l in lessons_learned)
        cols["lessons"].upsert(
            ids=[f"{project_id}_lessons"],
            documents=[f"项目：{project_name}\n经验：\n{lessons_text}"],
            metadatas=[metadata],
        )

    # 3. 遗漏需求规律（供"避免需求遗漏"使用）
    if common_missed_requirements:
        patterns_text = "\n".join(f"- {r}" for r in common_missed_requirements)
        cols["patterns"].upsert(
            ids=[f"{project_id}_patterns"],
            documents=[f"项目：{project_name}\n容易遗漏的需求：\n{patterns_text}"],
            metadatas=[metadata],
        )

    # 同时保存 JSON 备份到文件
    backup_path = KB_DIR / f"{project_id}.json"
    backup_path.write_text(json.dumps({
        "project_id": project_id,
        "project_name": project_name,
        "industry": industry,
        "project_type": project_type,
        "interview_notes": interview_notes,
        "lessons_learned": lessons_learned,
        "common_missed_requirements": common_missed_requirements,
        "date": metadata["date"],
    }, ensure_ascii=False, indent=2))

    print(f"  [知识库] 已保存项目：{project_name}")


# ─── 读取：新项目开始前调用 ───────────────────────────────
def search_similar_projects(query: str, n_results: int = 3) -> list[dict]:
    """
    语义搜索相似历史项目。
    返回结果注入到调研智能体的 System Prompt 里。
    """
    if not CHROMA_AVAILABLE:
        return _fallback_file_search(query, n_results)

    cols = _get_collections()

    # 搜索相似项目
    summary_results = cols["summaries"].query(
        query_texts=[query], n_results=min(n_results, 3)
    )
    lesson_results = cols["lessons"].query(
        query_texts=[query], n_results=min(n_results, 3)
    )
    pattern_results = cols["patterns"].query(
        query_texts=[query], n_results=min(n_results, 2)
    )

    results = []

    # 组合相似项目
    for doc, meta, distance in zip(
        summary_results["documents"][0],
        summary_results["metadatas"][0],
        summary_results["distances"][0],
    ):
        relevance = round(1 - distance, 2)
        if relevance < 0.3:  # 相关度太低就跳过
            continue
        results.append({
            "type": "similar_project",
            "project_name": meta["project_name"],
            "relevance": relevance,
            "summary": doc,
        })

    # 相关经验教训
    lessons = []
    for doc, meta in zip(
        lesson_results["documents"][0],
        lesson_results["metadatas"][0],
    ):
        lessons.append({
            "project": meta["project_name"],
            "content": doc,
        })

    # 容易遗漏的需求
    patterns = []
    for doc, meta in zip(
        pattern_results["documents"][0],
        pattern_results["metadatas"][0],
    ):
        patterns.append({
            "project": meta["project_name"],
            "content": doc,
        })

    return {
        "similar_projects": results,
        "lessons_learned": lessons,
        "requirement_patterns": patterns,
        "total_projects_in_kb": cols["summaries"].count(),
    }


def _fallback_file_search(query: str, n_results: int) -> dict:
    """
    Chroma 未安装时的降级方案：直接读取 JSON 备份文件。
    不做语义搜索，只返回最近的几个项目。
    """
    files = sorted(KB_DIR.glob("*.json"), key=os.path.getmtime, reverse=True)
    results = []
    for f in files[:n_results]:
        try:
            data = json.loads(f.read_text())
            results.append({
                "type": "similar_project",
                "project_name": data.get("project_name", ""),
                "relevance": 0.5,
                "summary": data.get("interview_notes", {}).get("summary", ""),
            })
        except Exception:
            continue
    return {
        "similar_projects": results,
        "lessons_learned": [],
        "requirement_patterns": [],
        "total_projects_in_kb": len(files),
        "note": "chromadb 未安装，使用文件搜索降级模式",
    }


def get_stats() -> dict:
    """返回知识库统计信息"""
    if not CHROMA_AVAILABLE:
        files = list(KB_DIR.glob("*.json"))
        return {"total_projects": len(files), "mode": "file_fallback"}
    cols = _get_collections()
    return {
        "total_projects": cols["summaries"].count(),
        "total_lessons": cols["lessons"].count(),
        "total_patterns": cols["patterns"].count(),
        "mode": "chroma_vector_db",
        "storage_path": str(KB_DIR),
    }
