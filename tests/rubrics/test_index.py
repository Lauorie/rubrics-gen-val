from pathlib import Path
import pytest
from rubrics.chunker import ChunkRecord
from rubrics.index import ChunkIndex


@pytest.fixture
def tiny_index():
    chunks = [
        ChunkRecord("a:p1-p1:c0", "a", 1, 1, "ALE 是任意拉格朗日欧拉方法，网格随材料运动"),
        ChunkRecord("a:p2-p2:c0", "a", 2, 2, "Lagrangian 方法节点与材料粒子绑定"),
        ChunkRecord("b:p10-p10:c0", "b", 10, 10, "JWL 状态方程描述爆轰产物膨胀"),
    ]
    idx = ChunkIndex.build(chunks, model_name="BAAI/bge-base-zh-v1.5")
    return idx, chunks


def test_index_build_then_search(tiny_index):
    idx, chunks = tiny_index
    hits = idx.search("什么是 ALE 方法？", k=2)
    assert len(hits) == 2
    assert hits[0].chunk_id.startswith("a:p1")


def test_index_search_within_doc_pages(tiny_index):
    idx, chunks = tiny_index
    hits = idx.search_within("JWL", k=1, doc_slug="b", pages=(10, 10))
    assert len(hits) == 1
    assert hits[0].chunk_id.startswith("b:p10")


def test_index_search_within_returns_empty_if_no_match(tiny_index):
    idx, _ = tiny_index
    hits = idx.search_within("JWL", k=1, doc_slug="a", pages=(1, 1))
    assert hits == []
