"""SciArena data loading and ground-truth selection.

The raw SciArena files are large (train.json ≈ 1.4 GB) and contain bare ``NaN``
tokens, which are invalid for strict streaming parsers (e.g. ``ijson``). We
therefore stream items one at a time with an incremental
:class:`json.JSONDecoder` (whose default ``parse_constant`` accepts ``NaN`` /
``Infinity``), never holding the whole file in memory.
"""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Iterator, List

_WS = " \t\n\r"
_WS_COMMA = _WS + ","
_DEFAULT_CHUNK = 1 << 20  # 1 MiB read granularity


def _skip(s: str, i: int, chars: str) -> int:
    n = len(s)
    while i < n and s[i] in chars:
        i += 1
    return i


def iter_items(path: str | Path, *, chunk_size: int = _DEFAULT_CHUNK) -> Iterator[dict]:
    """Yield top-level objects from a JSON array file, one at a time.

    Tolerant of bare ``NaN`` tokens and memory-safe for multi-GB files.

    Args:
        path: Path to a JSON file whose top level is an array of objects.
        chunk_size: Number of characters read per refill.

    Yields:
        Each array element as a ``dict``.

    Raises:
        ValueError: If the top-level value is not a JSON array.
        json.JSONDecodeError: If a genuinely malformed object is encountered.
    """
    dec = json.JSONDecoder()
    with open(path, "r", encoding="utf-8") as f:
        buf = f.read(chunk_size)
        i = _skip(buf, 0, _WS)
        while i >= len(buf):
            more = f.read(chunk_size)
            if not more:
                return  # empty file
            buf += more
            i = _skip(buf, i, _WS)
        if buf[i] != "[":
            raise ValueError(f"Expected a JSON array at top level, got {buf[i]!r}")
        i += 1

        while True:
            # Advance past whitespace/commas, refilling until a token is visible.
            while True:
                i = _skip(buf, i, _WS_COMMA)
                if i < len(buf):
                    break
                more = f.read(chunk_size)
                if not more:
                    return
                buf += more
            if buf[i] == "]":
                return
            # Decode one object; refill on incomplete buffer.
            while True:
                try:
                    obj, end = dec.raw_decode(buf, i)
                    break
                except json.JSONDecodeError:
                    more = f.read(chunk_size)
                    if not more:
                        raise
                    buf += more
            yield obj
            i = end
            # Trim consumed prefix so the buffer does not grow unbounded.
            if i > chunk_size:
                buf = buf[i:]
                i = 0


def write_jsonl(records: List[dict], path: str | Path) -> None:
    """Write records as JSON Lines (one object per line)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as out:
        for rec in records:
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")


def read_jsonl(path: str | Path) -> List[dict]:
    """Read a JSON Lines file written by :func:`write_jsonl`.

    Splits on ``"\\n"`` only (not :meth:`str.splitlines`): academic text may
    contain raw U+2028/U+2029/U+0085 inside JSON strings, which json does not
    escape and which ``splitlines`` would wrongly treat as record boundaries.
    """
    text = Path(path).read_text(encoding="utf-8")
    return [json.loads(ln) for ln in text.split("\n") if ln.strip()]


def select_gt(item: dict, rng: random.Random) -> dict:
    """Select the ground-truth response/citations from a SciArena item by vote.

    Args:
        item: A raw SciArena record with keys ``vote``, ``responseA/B``,
            ``citations_a/b``, etc.
        rng: Seeded RNG used to break ``"Tie"`` votes reproducibly.

    Returns:
        A cleaned record keeping only the GT side (winning response and its
        citations); the losing side is dropped.

    Raises:
        ValueError: If ``vote`` is not one of ``"A"``, ``"B"``, ``"Tie"``.
    """
    # SciArena mixes casing ("A"/"a", "Tie"/"tie"); normalize to canonical form.
    raw_vote = str(item["vote"]).strip().lower()
    canonical = {"a": "A", "b": "B", "tie": "Tie"}.get(raw_vote)
    if canonical is None:
        raise ValueError(f"Unknown vote value: {item['vote']!r}")
    vote = canonical
    if vote == "A":
        src = "A"
    elif vote == "B":
        src = "B"
    else:
        src = rng.choice(("A", "B"))

    if src == "A":
        reference_answer = item["responseA"]
        citations = item["citations_a"]
        model = item.get("modelA")
    else:
        reference_answer = item["responseB"]
        citations = item["citations_b"]
        model = item.get("modelB")

    return {
        "id": item["id"],
        "question": item["question"],
        "question_type": item.get("question type"),
        "subject": item.get("subject"),
        "vote": vote,
        "gt_source": src,
        "reference_answer": reference_answer,
        "citations": citations,
        "model": model,
    }
