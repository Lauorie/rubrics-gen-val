"""Tests for SciArena Stage-1 generator prompt assembly."""
from __future__ import annotations

import pytest

from rubrics_sciarena.generator import build_generation_prompt, type_rule_filename


def _cits():
    return [{"content": "Finding: dropout reduces overfitting.", "title": "Dropout",
             "concise_authors": "Srivastava 2014", "id": "9@9"}]


def test_type_rule_filename_maps_known_types():
    assert type_rule_filename("Conceptual Explanation") == "conceptual_explanation.txt"
    assert type_rule_filename("Challenges & Limitations") == "challenges_limitations.txt"
    assert type_rule_filename("State-of-the-Art Assessment") == "state_of_the_art_assessment.txt"
    assert type_rule_filename("Paper Finding") == "paper_finding.txt"
    assert type_rule_filename("Methodology Inquiry") == "methodology_inquiry.txt"


def test_type_rule_filename_unknown_falls_back_to_others():
    assert type_rule_filename("Weird New Type") == "others.txt"


def test_prompt_includes_question_reference_and_citations():
    system, user = build_generation_prompt(
        question="Why does dropout help?",
        reference_answer="Dropout reduces overfitting by random co-adaptation breaking.",
        question_type="Conceptual Explanation",
        subject="ML",
        citations=_cits(),
    )
    assert "Why does dropout help?" in user
    assert "Dropout reduces overfitting" in user
    assert "Finding: dropout reduces overfitting." in user  # citation content present
    assert "Conceptual Explanation" in user


def test_prompt_system_has_schema_and_rules():
    system, user = build_generation_prompt(
        question="q", reference_answer="r", question_type="Others",
        subject="s", citations=[],
    )
    assert "weighted binary checklist" in system
    assert "criterion_type" in system


def test_prompt_embeds_matching_type_rule_text():
    _, user = build_generation_prompt(
        question="q", reference_answer="r",
        question_type="Paper Finding", subject="s", citations=[],
    )
    assert "Paper Finding question" in user  # from paper_finding.txt
