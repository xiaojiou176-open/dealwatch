from __future__ import annotations

from enum import Enum


class WatchTaskStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    BLOCKED = "blocked"
    NEEDS_ATTENTION = "needs_attention"


class TaskRunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"


class RunTrigger(str, Enum):
    SCHEDULER = "scheduler"
    MANUAL = "manual"
    BOOTSTRAP = "bootstrap"


class ThresholdType(str, Enum):
    PRICE_BELOW = "price_below"
    PRICE_DROP_PERCENT = "price_drop_percent"
    EFFECTIVE_PRICE_BELOW = "effective_price_below"


class ResolutionStatus(str, Enum):
    RESOLVED = "resolved"
    UNSUPPORTED = "unsupported"
    BLOCKED = "blocked"


class CashbackRateType(str, Enum):
    PERCENT = "percent"
    FLAT = "flat"


class DeliveryStatus(str, Enum):
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    BOUNCED = "bounced"
    FAILED = "failed"


class FailureKind(str, Enum):
    FETCH_FAILED = "fetch_failed"
    BLOCKED = "blocked"
    DELIVERY_FAILED = "delivery_failed"
    OVERLAP_GUARD = "overlap_guard"
    UNEXPECTED_RUNTIME_ERROR = "unexpected_runtime_error"
