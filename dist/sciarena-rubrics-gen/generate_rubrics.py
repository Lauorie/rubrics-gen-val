"""Generate English rubrics for the SciArena (paperbank) dataset.

Two passes over the input file:
  Pass 1 (cheap, deterministic): stream items, select the GT side by human
          ``vote`` (Tie broken by a per-id seeded RNG), write a cleaned dataset
          keeping only the winning response + its citations.
  Pass 2 (LLM): for each cleaned record, run the 3-stage rubric pipeline using
          the GT citations as context (no RAG). Per-item files support --resume.

Examples:
    # quick validation on the first 3 train items
    python run/05_generate_rubrics_sciarena.py \
        --data sciarena-papers/SciArena-with-paperbank/train.json \
        --rubrics-out sciarena-papers/SciArena-with-paperbank/train_rubrics.json \
        --cleaned-out sciarena-papers/SciArena-with-paperbank/train_cleaned.jsonl \
        --items-dir runs/sciarena/train_items --limit 3
"""
from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import logging
import os
import random
import sys
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

# Allow running as a plain script: ensure repo's src/ is importable.
_SRC = Path(__file__).resolve().parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from rubrics.llm_client import LLMClient, LLMConfig
from rubrics_sciarena.data_loader import iter_items, read_jsonl, select_gt, write_jsonl
from rubrics_sciarena.pipeline import build_rubric_for_item_sciarena
from rubrics_sciarena.translate import translate_record_to_zh

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)
logger = logging.getLogger("generate_rubrics_sciarena")


def set_seed(seed: int = 42) -> None:
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", required=True, type=Path, help="Input SciArena JSON (train/test)")
    p.add_argument("--rubrics-out", required=True, type=Path, help="Aggregated rubrics JSON output")
    p.add_argument("--cleaned-out", required=True, type=Path, help="Cleaned dataset JSONL output")
    p.add_argument("--items-dir", required=True, type=Path, help="Per-item rubric file directory")
    p.add_argument("--limit", type=int, default=None, help="Only process first N items")
    p.add_argument("--dry-run", action="store_true", help="Stop after 1 item")
    p.add_argument("--resume", action="store_true", help="Skip items whose per-item file exists")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--lang", choices=("en", "zh"), default="en",
                   help="Rubric language. 'zh' also translates question+GT answer to Chinese "
                        "(citations stay English).")
    p.add_argument("--item-concurrency", type=int, default=4, help="Concurrent items")
    p.add_argument("--judge-concurrency", type=int, default=8, help="Concurrent judge calls per item")
    p.add_argument("--translate-concurrency", type=int, default=16, help="Concurrent translation calls")
    p.add_argument("--gen-model", default=None, help="Generator model (default: env LLM_MODEL)")
    p.add_argument("--judge-model", default="openai/gpt-5.4",
                   help="Stage-3 judge model (default: openai/gpt-5.4, stronger than the generator)")
    return p.parse_args()


def select_records(data: Path, seed: int, limit: Optional[int]) -> List[dict]:
    """Stream the input and select the GT side per human vote (cheap, no LLM).

    Records with no usable ground truth (e.g. vote "bad" = both answers poor)
    are skipped. ``limit`` counts *input* items scanned, not records kept.
    """
    records: List[dict] = []
    skipped: dict = {}
    for i, raw in enumerate(iter_items(data)):
        if limit is not None and i >= limit:
            break
        # Per-id seeded RNG -> reproducible Tie-breaking, order-independent.
        rng = random.Random(f"{seed}:{raw.get('id')}")
        try:
            records.append(select_gt(raw, rng))
        except ValueError:
            vote = str(raw.get("vote")).strip().lower()
            skipped[vote] = skipped.get(vote, 0) + 1
    if skipped:
        logger.info("Skipped %d items with no usable GT: %s", sum(skipped.values()), skipped)
    logger.info("Selected %d GT records", len(records))
    return records


async def translate_records(
    records: List[dict], client: LLMClient, *, concurrency: int,
) -> List[dict]:
    """Translate each record's question + GT answer to Chinese (concurrent)."""
    sem = asyncio.Semaphore(concurrency)
    done = 0

    async def one(rec: dict) -> dict:
        nonlocal done
        async with sem:
            try:
                out = await translate_record_to_zh(rec, client)
            except Exception:
                logger.exception("Translation failed for id=%s — keeping English", rec.get("id"))
                return rec
            done += 1
            if done % 50 == 0:
                logger.info("  translated %d/%d", done, len(records))
            return out

    translated = await asyncio.gather(*[one(r) for r in records])
    logger.info("Translated %d records to Chinese", done)
    return list(translated)


def write_cleaned(records: List[dict], cleaned_out: Path) -> None:
    write_jsonl(records, cleaned_out)
    logger.info("Wrote %d cleaned records -> %s", len(records), cleaned_out)


async def pass2_generate(
    records: List[dict], items_dir: Path, gen_client: LLMClient, judge_client: LLMClient,
    *, lang: str, item_concurrency: int, judge_concurrency: int, resume: bool, dry_run: bool,
) -> None:
    """Generate a rubric per cleaned record, writing per-item files."""
    items_dir.mkdir(parents=True, exist_ok=True)
    if dry_run:
        records = records[:1]

    def item_path(i: int) -> Path:
        return items_dir / f"item_{i:06d}.json"

    todo = [
        (i, r) for i, r in enumerate(records)
        if not (resume and item_path(i).exists())
    ]
    logger.info("Pass 2: %d/%d items to generate (resume=%s)", len(todo), len(records), resume)

    sem = asyncio.Semaphore(item_concurrency)
    done = 0

    async def worker(i: int, rec: dict) -> None:
        nonlocal done
        async with sem:
            try:
                rubric = await build_rubric_for_item_sciarena(
                    rec, gen_client=gen_client, judge_client=judge_client,
                    lang=lang, concurrency=judge_concurrency,
                )
            except Exception:
                logger.exception("Failed on item %d (id=%s) — skipping", i, rec.get("id"))
                return
            payload = rubric.model_dump()
            payload["item_idx"] = i
            item_path(i).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8",
            )
            done += 1
            if done % 25 == 0:
                logger.info("  generated %d/%d", done, len(todo))

    await asyncio.gather(*[worker(i, r) for i, r in todo])
    logger.info("Pass 2: generated %d rubrics", done)


def aggregate(items_dir: Path, rubrics_out: Path) -> int:
    """Collect per-item files into a single rubrics JSON array."""
    files = sorted(items_dir.glob("item_*.json"))
    rubrics = [json.loads(p.read_text(encoding="utf-8")) for p in files]
    rubrics_out.parent.mkdir(parents=True, exist_ok=True)
    rubrics_out.write_text(json.dumps(rubrics, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Aggregated %d rubrics -> %s", len(rubrics), rubrics_out)
    return len(rubrics)


def main() -> None:
    args = _parse_args()
    set_seed(args.seed)
    load_dotenv()

    base = LLMConfig.from_env()
    gen_cfg = dataclasses.replace(base, model=args.gen_model) if args.gen_model else base
    judge_cfg = dataclasses.replace(base, model=args.judge_model)
    gen_client = LLMClient(gen_cfg)
    judge_client = LLMClient(judge_cfg)
    logger.info("Generator model=%s | Judge model=%s", gen_cfg.model, judge_cfg.model)

    # Pass 1: build (or reuse) the cleaned dataset.
    if args.resume and args.cleaned_out.exists():
        records = read_jsonl(args.cleaned_out)
        logger.info("Resume: loaded %d cleaned records from %s", len(records), args.cleaned_out)
    else:
        records = select_records(args.data, args.seed, args.limit)
        if args.lang == "zh":
            records = asyncio.run(translate_records(
                records, gen_client, concurrency=args.translate_concurrency,
            ))
        write_cleaned(records, args.cleaned_out)

    # Pass 2: generate one rubric per record.
    asyncio.run(pass2_generate(
        records, args.items_dir, gen_client, judge_client,
        lang=args.lang, item_concurrency=args.item_concurrency,
        judge_concurrency=args.judge_concurrency,
        resume=args.resume, dry_run=args.dry_run,
    ))
    aggregate(args.items_dir, args.rubrics_out)


if __name__ == "__main__":
    main()
