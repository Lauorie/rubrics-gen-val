"""Score model predictions against CAE rubrics."""
from __future__ import annotations
import argparse
import asyncio
import datetime as dt
import json
import logging
import time
from pathlib import Path

from dotenv import load_dotenv

from rubrics.aggregate import build_aggregate
from rubrics.anchor import AnchorCache, compute_anchor_for_rubric
from rubrics.llm_client import LLMClient, LLMConfig
from rubrics.scorer import Scorer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")
logger = logging.getLogger("score_predictions")


def load_rubrics(items_dir: Path) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for p in sorted(items_dir.glob("idx_*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        out[r["item_idx"]] = r
    return out


def load_predictions(path: Path) -> list[dict]:
    preds: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        preds.append(json.loads(line))
    return preds


async def ensure_anchors(
    rubrics: dict[int, dict], cache: AnchorCache, client: LLMClient,
    refresh: bool, concurrency: int,
) -> None:
    cache.load()
    missing = [idx for idx in rubrics if refresh or not cache.has(idx)]
    if not missing:
        logger.info("Anchor cache hit for all %d rubrics", len(rubrics))
        return
    logger.info("Computing anchors for %d rubrics (refresh=%s)...", len(missing), refresh)

    sem = asyncio.Semaphore(concurrency)

    async def _one(idx: int) -> None:
        async with sem:
            res = await compute_anchor_for_rubric(rubrics[idx], client)
        cache.set(idx, ref_score=res["ref_score"], weak_score=res["weak_score"], judge_model=res["judge_model"])

    await asyncio.gather(*(_one(idx) for idx in missing))
    cache.flush()
    logger.info("Anchor cache written to %s", cache.path)


async def amain() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--predictions", required=True, type=Path)
    p.add_argument("--rubrics-dir", default=Path("rubrics/items"), type=Path)
    p.add_argument("--anchor-cache", default=Path("data/CAE-anchor-scores.json"), type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--concurrency", type=int, default=16)
    p.add_argument("--judge-model", default=None)
    p.add_argument("--refresh-anchors", action="store_true")
    p.add_argument("--no-anchors", action="store_true")
    p.add_argument("--resume", action="store_true")
    args = p.parse_args()

    load_dotenv()
    cfg = LLMConfig.from_env()
    if args.judge_model:
        cfg.model = args.judge_model
    client = LLMClient(cfg)

    rubrics = load_rubrics(args.rubrics_dir)
    logger.info("Loaded %d rubrics", len(rubrics))

    preds = load_predictions(args.predictions)
    logger.info("Loaded %d predictions from %s", len(preds), args.predictions)

    anchor_cache = AnchorCache(args.anchor_cache)
    if not args.no_anchors:
        await ensure_anchors(rubrics, anchor_cache, client, args.refresh_anchors, args.concurrency)

    anchors = {int(k): v for k, v in anchor_cache._data.items()} if not args.no_anchors else None

    already_done: dict[int, dict] = {}
    if args.resume and args.out.exists():
        prior = json.loads(args.out.read_text(encoding="utf-8"))
        for r in prior.get("per_candidate", []):
            if r.get("score") is not None:
                already_done[r["item_idx"]] = r
        logger.info("Resume: %d candidates already scored", len(already_done))

    todo = [pp for pp in preds if pp["item_idx"] not in already_done]
    logger.info("Scoring %d candidates...", len(todo))

    t0 = time.time()
    scorer = Scorer(rubrics=rubrics, judge_client=client, concurrency=args.concurrency, anchors=anchors)
    new_results = await scorer.score_batch(todo)
    elapsed = time.time() - t0

    all_results = list(already_done.values()) + new_results
    all_results.sort(key=lambda r: r.get("item_idx", -1))

    aggregate = build_aggregate(all_results)
    aggregate["judge_model"] = cfg.model
    aggregate["rubric_version"] = "1.0"
    aggregate["scored_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    aggregate["elapsed_seconds"] = round(elapsed, 2)

    report = {"per_candidate": all_results, "aggregate": aggregate}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Wrote eval report to %s", args.out)


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()
