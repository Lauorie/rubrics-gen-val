"""High-level retrieval: page-first, semantic fallback."""
from __future__ import annotations

from typing import List, Tuple

from rubrics.chunker import ChunkRecord, doc_slug_from_filename
from rubrics.index import ChunkIndex
from rubrics.source_parser import SourceRef, DOC_ALIASES


def retrieve_context(
    question: str,
    refs: List[SourceRef],
    index: ChunkIndex,
    k: int = 3,
) -> Tuple[List[ChunkRecord], str]:
    """Return (chunks, ground_status).

    Strategy:
      1. If refs resolve to a known doc + pages, search within that scope
         (score_threshold=0 — honor page constraint even at low similarity).
      2. Else if doc resolves but no pages, search within the doc.
      3. Else fall back to semantic search over the whole corpus.

    Args:
        question: Natural-language query string.
        refs: Parsed source references from the 来源 field.
        index: The ChunkIndex to search against.
        k: Maximum number of chunks to return.

    Returns:
        A tuple of (chunk_list, status_string) where status is one of:
        ``"page_specific"``, ``"doc_only"``, or ``"fallback_semantic"``.
    """
    if refs:
        all_hits: List[ChunkRecord] = []
        seen: set = set()
        had_pages = False
        for r in refs:
            filename = DOC_ALIASES.get(r.doc_alias)
            if filename is None:
                continue
            slug = doc_slug_from_filename(filename)
            if r.pages is not None:
                had_pages = True
                hits = index.search_within(
                    question, k=k, doc_slug=slug, pages=r.pages, score_threshold=0.0,
                )
            else:
                hits = index.search_within(
                    question, k=k, doc_slug=slug, pages=None, score_threshold=0.0,
                )
            for h in hits:
                if h.chunk_id not in seen:
                    all_hits.append(h)
                    seen.add(h.chunk_id)
        if all_hits:
            status = "page_specific" if had_pages else "doc_only"
            return all_hits[:k], status
    # fallback: no refs resolved or no hits found within constrained scope
    return index.search(question, k=k), "fallback_semantic"
