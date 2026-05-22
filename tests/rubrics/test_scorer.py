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
    assert all(r["score"] is not None for r in results)


@pytest.mark.asyncio
async def test_scorer_missing_idx_returns_error_record(mocker):
    fake_client = mocker.Mock()
    fake_client.cfg = mocker.Mock(model="m")
    scorer = Scorer(rubrics={0: _mk_rubric()}, judge_client=fake_client, concurrency=4)
    result = await scorer.score_one(item_idx=99, candidate="x")
    assert result["score"] is None
    assert "error" in result


@pytest.mark.asyncio
async def test_scorer_score_batch_isolates_crashes(mocker):
    """If one score_one raises (e.g., judge crash), other candidates still complete."""
    fake_client = mocker.Mock()
    fake_client.cfg = mocker.Mock(model="m")

    call_count = {"n": 0}
    async def flaky(*a, **k):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("transient")
        return {"met": True, "reason": ""}
    fake_client.complete_json_async = flaky

    rubrics = {i: _mk_rubric(idx=i) for i in range(2)}
    scorer = Scorer(rubrics=rubrics, judge_client=fake_client, concurrency=2)
    # Note: judge_one_async catches exceptions internally — so score_one won't crash.
    # We're testing the crash-isolation path explicitly by patching score_one to raise.
    original = scorer.score_one
    async def boom(item_idx, candidate):
        if item_idx == 0:
            raise RuntimeError("synthetic crash")
        return await original(item_idx, candidate)
    scorer.score_one = boom

    preds = [{"item_idx": 0, "answer": "a"}, {"item_idx": 1, "answer": "b"}]
    results = await scorer.score_batch(preds)
    assert len(results) == 2
    assert results[0]["score"] is None
    assert "error" in results[0]
    assert results[1]["score"] is not None
