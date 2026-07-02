"""End-to-end orchestrator for one SciArena item (RAG-free, English).

Stage 1 (generate) -> Stage 2 (refine) -> Stage 3 (misalignment filter), using
the GT citations as domain context instead of a retrieval index.
"""
from __future__ import annotations

import datetime as dt
import logging
from typing import Awaitable, Callable, List, Optional

import numpy as np

from rubrics.llm_client import LLMClient
from rubrics_sciarena.generator import generate_initial_rubric_async
from rubrics_sciarena.misalignment_filter import JudgeFn, filter_misaligned
from rubrics_sciarena.pseudo_chunk import citation_grounding
from rubrics_sciarena.refiner import refine_criteria
from rubrics_sciarena.schema import (
    CitationGrounding,
    Criterion,
    RubricMetadata,
    SciArenaRubricItem,
    normalize_question_type,
)

logger = logging.getLogger(__name__)

GenerateFn = Callable[..., Awaitable[list]]


def _model_name(client: Optional[LLMClient]) -> str:
    cfg = getattr(client, "cfg", None)
    return str(getattr(cfg, "model", None) or "mock")


async def build_rubric_for_item_sciarena(
    record: dict,
    gen_client: Optional[LLMClient],
    judge_client: Optional[LLMClient],
    *,
    lang: str = "en",
    embed_fn: Optional[Callable[[list[str]], np.ndarray]] = None,
    concurrency: int = 8,
    generate_fn: Optional[GenerateFn] = None,
    judge_fn: Optional[JudgeFn] = None,
) -> SciArenaRubricItem:
    """Build a complete rubric for one cleaned SciArena record.

    Args:
        record: A cleaned record from :func:`rubrics_sciarena.data_loader.select_gt`.
        gen_client: LLM client for Stage-1 generation.
        judge_client: LLM client for Stage-3 filtering.
        lang: Language code ("en"/"zh") for templates, pitfalls, and judging.
        embed_fn: Optional embedding function for Stage-2 dedup (skipped if None).
        concurrency: Max concurrent judge calls in Stage 3.
        generate_fn: Injectable Stage-1 generator (defaults to the real one).
        judge_fn: Injectable Stage-3 judge (defaults to the real one).

    Returns:
        A fully populated :class:`SciArenaRubricItem`.
    """
    generate = generate_fn or generate_initial_rubric_async
    question = record["question"]
    reference_answer = record["reference_answer"]
    question_type = record["question_type"]
    subject = record.get("subject") or "Others"
    citations = record.get("citations") or []

    raw = await generate(
        question, reference_answer, question_type, subject, citations, gen_client,
        lang=lang,
    )
    n_initial = len(raw)

    refined = refine_criteria(raw, embed_fn=embed_fn, lang=lang)
    filtered, n_dropped = await filter_misaligned(
        question=question, reference_answer=reference_answer, criteria=refined,
        judge_client=judge_client, lang=lang, concurrency=concurrency, judge_fn=judge_fn,
    )

    criteria_models = [Criterion(**c) for c in filtered]
    grounding = citation_grounding(citations)

    meta = RubricMetadata(
        generation_model=_model_name(gen_client),
        generation_passes=3,
        n_criteria_initial=n_initial,
        n_criteria_final=len(criteria_models),
        n_dropped_misaligned=n_dropped,
        language=lang,
        generated_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        schema_version="1.0",
    )

    return SciArenaRubricItem(
        id=str(record["id"]),
        question=question,
        reference_answer=reference_answer,
        question_type=normalize_question_type(question_type),
        subject=subject,
        vote=record["vote"],
        gt_source=record["gt_source"],
        citation_grounding=CitationGrounding(**grounding),
        criteria=criteria_models,
        rubric_metadata=meta,
    )
