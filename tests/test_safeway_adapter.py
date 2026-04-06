import sys

import pytest

from dealwatch.core.models import Offer, PriceContext
from dealwatch.infra.config import Settings
from dealwatch.stores.safeway import adapter as safeway_adapter_module
from dealwatch.stores.safeway.adapter import SafewayAdapter
from dealwatch.stores.safeway.discovery import SafewayDiscovery
from dealwatch.stores.safeway.parser import SafewayParser


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
async def test_safeway_adapter_discover_and_parse(monkeypatch) -> None:
    settings = Settings()
    client = _FakeClient()
    adapter = SafewayAdapter(client, settings)

    async def _discover(self):
        return ["https://www.safeway.com/shop/product-details.960127167.html"]

    monkeypatch.setattr(SafewayDiscovery, "discover_deals", _discover)

    offer = Offer(
        store_id="safeway",
        product_key="0000001234567",
        title="Fairlife Milk Ultra-Filtered Reduced Fat 2% - 52 Fl. Oz.",
        url="https://www.safeway.com/shop/product-details.960127167.html",
        price=6.99,
        original_price=None,
        fetch_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        context=PriceContext(region="98004"),
        unit_price_info={"raw": "52 fl oz", "brand": "fairlife"},
    )

    async def _parse(self, _page):
        return offer

    monkeypatch.setattr(SafewayParser, "parse", _parse)

    urls = await adapter.discover_deals()
    assert urls == ["https://www.safeway.com/shop/product-details.960127167.html"]

    parsed = await adapter.parse_product(urls[0])
    assert parsed == offer
    assert client.page.closed is True


@pytest.mark.asyncio
async def test_safeway_adapter_capture_on_parse_none(monkeypatch) -> None:
    settings = Settings()
    client = _FakeClient()
    adapter = SafewayAdapter(client, settings)

    async def _parse(self, _page):
        return None

    monkeypatch.setattr(SafewayParser, "parse", _parse)
    called: dict[str, str] = {}

    async def _capture(page, url, reason):
        called["url"] = url
        called["reason"] = reason

    monkeypatch.setattr(adapter, "_capture_failed_page", _capture)

    parsed = await adapter.parse_product("https://www.safeway.com/shop/product-details.960127167.html")

    assert parsed is None
    assert called["url"] == "https://www.safeway.com/shop/product-details.960127167.html"
    assert called["reason"] == "parse_returned_none"


@pytest.mark.asyncio
async def test_safeway_adapter_capture_on_parse_exception(monkeypatch) -> None:
    settings = Settings()
    client = _FakeClient()
    adapter = SafewayAdapter(client, settings)

    async def _parse(self, _page):
        raise RuntimeError("boom")

    monkeypatch.setattr(SafewayParser, "parse", _parse)
    called: dict[str, str] = {}

    async def _capture(page, url, reason):
        called["url"] = url
        called["reason"] = reason

    monkeypatch.setattr(adapter, "_capture_failed_page", _capture)

    parsed = await adapter.parse_product("https://www.safeway.com/shop/product-details.960127167.html")

    assert parsed is None
    assert called["url"] == "https://www.safeway.com/shop/product-details.960127167.html"
    assert called["reason"] == "parse_exception:RuntimeError"


def test_safeway_adapter_main_invokes_test_adapter(monkeypatch) -> None:
    called: dict[str, str] = {}

    async def _fake_test(url: str) -> None:
        called["url"] = url

    monkeypatch.setattr(safeway_adapter_module.SafewayAdapter, "test_adapter", _fake_test)
    monkeypatch.setattr(
        sys,
        "argv",
        ["adapter.py", "--test", "https://www.safeway.com/shop/product-details.960127167.html"],
    )

    safeway_adapter_module._main()

    assert called["url"] == "https://www.safeway.com/shop/product-details.960127167.html"
