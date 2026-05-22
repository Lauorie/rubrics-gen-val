"""Stage 3: drop criteria that don't behave as expected on (ref, weak) anchors."""
from __future__ import annotations
import logging
from pathlib import Path
from typing import List, Tuple

from rubrics.llm_client import LLMClient

logger = logging.getLogger(__name__)

WEAK_ANSWER = "我不知道。"
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
            # Skip — pitfalls are template-validated, see spec §10.2
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
