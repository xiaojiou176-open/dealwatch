from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz


_TOKEN_RE = re.compile(r"[a-z0-9]+")
_SIZE_RE = re.compile(
    r"(?P<qty>\d+(?:\.\d+)?)\s*(?P<unit>ct|count|oz|ounce|ounces|foz|fl oz|gal|gallon|kg|lb|lbs|ml|l|g|pack|pk|each)"
)
_UNIT_ALIASES = {
    "count": "ct",
    "ounce": "oz",
    "ounces": "oz",
    "foz": "fl oz",
    "gallon": "gal",
    "lbs": "lb",
    "pk": "pack",
}


@dataclass(slots=True)
class CandidateSnapshot:
    candidate_key: str
    normalized_title: str
    brand_hint: str | None
    size_hint: str | None
    product_key: str | None


def _normalize_phrase(raw: str | None) -> str | None:
    if raw is None:
        return None
    tokens = _TOKEN_RE.findall(raw.lower())
    if not tokens:
        return None
    return " ".join(tokens)


def _normalize_size_hint(raw: str | None) -> str | None:
    if raw is None:
        return None

    match = _SIZE_RE.search(raw.lower())
    if match is None:
        normalized = _normalize_phrase(raw)
        if not normalized:
            return None
        return normalized

    qty_raw = match.group("qty")
    if "." in qty_raw:
        qty = qty_raw.rstrip("0").rstrip(".")
    else:
        qty = qty_raw
    unit = match.group("unit").lower()
    unit = _UNIT_ALIASES.get(unit, unit)
    return f"{qty} {unit}"


def build_candidate_key(title: str, brand: str | None = None, size_hint: str | None = None) -> str:
    parts: list[str] = []
    normalized_title = _normalize_phrase(title)
    normalized_brand = _normalize_phrase(brand)
    normalized_size = _normalize_size_hint(size_hint)

    if normalized_title:
        parts.append(normalized_title)
    if normalized_brand:
        parts.append(normalized_brand)
    if normalized_size:
        parts.append(normalized_size)

    return " | ".join(parts)


def compute_match_score(left: str, right: str) -> float:
    return float(fuzz.token_sort_ratio(left, right))


def build_candidate_snapshot(
    title: str,
    *,
    brand: str | None = None,
    size_hint: str | None = None,
    product_key: str | None = None,
) -> CandidateSnapshot:
    normalized_title = _normalize_phrase(title) or ""
    normalized_brand = _normalize_phrase(brand)
    normalized_size = _normalize_size_hint(size_hint)
    return CandidateSnapshot(
        candidate_key=build_candidate_key(title, brand=brand, size_hint=size_hint),
        normalized_title=normalized_title,
        brand_hint=normalized_brand,
        size_hint=normalized_size,
        product_key=(str(product_key).strip() or None) if product_key is not None else None,
    )


def build_match_details(left: CandidateSnapshot, right: CandidateSnapshot) -> dict[str, object]:
    title_similarity = compute_match_score(left.normalized_title, right.normalized_title)
    score = title_similarity
    why_like: list[str] = []
    why_unlike: list[str] = []

    if title_similarity >= 90:
        why_like.append("Titles are nearly identical after normalization.")
    elif title_similarity >= 75:
        why_like.append("Titles stay close after normalization.")
    else:
        why_unlike.append("Titles diverge after normalization.")

    brand_signal = "unknown"
    if left.brand_hint and right.brand_hint:
        if left.brand_hint == right.brand_hint:
            brand_signal = "match"
            score += 8.0
            why_like.append("Brand hints match.")
        else:
            brand_signal = "mismatch"
            score -= 18.0
            why_unlike.append("Brand hints disagree.")

    size_signal = "unknown"
    if left.size_hint and right.size_hint:
        if left.size_hint == right.size_hint:
            size_signal = "match"
            score += 10.0
            why_like.append("Size hints match.")
        else:
            size_signal = "mismatch"
            score -= 15.0
            why_unlike.append("Size hints differ.")

    product_key_signal = "cross-store"
    if left.product_key and right.product_key:
        if left.product_key == right.product_key:
            product_key_signal = "same-product-key"
            why_like.append("Product keys match exactly.")
        else:
            product_key_signal = "different-product-key"
            why_like.append("Product keys differ, which is normal across stores.")

    score = max(0.0, min(score, 100.0))

    return {
        "score": round(score, 1),
        "title_similarity": round(title_similarity, 1),
        "brand_signal": brand_signal,
        "size_signal": size_signal,
        "product_key_signal": product_key_signal,
        "why_like": why_like,
        "why_unlike": why_unlike,
        "left_candidate_key": left.candidate_key,
        "right_candidate_key": right.candidate_key,
    }
