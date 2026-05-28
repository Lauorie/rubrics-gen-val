"""CLI: load indexes, retrieve+generate answers for the 94 questions -> predictions.jsonl."""
from __future__ import annotations
import argparse
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv
from pymilvus import MilvusClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cae_rag.config import Config, set_seed
from cae_rag.generate import generate_all
from cae_rag.index import COLLECTION, load_bm25, load_chunks, make_openai_client
from cae_rag.retrieve import HybridRetriever

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")
logger = logging.getLogger("run_rag")


def load_questions(path: Path) -> list[dict]:
    """Read ONLY item_idx + question. Never reference_answer/criteria (anti-cheat)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return [{"item_idx": r["item_idx"], "question": r["question"]} for r in data]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", default="/home/juli/RLM/data/CAE-v2.0-1-rubrics.json", type=Path)
    p.add_argument("--out-dir", default="outputs", type=Path)
    p.add_argument("--limit", type=int, default=0, help="0 = all; N = first N items (smoke test)")
    p.add_argument("--workers", type=int, default=8)
    args = p.parse_args()

    load_dotenv()
    set_seed(42)
    cfg = Config.from_env()

    chunks = load_chunks(str(args.out_dir / "chunks.jsonl"))
    chunk_lookup = {c.chunk_id: (c.text, c.doc) for c in chunks}
    bm25, chunk_ids = load_bm25(str(args.out_dir / "bm25.pkl"))
    milvus = MilvusClient(str(args.out_dir / "cae_rag.db"))
    milvus.load_collection(COLLECTION)  # required: a fresh process must load before search
    client = make_openai_client(cfg.api_key, cfg.base_url)

    def embed_query(q: str) -> list[float]:
        return client.embeddings.create(model=cfg.embedding_model, input=[q]).data[0].embedding

    retriever = HybridRetriever(
        milvus=milvus, bm25=bm25, chunk_ids=chunk_ids, chunk_lookup=chunk_lookup,
        embed_query=embed_query, top_k=cfg.top_k, candidate_pool=cfg.candidate_pool, rrf_k=cfg.rrf_k,
    )

    items = load_questions(args.dataset)
    if args.limit:
        items = items[: args.limit]
    logger.info("Answering %d questions", len(items))

    results = generate_all(client, items, retriever, cfg.gen_model, cfg.gen_temperature, args.workers)

    out_path = args.out_dir / "predictions.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps({"item_idx": r["item_idx"], "answer": r["answer"],
                                "retrieved": r.get("retrieved", [])}, ensure_ascii=False) + "\n")
    n_empty = sum(1 for r in results if not r["answer"])
    logger.info("Wrote %d predictions to %s (%d empty/errored)", len(results), out_path, n_empty)


if __name__ == "__main__":
    main()
