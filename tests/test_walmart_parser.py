import pytest

from dealwatch.core.models import PriceContext, SkipReason
from dealwatch.core.validator import DataValidator
from dealwatch.stores.base_adapter import SkipParse
from dealwatch.stores.walmart.parser import WalmartParser


class _FakePage:
    def __init__(self, url: str, html: str) -> None:
        self.url = url
        self._html = html

    async def content(self) -> str:
        return self._html


@pytest.mark.asyncio
async def test_walmart_parser_json_ld_success() -> None:
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
    page = _FakePage("https://www.walmart.com/ip/Great-Value-Whole-Vitamin-D-Milk-1-gal/10450117", html)
    parser = WalmartParser(store_id="walmart", context=PriceContext(region="98102"))

    offer = await parser.parse(page)

    assert offer is not None
    assert offer.product_key == "10450117"
    assert offer.title == "Great Value Whole Vitamin D Milk, 1 gal"
    assert offer.price == 3.74
    assert offer.unit_price_info["raw"] == "Great Value Whole Vitamin D Milk, 1 gal"
    assert offer.unit_price_info["gtin"] == "0078742012345"
    assert offer.unit_price_info["quantity"] == 1.0
    assert offer.unit_price_info["unit"] == "gal"
    assert DataValidator().validate_offer(offer) is True


@pytest.mark.asyncio
async def test_walmart_parser_out_of_stock_raises_skip() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
          {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": "Great Value Whole Vitamin D Milk, 1 gal",
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
    page = _FakePage("https://www.walmart.com/ip/10450117", html)
    parser = WalmartParser(store_id="walmart", context=PriceContext(region="98102"))

    with pytest.raises(SkipParse) as exc:
        await parser.parse(page)

    assert exc.value.reason == SkipReason.OUT_OF_STOCK
    assert parser.last_debug["availability"] == "out_of_stock"


@pytest.mark.asyncio
async def test_walmart_parser_missing_price_sets_debug_reason() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
          {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": "Great Value Whole Vitamin D Milk, 1 gal",
            "offers": {
              "@type": "Offer",
              "availability": "https://schema.org/InStock"
            }
          }
        </script>
      </head>
      <body></body>
    </html>
    """
    page = _FakePage("https://www.walmart.com/ip/10450117", html)
    parser = WalmartParser(store_id="walmart", context=PriceContext(region="98102"))

    offer = await parser.parse(page)

    assert offer is None
    assert parser.last_debug["price_missing"] == "missing json_ld offer price"


@pytest.mark.asyncio
async def test_walmart_parser_marks_robot_block_page() -> None:
    html = """
    <html>
      <head><title>Robot or human?</title></head>
      <body>
        <div>Activate and hold the button to confirm that you're human. Thank You!</div>
      </body>
    </html>
    """
    page = _FakePage("https://www.walmart.com/blocked?url=L2lwLzQzOTg0MzQz&g=b", html)
    parser = WalmartParser(store_id="walmart", context=PriceContext(region="98102"))

    offer = await parser.parse(page)

    assert offer is None
    assert parser.last_debug["page_blocked"] == "walmart_robot_or_human"
    assert parser.last_debug["json_ld"] == "skipped: block page"
