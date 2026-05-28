"""Build and load the dense (Milvus Lite) and sparse (BM25) indexes."""
from __future__ import annotations
import json
import logging
import pickle
from pathlib import Path
from typing import Any

import jieba
from openai import OpenAI
from pymilvus import MilvusClient
from rank_bm25 import BM25Okapi

from cae_rag.ingest import Chunk

logger = logging.getLogger(__name__)

COLLECTION = "cae_chunks"


def make_openai_client(api_key: str, base_url: str) -> OpenAI:
    return OpenAI(api_key=api_key, base_url=base_url)


def embed_texts(client: Any, texts: list[str], model: str, batch_size: int = 64) -> list[list[float]]:
    """Embed texts in batches, preserving input order."""
    vecs: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        resp = client.embeddings.create(model=model, input=batch)
        vecs.extend(d.embedding for d in resp.data)
        logger.info("Embedded %d/%d", min(i + batch_size, len(texts)), len(texts))
    return vecs


def build_milvus(db_path: str, chunks: list[Chunk], vectors: list[list[float]], dim: int) -> None:
    """(Re)create the Milvus Lite collection and insert chunk vectors."""
    client = MilvusClient(db_path)
    if client.has_collection(COLLECTION):
        client.drop_collection(COLLECTION)
    client.create_collection(collection_name=COLLECTION, dimension=dim, metric_type="COSINE", auto_id=False)
    rows = [
        {"id": i, "vector": vectors[i], "text": c.text, "doc": c.doc, "chunk_id": c.chunk_id}
        for i, c in enumerate(chunks)
    ]
    client.insert(COLLECTION, rows)
    client.load_collection(COLLECTION)
    logger.info("Inserted %d vectors into Milvus Lite at %s", len(rows), db_path)


def build_bm25(chunks: list[Chunk], pkl_path: str) -> None:
    """Tokenize chunks with jieba and pickle a BM25Okapi index + chunk order."""
    tokenized = [list(jieba.cut(c.text)) for c in chunks]
    bm25 = BM25Okapi(tokenized)
    payload = {"bm25": bm25, "chunk_ids": [c.chunk_id for c in chunks]}
    Path(pkl_path).write_bytes(pickle.dumps(payload))
    logger.info("Built BM25 over %d chunks -> %s", len(chunks), pkl_path)


def save_chunks(chunks: list[Chunk], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c.__dict__, ensure_ascii=False) + "\n")


def load_chunks(path: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            chunks.append(Chunk(**json.loads(line)))
    return chunks


def load_bm25(pkl_path: str) -> tuple[BM25Okapi, list[str]]:
    payload = pickle.loads(Path(pkl_path).read_bytes())
    return payload["bm25"], payload["chunk_ids"]
