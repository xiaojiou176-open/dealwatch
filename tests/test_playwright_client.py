import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from pathlib import Path

import pytest

from dealwatch.infra import playwright_client
from dealwatch.infra.playwright_client import PlaywrightClient


class _FakePage:
    def __init__(self, content: str = "ok") -> None:
        self._content = content
        self.closed = False
        self.url = "https://example.com"
        self.scripts: list[str] = []
        self.goto_args: list[tuple] = []

    async def add_init_script(self, script: str) -> None:
        self.scripts.append(script)

    async def goto(self, url: str, wait_until: str, timeout: int) -> None:
        self.goto_args.append((url, wait_until, timeout))
        self.url = url

    async def content(self) -> str:
        return self._content

    async def close(self) -> None:
        self.closed = True

    async def screenshot(self, path: str) -> None:
        with open(path, "wb") as handle:
            handle.write(b"fake")


class _FakeContext:
    def __init__(self, page: _FakePage) -> None:
        self.page = page
        self.closed = False
        self.route_handler = None
        self.storage_state_path: str | None = None

    async def new_page(self) -> _FakePage:
        return self.page

    async def close(self) -> None:
        self.closed = True

    async def route(self, pattern: str, handler) -> None:
        self.route_handler = handler

    async def storage_state(self, path: str) -> None:
        self.storage_state_path = path
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("{}")


class _FakeBrowser:
    def __init__(self, context: _FakeContext) -> None:
        self.context = context
        self.closed = False
        self.new_context_calls: list[dict] = []

    async def new_context(self, **kwargs):
        self.new_context_calls.append(kwargs)
        return self.context

    async def close(self) -> None:
        self.closed = True


class _FakeChromium:
    def __init__(self, browser: _FakeBrowser) -> None:
        self.browser = browser
        self.launch_args: list[bool] = []

    async def launch(self, headless: bool):
        self.launch_args.append(headless)
        return self.browser


class _FakePlaywright:
    def __init__(self, chromium: _FakeChromium) -> None:
        self.chromium = chromium
        self.stopped = False

    async def start(self):
        return self

    async def stop(self) -> None:
        self.stopped = True


class _FakeRoute:
    def __init__(self, resource_type: str) -> None:
        self.request = SimpleNamespace(resource_type=resource_type)
        self.aborted = False
        self.fallbacked = False

    async def abort(self) -> None:
        self.aborted = True

    async def fallback(self) -> None:
        self.fallbacked = True


@pytest.mark.asyncio
async def test_playwright_context_and_routing(tmp_path, monkeypatch) -> None:
    page = _FakePage()
    context = _FakeContext(page)
    browser = _FakeBrowser(context)
    chromium = _FakeChromium(browser)
    fake = _FakePlaywright(chromium)

    monkeypatch.setattr(playwright_client, "async_playwright", lambda: fake)

    storage_state = tmp_path / "state.json"
    client = PlaywrightClient(
        headless=True,
        storage_state_path=storage_state,
        proxy_server="proxy.example.com:8080",
        block_stylesheets=False,
    )

    async with client:
        ctx = await client.get_context()
        assert ctx is context
        assert context.route_handler is not None

        route = _FakeRoute("image")
        await context.route_handler(route)
        assert route.aborted is True

        route = _FakeRoute("document")
        await context.route_handler(route)
        assert route.fallbacked is True

        await client.save_state()
        assert storage_state.exists()

    assert browser.closed is True
    assert fake.stopped is True


@pytest.mark.asyncio
async def test_playwright_context_with_storage_state(tmp_path, monkeypatch) -> None:
    storage_state = tmp_path / "state.json"
    storage_state.write_text("{}", encoding="utf-8")

    page = _FakePage()
    context = _FakeContext(page)
    browser = _FakeBrowser(context)
    chromium = _FakeChromium(browser)
    fake = _FakePlaywright(chromium)

    monkeypatch.setattr(playwright_client, "async_playwright", lambda: fake)

    client = PlaywrightClient(
        headless=True,
        storage_state_path=storage_state,
    )

    async with client:
        await client.get_context()

    assert browser.new_context_calls[0].get("storage_state") == str(storage_state)


@pytest.mark.asyncio
async def test_fetch_page_return_page(tmp_path, monkeypatch) -> None:
    page = _FakePage("ok")
    context = _FakeContext(page)
    browser = _FakeBrowser(context)
    client = PlaywrightClient(
        headless=True,
        storage_state_path=tmp_path / "state.json",
    )
    client._browser = browser
    original_sleep = asyncio.sleep
    monkeypatch.setattr(
        playwright_client.asyncio,
        "sleep",
        lambda *_: original_sleep(0),
    )

    result = await client.fetch_page("https://example.com", return_page=True)
    assert result is page
    assert page.closed is False


@pytest.mark.asyncio
async def test_fetch_page_blocked_raises(tmp_path, monkeypatch) -> None:
    page = _FakePage("Access Denied by Cloudflare")
    context = _FakeContext(page)
    browser = _FakeBrowser(context)
    client = PlaywrightClient(
        headless=True,
        storage_state_path=tmp_path / "state.json",
    )
    client._browser = browser
    client._blocked_streak = playwright_client._BLOCKED_STREAK_LIMIT - 1
    client._blocked_lock = asyncio.Lock()
    original_sleep = asyncio.sleep
    monkeypatch.setattr(
        playwright_client.asyncio,
        "sleep",
        lambda *_: original_sleep(0),
    )

    async def _noop_record(self, page, content, url, keyword):
        return None

    monkeypatch.setattr(
        PlaywrightClient,
        "_record_blocked",
        _noop_record,
    )

    with pytest.raises(StopAsyncIteration):
        await client.fetch_page("https://example.com", return_page=False)
    assert page.closed is True


@pytest.mark.asyncio
async def test_save_state_without_context(tmp_path) -> None:
    client = PlaywrightClient(
        headless=True,
        storage_state_path=tmp_path / "state.json",
    )
    await client.save_state()


@pytest.mark.asyncio
async def test_record_blocked_writes_logs(tmp_path, monkeypatch) -> None:
    page = _FakePage("blocked")
    client = PlaywrightClient(
        headless=True,
        storage_state_path=tmp_path / "state.json",
    )
    monkeypatch.chdir(tmp_path)
    await client._record_blocked(page, "blocked content", "https://example.com", "access denied")
    run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    blocked_dir = tmp_path / ".runtime-cache" / "runs" / run_date / "blocked"
    assert blocked_dir.exists()
    assert any(path.suffix == ".png" for path in blocked_dir.iterdir())
    assert any(path.suffix == ".html" for path in blocked_dir.iterdir())
    index_json = blocked_dir.parent / "blocked_index.ndjson"
    assert index_json.exists() is True


@pytest.mark.asyncio
async def test_retry_async_wrapper(monkeypatch) -> None:
    calls = {"count": 0}
    original_sleep = asyncio.sleep
    monkeypatch.setattr(playwright_client.asyncio, "sleep", lambda *_: original_sleep(0))

    @playwright_client._retry_async
    async def _flaky():
        calls["count"] += 1
        if calls["count"] < 2:
            raise TimeoutError("timeout")
        return "ok"

    result = await _flaky()
    assert result == "ok"


@pytest.mark.asyncio
async def test_retry_async_budget_exhausted(monkeypatch) -> None:
    original_sleep = asyncio.sleep
    monkeypatch.setattr(playwright_client.asyncio, "sleep", lambda *_: original_sleep(0))

    class _BudgetHolder:
        def __init__(self) -> None:
            self.calls = 0

        def _consume_retry_budget(self) -> bool:
            self.calls += 1
            return False

    @playwright_client._retry_async
    async def _flaky(self):
        raise TimeoutError("timeout")

    holder = _BudgetHolder()
    with pytest.raises(RuntimeError):
        await _flaky(holder)
    assert holder.calls >= 1


@pytest.mark.asyncio
async def test_aenter_failure(monkeypatch, tmp_path) -> None:
    class _BadPlaywright:
        async def start(self):
            raise RuntimeError("boom")

    monkeypatch.setattr(playwright_client, "async_playwright", lambda: _BadPlaywright())
    client = PlaywrightClient(
        headless=True,
        storage_state_path=tmp_path / "state.json",
    )

    with pytest.raises(RuntimeError):
        await client.__aenter__()


@pytest.mark.asyncio
async def test_aenter_launch_failure_cleans_playwright(monkeypatch, tmp_path) -> None:
    class _BadChromium:
        async def launch(self, headless: bool):
            raise RuntimeError("boom")

    class _BadPlaywright:
        def __init__(self):
            self.chromium = _BadChromium()
            self.stopped = False

        async def start(self):
            return self

        async def stop(self) -> None:
            self.stopped = True

    fake = _BadPlaywright()
    monkeypatch.setattr(playwright_client, "async_playwright", lambda: fake)
    client = PlaywrightClient(
        headless=True,
        storage_state_path=tmp_path / "state.json",
    )

    with pytest.raises(RuntimeError):
        await client.__aenter__()
    assert fake.stopped is True


@pytest.mark.asyncio
async def test_blocked_streak_reset() -> None:
    client = PlaywrightClient(headless=True, storage_state_path="state.json")
    count = await client._update_blocked_streak(True)
    assert count == 1
    count = await client._update_blocked_streak(False)
    assert count == 0


@pytest.mark.asyncio
async def test_retry_async_unreachable(monkeypatch) -> None:
    monkeypatch.setattr(playwright_client, "_RETRY_ATTEMPTS", 0)

    @playwright_client._retry_async
    async def _noop():
        return "ok"

    with pytest.raises(RuntimeError):
        await _noop()


@pytest.mark.asyncio
async def test_get_context_without_browser(tmp_path) -> None:
    client = PlaywrightClient(headless=True, storage_state_path=tmp_path / "state.json")
    with pytest.raises(RuntimeError):
        await client.get_context()


@pytest.mark.asyncio
async def test_get_context_storage_state_oserror(tmp_path, monkeypatch) -> None:
    page = _FakePage()
    context = _FakeContext(page)
    browser = _FakeBrowser(context)
    client = PlaywrightClient(headless=True, storage_state_path=tmp_path / "state.json")
    client._browser = browser

    def _raise_exists(self) -> bool:
        raise OSError("boom")

    monkeypatch.setattr(Path, "exists", _raise_exists)

    await client.get_context()
    assert browser.new_context_calls[0].get("storage_state") is None


@pytest.mark.asyncio
async def test_get_context_new_context_failure(tmp_path) -> None:
    page = _FakePage()
    context = _FakeContext(page)

    class _BadBrowser(_FakeBrowser):
        async def new_context(self, **kwargs):
            raise RuntimeError("boom")

    browser = _BadBrowser(context)
    client = PlaywrightClient(headless=True, storage_state_path=tmp_path / "state.json")
    client._browser = browser

    with pytest.raises(RuntimeError):
        await client.get_context()


@pytest.mark.asyncio
async def test_aexit_close_failures(tmp_path) -> None:
    client = PlaywrightClient(headless=True, storage_state_path=tmp_path / "state.json")

    class _BadClose:
        async def close(self):
            raise RuntimeError("boom")

    class _BadStop:
        async def stop(self):
            raise RuntimeError("boom")

    client._context = _BadClose()
    client._browser = _BadClose()
    client._playwright = _BadStop()

    await client.__aexit__(None, None, None)


@pytest.mark.asyncio
async def test_save_state_failure(tmp_path) -> None:
    client = PlaywrightClient(headless=True, storage_state_path=tmp_path / "state.json")

    class _BadContext:
        async def storage_state(self, path: str) -> None:
            raise RuntimeError("boom")

    client._context = _BadContext()
    with pytest.raises(RuntimeError):
        await client.save_state()


@pytest.mark.asyncio
async def test_apply_routing_failure(tmp_path) -> None:
    client = PlaywrightClient(headless=True, storage_state_path=tmp_path / "state.json")

    class _BadContext:
        async def route(self, pattern: str, handler) -> None:
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await client._apply_routing(_BadContext())


@pytest.mark.asyncio
async def test_record_blocked_mkdir_failure(tmp_path, monkeypatch) -> None:
    client = PlaywrightClient(headless=True, storage_state_path=tmp_path / "state.json")
    page = _FakePage("blocked")

    def _raise(*args, **kwargs):
        raise OSError("boom")

    monkeypatch.setattr(Path, "mkdir", _raise)
    await client._record_blocked(page, "blocked content", "https://example.com", "access denied")


@pytest.mark.asyncio
async def test_record_blocked_screenshot_failure(tmp_path, monkeypatch) -> None:
    client = PlaywrightClient(headless=True, storage_state_path=tmp_path / "state.json")
    page = _FakePage("blocked")

    async def _bad_screenshot(path: str) -> None:
        raise OSError("boom")

    monkeypatch.setattr(page, "screenshot", _bad_screenshot)
    monkeypatch.chdir(tmp_path)
    await client._record_blocked(page, "blocked content", "https://example.com", "access denied")
    run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    blocked_dir = tmp_path / ".runtime-cache" / "runs" / run_date / "blocked"
    assert any(path.suffix == ".html" for path in blocked_dir.iterdir())


@pytest.mark.asyncio
async def test_record_blocked_content_failure(tmp_path, monkeypatch) -> None:
    client = PlaywrightClient(headless=True, storage_state_path=tmp_path / "state.json")
    page = _FakePage("blocked")

    original_write_text = Path.write_text

    def _write_text(self, data, *args, **kwargs):
        if self.suffix == ".txt":
            raise OSError("boom")
        return original_write_text(self, data, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", _write_text)
    monkeypatch.chdir(tmp_path)
    await client._record_blocked(page, "blocked content", "https://example.com", "access denied")
    run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    blocked_dir = tmp_path / ".runtime-cache" / "runs" / run_date / "blocked"
    assert any(path.suffix == ".png" for path in blocked_dir.iterdir())


def test_proxy_config_invalid() -> None:
    proxy = playwright_client.PlaywrightClient._build_proxy_config("http://")
    assert proxy == {"server": "http://"}


@pytest.mark.asyncio
async def test_routing_stylesheet_blocked(tmp_path, monkeypatch) -> None:
    page = _FakePage()
    context = _FakeContext(page)
    browser = _FakeBrowser(context)
    chromium = _FakeChromium(browser)
    fake = _FakePlaywright(chromium)

    monkeypatch.setattr(playwright_client, "async_playwright", lambda: fake)
    client = PlaywrightClient(
        headless=True,
        storage_state_path=tmp_path / "state.json",
        block_stylesheets=True,
    )

    async with client:
        ctx = await client.get_context()
        route = _FakeRoute("stylesheet")
        await ctx.route_handler(route)
        assert route.aborted is True
