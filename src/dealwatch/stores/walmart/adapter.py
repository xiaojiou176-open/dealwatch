from __future__ import annotations

import argparse
import asyncio
from typing import List, Optional

from dealwatch.core.models import Offer, PriceContext
from dealwatch.infra.config import Settings
from dealwatch.infra.playwright_client import PlaywrightClient
from dealwatch.stores.base_adapter import BaseStoreAdapter, SkipParse, safe_parse
from dealwatch.stores.walmart.discovery import WalmartDiscovery
from dealwatch.stores.walmart.parser import WalmartParser


class WalmartAdapter(BaseStoreAdapter):
    store_id = "walmart"
    base_url = "https://www.walmart.com"
    cashback_merchant_key = "walmart"

    def __init__(self, client: PlaywrightClient, settings: Settings) -> None:
        super().__init__(client, settings)
        self._discovery = WalmartDiscovery()
        self._parser = WalmartParser(
            store_id=self.store_id,
            context=PriceContext(region=settings.ZIP_CODE),
        )

    async def discover_deals(self) -> List[str]:
        return await self._discovery.discover_deals()

    @classmethod
    def normalize_product_url(cls, raw_url: str) -> str | None:
        return WalmartDiscovery._normalize_product_url(raw_url)

    @safe_parse
    async def parse_product(self, url: str) -> Optional[Offer]:
        page = await self.client.fetch_page(url, return_page=True)
        try:
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


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Walmart Adapter Self-Test")
    parser.add_argument("--test", required=True, help="Product URL to test")
    return parser.parse_args()


def _main() -> None:
    args = _parse_args()
    asyncio.run(WalmartAdapter.test_adapter(args.test))


if __name__ == "__main__":
    _main()
