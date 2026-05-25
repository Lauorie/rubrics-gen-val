"""Tests for src/score_rlm_answers.py — CLI + I/O wiring (no real LLM)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from score_rlm_answers import (
    load_scores,
    save_scores,
    filter_pending,
)


def test_load_scores_returns_empty_when_missing(tmp_path: Path) -> None:
    assert load_scores(tmp_path / "nope.json") == []


def test_load_scores_parses_json_array(tmp_path: Path) -> None:
    p = tmp_path / "s.json"
    p.write_text(json.dumps([{"item_idx": 0, "score": 0.5}], ensure_ascii=False))
    assert load_scores(p) == [{"item_idx": 0, "score": 0.5}]


def test_save_scores_atomic_chinese_safe(tmp_path: Path) -> None:
    p = tmp_path / "s.json"
    save_scores(p, [{"item_idx": 0, "score": 0.5, "candidate_answer": "答案"}])
    re = json.loads(p.read_text())
    assert re[0]["candidate_answer"] == "答案"
    assert not any(s.name.endswith(".tmp") for s in tmp_path.iterdir())


def test_filter_pending_skips_already_scored_ok(tmp_path: Path) -> None:
    rubrics = [{"item_idx": 0, "rlm_answer": "A0"},
               {"item_idx": 1, "rlm_answer": "A1"},
               {"item_idx": 2, "rlm_answer": "A2"}]
    existing = [{"item_idx": 0, "score": 0.5, "error": None}]
    todo = filter_pending(rubrics, existing)
    assert [t["item_idx"] for t in todo] == [1, 2]


def test_filter_pending_retries_errored_items(tmp_path: Path) -> None:
    rubrics = [{"item_idx": 0, "rlm_answer": "A0"},
               {"item_idx": 1, "rlm_answer": "A1"}]
    existing = [{"item_idx": 0, "score": None, "error": "boom"}]
    todo = filter_pending(rubrics, existing)
    assert [t["item_idx"] for t in todo] == [0, 1]


def test_filter_pending_skips_items_with_null_rlm_answer() -> None:
    rubrics = [{"item_idx": 0, "rlm_answer": None},
               {"item_idx": 1, "rlm_answer": "A1"}]
    todo = filter_pending(rubrics, [])
    assert [t["item_idx"] for t in todo] == [1]
