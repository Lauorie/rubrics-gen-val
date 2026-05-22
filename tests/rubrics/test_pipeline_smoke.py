import json
from rubrics.pipeline import build_rubric_for_item
from rubrics.chunker import ChunkRecord
from rubrics.index import ChunkIndex


def test_build_rubric_for_item_end_to_end(mocker):
    # Fake LLM that returns canned criteria for stage 1 then "met" judgments for stage 3
    fake_llm = mocker.Mock()
    fake_llm.complete_json.side_effect = [
        # Stage 1: initial criteria (1 positive, 1 pitfall)
        {"criteria": [
            {"id": "c1", "text": "明确解释附加质量效应导致迭代不收敛",
             "category": "Essential", "weight": 5, "sign": "positive",
             "criterion_type": "mechanism_explanation"},
        ]},
        # Stage 3: judge calls — ref met, weak not met for c1
        {"met": True, "reason": "ref says so"},
        {"met": False, "reason": "weak doesn't say"},
    ]
    chunks = [ChunkRecord("a:p1-p1:c0", "a", 1, 1, "附加质量效应是流体加速时表观增加的惯性")]
    idx = ChunkIndex.build(chunks)
    item = {
        "编号": "1",
        "问题描述": "为何附加质量效应导致数值不稳定？",
        "参考答案": "流体与结构密度接近时迭代易不收敛。",
        "题型": "主观题", "难易程度": "困难", "难度场景": "单文档多段落",
        "来源": "Benson教材, 第4章, 第166-189页", "语言": "中文",
    }
    rubric = build_rubric_for_item(
        item=item, index=idx,
        generator_client=fake_llm, judge_client=fake_llm,
        embed_fn=None,  # skip dedup in smoke test
    )
    assert rubric.question_id == "1"
    # Stage 2 injects 2 default pitfalls → final criteria ≥ 3
    assert len(rubric.criteria) >= 3
    pitfalls = [c for c in rubric.criteria if c.category == "Pitfall"]
    assert len(pitfalls) >= 2
