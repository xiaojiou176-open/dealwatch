import sys
from datetime import datetime, timezone

import pytest

from dealwatch.core.models import Offer, PriceContext
from dealwatch.infra.config import Settings
from dealwatch.stores.target import adapter as target_adapter_module
from dealwatch.stores.target.adapter import TargetAdapter
from dealwatch.stores.target.discovery import TargetDiscovery
from dealwatch.stores.target.parser import TargetParser


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
async def test_target_adapter_discover_and_parse(monkeypatch) -> None:
    settings = Settings()
    client = _FakeClient()
    adapter = TargetAdapter(client, settings)

    async def _discover(self):
        return ["https://www.target.com/p/-/A-13202943"]

    monkeypatch.setattr(TargetDiscovery, "discover_deals", _discover)

    offer = Offer(
        store_id="target",
        product_key="13202943",
        title="Utz Ripples Original Potato Chips - 7.75oz",
        url="https://www.target.com/p/-/A-13202943",
        price=3.49,
        original_price=None,
        fetch_at=datetime(2026, 3, 26, 12, 0, 0, tzinfo=timezone.utc),
        context=PriceContext(region="98102"),
        unit_price_info={"raw": "Utz Ripples Original Potato Chips - 7.75oz"},
    )

    async def _parse(self, _page):
        return offer

    monkeypatch.setattr(TargetParser, "parse", _parse)

    urls = await adapter.discover_deals()
    assert urls == ["https://www.target.com/p/-/A-13202943"]

    parsed = await adapter.parse_product(urls[0])
    assert parsed == offer
    assert client.page.closed is True


@pytest.mark.asyncio
async def test_target_adapter_capture_on_parse_none(monkeypatch) -> None:
    settings = Settings()
    client = _FakeClient()
    adapter = TargetAdapter(client, settings)

    async def _parse(self, _page):
        return None

    monkeypatch.setattr(TargetParser, "parse", _parse)

    called: dict[str, str] = {}

    async def _capture(page, url, reason):
        called["url"] = url
        called["reason"] = reason

    monkeypatch.setattr(adapter, "_capture_failed_page", _capture)

    parsed = await adapter.parse_product("https://www.target.com/p/-/A-13202943")
    assert parsed is None
    assert called["url"] == "https://www.target.com/p/-/A-13202943"
    assert called["reason"] == "parse_returned_none"


def test_target_adapter_main_invokes_test_adapter(monkeypatch) -> None:
    called: dict[str, str] = {}

    async def _fake_test(url: str) -> None:
        called["url"] = url

    monkeypatch.setattr(target_adapter_module.TargetAdapter, "test_adapter", _fake_test)
    monkeypatch.setattr(sys, "argv", ["adapter.py", "--test", "https://www.target.com/p/-/A-13202943"])

    target_adapter_module._main()
    assert called["url"] == "https://www.target.com/p/-/A-13202943"
