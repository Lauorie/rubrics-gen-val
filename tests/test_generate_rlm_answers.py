import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from generate_rlm_answers import load_rubrics_json, save_rubrics_json


def test_load_rubrics_json_returns_list_of_dicts(tmp_path: Path) -> None:
    p = tmp_path / "in.json"
    p.write_text(json.dumps([{"question_id": "1", "question": "Q1"}], ensure_ascii=False))
    items = load_rubrics_json(p)
    assert isinstance(items, list)
    assert items[0]["question_id"] == "1"


def test_load_rubrics_json_preserves_chinese(tmp_path: Path) -> None:
    p = tmp_path / "in.json"
    p.write_text(json.dumps([{"question_id": "1", "question": "附加质量效应"}], ensure_ascii=False))
    items = load_rubrics_json(p)
    assert items[0]["question"] == "附加质量效应"


def test_save_rubrics_json_atomic_and_chinese_safe(tmp_path: Path) -> None:
    p = tmp_path / "out.json"
    save_rubrics_json(p, [{"question_id": "1", "question": "中文问题", "rlm_answer": "答案"}])
    reread = json.loads(p.read_text())
    assert reread[0]["rlm_answer"] == "答案"
    # Atomic-rename leaves no `.tmp` siblings on success.
    assert not any(s.name.endswith(".tmp") for s in tmp_path.iterdir())


def test_save_rubrics_json_pretty_2_space_indent(tmp_path: Path) -> None:
    p = tmp_path / "out.json"
    save_rubrics_json(p, [{"a": 1}])
    expected = json.dumps([{"a": 1}], ensure_ascii=False, indent=2) + "\n"
    assert p.read_text() == expected


from generate_rlm_answers import to_inference_items


def test_to_inference_items_maps_question_id_to_id() -> None:
    rubrics = [
        {"question_id": "1", "question": "Q1", "reference_answer": "ignored"},
        {"question_id": "2", "question": "Q2"},
    ]
    items = to_inference_items(rubrics)
    assert items == [{"id": "1", "question": "Q1"}, {"id": "2", "question": "Q2"}]


def test_to_inference_items_skips_items_missing_question() -> None:
    rubrics = [
        {"question_id": "1", "question": "Q1"},
        {"question_id": "2"},  # no question — must be skipped, not crash
    ]
    items = to_inference_items(rubrics)
    assert [it["id"] for it in items] == ["1"]


def test_to_inference_items_raises_on_duplicate_id() -> None:
    import pytest as _pytest
    with _pytest.raises(ValueError, match="duplicate question_id"):
        to_inference_items([
            {"question_id": "1", "question": "Q1"},
            {"question_id": "1", "question": "Q1-dup"},
        ])


from generate_rlm_answers import merge_answers_into_rubrics


def _jsonl(tmp_path: Path, rows: list[dict[str, Any]]) -> Path:
    p = tmp_path / "answers.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")
    return p


def test_merge_attaches_rlm_answer_by_question_id(tmp_path: Path) -> None:
    rubrics = [
        {"question_id": "1", "question": "Q1", "reference_answer": "R1"},
        {"question_id": "2", "question": "Q2"},
    ]
    answers = _jsonl(tmp_path, [
        {"id": "1", "answer": "A1", "error": None},
        {"id": "2", "answer": "A2", "error": None},
    ])
    out = merge_answers_into_rubrics(rubrics, answers)
    assert out[0]["rlm_answer"] == "A1"
    assert out[0]["reference_answer"] == "R1"  # original field preserved
    assert out[1]["rlm_answer"] == "A2"


def test_merge_marks_missing_as_null(tmp_path: Path) -> None:
    rubrics = [{"question_id": "1", "question": "Q1"}, {"question_id": "2", "question": "Q2"}]
    answers = _jsonl(tmp_path, [{"id": "1", "answer": "A1", "error": None}])
    out = merge_answers_into_rubrics(rubrics, answers)
    assert out[0]["rlm_answer"] == "A1"
    assert out[1]["rlm_answer"] is None
    assert out[1]["rlm_error"] is None  # not failed, just not yet processed


def test_merge_propagates_error_string(tmp_path: Path) -> None:
    rubrics = [{"question_id": "1", "question": "Q1"}]
    answers = _jsonl(tmp_path, [{"id": "1", "answer": None, "error": "RuntimeError: boom"}])
    out = merge_answers_into_rubrics(rubrics, answers)
    assert out[0]["rlm_answer"] is None
    assert out[0]["rlm_error"] == "RuntimeError: boom"


def test_merge_last_row_wins_on_duplicate_id(tmp_path: Path) -> None:
    """JSONL append can have a failed row then a retry success — keep latest."""
    rubrics = [{"question_id": "1", "question": "Q1"}]
    answers = _jsonl(tmp_path, [
        {"id": "1", "answer": None, "error": "transient"},
        {"id": "1", "answer": "A1-retry", "error": None},
    ])
    out = merge_answers_into_rubrics(rubrics, answers)
    assert out[0]["rlm_answer"] == "A1-retry"
    assert out[0]["rlm_error"] is None


def test_merge_does_not_mutate_input(tmp_path: Path) -> None:
    rubrics = [{"question_id": "1", "question": "Q1"}]
    answers = _jsonl(tmp_path, [{"id": "1", "answer": "A", "error": None}])
    merge_answers_into_rubrics(rubrics, answers)
    assert "rlm_answer" not in rubrics[0]  # input list untouched


def test_merge_missing_answers_file_yields_all_null(tmp_path: Path) -> None:
    rubrics = [{"question_id": "1", "question": "Q1"}]
    out = merge_answers_into_rubrics(rubrics, tmp_path / "nope.jsonl")
    assert out[0]["rlm_answer"] is None
    assert out[0]["rlm_error"] is None


import sys as _sys

from generate_rlm_answers import build_env_overrides


def test_build_env_overrides_pins_papers_dir(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.invalid/v1")
    env = build_env_overrides(papers_dir=Path("/tmp/cae"))
    assert env["PAPERS_QA_PAPERS_DIR"] == "/tmp/cae"
    assert env["OPENAI_API_KEY"] == "sk-test"
    # No English-override addendum (questions are Chinese).
    assert "PAPERS_QA_SYSTEM_PROMPT_ADDENDUM" not in env
    assert env["PAPERS_QA_DISABLE_DISK_LOGGER"] == "1"


def test_build_env_overrides_requires_api_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    import pytest as _pytest
    with _pytest.raises(ValueError, match="OPENAI_API_KEY"):
        build_env_overrides(papers_dir=Path("/tmp/cae"))


def test_main_dry_run_writes_output_with_null_answers(tmp_path: Path, monkeypatch) -> None:
    """--dry-run: skip inference, just round-trip the JSON with null rlm_answer/rlm_error."""
    in_path = tmp_path / "rubrics.json"
    in_path.write_text(json.dumps(
        [{"question_id": "1", "question": "Q1", "reference_answer": "R1"}],
        ensure_ascii=False,
    ))
    out_path = tmp_path / "rubrics-out.json"
    jsonl_path = tmp_path / "answers.jsonl"
    papers = tmp_path / "papers"
    papers.mkdir()
    (papers / "a.md").write_text("x")

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setattr(_sys, "argv", [
        "generate_rlm_answers.py",
        "--input", str(in_path),
        "--output", str(out_path),
        "--jsonl", str(jsonl_path),
        "--papers-dir", str(papers),
        "--dry-run",
    ])
    from generate_rlm_answers import main
    rc = main()
    assert rc == 0
    out = json.loads(out_path.read_text())
    assert out[0]["question_id"] == "1"
    assert out[0]["reference_answer"] == "R1"
    assert out[0]["rlm_answer"] is None
    assert out[0]["rlm_error"] is None


def test_main_invokes_run_inference_with_correct_args(tmp_path, monkeypatch) -> None:
    in_path = tmp_path / "rubrics.json"
    in_path.write_text(json.dumps(
        [{"question_id": "1", "question": "Q1"},
         {"question_id": "2", "question": "Q2"}],
        ensure_ascii=False,
    ))
    out_path = tmp_path / "out.json"
    jsonl_path = tmp_path / "ans.jsonl"
    papers = tmp_path / "papers"
    papers.mkdir()
    (papers / "x.md").write_text("y")

    # Pretend inference produced two records.
    def fake_run_inference(*, items, out_path, max_workers, use_processes, env_overrides):
        assert use_processes is True
        assert env_overrides["PAPERS_QA_PAPERS_DIR"] == str(papers)
        assert max_workers == 3
        assert [it["id"] for it in items] == ["1", "2"]
        out_path.write_text(
            json.dumps({"id": "1", "answer": "A1", "error": None}) + "\n"
            + json.dumps({"id": "2", "answer": "A2", "error": None}) + "\n"
        )

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setattr(_sys, "argv", [
        "generate_rlm_answers.py",
        "--input", str(in_path),
        "--output", str(out_path),
        "--jsonl", str(jsonl_path),
        "--papers-dir", str(papers),
        "--workers", "3",
    ])
    import generate_rlm_answers as mod
    monkeypatch.setattr(mod, "run_inference", fake_run_inference)
    rc = mod.main()
    assert rc == 0
    out = json.loads(out_path.read_text())
    assert out[0]["rlm_answer"] == "A1"
    assert out[1]["rlm_answer"] == "A2"
