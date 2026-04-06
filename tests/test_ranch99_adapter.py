import sys

import pytest

from dealwatch.core.models import Offer, PriceContext
from dealwatch.infra.config import Settings
from dealwatch.stores.ranch99 import adapter as ranch99_adapter_module
from dealwatch.stores.ranch99.adapter import Ranch99Adapter
from dealwatch.stores.ranch99.discovery import Ranch99Discovery
from dealwatch.stores.ranch99.parser import Ranch99Parser


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
async def test_ranch99_adapter_discover_and_parse(monkeypatch) -> None:
    settings = Settings()
    client = _FakeClient()
    adapter = Ranch99Adapter(client, settings)

    async def _discover(self):
        return ["https://www.99ranch.com/product-details/1615424/8899/078895126389"]

    monkeypatch.setattr(Ranch99Discovery, "discover_deals", _discover)

    offer = Offer(
        store_id="ranch99",
        product_key="078895126389",
        title="Lkk Premium Dark Soy Sauce",
        url="https://www.99ranch.com/product-details/1615424/8899/078895126389",
        price=4.49,
        original_price=5.29,
        fetch_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        context=PriceContext(region="98004"),
        unit_price_info={"raw": "16.9000 foz/each"},
    )

    async def _parse(self, _page):
        return offer

    monkeypatch.setattr(Ranch99Parser, "parse", _parse)

    urls = await adapter.discover_deals()
    assert urls == ["https://www.99ranch.com/product-details/1615424/8899/078895126389"]

    parsed = await adapter.parse_product(urls[0])
    assert parsed == offer
    assert client.page.closed is True


@pytest.mark.asyncio
async def test_ranch99_adapter_capture_on_parse_none(monkeypatch) -> None:
    settings = Settings()
    client = _FakeClient()
    adapter = Ranch99Adapter(client, settings)

    async def _parse(self, _page):
        return None

    monkeypatch.setattr(Ranch99Parser, "parse", _parse)
    called: dict[str, str] = {}

    async def _capture(page, url, reason):
        called["url"] = url
        called["reason"] = reason

    monkeypatch.setattr(adapter, "_capture_failed_page", _capture)
    parsed = await adapter.parse_product("https://www.99ranch.com/product-details/1/2/3")
    assert parsed is None
    assert called["reason"] == "parse_returned_none"


def test_ranch99_adapter_main_invokes_test_adapter(monkeypatch) -> None:
    called: dict[str, str] = {}

    async def _fake_test(url: str) -> None:
        called["url"] = url

    monkeypatch.setattr(ranch99_adapter_module.Ranch99Adapter, "test_adapter", _fake_test)
    monkeypatch.setattr(sys, "argv", ["adapter.py", "--test", "https://www.99ranch.com/product-details/1/2/3"])

    ranch99_adapter_module._main()
    assert called["url"] == "https://www.99ranch.com/product-details/1/2/3"
