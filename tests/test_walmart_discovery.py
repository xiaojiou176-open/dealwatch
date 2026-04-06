import pytest

from dealwatch.stores.walmart.discovery import WalmartDiscovery


@pytest.mark.asyncio
async def test_walmart_discovery_is_manual_only() -> None:
    discovery = WalmartDiscovery()

    links = await discovery.discover_deals()

    assert links == []


def test_walmart_discovery_normalize_product_url_supported_shapes() -> None:
    assert (
        WalmartDiscovery._normalize_product_url(
            "https://www.walmart.com/ip/Great-Value-Whole-Vitamin-D-Milk-1-gal/10450117?athbdg=L1600#details"
        )
        == "https://www.walmart.com/ip/10450117"
    )
    assert (
        WalmartDiscovery._normalize_product_url("https://www.walmart.com/ip/10450117/")
        == "https://www.walmart.com/ip/10450117"
    )


def test_walmart_discovery_normalize_product_url_rejects_unsupported_shapes() -> None:
    assert WalmartDiscovery._normalize_product_url("https://www.walmart.com/ip/Great-Value-Whole-Vitamin-D-Milk-1-gal") is None
    assert WalmartDiscovery._normalize_product_url("https://www.walmart.com/browse/grocery/milk/976759_1071964") is None
    assert WalmartDiscovery._normalize_product_url("https://www.walmart.com/reviews/product/10450117") is None
    assert WalmartDiscovery._normalize_product_url("https://www.walmart.com/search?q=milk") is None
    assert WalmartDiscovery._normalize_product_url("https://evil.com/ip/10450117") is None
