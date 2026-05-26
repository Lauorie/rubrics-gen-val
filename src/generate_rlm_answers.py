"""Generate `rlm_answer` for each item in a rubrics JSON array.

Pipeline:
  1. Load JSON array (data/CAE-v2.0-1-rubrics.json) with `item_idx` + `question`.
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

DEFAULT_ID_FIELD = "item_idx"


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


def to_inference_items(
    rubrics: list[dict[str, Any]],
    *,
    id_field: str = DEFAULT_ID_FIELD,
) -> list[dict[str, Any]]:
    """Project rubrics → list of {id, question} dicts for rlm_runner.

    - `id_field` (default: ``item_idx``) → `id` (str)
    - drops items without a `question` field (logs a warning)
    - raises if two items share the same value of `id_field`
    """
    seen: set[str] = set()
    items: list[dict[str, Any]] = []
    for r in rubrics:
        qid = str(r[id_field])
        q = r.get("question")
        if not q:
            logger.warning("Skipping %s=%s: no `question` field", id_field, qid)
            continue
        if qid in seen:
            raise ValueError(f"duplicate {id_field}: {qid}")
        seen.add(qid)
        items.append({"id": qid, "question": q})
    return items


def merge_answers_into_rubrics(
    rubrics: list[dict[str, Any]],
    answers_jsonl: Path,
    *,
    id_field: str = DEFAULT_ID_FIELD,
) -> list[dict[str, Any]]:
    """Return a new list of rubric dicts with `rlm_answer` + `rlm_error` attached.

    Reads `answers_jsonl` (one JSON record per line, schema = rlm_runner output:
    `{id, answer, error, ...}`). Last row wins per `id` so a successful retry
    overrides an earlier failure. Items missing from the JSONL get both fields
    set to None. Does NOT mutate the input list.

    The join key on the rubric side is `id_field` (default: ``item_idx``);
    it is matched against the `id` field in each JSONL row.
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
        qid = str(r[id_field])
        row = by_id.get(qid)
        new["rlm_answer"] = (row.get("answer") if row else None)
        new["rlm_error"] = (row.get("error") if row else None)
        merged.append(new)
    return merged


# academic-eval is a sibling top-level dir, not on sys.path by default.
_RLM_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_RLM_ROOT / "academic-eval"))
sys.path.insert(0, str(_RLM_ROOT / "papers_qa"))
sys.path.insert(0, str(_RLM_ROOT / "rlm"))
from rlm_runner import load_done_ids, run_inference, write_record  # noqa: E402
from papers_qa.config import PapersQAConfig  # noqa: E402
from papers_qa.peek_integration import PeekCfg, build_peek_policy, DISTILLER_DECISIONS_ADDENDUM  # noqa: E402
from papers_qa.runner import PapersQA  # noqa: E402


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
        "PYTHONPATH": f"{_RLM_ROOT / 'papers_qa'}:{_RLM_ROOT / 'rlm'}",
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


def _parse_item_filter(spec: str | None) -> set[int] | None:
    """Parse --include-items or --skip-items spec strings.

    Accepts comma-separated ints and 'lo-hi' ranges, e.g.:
      '0-29'          → {0..29}
      '0,5,10'        → {0,5,10}
      '0-5,10,15-20'  → {0..5} ∪ {10} ∪ {15..20}
    Returns None when spec is None (= no filter).
    """
    if spec is None:
        return None
    out: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-", 1)
            out.update(range(int(lo), int(hi) + 1))
        else:
            out.add(int(part))
    return out


def _frozen_map_to_addendum(map_path: Path) -> str:
    """Read PEEK map JSON, brace-escape map_text, wrap in delimiters."""
    payload = json.loads(map_path.read_text(encoding="utf-8"))
    map_text = payload.get("map_text", "")
    escaped = map_text.replace("{", "{{").replace("}", "}}")
    return (
        "\n================ Context Map (PEEK frozen) ================\n"
        + escaped
        + "\n================ End of Context Map ================\n"
    )


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
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of parallel PapersQA worker processes (default: 4).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip inference; produce output JSON with all rlm_answer=null (for I/O testing).",
    )
    parser.add_argument(
        "--id-field",
        default=DEFAULT_ID_FIELD,
        help="Field in each rubric item to use as the unique join key (default: item_idx).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO).",
    )
    parser.add_argument(
        "--peek-map-out",
        type=Path,
        default=None,
        help="Enable PEEK orientation cache; save the frozen map JSON to this path. "
             "Forces --workers=1.",
    )
    parser.add_argument("--peek-token-budget", type=int, default=1024,
                        help="PEEK map size limit in tokens (default: 1024).")
    parser.add_argument("--peek-evolve-steps", type=int, default=30,
                        help="How many questions PEEK evolves the map before freezing.")
    parser.add_argument("--peek-distiller-model", default="deepseek/deepseek-v4-flash",
                        help="LLM used by PEEK's Distiller + Cartographer.")
    parser.add_argument("--peek-map-in", type=Path, default=None,
                        help="Load a frozen PEEK map JSON; inject its text into PAPERS_QA_SYSTEM_PROMPT_ADDENDUM. "
                             "No live PEEK calls. Compatible with --workers > 1.")
    parser.add_argument("--peek-distiller-addendum-preset", choices=["none", "decisions"], default="none",
                        help="Append a preset addendum to the PEEK distiller prompt. "
                             "'decisions' invites canonical-decision caching into REUSABLE RESULTS. "
                             "Only meaningful with --peek-map-out.")
    parser.add_argument("--include-items", default=None,
                        help="Filter rubric items by item_idx. Range syntax: '0-29' or '30-93,7' or '5'. "
                             "Applied BEFORE --skip-items.")
    parser.add_argument("--skip-items", default=None,
                        help="CSV list of item_idx to skip, e.g., '46,48'.")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    )

    if args.peek_map_out is not None:
        if args.workers != 1:
            parser.error("--peek-map-out requires --workers 1 (single-process for shared cache)")
        args.peek_map_out.parent.mkdir(parents=True, exist_ok=True)

    if args.peek_map_in is not None:
        if args.peek_map_out is not None:
            parser.error("--peek-map-in and --peek-map-out are mutually exclusive")
        if not args.peek_map_in.exists():
            parser.error(f"--peek-map-in path does not exist: {args.peek_map_in}")

    output_path = args.output or args.input
    rubrics = load_rubrics_json(args.input)
    logger.info("Loaded %d rubric items from %s", len(rubrics), args.input)

    _include = _parse_item_filter(args.include_items)
    _skip = _parse_item_filter(args.skip_items)
    def _keep(r: dict) -> bool:
        idx = int(r["item_idx"])
        if _include is not None and idx not in _include:
            return False
        if _skip is not None and idx in _skip:
            return False
        return True
    n_before = len(rubrics)
    rubrics = [r for r in rubrics if _keep(r)]
    if n_before != len(rubrics):
        logger.info("after include/skip filter: %d rubric items (was %d)", len(rubrics), n_before)

    if not args.dry_run:
        items = to_inference_items(rubrics, id_field=args.id_field)
        args.jsonl.parent.mkdir(parents=True, exist_ok=True)

        if args.peek_map_out is not None:
            # Serial PEEK loop — one PapersQA + one shared CachePolicy.
            logger.info("Running serial PEEK loop on %d items (workers=1)", len(items))
            done = load_done_ids(args.jsonl)
            todo = [it for it in items if it["id"] not in done]
            logger.info("PEEK serial: %d todo (%d already done)", len(todo), len(done))

            addendum = DISTILLER_DECISIONS_ADDENDUM if args.peek_distiller_addendum_preset == "decisions" else None
            peek_cfg = PeekCfg(
                token_budget=args.peek_token_budget,
                evolve_steps=args.peek_evolve_steps,
                distiller_model=args.peek_distiller_model,
                distiller_addendum=addendum,
            )
            policy = build_peek_policy(peek_cfg)
            pq_cfg = PapersQAConfig.from_env()
            pq_cfg = type(pq_cfg)(**{**pq_cfg.__dict__, "papers_dir": args.papers_dir})
            qa = PapersQA(pq_cfg, peek_policy=policy)

            for i, item in enumerate(todo):
                try:
                    res = qa.ask(item["question"])
                    record = {"id": item["id"], "answer": res.answer,
                              "cost_usd": res.cost_usd, "duration_s": res.duration_s,
                              "error": None}
                except Exception as e:
                    logger.exception("PEEK serial ask failed: id=%s", item["id"])
                    record = {"id": item["id"], "answer": None, "cost_usd": None,
                              "duration_s": None, "error": f"{type(e).__name__}: {e}"}
                write_record(args.jsonl, record)
                logger.info("[peek %d/%d] id=%s status=%s",
                            i + 1, len(todo), item["id"],
                            "ok" if record["error"] is None else "ERROR")
                # Save policy at the evolve_steps boundary and at the end.
                if not policy.evolving or (i + 1) == args.peek_evolve_steps:
                    policy.save(args.peek_map_out)
            policy.save(args.peek_map_out)
        else:
            logger.info("Running inference on %d items, workers=%d", len(items), args.workers)
            env_overrides = build_env_overrides(papers_dir=args.papers_dir)
            if args.peek_map_in is not None:
                env_overrides["PAPERS_QA_SYSTEM_PROMPT_ADDENDUM"] = _frozen_map_to_addendum(args.peek_map_in)
                logger.info("Injected frozen PEEK map (%d chars) into PAPERS_QA_SYSTEM_PROMPT_ADDENDUM",
                            len(env_overrides["PAPERS_QA_SYSTEM_PROMPT_ADDENDUM"]))
            # Workers need papers_qa + rlm on sys.path at interpreter startup;
            # setting it in env_overrides alone is too late (those run inside the
            # worker after Python has already initialized sys.path). Propagate to
            # the parent env so children inherit it during spawn/fork.
            os.environ["PYTHONPATH"] = env_overrides["PYTHONPATH"]
            for p in env_overrides["PYTHONPATH"].split(":"):
                if p and p not in sys.path:
                    sys.path.insert(0, p)
            run_inference(
                items=items,
                out_path=args.jsonl,
                max_workers=args.workers,
                use_processes=True,
                env_overrides=env_overrides,
            )

    merged = merge_answers_into_rubrics(rubrics, args.jsonl, id_field=args.id_field)
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
