import json
from pathlib import Path
import pytest
from rubrics.generator import generate_initial_rubric


def test_generate_initial_rubric_calls_llm_with_typed_template(mocker):
    fake_client = mocker.Mock()
    fake_client.complete_json.return_value = {
        "criteria": [
            {"id": "c1", "text": "明确指出 X", "category": "Essential",
             "weight": 5, "sign": "positive", "criterion_type": "factual_anchor"},
            {"id": "c2", "text": "回答以套话开头", "category": "Pitfall",
             "weight": 4, "sign": "negative", "criterion_type": "anti_hacking"},
        ]
    }
    out = generate_initial_rubric(
        question="什么是 ALE？",
        reference_answer="ALE 是任意拉格朗日-欧拉方法。",
        question_type="简答题",
        difficulty="简单",
        source="Benson教材",
        retrieved_chunks=[],
        client=fake_client,
    )
    assert len(out) == 2
    args, kwargs = fake_client.complete_json.call_args
    # template-rule for 简答题 must appear in user message
    assert "简答题" in kwargs["user"]


def test_generate_initial_rubric_passes_chunks_into_prompt(mocker):
    from rubrics.chunker import ChunkRecord
    fake_client = mocker.Mock()
    fake_client.complete_json.return_value = {"criteria": []}
    chunks = [ChunkRecord("a:p1-p1:c0", "a", 1, 1, "这是源文档的一段内容")]
    generate_initial_rubric(
        question="x", reference_answer="y", question_type="简答题",
        difficulty="简单", source="x", retrieved_chunks=chunks, client=fake_client,
    )
    args, kwargs = fake_client.complete_json.call_args
    assert "这是源文档的一段内容" in kwargs["user"]
