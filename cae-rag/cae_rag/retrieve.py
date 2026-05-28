"""Hybrid retrieval: dense (Milvus) + sparse (BM25) fused with RRF."""
from __future__ import annotations
import logging
from collections import defaultdict
from typing import Any, Callable, TypeVar

import jieba
import numpy as np

from cae_rag.index import COLLECTION

logger = logging.getLogger(__name__)

T = TypeVar("T")


def rrf_fuse(dense_ranked: list[T], sparse_ranked: list[T], k: int = 60, top_k: int = 5) -> list[T]:
    """Reciprocal Rank Fusion. rank is 1-based: contribution = 1/(k + rank).

    Ties broken by the natural sort order of the id (deterministic).
    """
    scores: dict[T, float] = defaultdict(float)
    for rank, cid in enumerate(dense_ranked, start=1):
        scores[cid] += 1.0 / (k + rank)
    for rank, cid in enumerate(sparse_ranked, start=1):
        scores[cid] += 1.0 / (k + rank)
    ordered = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    return [cid for cid, _ in ordered[:top_k]]


class HybridRetriever:
    """Dense (Milvus) + sparse (BM25) retrieval fused with RRF, returns top-k chunks."""

    def __init__(self, milvus: Any, bm25: Any, chunk_ids: list[str],
                 chunk_lookup: dict[str, tuple[str, str]], embed_query: Callable[[str], list[float]],
                 top_k: int = 5, candidate_pool: int = 20, rrf_k: int = 60) -> None:
        """Initialise retriever with pre-built indexes and a query embedding function.

        Args:
            milvus: MilvusClient (or compatible) used for dense search.
            bm25: BM25Okapi (or compatible) used for sparse scoring.
            chunk_ids: Ordered list of chunk ids matching the BM25 index rows.
            chunk_lookup: Mapping chunk_id -> (text, doc).
            embed_query: Callable[[str], list[float]] that returns the query vector.
            top_k: Number of final chunks to return.
            candidate_pool: Candidates drawn from each retriever before fusion.
            rrf_k: Smoothing constant for RRF scoring.
        """
        self.milvus = milvus
        self.bm25 = bm25
        self.chunk_ids = chunk_ids
        self.chunk_lookup = chunk_lookup
        self.embed_query = embed_query
        self.top_k = top_k
        self.candidate_pool = candidate_pool
        self.rrf_k = rrf_k

    def _dense(self, query: str) -> list[str]:
        """Return top-candidate_pool chunk ids via Milvus dense search."""
        qv = self.embed_query(query)
        res = self.milvus.search(
            collection_name=COLLECTION, data=[qv],
            limit=self.candidate_pool, output_fields=["chunk_id", "text", "doc"],
        )
        return [h["entity"]["chunk_id"] for h in res[0]]

    def _sparse(self, query: str) -> list[str]:
        """Return top-candidate_pool chunk ids via BM25 scoring."""
        tokens = list(jieba.cut(query))
        scores = self.bm25.get_scores(tokens)
        order = np.argsort(scores)[::-1][: self.candidate_pool]
        return [self.chunk_ids[i] for i in order]

    def retrieve(self, query: str) -> list[dict]:
        """Retrieve and fuse dense + sparse results, returning top_k chunk dicts.

        Args:
            query: Natural-language query string.

        Returns:
            List of dicts with keys ``chunk_id``, ``text``, and ``doc``.
        """
        dense_ids = self._dense(query)
        sparse_ids = self._sparse(query)
        fused = rrf_fuse(dense_ids, sparse_ids, k=self.rrf_k, top_k=self.top_k)
        out = []
        for cid in fused:
            text, doc = self.chunk_lookup[cid]
            out.append({"chunk_id": cid, "text": text, "doc": doc})
        return out
