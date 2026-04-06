from __future__ import annotations

import gzip
import logging
import re
from dataclasses import dataclass, field
from typing import Final
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx


_BASE_URL: Final[str] = "https://www.target.com"
_PDP_SITEMAP_INDEX_URL: Final[str] = "https://www.target.com/sitemap_pdp-index.xml.gz"
_HOST: Final[str] = urlsplit(_BASE_URL).netloc.lower()
_SITEMAP_LOC_RE: Final[re.Pattern[str]] = re.compile(r"<loc>(?P<url>https://www\.target\.com/[^<]+)</loc>")
_TCIN_PATH_RE: Final[re.Pattern[str]] = re.compile(r"/A-(?P<tcin>\d{6,})/?$", re.IGNORECASE)
_MAX_LINKS: Final[int] = 300
_MAX_SITEMAPS: Final[int] = 4


@dataclass(slots=True)
class TargetDiscovery:
    logger: logging.Logger = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.logger = logging.getLogger("dealwatch.stores.target.discovery")

    async def discover_deals(self) -> list[str]:
        links: list[str] = []
        seen: set[str] = set()

        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            index_response = await client.get(_PDP_SITEMAP_INDEX_URL)
            index_response.raise_for_status()
            sitemap_urls = self._extract_locations(index_response)

            for sitemap_url in sitemap_urls[:_MAX_SITEMAPS]:
                response = await client.get(sitemap_url)
                response.raise_for_status()
                for href in self._extract_locations(response):
                    normalized = self._normalize_product_url(href)
                    if normalized is None or normalized in seen:
                        continue
                    seen.add(normalized)
                    links.append(normalized)
                    if len(links) >= _MAX_LINKS:
                        return links

        return links

    def _extract_locations(self, response: httpx.Response) -> list[str]:
        xml = self._decode_response_text(response)
        return [match.group("url") for match in _SITEMAP_LOC_RE.finditer(xml)]

    @staticmethod
    def _decode_response_text(response: httpx.Response) -> str:
        content = response.content
        if content.startswith(b"\x1f\x8b"):
            try:
                return gzip.decompress(content).decode("utf-8")
            except OSError:
                pass
        return response.text

    @staticmethod
    def _normalize_product_url(href: str) -> str | None:
        candidate = href.strip()
        if not candidate:
            return None

        if not candidate.startswith("http"):
            candidate = urljoin(_BASE_URL, candidate)

        parsed = urlsplit(candidate)
        if parsed.netloc.lower() != _HOST:
            return None

        tcin_match = _TCIN_PATH_RE.search(parsed.path)
        if tcin_match is None or not parsed.path.startswith("/p/"):
            return None

        stable_path = f"/p/-/A-{tcin_match.group('tcin')}"
        return urlunsplit(("https", _HOST, stable_path, "", ""))
