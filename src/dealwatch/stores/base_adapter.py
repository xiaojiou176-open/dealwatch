from __future__ import annotations

import asyncio
import functools
import hashlib
from html.parser import HTMLParser
import json
import logging
import re
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable, ClassVar, List, Optional, ParamSpec
from urllib.parse import urlsplit, urlunsplit

from playwright.async_api import Page

from dealwatch.core.artifacts import ArtifactManager
from dealwatch.core.models import Offer, SkipReason
from dealwatch.infra.config import Settings
from dealwatch.infra.playwright_client import PlaywrightClient
from dealwatch.infra.retry_budget import RetryBudget


#########################################################
# Safe Parse Decorator
#########################################################
_P = ParamSpec("_P")
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_STORAGE_STATE_DIR = _PROJECT_ROOT / ".runtime-cache" / "cache" / "state"


#########################################################
# Exceptions
#########################################################
class SkipParse(Exception):
    def __init__(self, reason: SkipReason) -> None:
        super().__init__(reason.value)
        self.reason = reason


def safe_parse(
    func: Callable[_P, Awaitable[Optional[Offer]]]
) -> Callable[_P, Awaitable[Optional[Offer]]]:
    @functools.wraps(func)
    async def wrapper(self: "BaseStoreAdapter", *args: _P.args, **kwargs: _P.kwargs) -> Optional[Offer]:
        try:
            return await func(self, *args, **kwargs)
        except (StopIteration, StopAsyncIteration, SkipParse):
            raise
        except Exception as exc:
            self.logger.exception("Parse failed in %s: %s", func.__name__, exc)
            return None

    return wrapper


#########################################################
# Base Adapter
#########################################################
class BaseStoreAdapter(ABC):
    store_id: str
    base_url: str
    cashback_merchant_key: ClassVar[str | None] = None
    FAILURE_DIR_NAME: ClassVar[str] = "failures"
    _failure_index_lock: ClassVar[asyncio.Lock | None] = None

    def __init__(self, client: PlaywrightClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings
        self.logger = logging.getLogger(f"dealwatch.stores.{self.store_id}")

    def __repr__(self) -> str:
        return f"StoreAdapter(id={self.store_id})"

    @abstractmethod
    async def discover_deals(self) -> List[str]:
        """Return a list of product detail URLs from promo pages."""

    @abstractmethod
    async def parse_product(self, url: str) -> Optional[Offer]:
        """Parse a product detail page into a normalized Offer."""

    @classmethod
    def normalize_product_url(cls, raw_url: str) -> str | None:
        parsed = urlsplit(raw_url.strip())
        base_host = urlsplit(cls.base_url).netloc.lower()
        if parsed.netloc.lower() != base_host:
            return None
        return urlunsplit(
            (
                parsed.scheme or "https",
                parsed.netloc.lower(),
                parsed.path.rstrip("/") or "/",
                "",
                "",
            )
        )

    @classmethod
    def get_cashback_merchant_key(cls) -> str:
        return cls.cashback_merchant_key or cls.store_id

    @staticmethod
    async def test_adapter(url: str) -> None:
        settings = Settings()
        adapter_cls = None

        from dealwatch.stores import STORE_REGISTRY

        for candidate in STORE_REGISTRY.values():
            if url.startswith(candidate.base_url):
                adapter_cls = candidate
                break

        if adapter_cls is None:
            print(f"[SelfTest] No adapter matches URL: {url}")
            return

        storage_state_path = BaseStoreAdapter._build_storage_state_path(
            settings.ZIP_CODE,
            settings.STORAGE_STATE_DIR,
        )
        retry_budget = (
            RetryBudget(settings.PLAYWRIGHT_RETRY_BUDGET)
            if settings.PLAYWRIGHT_RETRY_BUDGET and settings.PLAYWRIGHT_RETRY_BUDGET > 0
            else None
        )
        async with PlaywrightClient(
            headless=settings.PLAYWRIGHT_HEADLESS,
            storage_state_path=storage_state_path,
            proxy_server=settings.PROXY_SERVER or None,
            block_stylesheets=settings.PLAYWRIGHT_BLOCK_STYLESHEETS,
            retry_budget=retry_budget,
        ) as client:
            adapter = adapter_cls(client, settings)
            offer = await adapter.parse_product(url)

            if offer is None:
                print("[SelfTest] parse_product returned None")
                BaseStoreAdapter._print_diagnostics(adapter)
                return

            print("[SelfTest] Title:", offer.title)
            print("[SelfTest] Price:", offer.price)
            print("[SelfTest] Original Price:", offer.original_price)
            print("[SelfTest] Unit Info:", offer.unit_price_info)
            print("[SelfTest] URL:", offer.url)

            BaseStoreAdapter._print_diagnostics(adapter)

    #########################################################
    # Internal
    #########################################################
    @staticmethod
    def _build_storage_state_path(
        zip_code: str,
        base_dir: Path | str | None = None,
    ) -> Path:
        safe = "".join(ch for ch in str(zip_code) if ch.isalnum())
        if not safe:
            safe = "default"
        base_path = Path(base_dir) if base_dir is not None else _DEFAULT_STORAGE_STATE_DIR
        return base_path / f"storage_state_{safe}.json"

    @staticmethod
    def _print_diagnostics(adapter: "BaseStoreAdapter") -> None:
        parser = getattr(adapter, "_parser", None)
        debug = getattr(parser, "last_debug", None)
        if isinstance(debug, dict) and debug:
            print("[SelfTest] Diagnostics:")
            for key, value in debug.items():
                print(f"  - {key}: {value}")

    #########################################################
    # Failure Capture
    #########################################################
    async def _capture_failed_page(
        self,
        page: Page,
        url: str,
        reason: str,
    ) -> None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        url_hash = hashlib.md5(url.encode("utf-8")).hexdigest()[:8]
        try:
            runs_dir = getattr(self.settings, "RUNS_DIR", None)
            manager = ArtifactManager(base_dir=runs_dir) if runs_dir else ArtifactManager()
            run_dir = manager.get_run_dir()
        except Exception as exc:
            self.logger.warning("Failed to resolve run directory: %s", exc)
            return

        failure_dir = run_dir / self.FAILURE_DIR_NAME / self.store_id

        try:
            failure_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            self.logger.warning("Failed to create failure dir: %s", exc)
            return

        html_path = failure_dir / f"{timestamp}_{url_hash}.html"
        screenshot_path = failure_dir / f"{timestamp}_{url_hash}.png"
        text_path = failure_dir / f"{timestamp}_{url_hash}.txt"
        meta_path = failure_dir / f"{timestamp}_{url_hash}.json"

        content = ""
        try:
            content = await page.content()
            html_path.write_text(content, encoding="utf-8")
        except Exception as exc:
            self.logger.warning("Failed to save failure HTML: %s", exc)

        try:
            await page.screenshot(path=str(screenshot_path))
        except Exception as exc:
            self.logger.warning("Failed to save failure screenshot: %s", exc)

        text_content = ""
        try:
            text_content = await page.inner_text("body")
        except Exception:
            if content:
                text_content = self._extract_text_from_html(content)
        if text_content:
            try:
                text_path.write_text(text_content, encoding="utf-8")
            except Exception as exc:
                self.logger.warning("Failed to save failure text: %s", exc)

        debug = getattr(getattr(self, "_parser", None), "last_debug", None)
        payload = {
            "store_id": self.store_id,
            "url": url,
            "reason": self._sanitize_reason(reason),
            "captured_at": timestamp,
            "debug": debug if isinstance(debug, dict) else {},
        }

        try:
            meta_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            self.logger.warning("Failed to save failure metadata: %s", exc)

        index_entry = {
            **payload,
            "html_path": self._safe_rel_path(html_path, run_dir),
            "screenshot_path": self._safe_rel_path(screenshot_path, run_dir),
            "text_path": self._safe_rel_path(text_path, run_dir),
            "meta_path": self._safe_rel_path(meta_path, run_dir),
        }
        await self._append_failure_index(run_dir, index_entry)

    @staticmethod
    def _sanitize_reason(reason: str) -> str:
        text = (reason or "").strip()
        if not text:
            return "unknown"
        return re.sub(r"[^a-zA-Z0-9._:-]+", "_", text)

    @classmethod
    def _get_failure_index_lock(cls) -> asyncio.Lock:
        if cls._failure_index_lock is None:
            cls._failure_index_lock = asyncio.Lock()
        return cls._failure_index_lock

    async def _append_failure_index(self, run_dir: Path, entry: dict) -> None:
        index_json = run_dir / "failures_index.ndjson"
        index_md = run_dir / "failures_index.md"
        lock = self._get_failure_index_lock()

        try:
            async with lock:
                try:
                    with index_json.open("a", encoding="utf-8") as handle:
                        handle.write(
                            json.dumps(entry, ensure_ascii=False) + "\n"
                        )
                except OSError as exc:
                    self.logger.warning("Failed to append failure index json: %s", exc)

                try:
                    html_path = entry.get("html_path", "")
                    screenshot_path = entry.get("screenshot_path", "")
                    text_path = entry.get("text_path", "")
                    line = (
                        f"- {entry.get('captured_at')} "
                        f"[{self.store_id}]({html_path}) "
                        f"(screenshot: {screenshot_path}) "
                        f"(text: {text_path}) "
                        f"{entry.get('reason')} {entry.get('url')}\n"
                    )
                    with index_md.open("a", encoding="utf-8") as handle:
                        handle.write(line)
                except OSError as exc:
                    self.logger.warning("Failed to append failure index md: %s", exc)
        except Exception as exc:
            self.logger.warning("Failed to append failure index: %s", exc)

    @staticmethod
    def _safe_rel_path(path: Path, base: Path) -> str:
        try:
            return str(path.relative_to(base))
        except ValueError:
            return str(path)

    @staticmethod
    def _extract_text_from_html(raw_html: str) -> str:
        class _TextExtractor(HTMLParser):
            def __init__(self) -> None:
                super().__init__()
                self._chunks: list[str] = []

            def handle_data(self, data: str) -> None:
                text = data.strip()
                if text:
                    self._chunks.append(text)

            def get_text(self) -> str:
                return "\n".join(self._chunks)

        parser = _TextExtractor()
        parser.feed(raw_html)
        return parser.get_text()
