import gzip

import pytest

from dealwatch.stores.target.discovery import TargetDiscovery


class _FakeResponse:
    def __init__(self, text: str, content: bytes | None = None) -> None:
        self.text = text
        self.content = text.encode("utf-8") if content is None else content

    def raise_for_status(self) -> None:
        return None


class _FakeClient:
    def __init__(self, responses: list[_FakeResponse]) -> None:
        self._responses = responses
        self._index = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url: str) -> _FakeResponse:
        response = self._responses[self._index]
        self._index += 1
        return response


@pytest.mark.asyncio
async def test_target_discovery_uses_pdp_sitemaps(monkeypatch) -> None:
    index_xml = """
    <sitemapindex>
      <sitemap><loc>https://www.target.com/pdp/sitemap_00-0001.xml.gz</loc></sitemap>
      <sitemap><loc>https://www.target.com/pdp/sitemap_00-0002.xml.gz</loc></sitemap>
    </sitemapindex>
    """
    product_xml = """
    <urlset>
      <url><loc>https://www.target.com/p/utz-ripples-original-potato-chips-7-75oz/-/A-13202943?preselect=2786</loc></url>
      <url><loc>https://www.target.com/p/-/A-13202943</loc></url>
      <url><loc>https://www.target.com/p/fritos-original-corn-chips-9-25oz/-/A-14939185</loc></url>
      <url><loc>https://evil.com/p/-/A-12345678</loc></url>
    </urlset>
    """
    gzipped_xml = gzip.compress(product_xml.encode("utf-8"))
    monkeypatch.setattr(
        "dealwatch.stores.target.discovery.httpx.AsyncClient",
        lambda **kwargs: _FakeClient(
            [
                _FakeResponse(index_xml),
                _FakeResponse(product_xml, content=gzipped_xml),
                _FakeResponse(product_xml),
            ]
        ),
    )

    discovery = TargetDiscovery()
    links = await discovery.discover_deals()

    assert links == [
        "https://www.target.com/p/-/A-13202943",
        "https://www.target.com/p/-/A-14939185",
    ]


def test_target_discovery_normalize_product_url() -> None:
    assert (
        TargetDiscovery._normalize_product_url(
            "https://www.target.com/p/utz-ripples-original-potato-chips-7-75oz/-/A-13202943?preselect=2786#reviews"
        )
        == "https://www.target.com/p/-/A-13202943"
    )
    assert TargetDiscovery._normalize_product_url("https://www.target.com/c/chips-snacks/-/N-5xsnx") is None
    assert TargetDiscovery._normalize_product_url("https://evil.com/p/-/A-13202943") is None
