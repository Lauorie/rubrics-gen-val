"""Tests for papers_qa.peek_integration — pure helpers, no real LLM."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "papers_qa"))

from papers_qa.peek_integration import (
    PeekCfg,
    build_peek_policy,
    completion_to_trajectory,
)


def test_peekcfg_defaults() -> None:
    cfg = PeekCfg()
    assert cfg.token_budget == 1024
    assert cfg.evolve_steps == 30
    assert cfg.distiller_model == "deepseek/deepseek-v4-flash"
    assert cfg.trajectory_max_chars == 12000


def test_build_peek_policy_with_explicit_client() -> None:
    """build_peek_policy accepts a pre-built LMClient and returns a CachePolicy."""
    from peek import CachePolicy

    stub = MagicMock()
    stub.completion.return_value = "stub response"
    cfg = PeekCfg(token_budget=512, evolve_steps=5)
    policy = build_peek_policy(cfg, client=stub)
    assert isinstance(policy, CachePolicy)
    assert policy.token_budget == 512
    assert policy.evolve_steps == 5


def test_build_peek_policy_from_env(monkeypatch) -> None:
    """When no client passed, build one from OPENAI_API_KEY/OPENAI_BASE_URL."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.invalid/v1")
    cfg = PeekCfg(distiller_model="openai/gpt-5.4-mini")
    policy = build_peek_policy(cfg)
    assert policy.client.model == "openai/gpt-5.4-mini"


def test_completion_to_trajectory_handles_none_metadata() -> None:
    """If completion.metadata is None, return just the final answer."""
    c = MagicMock()
    c.metadata = None
    c.response = "最终答案: A"
    s = completion_to_trajectory(c)
    assert "最终答案: A" in s
    assert "[Final answer]" in s


def test_completion_to_trajectory_flattens_iterations() -> None:
    """Each iteration's response/code/output appears in the trajectory string, in order."""
    c = MagicMock()
    c.metadata = {
        "iterations": [
            {"response": "I'll search for X", "code": "search('X')", "output": "found 3"},
            {"response": "Reading paper 1", "code": "llm_query(paper1)", "output": "details..."},
        ],
        "run_metadata": {"model": "deepseek"},
    }
    c.response = "X is Y because Z"
    s = completion_to_trajectory(c)
    assert s.find("I'll search for X") < s.find("Reading paper 1")
    assert "search('X')" in s
    assert "found 3" in s
    assert "X is Y because Z" in s
    assert "[Final answer]" in s


def test_completion_to_trajectory_truncates_to_max_chars() -> None:
    """Very long trajectories are hard-truncated at the configured limit."""
    c = MagicMock()
    big = "x" * 50000
    c.metadata = {"iterations": [{"response": big, "code": "", "output": ""}],
                  "run_metadata": {}}
    c.response = "tail"
    s = completion_to_trajectory(c, max_chars=500)
    assert len(s) <= 500 + 200  # allow a small header overhead
    assert "tail" in s  # final answer must always appear


def test_completion_to_trajectory_handles_missing_keys() -> None:
    """Missing 'code' or 'output' in an iteration shouldn't crash."""
    c = MagicMock()
    c.metadata = {"iterations": [{"response": "thinking"}], "run_metadata": {}}
    c.response = "answer"
    s = completion_to_trajectory(c)
    assert "thinking" in s
    assert "answer" in s


def test_build_peek_policy_requires_api_key_or_client(monkeypatch) -> None:
    """Without OPENAI_API_KEY and no client, build_peek_policy raises."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    import pytest as _pytest
    with _pytest.raises((KeyError, ValueError)):
        build_peek_policy(PeekCfg())
