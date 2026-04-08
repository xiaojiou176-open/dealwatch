from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html import unescape
from typing import Any, Final
from urllib.parse import urlsplit

from playwright.async_api import Page

from dealwatch.core.models import Offer, PriceContext, SkipReason
from dealwatch.stores.base_adapter import SkipParse


_PRODUCT_ID_RE: Final[re.Pattern[str]] = re.compile(
    r"/shop/product-details\.(?P<product_id>\d+)\.html/?$",
    re.IGNORECASE,
)
_JSON_LD_SCRIPT_RE: Final[re.Pattern[str]] = re.compile(
    r"""<script[^>]+\btype\s*=\s*['"]application/ld\+json['"][^>]*>(?P<payload>.*?)</script>""",
    re.IGNORECASE | re.DOTALL,
)
_UNIT_RE: Final[re.Pattern[str]] = re.compile(
    r"(?P<qty>\d+(?:\.\d+)?)\s*(?P<unit>lb|lbs|oz|fl\.?\s*oz|foz|g|kg|ml|l|ct|count|pk|pack)",
    re.IGNORECASE,
)
_INCAPSULA_BLOCK_MARKERS: Final[tuple[str, ...]] = (
    "_incapsula_resource",
    "incapsula incident id",
    "request unsuccessful",
)


@dataclass(slots=True)
class SafewayParser:
    store_id: str
    context: PriceContext
    logger: logging.Logger = field(init=False, repr=False)
    last_debug: dict[str, str] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        self.logger = logging.getLogger("dealwatch.stores.safeway.parser")

    async def parse(self, page: Page) -> Offer | None:
        self.last_debug = {"url": page.url}
        html_text = await page.content()
        block_reason = self._detect_blocked_page(html_text)
        if block_reason is not None:
            self.last_debug["page_blocked"] = block_reason
            self.last_debug["json_ld"] = "skipped: block page"
            return None

        product = self._extract_product_json_ld(html_text)
        if product is None:
            self.last_debug["json_ld"] = "missing product payload"
            return None

        if self._is_out_of_stock(product.get("offers")):
            self.last_debug["availability"] = "out_of_stock"
            raise SkipParse(SkipReason.OUT_OF_STOCK)

        title = self._clean_text(product.get("name"))
        price = self._extract_price(product.get("offers"))
        if not title:
            self.last_debug["title_missing"] = "missing json_ld product name"
            return None
        if price is None:
            self.last_debug["price_missing"] = "missing json_ld offer price"
            return None

        product_key = self._extract_product_key(page.url, product)
        if product_key is None:
            self.last_debug["product_key"] = "missing"
            return None

        return Offer(
            store_id=self.store_id,
            product_key=product_key,
            title=title,
            url=page.url,
            price=price,
            original_price=None,
            fetch_at=datetime.now(timezone.utc),
            context=self.context,
            unit_price_info=self._build_unit_price_info(title=title, product=product),
        )

    def _extract_product_json_ld(self, html_text: str) -> dict[str, Any] | None:
        for match in _JSON_LD_SCRIPT_RE.finditer(html_text):
            raw_payload = unescape(match.group("payload").strip())
            if not raw_payload:
                continue
            try:
                data = json.loads(raw_payload)
            except json.JSONDecodeError:
                continue
            product = self._find_product_payload(data)
            if product is not None:
                self.last_debug["json_ld"] = "product"
                return product
        return None

    def _find_product_payload(self, candidate: Any) -> dict[str, Any] | None:
        stack = [candidate]
        while stack:
            current = stack.pop()
            if isinstance(current, dict):
                if str(current.get("@type") or "").lower() == "product":
                    return current
                stack.extend(current.values())
            elif isinstance(current, list):
                stack.extend(current)
        return None

    @staticmethod
    def _detect_blocked_page(html_text: str) -> str | None:
        lowered = html_text.lower()
        if all(marker in lowered for marker in _INCAPSULA_BLOCK_MARKERS):
            return "incapsula"
        return None

    @staticmethod
    def _iter_offer_payloads(offers: Any) -> list[dict[str, Any]]:
        if isinstance(offers, dict):
            return [offers]
        if isinstance(offers, list):
            return [item for item in offers if isinstance(item, dict)]
        return []

    @classmethod
    def _extract_price(cls, offers: Any) -> float | None:
        for offer in cls._iter_offer_payloads(offers):
            raw = offer.get("price")
            if raw in (None, ""):
                continue
            try:
                return round(float(raw), 2)
            except (TypeError, ValueError):
                continue
        return None

    @classmethod
    def _is_out_of_stock(cls, offers: Any) -> bool:
        payloads = cls._iter_offer_payloads(offers)
        if not payloads:
            return False

        saw_availability = False
        for offer in payloads:
            availability = str(offer.get("availability") or "").lower()
            if not availability:
                return False
            saw_availability = True
            if "outofstock" not in availability and not availability.endswith("/outofstock"):
                return False
        return saw_availability

    @staticmethod
    def _extract_product_key(url: str, product: dict[str, Any]) -> str | None:
        gtin = str(product.get("gtin13") or "").strip()
        if gtin:
            return gtin
        match = _PRODUCT_ID_RE.search(urlsplit(url).path)
        if match is None:
            return None
        return match.group("product_id")

    def _build_unit_price_info(self, *, title: str, product: dict[str, Any]) -> dict[str, str | float]:
        info: dict[str, str | float] = {"raw": title}
        brand_name = self._extract_brand_name(product.get("brand"))
        if brand_name and brand_name.lower() not in title.lower():
            info["brand"] = brand_name

        unit_match = _UNIT_RE.search(title)
        if unit_match is not None:
            info["quantity"] = float(unit_match.group("qty"))
            info["unit"] = re.sub(r"\s+", " ", unit_match.group("unit").lower()).replace(".", "")

        return info

    @staticmethod
    def _extract_brand_name(brand: Any) -> str | None:
        if isinstance(brand, dict):
            return SafewayParser._clean_text(brand.get("name"))
        return SafewayParser._clean_text(brand)

    @staticmethod
    def _clean_text(value: Any) -> str | None:
        if value in (None, ""):
            return None
        text = re.sub(r"\s+", " ", unescape(str(value))).strip()
        return text or None
