import json

import pytest

from dealwatch.core.models import PriceContext, SkipReason
from dealwatch.stores.base_adapter import SkipParse
from dealwatch.stores.ranch99.parser import Ranch99Parser


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


class _FakePage:
    def __init__(self, url: str, selectors: dict[str, str | None]) -> None:
        self.url = url
        self._selectors = selectors

    def locator(self, selector: str):
        return _FakeLocator(self._selectors.get(selector))


def _payload(available: int = 3) -> str:
    return json.dumps(
        {
            "props": {
                "pageProps": {
                    "productDataRes": {
                        "data": {
                            "productId": 1615424,
                            "productName": "Lkk Premium Dark Soy Sauce",
                            "brand": {"name": "LEEKUMKEE"},
                            "variants": [
                                {
                                    "upcId": "078895126389",
                                    "variantName": "16.9000 foz/each",
                                    "netWeight": 16.9,
                                    "netWeightUom": "foz",
                                    "cooCode": "Hong Kong",
                                    "price": 4.49,
                                    "retailPrice": 5.29,
                                    "salePrice": 4.49,
                                    "available": available,
                                }
                            ],
                        }
                    }
                }
            }
        }
    )


@pytest.mark.asyncio
async def test_ranch99_parser_json_success() -> None:
    page = _FakePage(
        "https://www.99ranch.com/product-details/1615424/8899/078895126389",
        {"script#__NEXT_DATA__": _payload()},
    )
    parser = Ranch99Parser(store_id="ranch99", context=PriceContext(region="98004"))
    offer = await parser.parse(page)

    assert offer is not None
    assert offer.product_key == "078895126389"
    assert offer.title == "Lkk Premium Dark Soy Sauce"
    assert offer.price == 4.49
    assert offer.original_price == 5.29
    assert offer.unit_price_info["net_weight_uom"] == "foz"


@pytest.mark.asyncio
async def test_ranch99_parser_out_of_stock() -> None:
    page = _FakePage(
        "https://www.99ranch.com/product-details/1615424/8899/078895126389",
        {"script#__NEXT_DATA__": _payload(available=0)},
    )
    parser = Ranch99Parser(store_id="ranch99", context=PriceContext(region="98004"))

    with pytest.raises(SkipParse) as exc:
        await parser.parse(page)

    assert exc.value.reason == SkipReason.OUT_OF_STOCK


@pytest.mark.asyncio
async def test_ranch99_parser_missing_payload_returns_none() -> None:
    page = _FakePage("https://www.99ranch.com/product-details/1/1/1", {})
    parser = Ranch99Parser(store_id="ranch99", context=PriceContext(region="98004"))
    offer = await parser.parse(page)
    assert offer is None
