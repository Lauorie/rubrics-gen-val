"""Generate `rlm_answer` for each item in a rubrics JSON array.

Pipeline:
  1. Load JSON array (data/CAE-v2.0-1-rubrics.json) with `question_id` + `question`.
  2. Project to {id, question} pairs.
  3. Defer to academic-eval/rlm_runner.run_inference() for concurrent + resume.
  4. Merge JSONL output back into the JSON array, adding `rlm_answer`.
  5. Atomic-write back to the input file (or --output).
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def load_rubrics_json(path: Path) -> list[dict[str, Any]]:
    """Load a JSON array file. Raises if the top-level value is not a list."""
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"{path} is not a JSON array (got {type(data).__name__})")
    return data


def save_rubrics_json(path: Path, items: list[dict[str, Any]]) -> None:
    """Write a JSON array atomically (tmp file + os.replace). UTF-8, 2-space indent."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)
