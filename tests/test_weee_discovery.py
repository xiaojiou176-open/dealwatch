import asyncio

import pytest

from dealwatch.stores.weee.discovery import WeeeDiscovery


class _FakeLocator:
    def __init__(self, count: int) -> None:
        self._count = count

    async def count(self) -> int:
        return self._count


class _FakePage:
    def __init__(self) -> None:
        self.scroll_calls = 0
        self.eval_calls = 0
        self.goto_calls = 0

    async def add_init_script(self, script: str) -> None:
        return None

    async def goto(self, url: str, wait_until: str, timeout: int) -> None:
        self.goto_calls += 1

    async def eval_on_selector_all(self, selector: str, script: str):
        self.eval_calls += 1
        if self.eval_calls == 1:
            return [
                "/zh/product/alpha",
                "https://www.sayweee.com/zh/product/beta",
                "https://evil.com/zh/product/evil",
            ]
        return [
            "/zh/product/alpha",
        ]

    def locator(self, selector: str):
        # Return no-more marker on second loop
        if self.eval_calls >= 2:
            return _FakeLocator(1)
        return _FakeLocator(0)

    async def evaluate(self, script: str) -> None:
        self.scroll_calls += 1

    async def close(self) -> None:
        return None


class _BadPage(_FakePage):
    async def eval_on_selector_all(self, selector: str, script: str):
        raise RuntimeError("boom")


class _BadLocator:
    async def count(self) -> int:
        raise RuntimeError("boom")


class _FakeContext:
    def __init__(self, page: _FakePage) -> None:
        self.page = page

    async def new_page(self) -> _FakePage:
        return self.page


class _FakeClient:
    def __init__(self, context: _FakeContext) -> None:
        self._context = context

    async def get_context(self) -> _FakeContext:
        return self._context


@pytest.mark.asyncio
async def test_weee_discovery_flow(tmp_path, monkeypatch) -> None:
    page = _FakePage()
    client = _FakeClient(_FakeContext(page))
    storage_state = tmp_path / "state.json"

    discovery = WeeeDiscovery(client=client, storage_state_path=storage_state)
    original_sleep = asyncio.sleep
    monkeypatch.setattr(asyncio, "sleep", lambda *_: original_sleep(0))

    links = await discovery.discover_deals()

    assert "https://www.sayweee.com/zh/product/alpha" in links
    assert "https://www.sayweee.com/zh/product/beta" in links
    assert all("evil.com" not in item for item in links)
    assert page.scroll_calls >= 1


@pytest.mark.asyncio
async def test_weee_discovery_extract_links_error(tmp_path) -> None:
    page = _BadPage()
    client = _FakeClient(_FakeContext(page))
    discovery = WeeeDiscovery(client=client, storage_state_path=tmp_path / "state.json")
    links = await discovery._extract_links(page)
    assert links == set()


@pytest.mark.asyncio
async def test_weee_discovery_has_no_more_error() -> None:
    class _Page:
        def locator(self, selector: str):
            return _BadLocator()

    result = await WeeeDiscovery._has_no_more(_Page())
    assert result is False


def test_weee_discovery_normalize_product_url_invalid() -> None:
    assert WeeeDiscovery._normalize_product_url("https://evil.com/zh/product/x") is None
    assert WeeeDiscovery._normalize_product_url("/zh/category/sale") is None


@pytest.mark.asyncio
async def test_weee_discovery_discover_deals_error(tmp_path) -> None:
    class _ErrorPage(_FakePage):
        async def goto(self, url: str, wait_until: str, timeout: int) -> None:
            raise RuntimeError("boom")

    page = _ErrorPage()
    client = _FakeClient(_FakeContext(page))
    discovery = WeeeDiscovery(client=client, storage_state_path=tmp_path / "state.json")

    with pytest.raises(RuntimeError):
        await discovery.discover_deals()
