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
        # ref answer (has "ALE 是") satisfies c1; weak doesn't
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
