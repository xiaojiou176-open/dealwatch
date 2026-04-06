import sys
from datetime import datetime, timezone

import pytest

from dealwatch.core.models import Offer, PriceContext, SkipReason
from dealwatch.infra.config import Settings
from dealwatch.stores.base_adapter import SkipParse
from dealwatch.stores.weee import adapter as weee_adapter_module
from dealwatch.stores.weee.adapter import WeeeAdapter
from dealwatch.stores.weee.discovery import WeeeDiscovery
from dealwatch.stores.weee.parser import WeeeParser


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
async def test_weee_adapter_discover_and_parse(monkeypatch) -> None:
    settings = Settings()
    client = _FakeClient()
    adapter = WeeeAdapter(client, settings)

    async def _discover(self):
        return ["https://example.com"]

    monkeypatch.setattr(WeeeDiscovery, "discover_deals", _discover)

    offer = Offer(
        store_id="weee",
        product_key="p1",
        title="Test",
        url="https://example.com",
        price=1.0,
        original_price=None,
        fetch_at=datetime(2026, 1, 18, 12, 0, 0, tzinfo=timezone.utc),
        context=PriceContext(region="00000"),
        unit_price_info={},
    )
    async def _parse(self, _page):
        return offer

    monkeypatch.setattr(WeeeParser, "parse", _parse)

    urls = await adapter.discover_deals()
    assert urls == ["https://example.com"]

    parsed = await adapter.parse_product("https://example.com")
    assert parsed == offer
    assert client.page.closed is True


@pytest.mark.asyncio
async def test_weee_adapter_capture_on_parse_none(monkeypatch) -> None:
    settings = Settings()
    client = _FakeClient()
    adapter = WeeeAdapter(client, settings)

    async def _parse(self, _page):
        return None

    monkeypatch.setattr(WeeeParser, "parse", _parse)

    called: dict[str, str] = {}

    async def _capture(page, url, reason):
        called["url"] = url
        called["reason"] = reason

    monkeypatch.setattr(adapter, "_capture_failed_page", _capture)

    parsed = await adapter.parse_product("https://example.com")
    assert parsed is None
    assert called["url"] == "https://example.com"
    assert called["reason"] == "parse_returned_none"


@pytest.mark.asyncio
async def test_weee_adapter_capture_on_exception(monkeypatch) -> None:
    settings = Settings()
    client = _FakeClient()
    adapter = WeeeAdapter(client, settings)

    async def _parse(self, _page):
        raise RuntimeError("boom")

    monkeypatch.setattr(WeeeParser, "parse", _parse)

    called: dict[str, str] = {}

    async def _capture(page, url, reason):
        called["url"] = url
        called["reason"] = reason

    monkeypatch.setattr(adapter, "_capture_failed_page", _capture)

    parsed = await adapter.parse_product("https://example.com")
    assert parsed is None
    assert called["url"] == "https://example.com"
    assert called["reason"] == "parse_exception:RuntimeError"


@pytest.mark.asyncio
async def test_weee_adapter_skip_parse_bubbles(monkeypatch) -> None:
    settings = Settings()
    client = _FakeClient()
    adapter = WeeeAdapter(client, settings)

    async def _parse(self, _page):
        raise SkipParse(SkipReason.OUT_OF_STOCK)

    monkeypatch.setattr(WeeeParser, "parse", _parse)

    with pytest.raises(SkipParse):
        await adapter.parse_product("https://example.com")


def test_weee_adapter_main_invokes_test_adapter(monkeypatch) -> None:
    called: dict[str, str] = {}

    async def _fake_test(url: str) -> None:
        called["url"] = url

    monkeypatch.setattr(weee_adapter_module.WeeeAdapter, "test_adapter", _fake_test)
    monkeypatch.setattr(sys, "argv", ["adapter.py", "--test", "https://example.com/p1"])

    weee_adapter_module._main()
    assert called["url"] == "https://example.com/p1"
