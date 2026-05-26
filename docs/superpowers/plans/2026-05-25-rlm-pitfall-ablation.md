# RLM Pitfall Ablation — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce two stylistic pitfalls (verbosity 31 trips → < 10; boilerplate openings 12 → < 3) in RLM answers by appending three style directives to `papers_qa`'s `BILINGUAL_ADDENDUM` and lowering `PAPERS_QA_TEMPERATURE` from 0.8 → 0.3. Re-run all 94 questions to a sidecar v2 dataset, re-score, then emit a diff report so any substantive-score regression (> 0.02) is visible.

**Architecture:** Reuse existing CLI tools (`src/generate_rlm_answers.py`, `src/score_rlm_answers.py`) with sidecar `--input/--output/--scores-out/--report-out` paths to keep v1 intact. New code is a single pure-function diff renderer (`src/rubrics_diff_report.py`) + matching tests + a thin CLI.

**Tech Stack:** Python 3.12, pytest. No new dependencies.

---

## File Structure

**Files to create:**
- `src/rubrics_diff_report.py` (~150 lines) — `render_diff(scores_v1, scores_v2, rubrics, meta) -> str` (pure function) + `main()` argparse CLI.
- `tests/test_rubrics_diff_report.py` (~10 tests) — every diff section, top-N ordering, missing-item handling.

**Files to modify:**
- `papers_qa/papers_qa/prompts.py` — append 3 style directives to `BILINGUAL_ADDENDUM` (just before the closing `============================` divider at line 103).
- `papers_qa/.env` — `PAPERS_QA_TEMPERATURE=0.8` → `0.3`.

**Files to read but not modify:**
- `src/generate_rlm_answers.py`, `src/score_rlm_answers.py` — reused as-is via CLI flags.
- `data/CAE-v2.0-1-rubrics.json`, `outputs/scoring/cae-v2.0-1-scores.json` — read-only v1.

**Files NEVER overwritten:**
- `data/CAE-v2.0-1-rubrics.json` (v1)
- `outputs/scoring/cae-v2.0-1-scores.json` (v1)
- `outputs/scoring/cae-v2.0-1-report.md` (v1)

---

## Task 1: Prompt directives + temperature drop

**Files:**
- Modify: `papers_qa/papers_qa/prompts.py` (insert before the final `============================` divider in `BILINGUAL_ADDENDUM`, which is at line 103)
- Modify: `papers_qa/.env` (one-line change)
- Test: `tests/test_papers_qa_prompts.py` (new, 3 tests)

- [ ] **Step 1: Write failing tests for the prompt-build behavior**

Create `tests/test_papers_qa_prompts.py`:

```python
"""Verify the BILINGUAL_ADDENDUM style directives are present in the built prompt."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "papers_qa"))

from papers_qa.prompts import build_bilingual_system_prompt


def test_prompt_includes_no_boilerplate_directive() -> None:
    p = build_bilingual_system_prompt(num_papers=8)
    assert "不要以" in p
    assert "套话" in p
    assert "开场白" in p


def test_prompt_includes_concise_directive() -> None:
    p = build_bilingual_system_prompt(num_papers=8)
    assert "紧凑" in p or "聚焦" in p
    assert "无直接关联" in p or "无关的背景" in p


def test_prompt_includes_no_multiple_answers_directive() -> None:
    p = build_bilingual_system_prompt(num_papers=8)
    assert "不要给出多个相互矛盾" in p
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/juli/RLM
.venv/bin/python -m pytest tests/test_papers_qa_prompts.py -v
```
Expected: 3 failing tests (substrings not in current addendum).

- [ ] **Step 3: Modify `papers_qa/papers_qa/prompts.py`**

In `BILINGUAL_ADDENDUM`, locate the line `**Cite paper IDs.** End the answer with the paper IDs you used, e.g.:` (around line 101). After the next 1-2 lines and BEFORE the `================================================================` divider (line 103), insert this block:

```
**回答风格要求（必须遵守）：**

1. **直接给出答案。** 不要以"好的"、"我们来回答"、"接下来我将…"、"以下是…的回答"
   等套话、开场白或元评论开头。第一句话就要是实质内容。
2. **紧凑、聚焦。** 答案应直接针对问题，不要展开与问题无直接关联的背景知识、
   相邻概念或重复内容。一段说清楚的就不要分三段说。
3. **不要给出多个相互矛盾的候选答案。** 例如 "可能是 A 也可能是 B" / "以下是
   几种可能的解释……"。选定一个最佳答案并直接给出；如确有多种合理理解，
   只在末尾用一句话标注即可。
```

Concretely, the relevant section of `BILINGUAL_ADDENDUM` should end like this:

```
**Cite paper IDs.** End the answer with the paper IDs you used, e.g.:
"（据 Agarwal_2024_2306.13649 / Qwen3_Technical_Report 所述）"

**回答风格要求（必须遵守）：**

1. **直接给出答案。** 不要以"好的"、"我们来回答"、"接下来我将…"、"以下是…的回答"
   等套话、开场白或元评论开头。第一句话就要是实质内容。
2. **紧凑、聚焦。** 答案应直接针对问题，不要展开与问题无直接关联的背景知识、
   相邻概念或重复内容。一段说清楚的就不要分三段说。
3. **不要给出多个相互矛盾的候选答案。** 例如 "可能是 A 也可能是 B" / "以下是
   几种可能的解释……"。选定一个最佳答案并直接给出；如确有多种合理理解，
   只在末尾用一句话标注即可。

================================================================
"""
```

- [ ] **Step 4: Modify `papers_qa/.env`**

Change exactly the line `PAPERS_QA_TEMPERATURE=0.8` to `PAPERS_QA_TEMPERATURE=0.3`. All other lines untouched.

- [ ] **Step 5: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/test_papers_qa_prompts.py -v
```
Expected: 3 passed.

- [ ] **Step 6: Eyeball the env change**

```bash
grep TEMPERATURE /home/juli/RLM/papers_qa/.env
```
Expected: `PAPERS_QA_TEMPERATURE=0.3`.

- [ ] **Step 7: Commit**

```bash
git add papers_qa/papers_qa/prompts.py papers_qa/.env tests/test_papers_qa_prompts.py
git commit -m "feat(papers_qa): add style directives + drop temperature 0.8→0.3"
```

---

## Task 2: Diff report renderer

**Files:**
- Create: `src/rubrics_diff_report.py`
- Create: `tests/test_rubrics_diff_report.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_rubrics_diff_report.py`:

```python
"""Tests for src/rubrics_diff_report.py — pure markdown rendering, no LLM."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

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
    assert "0.50" in md  # v1 mean
    assert "0.70" in md  # v2 mean
    assert "+0.20" in md  # positive delta


def test_pitfall_trip_delta_per_text() -> None:
    v1 = [_result(0, 0.5, pitfalls=[("套话开场", True), ("冗长", True)])]
    v2 = [_result(0, 0.5, pitfalls=[("套话开场", False), ("冗长", True)])]
    md = render_diff(v1, v2, rubrics=[{"item_idx": 0, "question": "Q"}], meta=_meta())
    sec = md.split("## 2. Pitfall 触发对比")[1].split("## 3.")[0]
    # 套话开场: 1 → 0 (-1)
    assert "套话开场" in sec
    assert "-1" in sec or "−1" in sec
    # 冗长: 1 → 1 (0)
    assert "冗长" in sec


def test_by_criterion_type_delta_excludes_anti_hacking_or_separates() -> None:
    """By-criterion-type delta only covers POSITIVE criterion types (or labels them separately)."""
    v1 = [_result(0, 0.5, positives=[("factual_anchor", "f1", False),
                                      ("mechanism_explanation", "m1", False)])]
    v2 = [_result(0, 0.5, positives=[("factual_anchor", "f1", True),
                                      ("mechanism_explanation", "m1", True)])]
    md = render_diff(v1, v2, rubrics=[{"item_idx": 0, "question": "Q"}], meta=_meta())
    sec = md.split("## 3. 按 criterion_type 命中率对比")[1].split("## 4.")[0]
    assert "factual_anchor" in sec
    assert "mechanism_explanation" in sec
    # Both went 0% → 100%, delta +100pp
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
    v2 = [_result(0, 0.6, anchored=0.6),   # +0.1
          _result(1, 0.9, anchored=0.9),   # +0.4  ← biggest winner
          _result(2, 0.7, anchored=0.7)]   # +0.2
    rubrics = [{"item_idx": i, "question": f"Q{i}"} for i in range(3)]
    md = render_diff(v1, v2, rubrics=rubrics, meta=_meta(), top_n=3)
    sec = md.split("## 5. Top winners")[1].split("## 6.")[0]
    # Biggest winner (item 1, +0.4) appears first
    assert sec.find("item_idx=1") < sec.find("item_idx=2")
    assert sec.find("item_idx=2") < sec.find("item_idx=0")


def test_top_losers_ordered_by_anchored_delta_asc() -> None:
    v1 = [_result(0, 0.5, anchored=0.5), _result(1, 0.5, anchored=0.5)]
    v2 = [_result(0, 0.4, anchored=0.4),   # −0.1
          _result(1, 0.1, anchored=0.1)]   # −0.4 ← biggest loser
    rubrics = [{"item_idx": i, "question": f"Q{i}"} for i in range(2)]
    md = render_diff(v1, v2, rubrics=rubrics, meta=_meta(), top_n=2)
    sec = md.split("## 6. Top losers")[1]
    assert sec.find("item_idx=1") < sec.find("item_idx=0")


def test_losers_include_flipped_criteria() -> None:
    """For each loser, list criteria that went met=True → False (regressions)."""
    v1 = [_result(0, 0.8, anchored=0.8,
                  positives=[("factual_anchor", "must mention X", True),
                             ("mechanism_explanation", "must explain Y", True)])]
    v2 = [_result(0, 0.2, anchored=0.2,
                  positives=[("factual_anchor", "must mention X", False),
                             ("mechanism_explanation", "must explain Y", True)])]
    rubrics = [{"item_idx": 0, "question": "Q-fail"}]
    md = render_diff(v1, v2, rubrics=rubrics, meta=_meta(), top_n=1)
    sec = md.split("## 6. Top losers")[1]
    assert "must mention X" in sec  # the flipped criterion appears
    assert "Q-fail" in sec  # the question text appears


def test_items_only_in_one_version_are_flagged_at_top() -> None:
    """If v1 has item_idx=0 but v2 does not (or vice versa), header flags the counts."""
    v1 = [_result(0, 0.5, anchored=0.5), _result(1, 0.5, anchored=0.5)]
    v2 = [_result(0, 0.5, anchored=0.5)]  # missing item 1
    rubrics = [{"item_idx": 0, "question": "Q0"}, {"item_idx": 1, "question": "Q1"}]
    md = render_diff(v1, v2, rubrics=rubrics, meta=_meta())
    assert "在 v1 但不在 v2" in md or "in v1 but not v2" in md
    assert "1" in md  # the count of missing items


def test_render_diff_does_not_mutate_inputs() -> None:
    v1 = [_result(0, 0.5, anchored=0.5)]
    v2 = [_result(0, 0.7, anchored=0.7)]
    rubrics = [{"item_idx": 0, "question": "Q"}]
    snapshot = json.dumps([v1, v2, rubrics], default=str)
    render_diff(v1, v2, rubrics=rubrics, meta=_meta())
    assert json.dumps([v1, v2, rubrics], default=str) == snapshot
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest tests/test_rubrics_diff_report.py -v
```
Expected: ImportError on `from rubrics_diff_report import render_diff`.

- [ ] **Step 3: Implement `src/rubrics_diff_report.py`**

```python
"""Pure-function markdown diff between two scoring runs.

Inputs are two lists of per-item scoring results (output of
src/score_rlm_answers.py + src/rubrics/scorer.Scorer.score_one). No I/O
inside render_diff; main() does the CLI plumbing.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _fmt_signed(x: float, digits: int = 2) -> str:
    if x is None:
        return "—"
    sign = "+" if x >= 0 else "−"
    return f"{sign}{abs(x):.{digits}f}"


def _fmt_float(x: float | None, digits: int = 2) -> str:
    if x is None:
        return "—"
    return f"{x:.{digits}f}"


def _anchored(r: dict[str, Any]) -> float | None:
    sa = r.get("score_anchored") or {}
    if not isinstance(sa, dict):
        return None
    n = sa.get("normalized")
    return float(n) if n is not None else None


def _mean(xs: list[float]) -> float | None:
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _by_idx(results: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    return {int(r["item_idx"]): r for r in results}


def _render_header(v1: list, v2: list, meta: dict[str, str]) -> str:
    v1_idx = set(int(r["item_idx"]) for r in v1)
    v2_idx = set(int(r["item_idx"]) for r in v2)
    only_v1 = sorted(v1_idx - v2_idx)
    only_v2 = sorted(v2_idx - v1_idx)
    both = sorted(v1_idx & v2_idx)
    lines = [
        "# RLM 评测结果对比报告 (v1 vs v2)\n",
        f"- v1: `{meta.get('scores_v1_path', '?')}`",
        f"- v2: `{meta.get('scores_v2_path', '?')}`",
        f"- 生成时间: {meta.get('generated_at', '?')}",
        f"- 共 {len(both)} 项可对比",
    ]
    if only_v1:
        lines.append(f"- 在 v1 但不在 v2: {len(only_v1)} 项 (item_idx={only_v1[:10]}{'...' if len(only_v1) > 10 else ''})")
    if only_v2:
        lines.append(f"- 在 v2 但不在 v1: {len(only_v2)} 项 (item_idx={only_v2[:10]}{'...' if len(only_v2) > 10 else ''})")
    return "\n".join(lines) + "\n"


def _render_overall(v1: list, v2: list) -> str:
    raw_v1 = _mean([r["score"] for r in v1 if r.get("score") is not None])
    raw_v2 = _mean([r["score"] for r in v2 if r.get("score") is not None])
    anc_v1 = _mean([_anchored(r) for r in v1])
    anc_v2 = _mean([_anchored(r) for r in v2])
    raw_d = (raw_v2 - raw_v1) if (raw_v1 is not None and raw_v2 is not None) else None
    anc_d = (anc_v2 - anc_v1) if (anc_v1 is not None and anc_v2 is not None) else None
    return (
        "\n## 1. 总体得分对比\n\n"
        "| 指标 | v1 | v2 | Δ |\n"
        "|---|---|---|---|\n"
        f"| 平均原始分 (raw) | {_fmt_float(raw_v1)} | {_fmt_float(raw_v2)} | {_fmt_signed(raw_d) if raw_d is not None else '—'} |\n"
        f"| 平均锚定分 (anchored) | {_fmt_float(anc_v1)} | {_fmt_float(anc_v2)} | {_fmt_signed(anc_d) if anc_d is not None else '—'} |\n"
    )


def _count_pitfall_trips(results: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in results:
        for b in r.get("breakdown") or []:
            if b["criterion_type"] == "anti_hacking" and b["met"]:
                counts[b["text"]] = counts.get(b["text"], 0) + 1
    return counts


def _render_pitfall_diff(v1: list, v2: list) -> str:
    c1 = _count_pitfall_trips(v1)
    c2 = _count_pitfall_trips(v2)
    keys = sorted(set(c1) | set(c2), key=lambda k: -(c1.get(k, 0) + c2.get(k, 0)))
    lines = [
        "\n## 2. Pitfall 触发对比\n",
        "（按 v1+v2 总触发次数降序）\n",
        "| pitfall | v1 触发 | v2 触发 | Δ |",
        "|---|---|---|---|",
    ]
    for k in keys:
        a = c1.get(k, 0)
        b = c2.get(k, 0)
        delta = b - a
        sign = "+" if delta > 0 else ("−" if delta < 0 else "0")
        lines.append(f"| {k} | {a} | {b} | {sign if delta != 0 else '0'}{abs(delta) if delta != 0 else ''} |")
    return "\n".join(lines) + "\n"


def _criterion_rate_by_type(results: list[dict[str, Any]]) -> dict[str, tuple[int, int]]:
    """{criterion_type: (total, met)} for POSITIVE criteria only."""
    counter: dict[str, list[int]] = {}
    for r in results:
        for b in r.get("breakdown") or []:
            if b["sign"] != "positive":
                continue
            ct = b["criterion_type"]
            slot = counter.setdefault(ct, [0, 0])
            slot[0] += 1
            if b["met"]:
                slot[1] += 1
    return {ct: (t, m) for ct, (t, m) in counter.items()}


def _render_by_criterion_type(v1: list, v2: list) -> str:
    r1 = _criterion_rate_by_type(v1)
    r2 = _criterion_rate_by_type(v2)
    cts = sorted(set(r1) | set(r2))
    lines = [
        "\n## 3. 按 criterion_type 命中率对比\n",
        "（仅 sign=positive；Δ 单位为百分点 pp）\n",
        "| criterion_type | v1 命中率 | v2 命中率 | Δ (pp) |",
        "|---|---|---|---|",
    ]
    for ct in cts:
        t1, m1 = r1.get(ct, (0, 0))
        t2, m2 = r2.get(ct, (0, 0))
        rate1 = (m1 / t1 * 100) if t1 else 0.0
        rate2 = (m2 / t2 * 100) if t2 else 0.0
        delta = rate2 - rate1
        sign = "+" if delta >= 0 else "−"
        lines.append(
            f"| {ct} | {rate1:.1f}% ({m1}/{t1}) | {rate2:.1f}% ({m2}/{t2}) | {sign}{abs(delta):.1f} |"
        )
    return "\n".join(lines) + "\n"


def _by_qt_anchored(results: list[dict[str, Any]]) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    for r in results:
        a = _anchored(r)
        if a is None:
            continue
        out.setdefault(r.get("question_type", "?"), []).append(a)
    return out


def _render_by_question_type(v1: list, v2: list) -> str:
    g1 = _by_qt_anchored(v1)
    g2 = _by_qt_anchored(v2)
    qts = sorted(set(g1) | set(g2))
    lines = [
        "\n## 4. 按题型分组对比 (mean anchored)\n",
        "| 题型 | v1 数量 | v1 anchored | v2 数量 | v2 anchored | Δ |",
        "|---|---|---|---|---|---|",
    ]
    for qt in qts:
        a1, a2 = g1.get(qt, []), g2.get(qt, [])
        m1, m2 = _mean(a1), _mean(a2)
        delta = (m2 - m1) if (m1 is not None and m2 is not None) else None
        lines.append(
            f"| {qt} | {len(a1)} | {_fmt_float(m1)} | {len(a2)} | {_fmt_float(m2)} | "
            f"{_fmt_signed(delta) if delta is not None else '—'} |"
        )
    return "\n".join(lines) + "\n"


def _item_delta(r1: dict[str, Any], r2: dict[str, Any]) -> float | None:
    a1, a2 = _anchored(r1), _anchored(r2)
    if a1 is None or a2 is None:
        return None
    return a2 - a1


def _flipped_criteria(r1: dict[str, Any], r2: dict[str, Any], *, direction: str) -> list[dict[str, Any]]:
    """direction='regress' returns criteria that went True→False (lost points);
    direction='gain' returns criteria that went False→True (gained points).
    Anti-hacking pitfalls are skipped here (covered in §2)."""
    b1 = {b["id"]: b for b in (r1.get("breakdown") or []) if b["criterion_type"] != "anti_hacking"}
    b2 = {b["id"]: b for b in (r2.get("breakdown") or []) if b["criterion_type"] != "anti_hacking"}
    out = []
    for cid, bb1 in b1.items():
        bb2 = b2.get(cid)
        if bb2 is None:
            continue
        if direction == "regress" and bb1["met"] and not bb2["met"]:
            out.append(bb1)
        elif direction == "gain" and not bb1["met"] and bb2["met"]:
            out.append(bb1)
    return out


def _render_top_movers(
    v1: list, v2: list, rubrics: list[dict[str, Any]], top_n: int, *, winners: bool,
) -> str:
    by_v1 = _by_idx(v1)
    by_v2 = _by_idx(v2)
    questions = {int(r["item_idx"]): r.get("question", "") for r in rubrics}
    common = sorted(set(by_v1) & set(by_v2))
    deltas: list[tuple[int, float]] = []
    for idx in common:
        d = _item_delta(by_v1[idx], by_v2[idx])
        if d is None:
            continue
        deltas.append((idx, d))
    deltas.sort(key=lambda t: -t[1] if winners else t[1])
    deltas = deltas[:top_n]

    title_num = "5" if winners else "6"
    title_label = "Top winners" if winners else "Top losers"
    direction = "gain" if winners else "regress"
    out = [f"\n## {title_num}. {title_label} (按 anchored Δ {'降' if winners else '升'}序)\n"]
    if not deltas:
        out.append("\n_no movers_\n")
        return "\n".join(out)
    for idx, d in deltas:
        r1, r2 = by_v1[idx], by_v2[idx]
        a1, a2 = _anchored(r1), _anchored(r2)
        out.append(
            f"\n### item_idx={idx}  Δ={_fmt_signed(d)} "
            f"(v1 anchored={_fmt_float(a1)} → v2 anchored={_fmt_float(a2)})"
        )
        q = questions.get(idx, "")
        if q:
            out.append(f"\n**问题**: {q}\n")
        flipped = _flipped_criteria(r1, r2, direction=direction)
        if flipped:
            arrow = "❌→✅" if winners else "✅→❌"
            out.append(f"\n**翻转的 criteria ({arrow}):**\n")
            for b in flipped:
                out.append(
                    f"- [{b['category']}, {b['criterion_type']}, w={b['weight']}] {b['text']}"
                )
        else:
            out.append("\n_(no positive-criterion flips; movement is from pitfall/contribution changes only)_")
    return "\n".join(out) + "\n"


def render_diff(
    scores_v1: list[dict[str, Any]],
    scores_v2: list[dict[str, Any]],
    *,
    rubrics: list[dict[str, Any]],
    meta: dict[str, str],
    top_n: int = 5,
) -> str:
    """Render the full diff report. Pure function — does NOT mutate inputs."""
    # Defensive copy so callers' lists aren't affected by any local sort etc.
    v1 = copy.deepcopy(scores_v1)
    v2 = copy.deepcopy(scores_v2)
    rb = copy.deepcopy(rubrics)
    parts = [
        _render_header(v1, v2, meta),
        _render_overall(v1, v2),
        _render_pitfall_diff(v1, v2),
        _render_by_criterion_type(v1, v2),
        _render_by_question_type(v1, v2),
        _render_top_movers(v1, v2, rb, top_n, winners=True),
        _render_top_movers(v1, v2, rb, top_n, winners=False),
    ]
    return "".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate v1-vs-v2 diff markdown for RLM scoring runs.",
    )
    parser.add_argument("--scores-v1", type=Path, required=True)
    parser.add_argument("--scores-v2", type=Path, required=True)
    parser.add_argument("--rubrics", type=Path, required=True,
                        help="Rubrics JSON (any version — question text only).")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--top-n", type=int, default=5)
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    )

    v1 = json.loads(args.scores_v1.read_text(encoding="utf-8"))
    v2 = json.loads(args.scores_v2.read_text(encoding="utf-8"))
    rubrics = json.loads(args.rubrics.read_text(encoding="utf-8"))

    md = render_diff(v1, v2,
                     rubrics=rubrics,
                     meta={
                         "scores_v1_path": str(args.scores_v1),
                         "scores_v2_path": str(args.scores_v2),
                         "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                     },
                     top_n=args.top_n)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(md, encoding="utf-8")
    logger.info("wrote diff report to %s (%d chars)", args.out, len(md))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/test_rubrics_diff_report.py -v
```
Expected: 10 passed.

- [ ] **Step 5: Sanity-check the CLI**

```bash
.venv/bin/python src/rubrics_diff_report.py --help
```
Expected: argparse help output with all 6 flags.

- [ ] **Step 6: Commit**

```bash
git add src/rubrics_diff_report.py tests/test_rubrics_diff_report.py
git commit -m "feat(rubrics-diff): pure-function v1-vs-v2 diff report"
```

---

## Task 3: Re-run RLM answers on all 94 items → v2

**Pre-flight assumption:** Tasks 1 + 2 committed.

This task spends ~$10 and takes ~47 min wall clock. Launch in background, monitor for completion + commit.

- [ ] **Step 1: Confirm prompts.py + .env are the modified ones from Task 1**

```bash
cd /home/juli/RLM
grep -c "回答风格要求" papers_qa/papers_qa/prompts.py
grep TEMPERATURE papers_qa/.env
```
Expected: `1` (one occurrence of the new heading) and `PAPERS_QA_TEMPERATURE=0.3`.

- [ ] **Step 2: Launch the v2 run in background**

```bash
cd /home/juli/RLM
set -a && source papers_qa/.env && set +a
nohup .venv/bin/python src/generate_rlm_answers.py \
    --input  data/CAE-v2.0-1-rubrics.json \
    --output data/CAE-v2.0-1-rubrics-v2.json \
    --jsonl  outputs/rlm-answers/cae-v2.0-1-v2.jsonl \
    --papers-dir /home/juli/RLM/CAE-MDs \
    --workers 4 \
    > outputs/rlm-answers/cae-v2.0-1-v2.log 2>&1 &
PID=$!
disown
echo "pid=$PID" | tee outputs/rlm-answers/cae-v2.0-1-v2.pid
sleep 8
head -8 outputs/rlm-answers/cae-v2.0-1-v2.log
```
Expected: PID printed, log shows `Loaded 94 rubric items`, `Running inference on 94 items, workers=4`, per-worker `PapersQA ready`.

- [ ] **Step 3: Wait for completion, count completed items**

```bash
# Wait until JSONL has 94 lines or 90 min pass:
for i in $(seq 1 180); do
    n=$(wc -l < outputs/rlm-answers/cae-v2.0-1-v2.jsonl 2>/dev/null || echo 0)
    if [ "$n" -ge 94 ]; then break; fi
    sleep 30
done
tail -3 outputs/rlm-answers/cae-v2.0-1-v2.log
wc -l outputs/rlm-answers/cae-v2.0-1-v2.jsonl
```
Expected: 94 lines in JSONL, log's last line says `Wrote ... — 94/94 answered, 0 errored.`

- [ ] **Step 4: Verify rubric structure is preserved (only `rlm_answer` + `rlm_error` differ)**

```bash
cd /home/juli/RLM
.venv/bin/python - <<'PY'
import json
v1 = json.load(open("data/CAE-v2.0-1-rubrics.json"))
v2 = json.load(open("data/CAE-v2.0-1-rubrics-v2.json"))
assert len(v1) == len(v2) == 94, f"length mismatch: v1={len(v1)} v2={len(v2)}"
mutable_keys = {"rlm_answer", "rlm_error"}
diffs = 0
for a, b in zip(sorted(v1, key=lambda r: r["item_idx"]),
                sorted(v2, key=lambda r: r["item_idx"])):
    a_immut = {k: v for k, v in a.items() if k not in mutable_keys}
    b_immut = {k: v for k, v in b.items() if k not in mutable_keys}
    if a_immut != b_immut:
        diffs += 1
print(f"items where immutable fields differ: {diffs}")
assert diffs == 0
# Length sanity
import statistics as st
lens1 = [len(r["rlm_answer"]) for r in v1 if r.get("rlm_answer")]
lens2 = [len(r["rlm_answer"]) for r in v2 if r.get("rlm_answer")]
print(f"v1 lengths: median={int(st.median(lens1))} mean={int(st.mean(lens1))} max={max(lens1)}")
print(f"v2 lengths: median={int(st.median(lens2))} mean={int(st.mean(lens2))} max={max(lens2)}")
PY
```
Expected: `items where immutable fields differ: 0`. v2 median length should be **lower than v1** (style directives compress answers). If v2 median is ≥ 1.1× v1 median, flag as a concern — prompt may not have landed.

- [ ] **Step 5: Commit v2 rubrics + JSONL + log**

```bash
git add data/CAE-v2.0-1-rubrics-v2.json outputs/rlm-answers/cae-v2.0-1-v2.jsonl outputs/rlm-answers/cae-v2.0-1-v2.log
git commit -m "data(cae): v2 rlm_answer with style directives + temp=0.3"
```

---

## Task 4: Re-score v2 → scores-v2 + report-v2

**Pre-flight assumption:** Task 3 committed.

~$15, ~5 min.

- [ ] **Step 1: Launch v2 scoring in background**

```bash
cd /home/juli/RLM
set -a && source papers_qa/.env && set +a
nohup .venv/bin/python src/score_rlm_answers.py \
    --input       data/CAE-v2.0-1-rubrics-v2.json \
    --anchors     data/CAE-anchor-scores.json \
    --scores-out  outputs/scoring/cae-v2.0-1-scores-v2.json \
    --report-out  outputs/scoring/cae-v2.0-1-report-v2.md \
    --judge-model openai/gpt-5.5 \
    --concurrency 16 \
    --worst-n     10 \
    > outputs/scoring/cae-v2.0-1-v2.log 2>&1 &
PID=$!
disown
echo "pid=$PID" | tee outputs/scoring/cae-v2.0-1-v2.pid
sleep 5
head -6 outputs/scoring/cae-v2.0-1-v2.log
```
Expected: PID printed, log shows `loaded 94 rubric items`, `loaded 94 anchors`, `scoring 94 pending items`.

- [ ] **Step 2: Wait for completion**

```bash
for i in $(seq 1 30); do
    if grep -q "wrote scores=" outputs/scoring/cae-v2.0-1-v2.log 2>/dev/null; then break; fi
    sleep 20
done
tail -3 outputs/scoring/cae-v2.0-1-v2.log
```
Expected: `wrote scores=... report=... (94 items scored ok, 0 errors)`.

- [ ] **Step 3: Sanity-check scores**

```bash
cd /home/juli/RLM
.venv/bin/python - <<'PY'
import json, statistics as st
s = json.load(open("outputs/scoring/cae-v2.0-1-scores-v2.json"))
ok = [r for r in s if r.get("score") is not None]
assert len(ok) == 94, f"expected 94 ok, got {len(ok)}"
raw = [r["score"] for r in ok]
anc = [r["score_anchored"]["normalized"] for r in ok
       if r.get("score_anchored") and r["score_anchored"].get("normalized") is not None]
print(f"v2 raw:      mean={st.mean(raw):.3f}  median={st.median(raw):.3f}")
print(f"v2 anchored: mean={st.mean(anc):.3f}  median={st.median(anc):.3f}")
assert all(0 <= x <= 1 for x in raw), "raw out of [0,1]"
assert all(0 <= x <= 1 for x in anc), "anchored out of [0,1]"
print("OK")
PY
```
Expected: scores in [0,1], 94/94 ok.

- [ ] **Step 4: Commit v2 scores + report + log**

```bash
git add outputs/scoring/cae-v2.0-1-scores-v2.json outputs/scoring/cae-v2.0-1-report-v2.md outputs/scoring/cae-v2.0-1-v2.log
git commit -m "data(cae): score v2 RLM answers via gpt-5.5 judge"
```

---

## Task 5: Generate diff report + check acceptance criteria + commit

**Pre-flight assumption:** Task 4 committed.

- [ ] **Step 1: Generate the diff report**

```bash
cd /home/juli/RLM
.venv/bin/python src/rubrics_diff_report.py \
    --scores-v1 outputs/scoring/cae-v2.0-1-scores.json \
    --scores-v2 outputs/scoring/cae-v2.0-1-scores-v2.json \
    --rubrics   data/CAE-v2.0-1-rubrics-v2.json \
    --out       outputs/scoring/cae-v2.0-1-diff-v1-v2.md \
    --top-n     5
head -80 outputs/scoring/cae-v2.0-1-diff-v1-v2.md
```
Expected: report header + §1 总体得分对比 + §2 Pitfall 触发对比 visible at top.

- [ ] **Step 2: Programmatically verify acceptance criteria**

```bash
cd /home/juli/RLM
.venv/bin/python - <<'PY'
import json
from collections import Counter

s1 = json.load(open("outputs/scoring/cae-v2.0-1-scores.json"))
s2 = json.load(open("outputs/scoring/cae-v2.0-1-scores-v2.json"))

# AC #1 & #2: pitfall trip counts
def trips(scores):
    c = Counter()
    for r in scores:
        for b in r.get("breakdown", []):
            if b["criterion_type"] == "anti_hacking" and b["met"]:
                c[b["text"]] += 1
    return c

t1, t2 = trips(s1), trips(s2)
PITFALL_VERBOSE = "回答篇幅冗长，包含大量与问题无关的背景铺垫或重复"
PITFALL_OPENING = "回答以套话/开场白/元评论开头而无实质内容"

ac1 = t2.get(PITFALL_VERBOSE, 0)
ac2 = t2.get(PITFALL_OPENING, 0)
print(f"AC #1 verbosity: v1={t1.get(PITFALL_VERBOSE,0)} → v2={ac1}  (target: < 10)  {'PASS' if ac1 < 10 else 'FAIL'}")
print(f"AC #2 boilerplate: v1={t1.get(PITFALL_OPENING,0)} → v2={ac2}  (target: < 3)   {'PASS' if ac2 < 3 else 'FAIL'}")

# AC #3: overall mean anchored does NOT drop > 0.02
def mean_anchored(scores):
    xs = [r["score_anchored"]["normalized"] for r in scores
          if r.get("score_anchored") and r["score_anchored"].get("normalized") is not None]
    return sum(xs) / len(xs) if xs else None
a1 = mean_anchored(s1); a2 = mean_anchored(s2)
delta = a2 - a1
print(f"AC #3 mean anchored: v1={a1:.3f} → v2={a2:.3f}  Δ={delta:+.3f}  (target: Δ ≥ −0.02)  {'PASS' if delta >= -0.02 else 'FAIL'}")
PY
```
Expected: PASS on all 3 ACs. If any FAIL, note it but still commit the diff (the failure is data — we want it visible).

- [ ] **Step 3: Commit the diff report**

```bash
git add outputs/scoring/cae-v2.0-1-diff-v1-v2.md
git commit -m "$(cat <<'EOF'
data(cae): diff report v1 vs v2 (pitfall ablation)

v1 used the original BILINGUAL_ADDENDUM and PAPERS_QA_TEMPERATURE=0.8.
v2 added 3 style directives (no boilerplate, concise, no multiple
contradictory answers) and lowered temperature to 0.3.

See outputs/scoring/cae-v2.0-1-diff-v1-v2.md for the full delta.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 4: Print a final summary**

```bash
cd /home/juli/RLM
.venv/bin/python - <<'PY'
import json, statistics as st
from collections import Counter
s1 = json.load(open("outputs/scoring/cae-v2.0-1-scores.json"))
s2 = json.load(open("outputs/scoring/cae-v2.0-1-scores-v2.json"))
def mean_anchored(s):
    xs = [r["score_anchored"]["normalized"] for r in s if r.get("score_anchored") and r["score_anchored"].get("normalized") is not None]
    return sum(xs)/len(xs)
def trips(s, key):
    return sum(1 for r in s for b in r.get("breakdown",[]) if b["criterion_type"]=="anti_hacking" and b["met"] and b["text"].startswith(key))
print(f"=== Phase 1 ablation summary ===")
print(f"mean anchored: {mean_anchored(s1):.3f} → {mean_anchored(s2):.3f}  (Δ {mean_anchored(s2)-mean_anchored(s1):+.3f})")
print(f"verbosity trips: {trips(s1, '回答篇幅冗长')} → {trips(s2, '回答篇幅冗长')}")
print(f"boilerplate trips: {trips(s1, '回答以套话')} → {trips(s2, '回答以套话')}")
PY
```
Expected: numbers printed; this is the report-back-to-user line.

---

## Risks Summary

| Risk | Severity | Mitigation in plan |
|------|----------|---------------------|
| Re-run cost (~$10) | LOW | Per-call budget cap already in env |
| Re-score cost (~$15) | LOW | Same |
| Prompt directives ignored by deepseek-v4-flash | MEDIUM | Task 3 Step 4 measures answer length; if v2 median ≥ 1.1× v1, flag |
| Anchored mean regresses > 0.02 | MEDIUM | Task 5 Step 2 prints PASS/FAIL; failure is committed in the diff for visibility |
| v2 rubrics file structurally differs from v1 | LOW | Task 3 Step 4 asserts immutable fields are identical |
| Resume mid-failure on long re-run | LOW | `generate_rlm_answers.py` already supports JSONL-based resume |
