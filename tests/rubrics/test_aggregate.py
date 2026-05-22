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
