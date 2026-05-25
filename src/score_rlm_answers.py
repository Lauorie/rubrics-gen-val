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
    """Entry point for CLI scoring pipeline."""
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
    parser.add_argument("--concurrency", type=int, default=16,
                        help="Max concurrent judge calls (default: 16).")
    parser.add_argument("--worst-n", type=int, default=10,
                        help="How many lowest-scoring items to detail in the report (default: 10).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Skip scoring; render report from existing scores.json only.")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="Logging verbosity (default: INFO).")
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
