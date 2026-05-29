"""Text-based ReAct agent over the CAE knowledge base."""
from __future__ import annotations
import logging
import re
from dataclasses import dataclass
from typing import Any

from cae_rag.ingest import Chunk

logger = logging.getLogger(__name__)

_ACTION_RE = re.compile(r"Action:\s*(search|read)\s*\[\s*(.*?)\s*\]", re.IGNORECASE | re.DOTALL)
_FINAL_RE = re.compile(r"Final Answer:\s*(.+)", re.IGNORECASE | re.DOTALL)

SYSTEM_TEMPLATE = (
    '你是 CAE / 工程仿真领域专家，通过“思考-行动-观察”循环回答问题。\n'
    '知识库包含以下文档：\n{doc_list}\n\n'
    '你可以使用两个工具：\n'
    '- search[查询词]：在知识库中混合检索，返回若干片段指针（chunk_id | 文档 | 摘要）。\n'
    '- read[chunk_id]：读取该 chunk 及其相邻上下文的完整文本。\n\n'
    '每一步只能输出以下三种格式之一（且仅一个 Action）：\n'
    'Thought: <你的推理>\nAction: search[<查询词>]\n'
    '或\n'
    'Thought: <你的推理>\nAction: read[<chunk_id>]\n'
    '或\n'
    'Final Answer: <用中文给出的最终答案>\n\n'
    '只能依据检索/读取得到的资料作答，不得编造；资料不足时如实说明。'
    '答案要准确、聚焦，保留关键公式、数值与对比。'
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
