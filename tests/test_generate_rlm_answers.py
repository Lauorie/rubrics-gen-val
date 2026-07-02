import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rlm_pipeline"))

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


def test_to_inference_items_maps_id_field_to_id() -> None:
    rubrics = [
        {"item_idx": 0, "question": "Q1", "reference_answer": "ignored"},
        {"item_idx": 1, "question": "Q2"},
    ]
    items = to_inference_items(rubrics)
    assert items == [{"id": "0", "question": "Q1"}, {"id": "1", "question": "Q2"}]


def test_to_inference_items_skips_items_missing_question() -> None:
    rubrics = [
        {"item_idx": 0, "question": "Q1"},
        {"item_idx": 1},  # no question — must be skipped, not crash
    ]
    items = to_inference_items(rubrics)
    assert [it["id"] for it in items] == ["0"]


def test_to_inference_items_raises_on_duplicate_id() -> None:
    import pytest as _pytest
    with _pytest.raises(ValueError, match="duplicate item_idx"):
        to_inference_items([
            {"item_idx": 0, "question": "Q1"},
            {"item_idx": 0, "question": "Q1-dup"},
        ])


def test_to_inference_items_honors_custom_id_field() -> None:
    """Passing id_field='question_id' uses that key instead of item_idx."""
    rubrics = [{"question_id": "A", "item_idx": 0, "question": "Q1"}]
    items = to_inference_items(rubrics, id_field="question_id")
    assert items == [{"id": "A", "question": "Q1"}]


from generate_rlm_answers import merge_answers_into_rubrics


def _jsonl(tmp_path: Path, rows: list[dict[str, Any]]) -> Path:
    p = tmp_path / "answers.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")
    return p


def test_merge_attaches_rlm_answer_by_id_field(tmp_path: Path) -> None:
    rubrics = [
        {"item_idx": 0, "question": "Q1", "reference_answer": "R1"},
        {"item_idx": 1, "question": "Q2"},
    ]
    answers = _jsonl(tmp_path, [
        {"id": "0", "answer": "A1", "error": None},
        {"id": "1", "answer": "A2", "error": None},
    ])
    out = merge_answers_into_rubrics(rubrics, answers)
    assert out[0]["rlm_answer"] == "A1"
    assert out[0]["reference_answer"] == "R1"  # original field preserved
    assert out[1]["rlm_answer"] == "A2"


def test_merge_marks_missing_as_null(tmp_path: Path) -> None:
    rubrics = [{"item_idx": 0, "question": "Q1"}, {"item_idx": 1, "question": "Q2"}]
    answers = _jsonl(tmp_path, [{"id": "0", "answer": "A1", "error": None}])
    out = merge_answers_into_rubrics(rubrics, answers)
    assert out[0]["rlm_answer"] == "A1"
    assert out[1]["rlm_answer"] is None
    assert out[1]["rlm_error"] is None  # not failed, just not yet processed


def test_merge_propagates_error_string(tmp_path: Path) -> None:
    rubrics = [{"item_idx": 0, "question": "Q1"}]
    answers = _jsonl(tmp_path, [{"id": "0", "answer": None, "error": "RuntimeError: boom"}])
    out = merge_answers_into_rubrics(rubrics, answers)
    assert out[0]["rlm_answer"] is None
    assert out[0]["rlm_error"] == "RuntimeError: boom"


def test_merge_last_row_wins_on_duplicate_id(tmp_path: Path) -> None:
    """JSONL append can have a failed row then a retry success — keep latest."""
    rubrics = [{"item_idx": 0, "question": "Q1"}]
    answers = _jsonl(tmp_path, [
        {"id": "0", "answer": None, "error": "transient"},
        {"id": "0", "answer": "A1-retry", "error": None},
    ])
    out = merge_answers_into_rubrics(rubrics, answers)
    assert out[0]["rlm_answer"] == "A1-retry"
    assert out[0]["rlm_error"] is None


def test_merge_does_not_mutate_input(tmp_path: Path) -> None:
    rubrics = [{"item_idx": 0, "question": "Q1"}]
    answers = _jsonl(tmp_path, [{"id": "0", "answer": "A", "error": None}])
    merge_answers_into_rubrics(rubrics, answers)
    assert "rlm_answer" not in rubrics[0]  # input list untouched


def test_merge_missing_answers_file_yields_all_null(tmp_path: Path) -> None:
    rubrics = [{"item_idx": 0, "question": "Q1"}]
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


def test_build_env_overrides_includes_pythonpath_for_workers(monkeypatch) -> None:
    """Workers need papers_qa and rlm on PYTHONPATH (neither is pip-installed)."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    env = build_env_overrides(papers_dir=Path("/tmp/cae"))
    pp = env["PYTHONPATH"]
    assert "/papers_qa" in pp
    assert "/rlm" in pp
    # Two entries, colon-separated
    assert ":" in pp


def test_build_env_overrides_requires_api_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    import pytest as _pytest
    with _pytest.raises(ValueError, match="OPENAI_API_KEY"):
        build_env_overrides(papers_dir=Path("/tmp/cae"))


def test_main_dry_run_writes_output_with_null_answers(tmp_path: Path, monkeypatch) -> None:
    """--dry-run: skip inference, just round-trip the JSON with null rlm_answer/rlm_error."""
    in_path = tmp_path / "rubrics.json"
    in_path.write_text(json.dumps(
        [{"question_id": "1", "item_idx": 0, "question": "Q1", "reference_answer": "R1"}],
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
        [{"item_idx": 0, "question": "Q1"},
         {"item_idx": 1, "question": "Q2"}],
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
        assert [it["id"] for it in items] == ["0", "1"]
        out_path.write_text(
            json.dumps({"id": "0", "answer": "A1", "error": None}) + "\n"
            + json.dumps({"id": "1", "answer": "A2", "error": None}) + "\n"
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


def test_main_propagates_pythonpath_to_parent_env(tmp_path, monkeypatch) -> None:
    """The parent process's os.environ['PYTHONPATH'] must be set before workers spawn."""
    in_path = tmp_path / "rubrics.json"
    in_path.write_text(json.dumps([{"item_idx": 0, "question": "Q1"}], ensure_ascii=False))
    out_path = tmp_path / "out.json"
    jsonl_path = tmp_path / "ans.jsonl"
    papers = tmp_path / "papers"
    papers.mkdir()
    (papers / "x.md").write_text("y")

    captured: dict[str, str] = {}

    def fake_run_inference(*, items, out_path, max_workers, use_processes, env_overrides):
        captured["env_at_call"] = os.environ.get("PYTHONPATH", "")
        out_path.write_text(json.dumps({"id": "0", "answer": "A", "error": None}) + "\n")

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("PYTHONPATH", raising=False)
    monkeypatch.setattr(_sys, "argv", [
        "generate_rlm_answers.py",
        "--input", str(in_path), "--output", str(out_path),
        "--jsonl", str(jsonl_path), "--papers-dir", str(papers),
    ])
    import generate_rlm_answers as mod
    monkeypatch.setattr(mod, "run_inference", fake_run_inference)
    assert mod.main() == 0
    assert "/papers_qa" in captured["env_at_call"]
    assert "/rlm" in captured["env_at_call"]


def test_peek_flag_requires_workers_one(tmp_path, monkeypatch) -> None:
    """--peek-map-out with --workers > 1 must error before any LLM call."""
    in_path = tmp_path / "rubrics.json"
    in_path.write_text(json.dumps([{"item_idx": 0, "question": "Q", "rlm_answer": None}], ensure_ascii=False))
    papers = tmp_path / "papers"; papers.mkdir(); (papers / "x.md").write_text("y")

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setattr(_sys, "argv", [
        "generate_rlm_answers.py",
        "--input", str(in_path),
        "--output", str(tmp_path / "out.json"),
        "--jsonl", str(tmp_path / "ans.jsonl"),
        "--papers-dir", str(papers),
        "--workers", "4",
        "--peek-map-out", str(tmp_path / "map.json"),
    ])
    import generate_rlm_answers as mod
    import pytest as _pytest
    with _pytest.raises(SystemExit):
        mod.main()


def test_peek_flag_runs_serial_with_single_policy(tmp_path, monkeypatch) -> None:
    """--peek-map-out causes serial execution and a single shared CachePolicy."""
    in_path = tmp_path / "rubrics.json"
    in_path.write_text(json.dumps(
        [{"item_idx": 0, "question": "Q0", "rlm_answer": None},
         {"item_idx": 1, "question": "Q1", "rlm_answer": None}],
        ensure_ascii=False,
    ))
    out_path = tmp_path / "out.json"
    jsonl_path = tmp_path / "ans.jsonl"
    map_path = tmp_path / "map.json"
    papers = tmp_path / "papers"; papers.mkdir(); (papers / "x.md").write_text("y")

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.invalid/v1")

    captured: dict[str, Any] = {}

    class FakePapersQA:
        def __init__(self, cfg, *, peek_policy=None):
            captured.setdefault("policies", []).append(peek_policy)
            self.peek_policy = peek_policy
        def ask(self, question):
            captured.setdefault("questions", []).append(question)
            from papers_qa.runner import AskResult
            return AskResult(question=question, answer="A", cost_usd=None,
                             duration_s=0.0, trajectory=None)

    saved_paths: list[str] = []
    class FakePolicy:
        current_map_text = "## CONTEXT ROADMAP\n"
        evolving = True
        def update(self, **kw): return None
        def save(self, p): saved_paths.append(str(p))

    def fake_build_policy(cfg, client=None):
        return FakePolicy()

    monkeypatch.setattr(_sys, "argv", [
        "generate_rlm_answers.py",
        "--input", str(in_path),
        "--output", str(out_path),
        "--jsonl", str(jsonl_path),
        "--papers-dir", str(papers),
        "--workers", "1",
        "--peek-map-out", str(map_path),
    ])
    import generate_rlm_answers as mod
    monkeypatch.setattr(mod, "PapersQA", FakePapersQA)
    monkeypatch.setattr(mod, "build_peek_policy", fake_build_policy)

    assert mod.main() == 0
    assert len(captured["policies"]) == 1
    assert captured["questions"] == ["Q0", "Q1"]
    assert saved_paths


def test_include_items_range_filter(tmp_path, monkeypatch) -> None:
    """--include-items '0-1' processes only item_idx 0 and 1."""
    in_path = tmp_path / "rubrics.json"
    in_path.write_text(json.dumps(
        [{"item_idx": i, "question": f"Q{i}", "rlm_answer": None} for i in range(5)],
        ensure_ascii=False,
    ))
    papers = tmp_path / "papers"; papers.mkdir(); (papers / "x.md").write_text("y")
    out_path = tmp_path / "out.json"; jsonl_path = tmp_path / "ans.jsonl"

    captured = {"questions": []}
    class FakePQ:
        def __init__(self, cfg, *, peek_policy=None): pass
        def ask(self, q):
            captured["questions"].append(q)
            from papers_qa.runner import AskResult
            return AskResult(question=q, answer="A", cost_usd=None, duration_s=0, trajectory=None)

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setattr(_sys, "argv", [
        "generate_rlm_answers.py",
        "--input", str(in_path), "--output", str(out_path), "--jsonl", str(jsonl_path),
        "--papers-dir", str(papers), "--workers", "1",
        "--include-items", "0-1",
        "--peek-map-out", str(tmp_path / "map.json"),
    ])
    import generate_rlm_answers as mod
    monkeypatch.setattr(mod, "PapersQA", FakePQ)
    class FakePolicy:
        current_map_text = ""
        evolving = True
        def update(self, **k): pass
        def save(self, p): pass
    monkeypatch.setattr(mod, "build_peek_policy", lambda cfg, client=None: FakePolicy())
    assert mod.main() == 0
    assert captured["questions"] == ["Q0", "Q1"]


def test_skip_items_filter(tmp_path, monkeypatch) -> None:
    """--skip-items '1,3' excludes those item_idxs."""
    in_path = tmp_path / "rubrics.json"
    in_path.write_text(json.dumps(
        [{"item_idx": i, "question": f"Q{i}", "rlm_answer": None} for i in range(5)],
        ensure_ascii=False,
    ))
    papers = tmp_path / "papers"; papers.mkdir(); (papers / "x.md").write_text("y")
    out_path = tmp_path / "out.json"; jsonl_path = tmp_path / "ans.jsonl"
    captured = {"questions": []}
    class FakePQ:
        def __init__(self, cfg, *, peek_policy=None): pass
        def ask(self, q):
            captured["questions"].append(q)
            from papers_qa.runner import AskResult
            return AskResult(question=q, answer="A", cost_usd=None, duration_s=0, trajectory=None)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setattr(_sys, "argv", [
        "generate_rlm_answers.py",
        "--input", str(in_path), "--output", str(out_path), "--jsonl", str(jsonl_path),
        "--papers-dir", str(papers), "--workers", "1",
        "--skip-items", "1,3",
        "--peek-map-out", str(tmp_path / "map.json"),
    ])
    import generate_rlm_answers as mod
    monkeypatch.setattr(mod, "PapersQA", FakePQ)
    class FakePolicy:
        current_map_text = ""
        evolving = True
        def update(self, **k): pass
        def save(self, p): pass
    monkeypatch.setattr(mod, "build_peek_policy", lambda cfg, client=None: FakePolicy())
    assert mod.main() == 0
    assert captured["questions"] == ["Q0", "Q2", "Q4"]


def test_peek_map_in_allows_workers_gt_one(tmp_path, monkeypatch) -> None:
    """--peek-map-in + workers>1 must NOT error (since no live PEEK)."""
    in_path = tmp_path / "rubrics.json"
    in_path.write_text(json.dumps([{"item_idx": 0, "question": "Q", "rlm_answer": None}], ensure_ascii=False))
    papers = tmp_path / "papers"; papers.mkdir(); (papers / "x.md").write_text("y")
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps({"map_text": "## ROADMAP\n[r-0] hi\n", "scores": {}, "steps": 30, "token_budget": 1024, "evolve_steps": 30}))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.invalid/v1")
    captured = {}
    def fake_run_inference(*, items, out_path, max_workers, use_processes, env_overrides):
        captured["env"] = env_overrides
        out_path.write_text(json.dumps({"id": "0", "answer": "A", "error": None}) + "\n")
    monkeypatch.setattr(_sys, "argv", [
        "generate_rlm_answers.py",
        "--input", str(in_path), "--output", str(tmp_path / "out.json"), "--jsonl", str(tmp_path / "ans.jsonl"),
        "--papers-dir", str(papers), "--workers", "4",
        "--peek-map-in", str(map_path),
    ])
    import generate_rlm_answers as mod
    monkeypatch.setattr(mod, "run_inference", fake_run_inference)
    assert mod.main() == 0
    # frozen map text was injected into addendum env var, brace-escaped
    assert "PAPERS_QA_SYSTEM_PROMPT_ADDENDUM" in captured["env"]
    addendum = captured["env"]["PAPERS_QA_SYSTEM_PROMPT_ADDENDUM"]
    assert "## ROADMAP" in addendum
    assert "[r-0] hi" in addendum


def test_peek_distiller_addendum_preset_decisions(tmp_path, monkeypatch) -> None:
    """--peek-distiller-addendum-preset decisions threads the addendum through to PeekCfg."""
    in_path = tmp_path / "rubrics.json"
    in_path.write_text(json.dumps([{"item_idx": 0, "question": "Q", "rlm_answer": None}], ensure_ascii=False))
    papers = tmp_path / "papers"; papers.mkdir(); (papers / "x.md").write_text("y")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.invalid/v1")
    captured_cfg = {}
    class FakePolicy:
        current_map_text = ""
        evolving = True
        def update(self, **k): pass
        def save(self, p): pass
    def fake_build(cfg, client=None):
        captured_cfg["cfg"] = cfg
        return FakePolicy()
    class FakePQ:
        def __init__(self, cfg, *, peek_policy=None): pass
        def ask(self, q):
            from papers_qa.runner import AskResult
            return AskResult(question=q, answer="A", cost_usd=None, duration_s=0, trajectory=None)
    monkeypatch.setattr(_sys, "argv", [
        "generate_rlm_answers.py",
        "--input", str(in_path), "--output", str(tmp_path / "out.json"), "--jsonl", str(tmp_path / "ans.jsonl"),
        "--papers-dir", str(papers), "--workers", "1",
        "--peek-map-out", str(tmp_path / "map.json"),
        "--peek-distiller-addendum-preset", "decisions",
    ])
    import generate_rlm_answers as mod
    monkeypatch.setattr(mod, "build_peek_policy", fake_build)
    monkeypatch.setattr(mod, "PapersQA", FakePQ)
    assert mod.main() == 0
    assert captured_cfg["cfg"].distiller_addendum is not None
    assert "canonical" in captured_cfg["cfg"].distiller_addendum.lower()
