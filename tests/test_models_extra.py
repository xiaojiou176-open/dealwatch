from datetime import datetime, timezone

import pytest

from dealwatch.core.models import AnomalyReason, DealEvent, Offer, PriceContext, RunStats


def test_price_context_hash_stable() -> None:
    ctx1 = PriceContext(region="94538", currency="USD", is_member=False)
    ctx2 = PriceContext(region="94538", currency="USD", is_member=False)
    ctx3 = PriceContext(region="94538", currency="USD", is_member=True)

    assert ctx1.get_hash() == ctx2.get_hash()
    assert ctx1.get_hash() != ctx3.get_hash()
    assert len(ctx1.get_hash()) == 8


def test_offer_from_dict_missing_fields() -> None:
    with pytest.raises(ValueError):
        Offer.from_dict({"store_id": "weee"})

    with pytest.raises(ValueError):
        Offer.from_dict(
            {
                "store_id": "weee",
                "product_key": "p1",
                "title": "Test",
                "url": "https://example.com",
                "price": 1.0,
                "fetch_at": "2026-01-01T00:00:00+00:00",
                "context": "bad",
            }
        )


def test_offer_from_dict_unit_price_type_guard() -> None:
    payload = {
        "store_id": "weee",
        "product_key": "p1",
        "title": "Test",
        "url": "https://example.com",
        "price": 1.0,
        "fetch_at": "2026-01-01T00:00:00+00:00",
        "context": {"region": "00000"},
        "unit_price_info": "bad",
    }
    with pytest.raises(ValueError):
        Offer.from_dict(payload)


def test_deal_event_from_dict_guard() -> None:
    with pytest.raises(ValueError):
        DealEvent.from_dict({})

    offer = Offer(
        store_id="weee",
        product_key="p1",
        title="Test",
        url="https://example.com",
        price=1.0,
        original_price=None,
        fetch_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        context=PriceContext(region="00000"),
        unit_price_info={},
    )
    deal = DealEvent(
        offer=offer,
        last_price=2.0,
        drop_amount=1.0,
        drop_pct=50.0,
        is_new_low=False,
        anomaly_reason=AnomalyReason.IQR,
    )
    payload = deal.to_dict()
    payload["anomaly_reason"] = "bad"
    with pytest.raises(ValueError):
        DealEvent.from_dict(payload)


def test_run_stats_roundtrip_defaults() -> None:
    stats = RunStats(
        store_id="weee",
        start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        discovered_count=1,
        parsed_count=1,
        error_count=0,
        confirmed_deals_count=0,
    )
    payload = stats.to_dict()
    restored = RunStats.from_dict(payload)
    assert restored.skipped_count == 0
