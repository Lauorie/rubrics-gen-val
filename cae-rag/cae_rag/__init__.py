"""CAE-RAG: hybrid-retrieval RAG over CAE-MDs."""
from cae_rag.config import Config, set_seed
from cae_rag.ingest import Chunk, chunk_text, clean_markdown, load_and_chunk
from cae_rag.retrieve import HybridRetriever, rrf_fuse
from cae_rag.generate import build_prompt, generate_all, generate_answer
from cae_rag.compare import build_comparison_md, extract_rlm_predictions, load_aggregate, build_comparison_md_3way
from cae_rag.react import ReactAgent, ReactConfig

__all__ = [
    "Config", "set_seed",
    "Chunk", "chunk_text", "clean_markdown", "load_and_chunk",
    "HybridRetriever", "rrf_fuse",
    "build_prompt", "generate_all", "generate_answer",
    "build_comparison_md", "extract_rlm_predictions", "load_aggregate",
    "build_comparison_md_3way",
    "ReactAgent", "ReactConfig",
]
