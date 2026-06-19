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


# --- FIX A: _split_compound must not cut inside words and must preserve weight ---

def test_split_does_not_cut_inside_compound_word():
    """The bare '并' splitter used to slice inside 合并/归并 etc., producing
    unjudgeable 2-4 char phantom fragments. A non-punctuation-anchored 并 must NOT split."""
    criteria = [
        {"id": "c1", "text": "提到气泡合并或分裂等拓扑结构变化",
         "category": "Essential", "weight": 5, "sign": "positive",
         "criterion_type": "factual_anchor"},
    ]
    out = refine_criteria(criteria, embed_fn=None, split_compound=True)
    content = [c for c in out if c["category"] == "Essential"]
    assert len(content) == 1, [c["text"] for c in content]
    assert content[0]["text"] == "提到气泡合并或分裂等拓扑结构变化"


def test_split_preserves_total_positive_weight():
    """Splitting one criterion of weight w into k parts must keep sum(weights)==w,
    not duplicate w onto every fragment (which inflated pos_max)."""
    criteria = [
        {"id": "c1", "text": "明确给出选择是 USA，并解释 USA 基于边界元法",
         "category": "Essential", "weight": 5, "sign": "positive",
         "criterion_type": "decision_logic"},
    ]
    out = refine_criteria(criteria, embed_fn=None, split_compound=True)
    content = [c for c in out if c["category"] == "Essential"]
    assert len(content) == 2
    assert sum(c["weight"] for c in content) == 5
    assert all(c["weight"] >= 1 for c in content)


def test_split_skips_when_fragment_too_short():
    """If a split would yield a fragment shorter than the minimum, keep the
    original criterion intact rather than emit a stub."""
    criteria = [
        {"id": "c1", "text": "明确给出最终决策，并 X", "category": "Essential",
         "weight": 5, "sign": "positive", "criterion_type": "decision_logic"},
    ]
    out = refine_criteria(criteria, embed_fn=None, split_compound=True)
    content = [c for c in out if c["category"] == "Essential"]
    assert len(content) == 1


# --- FIX C: mandatory style pitfalls carry reduced, canonical weights ---

def test_default_pitfall_weights_are_reduced():
    weights = {p["text"]: p["weight"] for p in DEFAULT_PITFALLS}
    assert weights["回答以套话/开场白/元评论开头而无实质内容"] == 3
    assert weights["回答篇幅冗长，包含大量与问题无关的背景铺垫或重复"] == 2


def test_existing_style_pitfall_weight_is_normalized_to_canonical():
    """If the generator emits a mandatory style pitfall with an off weight,
    refiner normalizes it to the canonical DEFAULT_PITFALLS weight."""
    criteria = [
        {"id": "c1", "text": "x", "category": "Essential", "weight": 5,
         "sign": "positive", "criterion_type": "factual_anchor"},
        {"id": "c2", "text": DEFAULT_PITFALLS[0]["text"], "category": "Pitfall",
         "weight": 8, "sign": "negative", "criterion_type": "anti_hacking"},
    ]
    out = refine_criteria(criteria, embed_fn=None)
    p0 = [c for c in out if c["text"] == DEFAULT_PITFALLS[0]["text"]]
    assert len(p0) == 1
    assert p0[0]["weight"] == DEFAULT_PITFALLS[0]["weight"] == 3
