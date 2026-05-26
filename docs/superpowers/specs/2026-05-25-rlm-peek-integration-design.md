# RLM × PEEK Integration — Phase 4 Design Spec

## Goal

Integrate PEEK (a 1024-token "orientation cache" for long-context LLM agents, at `/home/juli/RLM/peek`) into the `papers_qa` agent. PEEK builds a context map across the first 30 questions, then freezes; the map is prepended to the system prompt every call. Target: close the remaining substantive gaps (especially `decision_logic`, still −14pp vs v1 after v3) by giving the agent a stable cache of "what the corpus looks like" and "what canonical answers have been confirmed".

## Non-goals

- **Not** changing the v3 prompt directives or the temperature (0.3). Those are held constant so the PEEK effect is isolated.
- **Not** rewriting `papers_qa.runner` beyond what's needed to inject PEEK. Existing tests must still pass.
- **Not** sharing a cache across processes. Workers=1 (serial), ~4 hours wall clock. Phase 5 can revisit if PEEK proves beneficial.
- **Not** modifying the PEEK package itself. We import and use it as a library.

## Inputs

- `/home/juli/RLM/peek/` — PEEK source (Apache-2.0). Has `peek.CachePolicy`, `peek.llm.OpenAIClient`. Will be installed via `uv pip install -e ./peek` into the existing `.venv`.
- `data/CAE-v2.0-1-rubrics.json` — 94 items with v1 `rlm_answer` (read-only; we re-generate v4).
- `data/CAE-anchor-scores.json` — cached anchors (reused).
- `papers_qa/papers_qa/{prompts.py,runner.py}` — v3 prompt directives unchanged; `runner.py` extended to support optional PEEK policy.
- aiberm credentials from `papers_qa/.env` (`OPENAI_API_KEY`, `OPENAI_BASE_URL`).

## Outputs

- **`papers_qa/papers_qa/runner.py`** (modified): `PapersQA.__init__` accepts an optional `peek_policy: CachePolicy | None`; `PapersQA.ask` prepends `policy.current_map_text` to the system prompt and calls `policy.update(trajectory=..., question=...)` after each completion.
- **`papers_qa/papers_qa/peek_integration.py`** (new, ~80 lines): factory `build_peek_policy(config) -> CachePolicy`, trajectory extractor `completion_to_trajectory(completion) -> str`, and a small `PeekCfg` dataclass.
- **`tests/test_peek_integration.py`** (~8 tests): policy build with stub LMClient, trajectory format from a synthetic completion, prepending logic, evolve_steps boundary, save/load.
- **`src/generate_rlm_answers.py`** (modified, ≤ 20 added lines): add `--peek-map-out PATH` flag; when set, runs serially (workers=1) and threads a single PEEK policy through PapersQA.
- **Data outputs:**
  - `data/CAE-v2.0-1-rubrics-v4.json` — sidecar rubrics with v4 `rlm_answer` (preserves v3).
  - `outputs/rlm-answers/cae-v2.0-1-v4.jsonl` — per-item answer audit trail.
  - `outputs/rlm-answers/cae-v2.0-1-v4.log` — run log.
  - `outputs/peek/cae-v2.0-1-map-frozen.json` — PEEK policy snapshot (saved after the 30th question; also at end of run).
- **Scoring:**
  - `outputs/scoring/cae-v2.0-1-scores-v4.json` + `cae-v2.0-1-report-v4.md` — produced by re-running existing `src/score_rlm_answers.py` on the v4 rubrics.
- **Diff reports:**
  - `outputs/scoring/cae-v2.0-1-diff-v1-v4.md` and `cae-v2.0-1-diff-v3-v4.md` — produced by existing `src/rubrics_diff_report.py`.

## Architecture

```
[generate_rlm_answers.py main]
        │
        ├──→ build_peek_policy(cfg)  ──→ peek.CachePolicy{
        │                                  client=OpenAIClient(deepseek-v4-flash,aiberm),
        │                                  token_budget=1024,
        │                                  evolve_steps=30,
        │                                }
        │
        ├──→ PapersQA(config, peek_policy=policy)   ── one long-lived instance
        │
        └──→ for item_idx in 0..93 (serial):
                ┌──────────────────────────────┐
                │  PapersQA.ask(question):     │
                │    map = policy.current_map  │
                │    sys = base + map          │
                │    rlm.custom_system_prompt = sys
                │    completion = rlm.completion(...)
                │    traj = completion_to_trajectory(completion)
                │    policy.update(trajectory=traj, question=question)
                │    if item_idx == 29: policy.save("outputs/peek/...-frozen.json")
                └──────────────────────────────┘
```

## Key interfaces (verified by reading the PEEK source)

- `from peek import CachePolicy`
- `from peek.llm.openai_client import OpenAIClient` — takes `model`, `api_key`, `base_url`
- `policy.current_map_text` — read-only str
- `policy.update(trajectory=str, question=str) -> UpdateResult | None` — None once frozen
- `policy.save(path)` / `CachePolicy.load(path, client=...)`
- `policy.evolving` — bool

## Trajectory format

PEEK's distiller expects a string trajectory. The RLM completion exposes a structured `metadata` dict with per-iteration LLM responses + REPL outputs + the final answer. `completion_to_trajectory` will:
1. Concatenate iteration headers `[Iter N] LLM response: ...` + `Code: ...` + `Output: ...`.
2. Append `[Final answer]: <completion.response>`.
3. Truncate to a sane max (e.g., 12000 chars; configurable) to keep distiller input cheap.

## CLI surface

```
python src/generate_rlm_answers.py \
    --input  data/CAE-v2.0-1-rubrics.json \
    --output data/CAE-v2.0-1-rubrics-v4.json \
    --jsonl  outputs/rlm-answers/cae-v2.0-1-v4.jsonl \
    --papers-dir /home/juli/RLM/CAE-MDs \
    --workers 1 \
    --peek-map-out outputs/peek/cae-v2.0-1-map-frozen.json \
    --peek-distiller-model deepseek/deepseek-v4-flash \
    --peek-token-budget 1024 \
    --peek-evolve-steps 30
```

When `--peek-map-out` is not set, PapersQA runs as today (no PEEK), so existing v1/v2/v3 flows are unaffected. When set, the code asserts `--workers == 1` to avoid the multi-process cache split.

## Failure modes

| Failure | Handling |
|---|---|
| `peek-ai` not installed | Hard error at import time with a `pip install` suggestion |
| `OpenAIClient` fails on aiberm proxy | Hard error; user diagnoses (likely auth) |
| Distiller call exceeds the call's budget | Tenacity-style retry inside PEEK is library's responsibility; if it raises, we let it bubble — the item fails (counted as `rlm_error`) and the next item proceeds (same behavior as today) |
| Map grows beyond token_budget | PEEK's evictor handles automatically |
| User passes `--workers 2+` with `--peek-map-out` | Hard error: "PEEK requires --workers 1" |
| Cache corruption / save IO error | `policy.save` raises; logged; non-fatal to the run (data is already in the jsonl) |

## Acceptance criteria

1. `papers_qa.runner.PapersQA(peek_policy=None)` is a no-op (existing tests still pass).
2. `papers_qa.runner.PapersQA(peek_policy=policy)` prepends the policy's `current_map_text` to the system prompt on every `ask()`.
3. After each `ask()` with policy, `policy.update(trajectory=..., question=...)` is called exactly once. Verified by a unit test with a stub policy.
4. `generate_rlm_answers.py` with `--peek-map-out` sets workers=1 internally (or errors if >1).
5. After question 30, the policy is saved to `--peek-map-out`. After the full run, the final policy state is also saved (overwriting).
6. v4 RLM run completes 94/94 with 0 errors.
7. v4 scoring produces a `scores-v4.json` + `report-v4.md`.
8. v3-vs-v4 diff is generated and committed.
9. v4 anchored mean does NOT regress more than 0.02 vs v3 (i.e., must be ≥ 0.695). This is the "PEEK doesn't actively hurt" floor.
10. ≥ 8 new tests in `tests/test_peek_integration.py`, all passing.

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Wall clock ~4 hours (serial) | LOW | Run overnight; resume already supported by `generate_rlm_answers.py` |
| PEEK distiller/cartographer calls cost more than $3 | MEDIUM | Bound by per-call budget; abort if total spend tracker exceeds $10 (manual monitoring) |
| PEEK map adds noise → v4 anchored regresses | MEDIUM | AC #9 floor at −0.02; if breached, accept failure and report (don't iterate) |
| `OpenAIClient` constructor mismatch (PEEK's API may differ from aiberm's) | LOW | Validated by a smoke test (instantiate client + 1 completion) before launching the full run |
| RLM's `custom_system_prompt` not mutable per-call | MEDIUM | If we can't override per-call, rebuild the RLM each ask (cheap; just stores config). The plan addresses this concretely. |
| Trajectory string too long for distiller | LOW | Hard truncate at 12k chars |
| The 30-question evolution window happens to cover only FSI topics (poor diversity) | MEDIUM | Item ordering covers many topics; eyeball the frozen map after question 30 for diversity before the remaining 64 run |

## What success enables

If AC #9 passes AND PEEK shows a meaningful gain on `decision_logic` (currently −14pp vs v1), we engineer Option C (split serial-then-parallel) to get production-grade throughput. If PEEK shows no signal, we abandon and revisit Phase 2 (substantive prompt iteration on decision_logic without PEEK).
