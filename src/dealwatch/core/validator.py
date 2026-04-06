from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Final

from dealwatch.core.models import Offer


#########################################################
# Constants
#########################################################
_MIN_PRICE: Final[float] = 0.0
_MAX_PRICE: Final[float] = 1000.0
_MIN_TITLE_LENGTH: Final[int] = 6
_TITLE_BAD_TOKENS: Final[tuple[str, ...]] = (
    "null",
    "undefined",
    "n/a",
)
_REPLACEMENT_CHAR: Final[str] = "\ufffd"
_CONTROL_CHAR_RE: Final[re.Pattern[str]] = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


#########################################################
# Validator
#########################################################
@dataclass(slots=True)
class DataValidator:
    min_price: float = _MIN_PRICE
    max_price: float = _MAX_PRICE
    min_title_length: int = _MIN_TITLE_LENGTH
    logger: logging.Logger = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.logger = logging.getLogger(__name__)

    def validate_offer(self, offer: Offer) -> bool:
        if offer.price <= self.min_price or offer.price > self.max_price:
            self._warn(offer, f"price_out_of_range={offer.price}")
            return False

        if offer.original_price is not None and offer.original_price < offer.price:
            self._warn(
                offer,
                f"original_price_lt_price={offer.original_price}<{offer.price}",
            )
            return False

        if not isinstance(offer.unit_price_info, dict):
            self._warn(offer, "unit_price_info_not_dict")
            return False

        for key, value in offer.unit_price_info.items():
            if not str(key).strip():
                self._warn(offer, "unit_price_info_empty_key")
                return False
            if value is None:
                self._warn(offer, "unit_price_info_none_value")
                return False

        title = (offer.title or "").strip()
        if len(title) < self.min_title_length:
            self._warn(offer, f"title_too_short={len(title)}")
            return False

        lowered = title.lower()
        if any(token in lowered for token in _TITLE_BAD_TOKENS):
            self._warn(offer, "title_contains_bad_token")
            return False

        if _REPLACEMENT_CHAR in title or _CONTROL_CHAR_RE.search(title):
            self._warn(offer, "title_contains_invalid_chars")
            return False

        return True

    def _warn(self, offer: Offer, reason: str) -> None:
        self.logger.warning(
            "Offer rejected store=%s product=%s url=%s reason=%s",
            offer.store_id,
            offer.product_key,
            offer.url,
            reason,
        )
