"""Stage 2: atomicity check, dedup, pitfall injection."""
from __future__ import annotations
import re
from typing import Callable, List, Optional

import numpy as np

# Two mandatory, content-agnostic style pitfalls injected into every rubric.
# Weights reduced (was 4/3) to trim the style-tax / score-ceiling compression
# documented in the v2.0 audit; these are the canonical weights and refiner
# normalizes any generator-emitted copy back to them.
DEFAULT_PITFALLS = [
    {
        "text": "回答以套话/开场白/元评论开头而无实质内容",
        "category": "Pitfall", "weight": 3, "sign": "negative",
        "criterion_type": "anti_hacking",
    },
    {
        "text": "回答篇幅冗长，包含大量与问题无关的背景铺垫或重复",
        "category": "Pitfall", "weight": 2, "sign": "negative",
        "criterion_type": "anti_hacking",
    },
]

# Canonical weight lookup for the mandatory style pitfalls.
_CANONICAL_PITFALL_WEIGHT = {p["text"]: p["weight"] for p in DEFAULT_PITFALLS}

# Split ONLY on punctuation-anchored clause boundaries. The previous bare "并"
# alternative matched mid-word (合并/归并 -> 合 | 并, 归 | 并), producing
# unjudgeable 2-4 char phantom criteria; that alternative is removed.
_COMPOUND_SPLIT_RE = re.compile(r"[，,]\s*(?:并|同时|且)\s*|\s*[；;]\s*")

# A split fragment shorter than this (in chars) is treated as a stub: keep the
# original criterion intact rather than emit it.
_MIN_FRAGMENT_LEN = 6


def _renumber(criteria: List[dict]) -> List[dict]:
    return [{**c, "id": f"c{i+1}"} for i, c in enumerate(criteria)]


def _ensure_default_pitfalls(criteria: List[dict]) -> List[dict]:
    # Normalize any generator-emitted copy of a mandatory style pitfall to its
    # canonical weight, so the reduced weights are guaranteed regardless of what
    # the model emitted.
    normalized = [
        {**c, "weight": _CANONICAL_PITFALL_WEIGHT[c["text"]]}
        if c["text"] in _CANONICAL_PITFALL_WEIGHT else c
        for c in criteria
    ]
    existing_texts = {c["text"] for c in normalized if c["category"] == "Pitfall"}
    to_add = [p for p in DEFAULT_PITFALLS if p["text"] not in existing_texts]
    return normalized + to_add


def _dedup_by_embedding(
    criteria: List[dict], embed_fn: Callable[[list[str]], np.ndarray], threshold: float = 0.9,
) -> List[dict]:
    if not criteria:
        return criteria
    texts = [c["text"] for c in criteria]
    emb = embed_fn(texts)
    emb = emb / np.linalg.norm(emb, axis=1, keepdims=True).clip(min=1e-8)
    keep = []
    seen_vecs: List[np.ndarray] = []
    for c, v in zip(criteria, emb):
        is_dup = any(np.dot(v, sv) > threshold for sv in seen_vecs)
        if not is_dup:
            keep.append(c)
            seen_vecs.append(v)
    return keep


def _distribute_weight(total: int, k: int) -> List[int]:
    """Split `total` weight across `k` fragments so the sum is preserved and
    each fragment gets >= 1 (earliest fragments absorb the remainder)."""
    base, rem = divmod(total, k)
    return [base + (1 if i < rem else 0) for i in range(k)]


def _split_compound(criteria: List[dict]) -> List[dict]:
    out = []
    for c in criteria:
        parts = [p.strip() for p in _COMPOUND_SPLIT_RE.split(c["text"]) if p.strip()]
        # Keep the criterion intact unless it cleanly yields >= 2 substantial
        # fragments AND the weight can be split so each fragment stays >= 1.
        if (
            len(parts) <= 1
            or any(len(p) < _MIN_FRAGMENT_LEN for p in parts)
            or c["weight"] < len(parts)
        ):
            out.append(c)
            continue
        # Explode into one atomic criterion per part, preserving total weight.
        weights = _distribute_weight(c["weight"], len(parts))
        for p, w in zip(parts, weights):
            out.append({**c, "text": p, "weight": w})
    return out


def refine_criteria(
    criteria: List[dict],
    embed_fn: Optional[Callable[[list[str]], np.ndarray]] = None,
    *,
    split_compound: bool = True,
    dedup_threshold: float = 0.9,
) -> List[dict]:
    work = list(criteria)
    if split_compound:
        work = _split_compound(work)
    if embed_fn is not None:
        work = _dedup_by_embedding(work, embed_fn, dedup_threshold)
    work = _ensure_default_pitfalls(work)
    return _renumber(work)
