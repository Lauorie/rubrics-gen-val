"""Tests for turning SciArena citations into generation context."""
from __future__ import annotations

from rubrics_sciarena.pseudo_chunk import citation_grounding, format_citations_as_context


def _cits():
    return [
        {
            "content": "Thermal expansion shifts the focal length by 0.3 mm.",
            "concise_authors": "Smith et al. 2020",
            "title": "Thermal Optics",
            "authors": "John Smith",
            "id": "111@1",
        },
        {
            "content": "Off-axis aberration grows with field angle.",
            "concise_authors": "Lee 2019",
            "title": "Triplet Design",
            "authors": "Ann Lee",
            "id": "222@2",
        },
    ]


def test_format_includes_content_and_titles():
    ctx = format_citations_as_context(_cits())
    assert "Thermal expansion shifts the focal length by 0.3 mm." in ctx
    assert "Off-axis aberration grows with field angle." in ctx
    assert "Thermal Optics" in ctx
    assert "Triplet Design" in ctx


def test_format_numbers_each_source():
    ctx = format_citations_as_context(_cits())
    # Two distinct numbered source markers.
    assert "1" in ctx and "2" in ctx
    assert ctx.count("Smith et al. 2020") == 1


def test_format_empty_citations():
    ctx = format_citations_as_context([])
    assert ctx.strip() != ""  # must be a non-empty placeholder
    assert "no" in ctx.lower()


def test_format_tolerates_missing_and_nan_fields():
    bad = [{"content": "Some finding.", "title": "T", "authors": float("nan"), "id": "9@9"}]
    ctx = format_citations_as_context(bad)
    assert "Some finding." in ctx
    assert "nan" not in ctx.lower()  # NaN authors must not leak as literal text


def test_citation_grounding_collects_ids_and_titles():
    g = citation_grounding(_cits())
    assert g["citation_ids"] == ["111@1", "222@2"]
    assert g["titles"] == ["Thermal Optics", "Triplet Design"]
    assert g["n_citations"] == 2
