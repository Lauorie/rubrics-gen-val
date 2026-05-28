# CAE ReAct Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a text-based ReAct agent to the existing `cae-rag` package, run it on the 94-question CAE benchmark, and extend the comparison to 3-way (RAG vs ReAct vs RLM v3) — all under the same model, knowledge base, and `cae-rubrics-eval` judge.

**Architecture:** A new `cae_rag/react.py` (frozen `ReactConfig`, pure parse/format/read helpers, `ReactAgent` loop) reusing the existing `HybridRetriever`, `Config`, and OpenAI-compatible client as its `search` backend and LLM. A `scripts/run_react.py` runs the loop over 94 questions → `predictions_react.jsonl`. `compare.py` gains a 3-way report builder; `compare_results.py` gains a `--react-predictions` flag and reuse-existing-scores logic; the scoring report's Section 8 is updated to 3-way.

**Tech Stack:** Python 3.12, existing cae-rag stack (pymilvus/Milvus Lite, openai SDK via aiberm, jieba, rank-bm25, tiktoken), pytest.

---

## Reference facts (verified against the repo)

- **Existing modules** (done, 15 tests passing): `cae_rag/config.py` (`Config.from_env`, `set_seed`), `cae_rag/ingest.py` (`Chunk(chunk_id, doc, text, token_start, token_end)` frozen dataclass; `load_chunks`/`save_chunks` live in index.py), `cae_rag/index.py` (`COLLECTION="cae_chunks"`, `load_chunks`, `load_bm25`, `make_openai_client`), `cae_rag/retrieve.py` (`HybridRetriever(milvus, bm25, chunk_ids, chunk_lookup, embed_query, top_k, candidate_pool, rrf_k)`; `.retrieve(query) -> list[{chunk_id, text, doc}]`), `cae_rag/generate.py`.
- **Built artifacts already present** in `cae-rag/outputs/`: `chunks.jsonl` (657 chunks), `cae_rag.db` (Milvus Lite), `bm25.pkl`, plus `eval_rag.json` and `eval_rlm_v3.json` from the prior run. **Reuse them — do not rebuild the index.**
- **`run_rag.py` pattern**: opens `MilvusClient(db)`, calls `milvus.load_collection(COLLECTION)` (required before search in a fresh process), builds an `embed_query` closure, constructs `HybridRetriever`, runs `generate_all` over questions read by `load_questions` (ONLY `item_idx`+`question` — anti-cheat).
- **`HybridRetriever.retrieve`** returns exactly `top_k` dicts. For ReAct, build the retriever with `top_k = ReactConfig.search_k`.
- **chunk_id format**: `"{doc}::{idx}"` with integer idx; neighbors are `"{doc}::{idx±1}"`. Doc names may contain spaces but never `"::"`, so `rpartition("::")` splits cleanly.
- **`compare.py`** currently has `load_aggregate`, `extract_rlm_predictions`, `_fmt(x)`, `_delta(a,b)`, `build_comparison_md(rag, rlm)`. `_delta` returns `f"{d:+.3f}"`.
- **`compare_results.py`** currently has `score(predictions, out, concurrency, eval_dir)` and a `main()` that scores RAG then RLM v3 then writes 2-way `comparison.md`. Module constants `EVAL_DIR`, `EVAL_PY`, `RLM_V3`. CLI args `--out-dir`, `--concurrency`, `--eval-dir`, `--rlm-v3`.
- **eval aggregate keys**: `mean_anchored, mean_score, n_scored_ok, n_errors, by_question_type{qt:{n,mean,mean_anchored}}, by_difficulty{d:{n,mean,mean_anchored}}, by_criterion_type, judge_model`.
- Work from `/home/juli/RLM/cae-rag`; venv `.venv`; repo root `/home/juli/RLM`; commit to `main`. Run tests with `.venv/bin/python -m pytest`.

---

## File Structure

```
cae_rag/react.py           # NEW: ReactConfig, parse_action, parse_final,
                           #      format_search_obs, read_chunk, ReactAgent
cae_rag/compare.py         # MODIFY: add build_comparison_md_3way (keep 2-way)
cae_rag/__init__.py        # MODIFY: export ReactAgent, ReactConfig, build_comparison_md_3way
scripts/run_react.py       # NEW: run ReAct over 94 Qs -> predictions_react.jsonl
scripts/compare_results.py # MODIFY: --react-predictions + reuse-existing + 3-way report
tests/test_react.py        # NEW: parse/read/format + one ReactAgent loop test
tests/test_compare.py      # MODIFY: add a 3-way builder test
data/CAE-v2.0-1 RLM Scoring Report.md  # MODIFY (final task): Section 8 -> 3-way
```

---

## Task 1: react.py — pure helpers (parse / format / read)

**Files:**
- Create: `cae-rag/cae_rag/react.py` (helpers + ReactConfig only this task; ReactAgent in Task 2)
- Test: `cae-rag/tests/test_react.py`

- [ ] **Step 1: Write the failing test**

Create `cae-rag/tests/test_react.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/juli/RLM/cae-rag && .venv/bin/python -m pytest tests/test_react.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'cae_rag.react'`.

- [ ] **Step 3: Write react.py (helpers only)**

Create `cae-rag/cae_rag/react.py`:

```python
"""Text-based ReAct agent over the CAE knowledge base."""
from __future__ import annotations
import logging
import re
from dataclasses import dataclass
from typing import Any, Callable

from cae_rag.ingest import Chunk

logger = logging.getLogger(__name__)

_ACTION_RE = re.compile(r"Action:\s*(search|read)\s*\[\s*(.*?)\s*\]", re.IGNORECASE | re.DOTALL)
_FINAL_RE = re.compile(r"Final Answer:\s*(.+)", re.IGNORECASE | re.DOTALL)

SYSTEM_TEMPLATE = (
    "你是 CAE / 工程仿真领域专家，通过“思考-行动-观察”循环回答问题。\n"
    "知识库包含以下文档：\n{doc_list}\n\n"
    "你可以使用两个工具：\n"
    "- search[查询词]：在知识库中混合检索，返回若干片段指针（chunk_id | 文档 | 摘要）。\n"
    "- read[chunk_id]：读取该 chunk 及其相邻上下文的完整文本。\n\n"
    "每一步只能输出以下三种格式之一（且仅一个 Action）：\n"
    "Thought: <你的推理>\nAction: search[<查询词>]\n"
    "或\n"
    "Thought: <你的推理>\nAction: read[<chunk_id>]\n"
    "或\n"
    "Final Answer: <用中文给出的最终答案>\n\n"
    "只能依据检索/读取得到的资料作答，不得编造；资料不足时如实说明。"
    "答案要准确、聚焦，保留关键公式、数值与对比。"
)


@dataclass(frozen=True)
class ReactConfig:
    max_steps: int = 6
    search_k: int = 5
    snippet_chars: int = 240
    read_window: int = 1
    temperature: float = 0.0


def parse_action(text: str) -> tuple[str, str] | None:
    """Return (tool, arg) from the first Action[...] match, or None."""
    m = _ACTION_RE.search(text)
    if not m:
        return None
    return m.group(1).lower(), m.group(2).strip()


def parse_final(text: str) -> str | None:
    """Return the text after 'Final Answer:', or None if absent."""
    m = _FINAL_RE.search(text)
    if not m:
        return None
    return m.group(1).strip()


def format_search_obs(hits: list[dict], snippet_chars: int) -> str:
    """Format hybrid-search hits as one pointer line each: [chunk_id | doc | snippet]."""
    if not hits:
        return "（无检索结果）"
    lines = []
    for h in hits:
        snippet = h["text"][:snippet_chars].replace("\n", " ")
        lines.append(f"[{h['chunk_id']} | {h['doc']} | {snippet}]")
    return "\n".join(lines)


def read_chunk(chunk_id: str, chunks_by_id: dict[str, Chunk], window: int) -> str:
    """Return full text of chunk_id plus `window` neighbors each side (same doc)."""
    if chunk_id not in chunks_by_id:
        return "未找到该 chunk_id"
    doc, _, idx_s = chunk_id.rpartition("::")
    try:
        idx = int(idx_s)
    except ValueError:
        return f"【{chunk_id}】\n{chunks_by_id[chunk_id].text}"
    parts = []
    for j in range(idx - window, idx + window + 1):
        cid = f"{doc}::{j}"
        if cid in chunks_by_id:
            parts.append(f"【{cid}】\n{chunks_by_id[cid].text}")
    return "\n\n".join(parts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/juli/RLM/cae-rag && .venv/bin/python -m pytest tests/test_react.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
cd /home/juli/RLM && git add cae-rag/cae_rag/react.py cae-rag/tests/test_react.py && git commit -m "feat(cae-rag): ReAct parse/format/read helpers + ReactConfig"
```

---

## Task 2: react.py — ReactAgent loop

**Files:**
- Modify: `cae-rag/cae_rag/react.py` (append `ReactAgent`)
- Test: `cae-rag/tests/test_react.py` (append a loop test)

- [ ] **Step 1: Append the failing test**

Append to `cae-rag/tests/test_react.py`:

```python
from cae_rag.react import ReactAgent


class _Msg:
    def __init__(self, content): self.content = content
class _Choice:
    def __init__(self, content): self.message = _Msg(content)
class _Resp:
    def __init__(self, content): self.choices = [_Choice(content)]
class _Chat:
    def __init__(self, scripted): self.scripted = list(scripted); self.calls = 0
    def create(self, **kw): r = _Resp(self.scripted[self.calls]); self.calls += 1; return r
class _Client:
    def __init__(self, scripted): self.chat = type("C", (), {"completions": _Chat(scripted)})()
class _FakeRetriever:
    def retrieve(self, q): return [{"chunk_id": "d::0", "doc": "d", "text": "附加质量全文内容"}]


def test_react_agent_runs_search_read_then_final():
    scripted = [
        "Thought: 先检索\nAction: search[附加质量]",
        "Thought: 读取细节\nAction: read[d::0]",
        "Final Answer: 这是最终答案",
    ]
    client = _Client(scripted)
    chunks = [Chunk("d::0", "d", "附加质量全文内容", 0, 1)]
    agent = ReactAgent(client=client, retriever=_FakeRetriever(), chunks=chunks,
                       cfg=ReactConfig(), gen_model="deepseek/deepseek-v4-flash",
                       doc_names=["d"])
    res = agent.answer("附加质量为何导致不稳定？")
    assert res["answer"] == "这是最终答案"
    assert res["steps"] == 3
    tools = [t["tool"] for t in res["trace"]]
    assert tools == ["search", "read"]


def test_react_agent_forces_answer_on_budget_exhaustion():
    # every step is a search; never a Final Answer until the forced call
    scripted = ["Thought: t\nAction: search[q]"] * 6 + ["Final Answer: 兜底答案"]
    client = _Client(scripted)
    chunks = [Chunk("d::0", "d", "x", 0, 1)]
    agent = ReactAgent(client=client, retriever=_FakeRetriever(), chunks=chunks,
                       cfg=ReactConfig(max_steps=6), gen_model="m", doc_names=["d"])
    res = agent.answer("q?")
    assert res["answer"] == "兜底答案"
    assert res["steps"] == 6
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/juli/RLM/cae-rag && .venv/bin/python -m pytest tests/test_react.py -k react_agent -v`
Expected: FAIL with `ImportError: cannot import name 'ReactAgent'`.

- [ ] **Step 3: Append ReactAgent to react.py**

Append to `cae-rag/cae_rag/react.py`:

```python
class ReactAgent:
    """Text-based ReAct loop: Thought/Action(search|read)/Observation, then Final Answer."""

    def __init__(self, client: Any, retriever: Any, chunks: list[Chunk], cfg: ReactConfig,
                 gen_model: str, doc_names: list[str]):
        self.client = client
        self.retriever = retriever
        self.cfg = cfg
        self.gen_model = gen_model
        self.chunks_by_id = {c.chunk_id: c for c in chunks}
        self.system = SYSTEM_TEMPLATE.format(doc_list="\n".join(f"- {d}" for d in doc_names))

    def _llm(self, scratchpad: str) -> str:
        resp = self.client.chat.completions.create(
            model=self.gen_model, temperature=self.cfg.temperature,
            messages=[{"role": "system", "content": self.system},
                      {"role": "user", "content": scratchpad}],
        )
        return (resp.choices[0].message.content or "").strip()

    def _run_tool(self, tool: str, arg: str) -> str:
        if tool == "search":
            hits = self.retriever.retrieve(arg)
            return format_search_obs(hits, self.cfg.snippet_chars)
        if tool == "read":
            return read_chunk(arg, self.chunks_by_id, self.cfg.read_window)
        return f"未知工具: {tool}"

    def answer(self, question: str) -> dict:
        scratchpad = f"问题：{question}\n"
        trace: list[dict] = []
        for step in range(self.cfg.max_steps):
            out = self._llm(scratchpad)
            final = parse_final(out)
            if final is not None:
                return {"answer": final, "steps": step + 1, "trace": trace}
            action = parse_action(out)
            if action is None:
                # one reformat nudge
                scratchpad += ("（上一步输出格式不正确）请仅用 "
                               "'Action: search[...]'、'Action: read[...]' 或 "
                               "'Final Answer: ...' 之一回复。\n")
                out = self._llm(scratchpad)
                final = parse_final(out)
                if final is not None:
                    return {"answer": final, "steps": step + 1, "trace": trace}
                action = parse_action(out)
                if action is None:
                    return {"answer": out, "steps": step + 1, "trace": trace}
            tool, arg = action
            obs = self._run_tool(tool, arg)
            trace.append({"tool": tool, "arg": arg})
            scratchpad += f"{out}\nObservation: {obs}\n"
        # budget exhausted -> force a final answer
        scratchpad += "\n请基于以上观察，现在直接给出 Final Answer（中文）。\n"
        forced = self._llm(scratchpad)
        final = parse_final(forced)
        return {"answer": final if final is not None else forced,
                "steps": self.cfg.max_steps, "trace": trace}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/juli/RLM/cae-rag && .venv/bin/python -m pytest tests/test_react.py -v`
Expected: 7 passed (5 helper + 2 agent).

- [ ] **Step 5: Commit**

```bash
cd /home/juli/RLM && git add cae-rag/cae_rag/react.py cae-rag/tests/test_react.py && git commit -m "feat(cae-rag): ReactAgent loop (search/read/final, nudge+forced-answer)"
```

---

## Task 3: scripts/run_react.py + smoke

**Files:**
- Create: `cae-rag/scripts/run_react.py`

- [ ] **Step 1: Write run_react.py**

Create `cae-rag/scripts/run_react.py`:

```python
"""CLI: run the ReAct agent over the 94 questions -> predictions_react.jsonl."""
from __future__ import annotations
import argparse
import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv
from pymilvus import MilvusClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cae_rag.config import Config, set_seed
from cae_rag.index import COLLECTION, load_bm25, load_chunks, make_openai_client
from cae_rag.react import ReactAgent, ReactConfig
from cae_rag.retrieve import HybridRetriever

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")
logger = logging.getLogger("run_react")


def load_questions(path: Path) -> list[dict]:
    """Read ONLY item_idx + question. Never reference_answer/criteria (anti-cheat)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return [{"item_idx": r["item_idx"], "question": r["question"]} for r in data]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", default="/home/juli/RLM/data/CAE-v2.0-1-rubrics.json", type=Path)
    p.add_argument("--out-dir", default="outputs", type=Path)
    p.add_argument("--limit", type=int, default=0, help="0 = all; N = first N items (smoke)")
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--max-steps", type=int, default=6)
    args = p.parse_args()

    load_dotenv()
    set_seed(42)
    cfg = Config.from_env()
    rcfg = ReactConfig(max_steps=args.max_steps)

    chunks = load_chunks(str(args.out_dir / "chunks.jsonl"))
    chunk_lookup = {c.chunk_id: (c.text, c.doc) for c in chunks}
    bm25, chunk_ids = load_bm25(str(args.out_dir / "bm25.pkl"))
    milvus = MilvusClient(str(args.out_dir / "cae_rag.db"))
    milvus.load_collection(COLLECTION)
    client = make_openai_client(cfg.api_key, cfg.base_url)

    def embed_query(q: str) -> list[float]:
        return client.embeddings.create(model=cfg.embedding_model, input=[q]).data[0].embedding

    retriever = HybridRetriever(
        milvus=milvus, bm25=bm25, chunk_ids=chunk_ids, chunk_lookup=chunk_lookup,
        embed_query=embed_query, top_k=rcfg.search_k,
        candidate_pool=cfg.candidate_pool, rrf_k=cfg.rrf_k,
    )
    doc_names = sorted({c.doc for c in chunks})
    agent = ReactAgent(client=client, retriever=retriever, chunks=chunks, cfg=rcfg,
                       gen_model=cfg.gen_model, doc_names=doc_names)

    items = load_questions(args.dataset)
    if args.limit:
        items = items[: args.limit]
    logger.info("ReAct answering %d questions (max_steps=%d)", len(items), rcfg.max_steps)

    def _one(item: dict) -> dict:
        try:
            res = agent.answer(item["question"])
            return {"item_idx": item["item_idx"], "answer": res["answer"], "steps": res["steps"]}
        except Exception as e:  # noqa: BLE001 - per-item failure, keep going
            logger.error("item %s failed: %s", item["item_idx"], e)
            return {"item_idx": item["item_idx"], "answer": "", "steps": 0, "error": str(e)}

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        results = list(ex.map(_one, items))
    results.sort(key=lambda r: r["item_idx"])

    out_path = args.out_dir / "predictions_react.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    n_empty = sum(1 for r in results if not r["answer"])
    avg_steps = sum(r["steps"] for r in results) / max(1, len(results))
    logger.info("Wrote %d predictions to %s (%d empty, avg_steps=%.2f)",
                len(results), out_path, n_empty, avg_steps)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke run on 3 questions (real LLM calls)**

Run:
```bash
cd /home/juli/RLM/cae-rag && .venv/bin/python scripts/run_react.py --limit 3 2>&1 | tee outputs/run_react_smoke.log
```
Expected: "ReAct answering 3 questions", then "Wrote 3 predictions ... (0 empty, avg_steps=N)". The benign Milvus `AllocTimestamp` gRPC line may appear — ignore it. Inspect:
```bash
cd /home/juli/RLM/cae-rag && .venv/bin/python -c "
import json
rows=[json.loads(l) for l in open('outputs/predictions_react.jsonl')]
print('rows', len(rows))
for r in rows: print('item', r['item_idx'], 'steps', r['steps'], 'ans_len', len(r['answer']))
assert all(isinstance(r['item_idx'],int) and isinstance(r['answer'],str) for r in rows)
print('preview:', rows[0]['answer'][:200])
"
```
Expected: 3 rows, non-empty Chinese answers, `steps` between 1 and 6. If all answers are empty or steps are always 1 with no tool use, the model isn't following the ReAct format — report DONE_WITH_CONCERNS with a sample raw answer so the prompt/parser can be adjusted.

- [ ] **Step 3: Verify no reference leakage**

Run: `cd /home/juli/RLM/cae-rag && grep -c "reference_answer\|criteria" scripts/run_react.py`
Expected: `0` (loader only reads item_idx + question; the only match would be the docstring, which the reviewer confirms is not a code path).

- [ ] **Step 4: Commit**

```bash
cd /home/juli/RLM && git add cae-rag/scripts/run_react.py && git commit -m "feat(cae-rag): run_react CLI (ReAct over 94 Qs -> predictions_react.jsonl)"
```

---

## Task 4: compare.py — 3-way report builder

**Files:**
- Modify: `cae-rag/cae_rag/compare.py` (add `build_comparison_md_3way`; keep everything else)
- Test: `cae-rag/tests/test_compare.py` (append a test)

- [ ] **Step 1: Append the failing test**

Append to `cae-rag/tests/test_compare.py`:

```python
from cae_rag.compare import build_comparison_md_3way

def test_build_comparison_md_3way():
    def agg(a):
        return {"mean_anchored": a, "mean_score": a - 0.01, "n_scored_ok": 94, "n_errors": 0,
                "by_question_type": {"主观题": {"n": 10, "mean": a, "mean_anchored": a}},
                "by_difficulty": {"困难": {"n": 5, "mean": a, "mean_anchored": a}},
                "judge_model": "openai/gpt-5.4-mini"}
    rag, react, rlm = agg(0.427), agg(0.55), agg(0.675)
    md = build_comparison_md_3way(rag, react, rlm)
    assert "RAG" in md and "ReAct" in md and "RLM v3" in md
    assert "0.427" in md and "0.550" in md and "0.675" in md
    # deltas vs RLM v3 present (negative)
    assert "-0.248" in md  # RAG - RLM
    assert "-0.125" in md  # ReAct - RLM
    assert "主观题" in md and "困难" in md
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/juli/RLM/cae-rag && .venv/bin/python -m pytest tests/test_compare.py -k 3way -v`
Expected: FAIL with `ImportError: cannot import name 'build_comparison_md_3way'`.

- [ ] **Step 3: Add build_comparison_md_3way to compare.py**

Append to `cae-rag/cae_rag/compare.py` (after `build_comparison_md`; reuse the existing `_fmt`, `_delta`, `PUBLISHED_RLM`):

```python
def build_comparison_md_3way(rag: dict, react: dict, rlm: dict) -> str:
    """3-way report: RAG vs ReAct vs RLM v3, all scored under the same judge."""
    lines: list[str] = []
    lines.append("# CAE: RAG vs ReAct vs RLM v3 — Comparison\n")
    lines.append(f"All scored with `cae-rubrics-eval`, judge `{rag.get('judge_model')}`, identical anchors.\n")
    lines.append("## Headline (mean_anchored — primary metric)\n")
    lines.append("| System | mean_anchored | mean_score | n_ok | n_err | Δ vs RLM v3 |")
    lines.append("|---|---|---|---|---|---|")
    lines.append(f"| RAG (hybrid top-5) | {_fmt(rag.get('mean_anchored'))} | {_fmt(rag.get('mean_score'))} | {rag.get('n_scored_ok')} | {rag.get('n_errors')} | {_delta(rag.get('mean_anchored'), rlm.get('mean_anchored'))} |")
    lines.append(f"| ReAct (iterative) | {_fmt(react.get('mean_anchored'))} | {_fmt(react.get('mean_score'))} | {react.get('n_scored_ok')} | {react.get('n_errors')} | {_delta(react.get('mean_anchored'), rlm.get('mean_anchored'))} |")
    lines.append(f"| RLM v3 | {_fmt(rlm.get('mean_anchored'))} | {_fmt(rlm.get('mean_score'))} | {rlm.get('n_scored_ok')} | {rlm.get('n_errors')} | — |")
    lines.append("")

    def _section(title: str, key: str) -> None:
        lines.append(f"## By {title} (mean_anchored)\n")
        lines.append("| " + title + " | RAG | ReAct | RLM v3 |")
        lines.append("|---|---|---|---|")
        groups = sorted(set(rag.get(key, {})) | set(react.get(key, {})) | set(rlm.get(key, {})))
        for g in groups:
            ga = rag.get(key, {}).get(g, {}).get("mean_anchored")
            ge = react.get(key, {}).get(g, {}).get("mean_anchored")
            gl = rlm.get(key, {}).get(g, {}).get("mean_anchored")
            lines.append(f"| {g} | {_fmt(ga)} | {_fmt(ge)} | {_fmt(gl)} |")
        lines.append("")

    _section("question_type", "by_question_type")
    _section("difficulty", "by_difficulty")

    lines.append("## Secondary context — published RLM (judge gpt-5.5, NOT comparable)\n")
    lines.append("| version | published mean_anchored |")
    lines.append("|---|---|")
    for v, s in PUBLISHED_RLM.items():
        lines.append(f"| {v} | {s:.3f} |")
    lines.append("\n> Published numbers used judge `gpt-5.5`; the headline above used "
                 "`gpt-5.4-mini`. Only compare within the headline table.\n")
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/juli/RLM/cae-rag && .venv/bin/python -m pytest tests/test_compare.py -v`
Expected: 3 passed (2 existing + 1 new 3-way).

- [ ] **Step 5: Commit**

```bash
cd /home/juli/RLM && git add cae-rag/cae_rag/compare.py cae-rag/tests/test_compare.py && git commit -m "feat(cae-rag): 3-way comparison report builder"
```

---

## Task 5: compare_results.py — --react-predictions + reuse-existing

**Files:**
- Modify: `cae-rag/scripts/compare_results.py`

- [ ] **Step 1: Rewrite compare_results.py main with reuse + 3-way**

Replace the body of `cae-rag/scripts/compare_results.py` with (keep the header imports + `score` helper as they are; replace from the `import` line for `build_comparison_md` and the `main()` function):

Full new file content:

```python
"""CLI: score RAG (+ optional ReAct), re-score RLM v3, then write comparison.md.

Reuses existing eval_*.json unless --force, so re-runs are cheap.
"""
from __future__ import annotations
import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cae_rag.compare import (
    build_comparison_md, build_comparison_md_3way, extract_rlm_predictions, load_aggregate,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")
logger = logging.getLogger("compare_results")

EVAL_DIR = Path("/home/juli/RLM/cae-rubrics-eval")
RLM_V3 = Path("/home/juli/RLM/data/CAE-v2.0-1-rubrics-v3.json")


def score(predictions: Path, out: Path, concurrency: int, eval_dir: Path) -> None:
    """Invoke cae-rubrics-eval/score.py from inside its dir (so its .env + anchors resolve)."""
    cmd = [str(eval_dir / ".venv/bin/python"), "score.py", "--predictions", str(predictions.resolve()),
           "--out", str(out.resolve()), "--concurrency", str(concurrency)]
    logger.info("Scoring -> %s", out)
    subprocess.run(cmd, cwd=str(eval_dir), check=True)


def ensure_scored(predictions: Path, out: Path, concurrency: int, eval_dir: Path, force: bool) -> None:
    """Score predictions unless an eval json already exists (and not force)."""
    if out.exists() and not force:
        logger.info("Reusing existing %s", out)
        return
    score(predictions, out, concurrency, eval_dir)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out-dir", default="outputs", type=Path)
    p.add_argument("--concurrency", type=int, default=16)
    p.add_argument("--eval-dir", default=EVAL_DIR, type=Path, help="Path to cae-rubrics-eval")
    p.add_argument("--rlm-v3", default=RLM_V3, type=Path, help="RLM v3 answers JSON")
    p.add_argument("--react-predictions", default=None, type=Path,
                   help="If given, also score ReAct predictions and emit a 3-way report")
    p.add_argument("--force", action="store_true", help="Re-score even if eval_*.json exists")
    args = p.parse_args()
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    # 1) RAG
    ensure_scored(out / "predictions.jsonl", out / "eval_rag.json",
                  args.concurrency, args.eval_dir, args.force)

    # 2) RLM v3 — build predictions only if we actually need to score
    if args.force or not (out / "eval_rlm_v3.json").exists():
        v3 = json.loads(args.rlm_v3.read_text(encoding="utf-8"))
        rlm_path = out / "rlm_v3_predictions.jsonl"
        with open(rlm_path, "w", encoding="utf-8") as f:
            for r in extract_rlm_predictions(v3):
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        score(rlm_path, out / "eval_rlm_v3.json", args.concurrency, args.eval_dir)
    else:
        logger.info("Reusing existing %s", out / "eval_rlm_v3.json")

    # 3) optional ReAct
    react_agg = None
    if args.react_predictions is not None:
        ensure_scored(args.react_predictions, out / "eval_react.json",
                      args.concurrency, args.eval_dir, args.force)
        react_agg = load_aggregate(str(out / "eval_react.json"))

    # 4) report
    rag_agg = load_aggregate(str(out / "eval_rag.json"))
    rlm_agg = load_aggregate(str(out / "eval_rlm_v3.json"))
    if react_agg is not None:
        md = build_comparison_md_3way(rag_agg, react_agg, rlm_agg)
        logger.info("RAG=%s  ReAct=%s  RLM v3=%s (anchored)",
                    rag_agg.get("mean_anchored"), react_agg.get("mean_anchored"), rlm_agg.get("mean_anchored"))
    else:
        md = build_comparison_md(rag_agg, rlm_agg)
        logger.info("RAG anchored=%s  RLM v3 anchored=%s",
                    rag_agg.get("mean_anchored"), rlm_agg.get("mean_anchored"))
    (out / "comparison.md").write_text(md, encoding="utf-8")
    logger.info("Wrote %s", out / "comparison.md")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify it parses and is backward compatible**

Run:
```bash
cd /home/juli/RLM/cae-rag && .venv/bin/python scripts/compare_results.py --help
```
Expected: help shows `--react-predictions` and `--force`. (Do NOT run actual scoring here.)

Run the full unit suite to confirm nothing broke:
```bash
cd /home/juli/RLM/cae-rag && .venv/bin/python -m pytest -q
```
Expected: all pass (config 3, ingest 3, retrieve 4, index 1, generate 2, compare 3, react 7 = 23).

- [ ] **Step 3: Commit**

```bash
cd /home/juli/RLM && git add cae-rag/scripts/compare_results.py && git commit -m "feat(cae-rag): compare_results --react-predictions + reuse-existing scores + 3-way"
```

---

## Task 6: Full ReAct run + 3-way comparison + report update

**Files:**
- Modify: `cae-rag/cae_rag/__init__.py` (export ReAct + 3-way builder)
- Modify: `data/CAE-v2.0-1 RLM Scoring Report.md` (Section 8 -> 3-way)

- [ ] **Step 1: Export new public API**

Edit `cae-rag/cae_rag/__init__.py` — add these imports and `__all__` entries (keep all existing ones):

```python
from cae_rag.react import ReactAgent, ReactConfig
from cae_rag.compare import build_comparison_md_3way
```
Add to `__all__`: `"ReactAgent", "ReactConfig", "build_comparison_md_3way"`.

Verify: `cd /home/juli/RLM/cae-rag && .venv/bin/python -c "import cae_rag; print('ReactAgent' in cae_rag.__all__ and 'build_comparison_md_3way' in cae_rag.__all__)"` → `True`.

- [ ] **Step 2: Run the full unit suite**

Run: `cd /home/juli/RLM/cae-rag && .venv/bin/python -m pytest -q`
Expected: 23 passed.

- [ ] **Step 3: Run ReAct over all 94 questions (long, real LLM calls)**

Run: `cd /home/juli/RLM/cae-rag && .venv/bin/python scripts/run_react.py --workers 8 2>&1 | tee outputs/run_react.log`
Expected: "ReAct answering 94 questions", then "Wrote 94 predictions ... (0 empty, avg_steps=N)". Be patient (ReAct makes several LLM calls per question). If a handful error/empty due to proxy timeouts, re-run (idempotent). Quick check:
```bash
cd /home/juli/RLM/cae-rag && .venv/bin/python -c "import json; r=[json.loads(l) for l in open('outputs/predictions_react.jsonl')]; print('rows',len(r),'empty',sum(1 for x in r if not x['answer']),'avg_steps',round(sum(x['steps'] for x in r)/len(r),2))"
```
Expected: rows 94, empty 0.

- [ ] **Step 4: Score ReAct + build 3-way comparison (reuses existing RAG/RLM scores)**

Run: `cd /home/juli/RLM/cae-rag && .venv/bin/python scripts/compare_results.py --react-predictions outputs/predictions_react.jsonl --concurrency 16 2>&1 | tee outputs/compare_3way.log`
Expected: logs "Reusing existing outputs/eval_rag.json" and "Reusing existing outputs/eval_rlm_v3.json", scores ReAct, then "RAG=… ReAct=… RLM v3=… (anchored)" and "Wrote outputs/comparison.md".

- [ ] **Step 5: Verify ReAct eval + print the 3-way report**

Run:
```bash
cd /home/juli/RLM/cae-rag && .venv/bin/python -c "
import json
a=json.load(open('outputs/eval_react.json'))['aggregate']
print('ReAct anchored', a['mean_anchored'], 'raw', a['mean_score'], 'n_ok', a['n_scored_ok'], 'n_err', a['n_errors'])
assert a['n_scored_ok']==94, a
print('VERIFY OK')
" && echo "--- comparison.md ---" && cat outputs/comparison.md
```
Expected: ReAct `n_scored_ok == 94`; the 3-way comparison.md prints with all three systems.

- [ ] **Step 6: Update the scoring report Section 8 to 3-way**

The report `data/CAE-v2.0-1 RLM Scoring Report.md` currently has a 2-way Section 8 (RAG vs RLM v3). Update it to 3-way using the ACTUAL numbers now in `cae-rag/outputs/comparison.md` and `cae-rag/outputs/eval_react.json`:
- In **8.2 总体得分** table, add a `ReAct (iterative)` row with its `mean_score`/`mean_anchored`/`n_ok`/`n_err`, and add its Δ vs RLM v3.
- In **8.3 按题型** and **8.4 按难度** tables, add a `ReAct` column between RAG and RLM v3 (values from `eval_react.json` aggregate `by_question_type` / `by_difficulty` `mean_anchored`).
- In **8.5 criterion_type** table, add a `ReAct` column (from `by_criterion_type` `met_rate`).
- Add a one-paragraph note in **8.6 结论** summarizing where ReAct lands relative to RAG and RLM v3 (e.g., whether iteration closes the gap).
Pull every number from the JSON aggregate (do not eyeball); use the same 3-decimal / percent formatting already in Section 8. Read `cae-rag/outputs/eval_react.json` for the exact by-group values:
```bash
cd /home/juli/RLM/cae-rag && .venv/bin/python -c "
import json; a=json.load(open('outputs/eval_react.json'))['aggregate']
print('headline', round(a['mean_score'],3), round(a['mean_anchored'],3), a['n_scored_ok'], a['n_errors'])
print('by_qt', {k:round(v['mean_anchored'],3) for k,v in a['by_question_type'].items()})
print('by_diff', {k:round(v['mean_anchored'],3) for k,v in a['by_difficulty'].items()})
print('by_ct', {k:round(v['met_rate']*100,1) for k,v in a['by_criterion_type'].items()})
"
```

- [ ] **Step 7: Commit code + report**

```bash
cd /home/juli/RLM && git add cae-rag/cae_rag/__init__.py "data/CAE-v2.0-1 RLM Scoring Report.md" && git commit -m "feat(cae-rag): export ReAct API; 3-way run complete; report Section 8 -> 3-way"
```
(`outputs/` stays gitignored. The report file was previously untracked; this commit adds it. Confirm `git status` before committing.)

---

## Self-Review notes

- **Spec coverage:** §2 loop → Task 2 (ReactAgent: final/action/nudge/forced). §3 tools → Task 1 (format_search_obs, read_chunk) + Task 2 (`_run_tool`) + Task 3 (retriever top_k=search_k, doc_names in prompt). §4 components → react.py (T1,T2), run_react.py (T3), compare 3-way (T4), compare_results reuse+flag (T5), __init__ + report (T6). §5 reproducibility → set_seed, temp 0, steps recorded, reuse index. §6 testing → T1 (5 helper tests), T2 (2 loop tests incl. forced-answer), T4 (3-way builder). §8 success criteria → T6 verify (n_scored_ok==94, 0 empty, 3-way report + report update).
- **Anti-cheat:** run_react `load_questions` reads only item_idx+question (T3 Step 3 greps).
- **Type consistency:** `ReactConfig` fields, `parse_action -> tuple[str,str]|None`, `parse_final -> str|None`, `read_chunk(chunk_id, chunks_by_id, window)`, `format_search_obs(hits, snippet_chars)`, `ReactAgent(client, retriever, chunks, cfg, gen_model, doc_names).answer() -> {answer, steps, trace}`, `build_comparison_md_3way(rag, react, rlm)` are consistent across tasks and match the spec.
- **Placeholder scan:** every code/command step is concrete. The report-update task (T6 S6) is data-dependent (fills from computed JSON, not a placeholder) and specifies exactly which tables/values.
- **Reuse:** ReAct shares the existing HybridRetriever/index/client; compare_results reuses existing eval_rag.json/eval_rlm_v3.json (no needless re-scoring). 2-way path preserved for backward compatibility.

## Out of scope
Native tool-calling; step-budget/k sweeps; re-scoring RLM v1/v4/v5.
