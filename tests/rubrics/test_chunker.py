from pathlib import Path
import pytest
from rubrics.chunker import chunk_markdown, ChunkRecord, doc_slug_from_filename


def test_doc_slug_from_filename_keeps_alnum():
    assert doc_slug_from_filename(
        "Arbitrary_Lagrangian-Eulerian_and_Fluid-Structure Interaction Numerical Simulation (Benson).md"
    ) == "Arbitrary_Lagrangian-Eulerian_and_Fluid-Structure_Interaction_Numerical_Simulation_Benson"


def test_chunk_markdown_produces_overlapping_chunks(tmp_path: Path):
    md = tmp_path / "doc.md"
    text = "一二三四五六七八九十" * 200  # 2000 chars
    md.write_text(text, encoding="utf-8")
    chunks = chunk_markdown(md, chunk_size=400, overlap=100)
    assert all(isinstance(c, ChunkRecord) for c in chunks)
    assert len(chunks) >= 4
    for c in chunks:
        assert c.doc_slug == "doc"
        assert c.chunk_id.startswith("doc:")
        assert len(c.text) <= 500  # chunk_size + slack


def test_chunk_markdown_extracts_page_from_mineru_url(tmp_path: Path):
    """mineru MDs embed page numbers in CDN image URLs as page_NNN_block_NNN."""
    md = tmp_path / "paged.md"
    md.write_text(
        "intro intro " * 50 +
        "\n![Img](https://cdn.example.com/wisdoc/images/xxx/page_004_block_001.png)\n" +
        "page-5 content " * 50 +
        "\n![Img](https://cdn.example.com/wisdoc/images/xxx/page_005_block_002.png)\n" +
        "page-6 content " * 50,
        encoding="utf-8",
    )
    chunks = chunk_markdown(md, chunk_size=400, overlap=100)
    chunk_pages = [(c.page_start, c.page_end) for c in chunks if c.page_start]
    # at least one chunk should have a non-None page (page_004 → page 5 after +1, or however you store)
    assert chunk_pages, f"No chunks have page info; chunks: {[c.chunk_id for c in chunks]}"
    # pages should include 5 or 6 (1-indexed) since the URL markers are page_004 and page_005
    seen_pages = {p for ps, pe in chunk_pages for p in (ps, pe) if p is not None}
    assert any(p >= 5 for p in seen_pages)


def test_chunk_markdown_real_cae_doc():
    """Smoke test against actual CAE-MD."""
    path = Path("/home/juli/RLM/CAE-MDs/水下爆炸冲击荷载作用下混凝土重力坝的破坏模式.md")
    if not path.exists():
        pytest.skip("CAE-MDs not present")
    chunks = chunk_markdown(path, chunk_size=400, overlap=100)
    assert len(chunks) > 1
    assert all(c.doc_slug for c in chunks)
    # Real doc should have multiple chunks with extracted pages
    chunks_with_pages = [c for c in chunks if c.page_start is not None]
    assert len(chunks_with_pages) >= 1, "Expected at least some chunks with page info from real mineru MD"
