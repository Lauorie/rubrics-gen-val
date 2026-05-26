# RLM × PEEK Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire `peek.CachePolicy` (a 1024-token "orientation cache" at `/home/juli/RLM/peek`) into `papers_qa`'s `PapersQA.ask()`. PEEK builds a context map across the first 30 questions then freezes; the map is prepended to the RLM system prompt every call. Run serially (workers=1) over all 94 CAE questions to produce a v4 sidecar dataset; re-score; diff vs v3.

**Architecture:** Three integration layers — (1) `papers_qa/papers_qa/peek_integration.py` (new pure helpers: `build_peek_policy`, `completion_to_trajectory`, `PeekCfg`), (2) `papers_qa/papers_qa/runner.py` (new optional `peek_policy` parameter on `PapersQA`; `ask()` mutates `self.rlm.system_prompt` per-call), (3) `src/generate_rlm_answers.py` (new `--peek-*` flags that enforce `workers=1` and thread the policy). Existing v3 prompt directives and temperature 0.3 held constant.

**Tech Stack:** Python 3.12, `peek-ai` (installed editable from `/home/juli/RLM/peek`), pytest. No other new deps.

---

## File Structure

**Files to create:**
- `papers_qa/papers_qa/peek_integration.py` (~90 lines) — `PeekCfg` dataclass, `build_peek_policy(cfg)`, `completion_to_trajectory(completion)`.
- `tests/test_peek_integration.py` (~8 tests) — stub-LMClient policy build, trajectory extractor from synthetic completion, etc.
- `tests/test_papers_qa_peek_wiring.py` (~3 tests) — verifies `PapersQA(peek_policy=...)` prepends the map and calls `policy.update`.

**Files to modify:**
- `papers_qa/papers_qa/runner.py` — add optional `peek_policy` to `__init__` and the prepend-+-update logic in `ask`. Inner-repo commit.
- `src/generate_rlm_answers.py` — add `--peek-*` flags, enforce `--workers 1`, thread a single PEEK policy through a sequential PapersQA loop instead of `run_inference`.
- `tests/test_generate_rlm_answers.py` — 2 new tests for the `--peek-*` flag validation.

**Files NOT to modify:**
- `papers_qa/papers_qa/prompts.py` — v3 directives stay.
- `papers_qa/.env` — temperature stays at 0.3.
- `src/score_rlm_answers.py`, `src/rubrics_diff_report.py`, `src/rubrics_report.py` — already-shipped tools, reused as-is.

**Files NEVER overwritten:**
- v1/v2/v3 rubric and score files.

---

## Task 1: Install peek-ai + peek_integration helpers

**Files:**
- Modify (system): install `peek-ai` editable into `.venv`
- Create: `papers_qa/papers_qa/peek_integration.py`
- Create: `tests/test_peek_integration.py`

- [ ] **Step 1: Install peek-ai editable**

```bash
cd /home/juli/RLM
.venv/bin/pip install -e ./peek
.venv/bin/python -c "from peek import CachePolicy; from peek.llm.openai_client import OpenAIClient; print('OK')"
```
Expected: `OK`. If `ImportError: ... requires openai`, also run `.venv/bin/pip install openai`. (PEEK's `openai` extra installs it.)

- [ ] **Step 2: Write failing tests**

Create `tests/test_peek_integration.py`:

```python
"""Tests for papers_qa.peek_integration — pure helpers, no real LLM."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "papers_qa"))

from papers_qa.peek_integration import (
    PeekCfg,
    build_peek_policy,
    completion_to_trajectory,
)


def test_peekcfg_defaults() -> None:
    cfg = PeekCfg()
    assert cfg.token_budget == 1024
    assert cfg.evolve_steps == 30
    assert cfg.distiller_model == "deepseek/deepseek-v4-flash"
    assert cfg.trajectory_max_chars == 12000


def test_build_peek_policy_with_explicit_client() -> None:
    """build_peek_policy accepts a pre-built LMClient and returns a CachePolicy."""
    from peek import CachePolicy

    stub = MagicMock()
    stub.completion.return_value = "stub response"
    cfg = PeekCfg(token_budget=512, evolve_steps=5)
    policy = build_peek_policy(cfg, client=stub)
    assert isinstance(policy, CachePolicy)
    assert policy.token_budget == 512
    assert policy.evolve_steps == 5


def test_build_peek_policy_from_env(monkeypatch) -> None:
    """When no client passed, build one from OPENAI_API_KEY/OPENAI_BASE_URL."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.invalid/v1")
    cfg = PeekCfg(distiller_model="openai/gpt-5.4-mini")
    policy = build_peek_policy(cfg)
    # client built; we don't make real calls
    assert policy.client.model == "openai/gpt-5.4-mini"


def test_completion_to_trajectory_handles_none_metadata() -> None:
    """If completion.metadata is None, return just the final answer."""
    c = MagicMock()
    c.metadata = None
    c.response = "最终答案: A"
    s = completion_to_trajectory(c)
    assert "最终答案: A" in s
    assert "[Final answer]" in s


def test_completion_to_trajectory_flattens_iterations() -> None:
    """Each iteration's response/code/output appears in the trajectory string, in order."""
    c = MagicMock()
    c.metadata = {
        "iterations": [
            {"response": "I'll search for X", "code": "search('X')", "output": "found 3"},
            {"response": "Reading paper 1", "code": "llm_query(paper1)", "output": "details..."},
        ],
        "run_metadata": {"model": "deepseek"},
    }
    c.response = "X is Y because Z"
    s = completion_to_trajectory(c)
    assert s.find("I'll search for X") < s.find("Reading paper 1")
    assert "search('X')" in s
    assert "found 3" in s
    assert "X is Y because Z" in s
    assert "[Final answer]" in s


def test_completion_to_trajectory_truncates_to_max_chars() -> None:
    """Very long trajectories are hard-truncated at the configured limit."""
    c = MagicMock()
    big = "x" * 50000
    c.metadata = {"iterations": [{"response": big, "code": "", "output": ""}],
                  "run_metadata": {}}
    c.response = "tail"
    s = completion_to_trajectory(c, max_chars=500)
    assert len(s) <= 500 + 200  # allow a small header overhead
    assert "tail" in s  # final answer must always appear


def test_completion_to_trajectory_handles_missing_keys() -> None:
    """Missing 'code' or 'output' in an iteration shouldn't crash."""
    c = MagicMock()
    c.metadata = {"iterations": [{"response": "thinking"}], "run_metadata": {}}
    c.response = "answer"
    s = completion_to_trajectory(c)
    assert "thinking" in s
    assert "answer" in s


def test_build_peek_policy_requires_api_key_or_client(monkeypatch) -> None:
    """Without OPENAI_API_KEY and no client, build_peek_policy raises."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    import pytest as _pytest
    with _pytest.raises((KeyError, ValueError)):
        build_peek_policy(PeekCfg())
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd /home/juli/RLM
.venv/bin/python -m pytest tests/test_peek_integration.py -v
```
Expected: 8 failing tests (ImportError on `papers_qa.peek_integration`).

- [ ] **Step 4: Implement `papers_qa/papers_qa/peek_integration.py`**

```python
"""Glue between papers_qa and the PEEK orientation-cache library.

Exposes:
  - PeekCfg: dataclass with token_budget, evolve_steps, distiller_model, etc.
  - build_peek_policy(cfg, client=None) -> peek.CachePolicy
  - completion_to_trajectory(completion, max_chars=12000) -> str
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from peek import CachePolicy
from peek.llm.base import LMClient
from peek.llm.openai_client import OpenAIClient


@dataclass
class PeekCfg:
    """Configuration for the PEEK CachePolicy used by papers_qa."""
    token_budget: int = 1024
    evolve_steps: int | None = 30
    distiller_model: str = "deepseek/deepseek-v4-flash"
    trajectory_max_chars: int = 12000
    api_key: str | None = None      # overrides OPENAI_API_KEY when set
    base_url: str | None = None     # overrides OPENAI_BASE_URL when set


def build_peek_policy(
    cfg: PeekCfg,
    *,
    client: LMClient | None = None,
) -> CachePolicy:
    """Construct a CachePolicy using cfg.

    If ``client`` is provided, it's used directly. Otherwise an OpenAIClient is
    built from cfg (api_key, base_url) or env (OPENAI_API_KEY, OPENAI_BASE_URL).
    """
    if client is None:
        api_key = cfg.api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "build_peek_policy: no client passed and OPENAI_API_KEY not set"
            )
        base_url = cfg.base_url or os.environ.get("OPENAI_BASE_URL")
        client = OpenAIClient(
            model=cfg.distiller_model,
            api_key=api_key,
            base_url=base_url,
        )
    return CachePolicy(
        client=client,
        token_budget=cfg.token_budget,
        evolve_steps=cfg.evolve_steps,
    )


def completion_to_trajectory(completion: Any, max_chars: int = 12000) -> str:
    """Render a papers_qa Completion (or any object with .metadata + .response)
    into a single trajectory string for the PEEK Distiller.

    Format:
        [Iter 0] response: ...
        [Iter 0] code: ...
        [Iter 0] output: ...
        [Iter 1] response: ...
        ...
        [Final answer]: ...
    """
    parts: list[str] = []
    meta = getattr(completion, "metadata", None) or {}
    iterations = meta.get("iterations") if isinstance(meta, dict) else None
    if iterations:
        for i, it in enumerate(iterations):
            resp = (it.get("response") or "").strip()
            code = (it.get("code") or "").strip()
            out = (it.get("output") or "").strip()
            if resp:
                parts.append(f"[Iter {i}] response: {resp}")
            if code:
                parts.append(f"[Iter {i}] code: {code}")
            if out:
                parts.append(f"[Iter {i}] output: {out}")

    body = "\n".join(parts)
    if len(body) > max_chars:
        body = body[:max_chars] + "\n... [truncated]"

    final = (getattr(completion, "response", "") or "").strip()
    return body + ("\n\n" if body else "") + f"[Final answer]: {final}"
```

- [ ] **Step 5: Run tests, expect 8 to pass**

```bash
.venv/bin/python -m pytest tests/test_peek_integration.py -v
```
Expected: 8 passed.

- [ ] **Step 6: Commit**

In the **inner** `papers_qa` repo (since `peek_integration.py` lives there):
```bash
cd /home/juli/RLM
git -C papers_qa add papers_qa/peek_integration.py
git -C papers_qa commit -m "feat(papers_qa): PEEK integration helpers (cfg, policy builder, trajectory)"
```

In the **outer** repo (tests only):
```bash
git add tests/test_peek_integration.py
git commit -m "test(peek): cover peek_integration helpers"
```

---

## Task 2: Wire PEEK into PapersQA.runner

**Files:**
- Modify: `papers_qa/papers_qa/runner.py` — add optional `peek_policy` parameter; mutate `rlm.system_prompt` per ask; call `policy.update` after each completion.
- Create: `tests/test_papers_qa_peek_wiring.py` — 3 tests with a mock policy.

- [ ] **Step 1: Write failing tests**

Create `tests/test_papers_qa_peek_wiring.py`:

```python
"""Verify PapersQA.ask wires the PEEK policy correctly."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "papers_qa"))


@pytest.fixture
def tiny_corpus(tmp_path, monkeypatch):
    p = tmp_path / "papers"
    p.mkdir()
    (p / "TinyPaper_2026.md").write_text("Tiny content.")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("PAPERS_QA_MODEL", "google/gemini-3.1-flash-lite")
    monkeypatch.setenv("PAPERS_QA_PAPERS_DIR", str(p))
    return p


def test_papersqa_accepts_none_peek_policy_noop(tiny_corpus):
    """peek_policy=None must be the default and a complete no-op."""
    from papers_qa.config import PapersQAConfig
    from papers_qa.runner import PapersQA
    cfg = PapersQAConfig.from_env()
    qa = PapersQA(cfg)  # no peek_policy kwarg
    assert qa.peek_policy is None
    assert "## CONTEXT ROADMAP" not in qa.rlm.system_prompt  # no map prepended


def test_papersqa_prepends_map_when_policy_provided(tiny_corpus, monkeypatch):
    """When peek_policy is set, ask() must prepend the policy's current map."""
    from papers_qa.config import PapersQAConfig
    from papers_qa.runner import PapersQA
    cfg = PapersQAConfig.from_env()

    fake_policy = MagicMock()
    fake_policy.current_map_text = "## CONTEXT ROADMAP\n[mock-1] sample item\n"
    fake_policy.update = MagicMock(return_value=None)

    qa = PapersQA(cfg, peek_policy=fake_policy)

    fake_completion = MagicMock()
    fake_completion.response = "答案"
    fake_completion.metadata = {"iterations": [], "run_metadata": {}}
    fake_completion.usage_summary = None
    fake_completion.execution_time = 1.23
    qa.rlm.completion = MagicMock(return_value=fake_completion)

    qa.ask("测试问题")
    # The policy's map text appears in the system prompt at ask time.
    assert "## CONTEXT ROADMAP" in qa.rlm.system_prompt
    assert "[mock-1] sample item" in qa.rlm.system_prompt


def test_papersqa_calls_policy_update_after_completion(tiny_corpus, monkeypatch):
    """ask() must call policy.update exactly once per ask, with trajectory + question."""
    from papers_qa.config import PapersQAConfig
    from papers_qa.runner import PapersQA
    cfg = PapersQAConfig.from_env()

    fake_policy = MagicMock()
    fake_policy.current_map_text = "## CONTEXT ROADMAP\n"
    fake_policy.update = MagicMock(return_value=None)

    qa = PapersQA(cfg, peek_policy=fake_policy)

    fake_completion = MagicMock()
    fake_completion.response = "final answer"
    fake_completion.metadata = {"iterations": [{"response": "thinking"}], "run_metadata": {}}
    fake_completion.usage_summary = None
    fake_completion.execution_time = 1.0
    qa.rlm.completion = MagicMock(return_value=fake_completion)

    qa.ask("Q1")
    assert fake_policy.update.call_count == 1
    _, kwargs = fake_policy.update.call_args
    assert kwargs["question"] == "Q1"
    assert "final answer" in kwargs["trajectory"]
    assert "thinking" in kwargs["trajectory"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/juli/RLM
.venv/bin/python -m pytest tests/test_papers_qa_peek_wiring.py -v
```
Expected: errors / failures (e.g., `TypeError: PapersQA.__init__() got an unexpected keyword 'peek_policy'`).

- [ ] **Step 3: Modify `papers_qa/papers_qa/runner.py`**

Locate the `PapersQA.__init__` method. Add `peek_policy` as a keyword-only parameter with default `None`. Store the base system prompt (current `self.system_prompt`) so we can re-derive it on each ask. Locate `ask()` and add the prepend + update logic.

Apply these edits:

(a) In `__init__`, change the signature:
```python
def __init__(self, config: PapersQAConfig, *, peek_policy: Any | None = None) -> None:
```

(b) After `self.system_prompt` is finalized (right before `self.logger = ...` or wherever `system_prompt` is set), add:
```python
self.peek_policy = peek_policy
self._base_system_prompt = self.system_prompt  # snapshot — pre-PEEK
```

(c) Modify `ask` from its current form:
```python
def ask(self, question: str) -> AskResult:
    """Ask a (Chinese) question against the corpus, return the answer + trajectory."""
    completion = self.rlm.completion(prompt=self.papers, root_prompt=question)
    cost = (
        completion.usage_summary.total_cost
        if completion.usage_summary
        else None
    )
    return AskResult(
        question=question,
        answer=completion.response,
        cost_usd=cost,
        duration_s=completion.execution_time,
        trajectory=completion.metadata,
    )
```

to:

```python
def ask(self, question: str) -> AskResult:
    """Ask a (Chinese) question against the corpus, return the answer + trajectory."""
    if self.peek_policy is not None:
        map_text = self.peek_policy.current_map_text
        self.rlm.system_prompt = (
            self._base_system_prompt
            + "\n\n================ Context Map (PEEK) ================\n"
            + map_text
            + "================ End of Context Map ================\n"
        )

    completion = self.rlm.completion(prompt=self.papers, root_prompt=question)

    if self.peek_policy is not None:
        from papers_qa.peek_integration import completion_to_trajectory
        traj = completion_to_trajectory(completion)
        try:
            self.peek_policy.update(trajectory=traj, question=question)
        except Exception as e:
            logger.warning("PEEK policy.update failed (continuing): %s", e)

    cost = (
        completion.usage_summary.total_cost
        if completion.usage_summary
        else None
    )
    return AskResult(
        question=question,
        answer=completion.response,
        cost_usd=cost,
        duration_s=completion.execution_time,
        trajectory=completion.metadata,
    )
```

(d) Update the docstring of `__init__` (or add a 1-line comment) to mention `peek_policy`.

- [ ] **Step 4: Run the new tests, expect 3 passed**

```bash
.venv/bin/python -m pytest tests/test_papers_qa_peek_wiring.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Run full pytest to confirm no regressions**

```bash
.venv/bin/python -m pytest tests/ -q --no-header 2>&1 | tail -3
```
Expected: all prior tests + 11 new tests pass.

- [ ] **Step 6: Commit**

```bash
cd /home/juli/RLM
git -C papers_qa add papers_qa/runner.py
git -C papers_qa commit -m "feat(papers_qa): optional peek_policy threading through ask()"
git add tests/test_papers_qa_peek_wiring.py
git commit -m "test(peek): verify PapersQA wires peek_policy correctly"
```

---

## Task 3: Add CLI flags + serial PEEK loop to generate_rlm_answers.py

**Files:**
- Modify: `src/generate_rlm_answers.py` — add `--peek-map-out`, `--peek-token-budget`, `--peek-evolve-steps`, `--peek-distiller-model` flags; when `--peek-map-out` set, force `workers==1` and execute serially with a single PapersQA + policy.
- Modify: `tests/test_generate_rlm_answers.py` — 2 new tests for flag validation.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_generate_rlm_answers.py` (at the end of the file):

```python


def test_peek_flag_requires_workers_one(tmp_path, monkeypatch) -> None:
    """--peek-map-out with --workers > 1 must error before any LLM call."""
    in_path = tmp_path / "rubrics.json"
    in_path.write_text(json.dumps([{"item_idx": 0, "question": "Q", "rlm_answer": None}], ensure_ascii=False))
    papers = tmp_path / "papers"; papers.mkdir(); (papers / "x.md").write_text("y")

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setattr(_sys, "argv", [
        "generate_rlm_answers.py",
        "--input", str(in_path),
        "--output", str(tmp_path / "out.json"),
        "--jsonl", str(tmp_path / "ans.jsonl"),
        "--papers-dir", str(papers),
        "--workers", "4",
        "--peek-map-out", str(tmp_path / "map.json"),
    ])
    import generate_rlm_answers as mod
    with __import__("pytest").raises(SystemExit):
        mod.main()


def test_peek_flag_runs_serial_with_single_policy(tmp_path, monkeypatch) -> None:
    """--peek-map-out causes serial execution and a single shared CachePolicy."""
    in_path = tmp_path / "rubrics.json"
    in_path.write_text(json.dumps(
        [{"item_idx": 0, "question": "Q0", "rlm_answer": None},
         {"item_idx": 1, "question": "Q1", "rlm_answer": None}],
        ensure_ascii=False,
    ))
    out_path = tmp_path / "out.json"
    jsonl_path = tmp_path / "ans.jsonl"
    map_path = tmp_path / "map.json"
    papers = tmp_path / "papers"; papers.mkdir(); (papers / "x.md").write_text("y")

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.invalid/v1")

    # Fake PapersQA whose ask returns a fixed AskResult — captures peek_policy
    captured: dict[str, Any] = {}

    class FakePapersQA:
        def __init__(self, cfg, *, peek_policy=None):
            captured.setdefault("policies", []).append(peek_policy)
            self.peek_policy = peek_policy
        def ask(self, question):
            captured.setdefault("questions", []).append(question)
            from papers_qa.runner import AskResult
            return AskResult(question=question, answer="A", cost_usd=None,
                             duration_s=0.0, trajectory=None)

    # Fake CachePolicy with .save
    saved_paths: list[str] = []
    class FakePolicy:
        current_map_text = "## CONTEXT ROADMAP\n"
        def update(self, **kw): return None
        def save(self, p): saved_paths.append(str(p))

    def fake_build_policy(cfg, client=None):
        return FakePolicy()

    monkeypatch.setattr(_sys, "argv", [
        "generate_rlm_answers.py",
        "--input", str(in_path),
        "--output", str(out_path),
        "--jsonl", str(jsonl_path),
        "--papers-dir", str(papers),
        "--workers", "1",
        "--peek-map-out", str(map_path),
    ])
    import generate_rlm_answers as mod
    monkeypatch.setattr(mod, "PapersQA", FakePapersQA)
    monkeypatch.setattr(mod, "build_peek_policy", fake_build_policy)

    assert mod.main() == 0
    # One policy instance used for both items
    assert len(captured["policies"]) == 1
    assert captured["questions"] == ["Q0", "Q1"]
    # save was called at least once
    assert saved_paths
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest tests/test_generate_rlm_answers.py::test_peek_flag_requires_workers_one tests/test_generate_rlm_answers.py::test_peek_flag_runs_serial_with_single_policy -v
```
Expected: 2 failures (unknown flag / unknown attribute).

- [ ] **Step 3: Modify `src/generate_rlm_answers.py`**

(a) At the top imports block, add:
```python
sys.path.insert(0, str(_RLM_ROOT / "papers_qa"))
from papers_qa.runner import PapersQA  # noqa: E402
from papers_qa.config import PapersQAConfig  # noqa: E402
from papers_qa.peek_integration import PeekCfg, build_peek_policy  # noqa: E402
```
(Place after the existing `_RLM_ROOT` block.)

(b) In `main()`, after `args = parser.parse_args()` and before logging setup, add the new flags. Find the existing argparse block and append:

```python
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
```

(c) After `args = parser.parse_args()` and before the inference dispatch, add a PEEK branch:

```python
if args.peek_map_out is not None:
    if args.workers != 1:
        parser.error("--peek-map-out requires --workers 1 (single-process for shared cache)")
    args.peek_map_out.parent.mkdir(parents=True, exist_ok=True)
```

(d) Replace the inference dispatch. Find the current block:
```python
if not args.dry_run:
    items = to_inference_items(rubrics)
    ...
    run_inference(items=items, out_path=args.jsonl, max_workers=args.workers,
                  use_processes=True, env_overrides=...)
```
and change it to handle the PEEK case BEFORE the existing `run_inference` call:

```python
if not args.dry_run:
    items = to_inference_items(rubrics)
    args.jsonl.parent.mkdir(parents=True, exist_ok=True)

    if args.peek_map_out is not None:
        # Serial PEEK loop — one PapersQA + one CachePolicy.
        logger.info("Running serial PEEK loop on %d items (workers=1)", len(items))
        from rlm_runner import load_done_ids, write_record  # reuse helpers
        done = load_done_ids(args.jsonl)
        todo = [it for it in items if it["id"] not in done]
        logger.info("PEEK serial: %d todo (%d already done)", len(todo), len(done))

        peek_cfg = PeekCfg(
            token_budget=args.peek_token_budget,
            evolve_steps=args.peek_evolve_steps,
            distiller_model=args.peek_distiller_model,
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
            # Save the policy at the evolve_steps boundary and at the end.
            if policy.evolving is False or (i + 1) == args.peek_evolve_steps:
                policy.save(args.peek_map_out)
        policy.save(args.peek_map_out)
    else:
        logger.info("Running inference on %d items, workers=%d", len(items), args.workers)
        env_overrides = build_env_overrides(papers_dir=args.papers_dir)
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
```

(Note: keep the existing non-PEEK branch unchanged in behavior — just nested in an `else`.)

- [ ] **Step 4: Run new tests, expect 2 passed**

```bash
.venv/bin/python -m pytest tests/test_generate_rlm_answers.py::test_peek_flag_requires_workers_one tests/test_generate_rlm_answers.py::test_peek_flag_runs_serial_with_single_policy -v
```
Expected: 2 passed.

- [ ] **Step 5: Full regression**

```bash
.venv/bin/python -m pytest tests/ -q --no-header 2>&1 | tail -3
```
Expected: all tests pass.

- [ ] **Step 6: --help sanity check**

```bash
.venv/bin/python src/generate_rlm_answers.py --help 2>&1 | grep -i peek
```
Expected: 4 lines listing the new flags.

- [ ] **Step 7: Commit**

```bash
git add src/generate_rlm_answers.py tests/test_generate_rlm_answers.py
git commit -m "feat(rlm-answers): --peek-* flags for serial PEEK-cached inference"
```

---

## Task 4: 2-question PEEK smoke

Real-API run on 2 items to confirm wiring + the PEEK calls actually fire against aiberm. Cost ~$0.30, ~10 min.

- [ ] **Step 1: Build a 2-item subset (reuse from prior smoke)**

```bash
cd /home/juli/RLM
.venv/bin/python - <<'PY'
import json
from pathlib import Path
src = json.load(open("data/CAE-v2.0-1-rubrics.json"))
Path("outputs/rlm-answers").mkdir(parents=True, exist_ok=True)
Path("outputs/rlm-answers/cae-v2.0-1-peek-smoke-input.json").write_text(
    json.dumps(src[:2], ensure_ascii=False, indent=2) + "\n")
print(f"wrote 2-item smoke input")
PY
```

- [ ] **Step 2: Run with PEEK enabled (small evolve_steps=2 so map evolves on both items)**

```bash
cd /home/juli/RLM
set -a && source papers_qa/.env && set +a
rm -f outputs/rlm-answers/cae-v2.0-1-peek-smoke.jsonl outputs/rlm-answers/cae-v2.0-1-peek-smoke-output.json
.venv/bin/python src/generate_rlm_answers.py \
    --input  outputs/rlm-answers/cae-v2.0-1-peek-smoke-input.json \
    --output outputs/rlm-answers/cae-v2.0-1-peek-smoke-output.json \
    --jsonl  outputs/rlm-answers/cae-v2.0-1-peek-smoke.jsonl \
    --papers-dir /home/juli/RLM/CAE-MDs \
    --workers 1 \
    --peek-map-out outputs/peek/cae-smoke-map.json \
    --peek-evolve-steps 2 \
    2>&1 | tee outputs/rlm-answers/cae-v2.0-1-peek-smoke.log | tail -30
```
Expected last line: `Wrote ... — 2/2 answered, 0 errored.` Log should show `[peek 1/2]` and `[peek 2/2]` lines.

- [ ] **Step 3: Inspect the frozen map**

```bash
.venv/bin/python - <<'PY'
import json
m = json.load(open("outputs/peek/cae-smoke-map.json"))
print(f"map text length: {len(m['map_text'])} chars")
print(f"steps: {m['steps']}  token_budget: {m['token_budget']}")
print("--- map_text head ---")
print(m["map_text"][:1500])
PY
```
Expected: non-trivial map_text (≥ 200 chars) with at least one populated section (likely CONTEXT ROADMAP or DOMAIN CONSTANTS based on the 2 FSI/HJC questions). `steps` should equal 2.

- [ ] **Step 4: Verify both smoke answers are non-empty**

```bash
.venv/bin/python - <<'PY'
import json
o = json.load(open("outputs/rlm-answers/cae-v2.0-1-peek-smoke-output.json"))
for it in o:
    a = it.get("rlm_answer") or ""
    print(f"item_idx={it['item_idx']}  len={len(a)}  err={it.get('rlm_error')}")
    print(f"  first 150 chars: {a[:150]}")
PY
```
Expected: both items have rlm_answer with > 100 chars and no error.

- [ ] **Step 5: STOP and report to controller**

Report:
- Smoke output sample
- Frozen map preview (first 1500 chars)
- Wall clock
- Any unexpected warnings or PEEK errors

Do NOT proceed to Task 5 (full run) until controller confirms.

---

## Task 5: Full v4 run (94 items, serial, ~4h)

**Pre-flight assumption:** Task 4 smoke passed and controller approved.

- [ ] **Step 1: Pre-flight checks**

```bash
cd /home/juli/RLM
grep -c "回答风格要求" papers_qa/papers_qa/prompts.py  # expect 1 (v3 directives still in place)
grep TEMPERATURE papers_qa/.env                       # expect 0.3
.venv/bin/python -c "from papers_qa.peek_integration import PeekCfg; print('OK')"
```
Expected: `1`, `PAPERS_QA_TEMPERATURE=0.3`, `OK`.

- [ ] **Step 2: Launch the v4 run in background**

```bash
cd /home/juli/RLM
set -a && source papers_qa/.env && set +a
mkdir -p outputs/peek
nohup .venv/bin/python src/generate_rlm_answers.py \
    --input  data/CAE-v2.0-1-rubrics.json \
    --output data/CAE-v2.0-1-rubrics-v4.json \
    --jsonl  outputs/rlm-answers/cae-v2.0-1-v4.jsonl \
    --papers-dir /home/juli/RLM/CAE-MDs \
    --workers 1 \
    --peek-map-out outputs/peek/cae-v2.0-1-map-frozen.json \
    --peek-evolve-steps 30 \
    --peek-token-budget 1024 \
    --peek-distiller-model deepseek/deepseek-v4-flash \
    > outputs/rlm-answers/cae-v2.0-1-v4.log 2>&1 &
PID=$!
disown
echo "pid=$PID" | tee outputs/rlm-answers/cae-v2.0-1-v4.pid
sleep 10
head -15 outputs/rlm-answers/cae-v2.0-1-v4.log
```
Expected: PID printed, log shows "Running serial PEEK loop on 94 items (workers=1)" and the first `[peek 1/94]` line within a couple minutes.

- [ ] **Step 3: Wait for completion (~4h, but resumable)**

Use a Monitor that watches `wc -l outputs/rlm-answers/cae-v2.0-1-v4.jsonl` and emits at milestones (every 10) + completion. If the run dies mid-way, resume by re-running the same command — `load_done_ids` skips completed items.

- [ ] **Step 4: Verify completion + length stats**

```bash
cd /home/juli/RLM
.venv/bin/python - <<'PY'
import json, statistics as st
v3 = json.load(open("data/CAE-v2.0-1-rubrics-v3.json"))
v4 = json.load(open("data/CAE-v2.0-1-rubrics-v4.json"))
assert len(v3) == len(v4) == 94
# Immutable fields preserved
mutable = {"rlm_answer", "rlm_error"}
diffs = sum(1 for a, b in zip(sorted(v3, key=lambda r: r["item_idx"]),
                              sorted(v4, key=lambda r: r["item_idx"]))
            if {k: v for k, v in a.items() if k not in mutable}
               != {k: v for k, v in b.items() if k not in mutable})
assert diffs == 0, f"{diffs} items have differing immutable fields"
ok = [r for r in v4 if r.get("rlm_answer")]
print(f"v4 answered: {len(ok)}/94")
L3 = [len(r["rlm_answer"]) for r in v3 if r.get("rlm_answer")]
L4 = [len(r["rlm_answer"]) for r in v4 if r.get("rlm_answer")]
print(f"v3 median={int(st.median(L3))} mean={int(st.mean(L3))}")
print(f"v4 median={int(st.median(L4))} mean={int(st.mean(L4))}")
PY
```
Expected: `v4 answered: 94/94`. v4 length should be in the same ballpark as v3 (PEEK doesn't directly affect length).

- [ ] **Step 5: Inspect the frozen map**

```bash
.venv/bin/python - <<'PY'
import json
m = json.load(open("outputs/peek/cae-v2.0-1-map-frozen.json"))
print(f"map_text length: {len(m['map_text'])} chars")
print(f"steps={m['steps']}  token_budget={m['token_budget']}  evolve_steps={m['evolve_steps']}")
print("\n--- full map_text ---\n")
print(m["map_text"])
PY
```
Expected: a populated map (≥ 500 chars) with multiple sections (CONTEXT ROADMAP, DOMAIN CONSTANTS, etc.). `steps` should be ≥ 30 (evolution finished).

- [ ] **Step 6: Commit v4 rubrics + jsonl + log + map**

```bash
cd /home/juli/RLM
git add data/CAE-v2.0-1-rubrics-v4.json \
        outputs/rlm-answers/cae-v2.0-1-v4.jsonl \
        outputs/rlm-answers/cae-v2.0-1-v4.log \
        outputs/peek/cae-v2.0-1-map-frozen.json
git commit -m "data(cae): v4 rlm_answer with PEEK orientation cache (evolve_steps=30)"
```

---

## Task 6: Re-score v4 + diff vs v3 + AC check + commit

- [ ] **Step 1: Re-score v4 in background (~5 min, ~$15)**

```bash
cd /home/juli/RLM
set -a && source papers_qa/.env && set +a
nohup .venv/bin/python src/score_rlm_answers.py \
    --input       data/CAE-v2.0-1-rubrics-v4.json \
    --anchors     data/CAE-anchor-scores.json \
    --scores-out  outputs/scoring/cae-v2.0-1-scores-v4.json \
    --report-out  outputs/scoring/cae-v2.0-1-report-v4.md \
    --judge-model openai/gpt-5.5 \
    --concurrency 16 \
    --worst-n     10 \
    > outputs/scoring/cae-v2.0-1-v4.log 2>&1 &
echo "scoring pid=$!"
disown
```

- [ ] **Step 2: Wait for scoring + verify**

```bash
for i in $(seq 1 60); do
    if grep -q "wrote scores=" outputs/scoring/cae-v2.0-1-v4.log 2>/dev/null; then break; fi
    sleep 15
done
tail -3 outputs/scoring/cae-v2.0-1-v4.log
```
Expected: `wrote scores=... report=... (94 items scored ok, 0 errors)`.

- [ ] **Step 3: Generate diffs (v1-vs-v4 and v3-vs-v4)**

```bash
cd /home/juli/RLM
.venv/bin/python src/rubrics_diff_report.py \
    --scores-v1 outputs/scoring/cae-v2.0-1-scores.json \
    --scores-v2 outputs/scoring/cae-v2.0-1-scores-v4.json \
    --rubrics   data/CAE-v2.0-1-rubrics-v4.json \
    --out       outputs/scoring/cae-v2.0-1-diff-v1-v4.md \
    --top-n     5

.venv/bin/python src/rubrics_diff_report.py \
    --scores-v1 outputs/scoring/cae-v2.0-1-scores-v3.json \
    --scores-v2 outputs/scoring/cae-v2.0-1-scores-v4.json \
    --rubrics   data/CAE-v2.0-1-rubrics-v4.json \
    --out       outputs/scoring/cae-v2.0-1-diff-v3-v4.md \
    --top-n     5
```

- [ ] **Step 4: AC verification**

```bash
.venv/bin/python - <<'PY'
import json, statistics as st
from collections import Counter

def trips(s):
    c = Counter()
    for r in s:
        for b in r.get("breakdown", []):
            if b["criterion_type"] == "anti_hacking" and b["met"]:
                c[b["text"]] += 1
    return c

def mean_anc(s):
    xs = [r["score_anchored"]["normalized"] for r in s
          if r.get("score_anchored") and r["score_anchored"].get("normalized") is not None]
    return sum(xs)/len(xs)

def ct_rates(s):
    counter = {}
    for r in s:
        for b in r.get("breakdown",[]):
            if b["sign"] != "positive": continue
            ct = b["criterion_type"]
            slot = counter.setdefault(ct, [0,0])
            slot[0] += 1
            if b["met"]: slot[1] += 1
    return {ct: m/t*100 if t else 0 for ct,(t,m) in counter.items()}

s1 = json.load(open("outputs/scoring/cae-v2.0-1-scores.json"))
s3 = json.load(open("outputs/scoring/cae-v2.0-1-scores-v3.json"))
s4 = json.load(open("outputs/scoring/cae-v2.0-1-scores-v4.json"))

a1, a3, a4 = mean_anc(s1), mean_anc(s3), mean_anc(s4)
print(f"=== anchored means ===")
print(f"  v1={a1:.3f}  v3={a3:.3f}  v4={a4:.3f}")
print(f"  v4 vs v3: {a4-a3:+.3f}   v4 vs v1: {a4-a1:+.3f}")
print(f"  AC #9 (v4 anchored ≥ v3 − 0.02): {'PASS ✅' if a4 >= a3 - 0.02 else 'FAIL ❌'}")
print()
print(f"=== decision_logic (the stubborn gap) ===")
r1, r3, r4 = ct_rates(s1), ct_rates(s3), ct_rates(s4)
print(f"  v1={r1.get('decision_logic',0):.1f}%  v3={r3.get('decision_logic',0):.1f}%  v4={r4.get('decision_logic',0):.1f}%")
print(f"  v4 vs v3: {r4.get('decision_logic',0)-r3.get('decision_logic',0):+.1f}pp")
print(f"  v4 vs v1: {r4.get('decision_logic',0)-r1.get('decision_logic',0):+.1f}pp")
print()
print(f"=== pitfall trips (v4) ===")
t4 = trips(s4)
t3 = trips(s3)
for k in sorted(set(t3)|set(t4), key=lambda k: -(t3.get(k,0)+t4.get(k,0))):
    print(f"  v3={t3.get(k,0):3d} → v4={t4.get(k,0):3d}  |  {k!r}")
PY
```

- [ ] **Step 5: Commit results**

```bash
git add outputs/scoring/cae-v2.0-1-scores-v4.json \
        outputs/scoring/cae-v2.0-1-report-v4.md \
        outputs/scoring/cae-v2.0-1-v4.log \
        outputs/scoring/cae-v2.0-1-diff-v1-v4.md \
        outputs/scoring/cae-v2.0-1-diff-v3-v4.md
git commit -m "$(cat <<'EOF'
data(cae): v4 RLM with PEEK orientation cache — scored + diffed

v4 = v3 prompt directives + PEEK CachePolicy (token_budget=1024,
evolve_steps=30, distiller=deepseek-v4-flash). Map prepended to RLM
system prompt every call; first 30 questions evolve the map, then
frozen for the remaining 64.

See outputs/scoring/cae-v2.0-1-diff-v3-v4.md for the full delta.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 6: Final summary**

Report back to controller:
- v4 anchored mean (and Δ vs v3, v1)
- decision_logic v4 hit rate (and Δ vs v3, v1)
- AC #9 PASS/FAIL
- 1-paragraph diagnostic on what the frozen map ended up containing
- Recommendation: keep v4 (and which lever to iterate next) OR discard (and what to try instead)

---

## Risks Summary

| Risk | Severity | Mitigation in plan |
|------|----------|---------------------|
| ~4 hour wall clock for serial run | LOW | Resumable via `load_done_ids`; launch in background |
| PEEK calls cost > $5 | LOW | Bounded by per-call budget; PEEK uses ~2 calls per question = ~190 calls × $0.01 ≈ $2 |
| `OpenAIClient` mismatch with aiberm | LOW | Task 4 smoke catches this before the 4-hour run |
| Map evolves on FSI-only first 30 → blind to JWL/ALE/HJC | MEDIUM | Task 5 Step 5 inspects map; if biased, document and propose Phase 5 with shuffled ordering |
| RLM trajectory format breaks distiller | LOW | `completion_to_trajectory` defensively handles missing keys |
| Anchored score regresses > 0.02 vs v3 | MEDIUM | AC #9; PEEK kept off by default if it doesn't help |
| Nested git: changes to runner.py in inner repo not visible to outer | LOW | Plan explicitly commits inner-repo changes; same pattern as Task 1 of v3 |
