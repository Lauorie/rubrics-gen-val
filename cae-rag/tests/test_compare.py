from cae_rag.compare import build_comparison_md, extract_rlm_predictions

def test_build_comparison_md_has_headline_and_delta():
    rag = {"mean_anchored": 0.62, "mean_score": 0.70, "n_scored_ok": 94, "n_errors": 0,
           "by_question_type": {"主观题": {"n": 10, "mean": 0.7, "mean_anchored": 0.6}},
           "by_difficulty": {"困难": {"n": 5, "mean": 0.6, "mean_anchored": 0.5}},
           "judge_model": "openai/gpt-5.4-mini"}
    rlm = {"mean_anchored": 0.68, "mean_score": 0.74, "n_scored_ok": 94, "n_errors": 0,
           "by_question_type": {"主观题": {"n": 10, "mean": 0.75, "mean_anchored": 0.66}},
           "by_difficulty": {"困难": {"n": 5, "mean": 0.65, "mean_anchored": 0.58}},
           "judge_model": "openai/gpt-5.4-mini"}
    md = build_comparison_md(rag, rlm)
    assert "RAG" in md and "RLM v3" in md
    assert "0.62" in md and "0.68" in md
    assert "-0.06" in md or "−0.06" in md  # delta RAG - RLM
    assert "主观题" in md and "困难" in md

def test_extract_rlm_predictions():
    data = [{"item_idx": 0, "rlm_answer": "A"}, {"item_idx": 1, "rlm_answer": "B"}]
    preds = extract_rlm_predictions(data)
    assert preds == [{"item_idx": 0, "answer": "A"}, {"item_idx": 1, "answer": "B"}]

from cae_rag.compare import build_comparison_md_3way

def test_build_comparison_md_3way():
    def agg(a):
        return {"mean_anchored": a, "mean_score": a - 0.01, "n_scored_ok": 94, "n_errors": 0,
                "by_question_type": {"主观题": {"n": 10, "mean": a, "mean_anchored": a}},
                "by_difficulty": {"困难": {"n": 5, "mean": a, "mean_anchored": a}},
                "judge_model": "openai/gpt-5.4-mini"}
    rag, react, rlm = agg(0.427), agg(0.55), agg(0.675)
    md = build_comparison_md_3way(rag, react, rlm)
    assert "RAG" in md and "ReAct" in md and "RLM v3" in md
    assert "0.427" in md and "0.550" in md and "0.675" in md
    # deltas vs RLM v3 present (negative)
    assert "-0.248" in md  # RAG - RLM
    assert "-0.125" in md  # ReAct - RLM
    assert "主观题" in md and "困难" in md
