"""Stage 3: drop criteria that don't behave as expected on (ref, weak) anchors."""
from __future__ import annotations
import logging
from pathlib import Path
from typing import List, Tuple

from rubrics.llm_client import LLMClient
from rubrics.refiner import DEFAULT_PITFALLS

logger = logging.getLogger(__name__)

WEAK_ANSWER = "我不知道。"

# The 2 mandatory style pitfalls are content-agnostic (does the answer open with
# boilerplate / is it bloated) and apply to any reference; they stay exempt from
# reference validation. Every OTHER (domain-specific) pitfall is validated.
_EXEMPT_PITFALL_TEXTS = {p["text"] for p in DEFAULT_PITFALLS}
_PROMPT = (Path(__file__).parent / "templates" / "misalignment_judge_prompt.txt").read_text(encoding="utf-8")


def _judge_one(
    judge_client: LLMClient, question: str, candidate: str, criterion: dict,
) -> bool:
    """Boolean shim for the generation-stage filter.
    Returns conservative True for positive / False for negative on judge failure.
    """
    from rubrics.judge import judge_one_sync
    result = judge_one_sync(judge_client, question, candidate, criterion)
    if "error" in result:
        return True if criterion["sign"] == "positive" else False
    return result["met"]


def filter_misaligned(
    question: str, reference_answer: str, criteria: List[dict],
    judge_client: LLMClient, weak_answer: str = WEAK_ANSWER,
) -> Tuple[List[dict], int]:
    kept: List[dict] = []
    dropped = 0
    for c in criteria:
        if c["category"] == "Pitfall":
            if c["text"] in _EXEMPT_PITFALL_TEXTS:
                # Content-agnostic mandatory style pitfalls stay exempt.
                kept.append(c)
                continue
            # Domain-specific pitfall: if the judge says the REFERENCE answer
            # triggers it, the pitfall is mis-specified (it would penalize a
            # correct answer) → drop it.
            fires_on_ref = _judge_one(judge_client, question, reference_answer, c)
            if fires_on_ref:
                dropped += 1
                logger.info("Drop pitfall %s: fires on reference answer", c.get("id"))
                continue
            kept.append(c)
            continue
        met_ref = _judge_one(judge_client, question, reference_answer, c)
        if not met_ref:
            dropped += 1
            logger.info("Drop criterion %s: not met on reference answer", c.get("id"))
            continue
        met_weak = _judge_one(judge_client, question, weak_answer, c)
        if met_weak:
            dropped += 1
            logger.info("Drop criterion %s: triggered on weak answer", c.get("id"))
            continue
        kept.append(c)
    return kept, dropped
