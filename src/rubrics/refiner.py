"""Stage 2: atomicity check, dedup, pitfall injection."""
from __future__ import annotations
import re
from typing import Callable, List, Optional

import numpy as np

DEFAULT_PITFALLS = [
    {
        "text": "回答以套话/开场白/元评论开头而无实质内容",
        "category": "Pitfall", "weight": 4, "sign": "negative",
        "criterion_type": "anti_hacking",
    },
    {
        "text": "回答篇幅冗长，包含大量与问题无关的背景铺垫或重复",
        "category": "Pitfall", "weight": 3, "sign": "negative",
        "criterion_type": "anti_hacking",
    },
]

_COMPOUND_SPLIT_RE = re.compile(r"\s*[，,]\s*并\s*|\s*[，,]\s*同时\s*|\s*[，,]\s*且\s*|\s*并\s*")


def _renumber(criteria: List[dict]) -> List[dict]:
    return [{**c, "id": f"c{i+1}"} for i, c in enumerate(criteria)]


def _ensure_default_pitfalls(criteria: List[dict]) -> List[dict]:
    existing_texts = {c["text"] for c in criteria if c["category"] == "Pitfall"}
    to_add = [p for p in DEFAULT_PITFALLS if p["text"] not in existing_texts]
    return criteria + to_add


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


def _split_compound(criteria: List[dict]) -> List[dict]:
    out = []
    for c in criteria:
        parts = _COMPOUND_SPLIT_RE.split(c["text"])
        parts = [p.strip() for p in parts if p.strip() and len(p.strip()) >= 4]
        if len(parts) <= 1:
            out.append(c)
            continue
        # explode into one criterion per part, weight unchanged
        for p in parts:
            out.append({**c, "text": p})
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
