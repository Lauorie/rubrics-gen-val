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
