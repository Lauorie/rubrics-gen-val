"""Stage 1: initial rubric generation."""
from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import List

from rubrics.chunker import ChunkRecord
from rubrics.llm_client import LLMClient

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent / "templates"


def _load_text(rel: str) -> str:
    return (_TEMPLATE_DIR / rel).read_text(encoding="utf-8")


def _format_chunks(chunks: List[ChunkRecord]) -> str:
    if not chunks:
        return "（无可用领域上下文）"
    parts = []
    for i, c in enumerate(chunks, 1):
        loc = f"{c.doc_slug} p{c.page_start}-p{c.page_end}"
        parts.append(f"[chunk {i} | {loc}]\n{c.text}")
    return "\n\n".join(parts)


def _format_exemplars(question_type: str) -> str:
    """Pick gold exemplars: 1 of same type if available + 2 other diverse types."""
    raw = json.loads(_load_text("exemplars/gold_rubrics.json"))
    same = [r for r in raw if r["question_type"] == question_type]
    others = [r for r in raw if r["question_type"] != question_type]
    selection = same[:1] + others[: max(0, 3 - len(same[:1]))]
    blocks = []
    for ex in selection:
        blocks.append(
            f"### 示例（{ex['question_type']}）\n"
            f"题目：{ex['question']}\n"
            f"参考答案：{ex['reference_answer']}\n"
            f"对应 rubric：\n{json.dumps({'criteria': ex['criteria']}, ensure_ascii=False, indent=2)}"
        )
    return "\n\n".join(blocks)


def generate_initial_rubric(
    question: str, reference_answer: str, question_type: str, difficulty: str,
    source: str, retrieved_chunks: List[ChunkRecord], client: LLMClient,
) -> list:
    """Call LLM once with full prompt; return raw criteria list.

    Args:
        question: The exam question text.
        reference_answer: The reference answer for the question.
        question_type: Type of question (e.g. 简答题, 主观题).
        difficulty: Difficulty level of the question.
        source: Source document identifier.
        retrieved_chunks: Relevant document chunks for context.
        client: LLM client for making API calls.

    Returns:
        List of rubric criteria dicts.
    """
    system = _load_text("system_prompt.txt")
    type_rule = _load_text(f"type_rules/{question_type}.txt")
    exemplars = _format_exemplars(question_type)
    chunks_text = _format_chunks(retrieved_chunks)

    user = (
        f"[Q] {question}\n\n"
        f"[参考答案] {reference_answer}\n\n"
        f"[题型] {question_type}（请遵循该题型的 rubric 结构）\n"
        f"[难易程度] {difficulty}\n"
        f"[来源] {source}\n\n"
        f"[领域上下文 — 来自源文档]\n{chunks_text}\n\n"
        f"[题型规则]\n{type_rule}\n\n"
        f"[few-shot 示例]\n{exemplars}\n\n"
        f"请直接输出 JSON，不要任何前后缀。"
    )
    out = client.complete_json(system=system, user=user, schema_hint="criteria array")
    return out.get("criteria", [])
