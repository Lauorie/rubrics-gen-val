"""Per-criterion judge: ask LLM whether a candidate response satisfies one rubric criterion.

Returns {met: bool, reason: str, [error: str]} dict.
"""
from __future__ import annotations
import logging
from pathlib import Path

from cae_eval.llm_client import LLMClient

logger = logging.getLogger(__name__)

JUDGE_PROMPT = (Path(__file__).parent / "templates" / "misalignment_judge_prompt.txt").read_text(encoding="utf-8")


def _build_user_message(question: str, candidate: str, criterion: dict) -> str:
    return (
        f"[题目] {question}\n"
        f"[候选回答] {candidate}\n"
        f"[criterion] {criterion['text']}\n"
        f"[criterion 类型] {criterion['criterion_type']}"
    )


def judge_one_sync(
    judge_client: LLMClient, question: str, candidate: str, criterion: dict,
) -> dict:
    """Synchronous per-criterion judge. Returns {met, reason, error?}."""
    user = _build_user_message(question, candidate, criterion)
    try:
        out = judge_client.complete_json(system=JUDGE_PROMPT, user=user, schema_hint="{met, reason}")
        return {"met": bool(out.get("met", False)), "reason": str(out.get("reason", ""))}
    except Exception as e:
        logger.warning("Judge sync call failed for criterion %s: %s", criterion.get("id"), e)
        return {"met": False, "reason": "", "error": str(e)}


async def judge_one_async(
    judge_client: LLMClient, question: str, candidate: str, criterion: dict,
) -> dict:
    """Async per-criterion judge. Returns {met, reason, error?}."""
    user = _build_user_message(question, candidate, criterion)
    try:
        out = await judge_client.complete_json_async(system=JUDGE_PROMPT, user=user, schema_hint="{met, reason}")
        return {"met": bool(out.get("met", False)), "reason": str(out.get("reason", ""))}
    except Exception as e:
        logger.warning("Judge async call failed for criterion %s: %s", criterion.get("id"), e)
        return {"met": False, "reason": "", "error": str(e)}
