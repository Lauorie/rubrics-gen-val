from cae_rag.ingest import Chunk
from cae_rag.react import (
    ReactConfig, parse_action, parse_final, format_search_obs, read_chunk,
)


def test_react_config_defaults_frozen():
    cfg = ReactConfig()
    assert cfg.max_steps == 6
    assert cfg.search_k == 5
    assert cfg.snippet_chars == 240
    assert cfg.read_window == 1
    assert cfg.temperature == 0.0
    try:
        cfg.max_steps = 9  # type: ignore[misc]
        assert False, "ReactConfig must be frozen"
    except Exception:
        pass


def test_parse_action_search_and_read():
    assert parse_action("Thought: x\nAction: search[附加质量]") == ("search", "附加质量")
    assert parse_action("Action: read[Benson::12]") == ("read", "Benson::12")
    # markdown-wrapped and extra whitespace
    assert parse_action("```\nAction:  search[ q ]\n```") == ("search", "q")
    # no action
    assert parse_action("Final Answer: 答案在这里") is None
    assert parse_action("我打算去查一下资料") is None


def test_parse_final():
    assert parse_final("Final Answer: 这是最终答案") == "这是最终答案"
    assert parse_final("Thought: ..\nAction: search[q]") is None
    assert parse_final("Final Answer: 多行\n第二行").startswith("多行")


def test_format_search_obs_truncates():
    hits = [{"chunk_id": "d::0", "doc": "docA", "text": "x" * 500},
            {"chunk_id": "d::1", "doc": "docB", "text": "短文本\n带换行"}]
    obs = format_search_obs(hits, snippet_chars=100)
    assert "d::0" in obs and "docA" in obs
    assert "x" * 100 in obs and "x" * 101 not in obs  # truncated to 100
    assert "\n带换行" not in obs  # newlines flattened within a pointer line
    assert format_search_obs([], 100) == "（无检索结果）"


def test_read_chunk_neighbors_and_missing():
    chunks = [Chunk(f"d::{i}", "d", f"text{i}", 0, 1) for i in range(3)]
    by_id = {c.chunk_id: c for c in chunks}
    out = read_chunk("d::1", by_id, window=1)
    assert "text0" in out and "text1" in out and "text2" in out
    edge = read_chunk("d::0", by_id, window=1)  # no d::-1
    assert "text0" in edge and "text1" in edge and "text2" not in edge
    assert read_chunk("d::99", by_id, window=1) == "未找到该 chunk_id"
