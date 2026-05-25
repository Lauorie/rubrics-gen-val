"""Score RLM answers in a rubrics JSON against per-item criteria.

Pipeline:
  1. Load rubrics+rlm_answer JSON (output of generate_rlm_answers.py).
  2. Load cached anchors (data/CAE-anchor-scores.json).
  3. Load existing scores.json (resume).
  4. For each pending item, call Scorer.score_batch (gpt-5.5 judge).
  5. Persist scores.json atomically.
  6. Render markdown report via rubrics_report.render_report.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def load_scores(path: Path) -> list[dict[str, Any]]:
    """Load a JSON array of per-item score records. Returns [] if missing."""
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"{path} is not a JSON array")
    return data


def save_scores(path: Path, scores: list[dict[str, Any]]) -> None:
    """Atomic JSON array write (tempfile + os.replace). UTF-8, 2-space indent."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp"
    ) as tmp:
        json.dump(scores, tmp, ensure_ascii=False, indent=2)
        tmp.write("\n")
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, path)


def filter_pending(
    rubrics: list[dict[str, Any]],
    existing_scores: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return the subset of rubrics that still need scoring.

    A rubric is pending if:
      - it has a non-null `rlm_answer`, AND
      - it does NOT already have a scored entry with `error is None`.
    """
    done: set[int] = {
        int(s["item_idx"])
        for s in existing_scores
        if s.get("error") is None and s.get("score") is not None
    }
    pending: list[dict[str, Any]] = []
    for r in rubrics:
        if r.get("rlm_answer") is None:
            logger.warning("item_idx=%s has no rlm_answer; skipping", r.get("item_idx"))
            continue
        if int(r["item_idx"]) in done:
            continue
        pending.append(r)
    return pending
