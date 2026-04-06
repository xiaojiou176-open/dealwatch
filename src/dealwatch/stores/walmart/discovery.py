from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Final
from urllib.parse import urlsplit, urlunsplit


_BASE_URL: Final[str] = "https://www.walmart.com"
_HOST: Final[str] = urlsplit(_BASE_URL).netloc.lower()
_PRODUCT_PATH_RE: Final[re.Pattern[str]] = re.compile(
    r"^/ip(?:/[^/?#]+)?/(?P<item_id>\d+)/?$",
    re.IGNORECASE,
)


@dataclass(slots=True)
class WalmartDiscovery:
    logger: logging.Logger = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.logger = logging.getLogger("dealwatch.stores.walmart.discovery")

    async def discover_deals(self) -> list[str]:
        self.logger.info("Walmart discovery is intentionally deferred in C1; manual product-detail intake is the supported path.")
        return []

    @staticmethod
    def _normalize_product_url(href: str) -> str | None:
        parsed = urlsplit(href.strip())
        if parsed.netloc.lower() != _HOST:
            return None
        match = _PRODUCT_PATH_RE.match(parsed.path)
        if match is None:
            return None
        stable_path = f"/ip/{match.group('item_id')}"
        return urlunsplit((parsed.scheme or "https", _HOST, stable_path, "", ""))
