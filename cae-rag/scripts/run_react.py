"""CLI: run the ReAct agent over the 94 questions -> predictions_react.jsonl."""
from __future__ import annotations
import argparse
import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv
from pymilvus import MilvusClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cae_rag.config import Config, set_seed
from cae_rag.index import COLLECTION, load_bm25, load_chunks, make_openai_client
from cae_rag.react import ReactAgent, ReactConfig
from cae_rag.retrieve import HybridRetriever

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")
logger = logging.getLogger("run_react")


def load_questions(path: Path) -> list[dict]:
    """Read ONLY item_idx + question. Never reference_answer/criteria (anti-cheat)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return [{"item_idx": r["item_idx"], "question": r["question"]} for r in data]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", default="/home/juli/RLM/data/CAE-v2.0-1-rubrics.json", type=Path)
    p.add_argument("--out-dir", default="outputs", type=Path)
    p.add_argument("--limit", type=int, default=0, help="0 = all; N = first N items (smoke)")
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--max-steps", type=int, default=6)
    args = p.parse_args()

    load_dotenv()
    set_seed(42)
    cfg = Config.from_env()
    rcfg = ReactConfig(max_steps=args.max_steps)

    chunks = load_chunks(str(args.out_dir / "chunks.jsonl"))
    chunk_lookup = {c.chunk_id: (c.text, c.doc) for c in chunks}
    bm25, chunk_ids = load_bm25(str(args.out_dir / "bm25.pkl"))
    milvus = MilvusClient(str(args.out_dir / "cae_rag.db"))
    milvus.load_collection(COLLECTION)
    client = make_openai_client(cfg.api_key, cfg.base_url)

    def embed_query(q: str) -> list[float]:
        return client.embeddings.create(model=cfg.embedding_model, input=[q]).data[0].embedding

    retriever = HybridRetriever(
        milvus=milvus, bm25=bm25, chunk_ids=chunk_ids, chunk_lookup=chunk_lookup,
        embed_query=embed_query, top_k=rcfg.search_k,
        candidate_pool=cfg.candidate_pool, rrf_k=cfg.rrf_k,
    )
    doc_names = sorted({c.doc for c in chunks})
    agent = ReactAgent(client=client, retriever=retriever, chunks=chunks, cfg=rcfg,
                       gen_model=cfg.gen_model, doc_names=doc_names)

    items = load_questions(args.dataset)
    if args.limit:
        items = items[: args.limit]
    logger.info("ReAct answering %d questions (max_steps=%d)", len(items), rcfg.max_steps)

    def _one(item: dict) -> dict:
        try:
            res = agent.answer(item["question"])
            return {"item_idx": item["item_idx"], "answer": res["answer"], "steps": res["steps"]}
        except Exception as e:  # noqa: BLE001 - per-item failure, keep going
            logger.error("item %s failed: %s", item["item_idx"], e)
            return {"item_idx": item["item_idx"], "answer": "", "steps": 0, "error": str(e)}

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        results = list(ex.map(_one, items))
    results.sort(key=lambda r: r["item_idx"])

    out_path = args.out_dir / "predictions_react.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    n_empty = sum(1 for r in results if not r["answer"])
    avg_steps = sum(r["steps"] for r in results) / max(1, len(results))
    logger.info("Wrote %d predictions to %s (%d empty, avg_steps=%.2f)",
                len(results), out_path, n_empty, avg_steps)


if __name__ == "__main__":
    main()
