from cae_rag.retrieve import rrf_fuse

def test_rrf_basic_fusion():
    # dense ranks A,B,C ; sparse ranks B,A,D  (1-based rank)
    dense = ["A", "B", "C"]
    sparse = ["B", "A", "D"]
    fused = rrf_fuse(dense, sparse, k=60, top_k=5)
    # A: 1/61 + 1/62 ; B: 1/62 + 1/61  -> A and B tie, then C:1/63, D:1/63
    # A == B by score; tie-break by id asc -> A before B
    assert fused[:2] == ["A", "B"]
    assert set(fused) == {"A", "B", "C", "D"}

def test_rrf_top_k_truncation():
    dense = [f"d{i}" for i in range(10)]
    sparse = [f"s{i}" for i in range(10)]
    fused = rrf_fuse(dense, sparse, k=60, top_k=5)
    assert len(fused) == 5

def test_rrf_item_in_both_ranks_higher():
    dense = ["X", "A", "B"]
    sparse = ["Y", "A", "C"]
    fused = rrf_fuse(dense, sparse, k=60, top_k=3)
    # A appears in both (ranks 2 & 2) -> highest combined score
    assert fused[0] == "A"


from cae_rag.retrieve import HybridRetriever

class _FakeMilvus:
    def search(self, collection_name, data, limit, output_fields):
        # return chunk_ids c2, c0, c1 (ints map to chunk_ids by index)
        hits = [{"id": 2, "entity": {"chunk_id": "c2", "text": "t2", "doc": "d"}},
                {"id": 0, "entity": {"chunk_id": "c0", "text": "t0", "doc": "d"}}]
        return [hits[:limit]]

class _FakeBM25:
    def get_scores(self, tokens):
        # scores indexed by chunk position: favor c1 then c0
        return [0.5, 0.9, 0.1]

def test_hybrid_retriever_returns_top_k_chunks(monkeypatch):
    import cae_rag.retrieve as R
    monkeypatch.setattr(R.jieba, "cut", lambda q: iter(["q"]))
    r = HybridRetriever(
        milvus=_FakeMilvus(), bm25=_FakeBM25(), chunk_ids=["c0", "c1", "c2"],
        chunk_lookup={"c0": ("t0", "d"), "c1": ("t1", "d"), "c2": ("t2", "d")},
        embed_query=lambda q: [0.0, 0.0, 0.0], top_k=3, candidate_pool=2, rrf_k=60,
    )
    out = r.retrieve("question?")
    assert len(out) == 3
    assert {c["chunk_id"] for c in out} <= {"c0", "c1", "c2"}
    assert all("text" in c and "doc" in c for c in out)
