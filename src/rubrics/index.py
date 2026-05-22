"""In-memory embedding index over CAE-MD chunks."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np
from sentence_transformers import SentenceTransformer

from rubrics.chunker import ChunkRecord


@dataclass
class ChunkIndex:
    """Embedding-based index over a list of :class:`ChunkRecord` objects.

    Build with :meth:`build`, then call :meth:`search` or
    :meth:`search_within` to retrieve relevant chunks by semantic similarity.
    """

    chunks: List[ChunkRecord]
    embeddings: np.ndarray
    model_name: str
    _model: Optional[SentenceTransformer] = field(default=None, repr=False, compare=False)

    @classmethod
    def build(
        cls, chunks: List[ChunkRecord], model_name: str = "BAAI/bge-base-zh-v1.5"
    ) -> "ChunkIndex":
        """Encode *chunks* and return a ready-to-query index.

        Args:
            chunks: ChunkRecords whose ``.text`` fields will be encoded.
            model_name: HuggingFace model identifier.  Must be a BGE-zh
                model that supports the asymmetric query prefix.

        Returns:
            A :class:`ChunkIndex` with normalised L2 embeddings.
        """
        model = SentenceTransformer(model_name)
        texts = [c.text for c in chunks]
        emb = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        inst = cls(chunks=chunks, embeddings=np.asarray(emb), model_name=model_name)
        inst._model = model
        return inst

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_model(self) -> SentenceTransformer:
        """Return the cached model, loading it if necessary."""
        if self._model is None:
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def _encode_query(self, q: str) -> np.ndarray:
        """Encode *q* with the BGE-zh asymmetric retrieval prefix.

        Args:
            q: Raw user query string.

        Returns:
            1-D normalised embedding vector.
        """
        prefix = "为这个句子生成表示以用于检索相关文章："
        v = self._get_model().encode(
            [prefix + q], normalize_embeddings=True, show_progress_bar=False
        )
        return np.asarray(v)[0]

    # ------------------------------------------------------------------
    # Public search API
    # ------------------------------------------------------------------

    def search(self, query: str, k: int = 3) -> List[ChunkRecord]:
        """Return the top-*k* chunks most similar to *query*.

        Args:
            query: Natural-language query string.
            k: Number of results to return.

        Returns:
            List of :class:`ChunkRecord` ordered by descending similarity.
        """
        if not self.chunks:
            return []
        qv = self._encode_query(query)
        scores = self.embeddings @ qv
        idx = np.argsort(-scores)[:k]
        return [self.chunks[i] for i in idx]

    def search_within(
        self,
        query: str,
        k: int = 3,
        doc_slug: Optional[str] = None,
        pages: Optional[Tuple[int, int]] = None,
        score_threshold: float = 0.3,
    ) -> List[ChunkRecord]:
        """Search restricted to a subset of chunks by document and/or page range.

        Args:
            query: Natural-language query string.
            k: Maximum number of results.
            doc_slug: If given, only consider chunks from this document.
            pages: Inclusive ``(page_lo, page_hi)`` page range filter.  A
                chunk is included if its page span overlaps the requested range.
            score_threshold: Minimum cosine similarity a candidate must reach
                to be included in results.  Chunks below this threshold are
                treated as non-matches and omitted.  Defaults to ``0.3``.

        Returns:
            List of matching :class:`ChunkRecord` ordered by descending
            similarity.  Returns ``[]`` when no candidates remain after
            filtering or when all candidates score below *score_threshold*.
        """
        candidates = [
            (i, c)
            for i, c in enumerate(self.chunks)
            if (doc_slug is None or c.doc_slug == doc_slug)
            and (pages is None or self._page_overlap(c, pages))
        ]
        if not candidates:
            return []
        qv = self._encode_query(query)
        sub_emb = self.embeddings[[i for i, _ in candidates]]
        scores = sub_emb @ qv
        order = np.argsort(-scores)[:k]
        return [
            candidates[j][1]
            for j in order
            if scores[j] >= score_threshold
        ]

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _page_overlap(chunk: ChunkRecord, pages: Tuple[int, int]) -> bool:
        """Return ``True`` when *chunk*'s page span overlaps *pages*.

        Args:
            chunk: Chunk whose page span to test.
            pages: ``(lo, hi)`` inclusive page range.

        Returns:
            ``True`` if the chunk's pages and the requested range share at
            least one page.
        """
        p_lo, p_hi = pages
        c_lo = chunk.page_start or 0
        c_hi = chunk.page_end or c_lo
        return not (c_hi < p_lo or c_lo > p_hi)
