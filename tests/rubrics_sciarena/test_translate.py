"""Tests for translating a cleaned record's question + GT answer to Chinese."""
from __future__ import annotations

import asyncio

from rubrics_sciarena.translate import translate_record_to_zh


def _record():
    return {
        "id": "rec-1",
        "question": "What are the limitations of RLHF?",
        "question_type": "Challenges & Limitations",
        "subject": "Computer Science",
        "vote": "A",
        "gt_source": "A",
        "reference_answer": "RLHF is limited by data cost and reward hacking.",
        "citations": [{"content": "English citation content.", "title": "Paper", "id": "1@1"}],
        "model": "Llama-4",
    }


async def _fake_translate(client, question, answer):
    return {"question": "RLHF 有哪些局限？", "answer": "RLHF 受限于数据成本和奖励作弊。"}


def _run(coro):
    return asyncio.run(coro)


def test_translates_question_and_answer():
    out = _run(translate_record_to_zh(_record(), client=None, translate_fn=_fake_translate))
    assert out["question"] == "RLHF 有哪些局限？"
    assert out["reference_answer"] == "RLHF 受限于数据成本和奖励作弊。"


def test_citations_remain_english():
    out = _run(translate_record_to_zh(_record(), client=None, translate_fn=_fake_translate))
    assert out["citations"] == [{"content": "English citation content.", "title": "Paper", "id": "1@1"}]


def test_preserves_metadata_fields():
    out = _run(translate_record_to_zh(_record(), client=None, translate_fn=_fake_translate))
    assert out["id"] == "rec-1"
    assert out["question_type"] == "Challenges & Limitations"
    assert out["subject"] == "Computer Science"
    assert out["vote"] == "A"
    assert out["gt_source"] == "A"
    assert out["model"] == "Llama-4"


def test_records_lang_zh_and_keeps_english_source():
    out = _run(translate_record_to_zh(_record(), client=None, translate_fn=_fake_translate))
    assert out["lang"] == "zh"
    # original English text preserved for traceability
    assert out["question_en"] == "What are the limitations of RLHF?"
    assert out["reference_answer_en"] == "RLHF is limited by data cost and reward hacking."
