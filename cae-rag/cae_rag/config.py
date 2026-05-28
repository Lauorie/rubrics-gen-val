"""Immutable run configuration + seeding."""
from __future__ import annotations
import os
import random
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Config:
    api_key: str
    base_url: str
    embedding_model: str
    gen_model: str
    chunk_size: int = 512
    chunk_overlap: int = 64
    top_k: int = 5
    rrf_k: int = 60
    candidate_pool: int = 20
    embed_dim: int = 1536
    gen_temperature: float = 0.0
    seed: int = 42

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            api_key=os.environ["LLM_API_KEY"],
            base_url=os.environ.get("LLM_BASE_URL", "https://aiberm.com/v1"),
            embedding_model=os.environ.get("EMBEDDING_MODEL", "openai/text-embedding-3-small"),
            gen_model=os.environ.get("GEN_MODEL", "deepseek/deepseek-v4-flash"),
        )


def set_seed(seed: int = 42) -> None:
    """Set random seeds for reproducibility."""
    random.seed(seed)
    np.random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
