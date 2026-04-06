from __future__ import annotations

import re
from dataclasses import dataclass

import httpx
from selectolax.parser import HTMLParser

from dealwatch.providers.cashback.base import CashbackQuotePayload, CashbackQuoteResult


_PERCENT_RE = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*%")
_FLAT_RE = re.compile(r"\$(?P<value>\d+(?:\.\d+)?)")


@dataclass(slots=True)
class CashbackMonitorProvider:
    base_url: str = "https://www.cashbackmonitor.com/cashback-store/{merchant_key}/"

    async def fetch_quote(self, payload: CashbackQuotePayload) -> CashbackQuoteResult | None:
        url = self.base_url.format(merchant_key=payload.merchant_key)
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            response = await client.get(url)
            if response.status_code >= 400:
                return None

        parser = HTMLParser(response.text)
        body_text = parser.body.text(separator=" ", strip=True) if parser.body else response.text

        percent_match = _PERCENT_RE.search(body_text)
        if percent_match:
            return CashbackQuoteResult(
                provider="cashbackmonitor",
                merchant_key=payload.merchant_key,
                rate_type="percent",
                rate_value=float(percent_match.group("value")),
                conditions_text="Parsed from CashbackMonitor store page",
                source_url=str(response.url),
                confidence=0.6,
            )

        flat_match = _FLAT_RE.search(body_text)
        if flat_match:
            return CashbackQuoteResult(
                provider="cashbackmonitor",
                merchant_key=payload.merchant_key,
                rate_type="flat",
                rate_value=float(flat_match.group("value")),
                conditions_text="Parsed from CashbackMonitor store page",
                source_url=str(response.url),
                confidence=0.5,
            )

        return None
