"""Generate `rlm_answer` for each item in a rubrics JSON array.

Pipeline:
  1. Load JSON array (data/CAE-v2.0-1-rubrics.json) with `question_id` + `question`.
  2. Project to {id, question} pairs.
  3. Defer to academic-eval/rlm_runner.run_inference() for concurrent + resume.
  4. Merge JSONL output back into the JSON array, adding `rlm_answer`.
  5. Atomic-write back to the input file (or --output).
"""
from __future__ import annotations

import argparse
import copy
import json
import logging
import os
import sys
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


def to_inference_items(rubrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Project rubrics → list of {id, question} dicts for rlm_runner.

    - `question_id` (str) → `id` (str)
    - drops items without a `question` field (logs a warning)
    - raises if two items share the same `question_id`
    """
    seen: set[str] = set()
    items: list[dict[str, Any]] = []
    for r in rubrics:
        qid = str(r["question_id"])
        q = r.get("question")
        if not q:
            logger.warning("Skipping question_id=%s: no `question` field", qid)
            continue
        if qid in seen:
            raise ValueError(f"duplicate question_id: {qid}")
        seen.add(qid)
        items.append({"id": qid, "question": q})
    return items


def merge_answers_into_rubrics(
    rubrics: list[dict[str, Any]],
    answers_jsonl: Path,
) -> list[dict[str, Any]]:
    """Return a new list of rubric dicts with `rlm_answer` + `rlm_error` attached.

    Reads `answers_jsonl` (one JSON record per line, schema = rlm_runner output:
    `{id, answer, error, ...}`). Last row wins per `id` so a successful retry
    overrides an earlier failure. Items missing from the JSONL get both fields
    set to None. Does NOT mutate the input list.
    """
    by_id: dict[str, dict[str, Any]] = {}
    if answers_jsonl.exists():
        with answers_jsonl.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                by_id[str(row["id"])] = row  # last write wins

    merged: list[dict[str, Any]] = []
    for r in rubrics:
        new = copy.deepcopy(r)
        qid = str(r["question_id"])
        row = by_id.get(qid)
        new["rlm_answer"] = (row.get("answer") if row else None)
        new["rlm_error"] = (row.get("error") if row else None)
        merged.append(new)
    return merged


# academic-eval is a sibling top-level dir, not on sys.path by default.
_RLM_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_RLM_ROOT / "academic-eval"))
from rlm_runner import run_inference  # noqa: E402


def build_env_overrides(*, papers_dir: Path) -> dict[str, str]:
    """Env vars passed to each PapersQA worker process.

    Pins PAPERS_QA_PAPERS_DIR to the CAE corpus. Inherits OPENAI creds and
    PapersQA tuning knobs from the current process env (with safe defaults).
    Deliberately omits PAPERS_QA_SYSTEM_PROMPT_ADDENDUM — questions are Chinese
    and we want the default bilingual prompt unchanged.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set (export it or source .env)")
    return {
        "OPENAI_API_KEY": api_key,
        "OPENAI_BASE_URL": os.environ.get("OPENAI_BASE_URL", "https://aiberm.com/v1"),
        "PAPERS_QA_MODEL": os.environ.get("PAPERS_QA_MODEL", "deepseek/deepseek-v4-flash"),
        "PAPERS_QA_PAPERS_DIR": str(papers_dir),
        "PAPERS_QA_TEMPERATURE": os.environ.get("PAPERS_QA_TEMPERATURE", "0.2"),
        "PAPERS_QA_MAX_ITERATIONS": os.environ.get("PAPERS_QA_MAX_ITERATIONS", "30"),
        "PAPERS_QA_MAX_DEPTH": os.environ.get("PAPERS_QA_MAX_DEPTH", "2"),
        "PAPERS_QA_MAX_BUDGET_USD": os.environ.get("PAPERS_QA_MAX_BUDGET_USD", "2.0"),
        "PAPERS_QA_MAX_TIMEOUT_S": os.environ.get("PAPERS_QA_MAX_TIMEOUT_S", "900"),
        "PAPERS_QA_THINKING_MODE": os.environ.get("PAPERS_QA_THINKING_MODE", "disabled"),
        "PAPERS_QA_DISABLE_DISK_LOGGER": "1",
    }


def main() -> int:
    """CLI entrypoint: generate rlm_answer for each item in a rubrics JSON array."""
    parser = argparse.ArgumentParser(
        description="Generate rlm_answer for each item in a rubrics JSON array.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("/home/juli/RLM/data/CAE-v2.0-1-rubrics.json"),
        help="Rubrics JSON array (read).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSON path (default: same as --input, in-place).",
    )
    parser.add_argument(
        "--jsonl",
        type=Path,
        default=Path("/home/juli/RLM/outputs/rlm-answers/cae-v2.0-1.jsonl"),
        help="Intermediate JSONL path (resume source-of-truth).",
    )
    parser.add_argument(
        "--papers-dir",
        type=Path,
        default=Path("/home/juli/RLM/CAE-MDs"),
        help="Knowledge-base directory of *.md files.",
    )
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip inference; produce output JSON with all rlm_answer=null (for I/O testing).",
    )
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    )

    output_path = args.output or args.input
    rubrics = load_rubrics_json(args.input)
    logger.info("Loaded %d rubric items from %s", len(rubrics), args.input)

    if not args.dry_run:
        items = to_inference_items(rubrics)
        logger.info("Running inference on %d items, workers=%d", len(items), args.workers)
        args.jsonl.parent.mkdir(parents=True, exist_ok=True)
        run_inference(
            items=items,
            out_path=args.jsonl,
            max_workers=args.workers,
            use_processes=True,
            env_overrides=build_env_overrides(papers_dir=args.papers_dir),
        )

    merged = merge_answers_into_rubrics(rubrics, args.jsonl)
    save_rubrics_json(output_path, merged)
    n_ok = sum(1 for r in merged if r["rlm_answer"] is not None)
    n_err = sum(1 for r in merged if r["rlm_error"] is not None)
    logger.info(
        "Wrote %s — %d/%d answered, %d errored.",
        output_path, n_ok, len(merged), n_err,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
