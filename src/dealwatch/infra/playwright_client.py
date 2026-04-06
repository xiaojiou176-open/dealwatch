from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
from datetime import datetime, timezone
from urllib.parse import urlsplit
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
    Error as PlaywrightError,
    async_playwright,
)

from dealwatch.infra.retry_budget import RetryBudget

#########################################################
# Constants
#########################################################
_DEFAULT_TIMEOUT_MS: Final[int] = 30_000
_RETRY_ATTEMPTS: Final[int] = 3
_RETRY_BASE_DELAY: Final[float] = 0.6
_RETRY_MAX_DELAY: Final[float] = 4.0
_JITTER_MIN: Final[float] = 0.5
_JITTER_MAX: Final[float] = 1.5
_BLOCKED_RESOURCE_TYPES: Final[set[str]] = {
    "image",
    "font",
    "media",
    "stylesheet",
    "texttrack",
}
_BLOCKED_KEYWORDS: Final[tuple[str, ...]] = (
    "verify you are human",
    "cloudflare",
    "access denied",
    "403 forbidden",
)
_BLOCKED_STREAK_LIMIT: Final[int] = 3
_BLOCKED_SIGNAL: Final[str] = "IP_RESTRICTED"
_RUNS_DIR: Final[Path] = Path(".runtime-cache") / "runs"
_RUN_DATE_FORMAT: Final[str] = "%Y-%m-%d"
_BLOCKED_DIR_NAME: Final[str] = "blocked"
_BLOCKED_INDEX_NAME: Final[str] = "blocked_index.ndjson"
_BLOCKED_INDEX_MD: Final[str] = "blocked_index.md"

_DESKTOP_USER_AGENTS: Final[list[str]] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6_3) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) "
    "Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13.6; rv:122.0) "
    "Gecko/20100101 Firefox/122.0",
]

_STEALTH_SCRIPT: Final[str] = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
"""


#########################################################
# Retry Helpers
#########################################################
_RETRY_EXCEPTIONS: Final[tuple[type[BaseException], ...]] = (
    PlaywrightTimeoutError,
    PlaywrightError,
    TimeoutError,
)


def _compute_backoff(attempt: int) -> float:
    base = min(_RETRY_BASE_DELAY * (2 ** (attempt - 1)), _RETRY_MAX_DELAY)
    return base + random.uniform(0.0, 0.3)


def _retry_async(func):
    async def wrapper(*args, **kwargs):
        budget_holder = args[0] if args else None
        last_exc: BaseException | None = None
        for attempt in range(1, _RETRY_ATTEMPTS + 1):
            try:
                return await func(*args, **kwargs)
            except _RETRY_EXCEPTIONS as exc:
                last_exc = exc
                if attempt >= _RETRY_ATTEMPTS:
                    raise
                if (
                    budget_holder is not None
                    and hasattr(budget_holder, "_consume_retry_budget")
                    and not budget_holder._consume_retry_budget()
                ):
                    raise RuntimeError("Retry budget exhausted") from exc
                await asyncio.sleep(_compute_backoff(attempt))

        if last_exc is not None:
            raise last_exc

        raise RuntimeError("Retry wrapper reached unreachable state")

    return wrapper


#########################################################
# Client
#########################################################
@dataclass(slots=True)
class PlaywrightClient:
    headless: bool
    storage_state_path: Path
    proxy_server: str | None = None
    block_stylesheets: bool = True
    retry_budget: int | RetryBudget | None = None
    runs_dir: Path | None = None

    _logger: logging.Logger = field(
        init=False, default_factory=lambda: logging.getLogger(__name__)
    )
    _playwright: Playwright | None = field(init=False, default=None)
    _browser: Browser | None = field(init=False, default=None)
    _context: BrowserContext | None = field(init=False, default=None)
    _user_agent: str | None = field(init=False, default=None)
    _proxy_config: dict[str, str] | None = field(init=False, default=None)
    _blocked_streak: int = field(init=False, default=0)
    _blocked_lock: asyncio.Lock | None = field(init=False, default=None)
    _blocked_index_lock: asyncio.Lock | None = field(init=False, default=None)
    _context_lock: asyncio.Lock | None = field(init=False, default=None)
    _retry_budget: RetryBudget | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        if not isinstance(self.storage_state_path, Path):
            self.storage_state_path = Path(self.storage_state_path)
        if self.runs_dir is not None and not isinstance(self.runs_dir, Path):
            self.runs_dir = Path(self.runs_dir)
        if self.runs_dir is None:
            self.runs_dir = _RUNS_DIR
        self._proxy_config = self._build_proxy_config(self.proxy_server)
        if isinstance(self.retry_budget, RetryBudget):
            self._retry_budget = self.retry_budget
        elif self.retry_budget is None or int(self.retry_budget) <= 0:
            self._retry_budget = None
        else:
            self._retry_budget = RetryBudget(int(self.retry_budget))

    async def __aenter__(self) -> "PlaywrightClient":
        try:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless
            )
        except Exception as exc:
            self._logger.exception("Failed to launch browser: %s", exc)
            await self._cleanup_startup_failure()
            raise

        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._context is not None:
            try:
                await self._context.close()
            except Exception as close_exc:
                self._logger.warning("Failed to close context: %s", close_exc)

        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception as close_exc:
                self._logger.warning("Failed to close browser: %s", close_exc)

        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception as close_exc:
                self._logger.warning("Failed to stop Playwright: %s", close_exc)

    async def get_context(self) -> BrowserContext:
        if self._context is not None:
            return self._context

        if self._browser is None:
            raise RuntimeError("PlaywrightClient is not started. Use 'async with'.")

        if self._blocked_lock is None:
            self._blocked_lock = asyncio.Lock()
        if self._context_lock is None:
            self._context_lock = asyncio.Lock()

        async with self._context_lock:
            if self._context is not None:
                return self._context

            storage_state = None
            try:
                if self.storage_state_path.exists():
                    storage_state = str(self.storage_state_path)
            except OSError as exc:
                self._logger.warning("Failed to check storage state path: %s", exc)

            self._user_agent = random.choice(_DESKTOP_USER_AGENTS)
            context_kwargs: dict[str, object] = {
                "user_agent": self._user_agent,
            }
            if self._proxy_config is not None:
                context_kwargs["proxy"] = self._proxy_config
            try:
                if storage_state is None:
                    self._context = await self._browser.new_context(**context_kwargs)
                else:
                    context_kwargs["storage_state"] = storage_state
                    self._context = await self._browser.new_context(**context_kwargs)

                await self._apply_routing(self._context)
            except Exception as exc:
                self._logger.exception("Failed to create browser context: %s", exc)
                raise

        return self._context

    async def save_state(self) -> None:
        if self._context is None:
            self._logger.warning("No active context to save state from.")
            return

        try:
            self.storage_state_path.parent.mkdir(parents=True, exist_ok=True)
            await self._context.storage_state(path=str(self.storage_state_path))
        except Exception as exc:
            self._logger.exception("Failed to save storage state: %s", exc)
            raise

    @_retry_async
    async def fetch_page(
        self,
        url: str,
        wait_until: str = "networkidle",
        timeout: int = _DEFAULT_TIMEOUT_MS,
        return_page: bool = False,
    ) -> str | Page:
        context = await self.get_context()
        page: Page | None = None

        try:
            page = await context.new_page()
            await page.add_init_script(_STEALTH_SCRIPT)
            await asyncio.sleep(random.uniform(_JITTER_MIN, _JITTER_MAX))
            await page.goto(url, wait_until=wait_until, timeout=timeout)

            content = await page.content()
            blocked_keyword = self._find_blocked_keyword(content)
            blocked = blocked_keyword is not None
            if blocked:
                self._logger.warning("Blocked keyword detected: %s", url)
                await self._record_blocked(page, content, url, blocked_keyword)

            streak = await self._update_blocked_streak(blocked)
            if blocked and streak >= _BLOCKED_STREAK_LIMIT:
                raise StopAsyncIteration(f"{_BLOCKED_SIGNAL}:{url}")

            if return_page:
                return page

            await page.close()
            return content
        except Exception:
            if page is not None:
                try:
                    await page.close()
                except Exception as close_exc:
                    self._logger.warning("Failed to close page: %s", close_exc)
            raise

    #########################################################
    # Internal
    #########################################################
    async def _apply_routing(self, context: BrowserContext) -> None:
        async def handler(route):
            resource_type = route.request.resource_type
            blocked_types = set(_BLOCKED_RESOURCE_TYPES)
            if not self.block_stylesheets:
                blocked_types.discard("stylesheet")
            if resource_type in blocked_types:
                await route.abort()
                return

            await route.fallback()

        try:
            await context.route("**/*", handler)
        except Exception as exc:
            self._logger.exception("Failed to apply routing rules: %s", exc)
            raise

    @staticmethod
    def _is_blocked_content(content: str) -> bool:
        return PlaywrightClient._find_blocked_keyword(content) is not None

    @staticmethod
    def _find_blocked_keyword(content: str) -> str | None:
        lowered = content.lower()
        for keyword in _BLOCKED_KEYWORDS:
            if keyword in lowered:
                return keyword
        return None

    async def _update_blocked_streak(self, blocked: bool) -> int:
        if self._blocked_lock is None:
            self._blocked_lock = asyncio.Lock()
        async with self._blocked_lock:
            if blocked:
                self._blocked_streak += 1
            else:
                self._blocked_streak = 0
            return self._blocked_streak

    async def _record_blocked(
        self,
        page: Page,
        content: str,
        url: str,
        keyword: str | None,
    ) -> None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        run_dir = self._resolve_run_dir()
        if run_dir is None:
            return

        blocked_dir = run_dir / _BLOCKED_DIR_NAME
        try:
            blocked_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            self._logger.warning("Failed to create blocked dir: %s", exc)
            return

        url_hash = hashlib.md5(url.encode("utf-8")).hexdigest()[:8]
        screenshot_path = blocked_dir / f"blocked_{timestamp}_{url_hash}.png"
        content_path = blocked_dir / f"blocked_{timestamp}_{url_hash}.html"

        try:
            await page.screenshot(path=str(screenshot_path))
        except Exception as exc:
            self._logger.warning("Failed to save blocked screenshot: %s", exc)

        try:
            content_path.write_text(content, encoding="utf-8")
        except Exception as exc:
            self._logger.warning("Failed to save blocked content: %s", exc)

        entry = {
            "captured_at": timestamp,
            "url": url,
            "keyword": keyword or "",
            "user_agent": self._user_agent or "",
            "content_path": self._safe_rel_path(content_path, run_dir),
            "screenshot_path": self._safe_rel_path(screenshot_path, run_dir),
        }
        await self._append_blocked_index(run_dir, entry)

    def _resolve_run_dir(self) -> Path | None:
        run_date = datetime.now(timezone.utc).strftime(_RUN_DATE_FORMAT)
        base_dir = self.runs_dir or _RUNS_DIR
        run_dir = base_dir / run_date
        try:
            run_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._logger.warning("Failed to create run dir: %s", exc)
            return None
        return run_dir

    async def _append_blocked_index(self, run_dir: Path, entry: dict) -> None:
        if self._blocked_index_lock is None:
            self._blocked_index_lock = asyncio.Lock()

        index_json = run_dir / _BLOCKED_INDEX_NAME
        index_md = run_dir / _BLOCKED_INDEX_MD

        try:
            async with self._blocked_index_lock:
                try:
                    with index_json.open("a", encoding="utf-8") as handle:
                        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
                except OSError as exc:
                    self._logger.warning("Failed to append blocked index json: %s", exc)

                try:
                    line = (
                        f"- {entry.get('captured_at')} "
                        f"[blocked]({entry.get('content_path')}) "
                        f"(screenshot: {entry.get('screenshot_path')}) "
                        f"{entry.get('keyword')} {entry.get('url')}\n"
                    )
                    with index_md.open("a", encoding="utf-8") as handle:
                        handle.write(line)
                except OSError as exc:
                    self._logger.warning("Failed to append blocked index md: %s", exc)
        except Exception as exc:
            self._logger.warning("Failed to append blocked index: %s", exc)

    @staticmethod
    def _safe_rel_path(path: Path, base: Path) -> str:
        try:
            return str(path.relative_to(base))
        except ValueError:
            return str(path)

    @staticmethod
    def _build_proxy_config(proxy_server: str | None) -> dict[str, str] | None:
        if not proxy_server:
            return None

        raw = str(proxy_server).strip()
        if not raw:
            return None

        if "://" not in raw:
            raw = f"http://{raw}"

        parsed = urlsplit(raw)
        if not parsed.hostname:
            return {"server": proxy_server}

        server = f"{parsed.scheme}://{parsed.hostname}"
        if parsed.port:
            server = f"{server}:{parsed.port}"

        proxy: dict[str, str] = {"server": server}
        if parsed.username:
            proxy["username"] = parsed.username
        if parsed.password:
            proxy["password"] = parsed.password

        return proxy

    def _consume_retry_budget(self) -> bool:
        if self._retry_budget is None:
            return True
        return self._retry_budget.consume()

    async def _cleanup_startup_failure(self) -> None:
        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception as close_exc:
                self._logger.warning("Failed to close browser after startup error: %s", close_exc)
            self._browser = None

        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception as close_exc:
                self._logger.warning("Failed to stop Playwright after startup error: %s", close_exc)
            self._playwright = None
