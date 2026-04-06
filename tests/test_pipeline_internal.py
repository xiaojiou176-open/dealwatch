from datetime import datetime, timezone

import pytest

from dealwatch.core.models import Offer, PriceContext
from dealwatch.core.pipeline import MonitoringPipeline
from dealwatch.infra.config import Settings
from dealwatch.stores.base_adapter import BaseStoreAdapter


class _DummyRepo:
    async def get_last_price(
        self,
        store_id: str,
        product_key: str,
        context_hash: str,
        max_age_days: int | None = None,
    ):
        return 10.0

    async def get_historical_low(self, store_id: str, product_key: str, context_hash: str):
        return 9.0

    async def get_price_series(
        self,
        store_id: str,
        product_key: str,
        context_hash: str,
        lookback_days: int = 90,
        limit: int = 30,
    ) -> list[float]:
        return [9.8, 10.1, 10.2, 9.9, 10.0, 10.3, 9.7, 10.4]

    async def upsert_product(self, offer: Offer) -> None:
        return None

    async def insert_price_point(self, offer: Offer) -> None:
        return None


class _Adapter(BaseStoreAdapter):
    store_id = "dummy"
    base_url = "https://example.com"

    def __init__(self, offers: list[Offer | None], settings: Settings) -> None:
        super().__init__(client=object(), settings=settings)
        self._offers = offers

    async def discover_deals(self) -> list[str]:
        return [f"https://example.com/{idx}" for idx in range(len(self._offers))]

    async def parse_product(self, url: str):
        index = int(url.rsplit("/", 1)[-1])
        return self._offers[index]


def _offer(price: float) -> Offer:
    return Offer(
        store_id="dummy",
        product_key="p1",
        title="Valid Title",
        url="https://example.com",
        price=price,
        original_price=None,
        fetch_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        context=PriceContext(region="00000"),
        unit_price_info={},
    )


def test_pipeline_progress_marks() -> None:
    marks = MonitoringPipeline._build_progress_marks(10)
    assert min(marks) >= 1
    assert 10 in marks
    assert len(marks) <= 5


def test_pipeline_extract_blocked_url() -> None:
    url = MonitoringPipeline._extract_blocked_url("IP_RESTRICTED:https://example.com")
    assert url == "https://example.com"

    assert MonitoringPipeline._extract_blocked_url("other") is None


@pytest.mark.asyncio
async def test_pipeline_skips_none_offers() -> None:
    settings = Settings(ANOMALY_ENABLED=False)
    repo = _DummyRepo()
    offers = [None, _offer(9.0)]
    adapter = _Adapter(offers, settings)
    pipeline = MonitoringPipeline(repo=repo, client=object(), settings=settings)

    deals = await pipeline.run_store(adapter)
    assert len(deals) == 1
    assert pipeline.last_stats is not None
    assert pipeline.last_stats.parsed_count == 1
