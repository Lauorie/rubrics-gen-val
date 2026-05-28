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
