import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from dealwatch.core.artifacts import ArtifactManager
from dealwatch.core.models import AnomalyReason, DealEvent, Offer, PriceContext, RunStats
from dealwatch.core.pipeline import MonitoringPipeline
from dealwatch.core.rules import RulesEngine
from dealwatch.infra.config import Settings
from dealwatch.legacy.db_repo import DatabaseRepository
from dealwatch.infra.obs.health_check import HealthMonitor
from dealwatch.stores.base_adapter import BaseStoreAdapter


def _build_offer(price: float) -> Offer:
    return Offer(
        store_id="test_store",
        product_key="product-1",
        title="Test Product",
        url="https://example.com/product-1",
        price=price,
        original_price=None,
        fetch_at=datetime(2026, 1, 18, 12, 0, 0, tzinfo=timezone.utc),
        context=PriceContext(region="00000"),
        unit_price_info={"unit": "lb", "quantity": 1.0},
    )


def test_rules_engine_exact_threshold() -> None:
    engine = RulesEngine()
    offer = _build_offer(9.90)
    deal = engine.analyze_drop(offer, last_price=10.00)
    assert deal is not None
    assert deal.drop_amount == 0.10
    assert deal.drop_pct == 1.0


def test_rules_engine_small_drop_filtered() -> None:
    engine = RulesEngine()
    offer = _build_offer(9.96)
    deal = engine.analyze_drop(offer, last_price=10.00)
    assert deal is None


def test_rules_engine_price_increase_filtered() -> None:
    engine = RulesEngine()
    offer = _build_offer(10.01)
    deal = engine.analyze_drop(offer, last_price=10.00)
    assert deal is None


def test_rules_engine_price_equal_filtered() -> None:
    engine = RulesEngine()
    offer = _build_offer(10.00)
    deal = engine.analyze_drop(offer, last_price=10.00)
    assert deal is None


def test_rules_engine_last_price_none() -> None:
    engine = RulesEngine()
    offer = _build_offer(9.50)
    deal = engine.analyze_drop(offer, last_price=None)
    assert deal is None


def test_rules_engine_last_price_zero() -> None:
    engine = RulesEngine()
    offer = _build_offer(1.00)
    deal = engine.analyze_drop(offer, last_price=0.0)
    assert deal is None


def test_rules_engine_drop_pct_below_threshold() -> None:
    engine = RulesEngine()
    offer = _build_offer(9.92)
    deal = engine.analyze_drop(offer, last_price=10.00)
    assert deal is None


def test_rules_engine_new_low_flag() -> None:
    engine = RulesEngine()
    offer = _build_offer(8.00)
    deal = engine.analyze_drop(offer, last_price=10.00, historical_low=8.50)
    assert deal is not None
    assert deal.is_new_low is True


def test_offer_roundtrip() -> None:
    offer = _build_offer(3.45)
    payload = offer.to_dict()
    restored = Offer.from_dict(payload)
    assert restored == offer


def test_deal_event_roundtrip() -> None:
    offer = _build_offer(8.50)
    deal = DealEvent(
        offer=offer,
        last_price=10.00,
        drop_amount=1.50,
        drop_pct=15.0,
        is_new_low=False,
        anomaly_reason=AnomalyReason.IQR,
    )
    payload = deal.to_dict()
    restored = DealEvent.from_dict(payload)
    assert restored == deal


class _DummyAdapter(BaseStoreAdapter):
    store_id = "dummy"
    base_url = "https://example.com"

    def __init__(self, offer: Offer, settings: Settings) -> None:
        super().__init__(client=object(), settings=settings)
        self._offer = offer

    async def discover_deals(self) -> list[str]:
        return ["https://example.com/product-1"]

    async def parse_product(self, url: str) -> Offer | None:
        return self._offer


class _DummyRepo:
    def __init__(self, raise_on_get: bool) -> None:
        self.raise_on_get = raise_on_get
        self.upsert_calls = 0
        self.insert_calls = 0

    async def get_last_price(
        self,
        store_id: str,
        product_key: str,
        context_hash: str,
        max_age_days: int | None = None,
    ) -> float | None:
        if self.raise_on_get:
            raise RuntimeError("db failure")
        return 10.00

    async def get_historical_low(
        self,
        store_id: str,
        product_key: str,
        context_hash: str,
    ) -> float | None:
        return 9.50

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
        self.upsert_calls += 1

    async def insert_price_point(self, offer: Offer) -> None:
        self.insert_calls += 1


@pytest.mark.asyncio
async def test_pipeline_handles_db_failure() -> None:
    settings = Settings()
    offer = _build_offer(9.50)
    adapter = _DummyAdapter(offer, settings)
    repo = _DummyRepo(raise_on_get=True)

    pipeline = MonitoringPipeline(repo=repo, client=object(), settings=settings)
    deals = await pipeline.run_store(adapter)

    assert deals == []
    assert pipeline.last_stats is not None
    assert pipeline.last_stats.error_count == 1


@pytest.mark.asyncio
async def test_pipeline_success_path() -> None:
    settings = Settings(ANOMALY_ENABLED=False)
    offer = _build_offer(9.00)
    adapter = _DummyAdapter(offer, settings)
    repo = _DummyRepo(raise_on_get=False)

    pipeline = MonitoringPipeline(repo=repo, client=object(), settings=settings)
    deals = await pipeline.run_store(adapter)

    assert len(deals) == 1
    assert repo.upsert_calls == 1
    assert repo.insert_calls == 1


def test_artifacts_total_checked_override(tmp_path) -> None:
    offer = _build_offer(3.20)
    deal = DealEvent(
        offer=offer,
        last_price=4.00,
        drop_amount=0.80,
        drop_pct=20.0,
        is_new_low=False,
    )
    manager = ArtifactManager(base_dir=tmp_path)
    json_path = manager.save_deals([deal], "test", total_checked=42)

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["total_checked"] == 42
    assert payload["confirmed_count"] == 1


def test_health_monitor_escapes_html() -> None:
    stats = RunStats(
        store_id="dummy",
        start_time=datetime(2026, 1, 18, 12, 0, 0, tzinfo=timezone.utc),
        discovered_count=10,
        parsed_count=8,
        error_count=1,
        confirmed_deals_count=2,
        skipped_count=1,
    )
    details = HealthMonitor._build_details(
        stats=stats,
        issue_type="PARSE_RATE_LOW",
        failed_urls=["https://example.com/?q=<bad>"],
        error_snippet="boom <script>",
        artifact_context="",
    )

    assert "<script>" not in details
    assert "&lt;script&gt;" in details
    assert "&lt;bad&gt;" in details


@pytest.mark.asyncio
async def test_db_legacy_fallback(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("dealwatch.legacy.db_repo.settings.ENABLE_LEGACY_FALLBACK", True)
    db_path = tmp_path / "dealwatch.db"
    repo = DatabaseRepository(db_path)
    await repo.initialize()
    context_hash = PriceContext(region="00000").get_hash()

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            INSERT INTO products
                (store_id, product_key, url, title, last_updated)
            VALUES (?, ?, ?, ?, ?);
            """,
            ("weee", "legacy-product", "https://example.com/legacy", "Legacy Product", datetime.now(timezone.utc).isoformat()),
        )
        conn.execute(
            """
            INSERT INTO price_history
                (store_id, product_key, price, original_price, context_hash, timestamp)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            ("legacy", "legacy-product", 9.99, None, context_hash, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()

    last_price = await repo.get_last_price("weee", "legacy-product", context_hash)
    assert last_price == 9.99


@pytest.mark.asyncio
async def test_db_legacy_fallback_blocked_without_unique_mapping(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("dealwatch.legacy.db_repo.settings.ENABLE_LEGACY_FALLBACK", True)
    db_path = tmp_path / "dealwatch.db"
    repo = DatabaseRepository(db_path)
    await repo.initialize()
    context_hash = PriceContext(region="00000").get_hash()

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            INSERT INTO price_history
                (store_id, product_key, price, original_price, context_hash, timestamp)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            ("legacy", "legacy-only", 5.55, None, context_hash, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()

    last_price = await repo.get_last_price("weee", "legacy-only", context_hash)
    assert last_price is None


@pytest.mark.asyncio
async def test_db_historical_low(tmp_path) -> None:
    db_path = tmp_path / "dealwatch.db"
    repo = DatabaseRepository(db_path)
    await repo.initialize()
    context_hash = PriceContext(region="00000").get_hash()

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            INSERT INTO price_history
                (store_id, product_key, price, original_price, context_hash, timestamp)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            ("weee", "low-product", 9.99, None, context_hash, datetime.now(timezone.utc).isoformat()),
        )
        conn.execute(
            """
            INSERT INTO price_history
                (store_id, product_key, price, original_price, context_hash, timestamp)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            ("weee", "low-product", 7.50, None, context_hash, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()

    low_price = await repo.get_historical_low("weee", "low-product", context_hash)
    assert low_price == 7.50


@pytest.mark.asyncio
async def test_cleanup_keeps_latest_when_low_is_outside_window(tmp_path) -> None:
    db_path = tmp_path / "dealwatch.db"
    repo = DatabaseRepository(db_path)
    await repo.initialize()
    context_hash = PriceContext(region="00000").get_hash()

    now = datetime.now(timezone.utc)
    rows = [
        ("weee", "cleanup-product", 10.00, None, context_hash, (now - timedelta(days=10)).isoformat()),
        ("weee", "cleanup-product", 11.00, None, context_hash, (now - timedelta(days=9)).isoformat()),
        ("weee", "cleanup-product", 12.00, None, context_hash, (now - timedelta(days=8)).isoformat()),
    ]

    conn = sqlite3.connect(str(db_path))
    try:
        conn.executemany(
            """
            INSERT INTO price_history
                (store_id, product_key, price, original_price, context_hash, timestamp)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            rows,
        )
        conn.commit()
    finally:
        conn.close()

    await repo.cleanup_price_history(older_than_days=1)

    last_price = await repo.get_last_price("weee", "cleanup-product", context_hash)
    low_price = await repo.get_historical_low("weee", "cleanup-product", context_hash)

    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.execute(
            """
            SELECT COUNT(*)
            FROM price_history
            WHERE store_id = ? AND product_key = ? AND context_hash = ?;
            """,
            ("weee", "cleanup-product", context_hash),
        )
        remaining = cursor.fetchone()[0]
    finally:
        conn.close()

    assert last_price == 12.00
    assert low_price == 10.00
    assert remaining == 2
