import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from dealwatch.core.models import PriceContext
from dealwatch.core.validator import DataValidator
from dealwatch.infra.config import PROJECT_ROOT
from dealwatch.stores import (
    STORE_CAPABILITY_REGISTRY,
    STORE_REGISTRY,
    derive_missing_capabilities,
    derive_runtime_binding_blockers,
    is_runtime_binding_eligible,
)
from dealwatch.stores.ranch99.parser import Ranch99Parser
from dealwatch.stores.safeway.parser import SafewayParser
from dealwatch.stores.target.parser import TargetParser
from dealwatch.stores.walmart.parser import WalmartParser
from dealwatch.stores.weee.parser import WeeeParser


class _FakeLocator:
    def __init__(self, text: str | list[str] | None) -> None:
        if text is None:
            self._texts = []
        elif isinstance(text, list):
            self._texts = text
        else:
            self._texts = [text]
        self.first = self

    async def count(self) -> int:
        return len(self._texts)

    async def text_content(self) -> str | None:
        if not self._texts:
            return None
        return self._texts[0]

    async def all_text_contents(self) -> list[str]:
        return list(self._texts)


class _FakePage:
    def __init__(
        self,
        url: str,
        selectors: dict[str, str | None],
        *,
        content: str = "",
        title: str = "",
    ) -> None:
        self.url = url
        self._selectors = selectors
        self._content = content
        self._title = title

    def locator(self, selector: str):
        if selector in self._selectors:
            return _FakeLocator(self._selectors[selector])
        return _FakeLocator(None)

    async def content(self) -> str:
        return self._content

    async def title(self) -> str:
        return self._title


def _assert_offer_contract(offer, store_id: str, url_prefix: str) -> None:
    assert offer is not None
    assert offer.store_id == store_id
    assert offer.url.startswith(url_prefix)
    assert offer.product_key
    assert offer.title
    assert isinstance(offer.unit_price_info, dict)
    for key, value in offer.unit_price_info.items():
        assert str(key).strip()
        assert value is not None
    assert offer.fetch_at.tzinfo is not None
    assert offer.fetch_at <= datetime.now(timezone.utc)
    if offer.original_price is not None:
        assert offer.original_price >= offer.price

    validator = DataValidator()
    assert validator.validate_offer(offer) is True


@pytest.mark.asyncio
async def test_adapter_contract_weee_json_payload() -> None:
    product = {
        "title": "Fresh Apple 2 lb",
        "price": 3.99,
        "base_price": 4.99,
        "product_id": "abc123",
    }
    payload = json.dumps({"props": {"pageProps": {"product": product}}})
    page = _FakePage(
        "https://www.sayweee.com/zh/product/abc123",
        {"script#__NEXT_DATA__": payload},
    )

    parser = WeeeParser(store_id="weee", context=PriceContext(region="00000"))
    offer = await parser.parse(page)

    _assert_offer_contract(offer, "weee", "https://www.sayweee.com")


@pytest.mark.asyncio
async def test_adapter_contract_weee_dom_fallback() -> None:
    page = _FakePage(
        "https://www.sayweee.com/zh/product/xyz",
        {
            "h1": "Golden Noodles 500g",
            '[class*="price_current"]': "$2.50",
            '[class*="price_original"]': "$3.00",
        },
    )
    parser = WeeeParser(store_id="weee", context=PriceContext(region="00000"))
    offer = await parser.parse(page)

    _assert_offer_contract(offer, "weee", "https://www.sayweee.com")


@pytest.mark.asyncio
async def test_adapter_contract_ranch99_json_payload() -> None:
    payload = json.dumps(
        {
            "props": {
                "pageProps": {
                    "productDataRes": {
                        "data": {
                            "productId": 1615424,
                            "productName": "Lkk Premium Dark Soy Sauce",
                            "variants": [
                                {
                                    "upcId": "078895126389",
                                    "variantName": "16.9000 foz/each",
                                    "netWeight": 16.9,
                                    "netWeightUom": "foz",
                                    "price": 4.49,
                                    "retailPrice": 5.29,
                                    "salePrice": 4.49,
                                    "available": 3,
                                }
                            ],
                        }
                    }
                }
            }
        }
    )
    page = _FakePage(
        "https://www.99ranch.com/product-details/1615424/8899/078895126389",
        {"script#__NEXT_DATA__": payload},
    )

    parser = Ranch99Parser(store_id="ranch99", context=PriceContext(region="00000"))
    offer = await parser.parse(page)

    _assert_offer_contract(offer, "ranch99", "https://www.99ranch.com")


@pytest.mark.asyncio
async def test_adapter_contract_target_html_payload() -> None:
    html = """
    <html>
      <head>
        <title>Utz Ripples Original Potato Chips - 7.75oz : Target</title>
      </head>
      <body>
        <script>tcin\\":\\"13202943\\"</script>
        <script>primary_barcode\\":\\"041780272096\\"</script>
        <script>primary_brand\\":{"name\\":\\"Utz\\"}</script>
        <script>current_retail\\":3.49</script>
        <script>reg_retail\\":3.99</script>
        <script>formatted_unit_price\\":\\"$0.45\\"</script>
      </body>
    </html>
    """
    page = _FakePage(
        "https://www.target.com/p/utz-ripples-original-potato-chips-7-75oz/-/A-13202943",
        {},
        content=html,
        title="Utz Ripples Original Potato Chips - 7.75oz : Target",
    )

    parser = TargetParser(store_id="target", context=PriceContext(region="00000"))
    offer = await parser.parse(page)

    _assert_offer_contract(offer, "target", "https://www.target.com")


@pytest.mark.asyncio
async def test_adapter_contract_safeway_json_ld_payload() -> None:
    html = """
    <html>
      <head>
        <title>Fairlife Milk Ultra-Filtered Reduced Fat 2% - 52 Fl. Oz. - safeway</title>
        <script type="application/ld+json">
          {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": "Fairlife Milk Ultra-Filtered Reduced Fat 2% - 52 Fl. Oz.",
            "gtin13": "0000001234567",
            "brand": {
              "@type": "Brand",
              "name": "fairlife"
            },
            "offers": {
              "@type": "Offer",
              "availability": "InStock",
              "price": "6.99",
              "priceCurrency": "USD",
              "url": "https://www.safeway.com/shop/product-details.960127167.html"
            }
          }
        </script>
      </head>
      <body></body>
    </html>
    """
    page = _FakePage(
        "https://www.safeway.com/shop/product-details.960127167.html",
        {},
        content=html,
        title="Fairlife Milk Ultra-Filtered Reduced Fat 2% - 52 Fl. Oz. - safeway",
    )

    parser = SafewayParser(store_id="safeway", context=PriceContext(region="00000"))
    offer = await parser.parse(page)

    _assert_offer_contract(offer, "safeway", "https://www.safeway.com")


@pytest.mark.asyncio
async def test_adapter_contract_safeway_json_ld_collection_payload() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
          [
            {
              "@context": "https://schema.org",
              "@type": "BreadcrumbList",
              "itemListElement": []
            },
            {
              "@context": "https://schema.org",
              "@type": "Product",
              "name": "Organic Strawberries - 16 Oz.",
              "brand": {
                "@type": "Brand",
                "name": "O Organics"
              },
              "offers": [
                {
                  "@type": "Offer",
                  "availability": "https://schema.org/InStock",
                  "price": "4.99",
                  "priceCurrency": "USD"
                }
              ]
            }
          ]
        </script>
      </head>
      <body></body>
    </html>
    """
    page = _FakePage(
        "https://www.safeway.com/shop/product-details.149030568.html?storeId=3132",
        {},
        content=html,
        title="Organic Strawberries - 16 Oz. - safeway",
    )

    parser = SafewayParser(store_id="safeway", context=PriceContext(region="00000"))
    offer = await parser.parse(page)

    _assert_offer_contract(offer, "safeway", "https://www.safeway.com")
    assert offer.product_key == "149030568"
    assert offer.unit_price_info["brand"] == "O Organics"
    assert offer.unit_price_info["quantity"] == 16.0
    assert offer.unit_price_info["unit"] == "oz"


@pytest.mark.asyncio
async def test_adapter_contract_walmart_json_ld_payload() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
          {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": "Great Value Whole Vitamin D Milk, 1 gal",
            "sku": "10450117",
            "gtin13": "0078742012345",
            "brand": {
              "@type": "Brand",
              "name": "Great Value"
            },
            "offers": {
              "@type": "Offer",
              "availability": "https://schema.org/InStock",
              "price": "3.74",
              "priceCurrency": "USD"
            }
          }
        </script>
      </head>
      <body></body>
    </html>
    """
    page = _FakePage(
        "https://www.walmart.com/ip/Great-Value-Whole-Vitamin-D-Milk-1-gal/10450117",
        {},
        content=html,
        title="Great Value Whole Vitamin D Milk, 1 gal - Walmart",
    )

    parser = WalmartParser(store_id="walmart", context=PriceContext(region="00000"))
    offer = await parser.parse(page)

    _assert_offer_contract(offer, "walmart", "https://www.walmart.com")


def test_store_capability_registry_covers_live_store_registry() -> None:
    assert set(STORE_CAPABILITY_REGISTRY) == set(STORE_REGISTRY)
    for store_id, capability in STORE_CAPABILITY_REGISTRY.items():
        assert capability.store_id == store_id
        assert capability.support_tier in {"official_full", "official_partial", "official_in_progress"}
        assert isinstance(capability.default_enabled, bool)
        assert isinstance(capability.support_reason_codes, tuple)
        assert isinstance(capability.next_step_codes, tuple)
        assert capability.contract_test_paths
        assert "tests/test_adapter_contracts.py" in capability.contract_test_paths
        for test_path in capability.contract_test_paths:
            assert (PROJECT_ROOT / Path(test_path)).is_file()
        assert capability.discovery_mode
        assert capability.parse_mode
        if capability.support_tier == "official_full":
            assert capability.supports_compare_intake is True
            assert capability.supports_watch_task is True
            assert capability.supports_watch_group is True
            assert capability.supports_recovery is True
            assert capability.support_reason_codes == ()
            assert capability.next_step_codes == ()
            assert derive_missing_capabilities(capability) == ()
            assert derive_runtime_binding_blockers(capability) == ()
            assert is_runtime_binding_eligible(capability) is True
        if capability.support_tier == "official_partial":
            assert capability.supports_compare_intake is True
            assert capability.supports_watch_task is True
            assert capability.support_reason_codes
            assert capability.next_step_codes
            assert (
                capability.supports_watch_group is False
                or capability.supports_recovery is False
                or capability.cashback_supported is False
            )
            assert derive_runtime_binding_blockers(capability) == ()
            assert is_runtime_binding_eligible(capability) is True
        if capability.support_tier == "official_in_progress":
            assert capability.support_reason_codes
            assert capability.next_step_codes
            assert derive_runtime_binding_blockers(capability)
            assert is_runtime_binding_eligible(capability) is False
        if store_id == "safeway":
            assert capability.support_tier == "official_full"
            assert capability.default_enabled is True
            assert capability.cashback_supported is True
            assert capability.supports_watch_group is True
            assert capability.supports_recovery is True
            assert "tests/test_safeway_adapter.py" in capability.contract_test_paths
            assert "tests/test_product_service.py" in capability.contract_test_paths
            assert "tests/test_product_api.py" in capability.contract_test_paths
