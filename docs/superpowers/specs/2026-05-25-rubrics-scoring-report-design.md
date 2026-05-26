# Rubric Scoring + Summary Report — Design Spec

## Goal

Score the 94 RLM-generated answers in `data/CAE-v2.0-1-rubrics.json` against their per-item criteria, save full per-item results, and emit a Chinese-language markdown report that highlights aggregate scores, lost-point patterns (失分点), gained-point patterns (得分点), pitfall trips, and the worst 10 items.

## Non-goals

- No new judge logic — reuse `src/rubrics/` (Scorer, judge, scoring, aggregate) as-is.
- No re-computation of anchors — `data/CAE-anchor-scores.json` is already populated for all 94 item_idxs.
- No per-item appendix for all 94 items — only the lowest-10 get drilled into.

## Inputs

- **`data/CAE-v2.0-1-rubrics.json`** — 94 items, each with: `item_idx` (0..93), `question`, `criteria` (list with `id`, `text`, `category`, `weight`, `sign`, `criterion_type`, `evidence_quote`), `reference_answer`, `rlm_answer`, and metadata fields (`question_type`, `difficulty`, `scenario`, `source`).
- **`data/CAE-anchor-scores.json`** — `{item_idx_str: {ref_score, weak_score, judge_model, computed_at}}` for all 94 items.
- **Credentials** — `OPENAI_API_KEY` + `OPENAI_BASE_URL` from `papers_qa/.env` (aiberm proxy).

## Outputs

- **`outputs/scoring/cae-v2.0-1-scores.json`** — JSON array, one entry per scored item:
  ```json
  {
    "item_idx": 0,
    "question_id": "1",
    "question_type": "...",
    "difficulty": "...",
    "score": 0.78,
    "score_anchored": {"ref_score": 1.0, "weak_score": 0.0, "normalized": 0.78},
    "breakdown": [
      {"id": "c1", "text": "...", "category": "Essential", "criterion_type": "factual_anchor",
       "weight": 5, "sign": "positive", "met": true, "reason": "..."},
      ...
    ],
    "judge_model": "openai/gpt-5.5",
    "computed_at": "2026-05-25T..."
  }
  ```
  Resume source-of-truth: re-running skips items whose `item_idx` already appears with no error.

- **`outputs/scoring/cae-v2.0-1-report.md`** — Chinese markdown, 7 sections:
  1. Header (候选模型, 评分模型, 总样本, 成功/错误, 生成时间).
  2. **总体得分** — table with `mean raw`, `mean anchored`.
  3. **按题型分组** — table of `{question_type, count, mean, mean_anchored}`.
  4. **按难度** — same shape as §3.
  5. **失分点 — criterion_type 命中率最低** — table of `{criterion_type, total, met, hit_rate}` sorted by `hit_rate` ASC (lowest first; only `sign=positive` rows; `anti_hacking` excluded).
  6. **得分点 — criterion_type 命中率最高** — same data, sorted DESC.
  7. **Pitfall 触发分析** — table of every `criterion_type=anti_hacking` row, sorted by `trip_count` DESC, showing `{pitfall text, items triggered, % of 94}`.
  8. **最低分 10 题** — for each of the 10 items with lowest `score_anchored.normalized`: heading with `item_idx`, `question_id`, score, then full `question` text, then a bulleted list of every criterion with ✅/❌ + judge reason.

## Pipeline

```
Load rubrics JSON      ─┐
Load anchors JSON      ─┤
Load existing scores ──┤  ──→  Scorer (semaphore=16)
                       │           │
                       │           └─→ judge_one_async ×836  (gpt-5.5)
                       │
                       └──→ score_response → per-item dict ─→ append to scores.json
                                                           └─→ aggregate → render report
```

Concurrency = 16 (existing Scorer default). Resume = filter input by `item_idx in already-scored-ok`.

## Modules

- **`src/score_rlm_answers.py`** (~180 lines) — CLI + orchestration. Loads JSON, builds Scorer, runs scoring, writes scores + report.
- **`src/rubrics_report.py`** (~150 lines) — pure-function markdown rendering. Inputs: aggregate dict + per-item results + meta dict. Output: markdown string. Kept separate so tests can render without API calls.
- **`tests/test_score_rlm_answers.py`** (~200 lines) — covers: scores-JSON I/O, resume filter, mocked Scorer end-to-end, CLI argparse.
- **`tests/test_rubrics_report.py`** (~150 lines) — covers: each report section rendered correctly from synthetic data; worst-10 ordering; pitfall section uses only anti_hacking; lost/gain sections exclude anti_hacking.

## Failure modes

- **Judge call fails** → that criterion's `met=False`, `error="..."` recorded in the breakdown; item still scored (penalized for that criterion). Existing `judge_one_async` already does this.
- **Item has no `rlm_answer` (null)** → skip with a logged warning; report shows `n_errors+=1`; item omitted from aggregate.
- **Anchor missing for an item_idx** → `score_anchored=None`; raw score still reported; item still counted.
- **scores.json corrupted mid-write** → atomic-rename via `tempfile.NamedTemporaryFile + os.replace` (same pattern as generate_rlm_answers).

## CLI

```
python src/score_rlm_answers.py \
    --input         data/CAE-v2.0-1-rubrics.json     (default)
    --anchors       data/CAE-anchor-scores.json       (default)
    --scores-out    outputs/scoring/cae-v2.0-1-scores.json   (default)
    --report-out    outputs/scoring/cae-v2.0-1-report.md      (default)
    --judge-model   openai/gpt-5.5                    (default)
    --concurrency   16                                (default)
    --worst-n       10                                (default)
    --dry-run                                          (skip LLM; render report from existing scores only)
    --log-level     INFO                              (default)
```

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| API cost ($15–20 at gpt-5.5) | MEDIUM | `--dry-run` first to verify wiring; aiberm dashboard for live spend |
| Judge contamination (judge same as candidate model) | LOW | We chose gpt-5.5 ≠ deepseek-v4-flash candidate; independent |
| Anchor judge mismatch (anchors used gpt-5.4-mini, scoring uses gpt-5.5) | LOW | Surfaced in report header; anchored scores are calibration, not point-precise |
| Long markdown file | LOW | Worst-10 cap keeps it under ~500 lines |
| Resume false-skip (item with `error` still skipped) | LOW | Filter matches `error is None` (mirrors `rlm_runner.load_done_ids`) |

## Acceptance criteria

1. Running the CLI produces `scores.json` with 94 entries and `report.md` with all 8 sections populated.
2. Mean anchored score is within [0, 1].
3. Worst-10 section lists exactly 10 items sorted ascending by `score_anchored.normalized` (NaN/None sorted last).
4. 失分点 section lists only `sign=positive` criterion_types, ordered by hit rate ASC.
5. Pitfall section lists only `criterion_type=anti_hacking` rows.
6. Re-running the CLI without `--dry-run` after a complete run makes 0 LLM calls.
7. All tests pass: ≥ 15 in test_score_rlm_answers + ≥ 10 in test_rubrics_report.
