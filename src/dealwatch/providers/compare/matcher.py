from __future__ import annotations

from rapidfuzz.fuzz import token_set_ratio


def score_candidate(left: str, right: str) -> float:
    if not left.strip() or not right.strip():
        return 0.0
    return round(token_set_ratio(left, right) / 100.0, 4)
