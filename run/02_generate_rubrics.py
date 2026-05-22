"""Run the full GroundedRubric-CAE pipeline over CAE-v2.0-1.json."""
from __future__ import annotations
import argparse
import json
import logging
import os
import pickle
import random
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from rubrics.llm_client import LLMClient, LLMConfig
from rubrics.pipeline import build_rubric_for_item

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")
logger = logging.getLogger("generate_rubrics")


def set_seed(seed: int = 42):
    random.seed(seed); np.random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", default="data/CAE-v2.0-1.json")
    p.add_argument("--index", default="data/cae_chunk_index.pkl")
    p.add_argument("--out", default="data/CAE-v2.0-1-rubrics.json")
    p.add_argument("--items-dir", default="rubrics/items")
    p.add_argument("--limit", type=int, default=None, help="Only process first N items (debug)")
    p.add_argument("--dry-run", action="store_true", help="Stop after 1 item")
    p.add_argument("--resume", action="store_true", help="Skip items whose per-item file already exists")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    set_seed(args.seed)
    load_dotenv()

    data = json.loads(Path(args.data).read_text(encoding="utf-8"))
    with open(args.index, "rb") as f:
        index = pickle.load(f)
    logger.info("Loaded %d items, index with %d chunks", len(data), len(index.chunks))

    cfg = LLMConfig.from_env()
    gen_client = LLMClient(cfg)
    judge_client = LLMClient(cfg)  # same model

    embedder = SentenceTransformer(os.environ.get("EMBEDDING_MODEL", "BAAI/bge-base-zh-v1.5"))
    def embed_fn(texts):
        return np.asarray(embedder.encode(texts, normalize_embeddings=True, show_progress_bar=False))

    items_dir = Path(args.items_dir)
    items_dir.mkdir(parents=True, exist_ok=True)

    indexed = list(enumerate(data))
    if args.limit:
        indexed = indexed[: args.limit]
    if args.dry_run:
        indexed = indexed[:1]

    def filename_for(idx: int) -> Path:
        return items_dir / f"idx_{idx:03d}.json"

    if args.resume:
        before = len(indexed)
        indexed = [(idx, item) for idx, item in indexed if not filename_for(idx).exists()]
        logger.info("Resume mode: skipping %d items already generated; %d remain", before - len(indexed), len(indexed))

    for idx, item in tqdm(indexed, desc="generating rubrics"):
        try:
            rubric = build_rubric_for_item(
                item=item, index=index,
                generator_client=gen_client, judge_client=judge_client,
                embed_fn=embed_fn,
            )
        except Exception:
            logger.exception("Failed on item idx=%d (编号=%s) — skipping", idx, item.get("编号"))
            continue
        payload = rubric.model_dump()
        payload["item_idx"] = idx  # source array position (disambiguates duplicate 编号s)
        filename_for(idx).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8",
        )

    # Aggregate from per-item files (idx-named) so resume runs don't lose previously-generated items
    all_items = sorted(items_dir.glob("idx_*.json"))
    aggregated = [json.loads(p.read_text(encoding="utf-8")) for p in all_items]
    Path(args.out).write_text(
        json.dumps(aggregated, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    logger.info("Aggregated %d rubrics from %s/ → %s", len(aggregated), items_dir, args.out)


if __name__ == "__main__":
    main()
