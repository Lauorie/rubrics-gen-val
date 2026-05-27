"""Scoring formula from spec §6."""
from __future__ import annotations
from typing import Iterable

from cae_eval.schema import Criterion


def score_response(criteria: Iterable[Criterion], met_by_text: dict[str, bool]) -> float:
    """Compute a normalised score in [0, 1] for a candidate response.

    Args:
        criteria: Iterable of Criterion objects defining the rubric.
        met_by_text: Mapping from criterion text to whether it was met.

    Returns:
        Score in [0.0, 1.0]; positive criteria summed, negative (pitfall)
        criteria subtracted, then divided by the positive-criteria maximum
        and clipped to [0, 1].
    """
    pos_score = 0
    pos_max = 0
    penalty = 0
    for c in criteria:
        met = met_by_text.get(c.text, False)
        if c.sign == "positive":
            pos_max += c.weight
            if met:
                pos_score += c.weight
        else:  # negative / pitfall
            if met:
                penalty += c.weight
    if pos_max == 0:
        return 0.0
    raw = (pos_score - penalty) / pos_max
    return max(0.0, min(1.0, raw))
