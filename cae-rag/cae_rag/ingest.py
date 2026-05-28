"""Load CAE markdown docs, clean, and chunk into 512-token windows."""
from __future__ import annotations
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import tiktoken

logger = logging.getLogger(__name__)

_ENC = tiktoken.get_encoding("cl100k_base")
_IMG_LINE = re.compile(r"^\s*!\[.*?\]\(.*?\)\s*$", re.MULTILINE)
_ARTIFACT_LINE = re.compile(r"^\s*\*{1,2}\s*$", re.MULTILINE)
_MULTI_BLANK = re.compile(r"\n{3,}")


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc: str
    text: str
    token_start: int
    token_end: int


def clean_markdown(raw: str) -> str:
    """Drop image lines and standalone artifact lines; collapse blank runs."""
    text = _IMG_LINE.sub("", raw)
    text = _ARTIFACT_LINE.sub("", text)
    text = _MULTI_BLANK.sub("\n\n", text)
    return text.strip()


def chunk_text(text: str, doc: str, chunk_size: int = 512, overlap: int = 64) -> list[Chunk]:
    """Sliding-window chunk by token count. step = chunk_size - overlap."""
    toks = _ENC.encode(text)
    if not toks:
        return []
    step = chunk_size - overlap
    chunks: list[Chunk] = []
    idx = 0
    for start in range(0, len(toks), step):
        window = toks[start : start + chunk_size]
        chunks.append(
            Chunk(
                chunk_id=f"{doc}::{idx}",
                doc=doc,
                text=_ENC.decode(window),
                token_start=start,
                token_end=start + len(window),
            )
        )
        idx += 1
        if start + chunk_size >= len(toks):
            break
    return chunks


def load_and_chunk(docs_dir: Path, chunk_size: int = 512, overlap: int = 64) -> list[Chunk]:
    """Load every .md under docs_dir, clean, chunk. doc name = file stem."""
    all_chunks: list[Chunk] = []
    for md_path in sorted(Path(docs_dir).glob("*.md")):
        cleaned = clean_markdown(md_path.read_text(encoding="utf-8"))
        doc_chunks = chunk_text(cleaned, doc=md_path.stem, chunk_size=chunk_size, overlap=overlap)
        logger.info("Chunked %s -> %d chunks", md_path.name, len(doc_chunks))
        all_chunks.extend(doc_chunks)
    logger.info("Total chunks: %d from %s", len(all_chunks), docs_dir)
    return all_chunks
