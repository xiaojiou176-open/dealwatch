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
    def __init__(self, url: str, html: str, selectors: dict[str, str | None] | None = None) -> None:
        self.url = url
        self._html = html
        self._selectors = selectors or {}

    async def content(self) -> str:
        return self._html

    def locator(self, selector: str):
        return _FakeLocator(self._selectors.get(selector))


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
