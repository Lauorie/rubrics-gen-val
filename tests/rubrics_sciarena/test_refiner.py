"""Tests for the SciArena Stage-2 refiner (English)."""
from __future__ import annotations

from rubrics_sciarena.refiner import DEFAULT_PITFALLS, refine_criteria


def _c(text, category="Essential", sign="positive", ctype="factual_anchor", weight=5):
    return {"text": text, "category": category, "weight": weight, "sign": sign,
            "criterion_type": ctype}


def test_appends_default_pitfalls_when_absent():
    out = refine_criteria([_c("Mentions the 0.3 mm focal shift")], embed_fn=None)
    pitfalls = [c for c in out if c["category"] == "Pitfall"]
    assert len(pitfalls) == len(DEFAULT_PITFALLS)
    assert all(p["sign"] == "negative" for p in pitfalls)
    assert all(p["criterion_type"] == "anti_hacking" for p in pitfalls)


def test_does_not_duplicate_existing_pitfall():
    existing = dict(DEFAULT_PITFALLS[0])
    out = refine_criteria([_c("A"), existing], embed_fn=None)
    texts = [c["text"] for c in out if c["category"] == "Pitfall"]
    assert texts.count(DEFAULT_PITFALLS[0]["text"]) == 1


def test_renumbers_sequentially():
    out = refine_criteria([_c("A"), _c("B"), _c("C")], embed_fn=None)
    assert [c["id"] for c in out] == [f"c{i+1}" for i in range(len(out))]


def test_does_not_split_english_and_by_default():
    # "and" is ubiquitous in English; a single criterion must stay intact.
    text = "Explains thermal expansion and the resulting focal shift"
    out = refine_criteria([_c(text)], embed_fn=None)
    positives = [c for c in out if c["category"] != "Pitfall"]
    assert len(positives) == 1
    assert positives[0]["text"] == text


def test_default_pitfalls_are_english():
    for p in DEFAULT_PITFALLS:
        # heuristic: no CJK characters in the SciArena pitfalls
        assert all(not ("一" <= ch <= "鿿") for ch in p["text"])


def test_default_pitfall_weights_are_reduced():
    # The two mandatory style pitfalls use the reduced 3/2 weights (v3.0 audit).
    assert [p["weight"] for p in DEFAULT_PITFALLS] == [3, 2]


def test_normalizes_emitted_pitfall_weight_to_canonical():
    # A generator-emitted copy of a mandatory pitfall carrying a stale weight (4)
    # is normalized back to the canonical reduced weight (3), not duplicated.
    emitted = {**DEFAULT_PITFALLS[0], "weight": 4}
    out = refine_criteria([_c("A"), emitted], embed_fn=None)
    match = [c for c in out if c["text"] == DEFAULT_PITFALLS[0]["text"]]
    assert len(match) == 1
    assert match[0]["weight"] == 3
