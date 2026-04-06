import sys

import pytest

from dealwatch.core.models import Offer, PriceContext
from dealwatch.infra.config import Settings
from dealwatch.stores.walmart import adapter as walmart_adapter_module
from dealwatch.stores.walmart.adapter import WalmartAdapter
from dealwatch.stores.walmart.discovery import WalmartDiscovery
from dealwatch.stores.walmart.parser import WalmartParser


class _FakePage:
    def __init__(self) -> None:
        self.closed = False

    async def content(self) -> str:
        return "<html><body>fake</body></html>"

    async def screenshot(self, path: str) -> None:
        return None

    async def close(self) -> None:
        self.closed = True


class _FakeClient:
    def __init__(self) -> None:
        self.storage_state_path = "state.json"
        self.page = _FakePage()

    async def fetch_page(self, url: str, return_page: bool = False):
        return self.page


@pytest.mark.asyncio
async def test_walmart_adapter_discover_and_parse(monkeypatch) -> None:
    settings = Settings()
    client = _FakeClient()
    adapter = WalmartAdapter(client, settings)

    async def _discover(self):
        return ["https://www.walmart.com/ip/10450117"]

    monkeypatch.setattr(WalmartDiscovery, "discover_deals", _discover)

    offer = Offer(
        store_id="walmart",
        product_key="10450117",
        title="Great Value Whole Vitamin D Milk, 1 gal",
        url="https://www.walmart.com/ip/10450117",
        price=3.74,
        original_price=None,
        fetch_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        context=PriceContext(region="98004"),
        unit_price_info={"raw": "Great Value Whole Vitamin D Milk, 1 gal", "brand": "Great Value"},
    )

    async def _parse(self, _page):
        return offer

    monkeypatch.setattr(WalmartParser, "parse", _parse)

    urls = await adapter.discover_deals()
    assert urls == ["https://www.walmart.com/ip/10450117"]

    parsed = await adapter.parse_product(urls[0])
    assert parsed == offer
    assert client.page.closed is True


@pytest.mark.asyncio
async def test_walmart_adapter_capture_on_parse_none(monkeypatch) -> None:
    settings = Settings()
    client = _FakeClient()
    adapter = WalmartAdapter(client, settings)

    async def _parse(self, _page):
        return None

    monkeypatch.setattr(WalmartParser, "parse", _parse)
    called: dict[str, str] = {}

    async def _capture(page, url, reason):
        called["url"] = url
        called["reason"] = reason

    monkeypatch.setattr(adapter, "_capture_failed_page", _capture)

    parsed = await adapter.parse_product("https://www.walmart.com/ip/10450117")

    assert parsed is None
    assert called["url"] == "https://www.walmart.com/ip/10450117"
    assert called["reason"] == "parse_returned_none"


@pytest.mark.asyncio
async def test_walmart_adapter_capture_on_parse_exception(monkeypatch) -> None:
    settings = Settings()
    client = _FakeClient()
    adapter = WalmartAdapter(client, settings)

    async def _parse(self, _page):
        raise RuntimeError("boom")

    monkeypatch.setattr(WalmartParser, "parse", _parse)
    called: dict[str, str] = {}

    async def _capture(page, url, reason):
        called["url"] = url
        called["reason"] = reason

    monkeypatch.setattr(adapter, "_capture_failed_page", _capture)

    parsed = await adapter.parse_product("https://www.walmart.com/ip/10450117")

    assert parsed is None
    assert called["url"] == "https://www.walmart.com/ip/10450117"
    assert called["reason"] == "parse_exception:RuntimeError"


def test_walmart_adapter_main_invokes_test_adapter(monkeypatch) -> None:
    called: dict[str, str] = {}

    async def _fake_test(url: str) -> None:
        called["url"] = url

    monkeypatch.setattr(walmart_adapter_module.WalmartAdapter, "test_adapter", _fake_test)
    monkeypatch.setattr(sys, "argv", ["adapter.py", "--test", "https://www.walmart.com/ip/10450117"])

    walmart_adapter_module._main()

    assert called["url"] == "https://www.walmart.com/ip/10450117"
