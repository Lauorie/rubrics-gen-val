"""Parse the 「来源」 field of CAE-v2.0-1 items into (doc, pages) tuples."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# Map short alias used in 来源 to the actual filename in CAE-MDs/.
DOC_ALIASES: Dict[str, str] = {
    "Benson": "Arbitrary_Lagrangian-Eulerian_and_Fluid-Structure Interaction Numerical Simulation (Benson).md",
    "ThyssenKrupp": "oezarmut_thyssenkrupp_Fluid-Composite Structure-Interaction in Underwater Shock Simulations.md",
    "贾宪振博士论文": "PhD 基于通用程序的水下爆炸及其对结构作用的数值模拟研究.md",
    "贾宪振论文": "PhD 基于通用程序的水下爆炸及其对结构作用的数值模拟研究.md",
    "重力坝论文": "水下爆炸冲击荷载作用下混凝土重力坝的破坏模式.md",
    "混凝土重力坝破坏模式论文": "水下爆炸冲击荷载作用下混凝土重力坝的破坏模式.md",
    "混凝土重力坝论文": "水下爆炸冲击荷载作用下混凝土重力坝的破坏模式.md",
    "钢板混凝土墙": "基于ANSYS_LS-DYNA的钢板混凝土墙冲击实验的有限元分析.md",
    "液电效应": "基于LS-DYNA的液电效应冲击波数值模拟.md",
    "高速破片": "基于LS-DYNA的高速破片水中运动特性流固耦合数值模拟.md",
    "加筋结构": "不同加筋结构在水中接触爆炸下的破损规律.md",
}

# Pattern for a bare chapter reference with no doc alias, e.g. "第3章，第38页".
# In this dataset such references implicitly refer to the Benson textbook.
_CHAPTER_ONLY = re.compile(r"^第\s*\d+\s*章")

# Aliases that exist in source data but have no corresponding CAE-MDs file.
# They are recognised so that segments referencing them are not lost, but
# their doc_alias resolves to the raw key and pages are still extracted.
_EXTERNAL_ALIASES: List[str] = [
    "Souli教材",
]

# All known alias keys ordered longest-first to avoid prefix collisions.
_ALL_ALIASES: List[str] = sorted(
    list(DOC_ALIASES.keys()) + _EXTERNAL_ALIASES,
    key=len,
    reverse=True,
)

# Segment delimiters: semicolons (ASCII / full-width) and Chinese enumeration comma 、.
# Note: ordinary comma , and 、 are used both as page-list separators AND as
# segment separators, so we split on ; / ； only first, then handle 、-separated
# page lists inside page-extraction logic.
_SEGMENT_SPLIT = re.compile(r"[;；]")

# Within a segment the secondary split on full-width comma may separate docs.
# We handle this in a second pass inside _split_segment().
_SUBSEGMENT_SPLIT = re.compile(r"[，,]")

# Chinese-style page range: 第N-M页  (various dash variants)
_PAGE_RANGE = re.compile(r"第\s*(\d+)\s*[-－~～至到]\s*(\d+)\s*页")
# Chinese-style single page: 第N页
_PAGE_SINGLE = re.compile(r"第\s*(\d+)\s*页")
# English-style: pN or pN-M (may appear with comma-separated lists like p14, 15)
_PAGE_ENG_PREFIX = re.compile(r"\bp\s*(\d+)(?:\s*[-]\s*(\d+))?")


@dataclass(frozen=True)
class SourceRef:
    """A reference to a document with an optional page range."""

    doc_alias: str
    pages: Optional[Tuple[int, int]]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _detect_alias(text: str) -> Optional[str]:
    """Return the first alias key found in *text*, longest-match first."""
    for alias in _ALL_ALIASES:
        if alias in text:
            return alias
    return None


def _parse_pages(text: str) -> Optional[Tuple[int, int]]:
    """Extract the first page or page-range from *text*.

    Tries Chinese 第N页 / 第N-M页 patterns first, then English pN / pN-M.
    For multi-page lists like 第13、39页 or p14, 15, 16 we return only the
    first page number as a single-page ref — the rubric schema stores a range
    and approximating is acceptable.
    """
    m = _PAGE_RANGE.search(text)
    if m:
        return (int(m.group(1)), int(m.group(2)))

    m = _PAGE_SINGLE.search(text)
    if m:
        p = int(m.group(1))
        return (p, p)

    m = _PAGE_ENG_PREFIX.search(text)
    if m:
        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else start
        return (start, end)

    return None


def _segment_has_new_alias(seg: str, prev_alias: Optional[str]) -> bool:
    """Return True if *seg* contains an alias different from *prev_alias*."""
    alias = _detect_alias(seg)
    return alias is not None and alias != prev_alias


def _split_by_subsegment(text: str) -> List[str]:
    """Split *text* on , / ， boundaries that introduce a new doc alias."""
    parts = _SUBSEGMENT_SPLIT.split(text)
    groups: List[str] = []
    current = parts[0]
    for part in parts[1:]:
        if _detect_alias(part) is not None:
            groups.append(current.strip())
            current = part
        else:
            current = current + "," + part
    groups.append(current.strip())
    return groups


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_source(s: str) -> List[SourceRef]:
    """Parse a 来源 field string into a list of :class:`SourceRef` objects.

    Handles:
    - Semicolon-separated multi-doc references  (; / ；)
    - Comma-separated multi-doc references      (, / ，)
    - Chinese page patterns                     第N页 / 第N-M页
    - English page patterns                     pN / pN-M
    - Single-doc with no page info
    """
    if not s or not s.strip():
        return []

    # Primary split on hard delimiters (semicolons).
    primary_segments = [seg.strip() for seg in _SEGMENT_SPLIT.split(s) if seg.strip()]

    # Secondary split on commas that start a new doc reference.
    segments: List[str] = []
    for seg in primary_segments:
        segments.extend(_split_by_subsegment(seg))

    out: List[SourceRef] = []
    last_alias: Optional[str] = None

    for seg in segments:
        alias = _detect_alias(seg)
        if alias is None:
            # Fall back: bare chapter-only refs (e.g. "第3章，第38页") are
            # implicitly from the Benson textbook in this dataset.
            if _CHAPTER_ONLY.match(seg):
                alias = "Benson"
            else:
                alias = last_alias
        if alias is None:
            continue
        pages = _parse_pages(seg)
        out.append(SourceRef(doc_alias=alias, pages=pages))
        last_alias = alias

    return out
