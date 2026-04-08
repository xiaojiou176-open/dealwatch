import pytest

from dealwatch.core.models import PriceContext, SkipReason
from dealwatch.stores.base_adapter import SkipParse
from dealwatch.stores.safeway.parser import SafewayParser


class _FakePage:
    def __init__(self, url: str, html: str) -> None:
        self.url = url
        self._html = html

    async def content(self) -> str:
        return self._html


@pytest.mark.asyncio
async def test_safeway_parser_out_of_stock_raises_skip_even_without_price() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
          {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": "Fairlife Milk Ultra-Filtered Reduced Fat 2% - 52 Fl. Oz.",
            "offers": {
              "@type": "Offer",
              "availability": "https://schema.org/OutOfStock"
            }
          }
        </script>
      </head>
      <body></body>
    </html>
    """
    page = _FakePage("https://www.safeway.com/shop/product-details.960127167.html", html)
    parser = SafewayParser(store_id="safeway", context=PriceContext(region="98004"))

    with pytest.raises(SkipParse) as exc:
        await parser.parse(page)

    assert exc.value.reason == SkipReason.OUT_OF_STOCK
    assert parser.last_debug["availability"] == "out_of_stock"


@pytest.mark.asyncio
async def test_safeway_parser_missing_price_sets_debug_reason() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
          {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": "Fairlife Milk Ultra-Filtered Reduced Fat 2% - 52 Fl. Oz.",
            "offers": {
              "@type": "Offer",
              "availability": "InStock"
            }
          }
        </script>
      </head>
      <body></body>
    </html>
    """
    page = _FakePage("https://www.safeway.com/shop/product-details.960127167.html", html)
    parser = SafewayParser(store_id="safeway", context=PriceContext(region="98004"))

    offer = await parser.parse(page)

    assert offer is None
    assert parser.last_debug["price_missing"] == "missing json_ld offer price"


@pytest.mark.asyncio
async def test_safeway_parser_missing_title_sets_debug_reason() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
          {
            "@context": "https://schema.org",
            "@type": "Product",
            "offers": {
              "@type": "Offer",
              "availability": "InStock",
              "price": "6.99"
            }
          }
        </script>
      </head>
      <body></body>
    </html>
    """
    page = _FakePage("https://www.safeway.com/shop/product-details.960127167.html", html)
    parser = SafewayParser(store_id="safeway", context=PriceContext(region="98004"))

    offer = await parser.parse(page)

    assert offer is None
    assert parser.last_debug["title_missing"] == "missing json_ld product name"


@pytest.mark.asyncio
async def test_safeway_parser_marks_incapsula_block_page() -> None:
    html = """
    <html style="height:100%">
      <head>
        <meta name="ROBOTS" content="NOINDEX, NOFOLLOW">
      </head>
      <body style="margin:0px;height:100%">
        <iframe
          id="main-iframe"
          src="/_Incapsula_Resource?incident_id=123"
          frameborder="0"
          width="100%"
          height="100%">
          Request unsuccessful. Incapsula incident ID: 123
        </iframe>
      </body>
    </html>
    """
    page = _FakePage("https://www.safeway.com/shop/product-details.960127167.html", html)
    parser = SafewayParser(store_id="safeway", context=PriceContext(region="98004"))

    offer = await parser.parse(page)

    assert offer is None
    assert parser.last_debug["page_blocked"] == "incapsula"
    assert parser.last_debug["json_ld"] == "skipped: block page"


@pytest.mark.asyncio
async def test_safeway_parser_accepts_single_quoted_json_ld_script_type() -> None:
    html = """
    <html>
      <head>
        <script type='application/ld+json' data-test='product-json'>
          {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": "Lucerne Eggs Cage Free Large - 12 Count",
            "gtin13": "0000007654321",
            "brand": {
              "@type": "Brand",
              "name": "Lucerne"
            },
            "offers": {
              "@type": "Offer",
              "availability": "https://schema.org/InStock",
              "price": "5.49"
            }
          }
        </script>
      </head>
      <body></body>
    </html>
    """
    page = _FakePage("https://www.safeway.com/shop/product-details.149030568.html", html)
    parser = SafewayParser(store_id="safeway", context=PriceContext(region="98004"))

    offer = await parser.parse(page)

    assert offer is not None
    assert offer.product_key == "0000007654321"
    assert offer.price == 5.49
    assert offer.unit_price_info["raw"] == "Lucerne Eggs Cage Free Large - 12 Count"
    assert offer.unit_price_info["quantity"] == 12.0
    assert offer.unit_price_info["unit"] == "count"
    assert "brand" not in offer.unit_price_info
    assert parser.last_debug["json_ld"] == "product"
