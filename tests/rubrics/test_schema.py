import pytest
from pydantic import ValidationError
from rubrics.schema import Criterion, RubricItem, SourceGrounding, RubricMetadata


def test_criterion_accepts_valid_essential():
    c = Criterion(
        id="c1",
        text="必须明确指出 ALE 方法保持网格拓扑固定",
        category="Essential",
        weight=5,
        sign="positive",
        criterion_type="factual_anchor",
    )
    assert c.weight == 5
    assert c.sign == "positive"


def test_criterion_rejects_invalid_category():
    with pytest.raises(ValidationError):
        Criterion(
            id="c1",
            text="x",
            category="Bogus",
            weight=5,
            sign="positive",
            criterion_type="factual_anchor",
        )


def test_criterion_rejects_pitfall_with_positive_sign():
    with pytest.raises(ValidationError):
        Criterion(
            id="c1",
            text="x",
            category="Pitfall",
            weight=4,
            sign="positive",
            criterion_type="anti_hacking",
        )


def test_criterion_rejects_weight_out_of_range():
    with pytest.raises(ValidationError):
        Criterion(
            id="c1",
            text="x",
            category="Essential",
            weight=99,
            sign="positive",
            criterion_type="factual_anchor",
        )


def test_rubric_item_minimal():
    item = RubricItem(
        question_id="1",
        question="什么是 ALE？",
        reference_answer="ALE 是任意拉格朗日-欧拉方法。",
        question_type="简答题",
        difficulty="简单",
        scenario="单文档单段落",
        source="Benson教材, 第1章, 第1页",
        source_grounding=SourceGrounding(
            parsed_docs=["benson"], pages=[1, 1],
            retrieved_chunk_ids=[], ground_status="page_specific",
        ),
        criteria=[
            Criterion(id="c1", text="x", category="Essential",
                      weight=5, sign="positive", criterion_type="factual_anchor"),
        ],
        rubric_metadata=RubricMetadata(
            generation_model="openai/gpt-5.4-mini",
            generation_passes=3,
            n_criteria_initial=1, n_criteria_final=1,
            n_dropped_misaligned=0,
            ref_answer_self_score=None, weak_answer_self_score=None,
            generated_at="2026-05-22T00:00:00Z",
            schema_version="1.0",
        ),
    )
    assert item.question_id == "1"


def test_rubric_item_rejects_unknown_question_type():
    with pytest.raises(ValidationError):
        RubricItem(
            question_id="1", question="x", reference_answer="y",
            question_type="奇怪题型",
            difficulty="简单", scenario="x", source="x",
            source_grounding=SourceGrounding(
                parsed_docs=[], pages=[], retrieved_chunk_ids=[],
                ground_status="fallback_semantic",
            ),
            criteria=[],
            rubric_metadata=RubricMetadata(
                generation_model="x", generation_passes=1,
                n_criteria_initial=0, n_criteria_final=0,
                n_dropped_misaligned=0,
                ref_answer_self_score=None, weak_answer_self_score=None,
                generated_at="2026-05-22T00:00:00Z", schema_version="1.0",
            ),
        )
