"""Chunk all CAE-MDs and persist a pickled ChunkIndex for reuse."""
from __future__ import annotations
import argparse
import logging
import pickle
from pathlib import Path

from rubrics.chunker import chunk_markdown
from rubrics.index import ChunkIndex

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")
logger = logging.getLogger("build_index")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mds-dir", default="CAE-MDs")
    p.add_argument("--out", default="data/cae_chunk_index.pkl")
    p.add_argument("--chunk-size", type=int, default=400)
    p.add_argument("--overlap", type=int, default=100)
    p.add_argument("--model", default="BAAI/bge-base-zh-v1.5")
    args = p.parse_args()

    md_paths = sorted(Path(args.mds_dir).glob("*.md"))
    logger.info("Found %d MD files in %s", len(md_paths), args.mds_dir)

    all_chunks = []
    for md in md_paths:
        cs = chunk_markdown(md, chunk_size=args.chunk_size, overlap=args.overlap)
        logger.info("Chunked %s → %d chunks", md.name, len(cs))
        all_chunks.extend(cs)
    logger.info("Total chunks: %d", len(all_chunks))

    idx = ChunkIndex.build(all_chunks, model_name=args.model)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as f:
        pickle.dump(idx, f)
    logger.info("Saved index to %s", out)


if __name__ == "__main__":
    main()
