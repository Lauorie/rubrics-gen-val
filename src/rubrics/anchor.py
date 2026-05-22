"""Compute ref/weak anchor scores per rubric and cache to disk."""
from __future__ import annotations
import asyncio
import datetime as dt
import json
import logging
from pathlib import Path
from typing import Optional

from rubrics.judge import judge_one_async
from rubrics.llm_client import LLMClient
from rubrics.schema import Criterion
from rubrics.scoring import score_response

logger = logging.getLogger(__name__)

WEAK_ANSWER = "我不知道。"


async def compute_anchor_for_rubric(
    rubric: dict, judge_client: LLMClient,
    weak_answer: str = WEAK_ANSWER,
) -> dict:
    """Score reference_answer and weak_answer against the rubric's criteria.

    Args:
        rubric: Rubric dict containing question, reference_answer, and criteria.
        judge_client: LLM client used to judge each criterion.
        weak_answer: Deliberately weak answer used as lower-bound anchor.

    Returns:
        Dict with ref_score, weak_score, judge_model, computed_at.
    """
    question = rubric["question"]
    ref_answer = rubric["reference_answer"]
    criteria_dicts = rubric["criteria"]

    async def _judge_all(candidate: str) -> dict[str, bool]:
        tasks = [
            judge_one_async(judge_client, question, candidate, c)
            for c in criteria_dicts
        ]
        results = await asyncio.gather(*tasks)
        return {c["text"]: r["met"] for c, r in zip(criteria_dicts, results)}

    ref_met = await _judge_all(ref_answer)
    weak_met = await _judge_all(weak_answer)

    criteria_models = [Criterion(**c) for c in criteria_dicts]
    ref_score = score_response(criteria_models, ref_met)
    weak_score = score_response(criteria_models, weak_met)

    return {
        "ref_score": ref_score,
        "weak_score": weak_score,
        "judge_model": getattr(getattr(judge_client, "cfg", None), "model", "unknown"),
        "computed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }


class AnchorCache:
    """JSON-backed cache of anchor scores, keyed by item_idx (as string)."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._data: dict[str, dict] = {}

    def load(self) -> None:
        """Load cache from disk. No-ops if file does not exist."""
        if self.path.exists():
            self._data = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self._data = {}

    def get(self, idx: int) -> Optional[dict]:
        """Return cached anchor record for item_idx, or None if not cached."""
        return self._data.get(str(idx))

    def set(self, idx: int, *, ref_score: float, weak_score: float, judge_model: str) -> None:
        """Store anchor scores for item_idx in memory (call flush() to persist)."""
        self._data[str(idx)] = {
            "ref_score": ref_score,
            "weak_score": weak_score,
            "judge_model": judge_model,
            "computed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        }

    def has(self, idx: int) -> bool:
        """Return True if item_idx is present in the cache."""
        return str(idx) in self._data

    def flush(self) -> None:
        """Persist the in-memory cache to disk as JSON."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
