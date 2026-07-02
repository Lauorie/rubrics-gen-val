"""Tests for src/rubrics_report.py — pure markdown rendering, no LLM."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rlm_pipeline"))

from rubrics_report import render_report


def _fake_breakdown(criterion_type: str, sign: str, met: bool, **extra) -> dict[str, Any]:
    base = {
        "id": extra.get("id", "c1"),
        "text": extra.get("text", "criterion text"),
        "category": extra.get("category", "Essential"),
        "weight": extra.get("weight", 5),
        "sign": sign,
        "criterion_type": criterion_type,
        "met": met,
        "reason": extra.get("reason", "rationale"),
        "contribution": (extra.get("weight", 5) if met else 0) * (1 if sign == "positive" else -1),
    }
    return base


def _fake_result(
    item_idx: int, score: float, anchored: float | None = None,
    question_type: str = "主观题", difficulty: str = "中等",
    question: str = "Q text", breakdown: list[dict] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    r: dict[str, Any] = {
        "item_idx": item_idx,
        "question_id": str(item_idx + 1),
        "question_type": question_type,
        "difficulty": difficulty,
        "candidate_answer": "A",
        "score": score if error is None else None,
        "score_anchored": (
            None if anchored is None
            else {"ref_score": 1.0, "weak_score": 0.0, "normalized": anchored}
        ),
        "breakdown": breakdown if breakdown is not None else [
            _fake_breakdown("factual_anchor", "positive", True),
        ],
        "judge_model": "openai/gpt-5.5",
        "scored_at": "2026-05-25T00:00:00+00:00",
        "_question_text": question,
    }
    if error:
        r["error"] = error
    return r


def _fake_aggregate(results: list[dict]) -> dict[str, Any]:
    ok = [r for r in results if r.get("score") is not None]
    raws = [r["score"] for r in ok]
    anchored = [
        r["score_anchored"]["normalized"]
        for r in ok if r.get("score_anchored") and r["score_anchored"].get("normalized") is not None
    ]
    from collections import defaultdict
    by_qt, by_diff = defaultdict(list), defaultdict(list)
    by_qt_n, by_diff_n = defaultdict(list), defaultdict(list)
    crit: dict[str, list[bool]] = defaultdict(list)
    for r in ok:
        by_qt[r["question_type"]].append(r["score"])
        by_diff[r["difficulty"]].append(r["score"])
        if r.get("score_anchored") and r["score_anchored"].get("normalized") is not None:
            by_qt_n[r["question_type"]].append(r["score_anchored"]["normalized"])
            by_diff_n[r["difficulty"]].append(r["score_anchored"]["normalized"])
        for b in r["breakdown"]:
            crit[b["criterion_type"]].append(b["met"])
    mean = lambda xs: sum(xs) / len(xs) if xs else None
    return {
        "n_predictions": len(results),
        "n_scored_ok": len(ok),
        "n_errors": len(results) - len(ok),
        "mean_score": mean(raws),
        "mean_anchored": mean(anchored),
        "by_question_type": {
            qt: {"n": len(s), "mean": mean(s), "mean_anchored": mean(by_qt_n.get(qt, []))}
            for qt, s in by_qt.items()
        },
        "by_difficulty": {
            d: {"n": len(s), "mean": mean(s), "mean_anchored": mean(by_diff_n.get(d, []))}
            for d, s in by_diff.items()
        },
        "by_criterion_type": {
            ct: {"n_criteria": len(m), "met_rate": sum(m) / len(m) if m else 0.0}
            for ct, m in crit.items()
        },
    }


def test_header_contains_models_and_counts() -> None:
    results = [_fake_result(0, 0.8, anchored=0.8)]
    md = render_report(
        aggregate=_fake_aggregate(results),
        results=results,
        meta={"candidate_model": "deepseek/deepseek-v4-flash",
              "judge_model": "openai/gpt-5.5",
              "generated_at": "2026-05-25T01:23:45+00:00"},
        worst_n=10,
    )
    assert "deepseek/deepseek-v4-flash" in md
    assert "openai/gpt-5.5" in md
    assert "2026-05-25" in md
    assert "总样本" in md and "1" in md
    assert "成功" in md and "错误" in md


def test_overall_score_section_shows_mean_raw_and_anchored() -> None:
    results = [
        _fake_result(0, 0.6, anchored=0.6),
        _fake_result(1, 0.8, anchored=0.8),
    ]
    md = render_report(
        aggregate=_fake_aggregate(results),
        results=results,
        meta={"candidate_model": "M", "judge_model": "J", "generated_at": "T"},
        worst_n=10,
    )
    assert "## 1. 总体得分" in md
    assert "0.70" in md


def test_by_question_type_section_lists_each_type() -> None:
    results = [
        _fake_result(0, 0.5, anchored=0.5, question_type="主观题"),
        _fake_result(1, 0.9, anchored=0.9, question_type="客观题"),
    ]
    md = render_report(
        aggregate=_fake_aggregate(results),
        results=results,
        meta={"candidate_model": "M", "judge_model": "J", "generated_at": "T"},
        worst_n=10,
    )
    assert "## 2. 按题型分组" in md
    assert "主观题" in md
    assert "客观题" in md


def test_by_difficulty_section_lists_each_level() -> None:
    results = [
        _fake_result(0, 0.5, anchored=0.5, difficulty="简单"),
        _fake_result(1, 0.9, anchored=0.9, difficulty="困难"),
    ]
    md = render_report(
        aggregate=_fake_aggregate(results),
        results=results,
        meta={"candidate_model": "M", "judge_model": "J", "generated_at": "T"},
        worst_n=10,
    )
    assert "## 3. 按难度" in md
    assert "简单" in md and "困难" in md


def test_lost_points_excludes_anti_hacking_and_sorts_ascending() -> None:
    results = [
        _fake_result(0, 0.5, breakdown=[
            _fake_breakdown("factual_anchor", "positive", True),
            _fake_breakdown("mechanism_explanation", "positive", False),
            _fake_breakdown("anti_hacking", "negative", False),
        ]),
    ]
    md = render_report(
        aggregate=_fake_aggregate(results),
        results=results,
        meta={"candidate_model": "M", "judge_model": "J", "generated_at": "T"},
        worst_n=10,
    )
    assert "## 4. 失分点" in md
    sec4 = md.split("## 4. 失分点")[1].split("## 5.")[0]
    assert "mechanism_explanation" in sec4
    assert "factual_anchor" in sec4
    assert "anti_hacking" not in sec4
    assert sec4.find("mechanism_explanation") < sec4.find("factual_anchor")


def test_gained_points_section_sorts_descending() -> None:
    results = [
        _fake_result(0, 0.5, breakdown=[
            _fake_breakdown("factual_anchor", "positive", True),
            _fake_breakdown("mechanism_explanation", "positive", False),
        ]),
    ]
    md = render_report(
        aggregate=_fake_aggregate(results),
        results=results,
        meta={"candidate_model": "M", "judge_model": "J", "generated_at": "T"},
        worst_n=10,
    )
    sec5 = md.split("## 5. 得分点")[1].split("## 6.")[0]
    assert sec5.find("factual_anchor") < sec5.find("mechanism_explanation")


def test_pitfall_section_only_lists_anti_hacking() -> None:
    results = [
        _fake_result(0, 0.5, breakdown=[
            _fake_breakdown("anti_hacking", "negative", True, id="p1", text="陷阱1"),
            _fake_breakdown("anti_hacking", "negative", False, id="p2", text="陷阱2"),
            _fake_breakdown("factual_anchor", "positive", True),
        ]),
    ]
    md = render_report(
        aggregate=_fake_aggregate(results),
        results=results,
        meta={"candidate_model": "M", "judge_model": "J", "generated_at": "T"},
        worst_n=10,
    )
    sec6 = md.split("## 6. Pitfall 触发分析")[1].split("## 7.")[0]
    assert "陷阱1" in sec6
    assert "factual_anchor" not in sec6


def test_worst_items_section_sorted_ascending_by_anchored() -> None:
    results = [
        _fake_result(0, 0.9, anchored=0.9, question="Q-high"),
        _fake_result(1, 0.2, anchored=0.2, question="Q-low"),
        _fake_result(2, 0.5, anchored=0.5, question="Q-mid"),
    ]
    md = render_report(
        aggregate=_fake_aggregate(results),
        results=results,
        meta={"candidate_model": "M", "judge_model": "J", "generated_at": "T"},
        worst_n=2,
    )
    sec7 = md.split("## 7. 最低分")[1]
    assert sec7.find("Q-low") < sec7.find("Q-mid")
    assert "Q-high" not in sec7


def test_worst_items_shows_met_unmet_with_reason() -> None:
    results = [
        _fake_result(0, 0.3, anchored=0.3, question="Q-fail",
                     breakdown=[
                         _fake_breakdown("factual_anchor", "positive", False,
                                         text="must mention X", reason="answer omitted X"),
                         _fake_breakdown("mechanism_explanation", "positive", True,
                                         text="explain Y", reason="answer covers Y"),
                     ]),
    ]
    md = render_report(
        aggregate=_fake_aggregate(results),
        results=results,
        meta={"candidate_model": "M", "judge_model": "J", "generated_at": "T"},
        worst_n=10,
    )
    sec7 = md.split("## 7. 最低分")[1]
    assert "❌" in sec7 and "✅" in sec7
    assert "answer omitted X" in sec7
    assert "answer covers Y" in sec7


def test_worst_items_uses_resolved_question_when_available() -> None:
    """Renderer accepts question text via results[i]['_question_text']."""
    results = [
        _fake_result(0, 0.1, anchored=0.1, question="Full question text here"),
    ]
    md = render_report(
        aggregate=_fake_aggregate(results),
        results=results,
        meta={"candidate_model": "M", "judge_model": "J", "generated_at": "T"},
        worst_n=10,
    )
    assert "Full question text here" in md


def test_handles_none_anchored_in_worst_section() -> None:
    """Items with anchored=None sort last in worst-N."""
    results = [
        _fake_result(0, 0.5, anchored=0.5, question="Q-anchored"),
        _fake_result(1, None, anchored=None, question="Q-none", error="boom"),
    ]
    md = render_report(
        aggregate=_fake_aggregate(results),
        results=results,
        meta={"candidate_model": "M", "judge_model": "J", "generated_at": "T"},
        worst_n=10,
    )
    assert "## 7. 最低分" in md
