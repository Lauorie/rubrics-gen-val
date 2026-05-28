"""CLI: ingest CAE-MDs, embed, build Milvus Lite + BM25 indexes."""
from __future__ import annotations
import argparse
import hashlib
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cae_rag.config import Config, set_seed
from cae_rag.index import build_bm25, build_milvus, embed_texts, make_openai_client, save_chunks
from cae_rag.ingest import load_and_chunk

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")
logger = logging.getLogger("build_index")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--docs-dir", default="/home/juli/RLM/CAE-MDs", type=Path)
    p.add_argument("--out-dir", default="outputs", type=Path)
    args = p.parse_args()

    load_dotenv()
    set_seed(42)
    cfg = Config.from_env()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    chunks = load_and_chunk(args.docs_dir, cfg.chunk_size, cfg.chunk_overlap)
    save_chunks(chunks, str(args.out_dir / "chunks.jsonl"))

    client = make_openai_client(cfg.api_key, cfg.base_url)
    vectors = embed_texts(client, [c.text for c in chunks], cfg.embedding_model)
    assert len(vectors[0]) == cfg.embed_dim, f"embed dim {len(vectors[0])} != {cfg.embed_dim}"

    build_milvus(str(args.out_dir / "cae_rag.db"), chunks, vectors, cfg.embed_dim)
    build_bm25(chunks, str(args.out_dir / "bm25.pkl"))

    manifest = hashlib.sha256(
        "".join(c.chunk_id + c.text for c in chunks).encode("utf-8")
    ).hexdigest()[:12]
    (args.out_dir / "run_meta.json").write_text(
        json.dumps({"n_chunks": len(chunks), "embed_dim": cfg.embed_dim,
                    "chunk_manifest_sha": manifest, "embedding_model": cfg.embedding_model},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Index built: %d chunks, manifest %s", len(chunks), manifest)


if __name__ == "__main__":
    main()
