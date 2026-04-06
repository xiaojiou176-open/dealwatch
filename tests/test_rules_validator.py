from dealwatch.core.models import AnomalyReason, Offer, PriceContext
from dealwatch.core.rules import RulesEngine
from dealwatch.core.validator import DataValidator
from datetime import datetime, timezone


def _offer(price: float, title: str = "Valid Title", original_price=None) -> Offer:
    return Offer(
        store_id="weee",
        product_key="p1",
        title=title,
        url="https://example.com",
        price=price,
        original_price=original_price,
        fetch_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        context=PriceContext(region="00000"),
        unit_price_info={},
    )


def test_rules_engine_drop_thresholds() -> None:
    engine = RulesEngine(min_drop_amount=0.10, min_drop_pct=2.0)
    offer = _offer(9.90)
    assert engine.analyze_drop(offer, last_price=10.00) is None

    offer = _offer(9.79)
    deal = engine.analyze_drop(offer, last_price=10.00)
    assert deal is not None
    assert deal.drop_amount == 0.21
    assert deal.drop_pct == 2.1


def test_rules_engine_historical_low_flag() -> None:
    engine = RulesEngine()
    offer = _offer(5.00)
    deal = engine.analyze_drop(offer, last_price=6.00, historical_low=4.00)
    assert deal is not None
    assert deal.is_new_low is False

    deal = engine.analyze_drop(
        offer,
        last_price=6.00,
        historical_low=4.00,
        anomaly_reason=AnomalyReason.IQR,
    )
    assert deal is not None
    assert deal.anomaly_reason == AnomalyReason.IQR


def test_validator_original_price_lt_price() -> None:
    validator = DataValidator()
    offer = _offer(5.00, original_price=4.00)
    assert validator.validate_offer(offer) is False


def test_validator_title_tokens_and_chars() -> None:
    validator = DataValidator(min_title_length=3)
    offer = _offer(5.00, title="n/a product")
    assert validator.validate_offer(offer) is False

    bad = _offer(5.00, title="Bad\uFFFDTitle")
    assert validator.validate_offer(bad) is False

    control = _offer(5.00, title="Bad\u0001Title")
    assert validator.validate_offer(control) is False


def test_validator_price_range() -> None:
    validator = DataValidator(min_price=0.5, max_price=10.0)
    assert validator.validate_offer(_offer(0.4)) is False
    assert validator.validate_offer(_offer(10.1)) is False
    assert validator.validate_offer(_offer(1.0)) is True


def test_validator_unit_price_info_guard() -> None:
    validator = DataValidator()
    offer = _offer(5.0)
    offer.unit_price_info = {"": 1.0}
    assert validator.validate_offer(offer) is False

    offer = _offer(5.0)
    offer.unit_price_info = {"unit": None}
    assert validator.validate_offer(offer) is False


def test_rules_engine_anomaly_detection() -> None:
    engine = RulesEngine(
        anomaly_min_samples=5,
        anomaly_iqr_multiplier=1.5,
        anomaly_zscore_threshold=3.0,
    )
    history = [10.0, 10.2, 9.9, 10.1, 10.3, 9.8, 10.0]
    is_anomaly, reason = engine.is_anomalous_price(1.0, history)
    assert is_anomaly is True
    assert reason in (AnomalyReason.IQR, AnomalyReason.ZSCORE)

    is_anomaly, reason = engine.is_anomalous_price(10.0, history[:2])
    assert is_anomaly is False
    assert reason is None


def test_rules_engine_zero_variance_guard() -> None:
    engine = RulesEngine(
        anomaly_min_samples=5,
        anomaly_zero_var_pct=0.3,
        anomaly_zero_var_abs=2.0,
    )
    history = [10.0] * 6
    is_anomaly, reason = engine.is_anomalous_price(14.0, history)
    assert is_anomaly is True
    assert reason == AnomalyReason.ZERO_VAR

    is_anomaly, reason = engine.is_anomalous_price(11.0, history)
    assert is_anomaly is False
    assert reason is None
