from datetime import datetime, timezone

from dealwatch.core.artifacts import ArtifactManager
from dealwatch.core.models import Offer, PriceContext
from dealwatch.core.validator import DataValidator


def _build_offer(price: float, title: str = "Valid Title") -> Offer:
    return Offer(
        store_id="weee",
        product_key="p1",
        title=title,
        url="https://example.com/p1",
        price=price,
        original_price=None,
        fetch_at=datetime(2026, 1, 18, 12, 0, 0, tzinfo=timezone.utc),
        context=PriceContext(region="00000"),
        unit_price_info={},
    )


def test_clip_text_truncates() -> None:
    manager = ArtifactManager()
    long_text = "x" * 1000
    clipped = manager._clip_text(long_text)
    assert len(clipped) == 500


def test_validator_rejects_bad_price() -> None:
    validator = DataValidator(min_price=0.01)
    offer = _build_offer(0.0)
    assert validator.validate_offer(offer) is False


def test_validator_rejects_bad_title() -> None:
    validator = DataValidator(min_title_length=6)
    offer = _build_offer(1.99, title="bad")
    assert validator.validate_offer(offer) is False
