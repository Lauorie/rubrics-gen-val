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
