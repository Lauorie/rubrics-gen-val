"""CLI: score RAG (+ optional ReAct), re-score RLM v3, then write comparison.md.

Reuses existing eval_*.json unless --force, so re-runs are cheap.
"""
from __future__ import annotations
import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cae_rag.compare import (
    build_comparison_md, build_comparison_md_3way, extract_rlm_predictions, load_aggregate,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")
logger = logging.getLogger("compare_results")

EVAL_DIR = Path("/home/juli/RLM/cae-rubrics-eval")
RLM_V3 = Path("/home/juli/RLM/data/CAE-v2.0-1-rubrics-v3.json")


def score(predictions: Path, out: Path, concurrency: int, eval_dir: Path) -> None:
    """Invoke cae-rubrics-eval/score.py from inside its dir (so its .env + anchors resolve)."""
    cmd = [str(eval_dir / ".venv/bin/python"), "score.py", "--predictions", str(predictions.resolve()),
           "--out", str(out.resolve()), "--concurrency", str(concurrency)]
    logger.info("Scoring -> %s", out)
    subprocess.run(cmd, cwd=str(eval_dir), check=True)


def ensure_scored(predictions: Path, out: Path, concurrency: int, eval_dir: Path, force: bool) -> None:
    """Score predictions unless an eval json already exists (and not force)."""
    if out.exists() and not force:
        logger.info("Reusing existing %s", out)
        return
    score(predictions, out, concurrency, eval_dir)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out-dir", default="outputs", type=Path)
    p.add_argument("--concurrency", type=int, default=16)
    p.add_argument("--eval-dir", default=EVAL_DIR, type=Path, help="Path to cae-rubrics-eval")
    p.add_argument("--rlm-v3", default=RLM_V3, type=Path, help="RLM v3 answers JSON")
    p.add_argument("--react-predictions", default=None, type=Path,
                   help="If given, also score ReAct predictions and emit a 3-way report")
    p.add_argument("--force", action="store_true", help="Re-score even if eval_*.json exists")
    args = p.parse_args()
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    # 1) RAG
    ensure_scored(out / "predictions.jsonl", out / "eval_rag.json",
                  args.concurrency, args.eval_dir, args.force)

    # 2) RLM v3 — build predictions only if we actually need to score
    if args.force or not (out / "eval_rlm_v3.json").exists():
        v3 = json.loads(args.rlm_v3.read_text(encoding="utf-8"))
        rlm_path = out / "rlm_v3_predictions.jsonl"
        with open(rlm_path, "w", encoding="utf-8") as f:
            for r in extract_rlm_predictions(v3):
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        score(rlm_path, out / "eval_rlm_v3.json", args.concurrency, args.eval_dir)
    else:
        logger.info("Reusing existing %s", out / "eval_rlm_v3.json")

    # 3) optional ReAct
    react_agg = None
    if args.react_predictions is not None:
        ensure_scored(args.react_predictions, out / "eval_react.json",
                      args.concurrency, args.eval_dir, args.force)
        react_agg = load_aggregate(str(out / "eval_react.json"))

    # 4) report
    rag_agg = load_aggregate(str(out / "eval_rag.json"))
    rlm_agg = load_aggregate(str(out / "eval_rlm_v3.json"))
    if react_agg is not None:
        md = build_comparison_md_3way(rag_agg, react_agg, rlm_agg)
        logger.info("RAG=%s  ReAct=%s  RLM v3=%s (anchored)",
                    rag_agg.get("mean_anchored"), react_agg.get("mean_anchored"), rlm_agg.get("mean_anchored"))
    else:
        md = build_comparison_md(rag_agg, rlm_agg)
        logger.info("RAG anchored=%s  RLM v3 anchored=%s",
                    rag_agg.get("mean_anchored"), rlm_agg.get("mean_anchored"))
    (out / "comparison.md").write_text(md, encoding="utf-8")
    logger.info("Wrote %s", out / "comparison.md")


if __name__ == "__main__":
    main()
