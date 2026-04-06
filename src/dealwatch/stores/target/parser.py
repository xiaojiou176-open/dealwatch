from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import html
import logging
import re
from typing import Final

from playwright.async_api import Page

from dealwatch.core.models import Offer, PriceContext, SkipReason
from dealwatch.stores.base_adapter import SkipParse


_TCIN_IN_URL_RE: Final[re.Pattern[str]] = re.compile(r"/A-(?P<tcin>\d{6,})/?$", re.IGNORECASE)
_ESCAPED_TCIN_RE_TEMPLATE: Final[str] = r'(?:\\)?"tcin(?:\\)?":(?:\\)?"?{tcin}"?'
_JSON_QUOTE_RE: Final[str] = r'(?:\\"|")?'
_PRICE_NUMBER_RE: Final[re.Pattern[str]] = re.compile(r"\d+(?:\.\d+)?")
_CURRENT_RETAIL_RE: Final[re.Pattern[str]] = re.compile(
    _JSON_QUOTE_RE + r"current_retail" + _JSON_QUOTE_RE + r":(?P<value>\d+(?:\.\d+)?)"
)
_FORMATTED_CURRENT_PRICE_RE: Final[re.Pattern[str]] = re.compile(
    _JSON_QUOTE_RE + r"formatted_current_price" + _JSON_QUOTE_RE + r':(?:\\"|")(?P<value>[^"\\<]+)'
)
_ORIGINAL_PRICE_RE: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(_JSON_QUOTE_RE + r"reg_retail" + _JSON_QUOTE_RE + r":(?P<value>\d+(?:\.\d+)?)"),
    re.compile(_JSON_QUOTE_RE + r"regular_retail" + _JSON_QUOTE_RE + r":(?P<value>\d+(?:\.\d+)?)"),
    re.compile(_JSON_QUOTE_RE + r"retail_price" + _JSON_QUOTE_RE + r":(?P<value>\d+(?:\.\d+)?)"),
)
_BARCODE_RE: Final[re.Pattern[str]] = re.compile(
    _JSON_QUOTE_RE + r"primary_barcode" + _JSON_QUOTE_RE + r':(?:\\"|")(?P<value>\d{12,14})'
)
_OG_TITLE_RE: Final[re.Pattern[str]] = re.compile(
    r'<meta[^>]+property="og:title"[^>]+content="(?P<value>[^"]+)"',
    re.IGNORECASE,
)
_TITLE_RE: Final[re.Pattern[str]] = re.compile(
    r"<title[^>]*>(?P<value>.*?)</title>",
    re.IGNORECASE | re.DOTALL,
)
_H1_RE: Final[re.Pattern[str]] = re.compile(
    r'<h1[^>]*data-test="product-title"[^>]*>(?P<value>.*?)</h1>',
    re.IGNORECASE | re.DOTALL,
)
_UNIT_RE: Final[re.Pattern[str]] = re.compile(
    r"(?P<qty>\d+(?:\.\d+)?)\s*(?P<unit>lb|lbs|oz|fl oz|foz|g|kg|ml|l|ct|count|pk|pack)",
    re.IGNORECASE,
)
_OUT_OF_STOCK_MARKERS: Final[tuple[str, ...]] = (
    "out of stock",
    "sold out",
    "unavailable",
    '"availability_status":"out_of_stock"',
    '\\"availability_status\\":\\"out_of_stock\\"',
    '"is_out_of_stock":true',
    '\\"is_out_of_stock\\":true',
)


@dataclass(slots=True)
class TargetParser:
    store_id: str
    context: PriceContext
    logger: logging.Logger = field(init=False, repr=False)
    last_debug: dict[str, str] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        self.logger = logging.getLogger("dealwatch.stores.target.parser")

    async def parse(self, page: Page) -> Offer | None:
        self.last_debug = {"url": page.url}
        html_text = await page.content()
        product_key = self._extract_product_key(page.url, html_text)
        if product_key is None:
            self.last_debug["product_key"] = "missing"
            return None

        product_window = self._extract_product_window(html_text, product_key)
        if self._is_out_of_stock(product_window):
            self.last_debug["availability"] = "out_of_stock"
            raise SkipParse(SkipReason.OUT_OF_STOCK)

        title = await self._extract_title(page, html_text)
        price = self._extract_price(product_window)
        original_price = self._extract_original_price(product_window, price)

        if title is None:
            self.last_debug["title_missing"] = "missing product-title, og:title, and title tag"
            return None
        if price is None:
            self.last_debug["price_missing"] = "missing current_retail and formatted_current_price"
            return None

        unit_price_info = self._build_unit_price_info(
            title=title,
            product_window=product_window,
        )

        return Offer(
            store_id=self.store_id,
            product_key=product_key,
            title=title,
            url=page.url,
            price=price,
            original_price=original_price,
            fetch_at=datetime.now(timezone.utc),
            context=self.context,
            unit_price_info=unit_price_info,
        )

    async def _extract_title(self, page: Page, html_text: str) -> str | None:
        for selector in ('[data-test="product-title"]', "h1"):
            value = await self._text_by_selector(page, selector)
            cleaned = self._clean_text(value)
            if cleaned:
                self.last_debug["title_source"] = f"dom:{selector}"
                return self._strip_target_suffix(cleaned)

        for pattern, source in (
            (_H1_RE, "html:h1[data-test=product-title]"),
            (_OG_TITLE_RE, "meta:og:title"),
            (_TITLE_RE, "html:title"),
        ):
            match = pattern.search(html_text)
            if match is None:
                continue
            cleaned = self._clean_text(match.group("value"))
            if cleaned:
                self.last_debug["title_source"] = source
                return self._strip_target_suffix(cleaned)

        return None

    @staticmethod
    def _extract_product_key(url: str, html_text: str) -> str | None:
        match = _TCIN_IN_URL_RE.search(url)
        if match is not None:
            return match.group("tcin")

        generic = re.search(r'(?:\\)?"tcin(?:\\)?":(?:\\)?"?(?P<value>\d{6,})"?', html_text)
        if generic is None:
            return None
        return generic.group("value")

    def _extract_product_window(self, html_text: str, product_key: str) -> str:
        pattern = re.compile(_ESCAPED_TCIN_RE_TEMPLATE.format(tcin=re.escape(product_key)))
        matches = list(pattern.finditer(html_text))
        if not matches:
            return html_text

        for match in matches:
            start = max(0, match.start() - 1500)
            end = min(len(html_text), match.end() + 5000)
            window = html_text[start:end]
            if _CURRENT_RETAIL_RE.search(window) is not None:
                self.last_debug["price_source"] = "html:tcin_window.current_retail"
                return window

        first = matches[0]
        return html_text[max(0, first.start() - 1500):min(len(html_text), first.end() + 5000)]

    @staticmethod
    def _extract_price(text: str) -> float | None:
        match = _CURRENT_RETAIL_RE.search(text)
        if match is not None:
            return round(float(match.group("value")), 2)

        formatted = _FORMATTED_CURRENT_PRICE_RE.search(text)
        if formatted is None:
            return None

        price_match = _PRICE_NUMBER_RE.search(formatted.group("value"))
        if price_match is None:
            return None
        return round(float(price_match.group(0)), 2)

    @staticmethod
    def _extract_original_price(text: str, current_price: float | None) -> float | None:
        if current_price is None:
            return None

        for pattern in _ORIGINAL_PRICE_RE:
            match = pattern.search(text)
            if match is None:
                continue
            value = round(float(match.group("value")), 2)
            if value > current_price:
                return value
        return None

    @staticmethod
    def _is_out_of_stock(text: str) -> bool:
        lowered = text.lower()
        if "availability_status" in lowered and "out_of_stock" in lowered:
            return True
        if "is_out_of_stock" in lowered and "true" in lowered:
            return True
        return any(marker in lowered for marker in _OUT_OF_STOCK_MARKERS)

    def _build_unit_price_info(self, title: str, product_window: str) -> dict[str, str | float]:
        info: dict[str, str | float] = {"raw": title}

        unit_match = _UNIT_RE.search(title)
        if unit_match is not None:
            info["quantity"] = float(unit_match.group("qty"))
            info["unit"] = unit_match.group("unit").lower()

        barcode_match = _BARCODE_RE.search(product_window)
        if barcode_match is not None:
            info["upc"] = barcode_match.group("value")

        brand = self._extract_brand(product_window)
        if brand:
            info["brand"] = brand

        return info

    def _extract_brand(self, product_window: str) -> str | None:
        for marker in ("primary_brand", "brand"):
            index = product_window.find(marker)
            if index < 0:
                continue
            snippet = product_window[index:index + 400]
            for prefix, suffix in (
                ('\\"name\\":\\"', '\\"'),
                ('"name":"', '"'),
            ):
                name_index = snippet.find(prefix)
                if name_index < 0:
                    continue
                start = name_index + len(prefix)
                end = snippet.find(suffix, start)
                if end < 0:
                    continue
                brand = self._clean_text(snippet[start:end])
                if brand:
                    return brand
        return None

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
    def _clean_text(value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = html.unescape(re.sub(r"\s+", " ", value)).strip()
        return cleaned or None

    @staticmethod
    def _strip_target_suffix(title: str) -> str:
        suffix = " : Target"
        if title.endswith(suffix):
            return title[: -len(suffix)].strip()
        return title
