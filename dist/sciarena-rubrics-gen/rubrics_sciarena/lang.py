"""Language packs for SciArena rubric generation (English / Chinese).

Selects the template directory, the weak-answer anchor, and the default
anti-hacking pitfalls for a given language code.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

_TEMPLATES = Path(__file__).parent / "templates"

LANGS = ("en", "zh")

WEAK_ANSWERS = {
    "en": "I don't know.",
    "zh": "我不知道。",
}

# Two mandatory, content-agnostic style pitfalls injected into every rubric.
# Weights reduced (was 4/3) to trim the style-tax / score-ceiling compression
# documented in the v2.0/v3.0 audit; these are the canonical weights and
# rubrics_sciarena.refiner normalizes any generator-emitted copy back to them.
EN_PITFALLS: List[dict] = [
    {
        "text": "The answer opens with boilerplate, filler, or meta-commentary "
                "instead of substantive content",
        "category": "Pitfall", "weight": 3, "sign": "negative",
        "criterion_type": "anti_hacking",
    },
    {
        "text": "The answer is padded with lengthy off-topic background or "
                "repeats itself without adding information",
        "category": "Pitfall", "weight": 2, "sign": "negative",
        "criterion_type": "anti_hacking",
    },
]

ZH_PITFALLS: List[dict] = [
    {
        "text": "回答以套话、开场白或元评论开头，而没有实质内容",
        "category": "Pitfall", "weight": 3, "sign": "negative",
        "criterion_type": "anti_hacking",
    },
    {
        "text": "回答冗长，包含大量与问题无关的背景铺垫或重复，没有补充有效信息",
        "category": "Pitfall", "weight": 2, "sign": "negative",
        "criterion_type": "anti_hacking",
    },
]

_PITFALLS = {"en": EN_PITFALLS, "zh": ZH_PITFALLS}


def _check(lang: str) -> None:
    if lang not in LANGS:
        raise ValueError(f"Unsupported language {lang!r}; expected one of {LANGS}")


def template_dir(lang: str) -> Path:
    """Return the template directory for ``lang``."""
    _check(lang)
    return _TEMPLATES / lang


def weak_answer(lang: str) -> str:
    """Return the weak-answer anchor string for ``lang``."""
    _check(lang)
    return WEAK_ANSWERS[lang]


def default_pitfalls(lang: str) -> List[dict]:
    """Return a fresh copy of the default pitfalls for ``lang``."""
    _check(lang)
    return [dict(p) for p in _PITFALLS[lang]]
