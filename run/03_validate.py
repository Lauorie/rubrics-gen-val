"""Quick QC over generated rubrics."""
from __future__ import annotations
import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import mean


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--rubrics", default="data/CAE-v2.0-1-rubrics.json")
    p.add_argument("--source-data", default="data/CAE-v2.0-1.json")
    args = p.parse_args()

    rubrics = json.loads(Path(args.rubrics).read_text(encoding="utf-8"))
    source = json.loads(Path(args.source_data).read_text(encoding="utf-8"))

    print(f"Rubrics: {len(rubrics)} / {len(source)} items")

    n_criteria = [len(r["criteria"]) for r in rubrics]
    print(f"criteria/item: min={min(n_criteria)} max={max(n_criteria)} mean={mean(n_criteria):.1f}")

    by_type = Counter(r["question_type"] for r in rubrics)
    print("By type:", dict(by_type))

    short_pitfalls = [r["question_id"] for r in rubrics
                       if sum(1 for c in r["criteria"] if c["category"] == "Pitfall") < 2]
    print(f"items with <2 Pitfall: {len(short_pitfalls)} → {short_pitfalls[:10]}")

    gs = Counter(r["source_grounding"]["ground_status"] for r in rubrics)
    print("ground_status:", dict(gs))

    drops = [r["rubric_metadata"]["n_dropped_misaligned"] for r in rubrics]
    print(f"dropped/item: mean={mean(drops):.1f} max={max(drops)}")


if __name__ == "__main__":
    main()
