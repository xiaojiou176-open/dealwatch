from __future__ import annotations

import httpx
import pytest

from dealwatch.providers.cashback.base import CashbackQuotePayload
from dealwatch.providers.cashback.cashback_monitor import CashbackMonitorProvider


class _FakeClient:
    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url: str):
        request = httpx.Request("GET", url)
        return httpx.Response(
            200,
            request=request,
            text="<html><body><main>Best portal pays 12.5% cash back today</main></body></html>",
        )


@pytest.mark.asyncio
async def test_cashback_monitor_provider_parses_percent(monkeypatch) -> None:
    monkeypatch.setattr("dealwatch.providers.cashback.cashback_monitor.httpx.AsyncClient", _FakeClient)
    provider = CashbackMonitorProvider()
    quote = await provider.fetch_quote(
        CashbackQuotePayload(
            merchant_key="sayweee",
            product_url="https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
        )
    )
    assert quote is not None
    assert quote.rate_type == "percent"
    assert quote.rate_value == 12.5
