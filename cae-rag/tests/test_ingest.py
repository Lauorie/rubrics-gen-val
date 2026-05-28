import tiktoken
from cae_rag.ingest import clean_markdown, chunk_text, Chunk

ENC = tiktoken.get_encoding("cl100k_base")

def test_clean_strips_image_lines():
    raw = "# Title\n![Image](https://x/y.png)\nreal body text\n**\n more text"
    cleaned = clean_markdown(raw)
    assert "![Image]" not in cleaned
    assert "https://x/y.png" not in cleaned
    assert "# Title" in cleaned
    assert "real body text" in cleaned

def test_chunk_sizes_and_overlap():
    # 1100 tokens of a repeating ascii word -> deterministic token count
    text = "alpha " * 1100  # ~1100 tokens
    chunks = chunk_text(text, doc="d", chunk_size=512, overlap=64)
    # step = 512 - 64 = 448 ; windows starting at 0,448,896 -> 3 windows
    assert len(chunks) == 3
    for c in chunks[:-1]:
        assert len(ENC.encode(c.text)) == 512
    # overlap: last 64 tokens of chunk0 == first 64 tokens of chunk1
    t0 = ENC.encode(chunks[0].text)
    t1 = ENC.encode(chunks[1].text)
    assert t0[-64:] == t1[:64]

def test_chunk_ids_unique_and_doc_tagged():
    chunks = chunk_text("beta " * 600, doc="mydoc", chunk_size=512, overlap=64)
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))
    assert all(c.doc == "mydoc" for c in chunks)
    assert all(c.chunk_id.startswith("mydoc::") for c in chunks)
