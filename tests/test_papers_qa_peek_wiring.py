"""Verify PapersQA.ask wires the PEEK policy correctly."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "papers_qa"))


@pytest.fixture
def tiny_corpus(tmp_path, monkeypatch):
    p = tmp_path / "papers"
    p.mkdir()
    (p / "TinyPaper_2026.md").write_text("Tiny content.")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("PAPERS_QA_MODEL", "google/gemini-3.1-flash-lite")
    monkeypatch.setenv("PAPERS_QA_PAPERS_DIR", str(p))
    return p


def test_papersqa_accepts_none_peek_policy_noop(tiny_corpus):
    """peek_policy=None must be the default and a complete no-op."""
    from papers_qa.config import PapersQAConfig
    from papers_qa.runner import PapersQA
    cfg = PapersQAConfig.from_env()
    qa = PapersQA(cfg)  # no peek_policy kwarg
    assert qa.peek_policy is None
    assert "## CONTEXT ROADMAP" not in qa.rlm.system_prompt  # no map prepended


def test_papersqa_prepends_map_when_policy_provided(tiny_corpus, monkeypatch):
    """When peek_policy is set, ask() must prepend the policy's current map."""
    from papers_qa.config import PapersQAConfig
    from papers_qa.runner import PapersQA
    cfg = PapersQAConfig.from_env()

    fake_policy = MagicMock()
    fake_policy.current_map_text = "## CONTEXT ROADMAP\n[mock-1] sample item\n"
    fake_policy.update = MagicMock(return_value=None)

    qa = PapersQA(cfg, peek_policy=fake_policy)

    fake_completion = MagicMock()
    fake_completion.response = "答案"
    fake_completion.metadata = {"iterations": [], "run_metadata": {}}
    fake_completion.usage_summary = None
    fake_completion.execution_time = 1.23
    qa.rlm.completion = MagicMock(return_value=fake_completion)

    qa.ask("测试问题")
    # The policy's map text appears in the system prompt at ask time.
    assert "## CONTEXT ROADMAP" in qa.rlm.system_prompt
    assert "[mock-1] sample item" in qa.rlm.system_prompt


def test_papersqa_calls_policy_update_after_completion(tiny_corpus, monkeypatch):
    """ask() must call policy.update exactly once per ask, with trajectory + question."""
    from papers_qa.config import PapersQAConfig
    from papers_qa.runner import PapersQA
    cfg = PapersQAConfig.from_env()

    fake_policy = MagicMock()
    fake_policy.current_map_text = "## CONTEXT ROADMAP\n"
    fake_policy.update = MagicMock(return_value=None)

    qa = PapersQA(cfg, peek_policy=fake_policy)

    fake_completion = MagicMock()
    fake_completion.response = "final answer"
    fake_completion.metadata = {"iterations": [{"response": "thinking"}], "run_metadata": {}}
    fake_completion.usage_summary = None
    fake_completion.execution_time = 1.0
    qa.rlm.completion = MagicMock(return_value=fake_completion)

    qa.ask("Q1")
    assert fake_policy.update.call_count == 1
    _, kwargs = fake_policy.update.call_args
    assert kwargs["question"] == "Q1"
    assert "final answer" in kwargs["trajectory"]
    assert "thinking" in kwargs["trajectory"]


def test_papersqa_brace_escapes_peek_map_to_avoid_format_crash(tiny_corpus, monkeypatch):
    """PEEK map text with literal {} must not crash RLM's downstream str.format."""
    from papers_qa.config import PapersQAConfig
    from papers_qa.runner import PapersQA
    cfg = PapersQAConfig.from_env()

    fake_policy = MagicMock()
    # A map containing braces — common in PEEK output (e.g. item-id references).
    fake_policy.current_map_text = "[roadmap-{-1}] foo\n[const-1] bar = {x}\n"
    fake_policy.update = MagicMock(return_value=None)

    qa = PapersQA(cfg, peek_policy=fake_policy)
    fake_completion = MagicMock()
    fake_completion.response = "ans"
    fake_completion.metadata = {"iterations": [], "run_metadata": {}}
    fake_completion.usage_summary = None
    fake_completion.execution_time = 0.1
    qa.rlm.completion = MagicMock(return_value=fake_completion)
    qa.ask("Q1")

    # In the mutated system_prompt, every original `{` must be doubled.
    assert "{{-1}}" in qa.rlm.system_prompt
    assert "{{x}}" in qa.rlm.system_prompt
    # And ZERO un-doubled single braces from the PEEK map should survive.
    # (The base system prompt may contain other braces — we only check the map region.)
    map_region = qa.rlm.system_prompt.split("================ Context Map (PEEK) ================\n", 1)[1]
    map_region = map_region.split("================ End of Context Map ================", 1)[0]
    # Every `{` and `}` in the map region must be doubled.
    assert "{{" in map_region and "}}" in map_region
    # No lone `{` followed by a non-`{` (that would be a format placeholder).
    import re
    assert re.search(r"(?<!\{)\{(?!\{)", map_region) is None
    assert re.search(r"(?<!\})\}(?!\})", map_region) is None
