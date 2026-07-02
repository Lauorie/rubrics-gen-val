"""Stage 2 (SciArena): dedup + default-pitfall injection + renumbering.

English-language counterpart of :mod:`rubrics.refiner`. Compound splitting is
disabled by default because the English conjunction "and" is too common to
split on safely; the generator prompt already enforces atomic criteria.
"""
from __future__ import annotations

from typing import Callable, List, Optional

import numpy as np

from rubrics_sciarena.lang import EN_PITFALLS, ZH_PITFALLS, default_pitfalls

# Back-compat alias: the English defaults.
DEFAULT_PITFALLS = EN_PITFALLS

# Canonical weight lookup for the two mandatory style pitfalls, covering both
# languages. The refiner normalizes any generator-emitted copy back to these
# reduced weights (3/2), so the reduction holds regardless of what the model
# emitted (mirrors rubrics.refiner in the CAE pipeline).
_CANONICAL_PITFALL_WEIGHT = {
    p["text"]: p["weight"] for p in (*EN_PITFALLS, *ZH_PITFALLS)
}


def _renumber(criteria: List[dict]) -> List[dict]:
    return [{**c, "id": f"c{i + 1}"} for i, c in enumerate(criteria)]


def _ensure_default_pitfalls(criteria: List[dict], pitfalls: List[dict]) -> List[dict]:
    # Normalize any generator-emitted copy of a mandatory style pitfall to its
    # canonical (reduced) weight, then append any mandatory pitfall still absent.
    normalized = [
        {**c, "weight": _CANONICAL_PITFALL_WEIGHT[c["text"]]}
        if c["text"] in _CANONICAL_PITFALL_WEIGHT else c
        for c in criteria
    ]
    existing = {c["text"] for c in normalized if c.get("category") == "Pitfall"}
    to_add = [p for p in pitfalls if p["text"] not in existing]
    return normalized + to_add


def _dedup_by_embedding(
    criteria: List[dict], embed_fn: Callable[[list[str]], np.ndarray], threshold: float = 0.9,
) -> List[dict]:
    if not criteria:
        return criteria
    emb = embed_fn([c["text"] for c in criteria])
    emb = emb / np.linalg.norm(emb, axis=1, keepdims=True).clip(min=1e-8)
    keep: List[dict] = []
    seen_vecs: List[np.ndarray] = []
    for c, v in zip(criteria, emb):
        if not any(np.dot(v, sv) > threshold for sv in seen_vecs):
            keep.append(c)
            seen_vecs.append(v)
    return keep


def refine_criteria(
    criteria: List[dict],
    embed_fn: Optional[Callable[[list[str]], np.ndarray]] = None,
    *,
    lang: str = "en",
    dedup_threshold: float = 0.9,
) -> List[dict]:
    """Refine raw Stage-1 criteria into the final, numbered list.

    Args:
        criteria: Raw criteria dicts from the generator.
        embed_fn: Optional embedding function for near-duplicate removal; if
            ``None``, dedup is skipped.
        lang: Language code selecting the default anti-hacking pitfalls.
        dedup_threshold: Cosine-similarity threshold above which two criteria
            are treated as duplicates.

    Returns:
        A refined, sequentially-numbered list of criteria including default
        anti-hacking pitfalls.
    """
    work = list(criteria)
    if embed_fn is not None:
        work = _dedup_by_embedding(work, embed_fn, dedup_threshold)
    work = _ensure_default_pitfalls(work, default_pitfalls(lang))
    return _renumber(work)
