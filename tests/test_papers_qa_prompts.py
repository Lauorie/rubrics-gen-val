"""Verify the BILINGUAL_ADDENDUM style directives are present in the built prompt."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "papers_qa"))

from papers_qa.prompts import build_bilingual_system_prompt


def test_prompt_includes_no_boilerplate_directive() -> None:
    p = build_bilingual_system_prompt(num_papers=8)
    assert "不要以" in p
    assert "套话" in p
    assert "开场白" in p


def test_prompt_includes_concise_directive() -> None:
    p = build_bilingual_system_prompt(num_papers=8)
    assert "紧凑" in p or "聚焦" in p
    assert "无直接关联" in p or "无关的背景" in p


def test_prompt_includes_no_multiple_answers_directive() -> None:
    p = build_bilingual_system_prompt(num_papers=8)
    assert "不要给出多个相互矛盾" in p
