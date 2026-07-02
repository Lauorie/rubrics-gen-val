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
    text: str = Field(min_length=1)
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
