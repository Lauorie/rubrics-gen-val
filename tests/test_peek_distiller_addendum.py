"""Tests for the PEEK distiller addendum mechanism."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "papers_qa"))

from papers_qa.peek_integration import (
    DISTILLER_DECISIONS_ADDENDUM,
    PeekCfg,
    build_peek_policy,
)


def test_decisions_addendum_mentions_canonical_decisions() -> None:
    """The decisions preset addendum must explicitly invite canonical-answer caching."""
    assert "canonical" in DISTILLER_DECISIONS_ADDENDUM.lower() or "decision" in DISTILLER_DECISIONS_ADDENDUM.lower()
    assert "reusable_results" in DISTILLER_DECISIONS_ADDENDUM
    assert "exception" in DISTILLER_DECISIONS_ADDENDUM.lower()  # acknowledges override


def test_peekcfg_has_distiller_addendum_field() -> None:
    cfg = PeekCfg(distiller_addendum="hello")
    assert cfg.distiller_addendum == "hello"
    assert PeekCfg().distiller_addendum is None  # default


def test_build_peek_policy_with_addendum_patches_distiller_prompt() -> None:
    """When PeekCfg.distiller_addendum is set, policy._distiller.prompt includes it."""
    stub = MagicMock()
    stub.completion.return_value = "stub"
    cfg = PeekCfg(distiller_addendum="EXTRA DIRECTIVE XYZ123")
    policy = build_peek_policy(cfg, client=stub)
    assert "EXTRA DIRECTIVE XYZ123" in policy._distiller.prompt
    # The original prompt is still there (we appended, not replaced)
    assert "context map" in policy._distiller.prompt.lower()


def test_build_peek_policy_without_addendum_uses_default_prompt() -> None:
    """When distiller_addendum is None (default), the distiller prompt is unmodified."""
    stub = MagicMock()
    stub.completion.return_value = "stub"
    cfg = PeekCfg()
    policy = build_peek_policy(cfg, client=stub)
    assert "EXTRA DIRECTIVE" not in policy._distiller.prompt
