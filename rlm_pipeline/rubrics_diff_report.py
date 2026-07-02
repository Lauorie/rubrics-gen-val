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
        if delta > 0:
            cell = f"+{delta}"
        elif delta < 0:
            cell = f"−{abs(delta)}"
        else:
            cell = "0"
        lines.append(f"| {k} | {a} | {b} | {cell} |")
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
    Anti-hacking pitfalls are skipped here (covered in §2).

    Matching uses (id, position) as compound key to handle duplicate IDs
    gracefully while still rejecting renamed criteria false-positives.
    """
    bd1 = [(i, b) for i, b in enumerate(r1.get("breakdown") or [])
           if b["criterion_type"] != "anti_hacking"]
    bd2 = {(i, b["id"]): b for i, b in enumerate(r2.get("breakdown") or [])
           if b["criterion_type"] != "anti_hacking"}
    out = []
    for pos, bb1 in bd1:
        bb2 = bd2.get((pos, bb1["id"]))
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
