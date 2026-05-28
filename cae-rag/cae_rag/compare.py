"""Build the RAG-vs-RLM-v3 comparison report from two eval.json aggregates."""
from __future__ import annotations
import json
from pathlib import Path

# Published RLM numbers from EXPERIMENTS.md (judge gpt-5.5 — different judge, context only)
PUBLISHED_RLM = {"v1": 0.698, "v3": 0.711, "v4": 0.706, "v5": 0.693}


def load_aggregate(eval_json_path: str) -> dict:
    return json.loads(Path(eval_json_path).read_text(encoding="utf-8"))["aggregate"]


def extract_rlm_predictions(rubrics_v3: list[dict]) -> list[dict]:
    """Map RLM v3 records to predictions: {item_idx, answer=rlm_answer}."""
    return [{"item_idx": r["item_idx"], "answer": r.get("rlm_answer", "")} for r in rubrics_v3]


def _fmt(x) -> str:
    return f"{x:.3f}" if isinstance(x, (int, float)) else "—"


def _delta(a, b) -> str:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        d = a - b
        return f"{d:+.3f}".replace("+-", "-")
    return "—"


def build_comparison_md(rag: dict, rlm: dict) -> str:
    lines: list[str] = []
    lines.append("# CAE-RAG vs RLM v3 — Comparison\n")
    lines.append(f"Both scored with `cae-rubrics-eval`, judge `{rag.get('judge_model')}`, identical anchors.\n")
    lines.append("## Headline (mean_anchored — primary metric)\n")
    lines.append("| System | mean_anchored | mean_score | n_ok | n_err |")
    lines.append("|---|---|---|---|---|")
    lines.append(f"| RAG (hybrid top-5) | {_fmt(rag.get('mean_anchored'))} | {_fmt(rag.get('mean_score'))} | {rag.get('n_scored_ok')} | {rag.get('n_errors')} |")
    lines.append(f"| RLM v3 | {_fmt(rlm.get('mean_anchored'))} | {_fmt(rlm.get('mean_score'))} | {rlm.get('n_scored_ok')} | {rlm.get('n_errors')} |")
    lines.append(f"\n**Delta (RAG − RLM v3) anchored: {_delta(rag.get('mean_anchored'), rlm.get('mean_anchored'))}**\n")

    lines.append("## By question type (mean_anchored)\n")
    lines.append("| question_type | RAG | RLM v3 | Δ |")
    lines.append("|---|---|---|---|")
    qts = sorted(set(rag.get("by_question_type", {})) | set(rlm.get("by_question_type", {})))
    for qt in qts:
        ra = rag.get("by_question_type", {}).get(qt, {}).get("mean_anchored")
        rl = rlm.get("by_question_type", {}).get(qt, {}).get("mean_anchored")
        lines.append(f"| {qt} | {_fmt(ra)} | {_fmt(rl)} | {_delta(ra, rl)} |")

    lines.append("\n## By difficulty (mean_anchored)\n")
    lines.append("| difficulty | RAG | RLM v3 | Δ |")
    lines.append("|---|---|---|---|")
    diffs = sorted(set(rag.get("by_difficulty", {})) | set(rlm.get("by_difficulty", {})))
    for d in diffs:
        ra = rag.get("by_difficulty", {}).get(d, {}).get("mean_anchored")
        rl = rlm.get("by_difficulty", {}).get(d, {}).get("mean_anchored")
        lines.append(f"| {d} | {_fmt(ra)} | {_fmt(rl)} | {_delta(ra, rl)} |")

    lines.append("\n## Secondary context — published RLM (judge gpt-5.5, NOT comparable to above)\n")
    lines.append("| version | published mean_anchored |")
    lines.append("|---|---|")
    for v, s in PUBLISHED_RLM.items():
        lines.append(f"| {v} | {s:.3f} |")
    lines.append("\n> The table above used judge `gpt-5.5`; the headline used `gpt-5.4-mini`. "
                 "Compare RAG only against the re-scored RLM v3 headline number.\n")
    return "\n".join(lines)
