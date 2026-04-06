from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from playwright.async_api import Page

from dealwatch.core.models import Offer, PriceContext, SkipReason
from dealwatch.stores.base_adapter import SkipParse


@dataclass(slots=True)
class Ranch99Parser:
    store_id: str
    context: PriceContext
    logger: logging.Logger = field(init=False, repr=False)
    last_debug: dict[str, str] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        self.logger = logging.getLogger("dealwatch.stores.ranch99.parser")

    async def parse(self, page: Page) -> Offer | None:
        self.last_debug = {"url": page.url}
        product = await self._extract_product_payload(page)
        if product is None:
            self.last_debug["payload"] = "missing"
            return None

        variant = self._select_variant(product)
        title = self._extract_title(product, variant)
        price = self._extract_price(variant)
        if not title or price is None:
            return None

        if self._is_out_of_stock(variant):
            self.last_debug["availability"] = "out_of_stock"
            raise SkipParse(SkipReason.OUT_OF_STOCK)

        product_key = self._extract_product_key(product, variant)
        if product_key is None:
            self.last_debug["product_key"] = "missing"
            return None

        original_price = self._extract_original_price(variant, price)
        unit_price_info = self._build_unit_price_info(variant)

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

    async def _extract_product_payload(self, page: Page) -> dict[str, Any] | None:
        locator = page.locator("script#__NEXT_DATA__")
        if await locator.count() == 0:
            return None
        raw_json = await locator.first.text_content()
        if not raw_json:
            return None
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError:
            self.logger.exception("Failed to decode __NEXT_DATA__ for %s", page.url)
            return None

        product = (
            data.get("props", {})
            .get("pageProps", {})
            .get("productDataRes", {})
            .get("data")
        )
        return product if isinstance(product, dict) else None

    @staticmethod
    def _select_variant(product: dict[str, Any]) -> dict[str, Any]:
        variants = product.get("variants")
        if isinstance(variants, list):
            for candidate in variants:
                if isinstance(candidate, dict):
                    return candidate
        return {}

    @staticmethod
    def _extract_title(product: dict[str, Any], variant: dict[str, Any]) -> str | None:
        for key in ("productNameEN", "productName", "productNameSCH", "productNameTCH"):
            value = str(variant.get(key) or product.get(key) or "").strip()
            if value:
                return value
        return None

    @staticmethod
    def _extract_price(variant: dict[str, Any]) -> float | None:
        for key in ("salePrice", "price", "retailPrice"):
            value = variant.get(key)
            if value in (None, ""):
                continue
            return float(value)
        return None

    @staticmethod
    def _extract_original_price(variant: dict[str, Any], price: float) -> float | None:
        retail = variant.get("retailPrice")
        if retail in (None, ""):
            return None
        retail_value = float(retail)
        return retail_value if retail_value > price else None

    @staticmethod
    def _is_out_of_stock(variant: dict[str, Any]) -> bool:
        available = variant.get("available")
        if available is None:
            return False
        try:
            return int(available) <= 0
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _extract_product_key(product: dict[str, Any], variant: dict[str, Any]) -> str | None:
        for key in ("upcId", "variantId", "articleNumber"):
            value = str(variant.get(key) or product.get(key) or "").strip()
            if value:
                return value
        product_id = product.get("productId")
        return str(product_id).strip() if product_id is not None else None

    @staticmethod
    def _build_unit_price_info(variant: dict[str, Any]) -> dict[str, Any]:
        raw = str(variant.get("variantName") or "").strip()
        info: dict[str, Any] = {}
        if raw:
            info["raw"] = raw
        net_weight = variant.get("netWeight")
        if net_weight not in (None, ""):
            info["net_weight"] = float(net_weight)
        net_weight_uom = str(variant.get("netWeightUom") or "").strip()
        if net_weight_uom:
            info["net_weight_uom"] = net_weight_uom.lower()
        coo = str(variant.get("cooCode") or "").strip()
        if coo:
            info["country_of_origin"] = coo
        return info
