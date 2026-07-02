"""Tests for src/rubrics_diff_report.py — pure markdown rendering, no LLM."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rlm_pipeline"))

from rubrics_diff_report import render_diff


def _result(
    item_idx: int, score: float, anchored: float | None = None,
    question_type: str = "主观题", difficulty: str = "中等",
    pitfalls: list[tuple[str, bool]] | None = None,
    positives: list[tuple[str, str, bool]] | None = None,
) -> dict[str, Any]:
    """Build a synthetic scorer result. pitfalls = [(text, triggered)],
    positives = [(criterion_type, text, met)]."""
    breakdown: list[dict[str, Any]] = []
    for text, met in (pitfalls or []):
        breakdown.append({
            "id": f"p_{text[:5]}", "text": text, "category": "Pitfall",
            "weight": 3, "sign": "negative", "criterion_type": "anti_hacking",
            "met": met, "reason": "", "contribution": 0,
        })
    for ct, text, met in (positives or []):
        breakdown.append({
            "id": f"c_{text[:5]}", "text": text, "category": "Essential",
            "weight": 5, "sign": "positive", "criterion_type": ct,
            "met": met, "reason": "", "contribution": 0,
        })
    return {
        "item_idx": item_idx,
        "question_id": str(item_idx + 1),
        "question_type": question_type,
        "difficulty": difficulty,
        "score": score,
        "score_anchored": (
            None if anchored is None
            else {"ref_score": 1.0, "weak_score": 0.0, "normalized": anchored}
        ),
        "breakdown": breakdown,
        "judge_model": "openai/gpt-5.5",
        "scored_at": "t",
    }


def _meta() -> dict[str, str]:
    return {"scores_v1_path": "v1.json", "scores_v2_path": "v2.json",
            "generated_at": "2026-05-25T00:00:00+00:00"}


def test_header_includes_paths_and_count() -> None:
    v1 = [_result(0, 0.5, anchored=0.5)]
    v2 = [_result(0, 0.7, anchored=0.7)]
    md = render_diff(v1, v2, rubrics=[{"item_idx": 0, "question": "Q"}], meta=_meta())
    assert "v1.json" in md and "v2.json" in md
    assert "2026-05-25" in md
    assert "共 1 项" in md


def test_overall_delta_signs_and_values() -> None:
    v1 = [_result(0, 0.5, anchored=0.5), _result(1, 0.5, anchored=0.5)]
    v2 = [_result(0, 0.7, anchored=0.7), _result(1, 0.7, anchored=0.7)]
    md = render_diff(v1, v2, rubrics=[{"item_idx": 0, "question": "Q0"},
                                       {"item_idx": 1, "question": "Q1"}], meta=_meta())
    assert "## 1. 总体得分对比" in md
    assert "0.50" in md
    assert "0.70" in md
    assert "+0.20" in md


def test_pitfall_trip_delta_per_text() -> None:
    v1 = [_result(0, 0.5, pitfalls=[("套话开场", True), ("冗长", True)])]
    v2 = [_result(0, 0.5, pitfalls=[("套话开场", False), ("冗长", True)])]
    md = render_diff(v1, v2, rubrics=[{"item_idx": 0, "question": "Q"}], meta=_meta())
    sec = md.split("## 2. Pitfall 触发对比")[1].split("## 3.")[0]
    assert "套话开场" in sec
    assert "-1" in sec or "−1" in sec
    assert "冗长" in sec


def test_by_criterion_type_delta_excludes_anti_hacking_or_separates() -> None:
    v1 = [_result(0, 0.5, positives=[("factual_anchor", "f1", False),
                                      ("mechanism_explanation", "m1", False)])]
    v2 = [_result(0, 0.5, positives=[("factual_anchor", "f1", True),
                                      ("mechanism_explanation", "m1", True)])]
    md = render_diff(v1, v2, rubrics=[{"item_idx": 0, "question": "Q"}], meta=_meta())
    sec = md.split("## 3. 按 criterion_type 命中率对比")[1].split("## 4.")[0]
    assert "factual_anchor" in sec
    assert "mechanism_explanation" in sec
    assert "+100" in sec or "100.0" in sec


def test_by_question_type_delta() -> None:
    v1 = [_result(0, 0.5, anchored=0.5, question_type="主观题"),
          _result(1, 0.8, anchored=0.8, question_type="客观题")]
    v2 = [_result(0, 0.7, anchored=0.7, question_type="主观题"),
          _result(1, 0.8, anchored=0.8, question_type="客观题")]
    md = render_diff(v1, v2, rubrics=[{"item_idx": 0, "question": "Q0"},
                                       {"item_idx": 1, "question": "Q1"}], meta=_meta())
    sec = md.split("## 4. 按题型分组对比")[1].split("## 5.")[0]
    assert "主观题" in sec and "客观题" in sec
    assert "+0.20" in sec


def test_top_winners_ordered_by_anchored_delta_desc() -> None:
    v1 = [_result(0, 0.5, anchored=0.5), _result(1, 0.5, anchored=0.5),
          _result(2, 0.5, anchored=0.5)]
    v2 = [_result(0, 0.6, anchored=0.6),
          _result(1, 0.9, anchored=0.9),
          _result(2, 0.7, anchored=0.7)]
    rubrics = [{"item_idx": i, "question": f"Q{i}"} for i in range(3)]
    md = render_diff(v1, v2, rubrics=rubrics, meta=_meta(), top_n=3)
    sec = md.split("## 5. Top winners")[1].split("## 6.")[0]
    assert sec.find("item_idx=1") < sec.find("item_idx=2")
    assert sec.find("item_idx=2") < sec.find("item_idx=0")


def test_top_losers_ordered_by_anchored_delta_asc() -> None:
    v1 = [_result(0, 0.5, anchored=0.5), _result(1, 0.5, anchored=0.5)]
    v2 = [_result(0, 0.4, anchored=0.4),
          _result(1, 0.1, anchored=0.1)]
    rubrics = [{"item_idx": i, "question": f"Q{i}"} for i in range(2)]
    md = render_diff(v1, v2, rubrics=rubrics, meta=_meta(), top_n=2)
    sec = md.split("## 6. Top losers")[1]
    assert sec.find("item_idx=1") < sec.find("item_idx=0")


def test_losers_include_flipped_criteria() -> None:
    v1 = [_result(0, 0.8, anchored=0.8,
                  positives=[("factual_anchor", "must mention X", True),
                             ("mechanism_explanation", "must explain Y", True)])]
    v2 = [_result(0, 0.2, anchored=0.2,
                  positives=[("factual_anchor", "must mention X", False),
                             ("mechanism_explanation", "must explain Y", True)])]
    rubrics = [{"item_idx": 0, "question": "Q-fail"}]
    md = render_diff(v1, v2, rubrics=rubrics, meta=_meta(), top_n=1)
    sec = md.split("## 6. Top losers")[1]
    assert "must mention X" in sec
    assert "Q-fail" in sec


def test_items_only_in_one_version_are_flagged_at_top() -> None:
    v1 = [_result(0, 0.5, anchored=0.5), _result(1, 0.5, anchored=0.5)]
    v2 = [_result(0, 0.5, anchored=0.5)]
    rubrics = [{"item_idx": 0, "question": "Q0"}, {"item_idx": 1, "question": "Q1"}]
    md = render_diff(v1, v2, rubrics=rubrics, meta=_meta())
    assert "在 v1 但不在 v2" in md or "in v1 but not v2" in md
    assert "1" in md


def test_render_diff_does_not_mutate_inputs() -> None:
    v1 = [_result(0, 0.5, anchored=0.5)]
    v2 = [_result(0, 0.7, anchored=0.7)]
    rubrics = [{"item_idx": 0, "question": "Q"}]
    snapshot = json.dumps([v1, v2, rubrics], default=str)
    render_diff(v1, v2, rubrics=rubrics, meta=_meta())
    assert json.dumps([v1, v2, rubrics], default=str) == snapshot
