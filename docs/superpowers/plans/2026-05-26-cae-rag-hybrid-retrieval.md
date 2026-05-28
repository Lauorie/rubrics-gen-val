# CAE-RAG Hybrid-Retrieval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a hybrid-retrieval (dense + BM25, RRF top-5) RAG over the 8 `CAE-MDs` documents, answer the 94-question CAE benchmark with `deepseek/deepseek-v4-flash`, and compare its `mean_anchored` score against a re-scored RLM v3 baseline under the identical `cae-rubrics-eval` judge.

**Architecture:** A self-contained `cae-rag/` Python package. Pipeline: ingest+chunk (512 tok) → index (Milvus Lite dense + rank-bm25 sparse) → retrieve (RRF fuse top-5) → generate → score both RAG and RLM v3 via the existing `cae-rubrics-eval/score.py` → comparison report. Generation model and source documents are identical to the RLM run, so the only variable is retrieval method.

**Tech Stack:** Python 3.12 (3.11 fallback), pymilvus (Milvus Lite), openai SDK (aiberm OpenAI-compatible proxy), tiktoken, jieba, rank-bm25, pytest, tenacity, python-dotenv.

---

## Reference facts (verified against the repo)

- **Questions source:** `/home/juli/RLM/data/CAE-v2.0-1-rubrics.json` — read ONLY `item_idx` (int) and `question` (str). NEVER read `reference_answer`/`criteria`/`source_grounding` (cheating).
- **RLM v3 answers:** `/home/juli/RLM/data/CAE-v2.0-1-rubrics-v3.json` — each item has `item_idx` (int) and `rlm_answer` (str).
- **Scorer CLI:** `cae-rubrics-eval/score.py --predictions <jsonl> --out <json>`. It calls `load_dotenv()` (reads `cae-rubrics-eval/.env`: `LLM_API_KEY`, `LLM_BASE_URL=https://aiberm.com/v1`, `LLM_MODEL=openai/gpt-5.4-mini`), defaults `--rubrics` to its own bundled `data/CAE-v2.0-1-rubrics.json` and `--anchors` to `data/CAE-anchor-scores.json` (both `gpt-5.4-mini`). Run it from inside `cae-rubrics-eval/` using `cae-rubrics-eval/.venv/bin/python` so its `.env` and installed package resolve.
- **Predictions format:** JSONL, one `{"item_idx": int, "answer": str}` per line. Extra fields ignored.
- **eval.json shape:** `{"per_candidate": [...], "aggregate": {...}}`. `aggregate` keys: `n_predictions, n_scored_ok, n_errors, mean_score, mean_anchored, by_question_type{qt:{n,mean,mean_anchored}}, by_difficulty{d:{n,mean,mean_anchored}}, by_criterion_type{ct:{n_criteria,met_rate}}, judge_model, rubric_version, scored_at, elapsed_seconds`.
- **Embeddings/generation:** OpenAI-compatible at `https://aiberm.com/v1`. Embedding `openai/text-embedding-3-small` (dim 1536); generation `deepseek/deepseek-v4-flash`. API key from `.env`.

---

## File Structure

```
cae-rag/
├── pyproject.toml                 # package metadata + deps
├── .env.example                   # credential template
├── .env                           # real creds (gitignored)
├── .gitignore                     # .env, .venv, outputs/, *.db
├── cae_rag/
│   ├── __init__.py                # __all__ public API
│   ├── config.py                  # frozen Config dataclass, env load, set_seed
│   ├── ingest.py                  # clean_markdown, chunk_text, load_and_chunk
│   ├── index.py                   # embed_texts, build_milvus, build_bm25, load_*
│   ├── retrieve.py                # rrf_fuse (pure), HybridRetriever
│   ├── generate.py                # build_prompt, generate_answer, generate_all
│   └── compare.py                 # load_aggregate, build_comparison_md
├── scripts/
│   ├── build_index.py             # CLI: ingest + index → outputs/{chunks.jsonl,cae_rag.db,bm25.pkl}
│   ├── run_rag.py                 # CLI: retrieve + generate → outputs/predictions.jsonl
│   └── compare_results.py         # CLI: score RAG + RLM v3 → outputs/comparison.md
├── tests/
│   ├── test_config.py
│   ├── test_ingest.py
│   ├── test_retrieve.py
│   ├── test_generate.py
│   └── test_compare.py
└── outputs/                       # gitignored run artifacts
```

All paths below are relative to `/home/juli/RLM/` unless absolute. Work inside `cae-rag/` with its own venv `cae-rag/.venv`.

---

## Task 1: Scaffold + environment + Milvus Lite smoke test

De-risk the single riskiest dependency (milvus-lite on Python 3.12) before writing any feature code.

**Files:**
- Create: `cae-rag/pyproject.toml`, `cae-rag/.gitignore`, `cae-rag/.env.example`, `cae-rag/.env`, `cae-rag/cae_rag/__init__.py`, `cae-rag/scripts/_smoke_milvus.py`

- [ ] **Step 1: Create the package directory and metadata**

Create `cae-rag/pyproject.toml`:

```toml
[project]
name = "cae-rag"
version = "0.1.0"
description = "Hybrid-retrieval RAG over CAE-MDs, scored with cae-rubrics-eval"
requires-python = ">=3.11"
dependencies = [
    "pymilvus>=2.4.2",
    "milvus-lite>=2.4.0",
    "openai>=1.40",
    "tiktoken>=0.7",
    "jieba>=0.42",
    "rank-bm25>=0.2.2",
    "tenacity>=8.2",
    "python-dotenv>=1.0",
    "numpy>=1.26",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[tool.setuptools.packages.find]
include = ["cae_rag*"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"
```

Create `cae-rag/.gitignore`:

```
.venv/
.env
outputs/
__pycache__/
*.pyc
*.db
*.db.lock
```

Create `cae-rag/.env.example`:

```
LLM_API_KEY=
LLM_BASE_URL=https://aiberm.com/v1
EMBEDDING_MODEL=openai/text-embedding-3-small
GEN_MODEL=deepseek/deepseek-v4-flash
```

Create `cae-rag/.env` (real creds from the task spec):

```
LLM_API_KEY=sk-HTwWz6Sl51dX5i8MkH8luYoqBdTHcqzfraGaXTrWNBbbDEMG
LLM_BASE_URL=https://aiberm.com/v1
EMBEDDING_MODEL=openai/text-embedding-3-small
GEN_MODEL=deepseek/deepseek-v4-flash
```

Create empty `cae-rag/cae_rag/__init__.py` (populate `__all__` in later tasks):

```python
"""CAE-RAG: hybrid-retrieval RAG over CAE-MDs."""
__all__: list[str] = []
```

- [ ] **Step 2: Create venv and install (Python 3.12, fallback 3.11)**

Run:
```bash
cd /home/juli/RLM/cae-rag && python3.12 -m venv .venv && .venv/bin/pip install -U pip && .venv/bin/pip install -e ".[dev]"
```
Expected: installs cleanly, including `milvus-lite`. If `milvus-lite` has no wheel for 3.12, redo with `python3.11 -m venv .venv` (cae-rubrics-eval's README uses 3.11) and reinstall. Record which interpreter succeeded.

- [ ] **Step 3: Write a Milvus Lite smoke script**

Create `cae-rag/scripts/_smoke_milvus.py`:

```python
"""One-shot check that Milvus Lite works on this machine."""
from pymilvus import MilvusClient

def main() -> None:
    client = MilvusClient("outputs/_smoke.db")
    client.create_collection(collection_name="smoke", dimension=4, metric_type="COSINE", auto_id=False)
    client.insert("smoke", [
        {"id": 0, "vector": [0.1, 0.2, 0.3, 0.4], "text": "a", "doc": "d1"},
        {"id": 1, "vector": [0.9, 0.8, 0.7, 0.6], "text": "b", "doc": "d2"},
    ])
    res = client.search("smoke", data=[[0.1, 0.2, 0.3, 0.4]], limit=2, output_fields=["text", "doc"])
    print("OK", [(h["id"], h["entity"]["text"]) for h in res[0]])

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the smoke test**

Run:
```bash
cd /home/juli/RLM/cae-rag && mkdir -p outputs && .venv/bin/python scripts/_smoke_milvus.py
```
Expected: prints `OK [(0, 'a'), (1, 'b')]` (nearest first). Confirms create/insert/search + dynamic fields (`text`, `doc`) work. Then `rm outputs/_smoke.db`.

- [ ] **Step 5: Commit**

```bash
cd /home/juli/RLM && git add cae-rag/pyproject.toml cae-rag/.gitignore cae-rag/.env.example cae-rag/cae_rag/__init__.py cae-rag/scripts/_smoke_milvus.py && git commit -m "feat(cae-rag): scaffold package + Milvus Lite smoke test"
```
(Note: `cae-rag/.env` is gitignored — do not commit it.)

---

## Task 2: config.py — frozen config, env load, seed

**Files:**
- Create: `cae-rag/cae_rag/config.py`
- Test: `cae-rag/tests/test_config.py`

- [ ] **Step 1: Write the failing test**

Create `cae-rag/tests/test_config.py`:

```python
import os
import random
import numpy as np
from cae_rag.config import Config, set_seed

def test_config_from_env(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_BASE_URL", "https://aiberm.com/v1")
    monkeypatch.setenv("EMBEDDING_MODEL", "openai/text-embedding-3-small")
    monkeypatch.setenv("GEN_MODEL", "deepseek/deepseek-v4-flash")
    cfg = Config.from_env()
    assert cfg.api_key == "sk-test"
    assert cfg.embedding_model == "openai/text-embedding-3-small"
    assert cfg.gen_model == "deepseek/deepseek-v4-flash"
    assert cfg.chunk_size == 512
    assert cfg.chunk_overlap == 64
    assert cfg.top_k == 5
    assert cfg.rrf_k == 60
    assert cfg.candidate_pool == 20

def test_config_is_frozen():
    cfg = Config(api_key="x", base_url="u", embedding_model="e", gen_model="g")
    try:
        cfg.chunk_size = 999  # type: ignore[misc]
        assert False, "Config must be frozen"
    except Exception:
        pass

def test_set_seed_is_deterministic():
    set_seed(42)
    a = (random.random(), float(np.random.rand()))
    set_seed(42)
    b = (random.random(), float(np.random.rand()))
    assert a == b
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/juli/RLM/cae-rag && .venv/bin/python -m pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'cae_rag.config'`.

- [ ] **Step 3: Write config.py**

Create `cae-rag/cae_rag/config.py`:

```python
"""Immutable run configuration + seeding."""
from __future__ import annotations
import os
import random
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Config:
    api_key: str
    base_url: str
    embedding_model: str
    gen_model: str
    chunk_size: int = 512
    chunk_overlap: int = 64
    top_k: int = 5
    rrf_k: int = 60
    candidate_pool: int = 20
    embed_dim: int = 1536
    gen_temperature: float = 0.0
    seed: int = 42

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            api_key=os.environ["LLM_API_KEY"],
            base_url=os.environ.get("LLM_BASE_URL", "https://aiberm.com/v1"),
            embedding_model=os.environ.get("EMBEDDING_MODEL", "openai/text-embedding-3-small"),
            gen_model=os.environ.get("GEN_MODEL", "deepseek/deepseek-v4-flash"),
        )


def set_seed(seed: int = 42) -> None:
    """Set random seeds for reproducibility."""
    random.seed(seed)
    np.random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/juli/RLM/cae-rag && .venv/bin/python -m pytest tests/test_config.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd /home/juli/RLM && git add cae-rag/cae_rag/config.py cae-rag/tests/test_config.py && git commit -m "feat(cae-rag): immutable Config + set_seed"
```

---

## Task 3: ingest.py — cleaning + 512-token chunking

**Files:**
- Create: `cae-rag/cae_rag/ingest.py`
- Test: `cae-rag/tests/test_ingest.py`

- [ ] **Step 1: Write the failing test**

Create `cae-rag/tests/test_ingest.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/juli/RLM/cae-rag && .venv/bin/python -m pytest tests/test_ingest.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'cae_rag.ingest'`.

- [ ] **Step 3: Write ingest.py**

Create `cae-rag/cae_rag/ingest.py`:

```python
"""Load CAE markdown docs, clean, and chunk into 512-token windows."""
from __future__ import annotations
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import tiktoken

logger = logging.getLogger(__name__)

_ENC = tiktoken.get_encoding("cl100k_base")
_IMG_LINE = re.compile(r"^\s*!\[.*?\]\(.*?\)\s*$", re.MULTILINE)
_ARTIFACT_LINE = re.compile(r"^\s*\*{1,2}\s*$", re.MULTILINE)
_MULTI_BLANK = re.compile(r"\n{3,}")


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc: str
    text: str
    token_start: int
    token_end: int


def clean_markdown(raw: str) -> str:
    """Drop image lines and standalone artifact lines; collapse blank runs."""
    text = _IMG_LINE.sub("", raw)
    text = _ARTIFACT_LINE.sub("", text)
    text = _MULTI_BLANK.sub("\n\n", text)
    return text.strip()


def chunk_text(text: str, doc: str, chunk_size: int = 512, overlap: int = 64) -> list[Chunk]:
    """Sliding-window chunk by token count. step = chunk_size - overlap."""
    toks = _ENC.encode(text)
    if not toks:
        return []
    step = chunk_size - overlap
    chunks: list[Chunk] = []
    idx = 0
    for start in range(0, len(toks), step):
        window = toks[start : start + chunk_size]
        chunks.append(
            Chunk(
                chunk_id=f"{doc}::{idx}",
                doc=doc,
                text=_ENC.decode(window),
                token_start=start,
                token_end=start + len(window),
            )
        )
        idx += 1
        if start + chunk_size >= len(toks):
            break
    return chunks


def load_and_chunk(docs_dir: Path, chunk_size: int = 512, overlap: int = 64) -> list[Chunk]:
    """Load every .md under docs_dir, clean, chunk. doc name = file stem."""
    all_chunks: list[Chunk] = []
    for md_path in sorted(Path(docs_dir).glob("*.md")):
        cleaned = clean_markdown(md_path.read_text(encoding="utf-8"))
        doc_chunks = chunk_text(cleaned, doc=md_path.stem, chunk_size=chunk_size, overlap=overlap)
        logger.info("Chunked %s -> %d chunks", md_path.name, len(doc_chunks))
        all_chunks.extend(doc_chunks)
    logger.info("Total chunks: %d from %s", len(all_chunks), docs_dir)
    return all_chunks
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/juli/RLM/cae-rag && .venv/bin/python -m pytest tests/test_ingest.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd /home/juli/RLM && git add cae-rag/cae_rag/ingest.py cae-rag/tests/test_ingest.py && git commit -m "feat(cae-rag): markdown cleaning + 512-token chunking"
```

---

## Task 4: retrieve.py — RRF fusion (pure function first)

**Files:**
- Create: `cae-rag/cae_rag/retrieve.py` (rrf_fuse only in this task)
- Test: `cae-rag/tests/test_retrieve.py`

- [ ] **Step 1: Write the failing test**

Create `cae-rag/tests/test_retrieve.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/juli/RLM/cae-rag && .venv/bin/python -m pytest tests/test_retrieve.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'cae_rag.retrieve'`.

- [ ] **Step 3: Write rrf_fuse in retrieve.py**

Create `cae-rag/cae_rag/retrieve.py` (HybridRetriever added in Task 6):

```python
"""Hybrid retrieval: dense (Milvus) + sparse (BM25) fused with RRF."""
from __future__ import annotations
import logging
from collections import defaultdict
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def rrf_fuse(dense_ranked: list[T], sparse_ranked: list[T], k: int = 60, top_k: int = 5) -> list[T]:
    """Reciprocal Rank Fusion. rank is 1-based: contribution = 1/(k + rank).

    Ties broken by the natural sort order of the id (deterministic).
    """
    scores: dict[T, float] = defaultdict(float)
    for rank, cid in enumerate(dense_ranked, start=1):
        scores[cid] += 1.0 / (k + rank)
    for rank, cid in enumerate(sparse_ranked, start=1):
        scores[cid] += 1.0 / (k + rank)
    ordered = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    return [cid for cid, _ in ordered[:top_k]]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/juli/RLM/cae-rag && .venv/bin/python -m pytest tests/test_retrieve.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd /home/juli/RLM && git add cae-rag/cae_rag/retrieve.py cae-rag/tests/test_retrieve.py && git commit -m "feat(cae-rag): RRF fusion (pure function)"
```

---

## Task 5: index.py — embeddings, Milvus Lite, BM25

Integration-heavy; unit-test only the embedding-batching glue with a mocked client. Real indexing is validated in Task 8.

**Files:**
- Create: `cae-rag/cae_rag/index.py`
- Test: `cae-rag/tests/test_index.py`

- [ ] **Step 1: Write the failing test (mocked embeddings batching)**

Create `cae-rag/tests/test_index.py`:

```python
from cae_rag.index import embed_texts

class _FakeEmb:
    def __init__(self, dim): self.dim = dim; self.calls = []
    def create(self, model, input):
        self.calls.append(list(input))
        class _D:  # mimic openai response
            def __init__(self, v): self.embedding = v
        class _R:
            pass
        r = _R(); r.data = [_D([float(len(t))] * self.dim) for t in input]
        return r

class _FakeClient:
    def __init__(self, dim): self.embeddings = _FakeEmb(dim)

def test_embed_texts_batches_and_orders():
    client = _FakeClient(dim=3)
    texts = [f"t{i}" for i in range(5)]
    vecs = embed_texts(client, texts, model="m", batch_size=2)
    assert len(vecs) == 5
    assert all(len(v) == 3 for v in vecs)
    # 3 batches for 5 items at batch_size 2
    assert len(client.embeddings.calls) == 3
    # order preserved: vec i corresponds to text i (len("t0")==2 -> [2,2,2])
    assert vecs[0] == [2.0, 2.0, 2.0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/juli/RLM/cae-rag && .venv/bin/python -m pytest tests/test_index.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'cae_rag.index'`.

- [ ] **Step 3: Write index.py**

Create `cae-rag/cae_rag/index.py`:

```python
"""Build and load the dense (Milvus Lite) and sparse (BM25) indexes."""
from __future__ import annotations
import json
import logging
import pickle
from pathlib import Path
from typing import Any

import jieba
from openai import OpenAI
from pymilvus import MilvusClient
from rank_bm25 import BM25Okapi

from cae_rag.ingest import Chunk

logger = logging.getLogger(__name__)

COLLECTION = "cae_chunks"


def make_openai_client(api_key: str, base_url: str) -> OpenAI:
    return OpenAI(api_key=api_key, base_url=base_url)


def embed_texts(client: Any, texts: list[str], model: str, batch_size: int = 64) -> list[list[float]]:
    """Embed texts in batches, preserving input order."""
    vecs: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        resp = client.embeddings.create(model=model, input=batch)
        vecs.extend(d.embedding for d in resp.data)
        logger.info("Embedded %d/%d", min(i + batch_size, len(texts)), len(texts))
    return vecs


def build_milvus(db_path: str, chunks: list[Chunk], vectors: list[list[float]], dim: int) -> None:
    """(Re)create the Milvus Lite collection and insert chunk vectors."""
    client = MilvusClient(db_path)
    if client.has_collection(COLLECTION):
        client.drop_collection(COLLECTION)
    client.create_collection(collection_name=COLLECTION, dimension=dim, metric_type="COSINE", auto_id=False)
    rows = [
        {"id": i, "vector": vectors[i], "text": c.text, "doc": c.doc, "chunk_id": c.chunk_id}
        for i, c in enumerate(chunks)
    ]
    client.insert(COLLECTION, rows)
    logger.info("Inserted %d vectors into Milvus Lite at %s", len(rows), db_path)


def build_bm25(chunks: list[Chunk], pkl_path: str) -> None:
    """Tokenize chunks with jieba and pickle a BM25Okapi index + chunk order."""
    tokenized = [list(jieba.cut(c.text)) for c in chunks]
    bm25 = BM25Okapi(tokenized)
    payload = {"bm25": bm25, "chunk_ids": [c.chunk_id for c in chunks]}
    Path(pkl_path).write_bytes(pickle.dumps(payload))
    logger.info("Built BM25 over %d chunks -> %s", len(chunks), pkl_path)


def save_chunks(chunks: list[Chunk], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c.__dict__, ensure_ascii=False) + "\n")


def load_chunks(path: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            chunks.append(Chunk(**json.loads(line)))
    return chunks


def load_bm25(pkl_path: str) -> tuple[BM25Okapi, list[str]]:
    payload = pickle.loads(Path(pkl_path).read_bytes())
    return payload["bm25"], payload["chunk_ids"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/juli/RLM/cae-rag && .venv/bin/python -m pytest tests/test_index.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
cd /home/juli/RLM && git add cae-rag/cae_rag/index.py cae-rag/tests/test_index.py && git commit -m "feat(cae-rag): dense (Milvus Lite) + BM25 index build/load"
```

---

## Task 6: retrieve.py — HybridRetriever

**Files:**
- Modify: `cae-rag/cae_rag/retrieve.py` (add HybridRetriever)
- Test: `cae-rag/tests/test_retrieve.py` (add a retriever test with fakes)

- [ ] **Step 1: Write the failing test**

Append to `cae-rag/tests/test_retrieve.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/juli/RLM/cae-rag && .venv/bin/python -m pytest tests/test_retrieve.py::test_hybrid_retriever_returns_top_k_chunks -v`
Expected: FAIL with `ImportError: cannot import name 'HybridRetriever'`.

- [ ] **Step 3: Add HybridRetriever to retrieve.py**

Append to `cae-rag/cae_rag/retrieve.py`:

```python
import jieba
import numpy as np

from cae_rag.index import COLLECTION


class HybridRetriever:
    """Dense (Milvus) + sparse (BM25) retrieval fused with RRF, returns top-k chunks."""

    def __init__(self, milvus, bm25, chunk_ids, chunk_lookup, embed_query,
                 top_k=5, candidate_pool=20, rrf_k=60):
        self.milvus = milvus
        self.bm25 = bm25
        self.chunk_ids = chunk_ids
        self.chunk_lookup = chunk_lookup  # chunk_id -> (text, doc)
        self.embed_query = embed_query
        self.top_k = top_k
        self.candidate_pool = candidate_pool
        self.rrf_k = rrf_k

    def _dense(self, query: str) -> list[str]:
        qv = self.embed_query(query)
        res = self.milvus.search(
            collection_name=COLLECTION, data=[qv],
            limit=self.candidate_pool, output_fields=["chunk_id", "text", "doc"],
        )
        return [h["entity"]["chunk_id"] for h in res[0]]

    def _sparse(self, query: str) -> list[str]:
        tokens = list(jieba.cut(query))
        scores = self.bm25.get_scores(tokens)
        order = np.argsort(scores)[::-1][: self.candidate_pool]
        return [self.chunk_ids[i] for i in order]

    def retrieve(self, query: str) -> list[dict]:
        dense_ids = self._dense(query)
        sparse_ids = self._sparse(query)
        fused = rrf_fuse(dense_ids, sparse_ids, k=self.rrf_k, top_k=self.top_k)
        out = []
        for cid in fused:
            text, doc = self.chunk_lookup[cid]
            out.append({"chunk_id": cid, "text": text, "doc": doc})
        return out
```

- [ ] **Step 4: Run all retrieve tests**

Run: `cd /home/juli/RLM/cae-rag && .venv/bin/python -m pytest tests/test_retrieve.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
cd /home/juli/RLM && git add cae-rag/cae_rag/retrieve.py cae-rag/tests/test_retrieve.py && git commit -m "feat(cae-rag): HybridRetriever (dense+BM25+RRF top-5)"
```

---

## Task 7: generate.py — answer generation

**Files:**
- Create: `cae-rag/cae_rag/generate.py`
- Test: `cae-rag/tests/test_generate.py`

- [ ] **Step 1: Write the failing test**

Create `cae-rag/tests/test_generate.py`:

```python
from cae_rag.generate import build_prompt, generate_answer

def test_build_prompt_includes_question_and_chunks():
    chunks = [{"chunk_id": "d::0", "text": "context-A", "doc": "docX"},
              {"chunk_id": "d::1", "text": "context-B", "doc": "docY"}]
    system, user = build_prompt("为什么会失稳?", chunks)
    assert "仅" in system or "资料" in system  # grounded-only instruction present
    assert "为什么会失稳?" in user
    assert "context-A" in user and "context-B" in user
    assert "docX" in user and "docY" in user

def test_generate_answer_uses_client(monkeypatch):
    class _Msg: content = "  生成的答案  "
    class _Choice: message = _Msg()
    class _Resp: choices = [_Choice()]
    class _Chat:
        def __init__(self): self.kwargs = None
        def create(self, **kw): self.kwargs = kw; return _Resp()
    class _Completions:
        def __init__(self): self.completions = _Chat()
    class _Client:
        def __init__(self): self.chat = _Completions()
    client = _Client()
    chunks = [{"chunk_id": "d::0", "text": "ctx", "doc": "docX"}]
    ans = generate_answer(client, "问题?", chunks, model="deepseek/deepseek-v4-flash", temperature=0.0)
    assert ans == "生成的答案"
    assert client.chat.completions.kwargs["model"] == "deepseek/deepseek-v4-flash"
    assert client.chat.completions.kwargs["temperature"] == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/juli/RLM/cae-rag && .venv/bin/python -m pytest tests/test_generate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'cae_rag.generate'`.

- [ ] **Step 3: Write generate.py**

Create `cae-rag/cae_rag/generate.py`:

```python
"""Generate grounded answers from retrieved chunks with deepseek-v4-flash."""
from __future__ import annotations
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "你是 CAE / 工程仿真领域专家。请严格依据下面提供的资料回答用户问题。"
    "只能使用资料中的信息，不得编造；若资料不足以回答，请明确说明资料中没有相关内容。"
    "回答使用中文，准确、聚焦，保留关键公式、数值与对比。"
)


def build_prompt(question: str, chunks: list[dict]) -> tuple[str, str]:
    """Return (system, user). user embeds the retrieved context + the question."""
    blocks = []
    for i, c in enumerate(chunks, 1):
        blocks.append(f"【资料{i} | 来源:{c['doc']}】\n{c['text']}")
    context = "\n\n".join(blocks)
    user = f"以下是检索到的资料：\n\n{context}\n\n----\n问题：{question}\n\n请基于以上资料作答。"
    return SYSTEM_PROMPT, user


def generate_answer(client: Any, question: str, chunks: list[dict], model: str,
                    temperature: float = 0.0) -> str:
    system, user = build_prompt(question, chunks)
    resp = client.chat.completions.create(
        model=model, temperature=temperature,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    return resp.choices[0].message.content.strip()


def generate_all(client: Any, items: list[dict], retriever: Any, model: str,
                 temperature: float = 0.0, max_workers: int = 8) -> list[dict]:
    """items: [{item_idx, question}]. Returns [{item_idx, answer, retrieved}] sorted by item_idx."""
    def _one(item: dict) -> dict:
        try:
            chunks = retriever.retrieve(item["question"])
            answer = generate_answer(client, item["question"], chunks, model, temperature)
            return {"item_idx": item["item_idx"], "answer": answer,
                    "retrieved": [c["chunk_id"] for c in chunks]}
        except Exception as e:  # noqa: BLE001 - record per-item failure, keep going
            logger.error("item %s failed: %s", item["item_idx"], e)
            return {"item_idx": item["item_idx"], "answer": "", "error": str(e)}

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        results = list(ex.map(_one, items))
    results.sort(key=lambda r: r["item_idx"])
    return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/juli/RLM/cae-rag && .venv/bin/python -m pytest tests/test_generate.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
cd /home/juli/RLM && git add cae-rag/cae_rag/generate.py cae-rag/tests/test_generate.py && git commit -m "feat(cae-rag): grounded answer generation (deepseek-v4-flash)"
```

---

## Task 8: scripts/build_index.py — ingest + index the real KB

**Files:**
- Create: `cae-rag/scripts/build_index.py`

- [ ] **Step 1: Write build_index.py**

Create `cae-rag/scripts/build_index.py`:

```python
"""CLI: ingest CAE-MDs, embed, build Milvus Lite + BM25 indexes."""
from __future__ import annotations
import argparse
import hashlib
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cae_rag.config import Config, set_seed
from cae_rag.index import build_bm25, build_milvus, embed_texts, make_openai_client, save_chunks
from cae_rag.ingest import load_and_chunk

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")
logger = logging.getLogger("build_index")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--docs-dir", default="/home/juli/RLM/CAE-MDs", type=Path)
    p.add_argument("--out-dir", default="outputs", type=Path)
    args = p.parse_args()

    load_dotenv()
    set_seed(42)
    cfg = Config.from_env()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    chunks = load_and_chunk(args.docs_dir, cfg.chunk_size, cfg.chunk_overlap)
    save_chunks(chunks, str(args.out_dir / "chunks.jsonl"))

    client = make_openai_client(cfg.api_key, cfg.base_url)
    vectors = embed_texts(client, [c.text for c in chunks], cfg.embedding_model)
    assert len(vectors[0]) == cfg.embed_dim, f"embed dim {len(vectors[0])} != {cfg.embed_dim}"

    build_milvus(str(args.out_dir / "cae_rag.db"), chunks, vectors, cfg.embed_dim)
    build_bm25(chunks, str(args.out_dir / "bm25.pkl"))

    manifest = hashlib.sha256(
        "".join(c.chunk_id + c.text for c in chunks).encode("utf-8")
    ).hexdigest()[:12]
    (args.out_dir / "run_meta.json").write_text(
        json.dumps({"n_chunks": len(chunks), "embed_dim": cfg.embed_dim,
                    "chunk_manifest_sha": manifest, "embedding_model": cfg.embedding_model},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Index built: %d chunks, manifest %s", len(chunks), manifest)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it on the real knowledge base**

Run:
```bash
cd /home/juli/RLM/cae-rag && .venv/bin/python scripts/build_index.py
```
Expected: logs per-doc chunk counts for all 8 docs, "Embedded N/N", "Inserted N vectors", "Built BM25 over N chunks", and a final manifest line. Produces `outputs/chunks.jsonl`, `outputs/cae_rag.db`, `outputs/bm25.pkl`, `outputs/run_meta.json`. N expected ~800–1400.

- [ ] **Step 3: Sanity-check the artifacts**

Run:
```bash
cd /home/juli/RLM/cae-rag && .venv/bin/python -c "
from cae_rag.index import load_chunks, load_bm25
c = load_chunks('outputs/chunks.jsonl'); print('chunks', len(c))
bm, ids = load_bm25('outputs/bm25.pkl'); print('bm25 docs', len(ids)); assert len(ids)==len(c)
import json; print(json.load(open('outputs/run_meta.json')))
"
```
Expected: chunk count == bm25 doc count, prints run_meta. No assertion error.

- [ ] **Step 4: Commit**

```bash
cd /home/juli/RLM && git add cae-rag/scripts/build_index.py && git commit -m "feat(cae-rag): build_index CLI (ingest+embed+Milvus+BM25)"
```
(`outputs/` is gitignored — artifacts are not committed.)

---

## Task 9: scripts/run_rag.py — answer the 94 questions

**Files:**
- Create: `cae-rag/scripts/run_rag.py`

- [ ] **Step 1: Write run_rag.py**

Create `cae-rag/scripts/run_rag.py`:

```python
"""CLI: load indexes, retrieve+generate answers for the 94 questions -> predictions.jsonl."""
from __future__ import annotations
import argparse
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv
from pymilvus import MilvusClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cae_rag.config import Config, set_seed
from cae_rag.generate import generate_all
from cae_rag.index import COLLECTION, load_bm25, load_chunks, make_openai_client
from cae_rag.retrieve import HybridRetriever

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")
logger = logging.getLogger("run_rag")


def load_questions(path: Path) -> list[dict]:
    """Read ONLY item_idx + question. Never reference_answer/criteria (anti-cheat)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return [{"item_idx": r["item_idx"], "question": r["question"]} for r in data]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", default="/home/juli/RLM/data/CAE-v2.0-1-rubrics.json", type=Path)
    p.add_argument("--out-dir", default="outputs", type=Path)
    p.add_argument("--limit", type=int, default=0, help="0 = all; N = first N items (smoke test)")
    p.add_argument("--workers", type=int, default=8)
    args = p.parse_args()

    load_dotenv()
    set_seed(42)
    cfg = Config.from_env()

    chunks = load_chunks(str(args.out_dir / "chunks.jsonl"))
    chunk_lookup = {c.chunk_id: (c.text, c.doc) for c in chunks}
    bm25, chunk_ids = load_bm25(str(args.out_dir / "bm25.pkl"))
    milvus = MilvusClient(str(args.out_dir / "cae_rag.db"))
    client = make_openai_client(cfg.api_key, cfg.base_url)

    def embed_query(q: str) -> list[float]:
        return client.embeddings.create(model=cfg.embedding_model, input=[q]).data[0].embedding

    retriever = HybridRetriever(
        milvus=milvus, bm25=bm25, chunk_ids=chunk_ids, chunk_lookup=chunk_lookup,
        embed_query=embed_query, top_k=cfg.top_k, candidate_pool=cfg.candidate_pool, rrf_k=cfg.rrf_k,
    )

    items = load_questions(args.dataset)
    if args.limit:
        items = items[: args.limit]
    logger.info("Answering %d questions", len(items))

    results = generate_all(client, items, retriever, cfg.gen_model, cfg.gen_temperature, args.workers)

    out_path = args.out_dir / "predictions.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps({"item_idx": r["item_idx"], "answer": r["answer"],
                                "retrieved": r.get("retrieved", [])}, ensure_ascii=False) + "\n")
    n_empty = sum(1 for r in results if not r["answer"])
    logger.info("Wrote %d predictions to %s (%d empty/errored)", len(results), out_path, n_empty)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke run on 3 questions**

Run:
```bash
cd /home/juli/RLM/cae-rag && .venv/bin/python scripts/run_rag.py --limit 3
```
Expected: "Answering 3 questions", "Wrote 3 predictions ... (0 empty/errored)". Inspect `outputs/predictions.jsonl` — 3 lines, each with a non-empty Chinese `answer` and a `retrieved` list of 5 chunk_ids.

- [ ] **Step 3: Verify no reference leakage**

Run:
```bash
cd /home/juli/RLM/cae-rag && grep -c "reference_answer\|criteria" scripts/run_rag.py
```
Expected: `0` (the loader only ever touches `item_idx` and `question`).

- [ ] **Step 4: Commit**

```bash
cd /home/juli/RLM && git add cae-rag/scripts/run_rag.py && git commit -m "feat(cae-rag): run_rag CLI (retrieve+generate -> predictions.jsonl)"
```

---

## Task 10: compare.py + scripts/compare_results.py — score both, build report

**Files:**
- Create: `cae-rag/cae_rag/compare.py`
- Create: `cae-rag/scripts/compare_results.py`
- Test: `cae-rag/tests/test_compare.py`

- [ ] **Step 1: Write the failing test for compare.py**

Create `cae-rag/tests/test_compare.py`:

```python
from cae_rag.compare import build_comparison_md, extract_rlm_predictions

def test_build_comparison_md_has_headline_and_delta():
    rag = {"mean_anchored": 0.62, "mean_score": 0.70, "n_scored_ok": 94, "n_errors": 0,
           "by_question_type": {"主观题": {"n": 10, "mean": 0.7, "mean_anchored": 0.6}},
           "by_difficulty": {"困难": {"n": 5, "mean": 0.6, "mean_anchored": 0.5}},
           "judge_model": "openai/gpt-5.4-mini"}
    rlm = {"mean_anchored": 0.68, "mean_score": 0.74, "n_scored_ok": 94, "n_errors": 0,
           "by_question_type": {"主观题": {"n": 10, "mean": 0.75, "mean_anchored": 0.66}},
           "by_difficulty": {"困难": {"n": 5, "mean": 0.65, "mean_anchored": 0.58}},
           "judge_model": "openai/gpt-5.4-mini"}
    md = build_comparison_md(rag, rlm)
    assert "RAG" in md and "RLM v3" in md
    assert "0.62" in md and "0.68" in md
    assert "-0.06" in md or "−0.06" in md  # delta RAG - RLM
    assert "主观题" in md and "困难" in md

def test_extract_rlm_predictions():
    data = [{"item_idx": 0, "rlm_answer": "A"}, {"item_idx": 1, "rlm_answer": "B"}]
    preds = extract_rlm_predictions(data)
    assert preds == [{"item_idx": 0, "answer": "A"}, {"item_idx": 1, "answer": "B"}]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/juli/RLM/cae-rag && .venv/bin/python -m pytest tests/test_compare.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'cae_rag.compare'`.

- [ ] **Step 3: Write compare.py**

Create `cae-rag/cae_rag/compare.py`:

```python
"""Build the RAG-vs-RLM-v3 comparison report from two eval.json aggregates."""
from __future__ import annotations
import json
from pathlib import Path

# Published RLM numbers from EXPERIMENTS.md (judge gpt-5.5 — different judge, context only)
PUBLISHED_RLM = {"v1": 0.698, "v3": 0.711, "v4": 0.706, "v5": 0.693}


def load_aggregate(eval_json_path: str) -> dict:
    return json.loads(Path(eval_json_path).read_text(encoding="utf-8"))["aggregate"]


def extract_rlm_predictions(rubrics_v3: list[dict]) -> list[dict]:
    """Map RLM v3 records to predictions: {item_idx, answer=rlm_answer}."""
    return [{"item_idx": r["item_idx"], "answer": r.get("rlm_answer", "")} for r in rubrics_v3]


def _fmt(x) -> str:
    return f"{x:.3f}" if isinstance(x, (int, float)) else "—"


def _delta(a, b) -> str:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        d = a - b
        return f"{d:+.3f}".replace("+-", "-")
    return "—"


def build_comparison_md(rag: dict, rlm: dict) -> str:
    lines: list[str] = []
    lines.append("# CAE-RAG vs RLM v3 — Comparison\n")
    lines.append(f"Both scored with `cae-rubrics-eval`, judge `{rag.get('judge_model')}`, identical anchors.\n")
    lines.append("## Headline (mean_anchored — primary metric)\n")
    lines.append("| System | mean_anchored | mean_score | n_ok | n_err |")
    lines.append("|---|---|---|---|---|")
    lines.append(f"| RAG (hybrid top-5) | {_fmt(rag.get('mean_anchored'))} | {_fmt(rag.get('mean_score'))} | {rag.get('n_scored_ok')} | {rag.get('n_errors')} |")
    lines.append(f"| RLM v3 | {_fmt(rlm.get('mean_anchored'))} | {_fmt(rlm.get('mean_score'))} | {rlm.get('n_scored_ok')} | {rlm.get('n_errors')} |")
    lines.append(f"\n**Delta (RAG − RLM v3) anchored: {_delta(rag.get('mean_anchored'), rlm.get('mean_anchored'))}**\n")

    lines.append("## By question type (mean_anchored)\n")
    lines.append("| question_type | RAG | RLM v3 | Δ |")
    lines.append("|---|---|---|---|")
    qts = sorted(set(rag.get("by_question_type", {})) | set(rlm.get("by_question_type", {})))
    for qt in qts:
        ra = rag.get("by_question_type", {}).get(qt, {}).get("mean_anchored")
        rl = rlm.get("by_question_type", {}).get(qt, {}).get("mean_anchored")
        lines.append(f"| {qt} | {_fmt(ra)} | {_fmt(rl)} | {_delta(ra, rl)} |")

    lines.append("\n## By difficulty (mean_anchored)\n")
    lines.append("| difficulty | RAG | RLM v3 | Δ |")
    lines.append("|---|---|---|---|")
    diffs = sorted(set(rag.get("by_difficulty", {})) | set(rlm.get("by_difficulty", {})))
    for d in diffs:
        ra = rag.get("by_difficulty", {}).get(d, {}).get("mean_anchored")
        rl = rlm.get("by_difficulty", {}).get(d, {}).get("mean_anchored")
        lines.append(f"| {d} | {_fmt(ra)} | {_fmt(rl)} | {_delta(ra, rl)} |")

    lines.append("\n## Secondary context — published RLM (judge gpt-5.5, NOT comparable to above)\n")
    lines.append("| version | published mean_anchored |")
    lines.append("|---|---|")
    for v, s in PUBLISHED_RLM.items():
        lines.append(f"| {v} | {s:.3f} |")
    lines.append("\n> The table above used judge `gpt-5.5`; the headline used `gpt-5.4-mini`. "
                 "Compare RAG only against the re-scored RLM v3 headline number.\n")
    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/juli/RLM/cae-rag && .venv/bin/python -m pytest tests/test_compare.py -v`
Expected: 2 passed.

- [ ] **Step 5: Write scripts/compare_results.py**

Create `cae-rag/scripts/compare_results.py`:

```python
"""CLI: score RAG predictions + re-score RLM v3, then write comparison.md."""
from __future__ import annotations
import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cae_rag.compare import build_comparison_md, extract_rlm_predictions, load_aggregate

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")
logger = logging.getLogger("compare_results")

EVAL_DIR = Path("/home/juli/RLM/cae-rubrics-eval")
EVAL_PY = EVAL_DIR / ".venv/bin/python"
RLM_V3 = Path("/home/juli/RLM/data/CAE-v2.0-1-rubrics-v3.json")


def score(predictions: Path, out: Path, concurrency: int) -> None:
    """Invoke cae-rubrics-eval/score.py from inside its dir (so its .env + anchors resolve)."""
    cmd = [str(EVAL_PY), "score.py", "--predictions", str(predictions.resolve()),
           "--out", str(out.resolve()), "--concurrency", str(concurrency)]
    logger.info("Scoring -> %s", out)
    subprocess.run(cmd, cwd=str(EVAL_DIR), check=True)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out-dir", default="outputs", type=Path)
    p.add_argument("--concurrency", type=int, default=16)
    args = p.parse_args()
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    # 1) score RAG
    score(out / "predictions.jsonl", out / "eval_rag.json", args.concurrency)

    # 2) build + score RLM v3 through the SAME pipeline
    v3 = json.loads(RLM_V3.read_text(encoding="utf-8"))
    rlm_preds = extract_rlm_predictions(v3)
    rlm_path = out / "rlm_v3_predictions.jsonl"
    with open(rlm_path, "w", encoding="utf-8") as f:
        for r in rlm_preds:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    score(rlm_path, out / "eval_rlm_v3.json", args.concurrency)

    # 3) comparison report
    rag_agg = load_aggregate(str(out / "eval_rag.json"))
    rlm_agg = load_aggregate(str(out / "eval_rlm_v3.json"))
    md = build_comparison_md(rag_agg, rlm_agg)
    (out / "comparison.md").write_text(md, encoding="utf-8")
    logger.info("RAG anchored=%s  RLM v3 anchored=%s", rag_agg.get("mean_anchored"), rlm_agg.get("mean_anchored"))
    logger.info("Wrote %s", out / "comparison.md")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Verify the eval venv resolves**

Run:
```bash
cd /home/juli/RLM/cae-rubrics-eval && .venv/bin/python -c "import cae_eval; print('cae_eval OK')"
```
Expected: `cae_eval OK`. If it fails, run `cd /home/juli/RLM/cae-rubrics-eval && python3.11 -m venv .venv && .venv/bin/pip install -e .` first.

- [ ] **Step 7: Commit**

```bash
cd /home/juli/RLM && git add cae-rag/cae_rag/compare.py cae-rag/scripts/compare_results.py cae-rag/tests/test_compare.py && git commit -m "feat(cae-rag): score both + RAG-vs-RLM-v3 comparison report"
```

---

## Task 11: Full run + verification

**Files:**
- Modify: `cae-rag/cae_rag/__init__.py` (export public API)

- [ ] **Step 1: Populate the package public API**

Edit `cae-rag/cae_rag/__init__.py`:

```python
"""CAE-RAG: hybrid-retrieval RAG over CAE-MDs."""
from cae_rag.config import Config, set_seed
from cae_rag.ingest import Chunk, chunk_text, clean_markdown, load_and_chunk
from cae_rag.retrieve import HybridRetriever, rrf_fuse
from cae_rag.generate import build_prompt, generate_all, generate_answer
from cae_rag.compare import build_comparison_md, extract_rlm_predictions, load_aggregate

__all__ = [
    "Config", "set_seed",
    "Chunk", "chunk_text", "clean_markdown", "load_and_chunk",
    "HybridRetriever", "rrf_fuse",
    "build_prompt", "generate_all", "generate_answer",
    "build_comparison_md", "extract_rlm_predictions", "load_aggregate",
]
```

- [ ] **Step 2: Run the full unit test suite**

Run: `cd /home/juli/RLM/cae-rag && .venv/bin/python -m pytest -v`
Expected: all tests pass (config 3, ingest 3, retrieve 4, index 1, generate 2, compare 2 = 15).

- [ ] **Step 3: Build the index on the full KB (if not already from Task 8)**

Run: `cd /home/juli/RLM/cae-rag && .venv/bin/python scripts/build_index.py`
Expected: completes, ~800–1400 chunks, artifacts in `outputs/`.

- [ ] **Step 4: Answer all 94 questions**

Run: `cd /home/juli/RLM/cae-rag && .venv/bin/python scripts/run_rag.py 2>&1 | tee outputs/run_rag.log`
Expected: "Answering 94 questions", "Wrote 94 predictions ... (0 empty/errored)". If a few items error (proxy timeout), re-run — empty answers still score (as near-zero), but aim for 0 errored.

- [ ] **Step 5: Score both and build the comparison**

Run: `cd /home/juli/RLM/cae-rag && .venv/bin/python scripts/compare_results.py 2>&1 | tee outputs/compare.log`
Expected: two scoring passes complete; final log line shows `RAG anchored=<x>  RLM v3 anchored=<y>`; `outputs/comparison.md` written.

- [ ] **Step 6: Verify the outputs**

Run:
```bash
cd /home/juli/RLM/cae-rag && .venv/bin/python -c "
import json
rag = json.load(open('outputs/eval_rag.json'))['aggregate']
rlm = json.load(open('outputs/eval_rlm_v3.json'))['aggregate']
assert rag['n_scored_ok']==94 and rag['n_errors']==0, rag
assert rlm['n_scored_ok']==94, rlm
print('RAG anchored', rag['mean_anchored'], '| RLM v3 anchored', rlm['mean_anchored'])
" && echo "--- comparison.md ---" && cat outputs/comparison.md
```
Expected: prints both anchored means and the full comparison table. `n_scored_ok==94`, `n_errors==0` for RAG.

- [ ] **Step 7: Record environment + commit code (not outputs)**

Run:
```bash
cd /home/juli/RLM/cae-rag && .venv/bin/pip freeze > outputs/requirements.txt
cd /home/juli/RLM && git add cae-rag/cae_rag/__init__.py && git commit -m "feat(cae-rag): export public API; full 94-question run complete"
```
(`outputs/` stays gitignored. If you want the comparison artifact in git, add `outputs/comparison.md` explicitly with `git add -f`.)

---

## Self-Review notes

- **Spec coverage:** §2 params → Task 2 (Config). §3 Stage 1 → Task 3 + 8. Stage 2 → Task 5 + 8. Stage 3 → Tasks 4, 6. Stage 4 → Tasks 7, 9. Stage 5 (incl. re-score RLM v3) → Task 10, 11. §5 reproducibility → Config.set_seed (T2), run_meta hash + pip freeze (T8, T11). §6 tested cores → Tasks 2,3,4,7,10. §7 risks: Milvus Lite limits → client-side BM25 (T5,6) + 3.12/3.11 smoke (T1); item_idx parity → questions read from the dataset, scored against the bundled rubrics which share item_idx (verified in T11 Step 6 via n_scored_ok==94).
- **Anti-cheat:** run_rag loader reads only `item_idx`+`question` (T9 Step 3 greps to confirm).
- **Type consistency:** `Chunk` fields, `rrf_fuse(dense_ranked, sparse_ranked, k, top_k)`, `HybridRetriever.retrieve -> list[{chunk_id,text,doc}]`, `generate_all -> [{item_idx,answer,retrieved}]`, `build_comparison_md(rag, rlm)` are consistent across tasks.
- **Placeholder scan:** every code/command step contains concrete content; no TBD/TODO.

## Known follow-ups (out of scope, optional)

- Re-score RLM v1/v4/v5 under gpt-5.4-mini for a fuller table.
- Retrieval ablations (top-k, chunk size, dense-only vs hybrid).
- item_idx↔question parity hard-assert between the two rubric files (currently relied on implicitly; T11 Step 6 catches gross mismatch).
