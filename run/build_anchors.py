"""Compute ref/weak anchor scores for a generated rubric set and cache to disk.

Reuses the tested ``compute_anchor_for_rubric`` and ``AnchorCache``; runs the
per-rubric anchor computations concurrently. Model is taken from the env
(set ``LLM_MODEL=openai/gpt-5.5`` to anchor with GPT-5.5).
"""
from __future__ import annotations
import argparse
import asyncio
import json
import logging
from pathlib import Path

from dotenv import load_dotenv

from rubrics.anchor import AnchorCache, compute_anchor_for_rubric
from rubrics.llm_client import LLMClient, LLMConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")
logger = logging.getLogger("build_anchors")


def load_rubrics(items_dir: Path) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for p in sorted(Path(items_dir).glob("idx_*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        out[r["item_idx"]] = r
    return out


async def amain() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--rubrics-dir", default="outputs/rubrics_v3_items")
    p.add_argument("--anchor-cache", default="cae-rubrics-eval/data/CAE-v3.0-anchor-scores.json")
    p.add_argument("--concurrency", type=int, default=16)
    p.add_argument("--refresh", action="store_true")
    args = p.parse_args()

    load_dotenv()
    cfg = LLMConfig.from_env()
    client = LLMClient(cfg)

    rubrics = load_rubrics(Path(args.rubrics_dir))
    logger.info("Loaded %d rubrics; judge=%s", len(rubrics), cfg.model)

    cache = AnchorCache(Path(args.anchor_cache))
    cache.load()
    missing = [i for i in rubrics if args.refresh or not cache.has(i)]
    logger.info("Computing anchors for %d / %d rubrics", len(missing), len(rubrics))

    sem = asyncio.Semaphore(args.concurrency)

    async def _one(idx: int) -> None:
        async with sem:
            res = await compute_anchor_for_rubric(rubrics[idx], client)
        cache.set(idx, ref_score=res["ref_score"], weak_score=res["weak_score"], judge_model=res["judge_model"])
        logger.info("anchor idx=%d ref=%.3f weak=%.3f", idx, res["ref_score"], res["weak_score"])

    await asyncio.gather(*(_one(idx) for idx in missing))
    cache.flush()
    logger.info("Wrote %d anchors to %s", len(cache._data), args.anchor_cache)


if __name__ == "__main__":
    asyncio.run(amain())
