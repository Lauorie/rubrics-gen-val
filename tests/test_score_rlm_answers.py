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


import sys as _sys

from score_rlm_answers import build_llm_client, merge_results


def test_build_llm_client_uses_passed_model(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.invalid/v1")
    client = build_llm_client(model="openai/gpt-5.5")
    assert client.cfg.model == "openai/gpt-5.5"
    assert client.cfg.api_key == "sk-test"
    assert client.cfg.base_url == "https://example.invalid/v1"


def test_build_llm_client_raises_without_api_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    import pytest as _pytest
    with _pytest.raises(KeyError):
        build_llm_client(model="openai/gpt-5.5")


def test_merge_results_dedupes_by_item_idx_last_wins() -> None:
    existing = [{"item_idx": 0, "score": 0.5}, {"item_idx": 1, "score": 0.4}]
    new = [{"item_idx": 0, "score": 0.9}, {"item_idx": 2, "score": 0.3}]
    out = merge_results(existing, new)
    by_idx = {r["item_idx"]: r["score"] for r in out}
    assert by_idx == {0: 0.9, 1: 0.4, 2: 0.3}
    assert sorted(r["item_idx"] for r in out) == [0, 1, 2]


def test_main_dry_run_renders_report_from_existing_scores(tmp_path, monkeypatch) -> None:
    """--dry-run: skip Scorer; render report using whatever's already in scores.json."""
    rubrics_path = tmp_path / "rubrics.json"
    rubrics_path.write_text(json.dumps([
        {"item_idx": 0, "question_id": "1", "question": "Q1", "rlm_answer": "A1",
         "question_type": "主观题", "difficulty": "中等",
         "criteria": [{"id": "c1", "text": "t1", "category": "Essential",
                       "weight": 5, "sign": "positive", "criterion_type": "factual_anchor",
                       "evidence_quote": None}]}
    ], ensure_ascii=False))
    anchors_path = tmp_path / "anchors.json"
    anchors_path.write_text(json.dumps({"0": {"ref_score": 1.0, "weak_score": 0.0}}))
    scores_path = tmp_path / "scores.json"
    scores_path.write_text(json.dumps([
        {"item_idx": 0, "question_id": "1", "question_type": "主观题",
         "difficulty": "中等", "candidate_answer": "A1", "score": 0.8,
         "score_anchored": {"ref_score": 1.0, "weak_score": 0.0, "normalized": 0.8},
         "breakdown": [{"id": "c1", "text": "t1", "category": "Essential",
                        "weight": 5, "sign": "positive", "criterion_type": "factual_anchor",
                        "met": True, "reason": "ok", "contribution": 5}],
         "judge_model": "j", "scored_at": "t"}
    ]))
    report_path = tmp_path / "report.md"

    monkeypatch.setattr(_sys, "argv", [
        "score_rlm_answers.py",
        "--input", str(rubrics_path),
        "--anchors", str(anchors_path),
        "--scores-out", str(scores_path),
        "--report-out", str(report_path),
        "--dry-run",
    ])
    from score_rlm_answers import main
    assert main() == 0
    md = report_path.read_text()
    assert "# CAE-v2.0-1 RLM Scoring Report" in md
    assert "## 7. 最低分" in md
    assert "Q1" in md  # question text appears in worst-N


def test_main_invokes_scorer_for_pending_items(tmp_path, monkeypatch) -> None:
    """Confirm pending items are passed to Scorer.score_batch as {item_idx, answer}."""
    rubrics_path = tmp_path / "rubrics.json"
    rubrics_path.write_text(json.dumps([
        {"item_idx": 0, "question_id": "1", "question": "Q0", "rlm_answer": "A0",
         "question_type": "主观题", "difficulty": "中等", "criteria": []},
        {"item_idx": 1, "question_id": "2", "question": "Q1", "rlm_answer": "A1",
         "question_type": "主观题", "difficulty": "中等", "criteria": []},
    ], ensure_ascii=False))
    anchors_path = tmp_path / "anchors.json"
    anchors_path.write_text(json.dumps({}))
    scores_path = tmp_path / "scores.json"
    report_path = tmp_path / "report.md"

    captured: dict[str, Any] = {}

    class FakeScorer:
        def __init__(self, **kw):
            captured["init_kwargs"] = kw
        async def score_batch(self, predictions):
            captured["predictions"] = predictions
            return [
                {"item_idx": p["item_idx"], "question_id": str(p["item_idx"] + 1),
                 "question_type": "主观题", "difficulty": "中等",
                 "candidate_answer": p["answer"], "score": 0.5,
                 "score_anchored": None, "breakdown": [],
                 "judge_model": "fake", "scored_at": "t"}
                for p in predictions
            ]

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setattr(_sys, "argv", [
        "score_rlm_answers.py",
        "--input", str(rubrics_path),
        "--anchors", str(anchors_path),
        "--scores-out", str(scores_path),
        "--report-out", str(report_path),
    ])
    import score_rlm_answers as mod
    monkeypatch.setattr(mod, "Scorer", FakeScorer)
    assert mod.main() == 0
    preds = captured["predictions"]
    assert sorted(p["item_idx"] for p in preds) == [0, 1]
    assert {p["answer"] for p in preds} == {"A0", "A1"}
    saved = json.loads(scores_path.read_text())
    assert {r["item_idx"] for r in saved} == {0, 1}
    md = report_path.read_text()
    assert "# CAE-v2.0-1 RLM Scoring Report" in md
