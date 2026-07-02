"""Pydantic v2 models for SciArena (literature-QA) rubrics.

The :class:`Criterion` shape is kept identical to the CAE rubrics
(:mod:`rubrics.schema`) so generated rubrics remain compatible with the
``cae-rubrics-eval`` scorer. The item-level schema differs: English question
types, a ``subject`` field, the human ``vote`` / ``gt_source``, and citation
grounding instead of RAG grounding.
"""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

QuestionType = Literal[
    "Methodology Inquiry",
    "Conceptual Explanation",
    "Challenges & Limitations",
    "State-of-the-Art Assessment",
    "Paper Finding",
    "Others",
]
Category = Literal["Essential", "Important", "Optional", "Pitfall"]
Sign = Literal["positive", "negative"]
CriterionType = Literal[
    "factual_anchor", "mechanism_explanation", "numeric_precision",
    "decision_logic", "comparative_balance", "process_completeness",
    "anti_hacking",
]
GTSource = Literal["A", "B"]
Vote = Literal["A", "B", "Tie"]

_KNOWN_QUESTION_TYPES = set(QuestionType.__args__)  # type: ignore[attr-defined]


def normalize_question_type(value: Optional[str]) -> str:
    """Map a raw SciArena question type to a known :data:`QuestionType`.

    Unknown or missing values fall back to ``"Others"``.
    """
    if value in _KNOWN_QUESTION_TYPES:
        return value  # type: ignore[return-value]
    return "Others"


class Criterion(BaseModel):
    id: str
    text: str = Field(min_length=1)
    category: Category
    weight: int = Field(ge=1, le=8)
    sign: Sign
    criterion_type: CriterionType
    evidence_quote: Optional[str] = None

    @model_validator(mode="after")
    def check_sign_matches_category(self) -> "Criterion":
        if self.category == "Pitfall" and self.sign != "negative":
            raise ValueError("Pitfall must have sign=negative")
        if self.category != "Pitfall" and self.sign == "negative":
            raise ValueError(f"{self.category} must have sign=positive")
        return self


class CitationGrounding(BaseModel):
    citation_ids: List[str]
    titles: List[str]
    n_citations: int = Field(ge=0)


class RubricMetadata(BaseModel):
    generation_model: str
    generation_passes: int = Field(ge=1)
    n_criteria_initial: int = Field(ge=0)
    n_criteria_final: int = Field(ge=0)
    n_dropped_misaligned: int = Field(ge=0)
    language: str = "en"
    generated_at: str
    schema_version: str = "1.0"


class SciArenaRubricItem(BaseModel):
    id: str
    question: str
    reference_answer: str
    question_type: QuestionType
    subject: str
    vote: Vote
    gt_source: GTSource
    citation_grounding: CitationGrounding
    criteria: List[Criterion]
    rubric_metadata: RubricMetadata
