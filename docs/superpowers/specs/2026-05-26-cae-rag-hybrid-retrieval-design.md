# Design: CAE-RAG — hybrid-retrieval reading comprehension + rubric eval

**Date**: 2026-05-26
**Status**: Approved (pending spec review)

## 1. Goal

Build a hybrid-retrieval RAG over the 8 `CAE-MDs` documents, answer the 94-question
CAE expert QA benchmark with `deepseek/deepseek-v4-flash`, score the answers with the
`cae-rubrics-eval` package, and compare `mean_anchored` against the RLM agent baseline.

**Controlled variable.** RAG and RLM use the *same generation model*
(`deepseek/deepseek-v4-flash`) over the *same documents* (`CAE-MDs/`). The only
difference is how context is gathered: RAG retrieves top-5 hybrid chunks; the RLM
agent (`papers_qa`) explores the documents agentically. This makes the
RAG-vs-RLM delta interpretable as a *retrieval-method* effect.

**Clean comparison.** Both RAG answers and the RLM v3 answers
(`data/CAE-v2.0-1-rubrics-v3.json`, field `rlm_answer`) are scored through the
**same** `cae-rubrics-eval` pipeline (judge `openai/gpt-5.4-mini`, bundled anchors).
This removes the judge-model confound: the EXPERIMENTS.md figure of 0.711 used judge
`gpt-5.5`, so we re-score v3 under `gpt-5.4-mini` to get an apples-to-apples number.
The published v1/v3/v4/v5 numbers are reported only as secondary context.

## 2. Algorithm parameters (from task spec)

| Parameter | Value |
|---|---|
| Vector store | Milvus Lite (local `cae_rag.db`, no Docker) |
| Embedding model | `openai/text-embedding-3-small` via `https://aiberm.com/v1` (dim 1536) |
| Generation model | `deepseek/deepseek-v4-flash` via `https://aiberm.com/v1` |
| Judge model | `openai/gpt-5.4-mini` (cae-rubrics-eval default; do not override) |
| chunk_size | 512 tokens (tiktoken `cl100k_base`) |
| chunk_overlap | 64 tokens |
| Retrieval | dense (Milvus) + BM25 (rank-bm25 + jieba), RRF fusion, top-5 |
| RRF k | 60 |
| Candidate pool | top-20 per retriever before fusion |
| Generation temperature | 0 |
| Seed | 42 |

## 3. Pipeline

### Stage 1 — Ingest & chunk (`cae_rag/ingest.py`)
- Load 8 `.md` files from `/home/juli/RLM/CAE-MDs/`.
- Clean: drop `![Image](...)` lines and standalone image/`**` artifact lines;
  collapse repeated whitespace. Keep headings and body text.
- Chunk each document into 512-token windows (tiktoken `cl100k_base`) with 64-token
  overlap. Record `{doc, chunk_id, text, token_start, token_end}`.
- Estimated ~800–1400 chunks total. Persist `outputs/chunks.jsonl` + a manifest hash.

### Stage 2 — Index (`cae_rag/index.py`)
- **Dense**: embed each chunk via `text-embedding-3-small` (batched, OpenAI-compatible
  client → aiberm). Create Milvus Lite collection `cae_chunks`
  (`id`, `vector` dim 1536, `text`, `doc`); insert; build AUTOINDEX; load.
- **Sparse**: tokenize each chunk with jieba, build `BM25Okapi` (rank-bm25);
  pickle to `outputs/bm25.pkl` alongside the chunk-id ordering.

### Stage 3 — Retrieve (`cae_rag/retrieve.py`)
- Per query: embed query → Milvus dense search top-20; jieba-tokenize query →
  BM25 top-20.
- RRF fuse: `score(d) = Σ_retrievers 1/(k + rank_retriever(d))`, k=60.
  Sort desc, take top-5 chunks. Return chunks with provenance for the trace.

### Stage 4 — Generate (`cae_rag/generate.py`)
- Clean RAG prompt (NOT mirroring v3 style rules):
  - system: CAE/仿真领域专家，**仅依据给定资料作答，不得编造**；资料不足时说明。
  - user: 5 labeled context chunks (`[doc] text`) + the question.
- Call `deepseek/deepseek-v4-flash`, temp 0, concurrent over 94 questions.
- Read `question` + `item_idx` from `/home/juli/RLM/data/CAE-v2.0-1-rubrics.json`
  (MUST NOT read `reference_answer`/`criteria`/`source_grounding`).
- Output `outputs/predictions.jsonl`: `{item_idx, answer}` (+ optional retrieval trace
  in extra fields, ignored by the scorer).

### Stage 5 — Score & compare (`scripts/compare_results.py` + `cae_rag/compare.py`)
1. Score RAG: `cae-rubrics-eval/score.py --predictions outputs/predictions.jsonl
   --out outputs/eval_rag.json` (judge `gpt-5.4-mini`, bundled anchors).
2. Build RLM v3 predictions: extract `{item_idx, answer=rlm_answer}` from
   `data/CAE-v2.0-1-rubrics-v3.json` → `outputs/rlm_v3_predictions.jsonl`.
3. Score RLM v3 through the **same** pipeline → `outputs/eval_rlm_v3.json`.
4. `compare.py` reads both `eval_*.json` and writes `outputs/comparison.md`:
   - headline `mean_anchored`: RAG vs RLM v3 (same judge) + the delta.
   - `by_question_type`, `by_difficulty`, `by_criterion_type` side-by-side.
   - secondary context: published RLM v1/v3/v4/v5 numbers (judge `gpt-5.5`),
     clearly labeled as a different judge.

## 4. Project layout

New package `cae-rag/`, sibling to `cae-rubrics-eval/`, with its own venv.

```
cae-rag/
├── pyproject.toml
├── .env.example          # LLM_API_KEY, LLM_BASE_URL, EMBEDDING_MODEL, GEN_MODEL
├── .env                  # gitignored
├── cae_rag/
│   ├── __init__.py       # __all__ public API
│   ├── config.py         # frozen dataclass, env load, set_seed(42)
│   ├── ingest.py         # load + clean + 512-tok chunk
│   ├── index.py          # Milvus Lite dense + BM25 build
│   ├── retrieve.py       # hybrid dense+BM25 + RRF top-5
│   ├── generate.py       # deepseek-v4-flash answer generation
│   └── compare.py        # RAG-vs-RLM comparison report builder
├── scripts/
│   ├── build_index.py    # CLI: ingest + index
│   ├── run_rag.py        # CLI: retrieve + generate → predictions.jsonl
│   └── compare_results.py# CLI: score both + comparison.md
├── tests/
│   ├── test_ingest.py    # chunk boundary/overlap, image stripping
│   ├── test_retrieve.py  # RRF fusion correctness
│   └── test_predictions.py # predictions schema
└── outputs/
    ├── chunks.jsonl, cae_chunks (milvus .db), bm25.pkl
    ├── predictions.jsonl, rlm_v3_predictions.jsonl
    ├── eval_rag.json, eval_rlm_v3.json
    └── comparison.md
```

Each file targets 200–400 lines (coding-style rule). Config-driven (frozen
dataclass); module-level loggers; type hints; `__all__` in `__init__.py`.

## 5. Reproducibility (global rule)

- `set_seed(42)` at entry of every script.
- Log resolved config + environment (python/pymilvus/openai versions) at start.
- `pip freeze > outputs/requirements.txt`.
- Dataset hash (SHA256, 12 hex) of the rubrics file + chunk manifest hash recorded
  in `outputs/run_meta.json`.
- Determinism: tiktoken chunking, embeddings, BM25, RRF, and temp-0 generation are
  all deterministic given fixed inputs.

## 6. Testing (TDD where it pays off)

Unit-test the deterministic cores first:
- **Chunking**: a 1100-token synthetic doc → expected window count, 512-token size,
  64-token overlap, no token loss at boundaries.
- **RRF fusion**: two ranked lists with a known overlap → exact fused top-5 order.
- **Cleaning**: input with `![Image](...)` lines → those lines removed, body intact.
- **Predictions schema**: emitted rows are `{item_idx:int, answer:str}` and parse as
  valid JSONL.

Embedding / Milvus / LLM calls are integration concerns — mocked in unit tests; a
small end-to-end smoke run (3 questions) validates wiring before the full 94-question
run.

## 7. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Milvus Lite feature limits (sparse/full-text) | We do BM25 client-side, so Lite only needs dense search — well within its support. |
| OCR-garbled Chinese in `CAE-MDs` | Affects RAG and RLM equally (same docs); BM25 + dense both degrade together, so the comparison stays fair. |
| aiberm proxy timeouts (hit RLM v4/v5) | Concurrency cap + tenacity retries on generation calls; log failures per item. |
| item_idx ↔ question parity between main `data/` rubrics and the eval's bundled rubrics | Assert parity (same item_idx → same question text) before scoring. |
| jieba on the English Benson doc | jieba passes English tokens through on whitespace; acceptable for BM25 recall. |
| Chunk count / embedding cost | ~1k chunks × text-embedding-3-small ≈ <$0.1; trivial. |

## 8. Success criteria

- `outputs/predictions.jsonl` covers all 94 items; `eval_rag.json` reports
  `n_scored_ok == 94`, `n_errors == 0`.
- `comparison.md` shows RAG vs RLM-v3 `mean_anchored` under the identical judge, with
  per-type/per-difficulty breakdowns and the computed delta.
- Full run is reproducible from `build_index.py → run_rag.py → compare_results.py`
  with seed 42 and recorded config/env.

## 9. Out of scope

- Re-scoring RLM v1/v4/v5 (only v3, the production champion, is re-scored).
- Retrieval/prompt tuning iterations — this delivers one clean baseline RAG, not an
  ablation series.
- Native Milvus full-text BM25 / Docker standalone (explicitly decided against).
