import json

import pytest

from dealwatch.core.models import PriceContext, SkipReason
from dealwatch.stores.base_adapter import SkipParse
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
    def __init__(self, url: str, selectors: dict[str, str | None], html_text: str = "") -> None:
        self.url = url
        self._selectors = selectors
        self._html_text = html_text

    async def content(self) -> str:
        return self._html_text

    def locator(self, selector: str):
        if selector in self._selectors:
            return _FakeLocator(self._selectors[selector])
        return _FakeLocator(None)


@pytest.mark.asyncio
async def test_weee_parser_json_success() -> None:
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

    assert offer is not None
    assert offer.product_key == "abc123"
    assert offer.price == 3.99
    assert offer.original_price == 4.99
    assert offer.unit_price_info.get("unit") == "lb"


@pytest.mark.asyncio
async def test_weee_parser_dom_fallback() -> None:
    page = _FakePage(
        "https://www.sayweee.com/zh/product/xyz",
        {
            "h1": "Test Noodles 500g",
            '[class*="price_current"]': "$2.50",
            '[class*="price_original"]': "$3.00",
        },
    )
    parser = WeeeParser(store_id="weee", context=PriceContext(region="00000"))
    offer = await parser.parse(page)

    assert offer is not None
    assert offer.product_key == "xyz"
    assert offer.price == 2.50
    assert offer.original_price == 3.00


@pytest.mark.asyncio
async def test_weee_parser_json_ld_fallback() -> None:
    json_ld = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "Asian Honey Pears 3ct",
        "sku": "5869",
        "offers": {
            "@type": "Offer",
            "price": "6.79",
            "priceCurrency": "USD",
            "availability": "https://schema.org/InStock",
        },
    }
    page = _FakePage(
        "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
        {"script[type=\"application/ld+json\"]": json.dumps(json_ld)},
    )
    parser = WeeeParser(store_id="weee", context=PriceContext(region="00000"))
    offer = await parser.parse(page)

    assert offer is not None
    assert offer.product_key == "5869"
    assert offer.price == 6.79
    assert offer.title == "Asian Honey Pears 3ct"


@pytest.mark.asyncio
async def test_weee_parser_embedded_product_fallback() -> None:
    title_text = (
        "\u51b0\u7cd6\u6da6\u5fc3\u79cb\u6708\u68a8 3\u9897\u88c5 2.5-2.75 \u78c5"
    )
    subtitle_text = (
        "\u8089\u8d28\u7ec6\u817b \u6c41\u591a\u5473\u751c \u6e05\u9999\u723d\u53e3"
    )
    html = """
    <html>
      <head>
        <title>{title} - Weee! </title>
        <meta property="og:title" content="xiao176jiou | {title}" />
      </head>
      <body>
        <script>
          window.__flight = "{{\\"product\\":{{\\"id\\":5869,\\"name\\":\\"{title}\\",\\"sub_name\\":\\"{subtitle}\\",\\"sold_status_available\\":true,\\"price\\":6.99,\\"base_price\\":9.99,\\"unit_info\\":\\"2.5-2.75 \\u78c5\\"}}}}";
        </script>
      </body>
    </html>
    """.format(title=title_text, subtitle=subtitle_text)
    page = _FakePage(
        "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
        {},
        html_text=html,
    )
    parser = WeeeParser(store_id="weee", context=PriceContext(region="00000"))

    offer = await parser.parse(page)

    assert offer is not None
    assert offer.product_key == "5869"
    assert offer.title == title_text
    assert offer.price == 6.99
    assert offer.original_price == 9.99
    assert offer.unit_price_info["raw"] == title_text
    assert parser.last_debug["json_status"] == "embedded.product"


@pytest.mark.asyncio
async def test_weee_parser_json_ld_out_of_stock() -> None:
    json_ld = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "Out of Stock Item",
        "sku": "out-stock-1",
        "offers": {
            "@type": "Offer",
            "price": "2.99",
            "availability": "https://schema.org/OutOfStock",
        },
    }
    page = _FakePage(
        "https://www.sayweee.com/zh/product/out-stock-1",
        {"script[type=\"application/ld+json\"]": json.dumps(json_ld)},
    )
    parser = WeeeParser(store_id="weee", context=PriceContext(region="00000"))

    with pytest.raises(SkipParse) as exc:
        await parser.parse(page)

    assert exc.value.reason == SkipReason.OUT_OF_STOCK


@pytest.mark.asyncio
async def test_weee_parser_json_ld_sanitizes_control_chars() -> None:
    bad_json = (
        "{\"@context\":\"https://schema.org\","
        "\"@type\":\"Product\","
        "\"name\":\"Bad\x0bName\","
        "\"sku\":\"bad-1\","
        "\"offers\":{\"@type\":\"Offer\",\"price\":\"1.23\","
        "\"availability\":\"https://schema.org/InStock\"}}"
    )
    page = _FakePage(
        "https://www.sayweee.com/zh/product/bad-1",
        {"script[type=\"application/ld+json\"]": bad_json},
    )
    parser = WeeeParser(store_id="weee", context=PriceContext(region="00000"))
    offer = await parser.parse(page)

    assert offer is not None
    assert offer.title == "BadName"
    assert offer.price == 1.23


@pytest.mark.asyncio
async def test_weee_parser_out_of_stock() -> None:
    product = {
        "title": "Sold Out Item",
        "price": 1.99,
        "out_of_stock": True,
        "product_id": "soldout",
    }
    payload = json.dumps({"props": {"pageProps": {"product": product}}})
    page = _FakePage(
        "https://www.sayweee.com/zh/product/soldout",
        {"script#__NEXT_DATA__": payload},
    )
    parser = WeeeParser(store_id="weee", context=PriceContext(region="00000"))

    with pytest.raises(SkipParse) as exc:
        await parser.parse(page)

    assert exc.value.reason == SkipReason.OUT_OF_STOCK


def test_weee_parser_helpers() -> None:
    parser = WeeeParser(store_id="weee", context=PriceContext(region="00000"))

    product = {
        "pricing": {"price": "1.99", "base_price": "2.50"},
        "available": False,
        "unit": "2 lb",
        "sku": "sku-1",
    }
    price, base, price_key, base_key = parser._extract_prices(product)
    assert price == 1.99
    assert base == 2.50
    assert price_key == "pricing.price"
    assert base_key == "pricing.base_price"

    assert parser._extract_not_available(product) is True
    assert parser._extract_unit_hint(product) == "2 lb"
    assert parser._extract_product_key(product, "https://example.com/zh/product/sku-1") == "sku-1"

    assert parser._parse_price("$1,234.50") == 1234.50
    assert parser._build_unit_price_info("Pack of 3") == {"raw": "Pack of 3"}


@pytest.mark.asyncio
async def test_weee_parser_extract_payload_branches() -> None:
    parser = WeeeParser(store_id="weee", context=PriceContext(region="00000"))

    missing = _FakePage("https://example.com", {})
    payload = await parser._extract_product_payload(missing, missing.url, await missing.content())
    assert payload is None

    empty = _FakePage("https://example.com", {"script#__NEXT_DATA__": ""})
    payload = await parser._extract_product_payload(empty, empty.url, await empty.content())
    assert payload is None

    invalid = _FakePage("https://example.com", {"script#__NEXT_DATA__": "{bad"})
    payload = await parser._extract_product_payload(invalid, invalid.url, await invalid.content())
    assert payload is None

    fallback_product = {
        "props": {
            "pageProps": {
                "fallback": {
                    "x": {"product": {"title": "T", "price": 1.0}}
                }
            }
        }
    }
    page = _FakePage(
        "https://example.com",
        {"script#__NEXT_DATA__": json.dumps(fallback_product)},
    )
    payload = await parser._extract_product_payload(page, page.url, await page.content())
    assert payload is not None

    deep_product = {
        "props": {
            "pageProps": {
                "fallback": {
                    "x": {"data": {"title": "T", "price": 2.0}}
                }
            }
        }
    }
    deep_page = _FakePage(
        "https://example.com",
        {"script#__NEXT_DATA__": json.dumps(deep_product)},
    )
    payload = await parser._extract_product_payload(deep_page, deep_page.url, await deep_page.content())
    assert payload is not None

    deep_search = _FakePage(
        "https://example.com",
        {"script#__NEXT_DATA__": json.dumps({"data": [{"title": "T", "price": 3.0}]})},
    )
    payload = await parser._extract_product_payload(
        deep_search,
        deep_search.url,
        await deep_search.content(),
    )
    assert payload is not None


@pytest.mark.asyncio
async def test_weee_parser_text_by_selector_none() -> None:
    page = _FakePage("https://example.com", {})
    text = await WeeeParser._text_by_selector(page, "h1")
    assert text is None


@pytest.mark.asyncio
async def test_weee_parser_missing_price_returns_none() -> None:
    product = {"title": "No Price", "product_id": "np1"}
    page = _FakePage(
        "https://www.sayweee.com/zh/product/np1",
        {"script#__NEXT_DATA__": json.dumps({"props": {"pageProps": {"product": product}}})},
    )
    parser = WeeeParser(store_id="weee", context=PriceContext(region="00000"))
    offer = await parser.parse(page)
    assert offer is None


def test_weee_parser_as_bool_strings() -> None:
    assert WeeeParser._as_bool("true") is True
    assert WeeeParser._as_bool("false") is False
    assert WeeeParser._as_bool("sold out") is True
    assert WeeeParser._as_bool("https://schema.org/OutOfStock") is True
    assert WeeeParser._as_bool("https://schema.org/InStock") is False
