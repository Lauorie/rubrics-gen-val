"""Stage 3 (SciArena): drop criteria that misbehave on the (ref, weak) anchors.

A criterion is kept only if it is satisfied by the ground-truth reference
answer and NOT satisfied by the weak answer. Pitfall criteria are template-
validated and pass through untouched. Judging runs concurrently.
"""
from __future__ import annotations

import asyncio
import functools
import logging
from typing import Awaitable, Callable, List, Optional, Tuple

from rubrics.llm_client import LLMClient
from rubrics_sciarena.judge import judge_one_async
from rubrics_sciarena.lang import weak_answer as _weak_answer

logger = logging.getLogger(__name__)

WEAK_ANSWER = "I don't know."  # English default (back-compat)

JudgeFn = Callable[[Optional[LLMClient], str, str, dict], Awaitable[dict]]


def _met(result: dict, criterion: dict) -> bool:
    """Interpret a judge result, degrading conservatively on error."""
    if "error" in result:
        return criterion["sign"] == "positive"
    return bool(result.get("met", False))


async def filter_misaligned(
    question: str,
    reference_answer: str,
    criteria: List[dict],
    judge_client: Optional[LLMClient],
    *,
    lang: str = "en",
    weak_answer: Optional[str] = None,
    concurrency: int = 8,
    judge_fn: Optional[JudgeFn] = None,
) -> Tuple[List[dict], int]:
    """Filter criteria by their behaviour on the reference and weak answers.

    Args:
        question: The research question.
        reference_answer: The ground-truth (winning) response.
        criteria: Refined criteria dicts.
        judge_client: LLM client passed to the judge (may be ``None`` in tests).
        lang: Language code (selects judge prompt and default weak answer).
        weak_answer: The deliberately empty answer used as the lower anchor;
            defaults to the language-specific weak answer.
        concurrency: Max concurrent judge calls.
        judge_fn: Injectable async judge; defaults to the real one.

    Returns:
        ``(kept_criteria, n_dropped)``.
    """
    judge = judge_fn or functools.partial(judge_one_async, lang=lang)
    if weak_answer is None:
        weak_answer = _weak_answer(lang)
    sem = asyncio.Semaphore(concurrency)

    async def _judge(candidate: str, criterion: dict) -> bool:
        async with sem:
            return _met(await judge(judge_client, question, candidate, criterion), criterion)

    positives = [c for c in criteria if c.get("category") != "Pitfall"]
    ref_flags = await asyncio.gather(*[_judge(reference_answer, c) for c in positives])
    weak_flags = await asyncio.gather(*[_judge(weak_answer, c) for c in positives])

    dropped_ids = set()
    for c, met_ref, met_weak in zip(positives, ref_flags, weak_flags):
        if not met_ref:
            dropped_ids.add(id(c))
            logger.info("Drop criterion %s: not met on reference answer", c.get("id"))
        elif met_weak:
            dropped_ids.add(id(c))
            logger.info("Drop criterion %s: triggered on weak answer", c.get("id"))

    # Preserve original ordering; pitfalls always pass through.
    kept = [c for c in criteria if id(c) not in dropped_ids]
    return kept, len(dropped_ids)
