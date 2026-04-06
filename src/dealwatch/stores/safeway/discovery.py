from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Final
from urllib.parse import urlsplit, urlunsplit


_BASE_URL: Final[str] = "https://www.safeway.com"
_HOST: Final[str] = urlsplit(_BASE_URL).netloc.lower()
_PRODUCT_PATH_RE: Final[re.Pattern[str]] = re.compile(
    r"^/shop/product-details\.(?P<product_id>\d+)\.html/?$",
    re.IGNORECASE,
)


@dataclass(slots=True)
class SafewayDiscovery:
    logger: logging.Logger = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.logger = logging.getLogger("dealwatch.stores.safeway.discovery")

    async def discover_deals(self) -> list[str]:
        self.logger.info("Safeway discovery is intentionally deferred in C1; compare-first intake is the supported path.")
        return []

    @staticmethod
    def _normalize_product_url(href: str) -> str | None:
        parsed = urlsplit(href.strip())
        if parsed.netloc.lower() != _HOST:
            return None
        match = _PRODUCT_PATH_RE.match(parsed.path)
        if match is None:
            return None
        stable_path = f"/shop/product-details.{match.group('product_id')}.html"
        return urlunsplit((parsed.scheme or "https", _HOST, stable_path, "", ""))
