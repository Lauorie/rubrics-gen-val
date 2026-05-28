import os
import random
import numpy as np
from cae_rag.config import Config, set_seed

def test_config_from_env(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_BASE_URL", "https://aiberm.com/v1")
    monkeypatch.setenv("EMBEDDING_MODEL", "openai/text-embedding-3-small")
    monkeypatch.setenv("GEN_MODEL", "deepseek/deepseek-v4-flash")
    cfg = Config.from_env()
    assert cfg.api_key == "sk-test"
    assert cfg.embedding_model == "openai/text-embedding-3-small"
    assert cfg.gen_model == "deepseek/deepseek-v4-flash"
    assert cfg.chunk_size == 512
    assert cfg.chunk_overlap == 64
    assert cfg.top_k == 5
    assert cfg.rrf_k == 60
    assert cfg.candidate_pool == 20

def test_config_is_frozen():
    cfg = Config(api_key="x", base_url="u", embedding_model="e", gen_model="g")
    try:
        cfg.chunk_size = 999  # type: ignore[misc]
        assert False, "Config must be frozen"
    except Exception:
        pass

def test_set_seed_is_deterministic():
    set_seed(42)
    a = (random.random(), float(np.random.rand()))
    set_seed(42)
    b = (random.random(), float(np.random.rand()))
    assert a == b
