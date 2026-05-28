"""Hybrid retrieval: dense (Milvus) + sparse (BM25) fused with RRF."""
from __future__ import annotations
import logging
from collections import defaultdict
from typing import TypeVar

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
