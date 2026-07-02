# SciArena Rubric Generator (standalone, RAG-free)

Generate weighted binary **rubrics** (scoring checklists) for literature-QA
questions in the SciArena format. For each question it runs a 3-stage pipeline —
**generate → refine → misalignment-filter** — grounded in a ground-truth answer
and its cited sources. No retrieval index / embedding model is needed: each
citation already carries its text inline, which serves as the domain context.

Bilingual: English (`--lang en`) or Chinese (`--lang zh`, which also translates
the question + ground-truth answer to Chinese while keeping citations English).

## What you need

1. **Python ≥ 3.11**
2. **Python packages**: `pip install -r requirements.txt`
   (pydantic, httpx, tenacity, python-dotenv, numpy — all public PyPI)
3. **An OpenAI-compatible LLM endpoint** — this is the only external service.
   The code ships no model; it POSTs to `{LLM_BASE_URL}/chat/completions`.
   Copy `.env.example` to `.env` and set `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`.

That's it — no HuggingFace models, no vector index, no corpus.

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # then edit LLM_API_KEY / LLM_BASE_URL / LLM_MODEL
```

## Input format

A JSON **array** of SciArena items. Per item (only these keys are read):

```json
{
  "id": "any-unique-id",
  "question": "What are the limitations of ...?",
  "question type": "Challenges & Limitations",
  "subject": "Computer Science",
  "vote": "A",
  "responseA": "ground-truth-quality answer text ...",
  "responseB": "the other answer ...",
  "citations_a": [
    {"id": "c1", "title": "Paper title", "authors": "…", "content": "~2k chars of source text used as context"}
  ],
  "citations_b": [ ... ]
}
```

- `vote` picks the ground truth: `A`/`B` (case-insensitive); `Tie` is broken by a
  seeded RNG; `bad` (both answers poor) → item skipped.
- The winning side's `responseX` + `citations_x` become the reference answer and
  context; the losing side is dropped.
- `question type` (note the space) is mapped to a template; unknown → `Others`.

> Bare `NaN` tokens in the JSON are tolerated (streamed parse). Large files are
> read incrementally, so multi-GB inputs are fine.

## Run

```bash
# English rubrics
python generate_rubrics.py \
  --data        input.json \
  --cleaned-out out/cleaned.jsonl \
  --rubrics-out out/rubrics.json \
  --items-dir   out/items \
  --lang en \
  --gen-model   openai/gpt-5.5 \
  --judge-model openai/gpt-5.4 \
  --item-concurrency 6 --judge-concurrency 8 --seed 42

# Chinese rubrics: same, with --lang zh
```

**Resume / restart-safe.** Each item is written to `--items-dir/item_NNNNNN.json`
as it completes. Re-running with `--resume` skips items already done (and, if
`--cleaned-out` exists, reuses the cleaned dataset instead of re-selecting/-
translating). Occasional items may fail on a malformed-JSON LLM response
(~2–3%); just re-run with `--resume` to fill the gaps.

### Key flags

| flag | meaning | default |
|---|---|---|
| `--lang {en,zh}` | rubric language (zh also translates Q + GT answer) | `en` |
| `--gen-model` | Stage-1/2 generator model | env `LLM_MODEL` |
| `--judge-model` | Stage-3 misalignment judge (use a stronger model) | `openai/gpt-5.4` |
| `--item-concurrency` | items generated in parallel | 4 |
| `--judge-concurrency` | concurrent judge calls per item | 8 |
| `--limit N` / `--dry-run` | process first N / stop after 1 (smoke test) | — |
| `--resume` | skip finished items; reuse existing cleaned file | off |

## Output

`--rubrics-out` is a JSON array; each item has `question`, `reference_answer`,
`question_type`, `subject`, `vote`, `gt_source`, `citation_grounding`,
`rubric_metadata`, and `criteria`. Each criterion:

```json
{"id": "c1", "text": "...", "category": "Essential|Important|Optional|Pitfall",
 "weight": 1-8, "sign": "positive|negative",
 "criterion_type": "factual_anchor|mechanism_explanation|numeric_precision|decision_logic|comparative_balance|process_completeness|anti_hacking"}
```

Two mandatory anti-hacking "style" pitfalls are injected into every rubric and
their weights are normalized to a canonical **3 / 2** regardless of what the
generator emits (`rubrics_sciarena/refiner.py`).

## Layout

```
generate_rubrics.py            # CLI entry point
rubrics/llm_client.py          # OpenAI-compatible client (+ empty __init__.py)
rubrics_sciarena/              # the pipeline (generate/refine/filter) + templates/
```
