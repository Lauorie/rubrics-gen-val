# rubrics_sciarena

Generate rubrics (weighted binary checklists) for the **SciArena** literature-QA
dataset. Adapted from `src/rubrics` (CAE), with three key differences:

1. **No RAG.** Each SciArena citation already carries a ~2 k-char `content`
   field, so the ground-truth answer's citations serve as the domain context
   directly — no retrieval index.
2. **Ground truth by human vote.** For each item, the winning response
   (`vote` = `A`/`B`; `Tie` broken by a per-id seeded RNG) and its citations are
   kept; the losing side is dropped. Items with `vote = bad` (both poor) are
   skipped.
3. **Bilingual.** English (`--lang en`) or Chinese (`--lang zh`) rubrics. In
   `zh` mode the question + GT answer are translated to Chinese while citations
   stay English (a Chinese user querying an English knowledge base).

## Pipeline (per item)

```
select_gt (vote)  ->  [translate to zh]  ->  Stage 1 generate (gpt-5.4-mini)
                                          ->  Stage 2 refine (dedup + pitfalls)
                                          ->  Stage 3 filter   (gpt-5.4 judge:
                                                keep iff met on GT answer and
                                                NOT met on the weak answer)
```

## CLI

```bash
# English rubrics, validate on the first 50 train items
python rubrics_run/05_generate_rubrics_sciarena.py \
  --data sciarena-papers/SciArena-with-paperbank/train.json \
  --rubrics-out  sciarena-papers/SciArena-with-paperbank/train_rubrics.json \
  --cleaned-out  sciarena-papers/SciArena-with-paperbank/train_cleaned.jsonl \
  --items-dir    runs/sciarena/train_items \
  --limit 50 --item-concurrency 16 --judge-concurrency 8

# Chinese test set (translate question+answer; English citations) + Chinese rubrics
python rubrics_run/05_generate_rubrics_sciarena.py \
  --data sciarena-papers/SciArena-with-paperbank/test.json \
  --rubrics-out  sciarena-papers/SciArena-with-paperbank/test_zh_rubrics.json \
  --cleaned-out  sciarena-papers/SciArena-with-paperbank/test_zh_cleaned.jsonl \
  --items-dir    runs/sciarena/test_zh_items \
  --lang zh --item-concurrency 16 --judge-concurrency 8
```

Key flags: `--lang {en,zh}`, `--gen-model`, `--judge-model` (default
`openai/gpt-5.4`), `--limit`, `--resume` (skips per-item files that exist; reuses
an existing cleaned dataset so translations are not recomputed), `--seed`.

## Outputs

- **Cleaned dataset** (JSONL): one GT record per line — `id`, `question`,
  `question_type`, `subject`, `vote`, `gt_source`, `reference_answer`,
  `citations`, `model` (+ `question_en` / `reference_answer_en` / `lang` in zh).
- **Rubrics** (JSON array): one `SciArenaRubricItem` per record, each with
  `criteria` (`Criterion` shape identical to CAE, so they remain compatible with
  the `cae-rubrics-eval` scorer), `citation_grounding`, and `rubric_metadata`.

## Layout

```
schema.py              SciArenaRubricItem / Criterion / metadata
data_loader.py         NaN-tolerant streaming loader + select_gt
translate.py           question + GT answer -> Chinese (citations untouched)
pseudo_chunk.py        citations -> generation context
lang.py                en/zh language packs (templates, pitfalls, weak answer)
generator.py           Stage 1 prompt assembly + LLM call
refiner.py             Stage 2 dedup + default pitfalls
misalignment_filter.py Stage 3 (ref/weak anchor filter, concurrent)
judge.py               per-criterion judge (English/Chinese prompt)
pipeline.py            build_rubric_for_item_sciarena (orchestrator)
templates/{en,zh}/     system prompt, judge prompt, 6 type rules, exemplars
```
