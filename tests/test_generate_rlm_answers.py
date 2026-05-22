import json
import sys
from pathlib import Path

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
