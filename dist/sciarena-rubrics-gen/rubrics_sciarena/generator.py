"""Stage 1 (SciArena): initial rubric generation (English, citation-grounded)."""
from __future__ import annotations

import json
import logging
from typing import List, Tuple

from rubrics.llm_client import LLMClient
from rubrics_sciarena.lang import template_dir
from rubrics_sciarena.pseudo_chunk import format_citations_as_context
from rubrics_sciarena.schema import normalize_question_type

logger = logging.getLogger(__name__)

# Map normalized question types to their type-rule filename.
_TYPE_RULE_FILES = {
    "Methodology Inquiry": "methodology_inquiry.txt",
    "Conceptual Explanation": "conceptual_explanation.txt",
    "Challenges & Limitations": "challenges_limitations.txt",
    "State-of-the-Art Assessment": "state_of_the_art_assessment.txt",
    "Paper Finding": "paper_finding.txt",
    "Others": "others.txt",
}


def _load_text(rel: str, lang: str) -> str:
    return (template_dir(lang) / rel).read_text(encoding="utf-8")


def type_rule_filename(question_type: str) -> str:
    """Return the type-rule filename for a (possibly unknown) question type."""
    return _TYPE_RULE_FILES[normalize_question_type(question_type)]


def _format_exemplars(question_type: str, lang: str) -> str:
    raw = json.loads(_load_text("exemplars/gold_rubrics.json", lang))
    same = [r for r in raw if r["question_type"] == question_type]
    others = [r for r in raw if r["question_type"] != question_type]
    selection = same[:1] + others[: max(0, 2 - len(same[:1]))]
    lbl = _LABELS[lang]
    blocks = []
    for ex in selection:
        blocks.append(
            f"### {lbl['example']} ({ex['question_type']})\n"
            f"{lbl['question']}: {ex['question']}\n"
            f"{lbl['ref']}: {ex['reference_answer']}\n"
            f"{lbl['rubric']}:\n{json.dumps({'criteria': ex['criteria']}, ensure_ascii=False, indent=2)}"
        )
    return "\n\n".join(blocks)


# User-prompt scaffold labels per language. Criterion *text* is generated in the
# target language; these labels just structure the prompt.
_LABELS = {
    "en": {
        "example": "Example", "question": "Question", "ref": "Ground-truth answer",
        "rubric": "Rubric", "qtype": "Question type", "subject": "Subject",
        "context": "Cited sources — domain context", "rules": "Type rules",
        "fewshot": "Few-shot examples",
        "qtype_note": "(follow the rubric structure for this type)",
        "tail": "Output the JSON directly, with no prefix or suffix.",
    },
    "zh": {
        "example": "示例", "question": "问题", "ref": "标准答案",
        "rubric": "对应 rubric", "qtype": "题型", "subject": "学科",
        "context": "引用文献 — 领域上下文（英文）", "rules": "题型规则",
        "fewshot": "few-shot 示例",
        "qtype_note": "（请遵循该题型的 rubric 结构）",
        "tail": "请直接输出 JSON，不要任何前后缀。",
    },
}


def build_generation_prompt(
    question: str, reference_answer: str, question_type: str, subject: str,
    citations: List[dict], *, lang: str = "en",
) -> Tuple[str, str]:
    """Assemble the (system, user) prompt for Stage-1 generation.

    Args:
        question: The research question.
        reference_answer: The ground-truth (winning) response.
        question_type: SciArena question type (normalized internally).
        subject: SciArena subject tag.
        citations: GT citations used as domain context.
        lang: Language code selecting the template set and prompt labels.

    Returns:
        ``(system_prompt, user_prompt)``.
    """
    lbl = _LABELS[lang]
    system = _load_text("system_prompt.txt", lang)
    type_rule = _load_text(f"type_rules/{type_rule_filename(question_type)}", lang)
    exemplars = _format_exemplars(normalize_question_type(question_type), lang)
    context = format_citations_as_context(citations)

    user = (
        f"[{lbl['question']}] {question}\n\n"
        f"[{lbl['ref']}] {reference_answer}\n\n"
        f"[{lbl['qtype']}] {question_type} {lbl['qtype_note']}\n"
        f"[{lbl['subject']}] {subject}\n\n"
        f"[{lbl['context']}]\n{context}\n\n"
        f"[{lbl['rules']}]\n{type_rule}\n\n"
        f"[{lbl['fewshot']}]\n{exemplars}\n\n"
        f"{lbl['tail']}"
    )
    return system, user


async def generate_initial_rubric_async(
    question: str, reference_answer: str, question_type: str, subject: str,
    citations: List[dict], client: LLMClient, *, lang: str = "en",
) -> list:
    """Call the LLM once and return the raw criteria list."""
    system, user = build_generation_prompt(
        question, reference_answer, question_type, subject, citations, lang=lang,
    )
    out = await client.complete_json_async(system=system, user=user, schema_hint="criteria array")
    return out.get("criteria", [])
