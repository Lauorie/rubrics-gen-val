"""Score candidate answers against the CAE-v2.0-1 rubric set.

Usage:
    python score.py --predictions preds.jsonl --out eval.json

See README.md for full documentation.
"""
from __future__ import annotations
import argparse
import asyncio
import datetime as dt
import json
import logging
import time
from pathlib import Path

from dotenv import load_dotenv

from cae_eval.aggregate import build_aggregate
from cae_eval.anchor import AnchorCache, compute_anchor_for_rubric
from cae_eval.llm_client import LLMClient, LLMConfig
from cae_eval.scorer import Scorer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")
logger = logging.getLogger("score")

PACKAGE_ROOT = Path(__file__).parent
DEFAULT_RUBRICS = PACKAGE_ROOT / "data" / "CAE-v2.0-1-rubrics.json"
DEFAULT_ANCHORS = PACKAGE_ROOT / "data" / "CAE-anchor-scores.json"


def load_rubrics(path: Path) -> dict[int, dict]:
    """Load rubrics from a single JSON-array file keyed by `item_idx`."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return {r["item_idx"]: r for r in data}


def load_predictions(path: Path) -> list[dict]:
    """Load predictions from a JSONL file. Each line must have item_idx and answer."""
    preds: list[dict] = []
    for ln, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            raise ValueError(f"{path}:{ln} is not valid JSON: {e}") from e
        if "item_idx" not in obj or "answer" not in obj:
            raise ValueError(f"{path}:{ln} missing required field 'item_idx' or 'answer'")
        preds.append(obj)
    return preds


def warn_if_judge_mismatch(anchor_cache: dict, current_model: str) -> None:
    """Log a warning if the anchor cache was computed with a different judge model."""
    anchor_models = {v.get("judge_model") for v in anchor_cache.values()}
    anchor_models.discard(None)
    if anchor_models and current_model not in anchor_models:
        logger.warning(
            "Judge model mismatch: anchors computed with %s, you are using %s. "
            "score_anchored will NOT be comparable to prior RLM evaluations. "
            "To recalibrate, delete data/CAE-anchor-scores.json and re-run.",
            sorted(anchor_models), current_model,
        )


async def ensure_anchors(
    rubrics: dict[int, dict], cache: AnchorCache, client: LLMClient, concurrency: int,
) -> None:
    """Compute and persist any missing anchor scores."""
    cache.load()
    missing = [idx for idx in rubrics if not cache.has(idx)]
    if not missing:
        logger.info("Anchor cache hit for all %d rubrics", len(rubrics))
        return
    logger.info("Computing anchors for %d rubrics (cache miss)...", len(missing))
    sem = asyncio.Semaphore(concurrency)

    async def _one(idx: int) -> None:
        async with sem:
            res = await compute_anchor_for_rubric(rubrics[idx], client)
        cache.set(idx, ref_score=res["ref_score"], weak_score=res["weak_score"], judge_model=res["judge_model"])

    await asyncio.gather(*(_one(idx) for idx in missing))
    cache.flush()
    logger.info("Anchor cache written to %s", cache.path)


async def amain() -> None:
    p = argparse.ArgumentParser(description="Score predictions against CAE-v2.0-1 rubrics.")
    p.add_argument("--predictions", required=True, type=Path, help="JSONL file with one {item_idx, answer} per line")
    p.add_argument("--out", required=True, type=Path, help="Output JSON path for the eval report")
    p.add_argument("--rubrics", default=DEFAULT_RUBRICS, type=Path, help=f"Rubric JSON file (default: {DEFAULT_RUBRICS.name})")
    p.add_argument("--anchors", default=DEFAULT_ANCHORS, type=Path, help=f"Anchor cache JSON file (default: {DEFAULT_ANCHORS.name})")
    p.add_argument("--concurrency", type=int, default=16, help="Max concurrent judge LLM calls (default: 16)")
    p.add_argument("--judge-model", default=None, help="Override LLM_MODEL from env (NOT RECOMMENDED — breaks score comparability)")
    args = p.parse_args()

    load_dotenv()
    cfg = LLMConfig.from_env()
    if args.judge_model:
        cfg.model = args.judge_model
    client = LLMClient(cfg)

    rubrics = load_rubrics(args.rubrics)
    logger.info("Loaded %d rubrics from %s", len(rubrics), args.rubrics)

    preds = load_predictions(args.predictions)
    logger.info("Loaded %d predictions from %s", len(preds), args.predictions)

    anchor_cache = AnchorCache(args.anchors)
    await ensure_anchors(rubrics, anchor_cache, client, args.concurrency)
    warn_if_judge_mismatch(anchor_cache._data, cfg.model)
    anchors = {int(k): v for k, v in anchor_cache._data.items()}

    t0 = time.time()
    scorer = Scorer(rubrics=rubrics, judge_client=client, concurrency=args.concurrency, anchors=anchors)
    results = await scorer.score_batch(preds)
    elapsed = time.time() - t0

    results.sort(key=lambda r: r.get("item_idx", -1))
    aggregate = build_aggregate(results)
    aggregate["judge_model"] = cfg.model
    aggregate["rubric_version"] = "1.0"
    aggregate["scored_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    aggregate["elapsed_seconds"] = round(elapsed, 2)

    report = {"per_candidate": results, "aggregate": aggregate}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Wrote eval report to %s", args.out)
    logger.info("mean_score=%s mean_anchored=%s n=%d errors=%d",
                aggregate["mean_score"], aggregate["mean_anchored"],
                aggregate["n_scored_ok"], aggregate["n_errors"])


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()
