import numpy as np
from rubrics.refiner import refine_criteria, DEFAULT_PITFALLS


def test_refine_injects_default_pitfalls_when_missing():
    criteria = [
        {"id": "c1", "text": "x", "category": "Essential", "weight": 5,
         "sign": "positive", "criterion_type": "factual_anchor"},
    ]
    out = refine_criteria(criteria, embed_fn=None)
    pitfall_texts = [c["text"] for c in out if c["category"] == "Pitfall"]
    assert DEFAULT_PITFALLS[0]["text"] in pitfall_texts
    assert DEFAULT_PITFALLS[1]["text"] in pitfall_texts


def test_refine_does_not_duplicate_existing_pitfalls():
    criteria = [
        {"id": "c1", "text": DEFAULT_PITFALLS[0]["text"], "category": "Pitfall",
         "weight": 4, "sign": "negative", "criterion_type": "anti_hacking"},
        {"id": "c2", "text": DEFAULT_PITFALLS[1]["text"], "category": "Pitfall",
         "weight": 3, "sign": "negative", "criterion_type": "anti_hacking"},
    ]
    out = refine_criteria(criteria, embed_fn=None)
    pitfalls = [c for c in out if c["category"] == "Pitfall"]
    assert len(pitfalls) == 2


def test_refine_dedupes_near_duplicates_via_embedding():
    criteria = [
        {"id": "c1", "text": "明确指出 ALE 方法保持网格随材料运动",
         "category": "Essential", "weight": 5, "sign": "positive",
         "criterion_type": "factual_anchor"},
        {"id": "c2", "text": "明确指出 ALE 方法的网格随材料运动",
         "category": "Essential", "weight": 5, "sign": "positive",
         "criterion_type": "factual_anchor"},
    ]
    # Mock embedder that returns near-identical vectors for the two
    def embed_fn(texts):
        return np.array([[1.0, 0.0], [0.99, 0.01], [0.0, 1.0], [0.0, 1.0]][: len(texts)])

    out = refine_criteria(criteria, embed_fn=embed_fn)
    essentials = [c for c in out if c["category"] == "Essential"]
    assert len(essentials) == 1


def test_refine_splits_compound_criterion():
    criteria = [
        {"id": "c1", "text": "明确给出选择是 USA，并解释 USA 基于边界元法",
         "category": "Essential", "weight": 5, "sign": "positive",
         "criterion_type": "decision_logic"},
    ]
    out = refine_criteria(criteria, embed_fn=None, split_compound=True)
    essential_decisions = [c for c in out if c["category"] == "Essential"]
    # The compound is split into ≥ 2 atomic criteria
    assert len(essential_decisions) >= 2
