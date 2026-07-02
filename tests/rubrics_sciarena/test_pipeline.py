"""Tests for the SciArena rubric pipeline orchestration (no network)."""
from __future__ import annotations

import asyncio

from rubrics_sciarena.misalignment_filter import WEAK_ANSWER
from rubrics_sciarena.pipeline import build_rubric_for_item_sciarena
from rubrics_sciarena.schema import SciArenaRubricItem


def _record(qtype="Conceptual Explanation"):
    return {
        "id": "rec-1",
        "question": "Why does dropout help?",
        "question_type": qtype,
        "subject": "ML",
        "vote": "A",
        "gt_source": "A",
        "reference_answer": "Dropout reduces overfitting.",
        "citations": [{"content": "c", "title": "T", "id": "1@1"}],
        "model": "Llama-4",
    }


async def _fake_generate(question, reference_answer, question_type, subject, citations, client, *, lang="en"):
    return [
        {"text": "Identifies dropout reduces overfitting", "category": "Essential",
         "weight": 5, "sign": "positive", "criterion_type": "factual_anchor"},
        {"text": "Explains co-adaptation is broken", "category": "Important",
         "weight": 3, "sign": "positive", "criterion_type": "mechanism_explanation"},
    ]


async def _keep_all_judge(client, question, candidate, criterion):
    # met on reference, not met on the weak answer -> everything kept
    return {"met": candidate != WEAK_ANSWER}


def _build(record, **kw):
    return asyncio.run(build_rubric_for_item_sciarena(
        record, gen_client=None, judge_client=None,
        generate_fn=_fake_generate, judge_fn=_keep_all_judge, **kw,
    ))


def test_pipeline_returns_valid_rubric_item():
    item = _build(_record())
    assert isinstance(item, SciArenaRubricItem)
    assert item.id == "rec-1"
    assert item.gt_source == "A"
    assert item.question_type == "Conceptual Explanation"


def test_pipeline_injects_default_pitfalls():
    item = _build(_record())
    pitfalls = [c for c in item.criteria if c.category == "Pitfall"]
    assert len(pitfalls) == 2
    positives = [c for c in item.criteria if c.category != "Pitfall"]
    assert len(positives) == 2


def test_pipeline_metadata_counts():
    item = _build(_record())
    md = item.rubric_metadata
    assert md.n_criteria_initial == 2
    assert md.n_dropped_misaligned == 0
    assert md.n_criteria_final == len(item.criteria)  # 2 positives + 2 pitfalls
    assert md.generation_passes == 3


def test_pipeline_citation_grounding_from_record():
    item = _build(_record())
    assert item.citation_grounding.n_citations == 1
    assert item.citation_grounding.citation_ids == ["1@1"]


def test_pipeline_normalizes_unknown_question_type():
    item = _build(_record(qtype="Totally New Type"))
    assert item.question_type == "Others"
