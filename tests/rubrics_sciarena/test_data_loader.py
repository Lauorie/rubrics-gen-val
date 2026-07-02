"""Tests for SciArena data loading and GT selection."""
from __future__ import annotations

import random
from pathlib import Path

import pytest

from rubrics_sciarena.data_loader import iter_items, read_jsonl, select_gt, write_jsonl


def _mk_item(vote: str) -> dict:
    return {
        "id": "abc-123",
        "question": "What models assess thermal effects?",
        "responseA": "Answer A text.",
        "responseB": "Answer B text.",
        "modelA": "Llama-4",
        "modelB": "Grok-3",
        "vote": vote,
        "citations_a": [{"content": "cit A", "title": "Paper A", "id": "1@1"}],
        "citations_b": [{"content": "cit B", "title": "Paper B", "id": "2@2"}],
        "question type": "Conceptual Explanation",
        "subject": "Optics",
    }


def test_select_gt_vote_a_keeps_a_and_drops_b():
    rec = select_gt(_mk_item("A"), random.Random(42))
    assert rec["gt_source"] == "A"
    assert rec["reference_answer"] == "Answer A text."
    assert rec["citations"] == [{"content": "cit A", "title": "Paper A", "id": "1@1"}]
    assert rec["model"] == "Llama-4"
    # losing side must not leak through
    assert "responseB" not in rec
    assert "citations_b" not in rec


def test_select_gt_vote_b_keeps_b():
    rec = select_gt(_mk_item("B"), random.Random(42))
    assert rec["gt_source"] == "B"
    assert rec["reference_answer"] == "Answer B text."
    assert rec["citations"][0]["id"] == "2@2"
    assert rec["model"] == "Grok-3"


def test_select_gt_preserves_metadata():
    rec = select_gt(_mk_item("A"), random.Random(42))
    assert rec["id"] == "abc-123"
    assert rec["question"] == "What models assess thermal effects?"
    assert rec["question_type"] == "Conceptual Explanation"
    assert rec["subject"] == "Optics"
    assert rec["vote"] == "A"


def test_select_gt_tie_is_reproducible_with_seed():
    # Same seed -> same choice across runs.
    picks_run1 = [select_gt(_mk_item("Tie"), random.Random(7))["gt_source"] for _ in range(5)]
    picks_run2 = [select_gt(_mk_item("Tie"), random.Random(7))["gt_source"] for _ in range(5)]
    assert picks_run1 == picks_run2
    assert all(p in ("A", "B") for p in picks_run1)


def test_select_gt_accepts_lowercase_votes():
    # Real SciArena data mixes "A"/"B"/"Tie" with "a"/"b"/"tie".
    assert select_gt(_mk_item("a"), random.Random(1))["gt_source"] == "A"
    assert select_gt(_mk_item("b"), random.Random(1))["gt_source"] == "B"
    assert select_gt(_mk_item("tie"), random.Random(1))["gt_source"] in ("A", "B")


def test_select_gt_rejects_unknown_vote():
    with pytest.raises(ValueError):
        select_gt(_mk_item("maybe"), random.Random(1))


def test_select_gt_preserves_raw_vote_string():
    # The cleaned record normalizes vote to the canonical casing used downstream.
    assert select_gt(_mk_item("tie"), random.Random(1))["vote"] == "Tie"
    assert select_gt(_mk_item("a"), random.Random(1))["vote"] == "A"


def test_select_gt_tie_uses_matching_citations():
    rec = select_gt(_mk_item("Tie"), random.Random(7))
    if rec["gt_source"] == "A":
        assert rec["citations"][0]["id"] == "1@1"
    else:
        assert rec["citations"][0]["id"] == "2@2"


def test_iter_items_streams_nan_tolerant(tmp_path: Path):
    # Real SciArena data contains bare NaN (invalid JSON for strict parsers).
    payload = (
        '[\n'
        '  {"id": "x1", "vote": "A", "authors": NaN, "n": 1},\n'
        '  {"id": "x2", "vote": "B", "n": 2},\n'
        '  {"id": "x3", "vote": "Tie", "authors": NaN, "n": 3}\n'
        ']\n'
    )
    f = tmp_path / "mini.json"
    f.write_text(payload, encoding="utf-8")

    items = list(iter_items(f))
    assert [it["id"] for it in items] == ["x1", "x2", "x3"]
    assert [it["n"] for it in items] == [1, 2, 3]


def test_iter_items_empty_array(tmp_path: Path):
    f = tmp_path / "empty.json"
    f.write_text("[]", encoding="utf-8")
    assert list(iter_items(f)) == []


def test_jsonl_roundtrip_with_unicode_line_separators(tmp_path: Path):
    # Academic text contains raw U+2028 / U+2029 / U+0085 which json.dumps does
    # NOT escape; str.splitlines() would wrongly split a record on them.
    records = [
        {"id": "a", "text": "line one line two para", "n": 1},
        {"id": "b", "text": "nextnel", "n": 2},
        {"id": "c", "text": "plain", "n": 3},
    ]
    f = tmp_path / "out.jsonl"
    write_jsonl(records, f)
    loaded = read_jsonl(f)
    assert loaded == records
    assert len(loaded) == 3  # not split into more "lines"


def test_jsonl_skips_blank_lines(tmp_path: Path):
    f = tmp_path / "out.jsonl"
    f.write_text('{"id": "a"}\n\n{"id": "b"}\n', encoding="utf-8")
    assert read_jsonl(f) == [{"id": "a"}, {"id": "b"}]
