from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Final


#########################################################
# Type Aliases
#########################################################
UnitPriceInfo = dict[str, str | float | int]


#########################################################
# Enums
#########################################################
class SkipReason(str, Enum):
    OUT_OF_STOCK = "out_of_stock"


class AnomalyReason(str, Enum):
    IQR = "iqr"
    ZSCORE = "zscore"
    ZERO_VAR = "zero_var"


#########################################################
# Helpers
#########################################################
_HASH_TRUNCATE: Final[int] = 8


def _parse_iso_datetime(raw: str) -> datetime:
    return datetime.fromisoformat(raw)


def _require_str(data: dict[str, object], key: str) -> str:
    value = str(data.get(key, "")).strip()
    if not value:
        raise ValueError(f"{key} is required")
    return value


def _require_float(data: dict[str, object], key: str) -> float:
    raw = data.get(key)
    if raw is None or raw == "":
        raise ValueError(f"{key} is required")
    return float(raw)


def _parse_optional_enum(
    enum_type: type[Enum],
    raw_value: object,
    field_name: str,
) -> Enum | None:
    if raw_value in (None, ""):
        return None
    try:
        return enum_type(str(raw_value))
    except ValueError as exc:
        raise ValueError(f"{field_name} is invalid") from exc


#########################################################
# PriceContext
#########################################################
@dataclass(slots=True)
class PriceContext:
    region: str
    currency: str = "USD"
    is_member: bool = False

    def get_hash(self) -> str:
        raw = f"{self.region}|{self.currency}|{self.is_member}"
        digest = hashlib.md5(raw.encode("utf-8")).hexdigest()
        return digest[:_HASH_TRUNCATE]

    def to_dict(self) -> dict[str, str | bool]:
        return {
            "region": self.region,
            "currency": self.currency,
            "is_member": self.is_member,
        }

    @staticmethod
    def from_dict(data: dict[str, object]) -> "PriceContext":
        region = _require_str(data, "region")

        currency = str(data.get("currency", "USD")).strip() or "USD"
        is_member = bool(data.get("is_member", False))

        return PriceContext(
            region=region,
            currency=currency,
            is_member=is_member,
        )


#########################################################
# Offer
#########################################################
@dataclass(slots=True)
class Offer:
    store_id: str
    product_key: str
    title: str
    url: str
    price: float
    original_price: float | None
    fetch_at: datetime
    context: PriceContext
    unit_price_info: UnitPriceInfo = field(default_factory=dict)

    def get_deal_id(self) -> str:
        return f"{self.store_id}:{self.product_key}"

    def to_dict(self) -> dict[str, object]:
        return {
            "store_id": self.store_id,
            "product_key": self.product_key,
            "deal_id": self.get_deal_id(),
            "title": self.title,
            "url": self.url,
            "price": self.price,
            "original_price": self.original_price,
            "fetch_at": self.fetch_at.isoformat(),
            "context": self.context.to_dict(),
            "unit_price_info": dict(self.unit_price_info),
        }

    @staticmethod
    def from_dict(data: dict[str, object]) -> "Offer":
        context_raw = data.get("context")
        if not isinstance(context_raw, dict):
            raise ValueError("Offer.context is required and must be a dict")

        fetch_at_raw = data.get("fetch_at")
        if fetch_at_raw is None:
            raise ValueError("Offer.fetch_at is required")

        original_price_raw = data.get("original_price")
        original_price = (
            None
            if original_price_raw in (None, "")
            else float(original_price_raw)
        )

        unit_price_info_raw = data.get("unit_price_info", {})
        if not isinstance(unit_price_info_raw, dict):
            raise ValueError("Offer.unit_price_info must be a dict")

        return Offer(
            store_id=_require_str(data, "store_id"),
            product_key=_require_str(data, "product_key"),
            title=_require_str(data, "title"),
            url=_require_str(data, "url"),
            price=_require_float(data, "price"),
            original_price=original_price,
            fetch_at=_parse_iso_datetime(str(fetch_at_raw)),
            context=PriceContext.from_dict(context_raw),
            unit_price_info=dict(unit_price_info_raw),
        )


#########################################################
# DealEvent
#########################################################
@dataclass(slots=True)
class DealEvent:
    offer: Offer
    last_price: float
    drop_amount: float
    drop_pct: float
    is_new_low: bool
    anomaly_reason: AnomalyReason | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "offer": self.offer.to_dict(),
            "last_price": self.last_price,
            "drop_amount": self.drop_amount,
            "drop_pct": self.drop_pct,
            "is_new_low": self.is_new_low,
            "anomaly_reason": self.anomaly_reason.value if self.anomaly_reason else None,
        }

    @staticmethod
    def from_dict(data: dict[str, object]) -> "DealEvent":
        offer_raw = data.get("offer")
        if not isinstance(offer_raw, dict):
            raise ValueError("DealEvent.offer is required and must be a dict")

        return DealEvent(
            offer=Offer.from_dict(offer_raw),
            last_price=_require_float(data, "last_price"),
            drop_amount=_require_float(data, "drop_amount"),
            drop_pct=_require_float(data, "drop_pct"),
            is_new_low=bool(data.get("is_new_low", False)),
            anomaly_reason=_parse_optional_enum(
                AnomalyReason,
                data.get("anomaly_reason"),
                "anomaly_reason",
            ),
        )


#########################################################
# Run Stats
#########################################################
@dataclass(slots=True)
class RunStats:
    store_id: str
    start_time: datetime
    discovered_count: int
    parsed_count: int
    error_count: int
    confirmed_deals_count: int
    skipped_count: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "store_id": self.store_id,
            "start_time": self.start_time.isoformat(),
            "discovered_count": self.discovered_count,
            "parsed_count": self.parsed_count,
            "error_count": self.error_count,
            "confirmed_deals_count": self.confirmed_deals_count,
            "skipped_count": self.skipped_count,
        }

    @staticmethod
    def from_dict(data: dict[str, object]) -> "RunStats":
        return RunStats(
            store_id=_require_str(data, "store_id"),
            start_time=_parse_iso_datetime(_require_str(data, "start_time")),
            discovered_count=int(data.get("discovered_count", 0)),
            parsed_count=int(data.get("parsed_count", 0)),
            error_count=int(data.get("error_count", 0)),
            confirmed_deals_count=int(data.get("confirmed_deals_count", 0)),
            skipped_count=int(data.get("skipped_count", 0)),
        )
