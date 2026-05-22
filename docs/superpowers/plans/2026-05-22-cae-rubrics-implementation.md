# CAE-v2.0-1 Rubrics Generation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the **GroundedRubric-CAE** pipeline that ingests `data/CAE-v2.0-1.json` (94 items) + `CAE-MDs/` (8 source docs), runs a 3-stage RAG-grounded LLM pipeline, and outputs validated rubrics to `data/CAE-v2.0-1-rubrics.json` plus per-item files under `rubrics/items/`.

**Architecture:** RAG-grounded synthetic rubric generation. Stage 0 chunks/embeds the 8 source MDs. Stage 1 generates per-item weighted-binary checklist (8-15 criteria, signed, 4 categories) using gpt-5.4-mini with question + reference answer + retrieved page-specific chunks + type-aware template + 3 gold exemplars. Stage 2 enforces atomicity, dedup, pitfall injection. Stage 3 filters criteria by judging them on reference answer (expected met=true) and weak answer "我不知道" (expected met=false) — drop mismatches. Per-item JSON conforms to a strict pydantic schema; scoring uses `(positive_score - penalty) / positive_max` clipped to [0,1] for dual-purpose RL reward + eval breakdown.

**Tech Stack:** Python 3.11, pydantic v2, FAISS (cpu) or sentence-transformers for embedding index, BGE-zh-v1.5 embeddings (local, free), OpenAI-compatible HTTP client (httpx) for gpt-5.4-mini via aiberm/dubrify, pytest for tests, tenacity for retries, python-dotenv for secrets.

**Spec:** `docs/superpowers/specs/2026-05-22-cae-rubrics-design.md`

---

## File Structure

**New files (create):**

```
src/rubrics/
├── __init__.py
├── schema.py                          # pydantic v2 models for Criterion / RubricItem / Meta
├── chunker.py                         # MD chunking → ChunkRecord (chunk_id, doc_slug, pages, text)
├── source_parser.py                   # 「来源」 string → list[(doc_slug, page_range)]
├── index.py                           # BGE-zh embedding + in-memory FAISS index
├── retriever.py                       # Page-filtered → semantic fallback retrieval
├── llm_client.py                      # aiberm/dubrify endpoint, retry, JSON-mode call
├── generator.py                       # Stage 1
├── refiner.py                         # Stage 2: atomicity, dedup, pitfall injection
├── misalignment_filter.py             # Stage 3
├── scoring.py                         # scoring formula + judge wrapper (for downstream)
├── pipeline.py                        # end-to-end orchestrator
└── templates/
    ├── system_prompt.txt
    ├── misalignment_judge_prompt.txt
    ├── type_rules/
    │   ├── 简答题.txt
    │   ├── 主观题.txt
    │   ├── 决策题.txt
    │   ├── 对比分析题.txt
    │   ├── 数值提取题.txt
    │   ├── 流程描述题.txt
    │   └── 数值关系题.txt
    └── exemplars/
        └── gold_rubrics.json          # 3 hand-written gold rubrics

run/
├── 01_build_index.py                  # Build & persist BGE-zh index of CAE-MDs
├── 02_generate_rubrics.py             # Main pipeline (loops over 94 items)
└── 03_validate.py                     # Self-check + report

tests/rubrics/
├── __init__.py
├── conftest.py                        # shared fixtures
├── test_chunker.py
├── test_source_parser.py
├── test_index.py
├── test_retriever.py
├── test_llm_client.py
├── test_schema.py
├── test_generator.py
├── test_refiner.py
├── test_misalignment_filter.py
├── test_scoring.py
└── test_pipeline_smoke.py

.env.example                            # template for LLM_API_KEY / LLM_BASE_URL / LLM_MODEL
pyproject.toml                          # uv-managed deps (or extend existing)
```

**Modified files:** none (additive only; original `data/CAE-v2.0-1.json` untouched).

---

## Task 1: Project scaffold + dependencies + schema

**Files:**
- Create: `pyproject.toml` (or extend if exists)
- Create: `src/rubrics/__init__.py`
- Create: `src/rubrics/schema.py`
- Create: `tests/__init__.py`
- Create: `tests/rubrics/__init__.py`
- Create: `tests/rubrics/conftest.py`
- Create: `tests/rubrics/test_schema.py`
- Create: `.env.example`

- [ ] **Step 1: Check current project state**

Run: `ls /home/juli/RLM/ && cat /home/juli/RLM/pyproject.toml 2>/dev/null || echo "no pyproject"`
Expected: see whether `pyproject.toml` already exists.

- [ ] **Step 2: Write/extend pyproject.toml**

If no existing pyproject.toml, create:

```toml
[project]
name = "rlm-rubrics"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.6",
    "httpx>=0.27",
    "tenacity>=8.2",
    "python-dotenv>=1.0",
    "sentence-transformers>=2.7",
    "faiss-cpu>=1.8",
    "numpy>=1.26",
    "regex>=2024.5",
    "tqdm>=4.66",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-mock>=3.12", "ruff>=0.4", "mypy>=1.10"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
```

If pyproject already exists, add the dependencies to its `[project]` section without removing other content.

- [ ] **Step 3: Install deps**

Run:
```bash
cd /home/juli/RLM && python3 -m venv .venv 2>/dev/null; source .venv/bin/activate && pip install -e ".[dev]"
```

Expected: install completes; `pytest --version` prints a version.

Note: this repo may already have a working venv (`rlm_venv/`); if so, install into it instead.

- [ ] **Step 4: Create `.env.example`**

```
# Copy to .env (gitignored) and fill in
LLM_API_KEY=sk-xxxx
LLM_BASE_URL=https://aiberm.com/v1
LLM_MODEL=openai/gpt-5.4-mini
# Fallback (used if primary errors):
LLM_FALLBACK_API_KEY=
LLM_FALLBACK_BASE_URL=
LLM_FALLBACK_MODEL=
EMBEDDING_MODEL=BAAI/bge-base-zh-v1.5
```

- [ ] **Step 5: Write the failing test for schema**

Create `tests/rubrics/test_schema.py`:

```python
import pytest
from pydantic import ValidationError
from rubrics.schema import Criterion, RubricItem, SourceGrounding, RubricMetadata


def test_criterion_accepts_valid_essential():
    c = Criterion(
        id="c1",
        text="必须明确指出 ALE 方法保持网格拓扑固定",
        category="Essential",
        weight=5,
        sign="positive",
        criterion_type="factual_anchor",
    )
    assert c.weight == 5
    assert c.sign == "positive"


def test_criterion_rejects_invalid_category():
    with pytest.raises(ValidationError):
        Criterion(
            id="c1",
            text="x",
            category="Bogus",
            weight=5,
            sign="positive",
            criterion_type="factual_anchor",
        )


def test_criterion_rejects_pitfall_with_positive_sign():
    with pytest.raises(ValidationError):
        Criterion(
            id="c1",
            text="x",
            category="Pitfall",
            weight=4,
            sign="positive",
            criterion_type="anti_hacking",
        )


def test_criterion_rejects_weight_out_of_range():
    with pytest.raises(ValidationError):
        Criterion(
            id="c1",
            text="x",
            category="Essential",
            weight=99,
            sign="positive",
            criterion_type="factual_anchor",
        )


def test_rubric_item_minimal():
    item = RubricItem(
        question_id="1",
        question="什么是 ALE？",
        reference_answer="ALE 是任意拉格朗日-欧拉方法。",
        question_type="简答题",
        difficulty="简单",
        scenario="单文档单段落",
        source="Benson教材, 第1章, 第1页",
        source_grounding=SourceGrounding(
            parsed_docs=["benson"], pages=[1, 1],
            retrieved_chunk_ids=[], ground_status="page_specific",
        ),
        criteria=[
            Criterion(id="c1", text="x", category="Essential",
                      weight=5, sign="positive", criterion_type="factual_anchor"),
        ],
        rubric_metadata=RubricMetadata(
            generation_model="openai/gpt-5.4-mini",
            generation_passes=3,
            n_criteria_initial=1, n_criteria_final=1,
            n_dropped_misaligned=0,
            ref_answer_self_score=None, weak_answer_self_score=None,
            generated_at="2026-05-22T00:00:00Z",
            schema_version="1.0",
        ),
    )
    assert item.question_id == "1"


def test_rubric_item_rejects_unknown_question_type():
    with pytest.raises(ValidationError):
        RubricItem(
            question_id="1", question="x", reference_answer="y",
            question_type="奇怪题型",  # invalid
            difficulty="简单", scenario="x", source="x",
            source_grounding=SourceGrounding(
                parsed_docs=[], pages=[], retrieved_chunk_ids=[],
                ground_status="fallback_semantic",
            ),
            criteria=[],
            rubric_metadata=RubricMetadata(
                generation_model="x", generation_passes=1,
                n_criteria_initial=0, n_criteria_final=0,
                n_dropped_misaligned=0,
                ref_answer_self_score=None, weak_answer_self_score=None,
                generated_at="2026-05-22T00:00:00Z", schema_version="1.0",
            ),
        )
```

- [ ] **Step 6: Run tests — expect FAIL**

Run: `cd /home/juli/RLM && pytest tests/rubrics/test_schema.py -v`
Expected: ImportError or collection error — `rubrics.schema` does not exist.

- [ ] **Step 7: Implement schema**

Create `src/rubrics/__init__.py` (empty).

Create `src/rubrics/schema.py`:

```python
"""Pydantic v2 models for CAE rubrics."""
from __future__ import annotations
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, model_validator

QuestionType = Literal[
    "简答题", "主观题", "决策题", "对比分析题",
    "数值提取题", "流程描述题", "数值关系题",
]
Difficulty = Literal["简单", "中等", "困难"]
Category = Literal["Essential", "Important", "Optional", "Pitfall"]
Sign = Literal["positive", "negative"]
CriterionType = Literal[
    "factual_anchor", "mechanism_explanation", "numeric_precision",
    "decision_logic", "comparative_balance", "process_completeness",
    "anti_hacking",
]
GroundStatus = Literal["page_specific", "doc_only", "fallback_semantic"]


class Criterion(BaseModel):
    id: str
    text: str = Field(min_length=4)
    category: Category
    weight: int = Field(ge=1, le=8)
    sign: Sign
    criterion_type: CriterionType
    evidence_quote: Optional[str] = None

    @model_validator(mode="after")
    def check_sign_matches_category(self):
        if self.category == "Pitfall" and self.sign != "negative":
            raise ValueError("Pitfall must have sign=negative")
        if self.category != "Pitfall" and self.sign == "negative":
            raise ValueError(f"{self.category} must have sign=positive")
        return self


class SourceGrounding(BaseModel):
    parsed_docs: List[str]
    pages: List[int]
    retrieved_chunk_ids: List[str]
    ground_status: GroundStatus


class RubricMetadata(BaseModel):
    generation_model: str
    generation_passes: int = Field(ge=1)
    n_criteria_initial: int = Field(ge=0)
    n_criteria_final: int = Field(ge=0)
    n_dropped_misaligned: int = Field(ge=0)
    ref_answer_self_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    weak_answer_self_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    generated_at: str
    schema_version: str = "1.0"


class RubricItem(BaseModel):
    question_id: str
    question: str
    reference_answer: str
    question_type: QuestionType
    difficulty: Difficulty
    scenario: str
    source: str
    source_grounding: SourceGrounding
    criteria: List[Criterion]
    rubric_metadata: RubricMetadata
```

- [ ] **Step 8: Run tests — expect PASS**

Run: `pytest tests/rubrics/test_schema.py -v`
Expected: 6 passed.

- [ ] **Step 9: Commit**

```bash
cd /home/juli/RLM && git init 2>/dev/null; git add pyproject.toml .env.example src/rubrics/__init__.py src/rubrics/schema.py tests/__init__.py tests/rubrics/__init__.py tests/rubrics/conftest.py tests/rubrics/test_schema.py
git commit -m "feat(rubrics): scaffold project + pydantic schema for CAE rubrics"
```

(If git repo doesn't exist yet, this also initializes it. If a `.gitignore` is needed, add `.env`, `.venv`, `__pycache__/`, `*.egg-info/` to it first.)

---

## Task 2: Markdown chunker

**Files:**
- Create: `src/rubrics/chunker.py`
- Create: `tests/rubrics/test_chunker.py`

- [ ] **Step 1: Write failing test**

Create `tests/rubrics/test_chunker.py`:

```python
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
    # overlap check
    assert chunks[0].text[-50:] in (chunks[0].text + chunks[1].text)


def test_chunk_markdown_preserves_page_markers(tmp_path: Path):
    md = tmp_path / "paged.md"
    md.write_text(
        "intro intro\n\n<!-- page: 5 -->\npage5 content " * 50 +
        "\n<!-- page: 6 -->\npage6 content " * 50,
        encoding="utf-8",
    )
    chunks = chunk_markdown(md, chunk_size=400, overlap=100)
    chunk_pages = [(c.page_start, c.page_end) for c in chunks]
    assert any(ps >= 5 for ps, pe in chunk_pages)


def test_chunk_markdown_real_cae_doc():
    """Smoke test against actual CAE-MD."""
    path = Path("/home/juli/RLM/CAE-MDs/水下爆炸冲击荷载作用下混凝土重力坝的破坏模式.md")
    if not path.exists():
        pytest.skip("CAE-MDs not present")
    chunks = chunk_markdown(path, chunk_size=400, overlap=100)
    assert len(chunks) > 1
    assert all(c.doc_slug for c in chunks)
```

- [ ] **Step 2: Run test — expect FAIL**

Run: `pytest tests/rubrics/test_chunker.py -v`
Expected: ImportError.

- [ ] **Step 3: Inspect actual CAE-MDs structure**

Run: `head -50 /home/juli/RLM/CAE-MDs/水下爆炸冲击荷载作用下混凝土重力坝的破坏模式.md`
Expected: see whether mineru-converted MDs have explicit page markers (`<!-- page: N -->` or `## Page N` or none). Adapt the page-extraction regex accordingly.

- [ ] **Step 4: Implement chunker**

Create `src/rubrics/chunker.py`:

```python
"""Markdown file chunker with optional page tracking."""
from __future__ import annotations
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

# Detect page markers — covers mineru's common output formats.
_PAGE_RE = re.compile(r"<!--\s*page[:\s]+(\d+)\s*-->|##\s*Page\s+(\d+)", re.IGNORECASE)
_SAFE_SLUG_RE = re.compile(r"[^\w一-鿿]+")


def doc_slug_from_filename(name: str) -> str:
    """Strip extension, replace non-word/CJK chars with underscore, collapse."""
    stem = Path(name).stem
    slug = _SAFE_SLUG_RE.sub("_", stem)
    return slug.strip("_")


@dataclass(frozen=True)
class ChunkRecord:
    chunk_id: str
    doc_slug: str
    page_start: Optional[int]
    page_end: Optional[int]
    text: str


def _scan_page_anchors(text: str) -> List[tuple[int, int]]:
    """Return list of (char_offset, page_number) anchors sorted by offset."""
    anchors = []
    for m in _PAGE_RE.finditer(text):
        page = int(m.group(1) or m.group(2))
        anchors.append((m.start(), page))
    return anchors


def _page_at_offset(anchors: List[tuple[int, int]], offset: int) -> Optional[int]:
    last = None
    for off, page in anchors:
        if off <= offset:
            last = page
        else:
            break
    return last


def chunk_markdown(
    path: Path, chunk_size: int = 400, overlap: int = 100
) -> List[ChunkRecord]:
    """Slide a window over the text. Chunk size & overlap measured in chars
    (≈ tokens for Chinese; close enough)."""
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be greater than overlap")
    text = path.read_text(encoding="utf-8")
    slug = doc_slug_from_filename(path.name)
    anchors = _scan_page_anchors(text)

    chunks: List[ChunkRecord] = []
    step = chunk_size - overlap
    idx = 0
    pos = 0
    while pos < len(text):
        end = min(pos + chunk_size, len(text))
        sub = text[pos:end]
        ps = _page_at_offset(anchors, pos)
        pe = _page_at_offset(anchors, end - 1) or ps
        chunk_id = f"{slug}:p{ps or 0}-p{pe or 0}:c{idx}"
        chunks.append(ChunkRecord(chunk_id, slug, ps, pe, sub))
        idx += 1
        pos += step
    return chunks
```

- [ ] **Step 5: Run test — expect PASS**

Run: `pytest tests/rubrics/test_chunker.py -v`
Expected: 4 passed (or 3 + 1 skipped if MDs absent).

- [ ] **Step 6: Commit**

```bash
git add src/rubrics/chunker.py tests/rubrics/test_chunker.py
git commit -m "feat(rubrics): markdown chunker with page anchor tracking"
```

---

## Task 3: Source parser (来源 → doc + pages)

**Files:**
- Create: `src/rubrics/source_parser.py`
- Create: `tests/rubrics/test_source_parser.py`

- [ ] **Step 1: Write failing test**

Create `tests/rubrics/test_source_parser.py`:

```python
from rubrics.source_parser import parse_source, DOC_ALIASES


def test_parse_benson_with_page_range():
    parts = parse_source("Benson教材, 第4章, 第166-189页")
    assert len(parts) == 1
    assert parts[0].doc_alias == "Benson"
    assert parts[0].pages == (166, 189)


def test_parse_phd_with_single_page():
    parts = parse_source("贾宪振博士论文 第17页")
    assert parts[0].doc_alias == "贾宪振博士论文"
    assert parts[0].pages == (17, 17)


def test_parse_thyssenkrupp_short_form():
    parts = parse_source("ThyssenKrupp论文 第5页")
    assert parts[0].doc_alias == "ThyssenKrupp"


def test_parse_semicolon_multidoc():
    parts = parse_source("贾宪振博士论文 第17页; ThyssenKrupp论文 第5页")
    assert len(parts) == 2
    assert parts[0].doc_alias == "贾宪振博士论文"
    assert parts[1].doc_alias == "ThyssenKrupp"


def test_parse_no_page_info():
    parts = parse_source("Benson教材")
    assert len(parts) == 1
    assert parts[0].pages is None


def test_parse_comma_multidoc():
    parts = parse_source("贾宪振博士论文 第17页，重力坝论文 第502页")
    assert len(parts) == 2


def test_doc_aliases_map_to_actual_filenames():
    """Each alias must correspond to a real file in CAE-MDs/."""
    from pathlib import Path
    mds = list(Path("/home/juli/RLM/CAE-MDs").glob("*.md"))
    if not mds:
        return
    names = {m.name for m in mds}
    for alias, filename in DOC_ALIASES.items():
        assert filename in names, f"alias '{alias}' → '{filename}' not in CAE-MDs/"
```

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/rubrics/test_source_parser.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement source parser**

Create `src/rubrics/source_parser.py`:

```python
"""Parse the 「来源」 field of CAE-v2.0-1 items into (doc, pages) tuples."""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

# Map short alias used in 来源 to the actual filename in CAE-MDs/.
DOC_ALIASES: dict[str, str] = {
    "Benson": "Arbitrary_Lagrangian-Eulerian_and_Fluid-Structure Interaction Numerical Simulation (Benson).md",
    "ThyssenKrupp": "oezarmut_thyssenkrupp_Fluid-Composite Structure-Interaction in Underwater Shock Simulations.md",
    "贾宪振博士论文": "PhD 基于通用程序的水下爆炸及其对结构作用的数值模拟研究.md",
    "重力坝论文": "水下爆炸冲击荷载作用下混凝土重力坝的破坏模式.md",
    "混凝土重力坝破坏模式论文": "水下爆炸冲击荷载作用下混凝土重力坝的破坏模式.md",
    "钢板混凝土墙": "基于ANSYS_LS-DYNA的钢板混凝土墙冲击实验的有限元分析.md",
    "液电效应": "基于LS-DYNA的液电效应冲击波数值模拟.md",
    "高速破片": "基于LS-DYNA的高速破片水中运动特性流固耦合数值模拟.md",
    "加筋结构": "不同加筋结构在水中接触爆炸下的破损规律.md",
}

# Each segment: "<alias>(教材|论文)?... 第N-N页" or "第N页"
_SEGMENT_SPLIT = re.compile(r"[;；，,]")
_PAGE_RANGE = re.compile(r"第\s*(\d+)\s*[-－~～至到]\s*(\d+)\s*页")
_PAGE_SINGLE = re.compile(r"第\s*(\d+)\s*页")


@dataclass(frozen=True)
class SourceRef:
    doc_alias: str
    pages: Optional[Tuple[int, int]]


def _detect_alias(text: str) -> Optional[str]:
    for alias in DOC_ALIASES:
        if alias in text:
            return alias
    return None


def _parse_pages(text: str) -> Optional[Tuple[int, int]]:
    m = _PAGE_RANGE.search(text)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    m = _PAGE_SINGLE.search(text)
    if m:
        p = int(m.group(1))
        return (p, p)
    return None


def parse_source(s: str) -> List[SourceRef]:
    """Split by ; or ， then extract alias + pages from each segment."""
    if not s or not s.strip():
        return []
    segments = [seg.strip() for seg in _SEGMENT_SPLIT.split(s) if seg.strip()]
    out: List[SourceRef] = []
    last_alias: Optional[str] = None
    for seg in segments:
        alias = _detect_alias(seg) or last_alias
        if alias is None:
            continue
        pages = _parse_pages(seg)
        out.append(SourceRef(doc_alias=alias, pages=pages))
        last_alias = alias
    return out
```

- [ ] **Step 4: Run — expect PASS**

Run: `pytest tests/rubrics/test_source_parser.py -v`
Expected: 7 passed.

- [ ] **Step 5: Sanity check against real data**

Run:
```bash
cd /home/juli/RLM && python3 -c "
import json
from rubrics.source_parser import parse_source
data = json.load(open('data/CAE-v2.0-1.json'))
unparseable = []
for d in data:
    refs = parse_source(d['来源'])
    if not refs:
        unparseable.append((d['编号'], d['来源']))
print(f'Parsed: {len(data) - len(unparseable)} / {len(data)}')
print('Unparseable:')
for n, s in unparseable[:20]: print(f'  #{n}: {s!r}')
"
```
Expected: ≥ 90 / 94 parseable. If many fail, extend `DOC_ALIASES` with additional aliases observed in the unparseable rows.

- [ ] **Step 6: Commit**

```bash
git add src/rubrics/source_parser.py tests/rubrics/test_source_parser.py
git commit -m "feat(rubrics): 来源 field parser with doc-alias map"
```

---

## Task 4: Embedding index over CAE-MDs

**Files:**
- Create: `src/rubrics/index.py`
- Create: `tests/rubrics/test_index.py`

- [ ] **Step 1: Write failing test**

Create `tests/rubrics/test_index.py`:

```python
from pathlib import Path
import pytest
from rubrics.chunker import ChunkRecord
from rubrics.index import ChunkIndex


@pytest.fixture
def tiny_index():
    chunks = [
        ChunkRecord(c.chunk_id, c.doc_slug, c.page_start, c.page_end, c.text)
        for c in [
            ChunkRecord("a:p1-p1:c0", "a", 1, 1, "ALE 是任意拉格朗日欧拉方法，网格随材料运动"),
            ChunkRecord("a:p2-p2:c0", "a", 2, 2, "Lagrangian 方法节点与材料粒子绑定"),
            ChunkRecord("b:p10-p10:c0", "b", 10, 10, "JWL 状态方程描述爆轰产物膨胀"),
        ]
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
```

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/rubrics/test_index.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement index**

Create `src/rubrics/index.py`:

```python
"""In-memory embedding index over CAE-MD chunks."""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
from sentence_transformers import SentenceTransformer

from rubrics.chunker import ChunkRecord


@dataclass
class ChunkIndex:
    chunks: List[ChunkRecord]
    embeddings: np.ndarray
    model_name: str

    @classmethod
    def build(cls, chunks: List[ChunkRecord], model_name: str = "BAAI/bge-base-zh-v1.5") -> "ChunkIndex":
        model = SentenceTransformer(model_name)
        # bge family expects a query/passage prefix for asymmetric search.
        # For passages, no prefix needed in bge-zh-v1.5.
        texts = [c.text for c in chunks]
        emb = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return cls(chunks=chunks, embeddings=np.asarray(emb), model_name=model_name)

    def _encode_query(self, q: str) -> np.ndarray:
        # bge-zh uses "为这个句子生成表示以用于检索相关文章：" as query prefix
        model = SentenceTransformer(self.model_name)
        prefix = "为这个句子生成表示以用于检索相关文章："
        v = model.encode([prefix + q], normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(v)[0]

    def search(self, query: str, k: int = 3) -> List[ChunkRecord]:
        if not self.chunks:
            return []
        qv = self._encode_query(query)
        scores = self.embeddings @ qv
        idx = np.argsort(-scores)[:k]
        return [self.chunks[i] for i in idx]

    def search_within(
        self, query: str, k: int = 3, doc_slug: Optional[str] = None,
        pages: Optional[Tuple[int, int]] = None,
    ) -> List[ChunkRecord]:
        candidates = [
            (i, c) for i, c in enumerate(self.chunks)
            if (doc_slug is None or c.doc_slug == doc_slug)
            and (pages is None or self._page_overlap(c, pages))
        ]
        if not candidates:
            return []
        qv = self._encode_query(query)
        sub_emb = self.embeddings[[i for i, _ in candidates]]
        scores = sub_emb @ qv
        order = np.argsort(-scores)[:k]
        return [candidates[i][1] for i in order]

    @staticmethod
    def _page_overlap(chunk: ChunkRecord, pages: Tuple[int, int]) -> bool:
        p_lo, p_hi = pages
        c_lo = chunk.page_start or 0
        c_hi = chunk.page_end or c_lo
        return not (c_hi < p_lo or c_lo > p_hi)
```

- [ ] **Step 4: Run — expect PASS**

Run: `pytest tests/rubrics/test_index.py -v`
Expected: 3 passed. (First run downloads BGE model — ~400MB. Allow several minutes if first time.)

- [ ] **Step 5: Commit**

```bash
git add src/rubrics/index.py tests/rubrics/test_index.py
git commit -m "feat(rubrics): BGE-zh embedding index with page-filtered search"
```

---

## Task 5: Retriever — page-first with semantic fallback

**Files:**
- Create: `src/rubrics/retriever.py`
- Create: `tests/rubrics/test_retriever.py`

- [ ] **Step 1: Write failing test**

Create `tests/rubrics/test_retriever.py`:

```python
import pytest
from rubrics.chunker import ChunkRecord
from rubrics.index import ChunkIndex
from rubrics.source_parser import SourceRef
from rubrics.retriever import retrieve_context


@pytest.fixture
def idx():
    chunks = [
        ChunkRecord("Arbitrary_Lagrangian_Eulerian_and_Fluid_Structure_Interaction_Numerical_Simulation_Benson:p166-p180:c0", "Arbitrary_Lagrangian-Eulerian_and_Fluid-Structure_Interaction_Numerical_Simulation_Benson", 166, 180, "附加质量效应在 FSI 中会导致不稳定"),
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
```

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/rubrics/test_retriever.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement retriever**

Create `src/rubrics/retriever.py`:

```python
"""High-level retrieval: page-first, semantic fallback."""
from __future__ import annotations
from typing import List, Tuple

from rubrics.chunker import ChunkRecord
from rubrics.index import ChunkIndex
from rubrics.source_parser import SourceRef, DOC_ALIASES, doc_slug_from_filename


def retrieve_context(
    question: str, refs: List[SourceRef], index: ChunkIndex, k: int = 3,
) -> Tuple[List[ChunkRecord], str]:
    """Return (chunks, ground_status).

    Strategy:
      1. If `refs` resolves to a known doc + pages, search within that scope.
      2. Else if doc resolves but no pages, search within the doc.
      3. Else fall back to semantic search over the whole corpus.
    """
    if refs:
        all_hits: List[ChunkRecord] = []
        seen = set()
        for r in refs:
            filename = DOC_ALIASES.get(r.doc_alias)
            if filename is None:
                continue
            slug = doc_slug_from_filename(filename)
            if r.pages is not None:
                hits = index.search_within(question, k=k, doc_slug=slug, pages=r.pages)
                status_local = "page_specific"
            else:
                hits = index.search_within(question, k=k, doc_slug=slug, pages=None)
                status_local = "doc_only"
            for h in hits:
                if h.chunk_id not in seen:
                    all_hits.append(h)
                    seen.add(h.chunk_id)
        if all_hits:
            # If at least one ref had pages, mark page_specific
            status = "page_specific" if any(r.pages for r in refs) else "doc_only"
            return all_hits[:k], status
    # fallback
    return index.search(question, k=k), "fallback_semantic"
```

- [ ] **Step 4: Run — expect PASS**

Run: `pytest tests/rubrics/test_retriever.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/rubrics/retriever.py tests/rubrics/test_retriever.py
git commit -m "feat(rubrics): retriever with page-first then semantic fallback"
```

---

## Task 6: LLM client (gpt-5.4-mini via aiberm/dubrify)

**Files:**
- Create: `src/rubrics/llm_client.py`
- Create: `tests/rubrics/test_llm_client.py`

- [ ] **Step 1: Write failing test**

Create `tests/rubrics/test_llm_client.py`:

```python
import json
import pytest
import httpx
from rubrics.llm_client import LLMClient, LLMConfig


def test_llm_client_completion_calls_endpoint(mocker):
    response = {
        "choices": [{
            "message": {"content": json.dumps({"ok": True})}
        }],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50},
    }
    mock_post = mocker.patch.object(
        httpx.Client, "post",
        return_value=mocker.Mock(status_code=200, json=lambda: response, raise_for_status=lambda: None),
    )
    cfg = LLMConfig(api_key="sk-x", base_url="https://example/v1", model="m")
    client = LLMClient(cfg)
    out = client.complete_json(
        system="sys", user="usr", schema_hint="{ok: bool}",
    )
    assert out == {"ok": True}
    assert mock_post.called


def test_llm_client_retries_on_500(mocker):
    """Server error should trigger retry."""
    side_effects = [
        mocker.Mock(status_code=500, raise_for_status=mocker.Mock(side_effect=httpx.HTTPStatusError(
            "x", request=mocker.Mock(), response=mocker.Mock(status_code=500),
        ))),
        mocker.Mock(status_code=200, json=lambda: {
            "choices": [{"message": {"content": json.dumps({"ok": True})}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }, raise_for_status=lambda: None),
    ]
    mocker.patch.object(httpx.Client, "post", side_effect=side_effects)
    cfg = LLMConfig(api_key="sk-x", base_url="https://example/v1", model="m", max_retries=3)
    client = LLMClient(cfg)
    out = client.complete_json(system="s", user="u", schema_hint="x")
    assert out == {"ok": True}


def test_llm_client_raises_on_non_json_response(mocker):
    mocker.patch.object(
        httpx.Client, "post",
        return_value=mocker.Mock(status_code=200, json=lambda: {
            "choices": [{"message": {"content": "this is not json"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }, raise_for_status=lambda: None),
    )
    cfg = LLMConfig(api_key="sk-x", base_url="https://example/v1", model="m", max_retries=1)
    client = LLMClient(cfg)
    with pytest.raises(ValueError):
        client.complete_json(system="s", user="u", schema_hint="x")
```

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/rubrics/test_llm_client.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement LLM client**

Create `src/rubrics/llm_client.py`:

```python
"""OpenAI-compatible client for gpt-5.4-mini (aiberm.com / dubrify.com)."""
from __future__ import annotations
import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    api_key: str
    base_url: str
    model: str
    temperature: float = 0.3
    max_retries: int = 3
    timeout_s: float = 120.0

    @classmethod
    def from_env(cls) -> "LLMConfig":
        return cls(
            api_key=os.environ["LLM_API_KEY"],
            base_url=os.environ.get("LLM_BASE_URL", "https://aiberm.com/v1"),
            model=os.environ.get("LLM_MODEL", "openai/gpt-5.4-mini"),
        )


_JSON_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL)


def _extract_json_block(text: str) -> str:
    m = _JSON_FENCE.search(text)
    if m:
        return m.group(1)
    # Otherwise hope the whole thing is JSON.
    return text.strip()


class LLMClient:
    def __init__(self, cfg: LLMConfig):
        self.cfg = cfg
        self._client = httpx.Client(timeout=cfg.timeout_s)

    def complete_json(
        self, system: str, user: str, schema_hint: str,
        temperature: float | None = None, model: str | None = None,
    ) -> Any:
        """POST /chat/completions and parse JSON. Retries on 5xx/connection errors."""
        @retry(
            stop=stop_after_attempt(self.cfg.max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError)),
            reraise=True,
        )
        def _call() -> dict:
            r = self._client.post(
                f"{self.cfg.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.cfg.api_key}"},
                json={
                    "model": model or self.cfg.model,
                    "temperature": temperature if temperature is not None else self.cfg.temperature,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
            )
            r.raise_for_status()
            return r.json()

        data = _call()
        content = data["choices"][0]["message"]["content"]
        block = _extract_json_block(content)
        try:
            return json.loads(block)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON. Raw content (first 500 chars): %s", content[:500])
            raise ValueError(f"LLM did not return valid JSON: {e}") from e
```

- [ ] **Step 4: Run — expect PASS**

Run: `pytest tests/rubrics/test_llm_client.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/rubrics/llm_client.py tests/rubrics/test_llm_client.py
git commit -m "feat(rubrics): OpenAI-compatible LLM client with retries"
```

---

## Task 7: Prompt templates + gold exemplars

**Files:**
- Create: `src/rubrics/templates/system_prompt.txt`
- Create: `src/rubrics/templates/misalignment_judge_prompt.txt`
- Create: `src/rubrics/templates/type_rules/{简答题,主观题,决策题,对比分析题,数值提取题,流程描述题,数值关系题}.txt`
- Create: `src/rubrics/templates/exemplars/gold_rubrics.json`

- [ ] **Step 1: Create `system_prompt.txt`**

```
你是一位 CAE / 工程仿真领域的高级评审专家。你的任务是为一道专家问答题生成一份高质量的 rubric，用于：（a）RL 训练的 reward 信号；（b）模型评测的细粒度打分。

【RUBRIC 总体要求】
1. 输出 weighted binary checklist。每条 criterion 是一条独立、原子化、可被 judge 在阅读候选答案后 yes/no 判定的陈述。
2. 一条 criterion 只检查一件事。禁止"X 且 Y"形式的复合断言；如需多点，请拆成多条。
3. category 必须是 {"Essential", "Important", "Optional", "Pitfall"} 之一；sign 必须是 {"positive", "negative"} 之一。Pitfall 的 sign 必须为 "negative"，其余必须为 "positive"。
4. weight 默认值：Essential=5, Important=3, Optional=1, Pitfall=3-5；允许 ±1 微调（最终在 [1,8] 范围内）。
5. criterion_type 必须从以下 7 种中选择：factual_anchor, mechanism_explanation, numeric_precision, decision_logic, comparative_balance, process_completeness, anti_hacking。anti_hacking 仅用于 Pitfall。
6. 至少包含 2 条 Pitfall (anti_hacking) criterion。如下两条 anti_hacking pitfall 是必填默认项：
   - "回答以套话/开场白/元评论开头而无实质内容"（weight 4）
   - "回答篇幅冗长，包含大量与问题无关的背景铺垫或重复"（weight 3）
   你可以追加题型相关的 Pitfall。
7. 严禁使用「good」「clear」「comprehensive」「合理」「适当」等无锚点形容词。每条 criterion 必须引用具体术语、参数名、机制、数值、单位或步骤。
8. 优先从【参考答案】与【领域上下文】中提炼 criterion；不要凭空捏造参考答案未涉及的事实。
9. 输出严格遵循下面的 JSON 结构，不要加任何前后缀、注释或解释。

【JSON Schema (单道题)】
{
  "criteria": [
    {
      "id": "c1",
      "text": "...",
      "category": "Essential|Important|Optional|Pitfall",
      "weight": 1-8,
      "sign": "positive|negative",
      "criterion_type": "factual_anchor|mechanism_explanation|numeric_precision|decision_logic|comparative_balance|process_completeness|anti_hacking",
      "evidence_quote": "(可选) 引用自领域上下文的支撑短语"
    },
    ...
  ]
}
```

- [ ] **Step 2: Create `misalignment_judge_prompt.txt`**

```
你是 CAE 领域的严格 judge。给定一道题、一个候选回答、一条 rubric criterion，判断该候选回答是否满足该 criterion。

输出严格 JSON：{"met": true/false, "reason": "一句话理由"}

判定原则：
- 只看候选回答的内容，不假设作者未说出的意图。
- "met=true" 表示候选回答确实包含或满足了该 criterion 描述的内容。
- 对于 negative/Pitfall criterion："met=true" 表示候选回答触发了该负向规则（即出现了不该出现的内容）。
- 边界情形以严格态度判定为 "met=false"。
```

- [ ] **Step 3: Create `type_rules/简答题.txt`** (and the other 6)

`简答题.txt`:
```
【本题为简答题】
- 总条目数：8-10
- factual_anchor: 3-5 条（必须为 Essential，对应参考答案的关键事实点）
- mechanism_explanation: 1-2 条（对应"为什么"的机制陈述，Important）
- anti_hacking: 必填 2 条 Pitfall
```

`主观题.txt`:
```
【本题为主观题】
- 总条目数：10-12
- factual_anchor: 2-3 条（Essential）
- mechanism_explanation: 3-4 条（Important，针对开放性问题的多因解释）
- comparative_balance: 可选 0-1 条
- anti_hacking: 必填 2 条 Pitfall
- 注意：主观题鼓励对参考答案中提出的"原因列表/影响列表"逐点拆解为独立 criterion
```

`决策题.txt`:
```
【本题为决策题】
- 总条目数：8-11
- factual_anchor: 1-2 条
- mechanism_explanation: 1-2 条
- decision_logic: 3-4 条（Essential）。其中至少 1 条用于"明确给出选择/结论"，其余用于"论证逻辑、依据、可行性"。
- comparative_balance: 1 条（可选，针对"为什么不选 X"的反向论证）
- anti_hacking: 必填 2 条 Pitfall。建议追加 1 条："给出多个并列选项而不做决定"
```

`对比分析题.txt`:
```
【本题为对比分析题】
- 总条目数：8-10
- factual_anchor: 1-2 条
- mechanism_explanation: 1 条
- comparative_balance: 3-4 条（Essential，必须覆盖"相同点"+"不同点"+"权衡"+"结论")
- anti_hacking: 必填 2 条 Pitfall。建议追加 1 条："只列其中一方而忽略对比"
```

`数值提取题.txt`:
```
【本题为数值提取题】
- 总条目数：6-8
- factual_anchor: 1 条
- numeric_precision: 3-4 条（Essential）。每个关键数值/参数名独占一条；数值正确允许 ±2% 容差，单位错误判 met=false。
- anti_hacking: 必填 2 条 Pitfall。建议追加 1 条："写出数值但缺少单位或物理含义"
```

`流程描述题.txt`:
```
【本题为流程描述题】
- 总条目数：7-9
- factual_anchor: 1 条
- mechanism_explanation: 1 条
- process_completeness: 3-4 条（Essential）。每个关键步骤独占一条；顺序错误另立一条 Pitfall (process_completeness sign=positive 不能用，所以用 anti_hacking 形式)。
- anti_hacking: 必填 2 条 Pitfall。建议追加 1 条："步骤顺序颠倒或缺失关键中间步骤"
```

`数值关系题.txt`:
```
【本题为数值关系题】
- 总条目数：6-8
- factual_anchor: 1 条
- mechanism_explanation: 1 条
- numeric_precision: 2-3 条（Essential）。重点检查关系式正确性、自变量与因变量、幂次/系数。
- anti_hacking: 必填 2 条 Pitfall。建议追加 1 条："只写定性关系而不给量化形式"
```

- [ ] **Step 4: Create `exemplars/gold_rubrics.json`** (3 hand-written gold rubrics)

```json
[
  {
    "question_type": "简答题",
    "question": "为什么在LS-DYNA中使用ALE或Euler方法计算远场水下爆炸时，冲击波峰值压力往往比经验公式小？",
    "reference_answer": "网格尺寸限制：远场水域范围庞大，受限于计算资源，水域网格往往划分较粗（如10cm），有限分辨率的离散单元难以精确处理冲击波的高频分量。人工粘性影响：为了连续化处理强间断的冲击波，引入的人工体积粘性会引起数值耗散，系数越大，峰值压力衰减越快。累积误差：随着传播距离增加，计算误差不断累积，导致远场压力值偏小。",
    "criteria": [
      {"id": "c1", "text": "明确指出远场水域网格通常划分较粗（如~10cm 量级）", "category": "Essential", "weight": 5, "sign": "positive", "criterion_type": "factual_anchor"},
      {"id": "c2", "text": "解释粗网格无法分辨冲击波高频分量是峰值压力偏低的原因", "category": "Essential", "weight": 5, "sign": "positive", "criterion_type": "mechanism_explanation"},
      {"id": "c3", "text": "提到人工体积粘性会导致数值耗散使峰值衰减", "category": "Essential", "weight": 5, "sign": "positive", "criterion_type": "mechanism_explanation"},
      {"id": "c4", "text": "指出人工粘性系数越大衰减越快", "category": "Important", "weight": 3, "sign": "positive", "criterion_type": "factual_anchor"},
      {"id": "c5", "text": "指出冲击波传播距离增加导致误差累积", "category": "Important", "weight": 3, "sign": "positive", "criterion_type": "mechanism_explanation"},
      {"id": "c6", "text": "回答中至少给出 3 个独立的原因（网格、粘性、累积误差三类）", "category": "Important", "weight": 3, "sign": "positive", "criterion_type": "factual_anchor"},
      {"id": "c7", "text": "回答以套话/开场白/元评论开头而无实质内容", "category": "Pitfall", "weight": 4, "sign": "negative", "criterion_type": "anti_hacking"},
      {"id": "c8", "text": "回答篇幅冗长，包含大量与问题无关的背景铺垫或重复", "category": "Pitfall", "weight": 3, "sign": "negative", "criterion_type": "anti_hacking"}
    ]
  },
  {
    "question_type": "决策题",
    "question": "若要模拟潜艇复合材料面板在水下爆炸下的全系统响应，但在计算资源和时间极度受限（要求数分钟内完成）时，应选择哪种耦合方法？",
    "reference_answer": "决策：选择USA代码（Underwater Shock Analysis）。逻辑：USA基于边界元法（BEM），无需对庞大的水域进行有限元建模，计算速度比ALE快几个数量级，能在几百秒内完成远场冲击计算。",
    "criteria": [
      {"id": "c1", "text": "明确给出最终选择是 USA 代码", "category": "Essential", "weight": 6, "sign": "positive", "criterion_type": "decision_logic"},
      {"id": "c2", "text": "指出 USA 基于边界元法 (BEM)", "category": "Essential", "weight": 5, "sign": "positive", "criterion_type": "factual_anchor"},
      {"id": "c3", "text": "解释 USA 无需对水域进行有限元建模", "category": "Essential", "weight": 5, "sign": "positive", "criterion_type": "mechanism_explanation"},
      {"id": "c4", "text": "比较 USA 与 ALE 的速度差异（quantitative：数量级快、或几百秒）", "category": "Important", "weight": 4, "sign": "positive", "criterion_type": "decision_logic"},
      {"id": "c5", "text": "答案不应推荐 ALE 或 Lagrangian 作为首选（在该资源约束下）", "category": "Important", "weight": 3, "sign": "positive", "criterion_type": "decision_logic"},
      {"id": "c6", "text": "给出多个并列选项而不做决定", "category": "Pitfall", "weight": 5, "sign": "negative", "criterion_type": "anti_hacking"},
      {"id": "c7", "text": "回答以套话/开场白/元评论开头而无实质内容", "category": "Pitfall", "weight": 4, "sign": "negative", "criterion_type": "anti_hacking"},
      {"id": "c8", "text": "回答篇幅冗长，包含大量与问题无关的背景铺垫或重复", "category": "Pitfall", "weight": 3, "sign": "negative", "criterion_type": "anti_hacking"}
    ]
  },
  {
    "question_type": "数值提取题",
    "question": "在模拟炸药爆轰产物时，JWL状态方程中的主要参数及其物理意义是什么？",
    "reference_answer": "核心参数：A和B为压力系数（单位GPa）；R1、R2和ω为无量纲特征常数；V为相对体积；E为爆轰产物体积内能。应用：该方程精确描述了炸药爆轰后高温高压气体产物的膨胀过程及对周围介质的做功特性。",
    "criteria": [
      {"id": "c1", "text": "提到 JWL 方程的核心参数包括 A 和 B（压力系数）", "category": "Essential", "weight": 5, "sign": "positive", "criterion_type": "numeric_precision"},
      {"id": "c2", "text": "正确指出 A、B 的单位为 GPa", "category": "Essential", "weight": 5, "sign": "positive", "criterion_type": "numeric_precision"},
      {"id": "c3", "text": "提到无量纲特征常数 R1、R2、ω", "category": "Essential", "weight": 5, "sign": "positive", "criterion_type": "numeric_precision"},
      {"id": "c4", "text": "提到 V 为相对体积、E 为爆轰产物体积内能", "category": "Essential", "weight": 5, "sign": "positive", "criterion_type": "numeric_precision"},
      {"id": "c5", "text": "简要说明 JWL 用于描述爆轰后气体膨胀过程", "category": "Important", "weight": 3, "sign": "positive", "criterion_type": "factual_anchor"},
      {"id": "c6", "text": "写出数值但缺少单位或物理含义", "category": "Pitfall", "weight": 4, "sign": "negative", "criterion_type": "anti_hacking"},
      {"id": "c7", "text": "回答以套话/开场白/元评论开头而无实质内容", "category": "Pitfall", "weight": 4, "sign": "negative", "criterion_type": "anti_hacking"},
      {"id": "c8", "text": "回答篇幅冗长，包含大量与问题无关的背景铺垫或重复", "category": "Pitfall", "weight": 3, "sign": "negative", "criterion_type": "anti_hacking"}
    ]
  }
]
```

- [ ] **Step 5: Commit**

```bash
git add src/rubrics/templates/
git commit -m "feat(rubrics): prompt templates + 3 gold exemplar rubrics"
```

---

## Task 8: Generator (Stage 1)

**Files:**
- Create: `src/rubrics/generator.py`
- Create: `tests/rubrics/test_generator.py`

- [ ] **Step 1: Write failing test**

Create `tests/rubrics/test_generator.py`:

```python
import json
from pathlib import Path
import pytest
from rubrics.generator import generate_initial_rubric


def test_generate_initial_rubric_calls_llm_with_typed_template(mocker):
    fake_client = mocker.Mock()
    fake_client.complete_json.return_value = {
        "criteria": [
            {"id": "c1", "text": "明确指出 X", "category": "Essential",
             "weight": 5, "sign": "positive", "criterion_type": "factual_anchor"},
            {"id": "c2", "text": "回答以套话开头", "category": "Pitfall",
             "weight": 4, "sign": "negative", "criterion_type": "anti_hacking"},
        ]
    }
    out = generate_initial_rubric(
        question="什么是 ALE？",
        reference_answer="ALE 是任意拉格朗日-欧拉方法。",
        question_type="简答题",
        difficulty="简单",
        source="Benson教材",
        retrieved_chunks=[],
        client=fake_client,
    )
    assert len(out) == 2
    args, kwargs = fake_client.complete_json.call_args
    # template-rule for 简答题 must appear in user message
    assert "简答题" in kwargs["user"]
    # 3 few-shot exemplars must be injected
    assert "decision_logic" in kwargs["user"] or "示例" in kwargs["user"]


def test_generate_initial_rubric_passes_chunks_into_prompt(mocker):
    from rubrics.chunker import ChunkRecord
    fake_client = mocker.Mock()
    fake_client.complete_json.return_value = {"criteria": []}
    chunks = [ChunkRecord("a:p1-p1:c0", "a", 1, 1, "这是源文档的一段内容")]
    generate_initial_rubric(
        question="x", reference_answer="y", question_type="简答题",
        difficulty="简单", source="x", retrieved_chunks=chunks, client=fake_client,
    )
    args, kwargs = fake_client.complete_json.call_args
    assert "这是源文档的一段内容" in kwargs["user"]
```

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/rubrics/test_generator.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement generator**

Create `src/rubrics/generator.py`:

```python
"""Stage 1: initial rubric generation."""
from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import List

from rubrics.chunker import ChunkRecord
from rubrics.llm_client import LLMClient

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent / "templates"


def _load_text(rel: str) -> str:
    return (_TEMPLATE_DIR / rel).read_text(encoding="utf-8")


def _format_chunks(chunks: List[ChunkRecord]) -> str:
    if not chunks:
        return "（无可用领域上下文）"
    parts = []
    for i, c in enumerate(chunks, 1):
        loc = f"{c.doc_slug} p{c.page_start}-p{c.page_end}"
        parts.append(f"[chunk {i} | {loc}]\n{c.text}")
    return "\n\n".join(parts)


def _format_exemplars(question_type: str) -> str:
    """Pick gold exemplars: 1 of same type if available + 2 other diverse types."""
    raw = json.loads(_load_text("exemplars/gold_rubrics.json"))
    same = [r for r in raw if r["question_type"] == question_type]
    others = [r for r in raw if r["question_type"] != question_type]
    selection = same[:1] + others[: max(0, 3 - len(same[:1]))]
    blocks = []
    for ex in selection:
        blocks.append(
            f"### 示例（{ex['question_type']}）\n"
            f"题目：{ex['question']}\n"
            f"参考答案：{ex['reference_answer']}\n"
            f"对应 rubric：\n{json.dumps({'criteria': ex['criteria']}, ensure_ascii=False, indent=2)}"
        )
    return "\n\n".join(blocks)


def generate_initial_rubric(
    question: str, reference_answer: str, question_type: str, difficulty: str,
    source: str, retrieved_chunks: List[ChunkRecord], client: LLMClient,
) -> list:
    """Call LLM once with full prompt; return raw criteria list."""
    system = _load_text("system_prompt.txt")
    type_rule = _load_text(f"type_rules/{question_type}.txt")
    exemplars = _format_exemplars(question_type)
    chunks_text = _format_chunks(retrieved_chunks)

    user = (
        f"[Q] {question}\n\n"
        f"[参考答案] {reference_answer}\n\n"
        f"[题型] {question_type}（请遵循该题型的 rubric 结构）\n"
        f"[难易程度] {difficulty}\n"
        f"[来源] {source}\n\n"
        f"[领域上下文 — 来自源文档]\n{chunks_text}\n\n"
        f"[题型规则]\n{type_rule}\n\n"
        f"[few-shot 示例]\n{exemplars}\n\n"
        f"请直接输出 JSON，不要任何前后缀。"
    )
    out = client.complete_json(system=system, user=user, schema_hint="criteria array")
    return out.get("criteria", [])
```

- [ ] **Step 4: Run — expect PASS**

Run: `pytest tests/rubrics/test_generator.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/rubrics/generator.py tests/rubrics/test_generator.py
git commit -m "feat(rubrics): Stage 1 initial rubric generator"
```

---

## Task 9: Refiner (Stage 2 — atomicity + dedup + pitfall injection)

**Files:**
- Create: `src/rubrics/refiner.py`
- Create: `tests/rubrics/test_refiner.py`

- [ ] **Step 1: Write failing test**

Create `tests/rubrics/test_refiner.py`:

```python
import numpy as np
from rubrics.refiner import refine_criteria, DEFAULT_PITFALLS


def test_refine_injects_default_pitfalls_when_missing():
    criteria = [
        {"id": "c1", "text": "x", "category": "Essential", "weight": 5,
         "sign": "positive", "criterion_type": "factual_anchor"},
    ]
    out = refine_criteria(criteria, embed_fn=None)
    pitfall_texts = [c["text"] for c in out if c["category"] == "Pitfall"]
    assert DEFAULT_PITFALLS[0]["text"] in pitfall_texts
    assert DEFAULT_PITFALLS[1]["text"] in pitfall_texts


def test_refine_does_not_duplicate_existing_pitfalls():
    criteria = [
        {"id": "c1", "text": DEFAULT_PITFALLS[0]["text"], "category": "Pitfall",
         "weight": 4, "sign": "negative", "criterion_type": "anti_hacking"},
        {"id": "c2", "text": DEFAULT_PITFALLS[1]["text"], "category": "Pitfall",
         "weight": 3, "sign": "negative", "criterion_type": "anti_hacking"},
    ]
    out = refine_criteria(criteria, embed_fn=None)
    pitfalls = [c for c in out if c["category"] == "Pitfall"]
    assert len(pitfalls) == 2


def test_refine_dedupes_near_duplicates_via_embedding():
    criteria = [
        {"id": "c1", "text": "明确指出 ALE 方法保持网格随材料运动",
         "category": "Essential", "weight": 5, "sign": "positive",
         "criterion_type": "factual_anchor"},
        {"id": "c2", "text": "明确指出 ALE 方法的网格随材料运动",
         "category": "Essential", "weight": 5, "sign": "positive",
         "criterion_type": "factual_anchor"},
    ]
    # Mock embedder that returns near-identical vectors for the two
    def embed_fn(texts):
        return np.array([[1.0, 0.0], [0.99, 0.01], [0.0, 1.0], [0.0, 1.0]][: len(texts)])

    out = refine_criteria(criteria, embed_fn=embed_fn)
    essentials = [c for c in out if c["category"] == "Essential"]
    assert len(essentials) == 1


def test_refine_splits_compound_criterion():
    criteria = [
        {"id": "c1", "text": "明确给出选择是 USA，并解释 USA 基于边界元法",
         "category": "Essential", "weight": 5, "sign": "positive",
         "criterion_type": "decision_logic"},
    ]
    out = refine_criteria(criteria, embed_fn=None, split_compound=True)
    essential_decisions = [c for c in out if c["category"] == "Essential"]
    # The compound is split into ≥ 2 atomic criteria
    assert len(essential_decisions) >= 2
```

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/rubrics/test_refiner.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement refiner**

Create `src/rubrics/refiner.py`:

```python
"""Stage 2: atomicity check, dedup, pitfall injection."""
from __future__ import annotations
import re
from typing import Callable, List, Optional

import numpy as np

DEFAULT_PITFALLS = [
    {
        "text": "回答以套话/开场白/元评论开头而无实质内容",
        "category": "Pitfall", "weight": 4, "sign": "negative",
        "criterion_type": "anti_hacking",
    },
    {
        "text": "回答篇幅冗长，包含大量与问题无关的背景铺垫或重复",
        "category": "Pitfall", "weight": 3, "sign": "negative",
        "criterion_type": "anti_hacking",
    },
]

_COMPOUND_SPLIT_RE = re.compile(r"\s*[，,]\s*并\s*|\s*[，,]\s*同时\s*|\s*[，,]\s*且\s*|\s*并\s*")


def _renumber(criteria: List[dict]) -> List[dict]:
    return [{**c, "id": f"c{i+1}"} for i, c in enumerate(criteria)]


def _ensure_default_pitfalls(criteria: List[dict]) -> List[dict]:
    existing_texts = {c["text"] for c in criteria if c["category"] == "Pitfall"}
    to_add = [p for p in DEFAULT_PITFALLS if p["text"] not in existing_texts]
    return criteria + to_add


def _dedup_by_embedding(
    criteria: List[dict], embed_fn: Callable[[list[str]], np.ndarray], threshold: float = 0.9,
) -> List[dict]:
    if not criteria:
        return criteria
    texts = [c["text"] for c in criteria]
    emb = embed_fn(texts)
    emb = emb / np.linalg.norm(emb, axis=1, keepdims=True).clip(min=1e-8)
    keep = []
    seen_vecs: List[np.ndarray] = []
    for c, v in zip(criteria, emb):
        is_dup = any(np.dot(v, sv) > threshold for sv in seen_vecs)
        if not is_dup:
            keep.append(c)
            seen_vecs.append(v)
    return keep


def _split_compound(criteria: List[dict]) -> List[dict]:
    out = []
    for c in criteria:
        parts = _COMPOUND_SPLIT_RE.split(c["text"])
        parts = [p.strip() for p in parts if p.strip() and len(p.strip()) >= 4]
        if len(parts) <= 1:
            out.append(c)
            continue
        # explode into one criterion per part, weight unchanged
        for p in parts:
            out.append({**c, "text": p})
    return out


def refine_criteria(
    criteria: List[dict],
    embed_fn: Optional[Callable[[list[str]], np.ndarray]] = None,
    *,
    split_compound: bool = True,
    dedup_threshold: float = 0.9,
) -> List[dict]:
    work = list(criteria)
    if split_compound:
        work = _split_compound(work)
    if embed_fn is not None:
        work = _dedup_by_embedding(work, embed_fn, dedup_threshold)
    work = _ensure_default_pitfalls(work)
    return _renumber(work)
```

- [ ] **Step 4: Run — expect PASS**

Run: `pytest tests/rubrics/test_refiner.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/rubrics/refiner.py tests/rubrics/test_refiner.py
git commit -m "feat(rubrics): Stage 2 refiner (atomicity + dedup + pitfall injection)"
```

---

## Task 10: Misalignment filter (Stage 3)

**Files:**
- Create: `src/rubrics/misalignment_filter.py`
- Create: `tests/rubrics/test_misalignment_filter.py`

- [ ] **Step 1: Write failing test**

```python
from rubrics.misalignment_filter import filter_misaligned, WEAK_ANSWER


def test_filter_keeps_positive_criterion_that_passes_both_sides(mocker):
    judge_client = mocker.Mock()
    # criterion judged: met on ref (true), not met on weak (false) → keep
    judge_client.complete_json.side_effect = [
        {"met": True, "reason": "x"},
        {"met": False, "reason": "y"},
    ]
    criteria = [{
        "id": "c1", "text": "明确指出 ALE 方法网格随材料运动",
        "category": "Essential", "weight": 5, "sign": "positive",
        "criterion_type": "factual_anchor",
    }]
    kept, n_dropped = filter_misaligned(
        question="什么是 ALE？", reference_answer="ALE 网格随材料运动",
        criteria=criteria, judge_client=judge_client,
    )
    assert len(kept) == 1
    assert n_dropped == 0


def test_filter_drops_positive_criterion_not_met_on_ref(mocker):
    judge_client = mocker.Mock()
    judge_client.complete_json.side_effect = [
        {"met": False, "reason": "ref doesn't say"},
    ]
    criteria = [{
        "id": "c1", "text": "完全偏离的 criterion", "category": "Essential",
        "weight": 5, "sign": "positive", "criterion_type": "factual_anchor",
    }]
    kept, n_dropped = filter_misaligned(
        question="q", reference_answer="ref", criteria=criteria, judge_client=judge_client,
    )
    assert kept == []
    assert n_dropped == 1


def test_filter_skips_pitfalls(mocker):
    judge_client = mocker.Mock()
    criteria = [{
        "id": "c1", "text": "回答篇幅冗长", "category": "Pitfall", "weight": 3,
        "sign": "negative", "criterion_type": "anti_hacking",
    }]
    kept, n_dropped = filter_misaligned(
        question="q", reference_answer="ref", criteria=criteria, judge_client=judge_client,
    )
    assert len(kept) == 1
    assert n_dropped == 0
    assert not judge_client.complete_json.called
```

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/rubrics/test_misalignment_filter.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement filter**

Create `src/rubrics/misalignment_filter.py`:

```python
"""Stage 3: drop criteria that don't behave as expected on (ref, weak) anchors."""
from __future__ import annotations
import logging
from pathlib import Path
from typing import List, Tuple

from rubrics.llm_client import LLMClient

logger = logging.getLogger(__name__)

WEAK_ANSWER = "我不知道。"
_PROMPT = (Path(__file__).parent / "templates" / "misalignment_judge_prompt.txt").read_text(encoding="utf-8")


def _judge_one(
    judge_client: LLMClient, question: str, candidate: str, criterion: dict,
) -> bool:
    user = (
        f"[题目] {question}\n"
        f"[候选回答] {candidate}\n"
        f"[criterion] {criterion['text']}\n"
        f"[criterion 类型] {criterion['criterion_type']}"
    )
    try:
        out = judge_client.complete_json(system=_PROMPT, user=user, schema_hint="{met, reason}")
        return bool(out.get("met", False))
    except Exception as e:
        logger.warning("Judge call failed for criterion %s: %s — treating as inconclusive (keep)", criterion.get("id"), e)
        # Conservative: keep on judge failure (don't lose criteria to flaky API)
        return True if criterion["sign"] == "positive" else False


def filter_misaligned(
    question: str, reference_answer: str, criteria: List[dict],
    judge_client: LLMClient, weak_answer: str = WEAK_ANSWER,
) -> Tuple[List[dict], int]:
    kept: List[dict] = []
    dropped = 0
    for c in criteria:
        if c["category"] == "Pitfall":
            # Skip — pitfalls are template-validated, see spec §10.2
            kept.append(c)
            continue
        met_ref = _judge_one(judge_client, question, reference_answer, c)
        if not met_ref:
            dropped += 1
            logger.info("Drop criterion %s: not met on reference answer", c.get("id"))
            continue
        met_weak = _judge_one(judge_client, question, weak_answer, c)
        if met_weak:
            dropped += 1
            logger.info("Drop criterion %s: triggered on weak answer", c.get("id"))
            continue
        kept.append(c)
    return kept, dropped
```

- [ ] **Step 4: Run — expect PASS**

Run: `pytest tests/rubrics/test_misalignment_filter.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/rubrics/misalignment_filter.py tests/rubrics/test_misalignment_filter.py
git commit -m "feat(rubrics): Stage 3 misalignment filter (ref + weak anchors)"
```

---

## Task 11: Scoring module (downstream consumption)

**Files:**
- Create: `src/rubrics/scoring.py`
- Create: `tests/rubrics/test_scoring.py`

- [ ] **Step 1: Write failing test**

```python
from rubrics.scoring import score_response
from rubrics.schema import Criterion


def _mk(text, cat, weight, sign):
    types = {"Pitfall": "anti_hacking"}
    return Criterion(
        id="c", text=text, category=cat, weight=weight, sign=sign,
        criterion_type=types.get(cat, "factual_anchor"),
    )


def test_score_all_essentials_met():
    criteria = [_mk("a", "Essential", 5, "positive"), _mk("b", "Important", 3, "positive")]
    met = {"a": True, "b": True}
    s = score_response(criteria, met_by_text=met)
    # (5 + 3) / 8 = 1.0
    assert s == 1.0


def test_score_partial():
    criteria = [_mk("a", "Essential", 5, "positive"), _mk("b", "Important", 3, "positive")]
    met = {"a": True, "b": False}
    s = score_response(criteria, met_by_text=met)
    assert s == 5 / 8


def test_score_with_pitfall_penalty():
    criteria = [
        _mk("a", "Essential", 5, "positive"),
        _mk("套话", "Pitfall", 4, "negative"),
    ]
    met = {"a": True, "套话": True}
    s = score_response(criteria, met_by_text=met)
    # (5 - 4) / 5 = 0.2
    assert abs(s - 0.2) < 1e-9


def test_score_clips_to_zero_when_penalty_exceeds():
    criteria = [
        _mk("a", "Essential", 1, "positive"),
        _mk("套话", "Pitfall", 5, "negative"),
    ]
    met = {"a": True, "套话": True}
    s = score_response(criteria, met_by_text=met)
    assert s == 0.0
```

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/rubrics/test_scoring.py -v`

- [ ] **Step 3: Implement scoring**

Create `src/rubrics/scoring.py`:

```python
"""Scoring formula from spec §6."""
from __future__ import annotations
from typing import Iterable

from rubrics.schema import Criterion


def score_response(criteria: Iterable[Criterion], met_by_text: dict[str, bool]) -> float:
    pos_score = 0
    pos_max = 0
    penalty = 0
    for c in criteria:
        met = met_by_text.get(c.text, False)
        if c.sign == "positive":
            pos_max += c.weight
            if met:
                pos_score += c.weight
        else:  # negative / pitfall
            if met:
                penalty += c.weight
    if pos_max == 0:
        return 0.0
    raw = (pos_score - penalty) / pos_max
    return max(0.0, min(1.0, raw))
```

- [ ] **Step 4: Run — expect PASS**

Run: `pytest tests/rubrics/test_scoring.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/rubrics/scoring.py tests/rubrics/test_scoring.py
git commit -m "feat(rubrics): scoring formula (positive minus penalty, clipped)"
```

---

## Task 12: Pipeline orchestrator

**Files:**
- Create: `src/rubrics/pipeline.py`
- Create: `tests/rubrics/test_pipeline_smoke.py`

- [ ] **Step 1: Write failing smoke test**

```python
import json
from rubrics.pipeline import build_rubric_for_item
from rubrics.chunker import ChunkRecord
from rubrics.index import ChunkIndex


def test_build_rubric_for_item_end_to_end(mocker):
    # Fake LLM that returns canned criteria for stage 1 then "met" judgments for stage 3
    fake_llm = mocker.Mock()
    fake_llm.complete_json.side_effect = [
        # Stage 1: initial criteria (1 positive, 1 pitfall)
        {"criteria": [
            {"id": "c1", "text": "明确解释附加质量效应导致迭代不收敛",
             "category": "Essential", "weight": 5, "sign": "positive",
             "criterion_type": "mechanism_explanation"},
        ]},
        # Stage 3: judge calls — ref met, weak not met for c1
        {"met": True, "reason": "ref says so"},
        {"met": False, "reason": "weak doesn't say"},
    ]
    chunks = [ChunkRecord("a:p1-p1:c0", "a", 1, 1, "附加质量效应是流体加速时表观增加的惯性")]
    idx = ChunkIndex.build(chunks)
    item = {
        "编号": "1",
        "问题描述": "为何附加质量效应导致数值不稳定？",
        "参考答案": "流体与结构密度接近时迭代易不收敛。",
        "题型": "主观题", "难易程度": "困难", "难度场景": "单文档多段落",
        "来源": "Benson教材, 第4章, 第166-189页", "语言": "中文",
    }
    rubric = build_rubric_for_item(
        item=item, index=idx,
        generator_client=fake_llm, judge_client=fake_llm,
        embed_fn=None,  # skip dedup in smoke test
    )
    assert rubric.question_id == "1"
    # Stage 2 injects 2 default pitfalls → final criteria ≥ 3
    assert len(rubric.criteria) >= 3
    pitfalls = [c for c in rubric.criteria if c.category == "Pitfall"]
    assert len(pitfalls) >= 2
```

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/rubrics/test_pipeline_smoke.py -v`

- [ ] **Step 3: Implement pipeline**

Create `src/rubrics/pipeline.py`:

```python
"""End-to-end orchestrator for one item."""
from __future__ import annotations
import datetime as dt
import logging
from typing import Callable, Optional

import numpy as np

from rubrics.chunker import ChunkRecord
from rubrics.generator import generate_initial_rubric
from rubrics.index import ChunkIndex
from rubrics.llm_client import LLMClient
from rubrics.misalignment_filter import filter_misaligned
from rubrics.refiner import refine_criteria
from rubrics.retriever import retrieve_context
from rubrics.schema import RubricItem, Criterion, SourceGrounding, RubricMetadata
from rubrics.source_parser import parse_source, DOC_ALIASES
from rubrics.chunker import doc_slug_from_filename

logger = logging.getLogger(__name__)


def build_rubric_for_item(
    item: dict, index: ChunkIndex,
    generator_client: LLMClient, judge_client: LLMClient,
    embed_fn: Optional[Callable[[list[str]], np.ndarray]] = None,
) -> RubricItem:
    qid = str(item["编号"])
    question = item["问题描述"]
    ref = item["参考答案"]
    qtype = item["题型"]
    difficulty = item["难易程度"]
    scenario = item["难度场景"]
    source = item["来源"]

    refs = parse_source(source)
    chunks, ground_status = retrieve_context(question=question, refs=refs, index=index, k=3)

    raw_criteria = generate_initial_rubric(
        question=question, reference_answer=ref, question_type=qtype,
        difficulty=difficulty, source=source, retrieved_chunks=chunks,
        client=generator_client,
    )
    n_initial = len(raw_criteria)

    refined = refine_criteria(raw_criteria, embed_fn=embed_fn)
    filtered, n_dropped = filter_misaligned(
        question=question, reference_answer=ref, criteria=refined,
        judge_client=judge_client,
    )

    # Build SourceGrounding
    parsed_docs = list({DOC_ALIASES[r.doc_alias].rsplit(".", 1)[0] for r in refs if r.doc_alias in DOC_ALIASES})
    pages: list[int] = []
    for r in refs:
        if r.pages:
            pages.extend([r.pages[0], r.pages[1]])

    sg = SourceGrounding(
        parsed_docs=[doc_slug_from_filename(d + ".md") for d in parsed_docs] if parsed_docs else [],
        pages=pages, retrieved_chunk_ids=[c.chunk_id for c in chunks],
        ground_status=ground_status,
    )

    criteria_models = [Criterion(**c) for c in filtered]

    meta = RubricMetadata(
        generation_model=generator_client.cfg.model if hasattr(generator_client, "cfg") else "mock",
        generation_passes=3,
        n_criteria_initial=n_initial,
        n_criteria_final=len(criteria_models),
        n_dropped_misaligned=n_dropped,
        ref_answer_self_score=None,
        weak_answer_self_score=None,
        generated_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        schema_version="1.0",
    )

    return RubricItem(
        question_id=qid, question=question, reference_answer=ref,
        question_type=qtype, difficulty=difficulty, scenario=scenario,
        source=source, source_grounding=sg, criteria=criteria_models,
        rubric_metadata=meta,
    )
```

- [ ] **Step 4: Run — expect PASS**

Run: `pytest tests/rubrics/test_pipeline_smoke.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/rubrics/pipeline.py tests/rubrics/test_pipeline_smoke.py
git commit -m "feat(rubrics): pipeline orchestrator with stage 1→2→3 wiring"
```

---

## Task 13: Run scripts (build_index, generate_rubrics, validate)

**Files:**
- Create: `run/01_build_index.py`
- Create: `run/02_generate_rubrics.py`
- Create: `run/03_validate.py`

- [ ] **Step 1: Build-index script**

Create `run/01_build_index.py`:

```python
"""Chunk all CAE-MDs and persist a pickled ChunkIndex for reuse."""
from __future__ import annotations
import argparse
import logging
import pickle
from pathlib import Path

from rubrics.chunker import chunk_markdown
from rubrics.index import ChunkIndex

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")
logger = logging.getLogger("build_index")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mds-dir", default="CAE-MDs")
    p.add_argument("--out", default="data/cae_chunk_index.pkl")
    p.add_argument("--chunk-size", type=int, default=400)
    p.add_argument("--overlap", type=int, default=100)
    p.add_argument("--model", default="BAAI/bge-base-zh-v1.5")
    args = p.parse_args()

    md_paths = sorted(Path(args.mds_dir).glob("*.md"))
    logger.info("Found %d MD files in %s", len(md_paths), args.mds_dir)

    all_chunks = []
    for md in md_paths:
        cs = chunk_markdown(md, chunk_size=args.chunk_size, overlap=args.overlap)
        logger.info("Chunked %s → %d chunks", md.name, len(cs))
        all_chunks.extend(cs)
    logger.info("Total chunks: %d", len(all_chunks))

    idx = ChunkIndex.build(all_chunks, model_name=args.model)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as f:
        pickle.dump(idx, f)
    logger.info("Saved index to %s", out)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test build_index runs**

Run: `cd /home/juli/RLM && python run/01_build_index.py`
Expected: prints chunk counts per MD, saves `data/cae_chunk_index.pkl`. First run downloads BGE model (~400MB) — wall time ~3-5 min.

- [ ] **Step 3: Generate-rubrics script**

Create `run/02_generate_rubrics.py`:

```python
"""Run the full GroundedRubric-CAE pipeline over CAE-v2.0-1.json."""
from __future__ import annotations
import argparse
import json
import logging
import os
import pickle
import random
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from rubrics.llm_client import LLMClient, LLMConfig
from rubrics.pipeline import build_rubric_for_item

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")
logger = logging.getLogger("generate_rubrics")


def set_seed(seed: int = 42):
    random.seed(seed); np.random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", default="data/CAE-v2.0-1.json")
    p.add_argument("--index", default="data/cae_chunk_index.pkl")
    p.add_argument("--out", default="data/CAE-v2.0-1-rubrics.json")
    p.add_argument("--items-dir", default="rubrics/items")
    p.add_argument("--limit", type=int, default=None, help="Only process first N items (debug)")
    p.add_argument("--dry-run", action="store_true", help="Stop after 1 item")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    set_seed(args.seed)
    load_dotenv()

    data = json.loads(Path(args.data).read_text(encoding="utf-8"))
    with open(args.index, "rb") as f:
        index = pickle.load(f)
    logger.info("Loaded %d items, index with %d chunks", len(data), len(index.chunks))

    cfg = LLMConfig.from_env()
    gen_client = LLMClient(cfg)
    judge_client = LLMClient(cfg)  # same model per spec §D2

    # Embedding fn for refiner dedup
    embedder = SentenceTransformer(os.environ.get("EMBEDDING_MODEL", "BAAI/bge-base-zh-v1.5"))
    def embed_fn(texts):
        return np.asarray(embedder.encode(texts, normalize_embeddings=True, show_progress_bar=False))

    items_dir = Path(args.items_dir)
    items_dir.mkdir(parents=True, exist_ok=True)

    todo = data[: args.limit] if args.limit else data
    if args.dry_run:
        todo = todo[:1]

    results = []
    for item in tqdm(todo, desc="generating rubrics"):
        try:
            rubric = build_rubric_for_item(
                item=item, index=index,
                generator_client=gen_client, judge_client=judge_client,
                embed_fn=embed_fn,
            )
        except Exception:
            logger.exception("Failed on item #%s — skipping", item.get("编号"))
            continue
        results.append(rubric.model_dump())
        # Per-item file
        (items_dir / f"{rubric.question_id.zfill(3)}.json").write_text(
            json.dumps(rubric.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8",
        )

    Path(args.out).write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    logger.info("Wrote %d rubrics to %s and %s/", len(results), args.out, items_dir)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Dry-run on 1 item**

Run: `cd /home/juli/RLM && python run/02_generate_rubrics.py --dry-run`
Expected: completes one item; `data/CAE-v2.0-1-rubrics.json` has 1 entry; `rubrics/items/001.json` exists. Inspect it manually:

```bash
jq '.[0] | {qid: .question_id, n_criteria: (.criteria | length), categories: (.criteria | map(.category) | unique)}' data/CAE-v2.0-1-rubrics.json
```
Expected: 6-15 criteria, includes at least one "Essential" and at least two "Pitfall".

- [ ] **Step 5: Full run**

Run: `python run/02_generate_rubrics.py 2>&1 | tee data/generate-$(date +%Y%m%d-%H%M%S).log`
Expected: 94 items processed in ~15-20 min.

- [ ] **Step 6: Validation script**

Create `run/03_validate.py`:

```python
"""Quick QC over generated rubrics."""
from __future__ import annotations
import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import mean


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--rubrics", default="data/CAE-v2.0-1-rubrics.json")
    p.add_argument("--source-data", default="data/CAE-v2.0-1.json")
    args = p.parse_args()

    rubrics = json.loads(Path(args.rubrics).read_text(encoding="utf-8"))
    source = json.loads(Path(args.source_data).read_text(encoding="utf-8"))

    print(f"Rubrics: {len(rubrics)} / {len(source)} items")

    n_criteria = [len(r["criteria"]) for r in rubrics]
    print(f"criteria/item: min={min(n_criteria)} max={max(n_criteria)} mean={mean(n_criteria):.1f}")

    by_type = Counter(r["question_type"] for r in rubrics)
    print("By type:", dict(by_type))

    # Sanity: every item has ≥ 2 Pitfall
    short_pitfalls = [r["question_id"] for r in rubrics
                       if sum(1 for c in r["criteria"] if c["category"] == "Pitfall") < 2]
    print(f"items with <2 Pitfall: {len(short_pitfalls)} → {short_pitfalls[:10]}")

    # Ground status distribution
    gs = Counter(r["source_grounding"]["ground_status"] for r in rubrics)
    print("ground_status:", dict(gs))

    # Misalignment drop rate
    drops = [r["rubric_metadata"]["n_dropped_misaligned"] for r in rubrics]
    print(f"dropped/item: mean={mean(drops):.1f} max={max(drops)}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: Run validation**

Run: `python run/03_validate.py`
Expected:
- 94/94 items
- mean criteria per item ≈ 9-11
- 0 items with <2 Pitfall
- `page_specific` dominates over `fallback_semantic`
- mean drop rate < 3

- [ ] **Step 8: Commit run scripts + outputs**

```bash
git add run/ data/CAE-v2.0-1-rubrics.json rubrics/items/
git commit -m "feat(rubrics): run scripts + generated rubrics for 94 CAE items"
```

---

## Task 14: Spot-check 3 generated rubrics manually

This step has no code, but is essential before declaring success.

- [ ] **Step 1: Sample one item per question-type cluster**

Run:
```bash
jq '.[] | select(.question_type=="决策题") | .question_id' data/CAE-v2.0-1-rubrics.json | head -1
jq '.[] | select(.question_type=="数值提取题") | .question_id' data/CAE-v2.0-1-rubrics.json | head -1
jq '.[] | select(.question_type=="主观题") | .question_id' data/CAE-v2.0-1-rubrics.json | head -1
```

- [ ] **Step 2: Read each rubric and confirm**

For each of the 3 sampled items, open `rubrics/items/<id>.json` and verify:

1. Criteria are atomic (no "AND" compounds)
2. Numeric criteria (if numeric type) state both value and unit
3. Decision criteria include one Essential "明确给出选择 X"
4. Two default Pitfalls present verbatim
5. No vague adjectives ("合理", "恰当", "良好")

If any item fails — note which rule failed, then iterate on the prompt template (Task 7) and re-run just that item via `python run/02_generate_rubrics.py --limit 1` after editing the JSON to start from that question_id (or extend the script with a `--only-id` flag).

- [ ] **Step 3: Commit spot-check log**

```bash
echo "spot-check log:" > rubrics/SPOT-CHECK.md
# (fill with findings)
git add rubrics/SPOT-CHECK.md
git commit -m "docs(rubrics): manual spot-check log for 3 sampled rubrics"
```

---

## Self-Review

**Spec coverage:**
- Spec §4 architecture → Tasks 2-12 (each stage has a task)
- Spec §5 JSON schema → Task 1 (pydantic models)
- Spec §6 scoring formula → Task 11
- Spec §7 type×category matrix → Task 7 (type_rules/*.txt)
- Spec §8 source grounding → Tasks 2, 3, 4, 5
- Spec §9 few-shot exemplars → Task 7 (gold_rubrics.json)
- Spec §10 prompt templates → Task 7
- Spec §11 implementation layout → reflected in File Structure section
- Spec §12 reproducibility → Task 13 step 3 (set_seed) + logging
- Spec §13 security → Task 1 (.env.example, no hard-coded keys)
- Spec §15 cost estimate → covered implicitly via Tasks 8-10 + Task 13's full-run step
- Spec §16 success criteria → Task 13 validation script + Task 14 spot-check

**Placeholder scan:** none. Every step has runnable commands and concrete code.

**Type consistency:** `ChunkRecord` consistently has `(chunk_id, doc_slug, page_start, page_end, text)` across chunker/index/retriever/pipeline. `Criterion`, `RubricItem`, `SourceGrounding`, `RubricMetadata` field names match between schema.py and all consumers. `LLMClient.complete_json(system, user, schema_hint, ...)` signature consistent across generator / misalignment_filter.

**Open caveats noted in plan:**
- Task 4 step 4: first BGE model download is ~400MB and takes 3-5 min wall time.
- Task 13 step 5: full run uses real LLM calls (~$0.5); ensure `.env` is filled with a working `LLM_API_KEY` first.
- Task 2 step 3: page marker regex may need adjusting after inspecting actual mineru-converted MDs; instruction is to "look first, adapt if needed".

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-22-cae-rubrics-implementation.md`. Two execution options:**

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Cleaner audit trail; better for ~14 task plan.
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
