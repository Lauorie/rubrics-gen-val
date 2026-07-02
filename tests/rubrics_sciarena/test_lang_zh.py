"""Tests for Chinese-language rubric generation support."""
from __future__ import annotations

import pytest

from rubrics_sciarena.generator import _TYPE_RULE_FILES, build_generation_prompt
from rubrics_sciarena.lang import default_pitfalls, template_dir, weak_answer
from rubrics_sciarena.refiner import refine_criteria


def test_weak_answer_zh():
    assert weak_answer("zh") == "我不知道。"
    assert weak_answer("en") == "I don't know."


def test_unsupported_lang_raises():
    with pytest.raises(ValueError):
        weak_answer("fr")


def test_default_pitfalls_zh_are_chinese():
    pits = default_pitfalls("zh")
    assert len(pits) == 2
    assert all(any("一" <= ch <= "鿿" for ch in p["text"]) for p in pits)
    assert all(p["sign"] == "negative" for p in pits)


def test_refiner_injects_chinese_pitfalls():
    out = refine_criteria(
        [{"text": "指出某事实", "category": "Essential", "weight": 5,
          "sign": "positive", "criterion_type": "factual_anchor"}],
        embed_fn=None, lang="zh",
    )
    pitfalls = [c for c in out if c["category"] == "Pitfall"]
    assert len(pitfalls) == 2
    assert any("套话" in p["text"] for p in pitfalls)


def test_zh_generation_prompt_uses_chinese_system_and_labels():
    system, user = build_generation_prompt(
        question="为什么 dropout 有帮助？",
        reference_answer="dropout 通过随机失活打破共适应，从而减少过拟合。",
        question_type="Conceptual Explanation",
        subject="机器学习",
        citations=[{"content": "English source text.", "title": "T", "id": "1@1"}],
        lang="zh",
    )
    assert "weighted binary checklist" in system  # kept term
    assert "中文" in system  # instruction to write criteria in Chinese
    assert "[问题]" in user
    assert "[标准答案]" in user
    assert "为什么 dropout 有帮助？" in user
    # English citation content is preserved as-is in the context block
    assert "English source text." in user


def test_all_zh_type_rules_exist():
    zh = template_dir("zh")
    for fname in _TYPE_RULE_FILES.values():
        assert (zh / "type_rules" / fname).exists(), fname
