from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Final
from urllib.parse import urlsplit, urlunsplit

import httpx


_BASE_URL: Final[str] = "https://www.99ranch.com"
_SITEMAP_URLS: Final[tuple[str, ...]] = (
    "https://www.99ranch.com/sitemap/product-0.xml",
    "https://www.99ranch.com/sitemap/product-1.xml",
)
_PRODUCT_PATH_RE: Final[re.Pattern[str]] = re.compile(
    r"^/product-details/\d+/\d+/[A-Za-z0-9-]+/?$"
)
_LOC_RE: Final[re.Pattern[str]] = re.compile(r"<loc>(?P<url>https://www\.99ranch\.com/[^<]+)</loc>")
_MAX_LINKS: Final[int] = 300


@dataclass(slots=True)
class Ranch99Discovery:
    logger: logging.Logger = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.logger = logging.getLogger("dealwatch.stores.ranch99.discovery")

    async def discover_deals(self) -> list[str]:
        links: list[str] = []
        seen: set[str] = set()
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            for sitemap_url in _SITEMAP_URLS:
                response = await client.get(sitemap_url)
                response.raise_for_status()
                for match in _LOC_RE.finditer(response.text):
                    normalized = self._normalize_product_url(match.group("url"))
                    if normalized is None or normalized in seen:
                        continue
                    seen.add(normalized)
                    links.append(normalized)
                    if len(links) >= _MAX_LINKS:
                        return links
        return links

    @staticmethod
    def _normalize_product_url(href: str) -> str | None:
        parsed = urlsplit(href.strip())
        if parsed.netloc.lower() != urlsplit(_BASE_URL).netloc.lower():
            return None
        if not _PRODUCT_PATH_RE.match(parsed.path):
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
