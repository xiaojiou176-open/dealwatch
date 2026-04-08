from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Final, Optional

from playwright.async_api import Page

from dealwatch.core.models import Offer, PriceContext, SkipReason
from dealwatch.stores.base_adapter import SkipParse


#########################################################
# Constants
#########################################################
_PRICE_RE: Final[re.Pattern[str]] = re.compile(r"[-+]?\d+(?:\.\d+)?")
_PRODUCT_KEY_RE: Final[re.Pattern[str]] = re.compile(r"/zh/product/([^/?#]+)")
_HTML_TITLE_RE: Final[re.Pattern[str]] = re.compile(
    r"<title[^>]*>(?P<value>.*?)</title>",
    re.IGNORECASE | re.DOTALL,
)
_OG_TITLE_RE: Final[re.Pattern[str]] = re.compile(
    r'<meta[^>]+property="og:title"[^>]+content="(?P<value>[^"]+)"',
    re.IGNORECASE,
)
_UNIT_RE: Final[re.Pattern[str]] = re.compile(
    r"(?P<qty>\d+(?:\.\d+)?)\s*(?P<unit>lb|lbs|oz|g|kg|ml|l|ct|count|pcs|pc|pack|pk|\u4e2a)",
    re.IGNORECASE,
)
_EMBEDDED_PRODUCT_ID_RE: Final[re.Pattern[str]] = re.compile(r'\\"id\\":(?P<value>\d+)')
_EMBEDDED_PRODUCT_NAME_RE: Final[re.Pattern[str]] = re.compile(
    r'\\"name\\":\\"(?P<value>(?:[^"\\]|\\\\.)+)'
)
_EMBEDDED_PRODUCT_PRICE_RE: Final[re.Pattern[str]] = re.compile(
    r'\\"price\\":(?P<value>\d+(?:\.\d+)?)'
)
_EMBEDDED_PRODUCT_BASE_PRICE_RE: Final[re.Pattern[str]] = re.compile(
    r'\\"base_price\\":(?P<value>\d+(?:\.\d+)?)'
)
_EMBEDDED_PRODUCT_UNIT_RE: Final[re.Pattern[str]] = re.compile(
    r'\\"unit_info\\":\\"(?P<value>(?:[^"\\]|\\\\.)+)'
)
_EMBEDDED_PRODUCT_AVAILABLE_RE: Final[re.Pattern[str]] = re.compile(
    r'\\"sold_status_available\\":(?P<value>true|false)'
)

_OUT_OF_STOCK_MARKERS: Final[tuple[str, ...]] = (
    "out of stock",
    "sold out",
    "\u65e0\u8d27",
)


#########################################################
# Parser
#########################################################
@dataclass(slots=True)
class WeeeParser:
    store_id: str
    context: PriceContext
    logger: logging.Logger = field(init=False, repr=False)
    last_debug: dict[str, str] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        self.logger = logging.getLogger("dealwatch.stores.weee.parser")

    async def parse(self, page: Page) -> Optional[Offer]:
        url = page.url
        self.last_debug = {"url": url}
        html_text = await page.content()
        product_payload = await self._extract_product_payload(page, url, html_text)

        title: str | None = None
        price: float | None = None
        base_price: float | None = None
        not_available = False
        unit_raw: str | None = None

        if product_payload is not None:
            title, title_key = self._extract_title(product_payload)
            price, base_price, price_key, base_key = self._extract_prices(product_payload)
            not_available = self._extract_not_available(product_payload)
            unit_raw = self._extract_unit_hint(product_payload)

            if title_key:
                self.last_debug["title_source"] = f"json:{title_key}"
            if price_key:
                self.last_debug["price_source"] = f"json:{price_key}"
            if base_key:
                self.last_debug["original_price_source"] = f"json:{base_key}"

        if title is None:
            title = await self._extract_title_from_dom(page)
            if title:
                self.last_debug["title_source"] = "dom:h1"
        if title is None:
            title = self._extract_title_from_html(html_text)

        if price is None:
            price, base_price = await self._extract_prices_from_dom(page)
            if price is not None:
                self.last_debug["price_source"] = "dom:[class*='price_current']"
            else:
                self.last_debug["price_missing"] = (
                    "missing json:price/current_price/... and dom:[class*='price_current']"
                )
            if base_price is not None:
                self.last_debug["original_price_source"] = "dom:[class*='price_original']"

        if not_available:
            self.last_debug["availability"] = "out_of_stock"
            raise SkipParse(SkipReason.OUT_OF_STOCK)

        if price is None or title is None:
            if title is None:
                self.last_debug["title_missing"] = "missing json:title/name and dom:h1"
            return None

        product_key = self._extract_product_key(product_payload, url)
        if product_key is None:
            return None

        unit_price_info = self._build_unit_price_info(
            unit_raw or title
        )

        return Offer(
            store_id=self.store_id,
            product_key=product_key,
            title=title,
            url=url,
            price=price,
            original_price=base_price,
            fetch_at=datetime.now(timezone.utc),
            context=self.context,
            unit_price_info=unit_price_info,
        )

    #########################################################
    # JSON Extraction
    #########################################################
    async def _extract_product_payload(
        self,
        page: Page,
        url: str,
        html_text: str,
    ) -> dict | None:
        product = await self._extract_next_data_payload(page, url)
        if product is not None:
            return product

        json_ld_product = await self._extract_json_ld_payload(page, url)
        if json_ld_product is not None:
            self.last_debug["json_status"] = "jsonld.product"
            return json_ld_product

        embedded_product = self._extract_embedded_product_payload(html_text)
        if embedded_product is not None:
            self.last_debug["json_status"] = "embedded.product"
            return embedded_product

        return None

    async def _extract_next_data_payload(
        self,
        page: Page,
        url: str,
    ) -> dict | None:
        locator = page.locator("script#__NEXT_DATA__")
        if await locator.count() == 0:
            self.last_debug["json_status"] = "missing __NEXT_DATA__"
            return None

        raw_json = await locator.first.text_content()
        if not raw_json:
            self.last_debug["json_status"] = "empty __NEXT_DATA__"
            return None

        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            self.logger.exception("NEXT_DATA JSON parse failed for %s: %s", url, exc)
            self.last_debug["json_status"] = "invalid __NEXT_DATA__ json"
            return None

        page_props = (
            data.get("props", {})
            .get("pageProps", {})
        )

        product = page_props.get("product")
        if isinstance(product, dict):
            self.last_debug["json_status"] = "props.pageProps.product"
            return product

        fallback = page_props.get("fallback")
        if isinstance(fallback, dict):
            for value in fallback.values():
                if isinstance(value, dict):
                    if isinstance(value.get("product"), dict):
                        self.last_debug["json_status"] = "props.pageProps.fallback.product"
                        return value["product"]
                    if self._looks_like_product(value):
                        self.last_debug["json_status"] = "props.pageProps.fallback.value"
                        return value
                    nested = value.get("data")
                    if isinstance(nested, dict) and self._looks_like_product(nested):
                        self.last_debug["json_status"] = "props.pageProps.fallback.value.data"
                        return nested

        self.last_debug["json_status"] = "deep_search"
        return self._search_for_product(data)

    async def _extract_json_ld_payload(
        self,
        page: Page,
        url: str,
    ) -> dict | None:
        locator = page.locator('script[type="application/ld+json"]')
        if await locator.count() == 0:
            self.last_debug["json_ld_status"] = "missing jsonld"
            return None

        raw_list = await locator.all_text_contents()
        if not raw_list:
            self.last_debug["json_ld_status"] = "empty jsonld"
            return None

        for index, raw_json in enumerate(raw_list):
            if not raw_json:
                continue
            try:
                data = json.loads(raw_json)
            except json.JSONDecodeError as exc:
                cleaned = self._sanitize_json_text(raw_json)
                if cleaned == raw_json:
                    self.logger.exception("JSON-LD parse failed for %s: %s", url, exc)
                    continue
                try:
                    data = json.loads(cleaned)
                except json.JSONDecodeError as clean_exc:
                    self.logger.exception("JSON-LD parse failed for %s: %s", url, clean_exc)
                    continue

            product = self._find_json_ld_product(data)
            if product is not None:
                self.last_debug["json_ld_status"] = f"jsonld:{index}"
                return product

        self.last_debug["json_ld_status"] = "jsonld no product"
        return None

    def _search_for_product(self, data: object) -> dict | None:
        stack = [data]
        while stack:
            current = stack.pop()
            if isinstance(current, dict):
                if self._looks_like_product(current):
                    return current
                stack.extend(current.values())
            elif isinstance(current, list):
                stack.extend(current)
        return None

    @staticmethod
    def _looks_like_product(candidate: dict) -> bool:
        keys = {key.lower() for key in candidate.keys()}
        return "price" in keys and ("title" in keys or "name" in keys)

    def _find_json_ld_product(self, data: object) -> dict | None:
        stack = [data]
        while stack:
            current = stack.pop()
            if isinstance(current, dict):
                if self._is_json_ld_product(current):
                    normalized = self._normalize_json_ld_product(current)
                    if normalized:
                        return normalized
                stack.extend(current.values())
            elif isinstance(current, list):
                stack.extend(current)
        return None

    @staticmethod
    def _is_json_ld_product(candidate: dict) -> bool:
        raw_type = candidate.get("@type") or candidate.get("type")
        if raw_type is None:
            return False
        if isinstance(raw_type, list):
            types = [str(item).lower() for item in raw_type]
        else:
            types = [str(raw_type).lower()]
        return any("product" in item for item in types)

    def _normalize_json_ld_product(self, candidate: dict) -> dict | None:
        normalized: dict[str, object] = {}

        title = candidate.get("name") or candidate.get("title")
        if title:
            normalized["title"] = str(title).strip()

        sku = (
            candidate.get("sku")
            or candidate.get("mpn")
            or candidate.get("productID")
            or candidate.get("productId")
            or candidate.get("product_id")
        )
        if sku:
            normalized["sku"] = str(sku).strip()

        offers = candidate.get("offers")
        offer = self._extract_json_ld_offer(offers)
        if offer is not None:
            price = (
                offer.get("price")
                or offer.get("lowPrice")
                or offer.get("highPrice")
            )
            if price is None:
                price_spec = offer.get("priceSpecification")
                if isinstance(price_spec, dict):
                    price = price_spec.get("price")
            if price is not None:
                normalized["price"] = price

            availability = offer.get("availability")
            if availability:
                normalized["availability"] = availability

        return normalized or None

    @staticmethod
    def _extract_json_ld_offer(offers: object | None) -> dict | None:
        if isinstance(offers, dict):
            return offers
        if isinstance(offers, list):
            for item in offers:
                if isinstance(item, dict):
                    if any(key in item for key in ("price", "lowPrice", "highPrice", "priceSpecification")):
                        return item
            for item in offers:
                if isinstance(item, dict):
                    return item
        return None

    #########################################################
    # Field Extraction
    #########################################################
    @staticmethod
    def _extract_title(product: dict) -> tuple[str | None, str | None]:
        for key in ("title", "name", "product_name", "productName"):
            value = product.get(key)
            if value:
                return str(value).strip(), key
        return None, None

    async def _extract_title_from_dom(self, page: Page) -> str | None:
        locator = page.locator("h1")
        if await locator.count() == 0:
            return None
        text = await locator.first.text_content()
        if not text:
            return None
        return text.strip()

    def _extract_title_from_html(self, html_text: str) -> str | None:
        for pattern, source in (
            (_OG_TITLE_RE, "html:meta:og:title"),
            (_HTML_TITLE_RE, "html:title"),
        ):
            match = pattern.search(html_text)
            if match is None:
                continue
            text = self._clean_html_text(match.group("value"))
            if not text:
                continue
            title = re.sub(r"^\s*[^|]+?\s+\|\s+", "", text).strip()
            title = re.sub(r"\s*-\s*Weee!\s*$", "", title).strip()
            if title:
                self.last_debug["title_source"] = source
                return title
        return None

    def _extract_prices(
        self,
        product: dict,
    ) -> tuple[float | None, float | None, str | None, str | None]:
        price_raw, price_key = self._get_first_value_with_key(
            product,
            ["price", "current_price", "currentPrice", "sale_price", "salePrice"],
        )
        base_raw, base_key = self._get_first_value_with_key(
            product,
            [
                "base_price",
                "basePrice",
                "original_price",
                "originalPrice",
                "msrp",
            ],
        )

        pricing = product.get("pricing")
        if isinstance(pricing, dict):
            if price_raw is None:
                price_raw, price_key = self._get_first_value_with_key(
                    pricing,
                    ["price", "current_price", "currentPrice", "sale_price"],
                )
                if price_key:
                    price_key = f"pricing.{price_key}"
            if base_raw is None:
                base_raw, base_key = self._get_first_value_with_key(
                    pricing,
                    ["base_price", "basePrice", "original_price", "originalPrice"],
                )
                if base_key:
                    base_key = f"pricing.{base_key}"

        price = self._parse_price(price_raw)
        base_price = self._parse_price(base_raw)

        return price, base_price, price_key, base_key

    def _extract_embedded_product_payload(self, html_text: str) -> dict | None:
        anchor = html_text.find('\\"product\\":{')
        if anchor < 0:
            return None

        window = html_text[anchor : anchor + 12000]
        product: dict[str, object] = {}

        product_id = self._match_embedded_text(_EMBEDDED_PRODUCT_ID_RE, window)
        if product_id:
            product["id"] = product_id

        name = self._match_embedded_text(_EMBEDDED_PRODUCT_NAME_RE, window)
        if name:
            product["name"] = name

        price = self._match_embedded_number(_EMBEDDED_PRODUCT_PRICE_RE, window)
        if price is not None:
            product["price"] = price

        base_price = self._match_embedded_number(_EMBEDDED_PRODUCT_BASE_PRICE_RE, window)
        if base_price is not None:
            product["base_price"] = base_price

        unit_info = self._match_embedded_text(_EMBEDDED_PRODUCT_UNIT_RE, window)
        if unit_info:
            product["unit_info"] = unit_info

        available = self._match_embedded_text(_EMBEDDED_PRODUCT_AVAILABLE_RE, window)
        if available:
            product["sold_status_available"] = available == "true"

        return product or None

    async def _extract_prices_from_dom(
        self,
        page: Page,
    ) -> tuple[float | None, float | None]:
        current = await self._text_by_selector(page, '[class*="price_current"]')
        original = await self._text_by_selector(page, '[class*="price_original"]')
        return self._parse_price(current), self._parse_price(original)

    @staticmethod
    def _extract_not_available(product: dict) -> bool:
        for key in (
            "not_available",
            "notAvailable",
            "out_of_stock",
            "outOfStock",
            "is_out_of_stock",
            "isOutOfStock",
        ):
            if key in product:
                return WeeeParser._as_bool(product.get(key))

        for key in ("available", "is_available", "isAvailable"):
            if key in product:
                return not WeeeParser._as_bool(product.get(key))

        availability = product.get("availability")
        if availability:
            return WeeeParser._as_bool(availability)

        return False

    @staticmethod
    def _extract_unit_hint(product: dict) -> str | None:
        for key in ("unit", "size", "weight", "spec", "specification"):
            value = product.get(key)
            if value:
                return str(value).strip()
        return None

    @staticmethod
    def _extract_product_key(product: dict | None, url: str) -> str | None:
        if isinstance(product, dict):
            for key in (
                "product_key",
                "productKey",
                "product_id",
                "productId",
                "id",
                "sku",
            ):
                value = product.get(key)
                if value:
                    return str(value).strip()

        match = _PRODUCT_KEY_RE.search(url)
        if match:
            return match.group(1)

        return None

    #########################################################
    # Unit Helpers
    #########################################################
    @staticmethod
    def _build_unit_price_info(text: str | None) -> dict[str, str | float]:
        if not text:
            return {}

        match = _UNIT_RE.search(text)
        if not match:
            return {"raw": text}

        quantity = float(match.group("qty"))
        unit = match.group("unit").lower()
        return {
            "raw": text,
            "quantity": quantity,
            "unit": unit,
        }

    @staticmethod
    def _match_embedded_text(pattern: re.Pattern[str], text: str) -> str | None:
        match = pattern.search(text)
        if match is None:
            return None
        value = match.group("value")
        try:
            return json.loads(f'"{value}"')
        except json.JSONDecodeError:
            return value.replace('\\"', '"').strip()

    @staticmethod
    def _match_embedded_number(pattern: re.Pattern[str], text: str) -> float | None:
        match = pattern.search(text)
        if match is None:
            return None
        return WeeeParser._parse_price(match.group("value"))

    @staticmethod
    def _clean_html_text(value: str | None) -> str | None:
        if value is None:
            return None
        text = re.sub(r"\s+", " ", value).strip()
        return text or None

    #########################################################
    # Generic Helpers
    #########################################################
    @staticmethod
    def _get_first_value_with_key(
        data: dict,
        keys: list[str],
    ) -> tuple[object | None, str | None]:
        for key in keys:
            if key in data:
                return data.get(key), key
        return None, None

    @staticmethod
    def _parse_price(value: object | None) -> float | None:
        if value is None:
            return None

        if isinstance(value, (int, float)):
            return round(float(value), 2)

        text = str(value)
        match = _PRICE_RE.search(text.replace(",", ""))
        if not match:
            return None

        return round(float(match.group(0)), 2)

    @staticmethod
    def _sanitize_json_text(text: str) -> str:
        return re.sub(r"[\x00-\x1f\x7f]", "", text)

    @staticmethod
    async def _text_by_selector(page: Page, selector: str) -> str | None:
        locator = page.locator(selector)
        if await locator.count() == 0:
            return None
        text = await locator.first.text_content()
        if not text:
            return None
        return text.strip()

    @staticmethod
    def _as_bool(value: object | None) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        text = str(value).strip().lower()
        if "outofstock" in text or "out of stock" in text:
            return True
        if "instock" in text or "in stock" in text:
            return False
        if text in ("true", "1", "yes"):
            return True
        if text in ("false", "0", "no"):
            return False
        return any(marker in text for marker in _OUT_OF_STOCK_MARKERS)
