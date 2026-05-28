"""CLI: score RAG predictions + re-score RLM v3, then write comparison.md."""
from __future__ import annotations
import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cae_rag.compare import build_comparison_md, extract_rlm_predictions, load_aggregate

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")
logger = logging.getLogger("compare_results")

EVAL_DIR = Path("/home/juli/RLM/cae-rubrics-eval")
EVAL_PY = EVAL_DIR / ".venv/bin/python"
RLM_V3 = Path("/home/juli/RLM/data/CAE-v2.0-1-rubrics-v3.json")


def score(predictions: Path, out: Path, concurrency: int) -> None:
    """Invoke cae-rubrics-eval/score.py from inside its dir (so its .env + anchors resolve)."""
    cmd = [str(EVAL_PY), "score.py", "--predictions", str(predictions.resolve()),
           "--out", str(out.resolve()), "--concurrency", str(concurrency)]
    logger.info("Scoring -> %s", out)
    subprocess.run(cmd, cwd=str(EVAL_DIR), check=True)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out-dir", default="outputs", type=Path)
    p.add_argument("--concurrency", type=int, default=16)
    args = p.parse_args()
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    # 1) score RAG
    score(out / "predictions.jsonl", out / "eval_rag.json", args.concurrency)

    # 2) build + score RLM v3 through the SAME pipeline
    v3 = json.loads(RLM_V3.read_text(encoding="utf-8"))
    rlm_preds = extract_rlm_predictions(v3)
    rlm_path = out / "rlm_v3_predictions.jsonl"
    with open(rlm_path, "w", encoding="utf-8") as f:
        for r in rlm_preds:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    score(rlm_path, out / "eval_rlm_v3.json", args.concurrency)

    # 3) comparison report
    rag_agg = load_aggregate(str(out / "eval_rag.json"))
    rlm_agg = load_aggregate(str(out / "eval_rlm_v3.json"))
    md = build_comparison_md(rag_agg, rlm_agg)
    (out / "comparison.md").write_text(md, encoding="utf-8")
    logger.info("RAG anchored=%s  RLM v3 anchored=%s", rag_agg.get("mean_anchored"), rlm_agg.get("mean_anchored"))
    logger.info("Wrote %s", out / "comparison.md")


if __name__ == "__main__":
    main()
