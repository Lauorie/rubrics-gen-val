"""Pure-function markdown rendering of rubric scoring results.

No I/O, no LLM. All inputs in, markdown string out. Designed for trivial
unit testing of every section.
"""
from __future__ import annotations

import logging
from typing import Any, Iterable

logger = logging.getLogger(__name__)

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
    """Walk every breakdown row; return {criterion_type: {total, met, rate}}."""
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
        q = r.get("_question_text") or ""
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
