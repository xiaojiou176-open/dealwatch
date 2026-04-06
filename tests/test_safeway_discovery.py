import pytest

from dealwatch.stores.safeway.discovery import SafewayDiscovery


@pytest.mark.asyncio
async def test_safeway_discovery_is_manual_only() -> None:
    discovery = SafewayDiscovery()

    links = await discovery.discover_deals()

    assert links == []


def test_safeway_discovery_normalize_product_url() -> None:
    url = "https://www.safeway.com/shop/product-details.960127167.html?storeId=3132#details"
    assert (
        SafewayDiscovery._normalize_product_url(url)
        == "https://www.safeway.com/shop/product-details.960127167.html"
    )
    assert SafewayDiscovery._normalize_product_url("https://www.safeway.com/shop/categories/dairy") is None
    assert SafewayDiscovery._normalize_product_url("https://evil.com/shop/product-details.960127167.html") is None
