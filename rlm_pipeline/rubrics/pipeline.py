"""End-to-end orchestrator for one item."""
from __future__ import annotations
import datetime as dt
import logging
from typing import Callable, Optional

import numpy as np

from rubrics.chunker import doc_slug_from_filename
from rubrics.generator import generate_initial_rubric
from rubrics.index import ChunkIndex
from rubrics.llm_client import LLMClient
from rubrics.misalignment_filter import filter_misaligned
from rubrics.refiner import refine_criteria
from rubrics.retriever import retrieve_context
from rubrics.schema import RubricItem, Criterion, SourceGrounding, RubricMetadata
from rubrics.source_parser import parse_source, DOC_ALIASES

logger = logging.getLogger(__name__)


def build_rubric_for_item(
    item: dict, index: ChunkIndex,
    generator_client: LLMClient, judge_client: LLMClient,
    embed_fn: Optional[Callable[[list[str]], np.ndarray]] = None,
) -> RubricItem:
    """Build a complete rubric for a single CAE item via Stage 1 → 2 → 3.

    Args:
        item: Dict with keys 编号, 问题描述, 参考答案, 题型, 难易程度, 难度场景, 来源.
        index: Pre-built ChunkIndex for semantic retrieval.
        generator_client: LLM client used for Stage 1 initial generation.
        judge_client: LLM client used for Stage 3 misalignment filtering.
        embed_fn: Optional embedding function for Stage 2 dedup. If None, dedup is skipped.

    Returns:
        A fully populated :class:`~rubrics.schema.RubricItem`.
    """
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
    parsed_docs = list({
        DOC_ALIASES[r.doc_alias].rsplit(".", 1)[0]
        for r in refs if r.doc_alias in DOC_ALIASES
    })
    pages: list[int] = []
    for r in refs:
        if r.pages:
            pages.extend([r.pages[0], r.pages[1]])

    sg = SourceGrounding(
        parsed_docs=[doc_slug_from_filename(d + ".md") for d in parsed_docs] if parsed_docs else [],
        pages=pages,
        retrieved_chunk_ids=[c.chunk_id for c in chunks],
        ground_status=ground_status,
    )

    criteria_models = [Criterion(**c) for c in filtered]

    generation_model = str(generator_client.cfg.model) if hasattr(generator_client, "cfg") else "mock"

    meta = RubricMetadata(
        generation_model=generation_model,
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
