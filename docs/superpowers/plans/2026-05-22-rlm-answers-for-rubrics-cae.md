# Generate `rlm_answer` for CAE rubrics — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate one `rlm_answer` per item in `data/CAE-v2.0-1-rubrics.json` (94 items) by running each `question` through `papers_qa.PapersQA` against the `CAE-MDs/` knowledge base, and write the answers back into the JSON file under a new `rlm_answer` field while preserving every existing field.

**Architecture:** Thin orchestrator in `src/generate_rlm_answers.py` that (1) loads the rubrics JSON array, (2) projects to the `{id, question}` shape consumed by the existing `academic-eval/rlm_runner.py:run_inference()` (which already handles concurrent ProcessPoolExecutor + resume + per-process `PapersQA` construction + chdir-race avoidance), (3) writes intermediate per-question results as JSONL to `outputs/rlm-answers/cae-v2.0-1.jsonl`, (4) merges JSONL → original JSON array by `question_id`, attaching only `rlm_answer` (string or `null`) and `rlm_error` (string or `null` on failure). The intermediate JSONL is the resume source-of-truth across runs; the final JSON write is atomic (`tmp` + `os.replace`).

**Tech Stack:** Python 3.12, `papers_qa.PapersQA`, `academic-eval/rlm_runner.run_inference` (`use_processes=True`), pytest, stdlib only for the orchestrator.

---

## Pre-flight Decisions (defaults in plan; flag in response to modify)

1. **Output destination:** Default writes back to the input file `/home/juli/RLM/data/CAE-v2.0-1-rubrics.json` in-place via tmp+rename. Override with `--output PATH`.
2. **Added fields:** Only `rlm_answer` (string or `null`) and `rlm_error` (string or `null`). No cost/duration on items (kept in JSONL for audit). Strip with `--no-error-field` if user wants strict single-field.
3. **Concurrency:** 4 process workers by default (94 items × ~60s ÷ 4 ≈ 25 min wall-clock; halves API burn rate vs. 8). Override with `--workers N`.
4. **Budget cap:** `PAPERS_QA_MAX_BUDGET_USD=2.0` per call (existing default). Worst case total ≈ 94 × 2 = $188 (extreme upper bound); realistic ≈ $5–10 based on existing `papers_qa` README.
5. **Papers dir:** Hard-pinned to `/home/juli/RLM/CAE-MDs` via `--papers-dir` flag → passed into worker env via `env_overrides`.
6. **Question language:** Chinese (matches `papers_qa`'s default bilingual prompt — no `PAPERS_QA_SYSTEM_PROMPT_ADDENDUM` needed; do NOT copy the English-override addendum that `academic-eval/run_eval.py` uses).

---

## File Structure

**Files to create:**
- `src/generate_rlm_answers.py` — orchestrator (≤ 200 lines): load rubrics JSON, project to inference shape, call `run_inference()`, merge JSONL back into JSON array.
- `tests/test_generate_rlm_answers.py` — pytest module covering load/save round-trip, projection, merge, resume semantics, error injection, and CLI argparse.

**Files to read but not modify:**
- `academic-eval/rlm_runner.py` — `run_inference()`, `load_done_ids()`, `_init_worker_process()` are reused as-is.
- `papers_qa/papers_qa/config.py` — confirms env var contract for `PAPERS_QA_PAPERS_DIR` override.

**Files NOT to touch:**
- `data/CAE-v2.0-1-rubrics.json` is the input (and default output). All work goes through tmp files.

**Outputs at runtime:**
- `outputs/rlm-answers/cae-v2.0-1.jsonl` — intermediate, one record per question (resume source-of-truth).
- `outputs/rlm-answers/cae-v2.0-1.log` — orchestrator stderr (caller redirects).
- `outputs/logs/<question-hash>/...` — per-question RLM trajectories (auto, from `PapersQA`). Disable with `PAPERS_QA_DISABLE_DISK_LOGGER=1` if disk pressure matters.

---

## Task 1: Scaffold `src/generate_rlm_answers.py` with JSON I/O

**Files:**
- Create: `src/generate_rlm_answers.py`
- Create: `tests/test_generate_rlm_answers.py`

- [ ] **Step 1: Write failing tests for `load_rubrics_json` and `save_rubrics_json`**

Create `tests/test_generate_rlm_answers.py`:

```python
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from generate_rlm_answers import load_rubrics_json, save_rubrics_json


def test_load_rubrics_json_returns_list_of_dicts(tmp_path: Path) -> None:
    p = tmp_path / "in.json"
    p.write_text(json.dumps([{"question_id": "1", "question": "Q1"}], ensure_ascii=False))
    items = load_rubrics_json(p)
    assert isinstance(items, list)
    assert items[0]["question_id"] == "1"


def test_load_rubrics_json_preserves_chinese(tmp_path: Path) -> None:
    p = tmp_path / "in.json"
    p.write_text(json.dumps([{"question_id": "1", "question": "附加质量效应"}], ensure_ascii=False))
    items = load_rubrics_json(p)
    assert items[0]["question"] == "附加质量效应"


def test_save_rubrics_json_atomic_and_chinese_safe(tmp_path: Path) -> None:
    p = tmp_path / "out.json"
    save_rubrics_json(p, [{"question_id": "1", "question": "中文问题", "rlm_answer": "答案"}])
    reread = json.loads(p.read_text())
    assert reread[0]["rlm_answer"] == "答案"
    # Atomic-rename leaves no `.tmp` siblings on success.
    assert not any(s.name.endswith(".tmp") for s in tmp_path.iterdir())


def test_save_rubrics_json_pretty_2_space_indent(tmp_path: Path) -> None:
    p = tmp_path / "out.json"
    save_rubrics_json(p, [{"a": 1}])
    text = p.read_text()
    assert '  "a": 1' in text  # 2-space indent, matches existing data/ JSON style
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/juli/RLM
.venv/bin/python -m pytest tests/test_generate_rlm_answers.py -v
```
Expected: ImportError on `from generate_rlm_answers import ...`.

- [ ] **Step 3: Implement scaffolding in `src/generate_rlm_answers.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/test_generate_rlm_answers.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/generate_rlm_answers.py tests/test_generate_rlm_answers.py
git commit -m "feat(rlm-answers): scaffold load/save for rubrics JSON array"
```

---

## Task 2: Project rubrics → inference items (`{id, question}` shape)

**Files:**
- Modify: `src/generate_rlm_answers.py` (add `to_inference_items`)
- Modify: `tests/test_generate_rlm_answers.py` (add tests)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_generate_rlm_answers.py`:

```python
from generate_rlm_answers import to_inference_items


def test_to_inference_items_maps_question_id_to_id() -> None:
    rubrics = [
        {"question_id": "1", "question": "Q1", "reference_answer": "ignored"},
        {"question_id": "2", "question": "Q2"},
    ]
    items = to_inference_items(rubrics)
    assert items == [{"id": "1", "question": "Q1"}, {"id": "2", "question": "Q2"}]


def test_to_inference_items_skips_items_missing_question() -> None:
    rubrics = [
        {"question_id": "1", "question": "Q1"},
        {"question_id": "2"},  # no question — must be skipped, not crash
    ]
    items = to_inference_items(rubrics)
    assert [it["id"] for it in items] == ["1"]


def test_to_inference_items_raises_on_duplicate_id() -> None:
    import pytest as _pytest
    with _pytest.raises(ValueError, match="duplicate question_id"):
        to_inference_items([
            {"question_id": "1", "question": "Q1"},
            {"question_id": "1", "question": "Q1-dup"},
        ])
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest tests/test_generate_rlm_answers.py -v
```
Expected: ImportError on `to_inference_items`.

- [ ] **Step 3: Implement `to_inference_items`**

Append to `src/generate_rlm_answers.py`:

```python
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
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/python -m pytest tests/test_generate_rlm_answers.py -v
```
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add src/generate_rlm_answers.py tests/test_generate_rlm_answers.py
git commit -m "feat(rlm-answers): project rubrics to inference {id,question} shape"
```

---

## Task 3: Merge JSONL answers back onto the rubrics array

**Files:**
- Modify: `src/generate_rlm_answers.py` (add `merge_answers_into_rubrics`)
- Modify: `tests/test_generate_rlm_answers.py`

- [ ] **Step 1: Write failing tests**

Append:

```python
from generate_rlm_answers import merge_answers_into_rubrics


def _jsonl(tmp_path: Path, rows: list[dict[str, Any]]) -> Path:
    p = tmp_path / "answers.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")
    return p


def test_merge_attaches_rlm_answer_by_question_id(tmp_path: Path) -> None:
    rubrics = [
        {"question_id": "1", "question": "Q1", "reference_answer": "R1"},
        {"question_id": "2", "question": "Q2"},
    ]
    answers = _jsonl(tmp_path, [
        {"id": "1", "answer": "A1", "error": None},
        {"id": "2", "answer": "A2", "error": None},
    ])
    out = merge_answers_into_rubrics(rubrics, answers)
    assert out[0]["rlm_answer"] == "A1"
    assert out[0]["reference_answer"] == "R1"  # original field preserved
    assert out[1]["rlm_answer"] == "A2"


def test_merge_marks_missing_as_null(tmp_path: Path) -> None:
    rubrics = [{"question_id": "1", "question": "Q1"}, {"question_id": "2", "question": "Q2"}]
    answers = _jsonl(tmp_path, [{"id": "1", "answer": "A1", "error": None}])
    out = merge_answers_into_rubrics(rubrics, answers)
    assert out[0]["rlm_answer"] == "A1"
    assert out[1]["rlm_answer"] is None
    assert out[1]["rlm_error"] is None  # not failed, just not yet processed


def test_merge_propagates_error_string(tmp_path: Path) -> None:
    rubrics = [{"question_id": "1", "question": "Q1"}]
    answers = _jsonl(tmp_path, [{"id": "1", "answer": None, "error": "RuntimeError: boom"}])
    out = merge_answers_into_rubrics(rubrics, answers)
    assert out[0]["rlm_answer"] is None
    assert out[0]["rlm_error"] == "RuntimeError: boom"


def test_merge_last_row_wins_on_duplicate_id(tmp_path: Path) -> None:
    """JSONL append can have a failed row then a retry success — keep latest."""
    rubrics = [{"question_id": "1", "question": "Q1"}]
    answers = _jsonl(tmp_path, [
        {"id": "1", "answer": None, "error": "transient"},
        {"id": "1", "answer": "A1-retry", "error": None},
    ])
    out = merge_answers_into_rubrics(rubrics, answers)
    assert out[0]["rlm_answer"] == "A1-retry"
    assert out[0]["rlm_error"] is None


def test_merge_does_not_mutate_input(tmp_path: Path) -> None:
    rubrics = [{"question_id": "1", "question": "Q1"}]
    answers = _jsonl(tmp_path, [{"id": "1", "answer": "A", "error": None}])
    merge_answers_into_rubrics(rubrics, answers)
    assert "rlm_answer" not in rubrics[0]  # input list untouched


def test_merge_missing_answers_file_yields_all_null(tmp_path: Path) -> None:
    rubrics = [{"question_id": "1", "question": "Q1"}]
    out = merge_answers_into_rubrics(rubrics, tmp_path / "nope.jsonl")
    assert out[0]["rlm_answer"] is None
    assert out[0]["rlm_error"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest tests/test_generate_rlm_answers.py -v
```
Expected: ImportError on `merge_answers_into_rubrics`.

- [ ] **Step 3: Implement `merge_answers_into_rubrics`**

Append to `src/generate_rlm_answers.py`:

```python
import copy


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
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/python -m pytest tests/test_generate_rlm_answers.py -v
```
Expected: 13 passed.

- [ ] **Step 5: Commit**

```bash
git add src/generate_rlm_answers.py tests/test_generate_rlm_answers.py
git commit -m "feat(rlm-answers): merge JSONL answers into rubrics by question_id"
```

---

## Task 4: CLI entrypoint + end-to-end wiring with mocked inference

**Files:**
- Modify: `src/generate_rlm_answers.py` (add `build_env_overrides`, `main`)
- Modify: `tests/test_generate_rlm_answers.py`

- [ ] **Step 1: Write failing tests**

Append:

```python
import subprocess
import sys as _sys
from unittest.mock import patch

from generate_rlm_answers import build_env_overrides


def test_build_env_overrides_pins_papers_dir(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.invalid/v1")
    env = build_env_overrides(papers_dir=Path("/tmp/cae"))
    assert env["PAPERS_QA_PAPERS_DIR"] == "/tmp/cae"
    assert env["OPENAI_API_KEY"] == "sk-test"
    # No English-override addendum (questions are Chinese).
    assert "PAPERS_QA_SYSTEM_PROMPT_ADDENDUM" not in env
    assert env["PAPERS_QA_DISABLE_DISK_LOGGER"] == "1"


def test_build_env_overrides_requires_api_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    import pytest as _pytest
    with _pytest.raises(ValueError, match="OPENAI_API_KEY"):
        build_env_overrides(papers_dir=Path("/tmp/cae"))


def test_main_dry_run_writes_output_with_null_answers(tmp_path: Path, monkeypatch) -> None:
    """--dry-run: skip inference, just round-trip the JSON with null rlm_answer/rlm_error."""
    in_path = tmp_path / "rubrics.json"
    in_path.write_text(json.dumps(
        [{"question_id": "1", "question": "Q1", "reference_answer": "R1"}],
        ensure_ascii=False,
    ))
    out_path = tmp_path / "rubrics-out.json"
    jsonl_path = tmp_path / "answers.jsonl"
    papers = tmp_path / "papers"
    papers.mkdir()
    (papers / "a.md").write_text("x")

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setattr(_sys, "argv", [
        "generate_rlm_answers.py",
        "--input", str(in_path),
        "--output", str(out_path),
        "--jsonl", str(jsonl_path),
        "--papers-dir", str(papers),
        "--dry-run",
    ])
    from generate_rlm_answers import main
    rc = main()
    assert rc == 0
    out = json.loads(out_path.read_text())
    assert out[0]["question_id"] == "1"
    assert out[0]["reference_answer"] == "R1"
    assert out[0]["rlm_answer"] is None
    assert out[0]["rlm_error"] is None


def test_main_invokes_run_inference_with_correct_args(tmp_path, monkeypatch) -> None:
    in_path = tmp_path / "rubrics.json"
    in_path.write_text(json.dumps(
        [{"question_id": "1", "question": "Q1"},
         {"question_id": "2", "question": "Q2"}],
        ensure_ascii=False,
    ))
    out_path = tmp_path / "out.json"
    jsonl_path = tmp_path / "ans.jsonl"
    papers = tmp_path / "papers"
    papers.mkdir()
    (papers / "x.md").write_text("y")

    # Pretend inference produced two records.
    def fake_run_inference(*, items, out_path, max_workers, use_processes, env_overrides):
        assert use_processes is True
        assert env_overrides["PAPERS_QA_PAPERS_DIR"] == str(papers)
        assert max_workers == 3
        assert [it["id"] for it in items] == ["1", "2"]
        out_path.write_text(
            json.dumps({"id": "1", "answer": "A1", "error": None}) + "\n"
            + json.dumps({"id": "2", "answer": "A2", "error": None}) + "\n"
        )

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setattr(_sys, "argv", [
        "generate_rlm_answers.py",
        "--input", str(in_path),
        "--output", str(out_path),
        "--jsonl", str(jsonl_path),
        "--papers-dir", str(papers),
        "--workers", "3",
    ])
    import generate_rlm_answers as mod
    monkeypatch.setattr(mod, "run_inference", fake_run_inference)
    rc = mod.main()
    assert rc == 0
    out = json.loads(out_path.read_text())
    assert out[0]["rlm_answer"] == "A1"
    assert out[1]["rlm_answer"] == "A2"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest tests/test_generate_rlm_answers.py -v
```
Expected: ImportError on `build_env_overrides` / `main`.

- [ ] **Step 3: Implement CLI**

Append to `src/generate_rlm_answers.py`:

```python
import argparse
import sys

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
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/python -m pytest tests/test_generate_rlm_answers.py -v
```
Expected: 17 passed.

- [ ] **Step 5: Lint check (script must be syntactically clean)**

```bash
.venv/bin/python -c "import ast; ast.parse(open('src/generate_rlm_answers.py').read())"
.venv/bin/python src/generate_rlm_answers.py --help
```
Expected: no error; argparse `--help` prints all flags.

- [ ] **Step 6: Commit**

```bash
git add src/generate_rlm_answers.py tests/test_generate_rlm_answers.py
git commit -m "feat(rlm-answers): CLI for generating rlm_answer over rubrics JSON"
```

---

## Task 5: Two-question smoke test against real CAE corpus

This is a real-API call task (small spend, ~2 × $0.05 ≈ $0.10). Confirms env wiring, process pool, paper loading, JSON round-trip.

- [ ] **Step 1: Build a 2-item subset fixture**

```bash
cd /home/juli/RLM
.venv/bin/python - <<'PY'
import json
from pathlib import Path
src = json.loads(Path("data/CAE-v2.0-1-rubrics.json").read_text())
subset = src[:2]
Path("outputs/rlm-answers").mkdir(parents=True, exist_ok=True)
Path("outputs/rlm-answers/cae-v2.0-1-smoke-input.json").write_text(
    json.dumps(subset, ensure_ascii=False, indent=2) + "\n"
)
print("Wrote smoke input:", len(subset), "items")
for it in subset:
    print(" ", it["question_id"], it["question"][:60])
PY
```
Expected: prints 2 question_ids and their question text.

- [ ] **Step 2: Source `.env` and run the smoke**

```bash
cd /home/juli/RLM
set -a; source papers_qa/.env; set +a
.venv/bin/python src/generate_rlm_answers.py \
    --input outputs/rlm-answers/cae-v2.0-1-smoke-input.json \
    --output outputs/rlm-answers/cae-v2.0-1-smoke-output.json \
    --jsonl outputs/rlm-answers/cae-v2.0-1-smoke.jsonl \
    --papers-dir /home/juli/RLM/CAE-MDs \
    --workers 2 \
    2>&1 | tee outputs/rlm-answers/cae-v2.0-1-smoke.log
```
Expected: log shows "Loaded 2 rubric items", per-process "PapersQA ready: 8 papers", and `[2/2]` completion within ~5 minutes. Final line: "Wrote ... 2/2 answered, 0 errored."

- [ ] **Step 3: Inspect smoke output**

```bash
.venv/bin/python - <<'PY'
import json
o = json.loads(open("outputs/rlm-answers/cae-v2.0-1-smoke-output.json").read())
for it in o:
    print("---", it["question_id"], "---")
    print("Q:", it["question"][:80])
    print("REF:", (it.get("reference_answer") or "")[:80])
    print("RLM:", (it.get("rlm_answer") or "<NULL>")[:200])
    print("ERR:", it.get("rlm_error"))
PY
```
Expected: both items have a non-null `rlm_answer` in Chinese with reasonable length (> 100 chars). `rlm_error` is `None`.

- [ ] **Step 4: Resume sanity check (re-run should be a no-op)**

```bash
.venv/bin/python src/generate_rlm_answers.py \
    --input outputs/rlm-answers/cae-v2.0-1-smoke-input.json \
    --output outputs/rlm-answers/cae-v2.0-1-smoke-output.json \
    --jsonl outputs/rlm-answers/cae-v2.0-1-smoke.jsonl \
    --papers-dir /home/juli/RLM/CAE-MDs \
    --workers 2 \
    2>&1 | tail -20
```
Expected: log says `RLM inference: 2 total, 2 done, 0 todo` — no new API calls.

- [ ] **Step 5: STOP and report**

Report back to user with:
- Both answer strings (full text)
- Wall-clock duration
- Cost (from the JSONL, sum `cost_usd`)
- Any worker startup warnings

Do NOT proceed to Task 6 (full run) until user confirms the smoke output quality.

---

## Task 6: Full 94-question run

**Pre-flight assumption:** Task 5 smoke passed and user gave explicit go-ahead.

- [ ] **Step 1: Back up the input file**

```bash
cd /home/juli/RLM
cp data/CAE-v2.0-1-rubrics.json data/CAE-v2.0-1-rubrics.backup-$(date +%Y%m%d-%H%M%S).json
ls -la data/CAE-v2.0-1-rubrics*.json
```
Expected: backup file present alongside the original.

- [ ] **Step 2: Launch the full run in the background**

```bash
cd /home/juli/RLM
set -a; source papers_qa/.env; set +a
nohup .venv/bin/python src/generate_rlm_answers.py \
    --input  data/CAE-v2.0-1-rubrics.json \
    --output data/CAE-v2.0-1-rubrics.json \
    --jsonl  outputs/rlm-answers/cae-v2.0-1.jsonl \
    --papers-dir /home/juli/RLM/CAE-MDs \
    --workers 4 \
    > outputs/rlm-answers/cae-v2.0-1.log 2>&1 &
echo "pid=$!" | tee outputs/rlm-answers/cae-v2.0-1.pid
```
Expected: PID printed and saved. The job is detached and survives terminal close.

- [ ] **Step 3: Monitor progress**

```bash
# In another shell, watch:
tail -f /home/juli/RLM/outputs/rlm-answers/cae-v2.0-1.log

# Or count completed items in the JSONL:
wc -l /home/juli/RLM/outputs/rlm-answers/cae-v2.0-1.jsonl
```
Expected: steady `[N/94] id=... status=ok` lines. ETA ≈ 25–60 min depending on model latency.

- [ ] **Step 4: Verify completion**

```bash
cd /home/juli/RLM
.venv/bin/python - <<'PY'
import json
data = json.loads(open("data/CAE-v2.0-1-rubrics.json").read())
n_ok = sum(1 for r in data if r.get("rlm_answer"))
n_err = sum(1 for r in data if r.get("rlm_error"))
n_null = sum(1 for r in data if r.get("rlm_answer") is None and r.get("rlm_error") is None)
print(f"total={len(data)} answered={n_ok} errored={n_err} still-null={n_null}")
import statistics as st
lens = [len(r["rlm_answer"]) for r in data if r.get("rlm_answer")]
if lens:
    print(f"answer length: min={min(lens)} median={int(st.median(lens))} max={max(lens)}")
errs = [r["rlm_error"] for r in data if r.get("rlm_error")]
for e in errs[:10]:
    print("ERR:", e)
PY
```
Expected: `answered + errored = 94`, `still-null = 0`, median answer length > 200 chars. If `still-null > 0`, re-run the same command from Step 2 (resume picks up where it left off).

- [ ] **Step 5: Re-run for any errored items (optional)**

Errors are usually transient (rate-limit, timeout, REPL hiccup). To retry only errored items, delete their JSONL rows and rerun:

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path
p = Path("/home/juli/RLM/outputs/rlm-answers/cae-v2.0-1.jsonl")
rows = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
kept = [r for r in rows if r.get("error") is None]
p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in kept) + "\n")
print(f"Kept {len(kept)}/{len(rows)} rows (dropped errored).")
PY

# Then re-launch (Step 2). Resume will only target the dropped items.
```

- [ ] **Step 6: Commit the final result**

```bash
cd /home/juli/RLM
git add data/CAE-v2.0-1-rubrics.json outputs/rlm-answers/cae-v2.0-1.jsonl
git commit -m "data(cae): generate rlm_answer for 94 rubric items via papers_qa"
```
Expected: a commit containing the populated JSON + the audit-trail JSONL.

---

## Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| API cost overrun (no global budget cap, only per-call) | HIGH | Smoke first (Task 5); $-cap exposed in env via `PAPERS_QA_MAX_BUDGET_USD`; cost summed from JSONL at end |
| `ProcessPoolExecutor` worker crash mid-run | MEDIUM | Resume via JSONL is automatic; re-run is a no-op for completed items |
| RLM `LocalREPL` chdir race | MEDIUM | Already addressed by `use_processes=True` in existing `rlm_runner.py` |
| Atomic write corrupts the rubrics file on crash | LOW | `os.replace` is atomic on POSIX + same filesystem; backup taken in Task 6 Step 1 |
| Model returns English when question is Chinese | LOW | Default `papers_qa` bilingual prompt instructs Chinese reply; verified in smoke (Task 5 Step 3) |
| `CAE-MDs` filename contains spaces — search tool path issues | LOW | `papers_qa.loader` keys by stem (no path); search uses dict keys. Verified at smoke |
| 8 markdown files too few for retrieval (Benson book is ~600 pages in one .md) | LOW | `papers_qa` has its own chunking inside `search_papers()`; same setup as production |

## Estimated Complexity: LOW–MEDIUM

- Implementation: 4 tasks × ~30 min ≈ 2 h
- Smoke: ~15 min (mostly wait time)
- Full run: 30–90 min wall-clock (mostly model latency, ~$5–$15 spend)
- Total active engineer time: ≈ 3 h
