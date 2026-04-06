from __future__ import annotations

import asyncio
import logging
import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, Iterable, List
from urllib.parse import urljoin, urlsplit, urlunsplit

from dealwatch.infra.playwright_client import PlaywrightClient


#########################################################
# Constants
#########################################################
_BASE_URL: Final[str] = "https://www.sayweee.com"
_SALE_URL: Final[str] = "https://www.sayweee.com/zh/category/sale"

_MAX_LINKS: Final[int] = 300
_STAGNATION_LIMIT: Final[int] = 3

_SCROLL_SLEEP_MIN: Final[float] = 1.0
_SCROLL_SLEEP_MAX: Final[float] = 2.0

_NO_MORE_MARKERS: Final[tuple[str, ...]] = (
    "\u6ca1\u6709\u66f4\u591a\u5546\u54c1",
    "No more",
)

_PRODUCT_PATH_RE: Final[re.Pattern[str]] = re.compile(r"^/zh/product/")

_STEALTH_SCRIPT: Final[str] = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
"""


#########################################################
# Discovery
#########################################################
@dataclass(slots=True)
class WeeeDiscovery:
    client: PlaywrightClient
    storage_state_path: Path
    logger: logging.Logger = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.storage_state_path, Path):
            self.storage_state_path = Path(self.storage_state_path)
        self.logger = logging.getLogger("dealwatch.stores.weee.discovery")

    async def discover_deals(self) -> List[str]:
        if not self.storage_state_path.exists():
            self.logger.warning(
                "storage_state not found: %s", self.storage_state_path
            )

        context = await self.client.get_context()
        page = await context.new_page()

        try:
            await page.add_init_script(_STEALTH_SCRIPT)
            await page.goto(_SALE_URL, wait_until="networkidle", timeout=30_000)

            seen_links: set[str] = set()
            stagnant_rounds = 0

            while True:
                current_links = await self._extract_links(page)
                new_links = current_links - seen_links
                if new_links:
                    seen_links.update(new_links)
                    stagnant_rounds = 0
                else:
                    stagnant_rounds += 1

                if await self._has_no_more(page):
                    break

                if len(seen_links) >= _MAX_LINKS:
                    break

                if stagnant_rounds >= _STAGNATION_LIMIT:
                    break

                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(
                    random.uniform(_SCROLL_SLEEP_MIN, _SCROLL_SLEEP_MAX)
                )

            return sorted(seen_links)
        except Exception as exc:
            self.logger.exception("Discovery failed: %s", exc)
            raise
        finally:
            await page.close()

    #########################################################
    # Internal
    #########################################################
    async def _extract_links(self, page) -> set[str]:
        try:
            hrefs: Iterable[str] = await page.eval_on_selector_all(
                "a[href]",
                "els => els.map(el => el.getAttribute('href')).filter(Boolean)",
            )
        except Exception as exc:
            self.logger.exception("Failed to extract links: %s", exc)
            return set()

        results: set[str] = set()
        for href in hrefs:
            normalized = self._normalize_product_url(href)
            if normalized is not None:
                results.add(normalized)

        return results

    @staticmethod
    def _normalize_product_url(href: str) -> str | None:
        if href.startswith("http"):
            candidate = href
        else:
            candidate = urljoin(_BASE_URL, href)

        parsed = urlsplit(candidate)
        if parsed.netloc and parsed.netloc != urlsplit(_BASE_URL).netloc:
            return None

        if not _PRODUCT_PATH_RE.match(parsed.path):
            return None

        cleaned = urlunsplit((parsed.scheme or "https", parsed.netloc, parsed.path, "", ""))
        return cleaned

    @staticmethod
    async def _has_no_more(page) -> bool:
        for marker in _NO_MORE_MARKERS:
            locator = page.locator(f"text={marker}")
            try:
                if await locator.count() > 0:
                    return True
            except Exception:
                return False
        return False
