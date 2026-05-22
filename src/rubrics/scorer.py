"""Async per-candidate rubric scorer."""
from __future__ import annotations

import asyncio
import datetime as dt
import logging
from typing import Optional

from rubrics.judge import judge_one_async
from rubrics.llm_client import LLMClient
from rubrics.schema import Criterion
from rubrics.scoring import score_response

logger = logging.getLogger(__name__)


def _compute_anchored(
    score: float,
    ref: Optional[float],
    weak: Optional[float],
) -> Optional[dict]:
    """Compute anchor-normalized score relative to ref/weak baselines.

    Args:
        score: Raw rubric score for the candidate answer.
        ref: Score of the reference (ideal) answer on the same rubric.
        weak: Score of the weak (poor) answer on the same rubric.

    Returns:
        Dict with normalization info, or None if any input is missing.
    """
    if score is None or ref is None or weak is None:
        return None
    if ref <= weak:
        return {
            "ref_score": ref,
            "weak_score": weak,
            "normalized": None,
            "warning": "ref_score <= weak_score; rubric may be miscalibrated",
        }
    norm = (score - weak) / (ref - weak)
    return {
        "ref_score": ref,
        "weak_score": weak,
        "normalized": max(0.0, min(1.0, norm)),
    }


class Scorer:
    """Async per-candidate rubric scorer with semaphore-based concurrency control.

    Args:
        rubrics: Mapping of item_idx to rubric dicts.
        judge_client: LLM client used to judge each criterion.
        concurrency: Maximum number of concurrent judge calls.
        anchors: Optional mapping of item_idx to anchor dicts with
            ref_score and weak_score keys.
    """

    def __init__(
        self,
        rubrics: dict[int, dict],
        judge_client: LLMClient,
        concurrency: int = 16,
        anchors: Optional[dict[int, dict]] = None,
    ) -> None:
        self.rubrics = rubrics
        self.judge_client = judge_client
        self.semaphore = asyncio.Semaphore(concurrency)
        self.anchors = anchors or {}

    async def _judge_criterion(
        self, question: str, candidate: str, criterion: dict
    ) -> dict:
        """Judge a single criterion under the concurrency semaphore.

        Args:
            question: The exam question text.
            candidate: The candidate's answer text.
            criterion: Criterion dict with id, text, weight, sign, etc.

        Returns:
            Verdict dict with at least 'met' (bool) and 'reason' (str).
        """
        async with self.semaphore:
            return await judge_one_async(self.judge_client, question, candidate, criterion)

    async def score_one(self, item_idx: int, candidate: str) -> dict:
        """Score a single candidate answer against its rubric.

        Args:
            item_idx: Index identifying the rubric to use.
            candidate: The candidate's answer text.

        Returns:
            Result dict with score, breakdown, and metadata.
            If the rubric is missing, returns an error record with score=None.
        """
        if item_idx not in self.rubrics:
            return {
                "item_idx": item_idx,
                "score": None,
                "error": f"no rubric found for item_idx={item_idx}",
                "scored_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            }

        rubric = self.rubrics[item_idx]
        criteria_dicts = rubric["criteria"]

        tasks = [
            self._judge_criterion(rubric["question"], candidate, c)
            for c in criteria_dicts
        ]
        verdicts = await asyncio.gather(*tasks)

        met_by_text = {c["text"]: v["met"] for c, v in zip(criteria_dicts, verdicts)}
        criteria_models = [Criterion(**c) for c in criteria_dicts]
        score = score_response(criteria_models, met_by_text)

        breakdown = []
        for c, v in zip(criteria_dicts, verdicts):
            sign_val = c["weight"] if c["sign"] == "positive" else -c["weight"]
            contribution = sign_val if v["met"] else 0
            row = {
                "id": c["id"],
                "text": c["text"],
                "category": c["category"],
                "weight": c["weight"],
                "sign": c["sign"],
                "criterion_type": c["criterion_type"],
                "met": v["met"],
                "reason": v.get("reason", ""),
                "contribution": contribution,
            }
            if "error" in v:
                row["error"] = v["error"]
            breakdown.append(row)

        anchor = self.anchors.get(item_idx)
        if anchor is not None:
            score_anchored = _compute_anchored(
                score, anchor.get("ref_score"), anchor.get("weak_score")
            )
        else:
            score_anchored = None

        return {
            "item_idx": item_idx,
            "question_id": rubric.get("question_id"),
            "question_type": rubric.get("question_type"),
            "difficulty": rubric.get("difficulty"),
            "candidate_answer": candidate,
            "score": score,
            "score_anchored": score_anchored,
            "breakdown": breakdown,
            "judge_model": getattr(
                getattr(self.judge_client, "cfg", None), "model", "unknown"
            ),
            "scored_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        }

    async def score_batch(self, predictions: list[dict]) -> list[dict]:
        """Score a batch of candidate predictions concurrently.

        Each prediction dict must contain 'item_idx' and 'answer' keys.
        If score_one raises for a prediction, that item gets an error record
        while the rest of the batch continues unaffected.

        Args:
            predictions: List of dicts, each with 'item_idx' and 'answer'.

        Returns:
            List of result dicts in the same order as predictions.
        """
        tasks = [self.score_one(p["item_idx"], p["answer"]) for p in predictions]
        raw = await asyncio.gather(*tasks, return_exceptions=True)
        out: list[dict] = []
        for p, r in zip(predictions, raw):
            if isinstance(r, Exception):
                logger.exception(
                    "scorer crashed on item_idx=%s", p.get("item_idx")
                )
                out.append({
                    "item_idx": p.get("item_idx"),
                    "score": None,
                    "error": f"{type(r).__name__}: {r}",
                    "scored_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                })
            else:
                out.append(r)
        return out
