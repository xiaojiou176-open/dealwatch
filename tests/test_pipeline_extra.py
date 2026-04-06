from datetime import datetime, timezone

import pytest

from dealwatch.core.models import Offer, PriceContext, SkipReason
from dealwatch.core.pipeline import MonitoringPipeline
from dealwatch.infra.config import Settings
from dealwatch.stores.base_adapter import BaseStoreAdapter, SkipParse


class _DummyRepo:
    def __init__(self, raise_on_get: bool = False) -> None:
        self.raise_on_get = raise_on_get
        self.upsert_calls = 0
        self.insert_calls = 0
        self.series: list[float] = [10.0, 9.5, 10.2, 9.8, 10.1, 9.9, 10.0, 10.3]

    async def get_last_price(
        self,
        store_id: str,
        product_key: str,
        context_hash: str,
        max_age_days: int | None = None,
    ):
        if self.raise_on_get:
            raise RuntimeError("db failure")
        return 10.0

    async def get_historical_low(self, store_id: str, product_key: str, context_hash: str):
        return 8.0

    async def get_price_series(
        self,
        store_id: str,
        product_key: str,
        context_hash: str,
        lookback_days: int = 90,
        limit: int = 30,
    ) -> list[float]:
        return list(self.series)[:limit]

    async def upsert_product(self, offer: Offer) -> None:
        self.upsert_calls += 1

    async def insert_price_point(self, offer: Offer) -> None:
        self.insert_calls += 1


class _Adapter(BaseStoreAdapter):
    store_id = "dummy"
    base_url = "https://example.com"

    def __init__(self, offer: Offer | None, settings: Settings, mode: str = "ok") -> None:
        super().__init__(client=object(), settings=settings)
        self._offer = offer
        self._mode = mode

    async def discover_deals(self) -> list[str]:
        if self._mode == "discover_fail":
            raise RuntimeError("discover failed")
        if self._mode == "empty":
            return []
        return ["https://example.com/p1"]

    async def parse_product(self, url: str) -> Offer | None:
        if self._mode == "skip":
            raise SkipParse(SkipReason.OUT_OF_STOCK)
        if self._mode == "blocked":
            raise StopAsyncIteration("IP_RESTRICTED:https://example.com/p1")
        return self._offer


def _build_offer(price: float) -> Offer:
    return Offer(
        store_id="dummy",
        product_key="p1",
        title="Test Product",
        url="https://example.com/p1",
        price=price,
        original_price=None,
        fetch_at=datetime(2026, 1, 18, 12, 0, 0, tzinfo=timezone.utc),
        context=PriceContext(region="00000"),
        unit_price_info={},
    )


@pytest.mark.asyncio
async def test_pipeline_discover_fail() -> None:
    settings = Settings()
    repo = _DummyRepo()
    adapter = _Adapter(_build_offer(9.0), settings, mode="discover_fail")
    pipeline = MonitoringPipeline(repo=repo, client=object(), settings=settings)

    deals = await pipeline.run_store(adapter)
    assert deals == []
    assert pipeline.last_stats is not None
    assert pipeline.last_stats.error_count == 1


@pytest.mark.asyncio
async def test_pipeline_empty_discovery() -> None:
    settings = Settings()
    repo = _DummyRepo()
    adapter = _Adapter(_build_offer(9.0), settings, mode="empty")
    pipeline = MonitoringPipeline(repo=repo, client=object(), settings=settings)

    deals = await pipeline.run_store(adapter)
    assert deals == []
    assert pipeline.last_stats is not None
    assert pipeline.last_stats.discovered_count == 0


@pytest.mark.asyncio
async def test_pipeline_skip_parse() -> None:
    settings = Settings()
    repo = _DummyRepo()
    adapter = _Adapter(_build_offer(9.0), settings, mode="skip")
    pipeline = MonitoringPipeline(repo=repo, client=object(), settings=settings)

    deals = await pipeline.run_store(adapter)
    assert deals == []
    assert pipeline.last_stats is not None
    assert pipeline.last_stats.skipped_count == 1


@pytest.mark.asyncio
async def test_pipeline_validation_failure() -> None:
    settings = Settings()
    repo = _DummyRepo()
    adapter = _Adapter(_build_offer(0.0), settings, mode="ok")
    pipeline = MonitoringPipeline(repo=repo, client=object(), settings=settings)

    deals = await pipeline.run_store(adapter)
    assert deals == []
    assert pipeline.last_stats is not None
    assert pipeline.last_stats.error_count >= 1


@pytest.mark.asyncio
async def test_pipeline_blocked_stop() -> None:
    settings = Settings()
    repo = _DummyRepo()
    adapter = _Adapter(_build_offer(9.0), settings, mode="blocked")
    pipeline = MonitoringPipeline(repo=repo, client=object(), settings=settings)

    deals = await pipeline.run_store(adapter)
    assert deals == []
    assert pipeline.last_stats is not None
    assert "IP_RESTRICTED" in pipeline.last_error_snippet


@pytest.mark.asyncio
async def test_pipeline_anomaly_detection_skips_persist() -> None:
    settings = Settings()
    repo = _DummyRepo()
    repo.series = [9.8, 10.1, 10.2, 9.9, 10.0, 10.3, 9.7, 10.4]
    adapter = _Adapter(_build_offer(1.0), settings, mode="ok")
    pipeline = MonitoringPipeline(repo=repo, client=object(), settings=settings)

    deals = await pipeline.run_store(adapter)
    assert deals == []
    assert repo.upsert_calls == 0
    assert repo.insert_calls == 0


@pytest.mark.asyncio
async def test_pipeline_anomaly_detection_mark_only() -> None:
    settings = Settings()
    settings.ANOMALY_MARK_ONLY = True
    repo = _DummyRepo()
    repo.series = [9.8, 10.1, 10.2, 9.9, 10.0, 10.3, 9.7, 10.4]
    adapter = _Adapter(_build_offer(1.0), settings, mode="ok")
    pipeline = MonitoringPipeline(repo=repo, client=object(), settings=settings)

    deals = await pipeline.run_store(adapter)
    assert len(deals) == 1
    assert deals[0].anomaly_reason is not None
    assert repo.upsert_calls == 1
    assert repo.insert_calls == 1
