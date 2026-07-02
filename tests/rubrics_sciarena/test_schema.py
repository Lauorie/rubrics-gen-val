"""Tests for SciArena rubric schema."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from rubrics_sciarena.schema import (
    Criterion,
    SciArenaRubricItem,
    normalize_question_type,
)


def _crit(**kw):
    base = dict(
        id="c1", text="States the focal shift is 0.3 mm", category="Essential",
        weight=5, sign="positive", criterion_type="factual_anchor",
    )
    base.update(kw)
    return base


def test_criterion_pitfall_must_be_negative():
    Criterion(**_crit(category="Pitfall", sign="negative", criterion_type="anti_hacking"))
    with pytest.raises(ValidationError):
        Criterion(**_crit(category="Pitfall", sign="positive", criterion_type="anti_hacking"))


def test_criterion_non_pitfall_must_be_positive():
    with pytest.raises(ValidationError):
        Criterion(**_crit(category="Essential", sign="negative"))


def test_criterion_weight_bounds():
    with pytest.raises(ValidationError):
        Criterion(**_crit(weight=0))
    with pytest.raises(ValidationError):
        Criterion(**_crit(weight=9))


def test_normalize_question_type_keeps_known():
    assert normalize_question_type("Conceptual Explanation") == "Conceptual Explanation"
    assert normalize_question_type("Paper Finding") == "Paper Finding"


def test_normalize_question_type_maps_unknown_to_others():
    assert normalize_question_type("Something New") == "Others"
    assert normalize_question_type(None) == "Others"


def test_rubric_item_valid_construction():
    item = SciArenaRubricItem(
        id="abc",
        question="What models assess thermal effects?",
        reference_answer="Several studies ...",
        question_type="Conceptual Explanation",
        subject="Optics",
        vote="A",
        gt_source="A",
        citation_grounding={"citation_ids": ["1@1"], "titles": ["T"], "n_citations": 1},
        criteria=[Criterion(**_crit())],
        rubric_metadata={
            "generation_model": "m", "generation_passes": 3,
            "n_criteria_initial": 1, "n_criteria_final": 1, "n_dropped_misaligned": 0,
            "generated_at": "2026-06-01T00:00:00Z", "schema_version": "1.0",
        },
    )
    assert item.gt_source == "A"
    assert item.criteria[0].id == "c1"
    # round-trips to a plain dict for JSON output
    assert item.model_dump()["question_type"] == "Conceptual Explanation"


def test_rubric_item_rejects_bad_gt_source():
    with pytest.raises(ValidationError):
        SciArenaRubricItem(
            id="abc", question="q", reference_answer="r",
            question_type="Others", subject="s", vote="A", gt_source="C",
            citation_grounding={"citation_ids": [], "titles": [], "n_citations": 0},
            criteria=[Criterion(**_crit())],
            rubric_metadata={
                "generation_model": "m", "generation_passes": 3,
                "n_criteria_initial": 1, "n_criteria_final": 1, "n_dropped_misaligned": 0,
                "generated_at": "t", "schema_version": "1.0",
            },
        )
