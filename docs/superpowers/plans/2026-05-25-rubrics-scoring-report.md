# Rubric Scoring + Summary Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Score 94 RLM-generated answers against per-item rubrics via `src/rubrics/Scorer` (gpt-5.5 judge), persist per-item results to `outputs/scoring/cae-v2.0-1-scores.json`, and emit a Chinese-language markdown report (`outputs/scoring/cae-v2.0-1-report.md`) covering aggregate scores, 失分点/得分点 patterns, pitfall trips, and worst-10 items.

**Architecture:** Thin CLI orchestrator (`src/score_rlm_answers.py`) that wires the existing async `Scorer` machinery in `src/rubrics/`. A separate pure-function module (`src/rubrics_report.py`) renders the markdown so tests can verify the report shape without any LLM calls. Resume = filter input by `item_idx` already in scores.json with `error=None` (mirrors the `generate_rlm_answers.py` pattern).

**Tech Stack:** Python 3.12, asyncio, `src/rubrics/{scorer,aggregate,llm_client}`, pytest. No new dependencies.

---

## File Structure

**Files to create:**
- `src/rubrics_report.py` (~150 lines) — pure-function markdown rendering. Inputs: aggregate dict + per-item results + meta dict + worst_n. Output: markdown string. No I/O, no LLM, easy to test.
- `src/score_rlm_answers.py` (~180 lines) — CLI + orchestration. Loads rubrics+anchors+scores, builds LLMClient + Scorer, runs scoring, writes scores + report.
- `tests/test_rubrics_report.py` (~150 lines, ~10 tests) — every report section rendered correctly from synthetic data.
- `tests/test_score_rlm_answers.py` (~200 lines, ~10 tests) — scores-JSON round-trip, resume filter, mocked Scorer end-to-end, CLI argparse.

**Files to read (not modify):**
- `src/rubrics/scorer.py` — `Scorer(rubrics, judge_client, concurrency, anchors).score_batch(predictions)`.
- `src/rubrics/aggregate.py` — `build_aggregate(results)`.
- `src/rubrics/llm_client.py` — `LLMConfig(api_key, base_url, model)` + `LLMClient(cfg)`.
- `data/CAE-v2.0-1-rubrics.json`, `data/CAE-anchor-scores.json` — input data.

---

## Key Interfaces (Reference)

`Scorer.score_one` returns:
```python
{
    "item_idx": int,
    "question_id": str | None,
    "question_type": str | None,
    "difficulty": str | None,
    "candidate_answer": str,
    "score": float | None,         # raw [0,1]
    "score_anchored": {             # or None if no anchor
        "ref_score": float,
        "weak_score": float,
        "normalized": float | None, # None if ref<=weak
    } | None,
    "breakdown": [
        {
            "id": str, "text": str, "category": str,
            "weight": int, "sign": "positive"|"negative",
            "criterion_type": str,
            "met": bool, "reason": str,
            "contribution": int,
            "error": str,           # only present if judge failed
        },
        ...
    ],
    "judge_model": str,
    "scored_at": str (ISO8601),
}
```

`Scorer.score_batch(predictions: list[{item_idx: int, answer: str}]) -> list[result_dict]`. Crash-isolated per item.

`aggregate.build_aggregate(results)` returns:
```python
{
    "n_predictions": int, "n_scored_ok": int, "n_errors": int,
    "mean_score": float | None,
    "mean_anchored": float | None,
    "by_question_type": {qt: {"n", "mean", "mean_anchored"}, ...},
    "by_difficulty": {d: {"n", "mean", "mean_anchored"}, ...},
    "by_criterion_type": {ct: {"n_criteria", "met_rate"}, ...},
}
```

---

## Task 1: Pure-function markdown renderer

**Files:**
- Create: `src/rubrics_report.py`
- Create: `tests/test_rubrics_report.py`

- [ ] **Step 1: Write failing tests covering all sections**

Create `tests/test_rubrics_report.py`:

```python
"""Tests for src/rubrics_report.py — pure markdown rendering, no LLM."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

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
        # synthetic question text for worst-10 section lookup
        "_question_text": question,
    }
    if error:
        r["error"] = error
    return r


def _fake_aggregate(results: list[dict]) -> dict[str, Any]:
    # Tiny aggregator that mimics the shape build_aggregate produces.
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
    assert "0.70" in md  # mean of 0.6 and 0.8


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
            _fake_breakdown("anti_hacking", "negative", False),  # must NOT appear in §4 / §5
        ]),
    ]
    md = render_report(
        aggregate=_fake_aggregate(results),
        results=results,
        meta={"candidate_model": "M", "judge_model": "J", "generated_at": "T"},
        worst_n=10,
    )
    assert "## 4. 失分点" in md
    # mechanism_explanation has met_rate 0.0; factual_anchor 1.0
    # Lost-points table sorts ascending → mechanism appears before factual.
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
    # met_rate 1.0 (factual_anchor) > 0.0 (mechanism_explanation) → factual first
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
    assert "Q-high" not in sec7  # only 2 worst


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
    # The errored item has score=None, must not crash; presence in worst section optional.
    assert "## 7. 最低分" in md
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/juli/RLM
.venv/bin/python -m pytest tests/test_rubrics_report.py -v
```
Expected: ImportError on `from rubrics_report import render_report`.

- [ ] **Step 3: Implement `src/rubrics_report.py`**

```python
"""Pure-function markdown rendering of rubric scoring results.

No I/O, no LLM. All inputs in, markdown string out. Designed for trivial
unit testing of every section.
"""
from __future__ import annotations

import logging
from typing import Any, Iterable

logger = logging.getLogger(__name__)

# criterion_types we treat as "positive" (gained/lost-points sections).
# anti_hacking has sign=negative and lives in the Pitfall section instead.
_PITFALL_CRITERION_TYPE = "anti_hacking"


def _fmt_float(x: float | None, digits: int = 2) -> str:
    if x is None:
        return "—"
    return f"{x:.{digits}f}"


def _fmt_pct(x: float | None) -> str:
    if x is None:
        return "—"
    return f"{x * 100:.1f}%"


def _anchored_for_sort(r: dict[str, Any]) -> float:
    """Return a sortable key for worst-N. None / missing → +inf so they sort last."""
    sa = r.get("score_anchored") or {}
    n = sa.get("normalized") if isinstance(sa, dict) else None
    if n is None:
        return float("inf")
    return float(n)


def _render_header(meta: dict[str, str], agg: dict[str, Any]) -> str:
    return (
        f"# CAE-v2.0-1 RLM Scoring Report\n"
        f"\n"
        f"- 候选模型: `{meta.get('candidate_model', '?')}`\n"
        f"- 评分模型: `{meta.get('judge_model', '?')}`\n"
        f"- 总样本: {agg.get('n_predictions', 0)} · 评分成功: {agg.get('n_scored_ok', 0)} · 错误: {agg.get('n_errors', 0)}\n"
        f"- 生成时间: {meta.get('generated_at', '?')}\n"
    )


def _render_overall(agg: dict[str, Any]) -> str:
    return (
        f"\n## 1. 总体得分\n\n"
        f"| 指标 | 数值 |\n"
        f"|---|---|\n"
        f"| 平均原始分 (raw) | {_fmt_float(agg.get('mean_score'))} |\n"
        f"| 平均锚定分 (anchored) | {_fmt_float(agg.get('mean_anchored'))} |\n"
    )


def _render_group_table(title: str, group_dict: dict[str, dict[str, Any]]) -> str:
    rows = [f"\n## {title}\n", "| 分组 | 数量 | mean (raw) | mean (anchored) |", "|---|---|---|---|"]
    for k, v in sorted(group_dict.items(), key=lambda kv: -(kv[1].get("n") or 0)):
        rows.append(
            f"| {k} | {v.get('n', 0)} | {_fmt_float(v.get('mean'))} | {_fmt_float(v.get('mean_anchored'))} |"
        )
    return "\n".join(rows) + "\n"


def _collect_criterion_breakdown(
    results: Iterable[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Walk every breakdown row; return {criterion_type: {total, met}}."""
    counter: dict[str, dict[str, int]] = {}
    for r in results:
        for b in r.get("breakdown") or []:
            ct = b["criterion_type"]
            slot = counter.setdefault(ct, {"total": 0, "met": 0})
            slot["total"] += 1
            if b["met"]:
                slot["met"] += 1
    out: dict[str, dict[str, Any]] = {}
    for ct, slot in counter.items():
        rate = slot["met"] / slot["total"] if slot["total"] else 0.0
        out[ct] = {"total": slot["total"], "met": slot["met"], "rate": rate}
    return out


def _render_lost_points(by_ct: dict[str, dict[str, Any]]) -> str:
    rows = [
        "\n## 4. 失分点 — criterion_type 命中率最低\n",
        "（仅 sign=positive，按命中率升序）\n",
        "| criterion_type | 总数 | 命中 | 命中率 |",
        "|---|---|---|---|",
    ]
    filtered = [(ct, v) for ct, v in by_ct.items() if ct != _PITFALL_CRITERION_TYPE]
    for ct, v in sorted(filtered, key=lambda kv: kv[1]["rate"]):
        rows.append(f"| {ct} | {v['total']} | {v['met']} | {_fmt_pct(v['rate'])} |")
    return "\n".join(rows) + "\n"


def _render_gained_points(by_ct: dict[str, dict[str, Any]]) -> str:
    rows = [
        "\n## 5. 得分点 — criterion_type 命中率最高\n",
        "（仅 sign=positive，按命中率降序）\n",
        "| criterion_type | 总数 | 命中 | 命中率 |",
        "|---|---|---|---|",
    ]
    filtered = [(ct, v) for ct, v in by_ct.items() if ct != _PITFALL_CRITERION_TYPE]
    for ct, v in sorted(filtered, key=lambda kv: -kv[1]["rate"]):
        rows.append(f"| {ct} | {v['total']} | {v['met']} | {_fmt_pct(v['rate'])} |")
    return "\n".join(rows) + "\n"


def _render_pitfalls(results: Iterable[dict[str, Any]], n_items: int) -> str:
    """Group every anti_hacking breakdown row by criterion text; count met=True (= triggered)."""
    by_text: dict[str, int] = {}
    for r in results:
        for b in r.get("breakdown") or []:
            if b["criterion_type"] != _PITFALL_CRITERION_TYPE:
                continue
            if b["met"]:
                by_text[b["text"]] = by_text.get(b["text"], 0) + 1
    rows = [
        "\n## 6. Pitfall 触发分析\n",
        "（仅 criterion_type=anti_hacking 且 met=True，按触发次数降序）\n",
        "| pitfall | 触发次数 | 占比 |",
        "|---|---|---|",
    ]
    if not by_text:
        rows.append("| _no pitfalls triggered_ | 0 | — |")
    else:
        denom = max(n_items, 1)
        for text, n in sorted(by_text.items(), key=lambda kv: -kv[1]):
            rows.append(f"| {text} | {n} | {_fmt_pct(n / denom)} |")
    return "\n".join(rows) + "\n"


def _render_worst_items(
    results: list[dict[str, Any]], worst_n: int,
) -> str:
    ranked = sorted(results, key=_anchored_for_sort)[:worst_n]
    out = [f"\n## 7. 最低分 {len(ranked)} 题\n"]
    for r in ranked:
        idx = r.get("item_idx")
        qid = r.get("question_id")
        sa = r.get("score_anchored") or {}
        norm = sa.get("normalized") if isinstance(sa, dict) else None
        raw = r.get("score")
        q = r.get("_question_text") or r.get("candidate_answer", "")[:0]
        head = (
            f"\n### #{idx} (question_id={qid}, anchored={_fmt_float(norm)}, raw={_fmt_float(raw)})\n"
        )
        out.append(head)
        if q:
            out.append(f"\n**问题**: {q}\n")
        if r.get("error"):
            out.append(f"\n_评分错误_: `{r['error']}`\n")
            continue
        out.append("")
        for b in r.get("breakdown") or []:
            mark = "✅" if b["met"] else "❌"
            out.append(
                f"- {mark} `{b['id']}` [{b['category']}, {b['criterion_type']}, w={b['weight']}, {b['sign']}] {b['text']}\n"
                f"    judge: {b.get('reason', '')}"
            )
    return "\n".join(out) + "\n"


def render_report(
    *,
    aggregate: dict[str, Any],
    results: list[dict[str, Any]],
    meta: dict[str, str],
    worst_n: int = 10,
) -> str:
    """Render the full markdown report.

    Args:
        aggregate: Output of rubrics.aggregate.build_aggregate.
        results: Per-item scorer outputs (each item may carry an extra
            ``_question_text`` key for the worst-N section; the scorer does
            not include it natively, so the CLI joins it in before rendering).
        meta: {candidate_model, judge_model, generated_at} strings.
        worst_n: How many worst items to drill into.

    Returns:
        Markdown string (UTF-8 safe).
    """
    by_ct = _collect_criterion_breakdown(results)
    parts = [
        _render_header(meta, aggregate),
        _render_overall(aggregate),
        _render_group_table("2. 按题型分组 (question_type)", aggregate.get("by_question_type", {})),
        _render_group_table("3. 按难度 (difficulty)", aggregate.get("by_difficulty", {})),
        _render_lost_points(by_ct),
        _render_gained_points(by_ct),
        _render_pitfalls(results, aggregate.get("n_predictions", 0)),
        _render_worst_items(results, worst_n),
    ]
    return "".join(parts)
```

- [ ] **Step 4: Run tests, expect all to pass**

```bash
.venv/bin/python -m pytest tests/test_rubrics_report.py -v
```
Expected: 11 passed.

- [ ] **Step 5: Commit**

```bash
git add src/rubrics_report.py tests/test_rubrics_report.py
git commit -m "feat(rubrics-report): pure-function markdown renderer for scoring report"
```

---

## Task 2: scores.json I/O + resume filter

**Files:**
- Create: `src/score_rlm_answers.py` (scaffolding only — load/save/filter)
- Create: `tests/test_score_rlm_answers.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_score_rlm_answers.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify failure**

```bash
.venv/bin/python -m pytest tests/test_score_rlm_answers.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement scaffold in `src/score_rlm_answers.py`**

```python
"""Score RLM answers in a rubrics JSON against per-item criteria.

Pipeline:
  1. Load rubrics+rlm_answer JSON (output of generate_rlm_answers.py).
  2. Load cached anchors (data/CAE-anchor-scores.json).
  3. Load existing scores.json (resume).
  4. For each pending item, call Scorer.score_batch (gpt-5.5 judge).
  5. Persist scores.json atomically.
  6. Render markdown report via rubrics_report.render_report.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def load_scores(path: Path) -> list[dict[str, Any]]:
    """Load a JSON array of per-item score records. Returns [] if missing."""
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"{path} is not a JSON array")
    return data


def save_scores(path: Path, scores: list[dict[str, Any]]) -> None:
    """Atomic JSON array write (tempfile + os.replace). UTF-8, 2-space indent."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp"
    ) as tmp:
        json.dump(scores, tmp, ensure_ascii=False, indent=2)
        tmp.write("\n")
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, path)


def filter_pending(
    rubrics: list[dict[str, Any]],
    existing_scores: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return the subset of rubrics that still need scoring.

    A rubric is pending if:
      - it has a non-null `rlm_answer`, AND
      - it does NOT already have a scored entry with `error is None`.
    """
    done: set[int] = {
        int(s["item_idx"])
        for s in existing_scores
        if s.get("error") is None and s.get("score") is not None
    }
    pending: list[dict[str, Any]] = []
    for r in rubrics:
        if r.get("rlm_answer") is None:
            logger.warning("item_idx=%s has no rlm_answer; skipping", r.get("item_idx"))
            continue
        if int(r["item_idx"]) in done:
            continue
        pending.append(r)
    return pending
```

- [ ] **Step 4: Run tests, expect 6 to pass**

```bash
.venv/bin/python -m pytest tests/test_score_rlm_answers.py -v
```
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/score_rlm_answers.py tests/test_score_rlm_answers.py
git commit -m "feat(rubrics-scoring): scores I/O + resume filter"
```

---

## Task 3: Scorer wiring + end-to-end main() (mocked LLM)

**Files:**
- Modify: `src/score_rlm_answers.py` — add `build_llm_client`, `score_all`, `merge_results`, `main`
- Modify: `tests/test_score_rlm_answers.py` — add tests for the new functions

- [ ] **Step 1: Write failing tests**

Append to `tests/test_score_rlm_answers.py`:

```python
import sys as _sys
from unittest.mock import AsyncMock, patch

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
```

- [ ] **Step 2: Run tests to verify failure**

```bash
.venv/bin/python -m pytest tests/test_score_rlm_answers.py -v
```
Expected: ImportError on `build_llm_client`, `merge_results`, `main`.

- [ ] **Step 3: Implement the wiring**

Append to `src/score_rlm_answers.py`:

```python
import argparse
import asyncio
import datetime as dt
import sys

_RLM_ROOT = Path(__file__).resolve().parents[1]
if str(_RLM_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_RLM_ROOT / "src"))

from rubrics.llm_client import LLMClient, LLMConfig  # noqa: E402
from rubrics.scorer import Scorer  # noqa: E402
from rubrics.aggregate import build_aggregate  # noqa: E402

import rubrics_report  # noqa: E402


def build_llm_client(*, model: str) -> LLMClient:
    """Construct an LLMClient using OPENAI_API_KEY/OPENAI_BASE_URL env vars."""
    cfg = LLMConfig(
        api_key=os.environ["OPENAI_API_KEY"],
        base_url=os.environ.get("OPENAI_BASE_URL", "https://aiberm.com/v1"),
        model=model,
    )
    return LLMClient(cfg)


def merge_results(
    existing: list[dict[str, Any]],
    new: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge new score results onto existing, keyed by item_idx (new wins)."""
    by_idx: dict[int, dict[str, Any]] = {int(r["item_idx"]): r for r in existing}
    for r in new:
        by_idx[int(r["item_idx"])] = r
    return [by_idx[k] for k in sorted(by_idx.keys())]


def _attach_question_text(
    results: list[dict[str, Any]],
    rubrics: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Add `_question_text` to each result by joining on item_idx (for worst-N section)."""
    qs = {int(r["item_idx"]): r.get("question", "") for r in rubrics}
    for r in results:
        r["_question_text"] = qs.get(int(r["item_idx"]), "")
    return results


async def _run_scoring(
    rubrics_by_idx: dict[int, dict[str, Any]],
    pending: list[dict[str, Any]],
    anchors_by_idx: dict[int, dict[str, float]],
    judge_client: LLMClient,
    concurrency: int,
) -> list[dict[str, Any]]:
    if not pending:
        logger.info("no pending items to score")
        return []
    scorer = Scorer(
        rubrics=rubrics_by_idx,
        judge_client=judge_client,
        concurrency=concurrency,
        anchors=anchors_by_idx,
    )
    predictions = [{"item_idx": int(r["item_idx"]), "answer": r["rlm_answer"]}
                   for r in pending]
    logger.info("scoring %d pending items", len(predictions))
    return await scorer.score_batch(predictions)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Score RLM answers against per-item rubrics; emit JSON + markdown report.",
    )
    parser.add_argument("--input", type=Path,
                        default=Path("/home/juli/RLM/data/CAE-v2.0-1-rubrics.json"))
    parser.add_argument("--anchors", type=Path,
                        default=Path("/home/juli/RLM/data/CAE-anchor-scores.json"))
    parser.add_argument("--scores-out", type=Path,
                        default=Path("/home/juli/RLM/outputs/scoring/cae-v2.0-1-scores.json"))
    parser.add_argument("--report-out", type=Path,
                        default=Path("/home/juli/RLM/outputs/scoring/cae-v2.0-1-report.md"))
    parser.add_argument("--judge-model", default="openai/gpt-5.5",
                        help="Judge model name (default: openai/gpt-5.5).")
    parser.add_argument("--concurrency", type=int, default=16)
    parser.add_argument("--worst-n", type=int, default=10)
    parser.add_argument("--dry-run", action="store_true",
                        help="Skip scoring; render report from existing scores.json only.")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    )

    rubrics = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(rubrics, list):
        raise ValueError(f"{args.input} is not a JSON array")
    rubrics_by_idx = {int(r["item_idx"]): r for r in rubrics}
    logger.info("loaded %d rubric items from %s", len(rubrics), args.input)

    anchors_raw = json.loads(args.anchors.read_text(encoding="utf-8")) if args.anchors.exists() else {}
    anchors_by_idx: dict[int, dict[str, float]] = {int(k): v for k, v in anchors_raw.items()}
    logger.info("loaded %d anchors from %s", len(anchors_by_idx), args.anchors)

    existing_scores = load_scores(args.scores_out)
    logger.info("loaded %d existing scores from %s", len(existing_scores), args.scores_out)

    if not args.dry_run:
        pending = filter_pending(rubrics, existing_scores)
        if pending:
            judge_client = build_llm_client(model=args.judge_model)
            new_results = asyncio.run(_run_scoring(
                rubrics_by_idx, pending, anchors_by_idx, judge_client, args.concurrency,
            ))
            merged = merge_results(existing_scores, new_results)
            save_scores(args.scores_out, merged)
            existing_scores = merged
        else:
            logger.info("nothing to score (resume covered everything)")

    results = _attach_question_text(existing_scores, rubrics)
    aggregate = build_aggregate(results)
    md = rubrics_report.render_report(
        aggregate=aggregate,
        results=results,
        meta={
            "candidate_model": "deepseek/deepseek-v4-flash",
            "judge_model": args.judge_model,
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        },
        worst_n=args.worst_n,
    )
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.write_text(md, encoding="utf-8")
    logger.info("wrote scores=%s report=%s (%d items scored ok, %d errors)",
                args.scores_out, args.report_out,
                aggregate.get("n_scored_ok", 0), aggregate.get("n_errors", 0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests, expect 11 to pass (6 from Task 2 + 5 new)**

```bash
.venv/bin/python -m pytest tests/test_score_rlm_answers.py -v
```
Expected: 11 passed.

- [ ] **Step 5: Lint check**

```bash
.venv/bin/python -c "import ast; ast.parse(open('src/score_rlm_answers.py').read())"
.venv/bin/python src/score_rlm_answers.py --help
```
Expected: no error; --help prints all flags.

- [ ] **Step 6: Commit**

```bash
git add src/score_rlm_answers.py tests/test_score_rlm_answers.py
git commit -m "feat(rubrics-scoring): CLI + Scorer wiring with dry-run + resume"
```

---

## Task 4: Dry-run end-to-end smoke

This is a sanity-check task using `--dry-run` so it makes ZERO LLM calls — just confirms the CLI wires the real data shapes end-to-end without crashing.

- [ ] **Step 1: Create an empty scores.json so --dry-run has something to read**

```bash
cd /home/juli/RLM
mkdir -p outputs/scoring
echo "[]" > outputs/scoring/cae-v2.0-1-scores.json
```

- [ ] **Step 2: Run --dry-run against the real rubrics + anchors**

```bash
.venv/bin/python src/score_rlm_answers.py --dry-run 2>&1 | tail -10
```

Expected: log shows `loaded 94 rubric items`, `loaded 94 anchors`, `loaded 0 existing scores`, and `wrote scores=... report=... (0 items scored ok, 0 errors)`. No traceback.

- [ ] **Step 3: Verify the report file exists and has all sections**

```bash
.venv/bin/python - <<'PY'
md = open("outputs/scoring/cae-v2.0-1-report.md").read()
print("len:", len(md))
for sec in ["# CAE-v2.0-1 RLM Scoring Report",
            "## 1. 总体得分",
            "## 2. 按题型分组",
            "## 3. 按难度",
            "## 4. 失分点",
            "## 5. 得分点",
            "## 6. Pitfall",
            "## 7. 最低分"]:
    print("FOUND" if sec in md else "MISSING", sec)
PY
```

Expected: all 8 sections marked FOUND. (Section 1 will show `mean=—` since no items scored, but the markdown structure is valid.)

- [ ] **Step 4: STOP and report to controller**

Report:
- Dry-run output line ("wrote scores=... report=... (0 scored, 0 errors)")
- Section-presence checklist
- Any unexpected warnings

Do NOT proceed to Task 5 until controller confirms the dry-run looks healthy.

---

## Task 5: Real run on all 94 items

**Pre-flight assumption:** Task 4 dry-run passed cleanly and controller approved.

- [ ] **Step 1: Source env and launch in background**

```bash
cd /home/juli/RLM
set -a && source papers_qa/.env && set +a
nohup .venv/bin/python src/score_rlm_answers.py \
    --input         data/CAE-v2.0-1-rubrics.json \
    --anchors       data/CAE-anchor-scores.json \
    --scores-out    outputs/scoring/cae-v2.0-1-scores.json \
    --report-out    outputs/scoring/cae-v2.0-1-report.md \
    --judge-model   openai/gpt-5.5 \
    --concurrency   16 \
    --worst-n       10 \
    > outputs/scoring/cae-v2.0-1.log 2>&1 &
echo "pid=$!" | tee outputs/scoring/cae-v2.0-1.pid
sleep 5
head -10 outputs/scoring/cae-v2.0-1.log
```

Expected: PID printed, log shows `loaded 94 rubric items`, `loaded 94 anchors`, `scoring 94 pending items`. ETA ~3 min.

- [ ] **Step 2: Wait for completion + verify**

```bash
# Watch until the "wrote scores=..." line appears or 10 min pass:
for _ in $(seq 1 60); do
    if grep -q "wrote scores=" outputs/scoring/cae-v2.0-1.log 2>/dev/null; then break; fi
    sleep 10
done
tail -5 outputs/scoring/cae-v2.0-1.log
```

Expected: final log line `wrote scores=outputs/scoring/cae-v2.0-1-scores.json report=outputs/scoring/cae-v2.0-1-report.md (94 items scored ok, 0 errors)`.

- [ ] **Step 3: Numerical sanity check on scores**

```bash
.venv/bin/python - <<'PY'
import json
import statistics as st
s = json.loads(open("outputs/scoring/cae-v2.0-1-scores.json").read())
ok = [r for r in s if r.get("score") is not None]
err = [r for r in s if r.get("score") is None]
print(f"total={len(s)}, ok={len(ok)}, err={len(err)}")

raw = [r["score"] for r in ok]
print(f"raw score:      min={min(raw):.2f}  median={st.median(raw):.2f}  max={max(raw):.2f}  mean={st.mean(raw):.2f}")

anc = [r["score_anchored"]["normalized"] for r in ok
       if r.get("score_anchored") and r["score_anchored"].get("normalized") is not None]
print(f"anchored score: min={min(anc):.2f}  median={st.median(anc):.2f}  max={max(anc):.2f}  mean={st.mean(anc):.2f}")

# Smoke: confirm scores are in [0,1]
assert all(0 <= x <= 1 for x in raw), "raw score out of [0,1]"
assert all(0 <= x <= 1 for x in anc), "anchored score out of [0,1]"
print("OK: all scores in [0,1]")
PY
```

Expected: scores in [0,1], non-trivial spread, no errors.

- [ ] **Step 4: Re-run to verify resume is a no-op**

```bash
.venv/bin/python src/score_rlm_answers.py 2>&1 | tail -5
```

Expected: log says `loaded 94 existing scores`, then `nothing to score (resume covered everything)`, then `wrote scores=... report=... (94 items scored ok, 0 errors)`.

- [ ] **Step 5: Spot-check the report**

```bash
head -80 outputs/scoring/cae-v2.0-1-report.md
echo "---"
wc -l outputs/scoring/cae-v2.0-1-report.md
```

Expected: header + §1–§3 visible at the top; total length ~200–500 lines.

- [ ] **Step 6: Commit results**

```bash
git add outputs/scoring/cae-v2.0-1-scores.json outputs/scoring/cae-v2.0-1-report.md outputs/scoring/cae-v2.0-1.log
git commit -m "$(cat <<'EOF'
data(cae): score 94 RLM answers via gpt-5.5 judge

Ran src/score_rlm_answers.py on the 94 RLM-generated answers using
src/rubrics/Scorer with the gpt-5.5 judge model and cached
ref/weak anchors. Produces:
- outputs/scoring/cae-v2.0-1-scores.json (per-item full breakdown)
- outputs/scoring/cae-v2.0-1-report.md   (aggregate + worst-10 report)

EOF
)"
```

---

## Risks Summary

| Risk | Severity | Mitigation in plan |
|------|----------|---------------------|
| API spend ($15–20) | MEDIUM | Task 4 dry-run before Task 5; per-task review gate |
| Judge response malformed | LOW | `judge_one_async` already wraps in try/except → `met=False, error=...` |
| Scores file corrupted mid-write | LOW | `tempfile.NamedTemporaryFile + os.replace` (Task 2) |
| Resume false-skip on partial save | LOW | `filter_pending` keys on `error is None AND score is not None` |
| anchored=None breaks worst-N sort | LOW | `_anchored_for_sort` returns +inf for None (tested in Task 1) |
| `_question_text` key leaks into scores.json on resume save | LOW | `_attach_question_text` runs AFTER `save_scores`; merged list isn't saved again in dry-run |
