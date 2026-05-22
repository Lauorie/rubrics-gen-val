# CAE Rubrics Scorer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an offline eval scorer that consumes `(item_idx, candidate_answer)` predictions, judges each candidate against its rubric via async per-criterion LLM calls, anchors against `reference_answer`/`weak_answer` baselines, and emits a `eval_report.json` with per-candidate breakdown + aggregate stats.

**Architecture:** 5 new modules (`judge.py`, `anchor.py`, `scorer.py`, `aggregate.py`, `run/04_score_predictions.py`) plus an async method on the existing `LLMClient`. Async per-criterion judges with a semaphore-limited concurrency (default 16). Anchor scores cached to disk; resume support via `--resume`.

**Tech Stack:** Python 3.11, asyncio, httpx.AsyncClient, pydantic v2, tenacity, pytest + pytest-asyncio for async tests.

**Spec:** `docs/superpowers/specs/2026-05-22-cae-rubrics-scorer-design.md`

---

## File Structure

**New files:**
- `src/rubrics/judge.py` — extracted per-criterion judge (sync + async)
- `src/rubrics/anchor.py` — anchor (ref/weak) scoring + cache
- `src/rubrics/scorer.py` — `Scorer` class with `score_one()` (async) + `score_batch()` (async)
- `src/rubrics/aggregate.py` — `build_aggregate(per_candidate, rubric_store) -> dict`
- `run/04_score_predictions.py` — CLI entry
- `tests/rubrics/test_judge.py`
- `tests/rubrics/test_anchor.py`
- `tests/rubrics/test_scorer.py`
- `tests/rubrics/test_aggregate.py`

**Modified files:**
- `src/rubrics/llm_client.py` — add `async complete_json_async()`
- `src/rubrics/misalignment_filter.py` — refactor `_judge_one` to delegate to `judge.judge_one_sync()` (no behavior change)
- `pyproject.toml` — add `pytest-asyncio>=0.23`

---

## Task 1: Add async LLM client method

**Files:**
- Modify: `src/rubrics/llm_client.py`
- Modify: `pyproject.toml` (add `pytest-asyncio`)
- Test: `tests/rubrics/test_llm_client.py` (add async test)

- [ ] **Step 1: Add `pytest-asyncio` dependency**

Edit `pyproject.toml`'s `[project.optional-dependencies] dev = [...]` line — add `"pytest-asyncio>=0.23"`. Run:
```bash
cd /home/juli/RLM && source .venv/bin/activate && pip install "pytest-asyncio>=0.23"
```

Also add to `[tool.pytest.ini_options]`:
```toml
asyncio_mode = "auto"
```

- [ ] **Step 2: Write failing async test**

Append to `tests/rubrics/test_llm_client.py`:

```python
import asyncio
import pytest


@pytest.mark.asyncio
async def test_llm_client_async_completion(mocker):
    import httpx
    from rubrics.llm_client import LLMClient, LLMConfig

    response = {
        "choices": [{"message": {"content": json.dumps({"ok": True})}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }
    mock_resp = mocker.Mock(status_code=200, json=lambda: response)
    mock_resp.raise_for_status = lambda: None

    async def fake_post(*args, **kwargs):
        return mock_resp

    mocker.patch.object(httpx.AsyncClient, "post", side_effect=fake_post)
    cfg = LLMConfig(api_key="sk-x", base_url="https://example/v1", model="m")
    client = LLMClient(cfg)
    out = await client.complete_json_async(system="s", user="u", schema_hint="x")
    assert out == {"ok": True}
```

- [ ] **Step 3: Run test — expect FAIL (`complete_json_async` not defined)**

```bash
pytest tests/rubrics/test_llm_client.py::test_llm_client_async_completion -v
```

- [ ] **Step 4: Implement async method in `llm_client.py`**

Append to `src/rubrics/llm_client.py` (inside `LLMClient` class, after `complete_json`):

```python
    async def complete_json_async(
        self, system: str, user: str, schema_hint: str,
        temperature: float | None = None, model: str | None = None,
    ) -> Any:
        """Async variant of complete_json. Uses an internal httpx.AsyncClient."""
        from tenacity import AsyncRetrying, RetryError

        async def _do_call() -> dict:
            async with httpx.AsyncClient(timeout=self.cfg.timeout_s) as ac:
                r = await ac.post(
                    f"{self.cfg.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.cfg.api_key}"},
                    json={
                        "model": model or self.cfg.model,
                        "temperature": temperature if temperature is not None else self.cfg.temperature,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                    },
                )
                r.raise_for_status()
                return r.json()

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self.cfg.max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError)),
            reraise=True,
        ):
            with attempt:
                data = await _do_call()
        content = data["choices"][0]["message"]["content"]
        block = _extract_json_block(content)
        try:
            return json.loads(block)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON. Raw content (first 500): %s", content[:500])
            raise ValueError(f"LLM did not return valid JSON: {e}") from e
```

- [ ] **Step 5: Run test — expect PASS**

```bash
pytest tests/rubrics/test_llm_client.py -v
```

Expected: 4 passed (3 prior + 1 new).

- [ ] **Step 6: Commit**

```bash
cd /home/juli/RLM && git add src/rubrics/llm_client.py tests/rubrics/test_llm_client.py pyproject.toml
git commit -m "feat(rubrics): add async LLM client method with tenacity retry"
```

---

## Task 2: Extract judge module (sync + async)

**Files:**
- Create: `src/rubrics/judge.py`
- Modify: `src/rubrics/misalignment_filter.py` (delegate to judge.py)
- Test: `tests/rubrics/test_judge.py`

- [ ] **Step 1: Write failing test**

Create `tests/rubrics/test_judge.py`:

```python
import pytest
from rubrics.judge import judge_one_sync, judge_one_async, JUDGE_PROMPT


def test_judge_one_sync_returns_met_true(mocker):
    fake_client = mocker.Mock()
    fake_client.complete_json.return_value = {"met": True, "reason": "matches"}
    result = judge_one_sync(
        fake_client, "Q", "candidate",
        {"text": "明确指出 X", "criterion_type": "factual_anchor"},
    )
    assert result["met"] is True
    assert result["reason"] == "matches"


def test_judge_one_sync_returns_met_false_on_judge_error(mocker):
    fake_client = mocker.Mock()
    fake_client.complete_json.side_effect = RuntimeError("api blew up")
    result = judge_one_sync(
        fake_client, "Q", "candidate",
        {"text": "x", "criterion_type": "factual_anchor"},
    )
    assert result["met"] is False
    assert "error" in result


@pytest.mark.asyncio
async def test_judge_one_async_returns_met(mocker):
    fake_client = mocker.Mock()
    async def fake_async(*a, **k):
        return {"met": False, "reason": "no"}
    fake_client.complete_json_async = fake_async
    result = await judge_one_async(
        fake_client, "Q", "cand",
        {"text": "x", "criterion_type": "factual_anchor"},
    )
    assert result["met"] is False


def test_judge_prompt_constant_loaded():
    assert isinstance(JUDGE_PROMPT, str) and len(JUDGE_PROMPT) > 50
```

- [ ] **Step 2: Run — expect FAIL (ImportError)**

```bash
pytest tests/rubrics/test_judge.py -v
```

- [ ] **Step 3: Implement `judge.py`**

Create `src/rubrics/judge.py`:

```python
"""Per-criterion judge: ask LLM whether a candidate response satisfies one rubric criterion.

Returns {met: bool, reason: str, [error: str]} dict.
"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import Any

from rubrics.llm_client import LLMClient

logger = logging.getLogger(__name__)

JUDGE_PROMPT = (Path(__file__).parent / "templates" / "misalignment_judge_prompt.txt").read_text(encoding="utf-8")


def _build_user_message(question: str, candidate: str, criterion: dict) -> str:
    return (
        f"[题目] {question}\n"
        f"[候选回答] {candidate}\n"
        f"[criterion] {criterion['text']}\n"
        f"[criterion 类型] {criterion['criterion_type']}"
    )


def judge_one_sync(
    judge_client: LLMClient, question: str, candidate: str, criterion: dict,
) -> dict:
    """Synchronous per-criterion judge. Returns {met, reason, error?}."""
    user = _build_user_message(question, candidate, criterion)
    try:
        out = judge_client.complete_json(system=JUDGE_PROMPT, user=user, schema_hint="{met, reason}")
        return {"met": bool(out.get("met", False)), "reason": str(out.get("reason", ""))}
    except Exception as e:
        logger.warning("Judge sync call failed for criterion %s: %s", criterion.get("id"), e)
        return {"met": False, "reason": "", "error": str(e)}


async def judge_one_async(
    judge_client: LLMClient, question: str, candidate: str, criterion: dict,
) -> dict:
    """Async per-criterion judge. Returns {met, reason, error?}."""
    user = _build_user_message(question, candidate, criterion)
    try:
        out = await judge_client.complete_json_async(system=JUDGE_PROMPT, user=user, schema_hint="{met, reason}")
        return {"met": bool(out.get("met", False)), "reason": str(out.get("reason", ""))}
    except Exception as e:
        logger.warning("Judge async call failed for criterion %s: %s", criterion.get("id"), e)
        return {"met": False, "reason": "", "error": str(e)}
```

- [ ] **Step 4: Refactor `misalignment_filter._judge_one` to delegate**

Edit `src/rubrics/misalignment_filter.py` — replace the existing `_judge_one` function with:

```python
def _judge_one(
    judge_client: LLMClient, question: str, candidate: str, criterion: dict,
) -> bool:
    """Boolean shim for the generation-stage filter.
    Returns conservative True for positive / False for negative on judge failure.
    """
    from rubrics.judge import judge_one_sync
    result = judge_one_sync(judge_client, question, candidate, criterion)
    if "error" in result:
        return True if criterion["sign"] == "positive" else False
    return result["met"]
```

The existing `WEAK_ANSWER`, `filter_misaligned`, and `_PROMPT` constants stay in misalignment_filter.py. (`_PROMPT` is now redundant with `judge.JUDGE_PROMPT` but leave it alone — different module, no harm.)

- [ ] **Step 5: Run all tests — expect PASS**

```bash
pytest tests/rubrics/test_judge.py tests/rubrics/test_misalignment_filter.py -v
```

Expected: 7 passed (4 new judge + 3 unchanged misalignment_filter).

- [ ] **Step 6: Commit**

```bash
git add src/rubrics/judge.py src/rubrics/misalignment_filter.py tests/rubrics/test_judge.py
git commit -m "feat(rubrics): extract judge module with sync+async per-criterion judging"
```

---

## Task 3: Anchor scoring + cache

**Files:**
- Create: `src/rubrics/anchor.py`
- Test: `tests/rubrics/test_anchor.py`

- [ ] **Step 1: Write failing test**

Create `tests/rubrics/test_anchor.py`:

```python
import json
from pathlib import Path
import pytest
from rubrics.anchor import compute_anchor_for_rubric, AnchorCache, WEAK_ANSWER


def _mk_rubric(idx=0):
    return {
        "item_idx": idx,
        "question_id": "1",
        "question": "什么是 ALE？",
        "reference_answer": "ALE 是任意拉格朗日-欧拉方法",
        "question_type": "简答题",
        "difficulty": "简单",
        "criteria": [
            {"id": "c1", "text": "提到 ALE", "category": "Essential",
             "weight": 5, "sign": "positive", "criterion_type": "factual_anchor"},
            {"id": "c2", "text": "回答以套话开头", "category": "Pitfall",
             "weight": 4, "sign": "negative", "criterion_type": "anti_hacking"},
        ],
    }


@pytest.mark.asyncio
async def test_compute_anchor_returns_ref_and_weak(mocker):
    fake_client = mocker.Mock()
    async def fake_async(*a, **k):
        # ref answer should meet c1; weak answer shouldn't
        # First 2 calls (ref): met c1=True, c2=False; next 2 (weak): met c1=False, c2=False
        if "ALE 是" in k.get("user", ""):
            return {"met": True, "reason": "yes"}
        return {"met": False, "reason": "no"}
    fake_client.complete_json_async = fake_async

    result = await compute_anchor_for_rubric(_mk_rubric(), fake_client)
    assert "ref_score" in result and "weak_score" in result
    assert result["ref_score"] > 0
    assert result["weak_score"] == 0.0


def test_anchor_cache_roundtrip(tmp_path: Path):
    cache_path = tmp_path / "anchors.json"
    cache = AnchorCache(cache_path)
    cache.set(0, ref_score=0.92, weak_score=0.04, judge_model="m")
    cache.flush()

    cache2 = AnchorCache(cache_path)
    cache2.load()
    rec = cache2.get(0)
    assert rec["ref_score"] == 0.92
    assert rec["weak_score"] == 0.04


def test_anchor_cache_get_missing_returns_none(tmp_path: Path):
    cache = AnchorCache(tmp_path / "x.json")
    assert cache.get(99) is None
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/rubrics/test_anchor.py -v
```

- [ ] **Step 3: Implement `anchor.py`**

Create `src/rubrics/anchor.py`:

```python
"""Compute ref/weak anchor scores per rubric and cache to disk."""
from __future__ import annotations
import asyncio
import datetime as dt
import json
import logging
from pathlib import Path
from typing import Optional

from rubrics.judge import judge_one_async
from rubrics.llm_client import LLMClient
from rubrics.scoring import score_response
from rubrics.schema import Criterion

logger = logging.getLogger(__name__)

WEAK_ANSWER = "我不知道。"


async def compute_anchor_for_rubric(
    rubric: dict, judge_client: LLMClient,
    weak_answer: str = WEAK_ANSWER,
) -> dict:
    """Score reference_answer and weak_answer against the rubric's criteria.

    Returns {ref_score, weak_score, judge_model, computed_at}.
    """
    question = rubric["question"]
    ref_answer = rubric["reference_answer"]
    criteria_dicts = rubric["criteria"]

    async def _judge_all(candidate: str) -> dict[str, bool]:
        tasks = [
            judge_one_async(judge_client, question, candidate, c)
            for c in criteria_dicts
        ]
        results = await asyncio.gather(*tasks)
        return {c["text"]: r["met"] for c, r in zip(criteria_dicts, results)}

    ref_met = await _judge_all(ref_answer)
    weak_met = await _judge_all(weak_answer)

    criteria_models = [Criterion(**c) for c in criteria_dicts]
    ref_score = score_response(criteria_models, ref_met)
    weak_score = score_response(criteria_models, weak_met)

    return {
        "ref_score": ref_score,
        "weak_score": weak_score,
        "judge_model": getattr(getattr(judge_client, "cfg", None), "model", "unknown"),
        "computed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }


class AnchorCache:
    """JSON-backed cache of anchor scores, keyed by item_idx (as string)."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._data: dict[str, dict] = {}

    def load(self) -> None:
        if self.path.exists():
            self._data = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self._data = {}

    def get(self, idx: int) -> Optional[dict]:
        return self._data.get(str(idx))

    def set(self, idx: int, *, ref_score: float, weak_score: float, judge_model: str) -> None:
        self._data[str(idx)] = {
            "ref_score": ref_score,
            "weak_score": weak_score,
            "judge_model": judge_model,
            "computed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        }

    def has(self, idx: int) -> bool:
        return str(idx) in self._data

    def flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
```

- [ ] **Step 4: Run — expect PASS**

```bash
pytest tests/rubrics/test_anchor.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/rubrics/anchor.py tests/rubrics/test_anchor.py
git commit -m "feat(rubrics): anchor scoring (ref/weak) + JSON cache"
```

---

## Task 4: Scorer (async per-candidate)

**Files:**
- Create: `src/rubrics/scorer.py`
- Test: `tests/rubrics/test_scorer.py`

- [ ] **Step 1: Write failing test**

Create `tests/rubrics/test_scorer.py`:

```python
import asyncio
import pytest
from rubrics.scorer import Scorer


def _mk_rubric(idx=0, question_type="简答题"):
    return {
        "item_idx": idx,
        "question_id": str(idx + 1),
        "question": "Q",
        "reference_answer": "ref",
        "question_type": question_type,
        "difficulty": "简单",
        "scenario": "x",
        "source": "y",
        "source_grounding": {"parsed_docs": [], "pages": [], "retrieved_chunk_ids": [],
                              "ground_status": "fallback_semantic"},
        "criteria": [
            {"id": "c1", "text": "提到 X", "category": "Essential",
             "weight": 5, "sign": "positive", "criterion_type": "factual_anchor"},
            {"id": "c2", "text": "回答以套话开头", "category": "Pitfall",
             "weight": 4, "sign": "negative", "criterion_type": "anti_hacking"},
        ],
        "rubric_metadata": {
            "generation_model": "m", "generation_passes": 1,
            "n_criteria_initial": 2, "n_criteria_final": 2,
            "n_dropped_misaligned": 0, "ref_answer_self_score": None,
            "weak_answer_self_score": None, "generated_at": "2026-05-22T00:00:00Z",
            "schema_version": "1.0",
        },
    }


@pytest.mark.asyncio
async def test_scorer_score_one_returns_breakdown(mocker):
    fake_client = mocker.Mock()
    async def fake_async(*a, **k):
        # met c1 (positive) only
        if "提到 X" in k.get("user", ""):
            return {"met": True, "reason": "ok"}
        return {"met": False, "reason": "no"}
    fake_client.complete_json_async = fake_async
    fake_client.cfg = mocker.Mock(model="mockmodel")

    rubrics = {0: _mk_rubric()}
    scorer = Scorer(rubrics=rubrics, judge_client=fake_client, concurrency=4)
    result = await scorer.score_one(item_idx=0, candidate="X is here")
    assert result["item_idx"] == 0
    # c1 met (5) - 0 / 5 = 1.0
    assert result["score"] == 1.0
    assert len(result["breakdown"]) == 2
    by_id = {b["id"]: b for b in result["breakdown"]}
    assert by_id["c1"]["met"] is True
    assert by_id["c2"]["met"] is False


@pytest.mark.asyncio
async def test_scorer_score_batch_processes_all(mocker):
    fake_client = mocker.Mock()
    async def fake_async(*a, **k):
        return {"met": True, "reason": ""}
    fake_client.complete_json_async = fake_async
    fake_client.cfg = mocker.Mock(model="mockmodel")

    rubrics = {i: _mk_rubric(idx=i) for i in range(3)}
    scorer = Scorer(rubrics=rubrics, judge_client=fake_client, concurrency=4)
    preds = [{"item_idx": i, "answer": f"answer-{i}"} for i in range(3)]
    results = await scorer.score_batch(preds)
    assert len(results) == 3
    assert all(r["score"] >= 0 for r in results)


@pytest.mark.asyncio
async def test_scorer_missing_idx_returns_error_record(mocker):
    fake_client = mocker.Mock()
    fake_client.cfg = mocker.Mock(model="m")
    scorer = Scorer(rubrics={0: _mk_rubric()}, judge_client=fake_client, concurrency=4)
    result = await scorer.score_one(item_idx=99, candidate="x")
    assert result["score"] is None
    assert "error" in result
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/rubrics/test_scorer.py -v
```

- [ ] **Step 3: Implement `scorer.py`**

Create `src/rubrics/scorer.py`:

```python
"""Async per-candidate rubric scorer."""
from __future__ import annotations
import asyncio
import datetime as dt
import logging
from typing import Optional

from rubrics.judge import judge_one_async
from rubrics.llm_client import LLMClient
from rubrics.schema import Criterion
from rubrics.scoring import score_response

logger = logging.getLogger(__name__)


def _compute_anchored(score: float, ref: Optional[float], weak: Optional[float]) -> Optional[dict]:
    if score is None or ref is None or weak is None:
        return None
    if ref <= weak:
        return {"ref_score": ref, "weak_score": weak, "normalized": None,
                 "warning": "ref_score <= weak_score; rubric may be miscalibrated"}
    norm = (score - weak) / (ref - weak)
    return {"ref_score": ref, "weak_score": weak, "normalized": max(0.0, min(1.0, norm))}


class Scorer:
    def __init__(
        self, rubrics: dict[int, dict], judge_client: LLMClient,
        concurrency: int = 16, anchors: Optional[dict[int, dict]] = None,
    ):
        self.rubrics = rubrics
        self.judge_client = judge_client
        self.semaphore = asyncio.Semaphore(concurrency)
        self.anchors = anchors or {}

    async def _judge_criterion(self, question: str, candidate: str, criterion: dict) -> dict:
        async with self.semaphore:
            return await judge_one_async(self.judge_client, question, candidate, criterion)

    async def score_one(self, item_idx: int, candidate: str) -> dict:
        if item_idx not in self.rubrics:
            return {
                "item_idx": item_idx,
                "score": None,
                "error": f"no rubric found for item_idx={item_idx}",
                "scored_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            }
        rubric = self.rubrics[item_idx]
        criteria_dicts = rubric["criteria"]

        tasks = [
            self._judge_criterion(rubric["question"], candidate, c)
            for c in criteria_dicts
        ]
        verdicts = await asyncio.gather(*tasks)

        met_by_text = {c["text"]: v["met"] for c, v in zip(criteria_dicts, verdicts)}
        criteria_models = [Criterion(**c) for c in criteria_dicts]
        score = score_response(criteria_models, met_by_text)

        breakdown = []
        for c, v in zip(criteria_dicts, verdicts):
            sign_val = c["weight"] if c["sign"] == "positive" else -c["weight"]
            contribution = sign_val if v["met"] else 0
            breakdown.append({
                "id": c["id"],
                "text": c["text"],
                "category": c["category"],
                "weight": c["weight"],
                "sign": c["sign"],
                "criterion_type": c["criterion_type"],
                "met": v["met"],
                "reason": v.get("reason", ""),
                "contribution": contribution,
                **({"error": v["error"]} if "error" in v else {}),
            })

        anchor = self.anchors.get(item_idx)
        if anchor is not None:
            score_anchored = _compute_anchored(score, anchor.get("ref_score"), anchor.get("weak_score"))
        else:
            score_anchored = None

        return {
            "item_idx": item_idx,
            "question_id": rubric.get("question_id"),
            "question_type": rubric.get("question_type"),
            "difficulty": rubric.get("difficulty"),
            "candidate_answer": candidate,
            "score": score,
            "score_anchored": score_anchored,
            "breakdown": breakdown,
            "judge_model": getattr(getattr(self.judge_client, "cfg", None), "model", "unknown"),
            "scored_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        }

    async def score_batch(self, predictions: list[dict]) -> list[dict]:
        tasks = [self.score_one(p["item_idx"], p["answer"]) for p in predictions]
        return await asyncio.gather(*tasks)
```

- [ ] **Step 4: Run — expect PASS**

```bash
pytest tests/rubrics/test_scorer.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/rubrics/scorer.py tests/rubrics/test_scorer.py
git commit -m "feat(rubrics): async per-candidate Scorer with semaphore concurrency"
```

---

## Task 5: Aggregate report builder

**Files:**
- Create: `src/rubrics/aggregate.py`
- Test: `tests/rubrics/test_aggregate.py`

- [ ] **Step 1: Write failing test**

Create `tests/rubrics/test_aggregate.py`:

```python
from rubrics.aggregate import build_aggregate


def _mk_result(idx, qtype, difficulty, score, ref=0.95, weak=0.05, met_map=None):
    breakdown = []
    if met_map:
        for cid, (ctype, met, weight, sign) in met_map.items():
            breakdown.append({
                "id": cid, "text": cid, "category": "Essential" if sign == "positive" else "Pitfall",
                "weight": weight, "sign": sign, "criterion_type": ctype,
                "met": met, "reason": "", "contribution": weight if met else 0,
            })
    return {
        "item_idx": idx, "score": score,
        "score_anchored": {"ref_score": ref, "weak_score": weak,
                             "normalized": (score - weak) / max(ref - weak, 1e-6)},
        "question_type": qtype, "difficulty": difficulty,
        "breakdown": breakdown,
    }


def test_aggregate_computes_means():
    results = [
        _mk_result(0, "简答题", "简单", 0.9),
        _mk_result(1, "简答题", "困难", 0.5),
        _mk_result(2, "决策题", "中等", 0.7),
    ]
    agg = build_aggregate(results)
    assert agg["n_predictions"] == 3
    assert agg["n_scored_ok"] == 3
    assert abs(agg["mean_score"] - 0.7) < 1e-9
    assert agg["by_question_type"]["简答题"]["n"] == 2
    assert agg["by_difficulty"]["困难"]["n"] == 1


def test_aggregate_excludes_null_scores_from_mean():
    results = [
        _mk_result(0, "简答题", "简单", 0.9),
        {"item_idx": 1, "score": None, "error": "no rubric", "question_type": None, "difficulty": None, "breakdown": []},
    ]
    agg = build_aggregate(results)
    assert agg["n_predictions"] == 2
    assert agg["n_scored_ok"] == 1
    assert agg["n_errors"] == 1
    assert agg["mean_score"] == 0.9


def test_aggregate_by_criterion_type_met_rate():
    r1 = _mk_result(0, "简答题", "简单", 0.5,
                    met_map={"c1": ("factual_anchor", True, 5, "positive"),
                              "c2": ("factual_anchor", False, 5, "positive")})
    r2 = _mk_result(1, "简答题", "简单", 0.5,
                    met_map={"c3": ("factual_anchor", True, 5, "positive"),
                              "c4": ("anti_hacking", True, 4, "negative")})
    agg = build_aggregate([r1, r2])
    fa = agg["by_criterion_type"]["factual_anchor"]
    assert fa["n_criteria"] == 3
    assert abs(fa["met_rate"] - 2/3) < 1e-9
    ah = agg["by_criterion_type"]["anti_hacking"]
    assert ah["met_rate"] == 1.0
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement `aggregate.py`**

Create `src/rubrics/aggregate.py`:

```python
"""Build aggregate statistics over per-candidate score results."""
from __future__ import annotations
from collections import defaultdict
from statistics import mean
from typing import Iterable


def _safe_mean(xs: list[float]) -> float | None:
    xs = [x for x in xs if x is not None]
    return mean(xs) if xs else None


def build_aggregate(results: Iterable[dict]) -> dict:
    results = list(results)
    n = len(results)
    ok = [r for r in results if r.get("score") is not None]
    n_errors = n - len(ok)

    raw_scores = [r["score"] for r in ok]
    anchored = [
        r["score_anchored"]["normalized"]
        for r in ok
        if r.get("score_anchored") and r["score_anchored"].get("normalized") is not None
    ]

    by_qt: dict[str, list] = defaultdict(list)
    by_qt_norm: dict[str, list] = defaultdict(list)
    by_diff: dict[str, list] = defaultdict(list)
    by_diff_norm: dict[str, list] = defaultdict(list)
    crit_counter: dict[str, list[bool]] = defaultdict(list)

    for r in ok:
        qt = r.get("question_type")
        if qt:
            by_qt[qt].append(r["score"])
            if r.get("score_anchored") and r["score_anchored"].get("normalized") is not None:
                by_qt_norm[qt].append(r["score_anchored"]["normalized"])
        diff = r.get("difficulty")
        if diff:
            by_diff[diff].append(r["score"])
            if r.get("score_anchored") and r["score_anchored"].get("normalized") is not None:
                by_diff_norm[diff].append(r["score_anchored"]["normalized"])
        for b in r.get("breakdown", []):
            crit_counter[b["criterion_type"]].append(b["met"])

    return {
        "n_predictions": n,
        "n_scored_ok": len(ok),
        "n_errors": n_errors,
        "mean_score": _safe_mean(raw_scores),
        "mean_anchored": _safe_mean(anchored),
        "by_question_type": {
            qt: {
                "n": len(scores),
                "mean": _safe_mean(scores),
                "mean_anchored": _safe_mean(by_qt_norm.get(qt, [])),
            }
            for qt, scores in by_qt.items()
        },
        "by_difficulty": {
            d: {
                "n": len(scores),
                "mean": _safe_mean(scores),
                "mean_anchored": _safe_mean(by_diff_norm.get(d, [])),
            }
            for d, scores in by_diff.items()
        },
        "by_criterion_type": {
            ct: {"n_criteria": len(metlist), "met_rate": sum(metlist) / len(metlist) if metlist else 0.0}
            for ct, metlist in crit_counter.items()
        },
    }
```

- [ ] **Step 4: Run — expect PASS**

```bash
pytest tests/rubrics/test_aggregate.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/rubrics/aggregate.py tests/rubrics/test_aggregate.py
git commit -m "feat(rubrics): aggregate report (means, by_type, by_difficulty, by_criterion_type)"
```

---

## Task 6: CLI run script + smoke test

**Files:**
- Create: `run/04_score_predictions.py`
- Create: `tests/preds_sample.jsonl` (test fixture)

- [ ] **Step 1: Create CLI**

Create `run/04_score_predictions.py`:

```python
"""Score model predictions against CAE rubrics."""
from __future__ import annotations
import argparse
import asyncio
import datetime as dt
import json
import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv

from rubrics.aggregate import build_aggregate
from rubrics.anchor import AnchorCache, compute_anchor_for_rubric
from rubrics.llm_client import LLMClient, LLMConfig
from rubrics.scorer import Scorer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")
logger = logging.getLogger("score_predictions")


def load_rubrics(items_dir: Path) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for p in sorted(items_dir.glob("idx_*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        out[r["item_idx"]] = r
    return out


def load_predictions(path: Path) -> list[dict]:
    preds: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        preds.append(json.loads(line))
    return preds


async def ensure_anchors(
    rubrics: dict[int, dict], cache: AnchorCache, client: LLMClient,
    refresh: bool, concurrency: int,
) -> None:
    cache.load()
    missing = [idx for idx in rubrics if refresh or not cache.has(idx)]
    if not missing:
        logger.info("Anchor cache hit for all %d rubrics", len(rubrics))
        return
    logger.info("Computing anchors for %d rubrics (refresh=%s)...", len(missing), refresh)

    sem = asyncio.Semaphore(concurrency)

    async def _one(idx: int) -> None:
        async with sem:
            res = await compute_anchor_for_rubric(rubrics[idx], client)
        cache.set(idx, ref_score=res["ref_score"], weak_score=res["weak_score"], judge_model=res["judge_model"])

    await asyncio.gather(*(_one(idx) for idx in missing))
    cache.flush()
    logger.info("Anchor cache written to %s", cache.path)


async def amain() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--predictions", required=True, type=Path)
    p.add_argument("--rubrics-dir", default=Path("rubrics/items"), type=Path)
    p.add_argument("--anchor-cache", default=Path("data/CAE-anchor-scores.json"), type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--concurrency", type=int, default=16)
    p.add_argument("--judge-model", default=None)
    p.add_argument("--refresh-anchors", action="store_true")
    p.add_argument("--no-anchors", action="store_true")
    p.add_argument("--resume", action="store_true")
    args = p.parse_args()

    load_dotenv()
    cfg = LLMConfig.from_env()
    if args.judge_model:
        cfg.model = args.judge_model
    client = LLMClient(cfg)

    rubrics = load_rubrics(args.rubrics_dir)
    logger.info("Loaded %d rubrics", len(rubrics))

    preds = load_predictions(args.predictions)
    logger.info("Loaded %d predictions from %s", len(preds), args.predictions)

    anchor_cache = AnchorCache(args.anchor_cache)
    if not args.no_anchors:
        await ensure_anchors(rubrics, anchor_cache, client, args.refresh_anchors, args.concurrency)

    anchors = {int(k): v for k, v in anchor_cache._data.items()} if not args.no_anchors else None

    already_done: dict[int, dict] = {}
    if args.resume and args.out.exists():
        prior = json.loads(args.out.read_text(encoding="utf-8"))
        for r in prior.get("per_candidate", []):
            if r.get("score") is not None:
                already_done[r["item_idx"]] = r
        logger.info("Resume: %d candidates already scored", len(already_done))

    todo = [pp for pp in preds if pp["item_idx"] not in already_done]
    logger.info("Scoring %d candidates...", len(todo))

    t0 = time.time()
    scorer = Scorer(rubrics=rubrics, judge_client=client, concurrency=args.concurrency, anchors=anchors)
    new_results = await scorer.score_batch(todo)
    elapsed = time.time() - t0

    all_results = list(already_done.values()) + new_results
    all_results.sort(key=lambda r: r.get("item_idx", -1))

    aggregate = build_aggregate(all_results)
    aggregate["judge_model"] = cfg.model
    aggregate["rubric_version"] = "1.0"
    aggregate["scored_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    aggregate["elapsed_seconds"] = round(elapsed, 2)

    report = {"per_candidate": all_results, "aggregate": aggregate}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Wrote eval report to %s", args.out)


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Create a tiny sample predictions file**

```bash
cd /home/juli/RLM && cat > tests/preds_sample.jsonl <<'EOF'
{"item_idx": 0, "answer": "在流固耦合中，当流体与结构密度接近时，隐式分区算法的迭代会不收敛。压力滞后被强耦合放大导致失稳，因此需要采用 monolithic 方法或改进的压力投影技术。"}
{"item_idx": 3, "answer": "JWL 方程的核心参数包括 A 和 B（压力系数，单位 GPa）、R1、R2、ω（无量纲常数）、V（相对体积）、E（爆轰产物体积内能）。"}
EOF
```

- [ ] **Step 3: Dry-run scoring on 2-item sample**

```bash
cd /home/juli/RLM && source .venv/bin/activate && PYTHONPATH=src python run/04_score_predictions.py \
    --predictions tests/preds_sample.jsonl \
    --out data/eval_sample.json \
    --concurrency 8
```

Expected output ends with `Wrote eval report to data/eval_sample.json`. Anchor computation will run on first invocation (1700 calls, ~3 min).

After completion, inspect:
```bash
jq '.aggregate' data/eval_sample.json
```

Expected: `mean_score` between 0.3 and 1.0; both candidates scored; `n_errors == 0`.

- [ ] **Step 4: Commit (skip eval_sample.json from VCS via gitignore)**

Add to `.gitignore`:
```
data/eval_*.json
data/CAE-anchor-scores.json
tests/preds_*.jsonl
```

Then commit:
```bash
git add run/04_score_predictions.py .gitignore
git commit -m "feat(rubrics): score_predictions CLI with anchor cache + resume"
```

---

## Task 7: Validate output structure end-to-end

This task verifies the eval report's structure matches the spec.

- [ ] **Step 1: Write a structure assertion script**

Create `tests/rubrics/test_eval_report_structure.py`:

```python
"""End-to-end structure verification of a real eval_*.json report file.

Skipped if no real report exists. Runs after `python run/04_score_predictions.py`.
"""
import json
from pathlib import Path
import pytest


REPORT = Path("/home/juli/RLM/data/eval_sample.json")


@pytest.mark.skipif(not REPORT.exists(), reason="eval_sample.json not generated yet")
def test_report_has_required_top_level_keys():
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    assert set(report.keys()) >= {"per_candidate", "aggregate"}


@pytest.mark.skipif(not REPORT.exists(), reason="eval_sample.json not generated yet")
def test_per_candidate_records_well_formed():
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    for r in report["per_candidate"]:
        assert "item_idx" in r
        if r.get("score") is not None:
            assert 0.0 <= r["score"] <= 1.0
            assert "breakdown" in r
            for b in r["breakdown"]:
                assert "id" in b and "category" in b and "met" in b
                assert "contribution" in b


@pytest.mark.skipif(not REPORT.exists(), reason="eval_sample.json not generated yet")
def test_aggregate_has_required_subreports():
    agg = json.loads(REPORT.read_text(encoding="utf-8"))["aggregate"]
    for key in ["n_predictions", "n_scored_ok", "n_errors",
                "mean_score", "by_question_type", "by_difficulty", "by_criterion_type"]:
        assert key in agg, f"missing aggregate key: {key}"
```

- [ ] **Step 2: Run**

```bash
cd /home/juli/RLM && source .venv/bin/activate && pytest tests/rubrics/test_eval_report_structure.py -v
```

Expected: 3 passed (or 3 skipped if you haven't run the CLI dry-run yet).

- [ ] **Step 3: Commit**

```bash
git add tests/rubrics/test_eval_report_structure.py
git commit -m "test(rubrics): structure assertions for eval report"
```

---

## Self-Review

**Spec coverage:**
- §2 Architecture (4 components) → Tasks 2 (judge), 3 (anchor), 4 (scorer), 5 (aggregate) ✅
- §3 Input/output format → Task 4 (Scorer breakdown), Task 5 (aggregate), Task 6 (CLI loads JSONL) ✅
- §4 Anchor mechanism → Task 3 + Task 6 CLI orchestration ✅
- §5 Judge prompt → Task 2 (reuses existing template) ✅
- §6 Failure handling → Task 2 (judge returns error field on exception), Task 4 (null score on missing rubric), Task 6 (no try/except wrap because asyncio.gather propagates) — **gap noted below**
- §7 New/modified files — all 6 files covered ✅
- §8 CLI flags → Task 6 (all flags present) ✅
- §9 Async concurrency → Task 4 (semaphore) ✅
- §11 Cost — informational only, no task
- §13 Success criteria → Task 7 structure asserts

**Gap fix (failure handling, §6):** Spec says "整个 candidate 处理崩 → 写入 per_candidate {score: null, error: ...}". Currently `Scorer.score_batch` uses `asyncio.gather` which would propagate exceptions and fail the whole batch. The implementation in Task 4 handles missing rubric idx gracefully but not other crashes. **Fix inline:** add `return_exceptions=True` to `asyncio.gather` in `score_batch` and wrap exception cases into error records.

Inline fix to Task 4 Step 3, replace `score_batch`:

```python
    async def score_batch(self, predictions: list[dict]) -> list[dict]:
        tasks = [self.score_one(p["item_idx"], p["answer"]) for p in predictions]
        raw = await asyncio.gather(*tasks, return_exceptions=True)
        out: list[dict] = []
        for p, r in zip(predictions, raw):
            if isinstance(r, Exception):
                logger.exception("scorer crashed on item_idx=%s", p.get("item_idx"))
                out.append({
                    "item_idx": p.get("item_idx"),
                    "score": None,
                    "error": f"{type(r).__name__}: {r}",
                    "scored_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                })
            else:
                out.append(r)
        return out
```

(Engineer: include this version when writing scorer.py in Task 4 Step 3.)

**Placeholder scan:** No "TBD" / "TODO" / vague phrases. All code blocks complete.

**Type consistency:** `judge_one_async(client, question, candidate, criterion_dict) -> dict[str, Any]` consistent between judge.py, anchor.py, and scorer.py. `score_response(criteria: Iterable[Criterion], met_by_text: dict[str, bool]) -> float` matches existing `scoring.py`. CLI flag names match §8.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-22-cae-rubrics-scorer-implementation.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Cleaner audit trail for the 7-task plan.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
