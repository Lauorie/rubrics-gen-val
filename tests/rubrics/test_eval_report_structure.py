"""End-to-end structure verification of a real eval_*.json report file.

Skipped if no real report exists. Runs after `python run/04_score_predictions.py`.
"""
import json
from pathlib import Path
import pytest


REPORT = Path("/home/juli/RLM/data/eval_sample.json")


@pytest.mark.skipif(not REPORT.exists(), reason="eval_sample.json not generated yet")
def test_report_has_required_top_level_keys():
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    assert set(report.keys()) >= {"per_candidate", "aggregate"}


@pytest.mark.skipif(not REPORT.exists(), reason="eval_sample.json not generated yet")
def test_per_candidate_records_well_formed():
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    for r in report["per_candidate"]:
        assert "item_idx" in r
        if r.get("score") is not None:
            assert 0.0 <= r["score"] <= 1.0
            assert "breakdown" in r
            for b in r["breakdown"]:
                assert "id" in b and "category" in b and "met" in b
                assert "contribution" in b


@pytest.mark.skipif(not REPORT.exists(), reason="eval_sample.json not generated yet")
def test_aggregate_has_required_subreports():
    agg = json.loads(REPORT.read_text(encoding="utf-8"))["aggregate"]
    for key in ["n_predictions", "n_scored_ok", "n_errors",
                "mean_score", "by_question_type", "by_difficulty", "by_criterion_type"]:
        assert key in agg, f"missing aggregate key: {key}"
