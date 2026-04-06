import pytest

from dealwatch.stores.ranch99.discovery import Ranch99Discovery


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        return None


class _FakeClient:
    def __init__(self, responses: list[str]) -> None:
        self._responses = responses
        self._index = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url: str) -> _FakeResponse:
        text = self._responses[self._index]
        self._index += 1
        return _FakeResponse(text)


@pytest.mark.asyncio
async def test_ranch99_discovery_aggregates_sitemaps(monkeypatch) -> None:
    responses = [
        """
        <urlset>
          <url><loc>https://www.99ranch.com/product-details/1/8899/abc</loc></url>
          <url><loc>https://www.99ranch.com/product-details/2/8899/def</loc></url>
        </urlset>
        """,
        """
        <urlset>
          <url><loc>https://www.99ranch.com/product-details/2/8899/def</loc></url>
          <url><loc>https://www.99ranch.com/product-details/3/8899/ghi</loc></url>
        </urlset>
        """,
    ]
    monkeypatch.setattr(
        "dealwatch.stores.ranch99.discovery.httpx.AsyncClient",
        lambda **kwargs: _FakeClient(responses),
    )

    discovery = Ranch99Discovery()
    links = await discovery.discover_deals()

    assert links == [
        "https://www.99ranch.com/product-details/1/8899/abc",
        "https://www.99ranch.com/product-details/2/8899/def",
        "https://www.99ranch.com/product-details/3/8899/ghi",
    ]


def test_ranch99_discovery_normalize_product_url() -> None:
    url = "https://www.99ranch.com/product-details/1615424/8899/078895126389?foo=bar#frag"
    assert (
        Ranch99Discovery._normalize_product_url(url)
        == "https://www.99ranch.com/product-details/1615424/8899/078895126389"
    )
    assert Ranch99Discovery._normalize_product_url("https://evil.com/product-details/1/2/3") is None
    assert Ranch99Discovery._normalize_product_url("https://www.99ranch.com/categories/sale") is None
