"""SciArena rubric generation: English, citation-grounded, RAG-free.

A parallel module to :mod:`rubrics` that adapts the three-stage rubric pipeline
(generate -> refine -> misalignment-filter) to the SciArena literature-QA
dataset. Ground-truth answers and their citations are selected by human vote;
the citations themselves serve as the domain context (no retrieval index).
"""
from __future__ import annotations

from rubrics_sciarena.data_loader import iter_items, select_gt
from rubrics_sciarena.pipeline import build_rubric_for_item_sciarena
from rubrics_sciarena.schema import SciArenaRubricItem, normalize_question_type
from rubrics_sciarena.translate import translate_record_to_zh

__all__ = [
    "iter_items",
    "select_gt",
    "build_rubric_for_item_sciarena",
    "translate_record_to_zh",
    "SciArenaRubricItem",
    "normalize_question_type",
]
