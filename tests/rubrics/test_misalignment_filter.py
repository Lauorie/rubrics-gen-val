from rubrics.misalignment_filter import filter_misaligned, WEAK_ANSWER


def test_filter_keeps_positive_criterion_that_passes_both_sides(mocker):
    judge_client = mocker.Mock()
    # criterion judged: met on ref (true), not met on weak (false) → keep
    judge_client.complete_json.side_effect = [
        {"met": True, "reason": "x"},
        {"met": False, "reason": "y"},
    ]
    criteria = [{
        "id": "c1", "text": "明确指出 ALE 方法网格随材料运动",
        "category": "Essential", "weight": 5, "sign": "positive",
        "criterion_type": "factual_anchor",
    }]
    kept, n_dropped = filter_misaligned(
        question="什么是 ALE？", reference_answer="ALE 网格随材料运动",
        criteria=criteria, judge_client=judge_client,
    )
    assert len(kept) == 1
    assert n_dropped == 0


def test_filter_drops_positive_criterion_not_met_on_ref(mocker):
    judge_client = mocker.Mock()
    judge_client.complete_json.side_effect = [
        {"met": False, "reason": "ref doesn't say"},
    ]
    criteria = [{
        "id": "c1", "text": "完全偏离的 criterion", "category": "Essential",
        "weight": 5, "sign": "positive", "criterion_type": "factual_anchor",
    }]
    kept, n_dropped = filter_misaligned(
        question="q", reference_answer="ref", criteria=criteria, judge_client=judge_client,
    )
    assert kept == []
    assert n_dropped == 1


def test_filter_skips_pitfalls(mocker):
    judge_client = mocker.Mock()
    criteria = [{
        "id": "c1", "text": "回答篇幅冗长", "category": "Pitfall", "weight": 3,
        "sign": "negative", "criterion_type": "anti_hacking",
    }]
    kept, n_dropped = filter_misaligned(
        question="q", reference_answer="ref", criteria=criteria, judge_client=judge_client,
    )
    assert len(kept) == 1
    assert n_dropped == 0
    assert not judge_client.complete_json.called
