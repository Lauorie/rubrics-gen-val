"""Markdown file chunker with page tracking from mineru CDN URL markers."""
from __future__ import annotations
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

# mineru-converted MDs embed page numbers in image URLs as page_NNN_block_NNN.
# Page numbers are 0-indexed in the URL; we store them 1-indexed.
_PAGE_RE = re.compile(r"page_(\d+)_block_\d+", re.IGNORECASE)
_SAFE_SLUG_RE = re.compile(r"[^\w\-一-鿿]+")


def doc_slug_from_filename(name: str) -> str:
    """Strip extension, replace non-word/CJK chars with underscore, collapse."""
    stem = Path(name).stem
    slug = _SAFE_SLUG_RE.sub("_", stem)
    return slug.strip("_")


@dataclass(frozen=True)
class ChunkRecord:
    chunk_id: str
    doc_slug: str
    page_start: Optional[int]
    page_end: Optional[int]
    text: str


def _scan_page_anchors(text: str) -> List[tuple[int, int]]:
    """Return list of (char_offset, page_number_1indexed) anchors sorted by offset."""
    anchors = []
    for m in _PAGE_RE.finditer(text):
        page_0idx = int(m.group(1))
        anchors.append((m.start(), page_0idx + 1))
    return anchors


def _page_at_offset(anchors: List[tuple[int, int]], offset: int) -> Optional[int]:
    last = None
    for off, page in anchors:
        if off <= offset:
            last = page
        else:
            break
    return last


def chunk_markdown(
    path: Path, chunk_size: int = 400, overlap: int = 100
) -> List[ChunkRecord]:
    """Slide a window over the text. Chunk size & overlap measured in chars
    (≈ tokens for Chinese; close enough)."""
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be greater than overlap")
    text = path.read_text(encoding="utf-8")
    slug = doc_slug_from_filename(path.name)
    anchors = _scan_page_anchors(text)

    chunks: List[ChunkRecord] = []
    step = chunk_size - overlap
    idx = 0
    pos = 0
    while pos < len(text):
        end = min(pos + chunk_size, len(text))
        sub = text[pos:end]
        ps = _page_at_offset(anchors, pos)
        pe = _page_at_offset(anchors, end - 1) or ps
        chunk_id = f"{slug}:p{ps or 0}-p{pe or 0}:c{idx}"
        chunks.append(ChunkRecord(chunk_id, slug, ps, pe, sub))
        idx += 1
        pos += step
    return chunks
