"""Translate a cleaned SciArena record's question + GT answer into Chinese.

Models the scenario of a Chinese user querying an English knowledge base: the
question and the ground-truth answer are rewritten in Chinese while the cited
sources stay in their original English. The original English text is preserved
under ``*_en`` keys for traceability.
"""
from __future__ import annotations

import logging
from typing import Awaitable, Callable, Optional

from rubrics.llm_client import LLMClient

logger = logging.getLogger(__name__)

TranslateFn = Callable[[Optional[LLMClient], str, str], Awaitable[dict]]

_SYSTEM = (
    "你是一位专业的科技翻译。请把给定的英文研究【问题】和【回答】翻译成自然、准确、地道的中文，"
    "保留所有技术术语、方法名、模型名、指标和数字；专有名词与论文作者名可保留英文。"
    "不要增删内容，不要解释。"
)


async def _llm_translate(client: LLMClient, question: str, answer: str) -> dict:
    user = (
        f"[英文问题]\n{question}\n\n"
        f"[英文回答]\n{answer}\n\n"
        '请输出严格 JSON：{"question": "中文问题", "answer": "中文回答"}'
    )
    out = await client.complete_json_async(
        system=_SYSTEM, user=user, schema_hint='{question, answer}',
    )
    return {"question": str(out.get("question", "")), "answer": str(out.get("answer", ""))}


async def translate_record_to_zh(
    record: dict,
    client: Optional[LLMClient],
    *,
    translate_fn: Optional[TranslateFn] = None,
) -> dict:
    """Return a copy of ``record`` with its question and GT answer in Chinese.

    Args:
        record: A cleaned record from :func:`select_gt`.
        client: LLM client used for translation (``None`` in tests).
        translate_fn: Injectable async translator; defaults to the real one.

    Returns:
        A new record with Chinese ``question`` / ``reference_answer``, English
        citations untouched, and the original English text kept under
        ``question_en`` / ``reference_answer_en``.
    """
    translate = translate_fn or _llm_translate
    out = await translate(client, record["question"], record["reference_answer"])

    new = dict(record)
    new["question_en"] = record["question"]
    new["reference_answer_en"] = record["reference_answer"]
    new["question"] = out["question"]
    new["reference_answer"] = out["answer"]
    new["lang"] = "zh"
    return new
