"""Turn SciArena citations into rubric-generation context (RAG-free).

Each SciArena citation already carries a ``content`` field (~2 k chars of paper
text), so it plays the role a retrieved chunk would in the CAE pipeline. No
retrieval index is needed.
"""
from __future__ import annotations

from typing import Any, List

_EMPTY = "(no cited sources available)"


def _clean(value: Any) -> str:
    """Render a citation field as text, dropping NaN/None/empty values."""
    if value is None:
        return ""
    if isinstance(value, float):
        # bare NaN from the raw data should never surface as literal "nan"
        return "" if value != value else str(value)
    return str(value).strip()


def format_citations_as_context(citations: List[dict]) -> str:
    """Format GT citations into a numbered context block for the generator.

    Args:
        citations: List of citation dicts with ``content``/``title``/
            ``concise_authors``/``id`` fields (any may be missing or NaN).

    Returns:
        A human-readable, numbered context string; a placeholder if empty.
    """
    if not citations:
        return _EMPTY
    blocks: List[str] = []
    for i, c in enumerate(citations, 1):
        title = _clean(c.get("title")) or "Untitled"
        authors = _clean(c.get("concise_authors")) or _clean(c.get("authors"))
        cid = _clean(c.get("id"))
        content = _clean(c.get("content"))
        header = f"[Source {i} | {title}"
        if authors:
            header += f" — {authors}"
        if cid:
            header += f" (id={cid})"
        header += "]"
        blocks.append(f"{header}\n{content}")
    return "\n\n".join(blocks)


def citation_grounding(citations: List[dict]) -> dict:
    """Collect lightweight grounding metadata (ids + titles) from citations.

    Args:
        citations: List of citation dicts.

    Returns:
        Dict with ``citation_ids``, ``titles`` and ``n_citations``.
    """
    return {
        "citation_ids": [_clean(c.get("id")) for c in citations],
        "titles": [_clean(c.get("title")) for c in citations],
        "n_citations": len(citations),
    }
