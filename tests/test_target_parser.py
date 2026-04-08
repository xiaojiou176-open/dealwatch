import pytest

from dealwatch.core.models import PriceContext, SkipReason
from dealwatch.core.validator import DataValidator
from dealwatch.stores.base_adapter import SkipParse
from dealwatch.stores.target.parser import TargetParser


class _FakeLocator:
    def __init__(self, text: str | None) -> None:
        self._text = text
        self.first = self

    async def count(self) -> int:
        return 0 if self._text is None else 1

    async def text_content(self) -> str | None:
        return self._text


class _FakePage:
    def __init__(
        self,
        url: str,
        html: str,
        selectors: dict[str, str | None] | None = None,
        hydrated_html: str | None = None,
        hydrated_selectors: dict[str, str | None] | None = None,
    ) -> None:
        self.url = url
        self._html = html
        self._selectors = selectors or {}
        self._hydrated_html = hydrated_html
        self._hydrated_selectors = hydrated_selectors
        self._hydrated = False

    async def content(self) -> str:
        if self._hydrated and self._hydrated_html is not None:
            return self._hydrated_html
        return self._html

    def locator(self, selector: str):
        selectors = self._selectors
        if self._hydrated and self._hydrated_selectors is not None:
            selectors = self._hydrated_selectors
        return _FakeLocator(selectors.get(selector))

    async def wait_for_selector(self, selector: str, timeout: int | None = None):
        if self._hydrated_html is None and self._hydrated_selectors is None:
            raise RuntimeError(f"selector not available: {selector}")
        self._hydrated = True
        return object()


@pytest.mark.asyncio
async def test_target_parser_html_success() -> None:
    html = """
    <html>
      <head>
        <title>Utz Ripples Original Potato Chips - 7.75oz : Target</title>
        <meta property="og:title" content="Utz Ripples Original Potato Chips - 7.75oz" />
      </head>
      <body>
        <h1 data-test="product-title">Utz Ripples Original Potato Chips - 7.75oz</h1>
        <script>
          window.__STATE__ = "{\\"product\\":{\\"tcin\\":\\"13202943\\",\\"primary_barcode\\":\\"041780272096\\",\\"current_retail\\":3.49,\\"primary_brand\\":{\\"name\\":\\"Utz\\"}}}";
        </script>
      </body>
    </html>
    """
    page = _FakePage(
        "https://www.target.com/p/-/A-13202943",
        html,
        selectors={'[data-test="product-title"]': "Utz Ripples Original Potato Chips - 7.75oz"},
    )
    parser = TargetParser(store_id="target", context=PriceContext(region="98102"))

    offer = await parser.parse(page)

    assert offer is not None
    assert offer.product_key == "13202943"
    assert offer.price == 3.49
    assert offer.title == "Utz Ripples Original Potato Chips - 7.75oz"
    assert offer.unit_price_info["upc"] == "041780272096"
    assert offer.unit_price_info["brand"] == "Utz"
    assert DataValidator().validate_offer(offer) is True


@pytest.mark.asyncio
async def test_target_parser_title_fallback_and_original_price() -> None:
    html = """
    <html>
      <head>
        <title>Utz Ripples Original Potato Chips - 7.75oz : Target</title>
      </head>
      <body>
        <script>
          window.__STATE__ = "{\\"product\\":{\\"tcin\\":\\"13202943\\",\\"current_retail\\":3.49,\\"reg_retail\\":4.29}}";
        </script>
      </body>
    </html>
    """
    page = _FakePage("https://www.target.com/p/-/A-13202943", html)
    parser = TargetParser(store_id="target", context=PriceContext(region="98102"))

    offer = await parser.parse(page)

    assert offer is not None
    assert offer.title == "Utz Ripples Original Potato Chips - 7.75oz"
    assert offer.original_price == 4.29


@pytest.mark.asyncio
async def test_target_parser_out_of_stock() -> None:
    html = """
    <html>
      <body>
        <script>
          window.__STATE__ = "{\\"product\\":{\\"tcin\\":\\"13202943\\",\\"current_retail\\":3.49,\\"availability_status\\":\\"OUT_OF_STOCK\\"}}";
        </script>
      </body>
    </html>
    """
    page = _FakePage("https://www.target.com/p/-/A-13202943", html)
    parser = TargetParser(store_id="target", context=PriceContext(region="98102"))

    with pytest.raises(SkipParse) as exc:
        await parser.parse(page)

    assert exc.value.reason == SkipReason.OUT_OF_STOCK


@pytest.mark.asyncio
async def test_target_parser_missing_price_returns_none() -> None:
    html = """
    <html>
      <head><title>Utz Ripples Original Potato Chips - 7.75oz : Target</title></head>
      <body><script>window.__STATE__ = "{\\"product\\":{\\"tcin\\":\\"13202943\\"}}"</script></body>
    </html>
    """
    page = _FakePage("https://www.target.com/p/-/A-13202943", html)
    parser = TargetParser(store_id="target", context=PriceContext(region="98102"))

    offer = await parser.parse(page)
    assert offer is None


@pytest.mark.asyncio
async def test_target_parser_extracts_price_when_price_block_is_far_from_tcin() -> None:
    filler = "x" * 18_000
    html = f"""
    <html>
      <head>
        <title>Fairlife Lactose-Free 2% Chocolate Milk - 52 fl oz : Target</title>
      </head>
      <body>
        <script>
          window.__STATE__ = "{{\\"product\\":{{\\"tcin\\":\\"17093199\\",\\"primary_brand\\":{{\\"name\\":\\"fairlife\\"}}}}}}{filler}\\"price\\":{{\\"current_retail\\":5.39,\\"formatted_current_price\\":\\"$5.39\\",\\"reg_retail\\":5.39,\\"primary_barcode\\":\\"811620020444\\"}}";
        </script>
      </body>
    </html>
    """
    page = _FakePage(
        "https://www.target.com/p/fairlife-lactose-free-2-chocolate-milk-52-fl-oz/-/A-17093199",
        html,
        selectors={'[data-test="product-title"]': "Fairlife Lactose-Free 2% Chocolate Milk - 52 fl oz"},
    )
    parser = TargetParser(store_id="target", context=PriceContext(region="98102"))

    offer = await parser.parse(page)

    assert offer is not None
    assert offer.price == 5.39
    assert offer.unit_price_info["brand"] == "fairlife"
    assert parser.last_debug["price_source"] == "html:tcin_window.price"


@pytest.mark.asyncio
async def test_target_parser_falls_back_to_above_the_fold_dom_price() -> None:
    html = """
    <html>
      <head>
        <title>Fairlife Lactose-Free 2% Chocolate Milk - 52 fl oz : Target</title>
      </head>
      <body>
        <script>
          window.__STATE__ = "{\\"product\\":{\\"tcin\\":\\"17093199\\",\\"primary_barcode\\":\\"811620020444\\",\\"primary_brand\\":{\\"name\\":\\"fairlife\\"}}}";
        </script>
      </body>
    </html>
    """
    page = _FakePage(
        "https://www.target.com/p/fairlife-lactose-free-2-chocolate-milk-52-fl-oz/-/A-17093199",
        html,
        selectors={
            '[data-test="product-title"]': "Fairlife Lactose-Free 2% Chocolate Milk - 52 fl oz",
            "#above-the-fold-information": (
                "Shop all fairlife\n"
                "Fairlife Lactose-Free 2% Chocolate Milk - 52 fl oz\n"
                "4.7 out of 5 stars with 4570 reviews\n"
                "$5.39 ($0.10/fluid ounce)\n"
                "Add to cart\n"
                "Pay over time With Affirm on orders over $50"
            ),
        },
    )
    parser = TargetParser(store_id="target", context=PriceContext(region="98102"))

    offer = await parser.parse(page)

    assert offer is not None
    assert offer.price == 5.39
    assert offer.unit_price_info["upc"] == "811620020444"
    assert offer.unit_price_info["brand"] == "fairlife"
    assert parser.last_debug["price_source"] == "dom:#above-the-fold-information"


@pytest.mark.asyncio
async def test_target_parser_waits_for_hydrated_dom_price() -> None:
    html = """
    <html>
      <head>
        <title>Fairlife Lactose-Free 2% Chocolate Milk - 52 fl oz : Target</title>
      </head>
      <body>
        <script>
          window.__STATE__ = "{\\"product\\":{\\"tcin\\":\\"17093199\\",\\"primary_barcode\\":\\"811620020444\\",\\"primary_brand\\":{\\"name\\":\\"fairlife\\"}}}";
        </script>
      </body>
    </html>
    """
    page = _FakePage(
        "https://www.target.com/p/fairlife-lactose-free-2-chocolate-milk-52-fl-oz/-/A-17093199",
        html,
        selectors={
            '[data-test="product-title"]': "Fairlife Lactose-Free 2% Chocolate Milk - 52 fl oz",
        },
        hydrated_html=html,
        hydrated_selectors={
            '[data-test="product-title"]': "Fairlife Lactose-Free 2% Chocolate Milk - 52 fl oz",
            '[data-test="product-price"]': "$5.39",
        },
    )
    parser = TargetParser(store_id="target", context=PriceContext(region="98102"))

    offer = await parser.parse(page)

    assert offer is not None
    assert offer.price == 5.39
    assert offer.unit_price_info["upc"] == "811620020444"
    assert offer.unit_price_info["brand"] == "fairlife"
    assert parser.last_debug["price_wait"] == (
        'selector:[data-test="product-price"], #above-the-fold-information'
    )
    assert parser.last_debug["price_source"] == 'dom:[data-test="product-price"]'
