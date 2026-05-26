# rubrics-gen-val

RAG-grounded rubric **generation** + LLM-judge **evaluation** for Chinese-language CAE / engineering-simulation expert QA.

> 中文完整教程见 [`USAGE.md`](USAGE.md)。算法细节见 [`ALGORITHMS.md`](ALGORITHMS.md)。  
> 用本工具链对 `papers_qa` 做的 5 轮迭代实验总结见 [`EXPERIMENTS.md`](EXPERIMENTS.md)。

## What's here

Given a small expert QA dataset (94 Chinese CAE items in `data/CAE-v2.0-1.json`, mixed types: 简答题/主观题/决策题/对比分析题/数值提取题/流程描述题/数值关系题) plus 8 source documents that were used to author the answers, this repo:

1. **Generates** a high-quality rubric for each question — weighted binary checklist, signed criteria, anti-reward-hacking pitfalls, grounded in retrieved source-document chunks (RubricRAG-style). 94 rubrics output to `data/CAE-v2.0-1-rubrics.json` + `rubrics/items/idx_*.json`.
2. **Evaluates** any QA system's predictions against those rubrics via async per-criterion LLM judge, with `reference_answer` / "我不知道" anchor scores, producing a per-candidate breakdown + aggregate report (mean by question-type / difficulty / criterion-type).

The strategy is synthesized from ~22 papers in the rubric/LLM-as-judge literature (HealthBench, RubricRAG, Rubrics-as-Rewards, OpenRubrics, AdaRubric, Auto-Rubric, RIFT, RubricHub, etc.); rationale captured in [`docs/superpowers/specs/2026-05-22-cae-rubrics-design.md`](docs/superpowers/specs/2026-05-22-cae-rubrics-design.md).

## Pipeline

```
data/CAE-v2.0-1.json  +  CAE-MDs/*.md          ┐
                                                │
                ▼                               │
┌──────────────────────────────────────────┐   │
│  Generation pipeline (3 stages + 2 gates)│   │
│  1. RAG-grounded LLM rubric draft         │   │
│  2. atomicity + dedup + pitfall injection │   │
│  3. misalignment filter (ref + weak)      │   │
└──────────────────────────────────────────┘   │
                ▼                               │
     rubrics/items/idx_*.json                   │
     data/CAE-v2.0-1-rubrics.json               │
                                                │
predictions.jsonl  ─────────────────────────────┘
                ▼
┌──────────────────────────────────────────┐
│  Scoring pipeline                         │
│  - per-criterion async judge (semaphore)  │
│  - ref/weak anchor + normalization        │
│  - weighted (positive − penalty) / max    │
└──────────────────────────────────────────┘
                ▼
       eval_*.json (per_candidate + aggregate)
```

## Layout

```
src/rubrics/
├── schema.py              # pydantic models: Criterion / RubricItem
├── chunker.py             # MD chunking with page tracking
├── source_parser.py       # 来源 field → (doc, pages)
├── index.py               # BGE-zh embedding index
├── retriever.py           # page-first + semantic fallback
├── llm_client.py          # OpenAI-compatible HTTP client (sync + async)
├── templates/             # generator system prompt, judge prompt,
│   ├── system_prompt.txt  # 7 per-type rule files, 3 gold exemplars
│   ├── type_rules/
│   └── exemplars/
├── generator.py           # Stage 1
├── refiner.py             # Stage 2
├── misalignment_filter.py # Stage 3
├── pipeline.py            # end-to-end rubric generation orchestrator
│
├── judge.py               # per-criterion judge (sync + async)
├── anchor.py              # ref/weak anchor scoring + cache
├── scorer.py              # async per-candidate Scorer
├── aggregate.py           # eval aggregate report builder
└── scoring.py             # (positive − penalty) / pos_max  clipped

run/
├── 01_build_index.py             # chunk + embed source docs
├── 02_generate_rubrics.py        # run generation pipeline
├── 03_validate.py                # QC report on generated rubrics
└── 04_score_predictions.py       # eval QA model predictions

tests/rubrics/                    # 57 tests covering all modules
docs/superpowers/
├── specs/                        # design docs for generation + scoring
└── plans/                        # bite-sized TDD implementation plans
```

## Quickstart

```bash
# 0. Setup
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # then fill in LLM_API_KEY / LLM_BASE_URL / LLM_MODEL

# 1. (Optional) Re-generate rubrics from scratch  — needs the 8 CAE source MDs in CAE-MDs/
python run/01_build_index.py
python run/02_generate_rubrics.py
python run/03_validate.py

# 2. Score a QA system's predictions
cat > my_preds.jsonl <<EOF
{"item_idx": 0, "answer": "..."}
{"item_idx": 1, "answer": "..."}
EOF

python run/04_score_predictions.py \
    --predictions my_preds.jsonl \
    --out data/eval_modelA.json \
    --concurrency 16

jq '.aggregate' data/eval_modelA.json
```

## Design highlights

- **Weighted binary checklist** with 4 categories (Essential / Important / Optional / Pitfall) and 7 criterion types (factual_anchor / mechanism_explanation / numeric_precision / decision_logic / comparative_balance / process_completeness / anti_hacking). Per-type rubric templates differentiate 决策题 vs 数值提取题 vs 主观题, etc.
- **Source grounding via RAG**: the 来源 field on each item is parsed into `(doc_slug, page_range)`; BGE-zh embeddings index 8 mineru-converted markdowns; retrieval is page-first with semantic fallback. 84/94 items end up with page-specific or doc-only grounding.
- **Two anti-reward-hacking pitfalls injected by default** in every rubric (opening fluff, verbosity).
- **Misalignment filter** drops any positive criterion that doesn't fire on `reference_answer` OR that fires on the weak `"我不知道"` baseline.
- **Scoring formula**: `score = (Σ w_i · met_i for positive − Σ w_i · met_i for pitfall) / Σ w_i for positive`, clipped to `[0, 1]`.
- **Anchor normalization at eval time**: `(score − weak) / (ref − weak)` makes scores comparable across rubrics with different "natural ceilings".

## Generation stats (94 items, gpt-5.4-mini)

| Metric | Value |
|---|---|
| Items generated | 94/94 |
| Mean criteria/item | 8.9 (min 5, max 12) |
| Items with ≥ 2 Pitfall | 94/94 |
| Page-grounded retrieval | 68 page_specific + 16 doc_only + 10 semantic-fallback |
| Mean misalignment drops/item | 0.5 |
| Total cost | ~$0.5 |
| Wall time (sequential) | ~2.5 h |

## Tech stack

Python 3.11, pydantic v2, httpx, asyncio, tenacity, sentence-transformers (BGE-zh-v1.5), pytest + pytest-asyncio.

## License

Code: MIT. Source documents (`CAE-MDs/`, `CAE-PDFs/`) and rubric papers (`rubrics-papers-md/`) are intentionally **not committed**; they're retained locally for the RAG indexer.
