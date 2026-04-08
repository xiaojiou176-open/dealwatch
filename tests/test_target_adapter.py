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
        self.wait_calls: list[int] = []

    async def content(self) -> str:
        return "<html><body>fake</body></html>"

    async def screenshot(self, path: str) -> None:
        return None

    async def wait_for_timeout(self, timeout_ms: int) -> None:
        self.wait_calls.append(timeout_ms)

    async def close(self) -> None:
        self.closed = True

    def locator(self, selector: str):
        return _FakeLocator(None)


class _FakeLocator:
    def __init__(self, text: str | None) -> None:
        self._text = text
        self.first = self

    async def count(self) -> int:
        return 0 if self._text is None else 1

    async def text_content(self) -> str | None:
        return self._text


class _FakeClient:
    def __init__(self) -> None:
        self.storage_state_path = "state.json"
        self.page = _FakePage()
        self.last_fetch_kwargs: dict[str, object] = {}

    async def fetch_page(self, url: str, wait_until: str = "networkidle", return_page: bool = False):
        self.last_fetch_kwargs = {
            "url": url,
            "wait_until": wait_until,
            "return_page": return_page,
        }
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
    assert client.last_fetch_kwargs["wait_until"] == "domcontentloaded"
    assert client.last_fetch_kwargs["return_page"] is True


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


@pytest.mark.asyncio
async def test_target_adapter_waits_for_price_signal_before_parse(monkeypatch) -> None:
    class _DynamicPage(_FakePage):
        def __init__(self) -> None:
            super().__init__()
            self.summary_ready = False

        async def content(self) -> str:
            return "<html><body>no price yet</body></html>"

        async def wait_for_timeout(self, timeout_ms: int) -> None:
            await super().wait_for_timeout(timeout_ms)
            self.summary_ready = True

        def locator(self, selector: str):
            if selector == "#above-the-fold-information" and self.summary_ready:
                return _FakeLocator("$5.39 Add to cart")
            return _FakeLocator(None)

    settings = Settings()
    client = _FakeClient()
    client.page = _DynamicPage()
    adapter = TargetAdapter(client, settings)

    offer = Offer(
        store_id="target",
        product_key="17093199",
        title="Fairlife Lactose-Free 2% Chocolate Milk - 52 fl oz",
        url="https://www.target.com/p/fairlife-lactose-free-2-chocolate-milk-52-fl-oz/-/A-17093199",
        price=5.39,
        original_price=None,
        fetch_at=datetime(2026, 4, 8, 12, 0, 0, tzinfo=timezone.utc),
        context=PriceContext(region="98102"),
        unit_price_info={"raw": "Fairlife Lactose-Free 2% Chocolate Milk - 52 fl oz"},
    )

    async def _parse(self, page):
        summary = await self._text_by_selector(page, "#above-the-fold-information")
        return offer if summary else None

    monkeypatch.setattr(TargetParser, "parse", _parse)

    parsed = await adapter.parse_product(offer.url)

    assert parsed == offer
    assert client.page.wait_calls == [adapter._PRICE_WAIT_DELAY_MS]
