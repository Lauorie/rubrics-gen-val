"""Tests for the SciArena Stage-3 misalignment filter (async, injectable judge)."""
from __future__ import annotations

import asyncio

from rubrics_sciarena.misalignment_filter import WEAK_ANSWER, filter_misaligned


def _c(cid, category="Essential", sign="positive", ctype="factual_anchor"):
    return {"id": cid, "text": cid, "category": category, "weight": 5,
            "sign": sign, "criterion_type": ctype}


def _run(coro):
    return asyncio.run(coro)


def test_weak_answer_is_english():
    assert WEAK_ANSWER == "I don't know."


def test_keeps_criterion_met_on_ref_and_not_on_weak():
    async def fake_judge(client, question, candidate, criterion):
        # met on the real reference, not met on the weak answer
        return {"met": candidate != WEAK_ANSWER}

    kept, dropped = _run(filter_misaligned(
        "q", "REAL ANSWER", [_c("c1")], judge_client=None, judge_fn=fake_judge,
    ))
    assert dropped == 0
    assert [c["id"] for c in kept] == ["c1"]


def test_drops_criterion_not_met_on_reference():
    async def fake_judge(client, question, candidate, criterion):
        return {"met": False}  # never satisfied, even by the reference

    kept, dropped = _run(filter_misaligned(
        "q", "REAL", [_c("c1")], judge_client=None, judge_fn=fake_judge,
    ))
    assert dropped == 1
    assert kept == []


def test_drops_criterion_triggered_by_weak_answer():
    async def fake_judge(client, question, candidate, criterion):
        return {"met": True}  # satisfied by everything, including "I don't know."

    kept, dropped = _run(filter_misaligned(
        "q", "REAL", [_c("c1")], judge_client=None, judge_fn=fake_judge,
    ))
    assert dropped == 1
    assert kept == []


def test_pitfalls_are_kept_without_judging():
    calls = []

    async def fake_judge(client, question, candidate, criterion):
        calls.append(criterion["id"])
        return {"met": candidate != WEAK_ANSWER}

    pit = _c("p1", category="Pitfall", sign="negative", ctype="anti_hacking")
    kept, dropped = _run(filter_misaligned(
        "q", "REAL", [_c("c1"), pit], judge_client=None, judge_fn=fake_judge,
    ))
    assert dropped == 0
    assert {c["id"] for c in kept} == {"c1", "p1"}
    assert "p1" not in calls  # pitfall never sent to the judge
