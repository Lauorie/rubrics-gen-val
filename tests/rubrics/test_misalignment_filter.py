from rubrics.misalignment_filter import filter_misaligned, WEAK_ANSWER
from rubrics.refiner import DEFAULT_PITFALLS


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


def test_filter_keeps_mandatory_style_pitfalls_without_judging(mocker):
    """The 2 content-agnostic mandatory style pitfalls are domain-independent
    and stay exempt from reference validation (no judge call)."""
    judge_client = mocker.Mock()
    criteria = [
        {"id": "c1", "text": DEFAULT_PITFALLS[0]["text"], "category": "Pitfall",
         "weight": 3, "sign": "negative", "criterion_type": "anti_hacking"},
        {"id": "c2", "text": DEFAULT_PITFALLS[1]["text"], "category": "Pitfall",
         "weight": 2, "sign": "negative", "criterion_type": "anti_hacking"},
    ]
    kept, n_dropped = filter_misaligned(
        question="q", reference_answer="ref", criteria=criteria, judge_client=judge_client,
    )
    assert len(kept) == 2
    assert n_dropped == 0
    assert not judge_client.complete_json.called


def test_filter_drops_domain_pitfall_that_fires_on_reference(mocker):
    """A domain-specific pitfall that the judge says the REFERENCE answer triggers
    is mis-specified (it would penalize correct answers) → drop it."""
    judge_client = mocker.Mock()
    judge_client.complete_json.side_effect = [
        {"met": True, "reason": "reference itself exhibits this"},
    ]
    criteria = [{
        "id": "c1", "text": "将声速 C 误解释为材料热容", "category": "Pitfall",
        "weight": 4, "sign": "negative", "criterion_type": "anti_hacking",
    }]
    kept, n_dropped = filter_misaligned(
        question="q", reference_answer="ref answer that triggers it",
        criteria=criteria, judge_client=judge_client,
    )
    assert kept == []
    assert n_dropped == 1
    assert judge_client.complete_json.called


def test_filter_keeps_domain_pitfall_not_fired_on_reference(mocker):
    """A domain pitfall the reference does NOT trigger is well-specified → keep,
    but it must actually be validated (judge IS called)."""
    judge_client = mocker.Mock()
    judge_client.complete_json.side_effect = [
        {"met": False, "reason": "reference is clean"},
    ]
    criteria = [{
        "id": "c1", "text": "将声速 C 误解释为材料热容", "category": "Pitfall",
        "weight": 4, "sign": "negative", "criterion_type": "anti_hacking",
    }]
    kept, n_dropped = filter_misaligned(
        question="q", reference_answer="clean ref", criteria=criteria, judge_client=judge_client,
    )
    assert len(kept) == 1
    assert n_dropped == 0
    assert judge_client.complete_json.called
