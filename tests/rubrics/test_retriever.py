import pytest
from rubrics.chunker import ChunkRecord
from rubrics.index import ChunkIndex
from rubrics.source_parser import SourceRef
from rubrics.retriever import retrieve_context


@pytest.fixture
def idx():
    chunks = [
        ChunkRecord("Arbitrary_Lagrangian-Eulerian_and_Fluid-Structure_Interaction_Numerical_Simulation_Benson:p166-p180:c0", "Arbitrary_Lagrangian-Eulerian_and_Fluid-Structure_Interaction_Numerical_Simulation_Benson", 166, 180, "附加质量效应在 FSI 中会导致不稳定"),
        ChunkRecord("Arbitrary_Lagrangian-Eulerian_and_Fluid-Structure_Interaction_Numerical_Simulation_Benson:p166-p180:c1", "Arbitrary_Lagrangian-Eulerian_and_Fluid-Structure_Interaction_Numerical_Simulation_Benson", 166, 180, "隐式分区算法的迭代过程不收敛"),
        ChunkRecord("PhD_jia:p17-p17:c0", "PhD_基于通用程序的水下爆炸及其对结构作用的数值模拟研究", 17, 17, "JWL 状态方程参数 A B R1 R2"),
    ]
    return ChunkIndex.build(chunks)


def test_retrieve_with_parsed_source(idx):
    refs = [SourceRef(doc_alias="Benson", pages=(166, 189))]
    hits, status = retrieve_context(
        question="为何附加质量效应导致不稳定？",
        refs=refs, index=idx, k=2,
    )
    assert status == "page_specific"
    assert len(hits) == 2
    assert all("Benson" in h.doc_slug or "Arbitrary" in h.doc_slug for h in hits)


def test_retrieve_falls_back_to_semantic_when_alias_unknown(idx):
    refs = []  # parser returned nothing
    hits, status = retrieve_context(
        question="JWL 状态方程参数有哪些？",
        refs=refs, index=idx, k=2,
    )
    assert status == "fallback_semantic"
    assert any("JWL" in h.text for h in hits)
