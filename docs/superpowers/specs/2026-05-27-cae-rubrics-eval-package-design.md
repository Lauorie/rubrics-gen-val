# Design: `cae-rubrics-eval/` — standalone scoring package

**Date:** 2026-05-27
**Status:** Design — awaiting implementation plan
**Related specs:** [2026-05-22-cae-rubrics-design.md](2026-05-22-cae-rubrics-design.md), [2026-05-22-cae-rubrics-scorer-design.md](2026-05-22-cae-rubrics-scorer-design.md)

## 1. Problem

We want to give a collaborator the ability to score answers (produced by their own algorithm, e.g. ReAct) against our 94-item CAE rubric set, and produce scores that are directly comparable to our prior RLM evaluations.

The recipient should not need to clone the full RLM repo, install RAG dependencies (sentence-transformers / faiss), or understand the rubric generation pipeline. They should only need: this package, an OpenAI-compatible LLM key, and their own predictions file.

## 2. Goals & Non-goals

**Goals**
- Ship a self-contained subdirectory `cae-rubrics-eval/` under the RLM repo
- Score parity: a recipient's `score_anchored.normalized` numbers are directly comparable to our existing RLM eval reports
- Minimal install: pydantic / httpx / tenacity / python-dotenv only
- Clear Chinese-language README; predictions format documented with one ⚠️ banner about not leaking `reference_answer` / `criteria` into their generation context

**Non-goals**
- Do not ship the rubric generation pipeline (RAG indexing, generator, refiner, misalignment filter)
- Do not ship a ReAct scaffold — the recipient is the expert on their own algorithm
- Do not ship tests — keep surface area minimal; smoke validation done at packaging time, not packaged
- Do not support multiple judge models out of the box; locking to `openai/gpt-5.4-mini` is what makes scores comparable. README documents the (unsupported) override path for completeness.

## 3. Constraints (decided)

- **Eval mode: locked parameters** — ship precomputed `data/CAE-anchor-scores.json`; README requires `LLM_MODEL=openai/gpt-5.4-mini` for comparable scores.
- **Question delivery: read `question` field from `CAE-v2.0-1-rubrics.json` directly** — no separate `questions.jsonl`; README warns recipient to ignore `reference_answer` / `criteria` / `rubric_metadata` fields when building their prompt.
- **Distribution: subdirectory inside `RLM/`** — user manually copies/zips the folder when sending.
- **No tests shipped** — packaging-time smoke run is enough.

## 4. Approach

**Thin scoring kit.** Copy (do not import from main repo) the 7 eval-side modules from `src/rubrics/` into a new top-level Python package `cae_eval/`, plus the judge prompt template. Provide one thin CLI `score.py`. Ship the rubric JSON (with `rlm_answer`/`rlm_error` fields stripped) and the anchor cache. Recipient runs `pip install -e . && python score.py --predictions <their.jsonl> --out eval.json`.

Rejected alternatives:
- *Single-file CLI* — loses module boundaries; future fixes in main repo won't cleanly back-port; harder for recipient to extend.
- *Eval kit + ReAct example* — scope creep; recipient knows their algorithm better than we do.

## 5. Architecture

### 5.1 Directory layout

```
cae-rubrics-eval/
├── README.md                          # Chinese-language usage doc (primary entry point)
├── pyproject.toml                     # name=cae-rubrics-eval; deps: pydantic/httpx/tenacity/python-dotenv
├── .env.example                       # LLM_API_KEY / LLM_BASE_URL / LLM_MODEL
├── .gitignore                         # .env, __pycache__, *.egg-info, outputs/
│
├── data/
│   ├── CAE-v2.0-1-rubrics.json        # 94 rubrics (rlm_answer / rlm_error stripped)
│   └── CAE-anchor-scores.json         # 94 anchor (ref, weak) pairs from gpt-5.4-mini
│
├── cae_eval/                          # Python package
│   ├── __init__.py
│   ├── schema.py                      # ← copy of src/rubrics/schema.py
│   ├── scoring.py                     # ← copy of src/rubrics/scoring.py
│   ├── judge.py                       # ← copy; imports updated
│   ├── anchor.py                      # ← copy; imports updated
│   ├── scorer.py                      # ← copy; imports updated
│   ├── aggregate.py                   # ← copy of src/rubrics/aggregate.py
│   ├── llm_client.py                  # ← copy of src/rubrics/llm_client.py
│   └── templates/
│       └── misalignment_judge_prompt.txt
│
├── score.py                           # Thin CLI entry point
└── examples/
    ├── predictions_example.jsonl      # 3 sample predictions (good / "我不知道" / bad)
    └── eval_example.json              # Reference output, ~for format comparison
```

Package distribution name (PyPI-style): `cae-rubrics-eval`. Python import name (snake_case): `cae_eval`. Keep both consistent.

### 5.2 Module copy plan

For every file copied from `src/rubrics/` into `cae_eval/`:
- Replace `from rubrics.` → `from cae_eval.`
- Replace `rubrics.judge` / `rubrics.llm_client` etc. → `cae_eval.judge` / `cae_eval.llm_client`
- Verify no remaining import resolves to the parent `src/rubrics/` package.

Modules and their roles (unchanged from main repo):
- `schema.py` — pydantic Criterion / RubricItem models
- `scoring.py` — `(Σ positive − Σ pitfall) / Σ positive_max`, clipped [0,1]
- `llm_client.py` — OpenAI-compatible sync + async HTTP client with tenacity retries
- `judge.py` — per-criterion judge prompt + JSON parse
- `anchor.py` — reference / weak anchor scoring; `AnchorCache` JSON-backed
- `scorer.py` — `Scorer` async batch driver with semaphore concurrency
- `aggregate.py` — `build_aggregate` report builder (per-question-type / per-difficulty / per-criterion-type breakdown)

### 5.3 CLI: `score.py`

```bash
python score.py \
    --predictions <path>.jsonl \
    --out <path>.json \
    [--rubrics data/CAE-v2.0-1-rubrics.json] \
    [--anchors data/CAE-anchor-scores.json] \
    [--concurrency 16] \
    [--judge-model openai/gpt-5.4-mini]
```

Flag set is a strict subset of the in-tree `run/04_score_predictions.py`. Dropped: `--resume`, `--no-anchors`, `--refresh-anchors`. Kept anchor-cache code path because it gracefully self-heals if the recipient deletes `data/CAE-anchor-scores.json`.

Single behavioural change vs in-tree script:

```python
# in-tree: scans rubrics/items/idx_*.json
def load_rubrics(items_dir: Path) -> dict[int, dict]:
    return {json.loads(p.read_text())["item_idx"]: json.loads(p.read_text())
            for p in sorted(items_dir.glob("idx_*.json"))}

# package: reads single JSON array file
def load_rubrics(path: Path) -> dict[int, dict]:
    return {r["item_idx"]: r for r in json.loads(path.read_text(encoding="utf-8"))}
```

Startup behaviour: if `anchors[*].judge_model` ≠ `LLM_MODEL`, log a WARNING but do not block — recipient may have a valid reason (replication study). Document this in README.

### 5.4 Predictions format (recipient contract)

JSONL, one object per line:

```jsonl
{"item_idx": 0, "answer": "..."}
{"item_idx": 1, "answer": "..."}
```

- `item_idx` (int, required) — must match a value in the rubric file's `item_idx` field (0–93). Not the same as `question_id`.
- `answer` (str, required) — recipient's generated answer.
- Extra fields ignored.
- Missing items → those rubrics simply aren't scored; aggregate `n_predictions` reflects what was submitted.

### 5.5 Output format

```json
{
  "per_candidate": [ ... 94 records, each with item_idx, score, score_anchored.{ref,weak,normalized}, breakdown ... ],
  "aggregate": {
    "n_predictions": 94, "n_scored_ok": 94, "n_errors": 0,
    "mean_score": 0.71, "mean_anchored": 0.62,
    "by_question_type": {"简答题": {"n": 28, "mean": ..., "mean_anchored": ...}, ...},
    "by_difficulty": {...},
    "by_criterion_type": {...},
    "judge_model": "openai/gpt-5.4-mini",
    "rubric_version": "1.0",
    "scored_at": "<UTC ISO8601>",
    "elapsed_seconds": 412.3
  }
}
```

Primary headline metric for cross-system comparison: `aggregate.mean_anchored` (anchor-normalized to make scores comparable across rubrics with different natural ceilings). README explains this.

### 5.6 Data preparation steps

1. Read `RLM/data/CAE-v2.0-1-rubrics.json` (94 items). For each item, delete keys `rlm_answer` and `rlm_error` if present. Write to `cae-rubrics-eval/data/CAE-v2.0-1-rubrics.json`. **Reason:** those fields hold the prior RLM run's outputs and would confuse a recipient who reads the file as "the dataset".
2. Copy `RLM/data/CAE-anchor-scores.json` verbatim to `cae-rubrics-eval/data/CAE-anchor-scores.json` (94 entries, all `judge_model=openai/gpt-5.4-mini`).
3. Generate `examples/predictions_example.jsonl` with three deliberate samples:
   - `item_idx=0`, paraphrased reference answer (expected score ≈ 1.0)
   - `item_idx=1`, answer = `"我不知道。"` (expected score ≈ 0.0 — weak baseline)
   - `item_idx=2`, off-topic garbage (expected score ≈ 0.0)
4. Run `score.py` on the example file to produce `examples/eval_example.json`. Ship the output so recipient has a concrete target to compare their own pipeline's output shape against.

## 6. README outline

1. **What this is** — one sentence, links to ALGORITHMS.md in main repo for theory.
2. **Quickstart** (5 steps)
   - `pip install -e .`
   - `cp .env.example .env` → fill `LLM_API_KEY` (must be able to call `openai/gpt-5.4-mini` for comparability)
   - Generate `predictions.jsonl` (format below)
   - `python score.py --predictions predictions.jsonl --out eval.json`
   - Read `eval.json` `aggregate` field
3. **Dataset** — `data/CAE-v2.0-1-rubrics.json` structure; ⚠️ banner: "**do not feed `reference_answer` / `criteria` / `rubric_metadata` into your generator's context — those are scoring-side ground truth**"
4. **Predictions format** — must be JSONL, must have `item_idx` (not `question_id`!) and `answer`
5. **Output interpretation** — `score` (raw, 0–1) vs `score_anchored.normalized` (anchor min-max); the latter is the headline cross-system metric
6. **Scoring principle** — one paragraph: weighted binary checklist, `(positive − pitfall) / positive_max`, clipped; anchor uses `reference_answer` as upper bound and `"我不知道。"` as lower bound
7. **Cost estimate** — 94 items × ~8.9 criteria ≈ 836 judge calls. Generation pipeline (per `EXPERIMENTS.md`) cost ~$0.5; eval judge calls are shorter than generation, so order-of-magnitude estimate $0.1–0.3. Wall time ~5–10 min at concurrency 16. README states "~$0.5 worst case" rather than a precise number.
8. **FAQ** — missing `item_idx`, rate-limit handling (tenacity 3-retry built in), switching judge model (not recommended; if needed, delete anchor cache and re-run; bash one-liner included)
9. **Package layout** — `tree`-style dump

## 7. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| `rlm_answer` field leaks recipient confusion | Strip during data prep step 1 |
| Import path drift after copy | After copy, do `grep -r "from rubrics" cae_eval/` and `python -c "import cae_eval"` — both must come back clean |
| Recipient uses different judge model → anchor mismatch | Warn at startup (`judge_model` mismatch), README has explicit calibration warning |
| Recipient mistakes `question_id` for `item_idx` | README §4 calls this out; CLI would just error out cleanly with "no rubric for item_idx=X" |
| LLM service outage during recipient's eval | tenacity retries 3× with exponential backoff; `breakdown[*].error` field captures any final failures |
| Package name vs Python module name mismatch | Lock distribution name `cae-rubrics-eval` and import name `cae_eval`; document in pyproject.toml |
| Stale anchor cache after a rubric edit | Out of scope — recipient is consuming a frozen v1.0 rubric. If we ever ship v2.0 rubrics, ship a fresh anchor cache alongside. |

## 8. Implementation phases

For the writing-plans skill to expand:

1. **Skeleton** — create directory tree, empty files, `pyproject.toml`, `.gitignore`, `.env.example`
2. **Module copy** — copy 7 modules + judge prompt template, rewrite imports, verify clean `import cae_eval`
3. **Data prep** — strip `rlm_answer`/`rlm_error` from rubric file, copy anchor cache
4. **CLI** — write `score.py` (single-file rubric loader, 5 flags, anchor-mismatch warn)
5. **Examples** — generate `predictions_example.jsonl` and `eval_example.json` by running the CLI live
6. **README** — write per §6 outline
7. **Smoke verification** — fresh venv, `pip install -e .`, run example, sanity-check `aggregate.mean_score ∈ [0,1]`

## 9. Verification

End-to-end: from a clean shell,

```bash
cd cae-rubrics-eval
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env  # fill key
python score.py --predictions examples/predictions_example.jsonl --out /tmp/sanity.json
jq '.aggregate.mean_score, .aggregate.n_predictions, .aggregate.n_errors' /tmp/sanity.json
```

Expected: `mean_score` is a float in [0, 1]; `n_predictions == 3`; `n_errors == 0`.
