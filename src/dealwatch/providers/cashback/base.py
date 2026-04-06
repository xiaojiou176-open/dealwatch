from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class CashbackQuotePayload:
    merchant_key: str
    product_url: str


@dataclass(slots=True)
class CashbackQuoteResult:
    provider: str
    merchant_key: str
    rate_type: str
    rate_value: float
    conditions_text: str | None
    source_url: str | None
    confidence: float


class CashbackProvider(Protocol):
    async def fetch_quote(self, payload: CashbackQuotePayload) -> CashbackQuoteResult | None:
        raise NotImplementedError
