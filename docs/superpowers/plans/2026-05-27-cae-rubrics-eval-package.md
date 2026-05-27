# cae-rubrics-eval/ Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a standalone `cae-rubrics-eval/` subdirectory inside `RLM/` that a collaborator can copy out and use to score their own answers (e.g. from a ReAct algorithm) against the 94-item CAE rubric, producing scores directly comparable to our prior RLM evaluations.

**Architecture:** Copy (do not import from main repo) the 7 eval-side modules from `src/rubrics/` into a new `cae_eval/` Python package; rewrite their internal imports from `rubrics.*` → `cae_eval.*`. Ship the rubric JSON (with `rlm_answer`/`rlm_error` fields stripped) and the precomputed anchor cache. Provide a thin CLI `score.py` and a Chinese-language `README.md`.

**Tech Stack:** Python ≥3.11, pydantic v2, httpx, tenacity, python-dotenv. No sentence-transformers, no faiss-cpu, no numpy.

**Spec:** [docs/superpowers/specs/2026-05-27-cae-rubrics-eval-package-design.md](../specs/2026-05-27-cae-rubrics-eval-package-design.md)

**No package-level tests** per design decision — verification is done at packaging time via the smoke run in Task 10, not packaged into the deliverable.

---

## Task 1: Create skeleton directory + project metadata

**Files:**
- Create: `cae-rubrics-eval/pyproject.toml`
- Create: `cae-rubrics-eval/.env.example`
- Create: `cae-rubrics-eval/.gitignore`
- Create: `cae-rubrics-eval/cae_eval/__init__.py`
- Create: `cae-rubrics-eval/cae_eval/templates/.gitkeep`
- Create: `cae-rubrics-eval/data/.gitkeep`
- Create: `cae-rubrics-eval/examples/.gitkeep`

- [ ] **Step 1: Create directory tree**

```bash
cd /home/juli/RLM
mkdir -p cae-rubrics-eval/cae_eval/templates cae-rubrics-eval/data cae-rubrics-eval/examples
touch cae-rubrics-eval/cae_eval/templates/.gitkeep cae-rubrics-eval/data/.gitkeep cae-rubrics-eval/examples/.gitkeep
```

- [ ] **Step 2: Write `cae-rubrics-eval/pyproject.toml`**

```toml
[project]
name = "cae-rubrics-eval"
version = "1.0.0"
description = "Standalone scoring kit for the CAE-v2.0-1 rubric set (94 items, locked judge=gpt-5.4-mini)."
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.6",
    "httpx>=0.27",
    "tenacity>=8.2",
    "python-dotenv>=1.0",
]

[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[tool.setuptools]
packages = ["cae_eval"]

[tool.setuptools.package-data]
cae_eval = ["templates/*.txt"]
```

- [ ] **Step 3: Write `cae-rubrics-eval/.env.example`**

```bash
# Copy to .env and fill in your key.
# Required: an OpenAI-compatible chat-completions endpoint that can serve openai/gpt-5.4-mini.
# Using a different model will break score comparability with our prior RLM evaluations.

LLM_API_KEY=
LLM_BASE_URL=https://aiberm.com/v1
LLM_MODEL=openai/gpt-5.4-mini
```

- [ ] **Step 4: Write `cae-rubrics-eval/.gitignore`**

```
.env
__pycache__/
*.egg-info/
.venv/
outputs/
*.pyc
```

- [ ] **Step 5: Write `cae-rubrics-eval/cae_eval/__init__.py`**

```python
"""cae_eval — scoring kit for the CAE-v2.0-1 rubric set."""

__version__ = "1.0.0"
```

- [ ] **Step 6: Verify tree**

```bash
cd /home/juli/RLM
find cae-rubrics-eval -type f | sort
```

Expected output:

```
cae-rubrics-eval/.env.example
cae-rubrics-eval/.gitignore
cae-rubrics-eval/cae_eval/__init__.py
cae-rubrics-eval/cae_eval/templates/.gitkeep
cae-rubrics-eval/data/.gitkeep
cae-rubrics-eval/examples/.gitkeep
cae-rubrics-eval/pyproject.toml
```

- [ ] **Step 7: Commit**

```bash
cd /home/juli/RLM
git add cae-rubrics-eval/pyproject.toml cae-rubrics-eval/.env.example cae-rubrics-eval/.gitignore cae-rubrics-eval/cae_eval/__init__.py cae-rubrics-eval/cae_eval/templates/.gitkeep cae-rubrics-eval/data/.gitkeep cae-rubrics-eval/examples/.gitkeep
git commit -m "feat(cae-eval): scaffold cae-rubrics-eval/ package skeleton"
```

---

## Task 2: Copy modules that don't need import rewriting

These three modules (`schema.py`, `llm_client.py`, `aggregate.py`) have no `from rubrics.*` imports — they can be copied verbatim.

**Files:**
- Create: `cae-rubrics-eval/cae_eval/schema.py` (verbatim copy of `src/rubrics/schema.py`)
- Create: `cae-rubrics-eval/cae_eval/llm_client.py` (verbatim copy of `src/rubrics/llm_client.py`)
- Create: `cae-rubrics-eval/cae_eval/aggregate.py` (verbatim copy of `src/rubrics/aggregate.py`)

- [ ] **Step 1: Copy the three files**

```bash
cd /home/juli/RLM
cp src/rubrics/schema.py     cae-rubrics-eval/cae_eval/schema.py
cp src/rubrics/llm_client.py cae-rubrics-eval/cae_eval/llm_client.py
cp src/rubrics/aggregate.py  cae-rubrics-eval/cae_eval/aggregate.py
```

- [ ] **Step 2: Confirm no `rubrics` imports leaked through**

```bash
cd /home/juli/RLM
grep -nE "^from rubrics|^import rubrics" cae-rubrics-eval/cae_eval/schema.py cae-rubrics-eval/cae_eval/llm_client.py cae-rubrics-eval/cae_eval/aggregate.py || echo "CLEAN"
```

Expected output: `CLEAN`

- [ ] **Step 3: Commit**

```bash
cd /home/juli/RLM
git add cae-rubrics-eval/cae_eval/schema.py cae-rubrics-eval/cae_eval/llm_client.py cae-rubrics-eval/cae_eval/aggregate.py
git commit -m "feat(cae-eval): copy schema/llm_client/aggregate (no import rewrites needed)"
```

---

## Task 3: Copy modules with import rewriting

These four modules (`scoring.py`, `judge.py`, `anchor.py`, `scorer.py`) have `from rubrics.X` imports that must become `from cae_eval.X`.

**Files:**
- Create: `cae-rubrics-eval/cae_eval/scoring.py` (rewritten copy)
- Create: `cae-rubrics-eval/cae_eval/judge.py` (rewritten copy)
- Create: `cae-rubrics-eval/cae_eval/anchor.py` (rewritten copy)
- Create: `cae-rubrics-eval/cae_eval/scorer.py` (rewritten copy)
- Create: `cae-rubrics-eval/cae_eval/templates/misalignment_judge_prompt.txt` (verbatim copy)

- [ ] **Step 1: Copy the four files**

```bash
cd /home/juli/RLM
cp src/rubrics/scoring.py cae-rubrics-eval/cae_eval/scoring.py
cp src/rubrics/judge.py   cae-rubrics-eval/cae_eval/judge.py
cp src/rubrics/anchor.py  cae-rubrics-eval/cae_eval/anchor.py
cp src/rubrics/scorer.py  cae-rubrics-eval/cae_eval/scorer.py
```

- [ ] **Step 2: Rewrite imports `rubrics.` → `cae_eval.`**

```bash
cd /home/juli/RLM
sed -i 's/^from rubrics\./from cae_eval./g; s/^import rubrics\./import cae_eval./g' \
    cae-rubrics-eval/cae_eval/scoring.py \
    cae-rubrics-eval/cae_eval/judge.py \
    cae-rubrics-eval/cae_eval/anchor.py \
    cae-rubrics-eval/cae_eval/scorer.py
```

- [ ] **Step 3: Verify rewrites are complete and correct**

```bash
cd /home/juli/RLM
echo "=== Should show only 'cae_eval.' imports (no leftover 'rubrics.') ==="
grep -nE "^from (rubrics|cae_eval)\.|^import (rubrics|cae_eval)\." \
    cae-rubrics-eval/cae_eval/scoring.py \
    cae-rubrics-eval/cae_eval/judge.py \
    cae-rubrics-eval/cae_eval/anchor.py \
    cae-rubrics-eval/cae_eval/scorer.py
echo "=== Should be empty (no 'rubrics' leftovers anywhere in cae_eval/) ==="
grep -rnE "(^|\W)rubrics\." cae-rubrics-eval/cae_eval/ || echo "CLEAN"
```

Expected: the first grep shows 10 lines (1 in scoring + 1 in judge + 4 in anchor + 4 in scorer), each starting with `from cae_eval.`. The second grep prints `CLEAN`.

- [ ] **Step 4: Copy the judge prompt template**

```bash
cd /home/juli/RLM
cp src/rubrics/templates/misalignment_judge_prompt.txt cae-rubrics-eval/cae_eval/templates/misalignment_judge_prompt.txt
```

- [ ] **Step 5: Commit**

```bash
cd /home/juli/RLM
git add cae-rubrics-eval/cae_eval/scoring.py cae-rubrics-eval/cae_eval/judge.py cae-rubrics-eval/cae_eval/anchor.py cae-rubrics-eval/cae_eval/scorer.py cae-rubrics-eval/cae_eval/templates/misalignment_judge_prompt.txt
git commit -m "feat(cae-eval): copy scoring/judge/anchor/scorer with cae_eval import rewrites"
```

---

## Task 4: Verify the package imports cleanly

Sanity check: install the package locally and import every module, with no LLM calls.

- [ ] **Step 1: Create venv and install**

```bash
cd /home/juli/RLM/cae-rubrics-eval
python3.11 -m venv .venv
.venv/bin/pip install -e . 1>/dev/null
```

Expected: install completes without errors. pydantic / httpx / tenacity / python-dotenv are pulled in; no sentence-transformers, no faiss-cpu.

- [ ] **Step 2: Import every module**

```bash
cd /home/juli/RLM/cae-rubrics-eval
.venv/bin/python -c "
from cae_eval import schema, scoring, llm_client, judge, anchor, scorer, aggregate
print('imports OK')
print('schema.Criterion:', schema.Criterion)
print('scoring.score_response:', scoring.score_response)
print('judge.JUDGE_PROMPT first 40 chars:', judge.JUDGE_PROMPT[:40])
"
```

Expected output ends with `imports OK` and three non-empty lines.

If the judge prompt line shows an empty string or raises a `FileNotFoundError`, the template wasn't copied or the package-data entry in `pyproject.toml` is wrong — check Task 1 step 2 and Task 3 step 4.

- [ ] **Step 3: (No commit — pure verification step.)**

---

## Task 5: Prepare data files (strip + copy)

**Files:**
- Create: `cae-rubrics-eval/data/CAE-v2.0-1-rubrics.json` (94 items, `rlm_answer` + `rlm_error` removed)
- Create: `cae-rubrics-eval/data/CAE-anchor-scores.json` (verbatim copy of `data/CAE-anchor-scores.json`)

- [ ] **Step 1: Strip `rlm_answer` / `rlm_error` from rubrics, write to package**

```bash
cd /home/juli/RLM
python3.11 -c "
import json, pathlib
src = json.load(open('data/CAE-v2.0-1-rubrics.json'))
for r in src:
    r.pop('rlm_answer', None)
    r.pop('rlm_error', None)
out = pathlib.Path('cae-rubrics-eval/data/CAE-v2.0-1-rubrics.json')
out.write_text(json.dumps(src, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'wrote {len(src)} rubrics to {out}')
"
```

Expected output: `wrote 94 rubrics to cae-rubrics-eval/data/CAE-v2.0-1-rubrics.json`

- [ ] **Step 2: Verify the strip and required fields**

```bash
cd /home/juli/RLM
python3.11 -c "
import json
data = json.load(open('cae-rubrics-eval/data/CAE-v2.0-1-rubrics.json'))
assert len(data) == 94, f'expected 94, got {len(data)}'
for r in data:
    assert 'rlm_answer' not in r, f'leak in item_idx={r[\"item_idx\"]}'
    assert 'rlm_error' not in r, f'leak in item_idx={r[\"item_idx\"]}'
    for k in ('item_idx', 'question_id', 'question', 'reference_answer', 'criteria', 'question_type', 'difficulty'):
        assert k in r, f'missing {k} in item_idx={r.get(\"item_idx\")}'
print('rubrics OK — 94 items, no rlm_* leaks, required fields present')
"
```

Expected output: `rubrics OK — 94 items, no rlm_* leaks, required fields present`

- [ ] **Step 3: Copy the anchor cache verbatim**

```bash
cd /home/juli/RLM
cp data/CAE-anchor-scores.json cae-rubrics-eval/data/CAE-anchor-scores.json
```

- [ ] **Step 4: Verify anchor cache is parity-compatible**

```bash
cd /home/juli/RLM
python3.11 -c "
import json
a = json.load(open('cae-rubrics-eval/data/CAE-anchor-scores.json'))
assert len(a) == 94, f'expected 94 anchors, got {len(a)}'
models = {v['judge_model'] for v in a.values()}
assert models == {'openai/gpt-5.4-mini'}, f'unexpected judge models: {models}'
print(f'anchor cache OK — 94 entries, all judge_model=openai/gpt-5.4-mini')
"
```

Expected output: `anchor cache OK — 94 entries, all judge_model=openai/gpt-5.4-mini`

- [ ] **Step 5: Remove the now-redundant `.gitkeep` in `data/`**

```bash
cd /home/juli/RLM
rm cae-rubrics-eval/data/.gitkeep
git rm --cached cae-rubrics-eval/data/.gitkeep 2>/dev/null || true
```

- [ ] **Step 6: Commit**

```bash
cd /home/juli/RLM
git add cae-rubrics-eval/data/CAE-v2.0-1-rubrics.json cae-rubrics-eval/data/CAE-anchor-scores.json
git rm --cached cae-rubrics-eval/data/.gitkeep 2>/dev/null || true
git commit -m "data(cae-eval): ship rubrics (rlm_answer stripped) + anchor cache"
```

---

## Task 6: Write `score.py` CLI

**Files:**
- Create: `cae-rubrics-eval/score.py`

- [ ] **Step 1: Write the CLI**

```python
"""Score candidate answers against the CAE-v2.0-1 rubric set.

Usage:
    python score.py --predictions preds.jsonl --out eval.json

See README.md for full documentation.
"""
from __future__ import annotations
import argparse
import asyncio
import datetime as dt
import json
import logging
import time
from pathlib import Path

from dotenv import load_dotenv

from cae_eval.aggregate import build_aggregate
from cae_eval.anchor import AnchorCache, compute_anchor_for_rubric
from cae_eval.llm_client import LLMClient, LLMConfig
from cae_eval.scorer import Scorer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")
logger = logging.getLogger("score")

PACKAGE_ROOT = Path(__file__).parent
DEFAULT_RUBRICS = PACKAGE_ROOT / "data" / "CAE-v2.0-1-rubrics.json"
DEFAULT_ANCHORS = PACKAGE_ROOT / "data" / "CAE-anchor-scores.json"


def load_rubrics(path: Path) -> dict[int, dict]:
    """Load rubrics from a single JSON-array file keyed by `item_idx`."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return {r["item_idx"]: r for r in data}


def load_predictions(path: Path) -> list[dict]:
    """Load predictions from a JSONL file. Each line must have item_idx and answer."""
    preds: list[dict] = []
    for ln, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            raise ValueError(f"{path}:{ln} is not valid JSON: {e}") from e
        if "item_idx" not in obj or "answer" not in obj:
            raise ValueError(f"{path}:{ln} missing required field 'item_idx' or 'answer'")
        preds.append(obj)
    return preds


def warn_if_judge_mismatch(anchor_cache: dict, current_model: str) -> None:
    """Log a warning if the anchor cache was computed with a different judge model."""
    anchor_models = {v.get("judge_model") for v in anchor_cache.values()}
    anchor_models.discard(None)
    if anchor_models and current_model not in anchor_models:
        logger.warning(
            "Judge model mismatch: anchors computed with %s, you are using %s. "
            "score_anchored will NOT be comparable to prior RLM evaluations. "
            "To recalibrate, delete data/CAE-anchor-scores.json and re-run.",
            sorted(anchor_models), current_model,
        )


async def ensure_anchors(
    rubrics: dict[int, dict], cache: AnchorCache, client: LLMClient, concurrency: int,
) -> None:
    """Compute and persist any missing anchor scores."""
    cache.load()
    missing = [idx for idx in rubrics if not cache.has(idx)]
    if not missing:
        logger.info("Anchor cache hit for all %d rubrics", len(rubrics))
        return
    logger.info("Computing anchors for %d rubrics (cache miss)...", len(missing))
    sem = asyncio.Semaphore(concurrency)

    async def _one(idx: int) -> None:
        async with sem:
            res = await compute_anchor_for_rubric(rubrics[idx], client)
        cache.set(idx, ref_score=res["ref_score"], weak_score=res["weak_score"], judge_model=res["judge_model"])

    await asyncio.gather(*(_one(idx) for idx in missing))
    cache.flush()
    logger.info("Anchor cache written to %s", cache.path)


async def amain() -> None:
    p = argparse.ArgumentParser(description="Score predictions against CAE-v2.0-1 rubrics.")
    p.add_argument("--predictions", required=True, type=Path, help="JSONL file with one {item_idx, answer} per line")
    p.add_argument("--out", required=True, type=Path, help="Output JSON path for the eval report")
    p.add_argument("--rubrics", default=DEFAULT_RUBRICS, type=Path, help=f"Rubric JSON file (default: {DEFAULT_RUBRICS.name})")
    p.add_argument("--anchors", default=DEFAULT_ANCHORS, type=Path, help=f"Anchor cache JSON file (default: {DEFAULT_ANCHORS.name})")
    p.add_argument("--concurrency", type=int, default=16, help="Max concurrent judge LLM calls (default: 16)")
    p.add_argument("--judge-model", default=None, help="Override LLM_MODEL from env (NOT RECOMMENDED — breaks score comparability)")
    args = p.parse_args()

    load_dotenv()
    cfg = LLMConfig.from_env()
    if args.judge_model:
        cfg.model = args.judge_model
    client = LLMClient(cfg)

    rubrics = load_rubrics(args.rubrics)
    logger.info("Loaded %d rubrics from %s", len(rubrics), args.rubrics)

    preds = load_predictions(args.predictions)
    logger.info("Loaded %d predictions from %s", len(preds), args.predictions)

    anchor_cache = AnchorCache(args.anchors)
    await ensure_anchors(rubrics, anchor_cache, client, args.concurrency)
    warn_if_judge_mismatch(anchor_cache._data, cfg.model)
    anchors = {int(k): v for k, v in anchor_cache._data.items()}

    t0 = time.time()
    scorer = Scorer(rubrics=rubrics, judge_client=client, concurrency=args.concurrency, anchors=anchors)
    results = await scorer.score_batch(preds)
    elapsed = time.time() - t0

    results.sort(key=lambda r: r.get("item_idx", -1))
    aggregate = build_aggregate(results)
    aggregate["judge_model"] = cfg.model
    aggregate["rubric_version"] = "1.0"
    aggregate["scored_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    aggregate["elapsed_seconds"] = round(elapsed, 2)

    report = {"per_candidate": results, "aggregate": aggregate}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Wrote eval report to %s", args.out)
    logger.info("mean_score=%s mean_anchored=%s n=%d errors=%d",
                aggregate["mean_score"], aggregate["mean_anchored"],
                aggregate["n_scored_ok"], aggregate["n_errors"])


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke import — confirm the CLI module parses**

```bash
cd /home/juli/RLM/cae-rubrics-eval
.venv/bin/python -c "import importlib.util; spec = importlib.util.spec_from_file_location('score', 'score.py'); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); print('score.py imports OK')"
```

Expected: `score.py imports OK`

- [ ] **Step 3: Verify `--help` runs without an API key**

```bash
cd /home/juli/RLM/cae-rubrics-eval
.venv/bin/python score.py --help
```

Expected: an argparse help message listing `--predictions`, `--out`, `--rubrics`, `--anchors`, `--concurrency`, `--judge-model`. (No LLM call is made.)

- [ ] **Step 4: Commit**

```bash
cd /home/juli/RLM
git add cae-rubrics-eval/score.py
git commit -m "feat(cae-eval): add score.py CLI (5 flags, anchor-mismatch warning)"
```

---

## Task 7: Write example predictions file

**Files:**
- Create: `cae-rubrics-eval/examples/predictions_example.jsonl`

The three samples deliberately span the score range so the recipient can see what good / weak / bad answers produce.

- [ ] **Step 1: Write `cae-rubrics-eval/examples/predictions_example.jsonl`**

Write this exact content (the line-1 paraphrase is taken from the project's existing `tests/preds_sample.jsonl` — a known-good paraphrase for item_idx=0):

```jsonl
{"item_idx": 0, "answer": "在流固耦合中，当流体与结构密度接近时，隐式分区算法的迭代会不收敛。压力滞后被强耦合放大导致失稳，因此需要采用 monolithic 方法或改进的压力投影技术。"}
{"item_idx": 1, "answer": "我不知道。"}
{"item_idx": 2, "answer": "this answer is intentionally off-topic and in the wrong language — pineapples are tropical."}
```

Line 1 paraphrases item_idx=0's reference (covers density coupling + pressure lag + monolithic fix), line 2 is the weak baseline, line 3 is deliberate garbage. Together they span the expected score range so the recipient can see what good / weak / bad outputs produce.

- [ ] **Step 2: Verify the file parses as JSONL**

```bash
cd /home/juli/RLM
python3.11 -c "
import json
lines = open('cae-rubrics-eval/examples/predictions_example.jsonl').read().splitlines()
assert len(lines) == 3, f'expected 3 lines, got {len(lines)}'
for ln in lines:
    o = json.loads(ln)
    assert 'item_idx' in o and 'answer' in o
print('predictions_example.jsonl OK — 3 valid lines')
"
```

Expected output: `predictions_example.jsonl OK — 3 valid lines`

- [ ] **Step 3: Commit**

```bash
cd /home/juli/RLM
git add cae-rubrics-eval/examples/predictions_example.jsonl
git commit -m "examples(cae-eval): 3-line predictions sample (good/weak/bad)"
```

---

## Task 8: Generate `examples/eval_example.json` by running `score.py`

This requires a working `LLM_API_KEY`. The output file is shipped so the recipient has a concrete reference for the report shape.

**Files:**
- Create: `cae-rubrics-eval/examples/eval_example.json` (output of running `score.py` on `predictions_example.jsonl`)

- [ ] **Step 1: Prepare `.env`**

```bash
cd /home/juli/RLM/cae-rubrics-eval
test -f .env || cp .env.example .env
```

Then edit `.env` to fill in your real `LLM_API_KEY`. (Do not commit `.env`; it is gitignored.)

If you don't have an API key handy, defer this task — the package still works without `eval_example.json`, the recipient just has no reference output to compare against. Skip to Task 9 and revisit later.

- [ ] **Step 2: Run the scorer on the example file**

```bash
cd /home/juli/RLM/cae-rubrics-eval
.venv/bin/python score.py \
    --predictions examples/predictions_example.jsonl \
    --out examples/eval_example.json \
    --concurrency 8
```

Expected: the run completes in under a minute (3 items × ~9 criteria × <1s per call at concurrency 8). Final log line shows `mean_score=<float>` with `n=3 errors=0`.

- [ ] **Step 3: Sanity-check the output**

```bash
cd /home/juli/RLM/cae-rubrics-eval
.venv/bin/python -c "
import json
r = json.load(open('examples/eval_example.json'))
agg = r['aggregate']
assert agg['n_predictions'] == 3
assert agg['n_errors'] == 0
assert 0.0 <= agg['mean_score'] <= 1.0
# good > bad sanity check (allow for judge stochasticity)
scores_by_idx = {c['item_idx']: c['score'] for c in r['per_candidate']}
print('scores by item_idx:', scores_by_idx)
assert scores_by_idx[0] > scores_by_idx[2], 'good answer should outscore garbage'
print('eval_example.json OK')
"
```

Expected output: a dict of scores plus `eval_example.json OK`. If the assertion fails (good ≯ garbage), the judge is broken or your example paraphrase was too thin — go back to Task 7 step 2 and write a stronger paraphrase.

- [ ] **Step 4: Commit**

```bash
cd /home/juli/RLM
git add cae-rubrics-eval/examples/eval_example.json
git commit -m "examples(cae-eval): generate eval_example.json from predictions sample"
```

---

## Task 9: Write `README.md`

**Files:**
- Create: `cae-rubrics-eval/README.md`

The README is in Chinese, primary entry point for the recipient.

- [ ] **Step 1: Write `cae-rubrics-eval/README.md`**

````markdown
# cae-rubrics-eval

针对 CAE-v2.0-1（94 题中文 CAE/工程仿真专家 QA）的**独立打分工具包**。
你用任何算法（ReAct、CoT、纯 LLM、RAG、Agent…）生成答案，本包用 rubric + LLM judge 给你打分，并把分数归一化到与已有 RLM 实验直接可比的尺度。

打分原理与生成流程的完整设计见主仓库的 `ALGORITHMS.md` 与 `EXPERIMENTS.md`。本 README 只讲怎么用。

---

## 1. 快速开始（5 步）

```bash
# 1) 安装
cd cae-rubrics-eval
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e .

# 2) 配置 LLM 凭证
cp .env.example .env
# 编辑 .env，填入你的 LLM_API_KEY

# 3) 在 94 题上跑你的算法，生成 predictions.jsonl（格式见 §3）

# 4) 打分
python score.py --predictions predictions.jsonl --out eval.json

# 5) 看结果
python -c "import json; print(json.dumps(json.load(open('eval.json'))['aggregate'], ensure_ascii=False, indent=2))"
```

---

## 2. 数据集：`data/CAE-v2.0-1-rubrics.json`

94 条 rubric，每条字段：

| 字段 | 含义 | 你跑算法时是否要读 |
|---|---|---|
| `item_idx` | 唯一 id，0–93 | **要**（写到你 predictions 里） |
| `question_id` | 原数据集 id（"1"…"94"），与 item_idx 不一定相等 | 参考 |
| `question` | 题目原文 | **要**（喂给你的模型） |
| `question_type` | 简答题/主观题/决策题/对比分析题/数值提取题/流程描述题/数值关系题 | 参考 |
| `difficulty` | 简单 / 中等 / 困难 | 参考 |
| `scenario` | 题目场景 | 参考 |
| `source` | 题目来源（教材+页码） | 参考 |
| `reference_answer` | **标准答案** | ⚠️ **不能喂给被评模型** |
| `criteria` | 打分细则 | ⚠️ **不能喂给被评模型** |
| `source_grounding` | RAG 检索元数据 | 评分内部用 |
| `rubric_metadata` | rubric 生成元数据 | 评分内部用 |

> ⚠️ **重要**：`reference_answer`、`criteria`、`source_grounding`、`rubric_metadata` 是评分系统的「金标准」和「打分细则」。**把它们直接喂进被评模型 = 作弊**，分数会失去意义。你的算法只能看 `question`（最多再加 `question_type`、`scenario`、`source` 作为类型提示）。

简化代码示例：

```python
import json
rubrics = json.load(open("data/CAE-v2.0-1-rubrics.json"))
for r in rubrics:
    answer = my_react_algorithm(r["question"])  # 只看 question
    save({"item_idx": r["item_idx"], "answer": answer})
```

---

## 3. Predictions 文件格式

JSONL（每行一个 JSON 对象）：

```jsonl
{"item_idx": 0, "answer": "在流固耦合中..."}
{"item_idx": 1, "answer": "..."}
...
```

- `item_idx`（**int**，必填）：从 `data/CAE-v2.0-1-rubrics.json` 里取，**不要写成 `question_id`**
- `answer`（**str**，必填）：你算法生成的答案
- 其他字段会被忽略（你可以塞自己的 trace、token 数、retrieval log 等）
- 漏掉某些 item_idx → 那几题不会被打分，aggregate 里 `n_predictions` 反映你实际提交了多少

---

## 4. 打分

```bash
python score.py \
    --predictions predictions.jsonl \
    --out eval.json \
    --concurrency 16
```

可选参数：
- `--rubrics PATH`：默认 `data/CAE-v2.0-1-rubrics.json`
- `--anchors PATH`：默认 `data/CAE-anchor-scores.json`
- `--concurrency N`：默认 16，越高越快但更容易撞 LLM 限流
- `--judge-model NAME`：**不推荐**。换 judge 模型会破坏与已有 RLM 实验的分数可比性（详见 §6）

---

## 5. 输出 `eval.json` 怎么看

```json
{
  "per_candidate": [
    {
      "item_idx": 0,
      "question_type": "主观题",
      "difficulty": "困难",
      "score": 0.78,                    // 原始分，0–1
      "score_anchored": {               // 归一化分，0–1，跨题可比
        "ref_score": 1.0,
        "weak_score": 0.0,
        "normalized": 0.78
      },
      "breakdown": [
        {"id": "c1", "text": "...", "category": "Essential", "weight": 5,
         "sign": "positive", "met": true, "contribution": 5, "reason": "..."},
        ...
      ]
    },
    ...
  ],
  "aggregate": {
    "n_predictions": 94,
    "n_scored_ok": 94,
    "n_errors": 0,
    "mean_score": 0.71,
    "mean_anchored": 0.62,              // ⭐ 跨系统对比就看这个
    "by_question_type": {...},
    "by_difficulty": {...},
    "by_criterion_type": {...},
    "judge_model": "openai/gpt-5.4-mini",
    "rubric_version": "1.0"
  }
}
```

**主指标**：`aggregate.mean_anchored`。它把每道题的原始分按 `(score − weak_score) / (ref_score − weak_score)` 归一化，确保不同 rubric 的「自然天花板」差异不影响系统级对比。

`score` 是「这道题你拿到的原始权重比例」，`score_anchored.normalized` 是「相对 reference_answer 和 `我不知道。` 两个基准之间你处在哪个位置」。后者才是有意义的横向指标。

---

## 6. 打分原理（一段话）

- **rubric** = 加权二值清单：每个 criterion 有 `category ∈ {Essential, Important, Optional, Pitfall}`、`weight ∈ [1,8]`、`sign ∈ {positive, negative}`
- **judge** = 用 LLM 逐条判断「这个 candidate answer 是否满足该 criterion」
- **score** = `(Σ w_i · met_i [positive] − Σ w_i · met_i [pitfall]) / Σ w_i [positive_max]`，clip 到 `[0,1]`
- **anchor 归一化** = `(score − weak_score) / (ref_score − weak_score)`，其中 `ref_score` = 用同样 rubric 给 reference_answer 打分得到的分数（≈1.0），`weak_score` = 用同样 rubric 给 `"我不知道。"` 打分得到的分数（≈0.0）

anchor 分数预先算好放在 `data/CAE-anchor-scores.json`，**判别模型固定为 `openai/gpt-5.4-mini`**。换 judge 必须重算 anchor，否则归一化分会偏。

---

## 7. 成本与时长

| 阶段 | LLM 调用数 | 估算成本 (gpt-5.4-mini) | 时长 (concurrency=16) |
|---|---|---|---|
| 打分 94 题 | 94 题 × 平均 8.9 条 criterion ≈ 836 calls | ≲ $0.5 | 5–10 分钟 |
| 重算 anchor（不推荐） | 94 × 2 答案 × 8.9 ≈ 1672 calls | ≲ $1 | ~10 分钟 |

`anchor` 已经预算好，正常使用只会触发「打分 94 题」那一行。

---

## 8. 常见问题

**Q: 我写错了，把 `question_id` 当成 `item_idx` 了**
→ `score.py` 会跑完但所有 `item_idx` 都对不上 rubric，输出里全是 `error: no rubric found for item_idx=X`。改成正确字段即可。`question_id` 是字符串 `"1"`–`"94"`，`item_idx` 是整数 `0`–`93`。

**Q: LLM 限流了**
→ `score.py` 用 tenacity 自动重试 3 次（指数退避 1–8s）。还是失败的话单条 criterion 会在 `breakdown` 里挂一个 `error` 字段但不影响其他条目。可以降 `--concurrency`，从 16 降到 4。

**Q: 我想换 judge 模型**
→ 不推荐。如果非换不可：

```bash
# 1) 删掉旧 anchor 缓存
rm data/CAE-anchor-scores.json
# 2) 用新模型重跑（脚本会自动重算 anchor 再开始打分）
python score.py --predictions preds.jsonl --out eval.json --judge-model your/model
```

但要清楚：你的 `mean_anchored` 不再能和我们用 `openai/gpt-5.4-mini` 跑的历史结果直接对比。

**Q: 我中途断了**
→ 重新跑 `python score.py ...` 即可，anchor cache 是命中复用的，不会重复消耗。`per_candidate` 不支持断点续传——重跑会重新打分所有 item。如果你的预算紧，预先把 predictions 分成两份分别跑、输出两个 eval.json 自己合并。

**Q: 一些 item 的 `score_anchored.normalized` 是 null**
→ 那条 rubric 的 `ref_score <= weak_score`，说明 rubric 可能有问题或者 reference 太弱。breakdown 里会有 `warning` 字段。这种 item 仅在 `score`（原始分）层面比较即可。

---

## 9. 包结构

```
cae-rubrics-eval/
├── README.md                          # 本文件
├── pyproject.toml
├── .env.example
├── score.py                           # CLI 入口
├── cae_eval/                          # Python 包
│   ├── schema.py                      # pydantic 模型
│   ├── scoring.py                     # 评分公式
│   ├── llm_client.py                  # OpenAI-compatible HTTP 客户端
│   ├── judge.py                       # 单 criterion judge
│   ├── anchor.py                      # ref/weak anchor 缓存
│   ├── scorer.py                      # 异步批量打分
│   ├── aggregate.py                   # 汇总报告
│   └── templates/
│       └── misalignment_judge_prompt.txt
├── data/
│   ├── CAE-v2.0-1-rubrics.json        # 94 条 rubric（rlm_answer 已剥除）
│   └── CAE-anchor-scores.json         # 94 条 anchor（gpt-5.4-mini 跑出来的）
└── examples/
    ├── predictions_example.jsonl      # 3 条示例：好答案 / "我不知道。" / 离题废话
    └── eval_example.json              # 用上面跑出来的 eval 报告，给你对照输出格式
```

---

## License

代码 MIT，rubric 数据用于研究目的。
````

- [ ] **Step 2: Verify the file renders sensibly**

```bash
cd /home/juli/RLM/cae-rubrics-eval
wc -l README.md
head -20 README.md
```

Expected: ~200 lines, first 20 are the title + first section heading.

- [ ] **Step 3: Commit**

```bash
cd /home/juli/RLM
git add cae-rubrics-eval/README.md
git commit -m "docs(cae-eval): write Chinese-language README"
```

---

## Task 10: End-to-end smoke verification

Final sanity check: from a fresh shell, reinstall and rerun the example, simulating what the recipient will do.

- [ ] **Step 1: Reset to a fresh state**

```bash
cd /home/juli/RLM/cae-rubrics-eval
rm -rf .venv build *.egg-info
```

- [ ] **Step 2: Fresh install**

```bash
cd /home/juli/RLM/cae-rubrics-eval
python3.11 -m venv .venv
.venv/bin/pip install -e . 1>/dev/null
```

Expected: no errors. pydantic / httpx / tenacity / python-dotenv pulled in; no sentence-transformers, no faiss-cpu.

- [ ] **Step 3: Verify deps are minimal**

```bash
cd /home/juli/RLM/cae-rubrics-eval
.venv/bin/pip list | grep -iE "sentence|faiss|numpy|tqdm|regex" || echo "MINIMAL DEPS OK"
```

Expected: `MINIMAL DEPS OK`. (If something does match, the dep was over-pulled — go check `pyproject.toml`.)

- [ ] **Step 4: Confirm rubric / anchor data is shippable as-is**

```bash
cd /home/juli/RLM/cae-rubrics-eval
.venv/bin/python -c "
import json
r = json.load(open('data/CAE-v2.0-1-rubrics.json'))
a = json.load(open('data/CAE-anchor-scores.json'))
assert len(r) == 94
assert len(a) == 94
assert not any('rlm_answer' in x or 'rlm_error' in x for x in r)
print(f'rubrics={len(r)} anchors={len(a)} no rlm_* leaks')
"
```

Expected: `rubrics=94 anchors=94 no rlm_* leaks`

- [ ] **Step 5: Rerun the example end-to-end**

```bash
cd /home/juli/RLM/cae-rubrics-eval
cp .env.example .env  # if .env doesn't already exist; otherwise leave alone
# (ensure LLM_API_KEY is set in .env)
.venv/bin/python score.py \
    --predictions examples/predictions_example.jsonl \
    --out /tmp/cae-rubrics-eval-sanity.json \
    --concurrency 8
```

Expected: the run completes; log shows `mean_score=<float>` with `n=3 errors=0`.

- [ ] **Step 6: Final asserts on the smoke output**

```bash
cd /home/juli/RLM/cae-rubrics-eval
.venv/bin/python -c "
import json
r = json.load(open('/tmp/cae-rubrics-eval-sanity.json'))
agg = r['aggregate']
assert agg['n_predictions'] == 3, f\"n_predictions={agg['n_predictions']}\"
assert agg['n_errors'] == 0, f\"n_errors={agg['n_errors']}\"
assert 0.0 <= agg['mean_score'] <= 1.0, f\"mean_score={agg['mean_score']}\"
assert agg['judge_model'] == 'openai/gpt-5.4-mini', f\"judge_model={agg['judge_model']}\"
assert agg['rubric_version'] == '1.0'
print('SMOKE OK — package is ready to ship')
"
```

Expected: `SMOKE OK — package is ready to ship`

- [ ] **Step 7: (No commit — verification only.)**

If everything passed, the package at `cae-rubrics-eval/` is ready to be zipped and sent:

```bash
cd /home/juli/RLM
zip -r /tmp/cae-rubrics-eval.zip cae-rubrics-eval -x 'cae-rubrics-eval/.venv/*' 'cae-rubrics-eval/.env' 'cae-rubrics-eval/*.egg-info/*' 'cae-rubrics-eval/__pycache__/*' 'cae-rubrics-eval/cae_eval/__pycache__/*'
```

That zip is what gets sent to the recipient.

---

## Done. What was built

A self-contained `cae-rubrics-eval/` directory at the repo root, containing:
- A `cae_eval/` Python package (7 modules + 1 judge prompt template)
- A thin `score.py` CLI
- Pre-shipped rubric JSON (rlm_answer stripped) and anchor cache
- Chinese-language README
- 3-line example predictions + sample eval report

Recipient workflow: unzip → `pip install -e .` → `cp .env.example .env` and fill in key → write `predictions.jsonl` → `python score.py --predictions ... --out eval.json` → read `aggregate.mean_anchored`.
