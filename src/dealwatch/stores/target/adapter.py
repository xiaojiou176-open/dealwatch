from __future__ import annotations

import argparse
import asyncio
import re
from typing import List, Optional

from dealwatch.core.models import Offer, PriceContext
from dealwatch.infra.config import Settings
from dealwatch.infra.playwright_client import PlaywrightClient
from dealwatch.stores.base_adapter import BaseStoreAdapter, SkipParse, safe_parse
from dealwatch.stores.target.discovery import TargetDiscovery
from dealwatch.stores.target.parser import TargetParser


class TargetAdapter(BaseStoreAdapter):
    store_id = "target"
    base_url = "https://www.target.com"
    cashback_merchant_key = "target"
    _PRICE_READY_RE = re.compile(r"\$\d+(?:\.\d{1,2})?")
    _PRICE_WAIT_ATTEMPTS = 5
    _PRICE_WAIT_DELAY_MS = 2_000

    def __init__(self, client: PlaywrightClient, settings: Settings) -> None:
        super().__init__(client, settings)
        self._discovery = TargetDiscovery()
        self._parser = TargetParser(
            store_id=self.store_id,
            context=PriceContext(region=settings.ZIP_CODE),
        )

    async def discover_deals(self) -> List[str]:
        return await self._discovery.discover_deals()

    @classmethod
    def normalize_product_url(cls, raw_url: str) -> str | None:
        return TargetDiscovery._normalize_product_url(raw_url)

    @safe_parse
    async def parse_product(self, url: str) -> Optional[Offer]:
        page = await self.client.fetch_page(
            url,
            wait_until="domcontentloaded",
            return_page=True,
        )
        try:
            await self._wait_for_price_signal(page)
            offer = await self._parser.parse(page)
            if offer is None:
                await self._capture_failed_page(page, url, "parse_returned_none")
            return offer
        except SkipParse:
            raise
        except Exception as exc:
            await self._capture_failed_page(page, url, f"parse_exception:{type(exc).__name__}")
            raise
        finally:
            await page.close()

    async def _wait_for_price_signal(self, page) -> None:
        for attempt in range(self._PRICE_WAIT_ATTEMPTS):
            html_text = await page.content()
            if "current_retail" in html_text or "formatted_current_price" in html_text:
                return

            summary = await self._parser._text_by_selector(page, "#above-the-fold-information")
            if summary:
                leading_summary = summary.split("Add to cart", 1)[0]
                if self._PRICE_READY_RE.search(leading_summary):
                    return

            if attempt + 1 < self._PRICE_WAIT_ATTEMPTS:
                await page.wait_for_timeout(self._PRICE_WAIT_DELAY_MS)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Target Adapter Self-Test")
    parser.add_argument("--test", required=True, help="Product URL to test")
    return parser.parse_args()


def _main() -> None:
    args = _parse_args()
    asyncio.run(TargetAdapter.test_adapter(args.test))


if __name__ == "__main__":
    _main()
