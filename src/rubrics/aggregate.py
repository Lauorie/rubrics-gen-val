"""Build aggregate statistics over per-candidate score results."""
from __future__ import annotations
from collections import defaultdict
from statistics import mean
from typing import Iterable


def _safe_mean(xs: list) -> float | None:
    xs = [x for x in xs if x is not None]
    return mean(xs) if xs else None


def build_aggregate(results: Iterable[dict]) -> dict:
    results = list(results)
    n = len(results)
    ok = [r for r in results if r.get("score") is not None]
    n_errors = n - len(ok)

    raw_scores = [r["score"] for r in ok]
    anchored = [
        r["score_anchored"]["normalized"]
        for r in ok
        if r.get("score_anchored") and r["score_anchored"].get("normalized") is not None
    ]

    by_qt: dict[str, list] = defaultdict(list)
    by_qt_norm: dict[str, list] = defaultdict(list)
    by_diff: dict[str, list] = defaultdict(list)
    by_diff_norm: dict[str, list] = defaultdict(list)
    crit_counter: dict[str, list] = defaultdict(list)

    for r in ok:
        qt = r.get("question_type")
        if qt:
            by_qt[qt].append(r["score"])
            if r.get("score_anchored") and r["score_anchored"].get("normalized") is not None:
                by_qt_norm[qt].append(r["score_anchored"]["normalized"])
        diff = r.get("difficulty")
        if diff:
            by_diff[diff].append(r["score"])
            if r.get("score_anchored") and r["score_anchored"].get("normalized") is not None:
                by_diff_norm[diff].append(r["score_anchored"]["normalized"])
        for b in r.get("breakdown", []):
            crit_counter[b["criterion_type"]].append(b["met"])

    return {
        "n_predictions": n,
        "n_scored_ok": len(ok),
        "n_errors": n_errors,
        "mean_score": _safe_mean(raw_scores),
        "mean_anchored": _safe_mean(anchored),
        "by_question_type": {
            qt: {
                "n": len(scores),
                "mean": _safe_mean(scores),
                "mean_anchored": _safe_mean(by_qt_norm.get(qt, [])),
            }
            for qt, scores in by_qt.items()
        },
        "by_difficulty": {
            d: {
                "n": len(scores),
                "mean": _safe_mean(scores),
                "mean_anchored": _safe_mean(by_diff_norm.get(d, [])),
            }
            for d, scores in by_diff.items()
        },
        "by_criterion_type": {
            ct: {"n_criteria": len(metlist), "met_rate": sum(metlist) / len(metlist) if metlist else 0.0}
            for ct, metlist in crit_counter.items()
        },
    }
