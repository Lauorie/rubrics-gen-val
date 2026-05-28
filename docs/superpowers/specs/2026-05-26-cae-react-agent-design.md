# Design: ReAct Agent for CAE QA — third comparison point

**Date**: 2026-05-26
**Status**: Approved (pending spec review)

## 1. Goal

Add a **text-based ReAct agent** to the existing `cae-rag` package and benchmark it on the
same 94-question CAE set, same knowledge base (`CAE-MDs/`), same generation model
(`deepseek/deepseek-v4-flash`), and same scorer (`cae-rubrics-eval`, judge
`openai/gpt-5.4-mini`, identical anchors). This produces a third point on the
reading-comprehension spectrum:

- **RAG** — single-shot: retrieve top-5 → generate. (anchored 0.427)
- **ReAct** — iterative: reason → act (search/read) → observe, looped. (this work)
- **RLM v3** — `papers_qa` agent exploring the docs. (re-scored anchored 0.675)

The controlled variable vs RAG is **iterative agentic retrieval**: ReAct uses the *same*
`HybridRetriever` backend as RAG, so the difference is the reasoning loop + a `read` tool,
not the retrieval algorithm.

## 2. ReAct loop (Yao et al. text format)

A scratchpad transcript grows over up to `max_steps` (default 6) rounds. Each round the
model is called with `system + question + scratchpad` and must emit exactly one of:

```
Thought: <reasoning>
Action: search[<query>]
```
```
Thought: <reasoning>
Action: read[<chunk_id>]
```
```
Final Answer: <中文答案>
```

Flow per round:
1. Call LLM (temp 0, deterministic — consistent with RAG).
2. Parse: if `Final Answer:` present → done. Else if a parseable `Action:` → run the tool,
   append `Observation: <result>` to the scratchpad, continue.
3. **Robustness**: a response with neither a parseable action nor a Final Answer → append a
   one-time reformat nudge and retry that round once; if still unparseable → treat the raw
   response text as the final answer (never crash, never empty).
4. On reaching `max_steps` tool rounds without a Final Answer → one final "answer now using
   what you have" call; its output is the answer.

## 3. Tools (reuse existing plumbing)

- **`search(query)`** → the same `HybridRetriever` (dense+BM25+RRF), returns top-`search_k`
  (default 5) hits formatted as pointer lines: `[<chunk_id> | <doc> | <snippet>]`, where
  snippet is the chunk text truncated to `snippet_chars` (default 240). Pointers, not full
  text — keeps the scratchpad bounded and pushes the agent to `read` what it wants.
- **`read(chunk_id)`** → full text of that chunk plus `read_window` (default 1) neighbor
  chunks on each side. Chunk ids are `{doc}::{idx}`, so neighbors are `{doc}::{idx±1}`
  within the same doc. Invalid id → `Observation: 未找到该 chunk_id`.

The 8 KB document names are listed in the system prompt so the agent knows what exists
(covers "list documents" without a third tool). The answer instruction is **neutral and
grounded-only** — same spirit as the RAG prompt, NO by-question-type style rules.

## 4. Components (extends `cae-rag/`)

```
cae_rag/react.py        # ReactConfig (frozen), parse_action, parse_final,
                        #   format_search_obs, read_chunk, ReactAgent
scripts/run_react.py    # wire index+retriever+client, run 94 Qs concurrently
                        #   -> outputs/predictions_react.jsonl (+ steps/trace)
cae_rag/compare.py      # ADD build_comparison_md_3way(rag, react, rlm)
                        #   (keep existing 2-way build_comparison_md intact)
scripts/compare_results.py  # ADD --react-predictions; when given, score ReAct and
                        #   REUSE existing eval_rag.json/eval_rlm_v3.json if present
                        #   (skip re-scoring to save cost), emit 3-way comparison.md
```

`ReactConfig` (frozen dataclass) fields + defaults: `max_steps=6`, `search_k=5`,
`snippet_chars=240`, `read_window=1`, `temperature=0.0`. The LLM client, retriever, and a
`chunk_lookup`/chunk list are injected into `ReactAgent` (no global state).

`ReactAgent.answer(question) -> {"answer": str, "steps": int, "trace": list[dict]}`. The
runner writes `{item_idx, answer, steps}` to predictions (extra fields ignored by scorer).

### compare_results.py scoring reuse
For each of rag / rlm_v3 / react: if its `eval_*.json` already exists, reuse it; otherwise
run `score.py`. Add `--force` to re-score everything. This keeps re-runs cheap (RAG and
RLM v3 were already scored) and idempotent. The 3-way report is built from the three
aggregates.

## 5. Reproducibility

`set_seed(42)`, temp 0 generation, deterministic retriever. `run_react.py` records step
counts per item; the trace (actions taken) is saved for audit. Reuses the existing built
index (`outputs/cae_rag.db`, `bm25.pkl`, `chunks.jsonl`) — no rebuild.

## 6. Testing (TDD where it pays)

Pure/unit-testable cores first:
- `parse_action`: `search[q]`, `read[d::3]`, markdown-wrapped (` ```Action: search[q]``` `),
  extra whitespace, and a garbled line → returns `(tool, arg)` or `None`.
- `parse_final`: extracts text after `Final Answer:`; returns `None` when absent.
- `read_chunk`: given a chunk list and `d::3` with window 1 → returns d::2,d::3,d::4 text;
  invalid id → not-found sentinel; clamps at doc boundaries.
- `format_search_obs`: truncates to `snippet_chars`, one pointer line per hit.
- `build_comparison_md_3way`: three aggregates → headline table with all three +
  pairwise deltas vs RLM v3; by-type and by-difficulty tables.
- `ReactAgent.answer` (one integration unit): fake LLM scripted `search → read → Final
  Answer`, fake retriever → asserts both tools fire, scratchpad accumulates observations,
  final answer extracted, `steps` counted.

LLM / Milvus stay mocked in unit tests. A 3-question real smoke run validates the live loop
(format adherence, tool execution) before the full 94-question run.

## 7. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Model doesn't emit exact `Action:` format | Tolerant regex (case/space/markdown tolerant) + one reformat nudge + fallback-to-final-answer. Never empty/crash. |
| Infinite/again-and-again identical searches | Hard `max_steps` cap; forced-answer call on cap. |
| Scratchpad token blow-up | search returns truncated snippets; `read` bounded by `read_window`; `max_steps` bounds rounds. |
| Cost/latency (≤~7 LLM calls/question) | workers=8 concurrency; minutes for 94 Qs. Acceptable, authorized. |
| Unfair vs RAG | Identical retriever + same model + same eval; only the loop + read tool differ. |
| Re-scoring RAG/RLM wastes $ | compare_results reuses existing eval_*.json unless --force. |

## 8. Success criteria

- `outputs/predictions_react.jsonl` covers 94 items, 0 empty answers (fallback guarantees
  non-empty), with a `steps` count per item.
- `outputs/eval_react.json`: `n_scored_ok == 94`, `n_errors == 0`.
- 3-way `comparison.md` + an updated Section 8 (3-way) in `data/CAE-v2.0-1 RLM Scoring
  Report.md` showing RAG vs ReAct vs RLM v3 (headline anchored + by-type + by-difficulty).
- Full unit suite green; reproducible via `run_react.py → compare_results.py --react-predictions`.

## 9. Out of scope

- Native tool/function-calling (text-based ReAct chosen for portability).
- Step-budget / k sweeps or prompt tuning iterations — one clean ReAct baseline.
- Re-scoring RLM v1/v4/v5.
