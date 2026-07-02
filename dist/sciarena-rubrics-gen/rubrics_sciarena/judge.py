"""Per-criterion judge for SciArena rubrics (English prompt).

Thin English-language counterpart of :mod:`rubrics.judge`, reusing
:class:`rubrics.llm_client.LLMClient` for transport.
"""
from __future__ import annotations

import functools
import logging

from rubrics.llm_client import LLMClient
from rubrics_sciarena.lang import template_dir

logger = logging.getLogger(__name__)


@functools.lru_cache(maxsize=None)
def judge_prompt(lang: str) -> str:
    """Load (and cache) the judge system prompt for ``lang``."""
    return (template_dir(lang) / "misalignment_judge_prompt.txt").read_text(encoding="utf-8")


def _build_user_message(question: str, candidate: str, criterion: dict) -> str:
    return (
        f"[Question] {question}\n"
        f"[Candidate answer] {candidate}\n"
        f"[Criterion] {criterion['text']}\n"
        f"[Criterion type] {criterion['criterion_type']}"
    )


async def judge_one_async(
    judge_client: LLMClient, question: str, candidate: str, criterion: dict,
    *, lang: str = "en",
) -> dict:
    """Async per-criterion judge. Returns ``{met, reason, error?}``."""
    user = _build_user_message(question, candidate, criterion)
    try:
        out = await judge_client.complete_json_async(
            system=judge_prompt(lang), user=user, schema_hint="{met, reason}",
        )
        return {"met": bool(out.get("met", False)), "reason": str(out.get("reason", ""))}
    except Exception as e:  # noqa: BLE001 - degrade gracefully on judge failure
        logger.warning("Judge call failed for criterion %s: %s", criterion.get("id"), e)
        return {"met": False, "reason": "", "error": str(e)}
