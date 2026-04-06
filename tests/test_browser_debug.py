from __future__ import annotations

import json
from pathlib import Path

import pytest

from dealwatch.infra import browser_debug
from dealwatch.infra.browser_debug import (
    classify_browser_debug_state,
    collect_browser_debug_open_pages,
    collect_browser_debug_surfaces,
    diagnose_browser_debug,
    resolve_browser_debug_contract,
    write_browser_support_bundle,
)
from dealwatch.infra.config import Settings


def _make_settings(tmp_path: Path) -> Settings:
    settings = Settings(_env_file=None)
    settings.STORAGE_STATE_DIR = tmp_path / "state"
    settings.BROWSER_DEBUG_BUNDLE_DIR = tmp_path / "browser-debug"
    settings.CHROME_REMOTE_DEBUG_PORT = 9333
    settings.CHROME_CDP_URL = ""
    settings.CHROME_ATTACH_MODE = "browser"
    settings.CHROME_USER_DATA_DIR = ""
    settings.CHROME_PROFILE_NAME = ""
    settings.CHROME_PROFILE_DIRECTORY = ""
    settings.CHROME_START_URL = ""
    settings.CHROME_OBSERVE_MS = 0
    return settings


class _FakeConsoleMessage:
    def __init__(self, kind: str, text: str) -> None:
        self._kind = kind
        self._text = text

    def type(self) -> str:
        return self._kind

    def text(self) -> str:
        return self._text


class _FakeResponse:
    def __init__(self, status: int) -> None:
        self.status = status


class _FakeRequest:
    def __init__(self, method: str, url: str, status: int | None = None, error_text: str = "") -> None:
        self.method = method
        self.url = url
        self._status = status
        self._error_text = error_text

    def response(self):
        if self._status is None:
            return None
        return _FakeResponse(self._status)

    def failure(self):
        return {"errorText": self._error_text}


class _FakeAsyncResponseRequest(_FakeRequest):
    async def response(self):
        return _FakeResponse(self._status or 200)


class _FakeClosedAsyncResponseRequest(_FakeRequest):
    async def response(self):
        raise browser_debug.PlaywrightError("Target page, context or browser has been closed")


class _FakePage:
    def __init__(self, *, url: str, title: str, content: str) -> None:
        self.url = url
        self._title = title
        self._content = content
        self.removed_listeners: list[tuple[str, object]] = []

    def on(self, event: str, callback) -> None:
        if event == "console":
            callback(_FakeConsoleMessage("info", "console ready"))
        elif event == "pageerror":
            callback(RuntimeError("page exploded"))
        elif event == "requestfinished":
            callback(_FakeRequest("GET", "https://example.com/api", status=200))
        elif event == "requestfailed":
            callback(_FakeRequest("GET", "https://example.com/fail", error_text="net::ERR_ABORTED"))

    def remove_listener(self, event: str, callback) -> None:
        self.removed_listeners.append((event, callback))

    async def title(self) -> str:
        return self._title

    async def content(self) -> str:
        return self._content

    async def goto(self, url: str, wait_until: str = "load", timeout: int = 15_000) -> None:
        _ = wait_until
        _ = timeout
        self.url = url
        self._title = "Bootstrapped Page"
        self._content = "<html><body>bootstrapped</body></html>"


class _FakeContext:
    def __init__(self, pages: list[_FakePage]) -> None:
        self.pages = pages
        self.closed = False

    async def close(self) -> None:
        self.closed = True

    async def new_page(self) -> _FakePage:
        page = _FakePage(url="about:blank", title="Blank", content="<html><body>blank</body></html>")
        self.pages.append(page)
        return page


class _FakeBrowser:
    def __init__(self, contexts: list[_FakeContext]) -> None:
        self.contexts = contexts
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class _FakeChromium:
    def __init__(self, browser: _FakeBrowser | None = None, context: _FakeContext | None = None) -> None:
        self._browser = browser
        self._context = context

    async def connect_over_cdp(self, _cdp_url: str) -> _FakeBrowser:
        assert self._browser is not None
        return self._browser

    async def launch_persistent_context(self, _user_data_dir: str, **_kwargs) -> _FakeContext:
        assert self._context is not None
        return self._context


class _FakePlaywright:
    def __init__(self, chromium: _FakeChromium) -> None:
        self.chromium = chromium
        self.stopped = False

    async def start(self):
        return self

    async def stop(self) -> None:
        self.stopped = True


def test_resolve_browser_debug_contract_builds_default_cdp_url(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    settings.CHROME_USER_DATA_DIR = str(tmp_path / "chrome")
    settings.CHROME_PROFILE_NAME = "dealwatch"
    settings.CHROME_PROFILE_DIRECTORY = "Profile 13"

    contract = resolve_browser_debug_contract(settings)

    assert contract.cdp_url == "http://127.0.0.1:9333"
    assert contract.requested_profile_label == "dealwatch"
    assert contract.has_profile_contract is True


def test_resolve_browser_debug_contract_requires_three_profile_values(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    settings.CHROME_USER_DATA_DIR = str(tmp_path / "chrome")
    settings.CHROME_PROFILE_NAME = "dealwatch"

    contract = resolve_browser_debug_contract(settings)

    assert contract.has_profile_contract is False
    assert contract.has_any_profile_hint is True


def test_resolve_browser_debug_contract_expands_user_dir_tilde(tmp_path: Path, monkeypatch) -> None:
    settings = _make_settings(tmp_path)
    home_tmp = tmp_path / "home"
    dedicated_root = home_tmp / ".cache" / "dealwatch" / "browser" / "chrome-user-data"
    monkeypatch.setenv("HOME", str(home_tmp))
    settings.CHROME_USER_DATA_DIR = "~/.cache/dealwatch/browser/chrome-user-data"
    settings.CHROME_PROFILE_NAME = "dealwatch"
    settings.CHROME_PROFILE_DIRECTORY = "Profile 21"

    contract = resolve_browser_debug_contract(settings)

    assert contract.user_data_dir == str(dedicated_root)


def test_classify_browser_debug_state_profile_mismatch() -> None:
    status = classify_browser_debug_state(
        attached=True,
        requested_profile_label="dealwatch",
        observed_profile_label="wrong-profile",
        current_page_url="https://example.com",
    )
    assert status == "profile_mismatch"


@pytest.mark.asyncio
async def test_collect_browser_debug_surfaces_captures_console_and_network() -> None:
    page = _FakePage(
        url="https://example.com/login",
        title="Sign in to Example",
        content="<html><body>Please sign in</body></html>",
    )

    surfaces = await collect_browser_debug_surfaces(page, source="existing_browser_session", observe_ms=0)

    assert surfaces["current_page"]["url"] == "https://example.com/login"
    assert surfaces["current_console"][0]["text"] == "console ready"
    finished_events = [item for item in surfaces["current_network"] if item.get("event") == "finished"]
    assert any(item.get("status") == 200 for item in finished_events)
    assert surfaces["login_required"] is True


@pytest.mark.asyncio
async def test_collect_browser_debug_surfaces_treats_target_account_surface_as_logged_in() -> None:
    page = _FakePage(
        url="https://www.target.com/account",
        title="Account : Target",
        content="<html><body>Hi, Member Track Orders Account since March 2, 2024</body></html>",
    )

    surfaces = await collect_browser_debug_surfaces(page, source="existing_browser_session", observe_ms=0)

    assert surfaces["authenticated_account_surface"] is True
    assert surfaces["login_required"] is False


@pytest.mark.asyncio
async def test_collect_browser_debug_surfaces_awaits_async_request_response() -> None:
    page = _FakePage(
        url="https://example.com/health",
        title="Example Health",
        content="<html><body>ok</body></html>",
    )

    def _custom_on(event: str, callback) -> None:
        if event == "console":
            return
        if event == "pageerror":
            return
        if event == "requestfinished":
            callback(_FakeAsyncResponseRequest("GET", "https://example.com/api", status=204))
        if event == "requestfailed":
            return

    page.on = _custom_on  # type: ignore[assignment]
    surfaces = await collect_browser_debug_surfaces(page, source="bootstrapped_page", observe_ms=0)

    assert surfaces["current_network"][0]["status"] == 204


@pytest.mark.asyncio
async def test_collect_browser_debug_open_pages_sorts_canonical_tabs_first() -> None:
    identity_page = _FakePage(
        url="file:///tmp/repo/.runtime-cache/browser-identity/index.html",
        title="DealWatch · 9333 · browser lane",
        content="<html><body>repo-owned browser lane identity tab</body></html>",
    )
    account_page = _FakePage(
        url="https://www.walmart.com/account",
        title="Manage Account - Home - Walmart.com",
        content="<html><body>Hi, Member Reorder My Items</body></html>",
    )
    random_page = _FakePage(
        url="https://example.com",
        title="Example",
        content="<html><body>example</body></html>",
    )

    summaries = await collect_browser_debug_open_pages([random_page, identity_page, account_page])

    assert [item["url"] for item in summaries] == [
        "https://www.walmart.com/account",
        "https://example.com",
        "file:///tmp/repo/.runtime-cache/browser-identity/index.html",
    ]


@pytest.mark.asyncio
async def test_collect_browser_debug_open_pages_deduplicates_urls_and_prefers_non_empty_titles() -> None:
    first_target = _FakePage(
        url="https://www.target.com/account",
        title="",
        content="<html><body>target</body></html>",
    )
    second_target = _FakePage(
        url="https://www.target.com/account",
        title="Account : Target",
        content="<html><body>target</body></html>",
    )

    summaries = await collect_browser_debug_open_pages([first_target, second_target])

    assert summaries == [
        {
            "url": "https://www.target.com/account",
            "title": "Account : Target",
        }
    ]


@pytest.mark.asyncio
async def test_collect_browser_debug_open_pages_collects_ten_unique_urls_before_stopping() -> None:
    pages = [
        _FakePage(
            url=f"https://example.com/{index}",
            title=f"Example {index}",
            content="<html><body>example</body></html>",
        )
        for index in range(9)
    ]
    pages.insert(
        1,
        _FakePage(
            url="https://example.com/0",
            title="",
            content="<html><body>duplicate</body></html>",
        ),
    )
    pages.append(
        _FakePage(
            url="https://example.com/9",
            title="Example 9",
            content="<html><body>example</body></html>",
        )
    )

    summaries = await collect_browser_debug_open_pages(pages)

    assert len(summaries) == 10
    assert {item["url"] for item in summaries} == {
        f"https://example.com/{index}" for index in range(10)
    }


@pytest.mark.asyncio
async def test_collect_browser_debug_surfaces_ignores_closed_request_response() -> None:
    page = _FakePage(
        url="https://example.com/dashboard",
        title="Example Dashboard",
        content="<html><body>ready</body></html>",
    )

    def _custom_on(event: str, callback) -> None:
        if event == "requestfinished":
            callback(_FakeClosedAsyncResponseRequest("GET", "https://example.com/api", status=200))

    page.on = _custom_on  # type: ignore[assignment]
    surfaces = await collect_browser_debug_surfaces(page, source="existing_browser_session", observe_ms=0)

    assert surfaces["current_network"] == []
    assert [event for event, _ in page.removed_listeners] == [
        "console",
        "pageerror",
        "requestfinished",
        "requestfailed",
    ]


@pytest.mark.asyncio
async def test_diagnose_browser_debug_with_existing_browser_session(tmp_path: Path, monkeypatch) -> None:
    settings = _make_settings(tmp_path)
    page = _FakePage(
        url="https://example.com/dashboard",
        title="Example Dashboard",
        content="<html><body>ready</body></html>",
    )
    context = _FakeContext([page])
    browser = _FakeBrowser([context])
    fake = _FakePlaywright(_FakeChromium(browser=browser))
    monkeypatch.setattr(browser_debug, "async_playwright", lambda: fake)

    payload = await diagnose_browser_debug(settings)

    assert payload["status"] == "existing_browser_session"
    assert payload["current_page"]["title"] == "Example Dashboard"
    assert payload["current_console"]
    assert payload["current_network"]
    assert context.closed is False
    assert browser.closed is False


@pytest.mark.asyncio
async def test_diagnose_browser_debug_skips_identity_tab_when_account_tab_exists(tmp_path: Path, monkeypatch) -> None:
    settings = _make_settings(tmp_path)
    identity_page = _FakePage(
        url="file:///tmp/repo/.runtime-cache/browser-identity/index.html",
        title="DealWatch · 9333 · browser lane",
        content="<html><body>repo-owned browser lane identity tab</body></html>",
    )
    account_page = _FakePage(
        url="https://www.target.com/account",
        title="Account : Target",
        content="<html><body>Hi, Member Track Orders Account since March 2, 2024</body></html>",
    )
    context = _FakeContext([identity_page, account_page])
    browser = _FakeBrowser([context])
    fake = _FakePlaywright(_FakeChromium(browser=browser))
    monkeypatch.setattr(browser_debug, "async_playwright", lambda: fake)

    payload = await diagnose_browser_debug(settings)

    assert payload["status"] == "existing_browser_session"
    assert payload["current_page"]["url"] == "https://www.target.com/account"
    assert payload["current_page"]["title"] == "Account : Target"
    assert {item["url"] for item in payload["open_pages"]} == {
        "file:///tmp/repo/.runtime-cache/browser-identity/index.html",
        "https://www.target.com/account",
    }


@pytest.mark.asyncio
async def test_diagnose_browser_debug_requires_user_data_dir_for_persistent(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    settings.CHROME_ATTACH_MODE = "persistent"
    settings.CHROME_PROFILE_NAME = "dealwatch"
    settings.CHROME_PROFILE_DIRECTORY = "Profile 13"

    payload = await diagnose_browser_debug(settings)

    assert payload["status"] == "attach_failed"
    assert payload["reason"] == "profile_contract_incomplete"


@pytest.mark.asyncio
async def test_diagnose_browser_debug_rejects_legacy_shared_chrome_root(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    settings.CHROME_ATTACH_MODE = "browser"
    settings.CHROME_USER_DATA_DIR = "<default-macos-chrome-user-data-root>"
    settings.CHROME_PROFILE_NAME = "dealwatch"
    settings.CHROME_PROFILE_DIRECTORY = "Profile 21"

    payload = await diagnose_browser_debug(settings)

    assert payload["status"] == "attach_failed"
    assert payload["reason"] == "legacy_shared_chrome_root"
    assert payload["profile_truth"]["confirmation_status"] == "legacy_shared_chrome_root"


@pytest.mark.asyncio
async def test_diagnose_browser_debug_bootstraps_start_url_for_persistent_context(tmp_path: Path, monkeypatch) -> None:
    settings = _make_settings(tmp_path)
    settings.CHROME_ATTACH_MODE = "persistent"
    settings.CHROME_USER_DATA_DIR = str(tmp_path / "chrome")
    settings.CHROME_PROFILE_NAME = "dealwatch"
    settings.CHROME_PROFILE_DIRECTORY = "Profile 13"
    settings.CHROME_START_URL = "https://example.com/health"
    chrome_dir = Path(settings.CHROME_USER_DATA_DIR)
    (chrome_dir / settings.CHROME_PROFILE_DIRECTORY).mkdir(parents=True)
    (chrome_dir / "Local State").write_text(
        json.dumps(
            {
                "profile": {
                    "info_cache": {
                        settings.CHROME_PROFILE_DIRECTORY: {"name": settings.CHROME_PROFILE_NAME}
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    context = _FakeContext([])
    fake = _FakePlaywright(_FakeChromium(context=context))
    monkeypatch.setattr(browser_debug, "async_playwright", lambda: fake)

    payload = await diagnose_browser_debug(settings)

    assert payload["status"] == "public_or_unknown"
    assert payload["current_page"]["url"] == "https://example.com/health"
    assert payload["profile_truth"]["confirmation_status"] == "confirmed"
    assert payload["current_page"]["source"] == "bootstrapped_page"


@pytest.mark.asyncio
async def test_diagnose_browser_debug_detects_profile_name_mismatch(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    settings.CHROME_ATTACH_MODE = "persistent"
    settings.CHROME_USER_DATA_DIR = str(tmp_path / "chrome")
    settings.CHROME_PROFILE_NAME = "dealwatch"
    settings.CHROME_PROFILE_DIRECTORY = "Profile 13"
    chrome_dir = Path(settings.CHROME_USER_DATA_DIR)
    (chrome_dir / settings.CHROME_PROFILE_DIRECTORY).mkdir(parents=True)
    (chrome_dir / "Local State").write_text(
        json.dumps(
            {
                "profile": {
                    "info_cache": {
                        settings.CHROME_PROFILE_DIRECTORY: {"name": "wrong-name"}
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    payload = await diagnose_browser_debug(settings)

    assert payload["status"] == "profile_mismatch"
    assert payload["reason"] == "profile_name_mismatch"


def test_write_browser_support_bundle_creates_json(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    diagnosis = {
        "generated_at": "2026-04-03T00:00:00+00:00",
        "status": "attach_failed",
        "contract": {"attach_mode": "browser"},
        "open_pages": [{"url": "https://www.walmart.com/account", "title": "Manage Account - Home - Walmart.com"}],
        "next_actions": ["retry"],
    }

    result = write_browser_support_bundle(settings, diagnosis)

    output_path = Path(result["output_path"])
    assert output_path.is_file() is True
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["diagnosis"]["status"] == "attach_failed"
    assert payload["diagnosis"]["open_pages"][0]["url"] == "https://www.walmart.com/account"
