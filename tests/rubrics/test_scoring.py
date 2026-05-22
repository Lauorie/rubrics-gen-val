from rubrics.scoring import score_response
from rubrics.schema import Criterion


def _mk(text, cat, weight, sign):
    types = {"Pitfall": "anti_hacking"}
    return Criterion(
        id="c", text=text, category=cat, weight=weight, sign=sign,
        criterion_type=types.get(cat, "factual_anchor"),
    )


def test_score_all_essentials_met():
    criteria = [_mk("a", "Essential", 5, "positive"), _mk("b", "Important", 3, "positive")]
    met = {"a": True, "b": True}
    s = score_response(criteria, met_by_text=met)
    # (5 + 3) / 8 = 1.0
    assert s == 1.0


def test_score_partial():
    criteria = [_mk("a", "Essential", 5, "positive"), _mk("b", "Important", 3, "positive")]
    met = {"a": True, "b": False}
    s = score_response(criteria, met_by_text=met)
    assert s == 5 / 8


def test_score_with_pitfall_penalty():
    criteria = [
        _mk("a", "Essential", 5, "positive"),
        _mk("套话", "Pitfall", 4, "negative"),
    ]
    met = {"a": True, "套话": True}
    s = score_response(criteria, met_by_text=met)
    # (5 - 4) / 5 = 0.2
    assert abs(s - 0.2) < 1e-9


def test_score_clips_to_zero_when_penalty_exceeds():
    criteria = [
        _mk("a", "Essential", 1, "positive"),
        _mk("套话", "Pitfall", 5, "negative"),
    ]
    met = {"a": True, "套话": True}
    s = score_response(criteria, met_by_text=met)
    assert s == 0.0
