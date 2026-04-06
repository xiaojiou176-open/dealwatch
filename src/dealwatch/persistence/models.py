from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dealwatch.persistence.base import Base


def _uuid() -> str:
    return str(uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="owner")
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class UserPreference(Base):
    __tablename__ = "user_preferences"

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    timezone: Mapped[str] = mapped_column(String(64), default="America/Los_Angeles")
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    default_zip_code: Mapped[str] = mapped_column(String(32), default="00000")
    default_check_interval_minutes: Mapped[int] = mapped_column(Integer, default=360)
    default_email_recipient: Mapped[str] = mapped_column(String(255))
    notification_cooldown_minutes: Mapped[int] = mapped_column(Integer, default=240)
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class WatchTarget(Base):
    __tablename__ = "watch_targets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    submitted_url: Mapped[str] = mapped_column(Text)
    normalized_url: Mapped[str] = mapped_column(Text, index=True)
    store_key: Mapped[str] = mapped_column(String(64))
    product_url: Mapped[str] = mapped_column(Text)
    target_type: Mapped[str] = mapped_column(String(32), default="product_url")
    resolution_status: Mapped[str] = mapped_column(String(32), default="resolved")
    last_resolution_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class WatchTask(Base):
    __tablename__ = "watch_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    watch_target_id: Mapped[str] = mapped_column(String(36), ForeignKey("watch_targets.id", ondelete="CASCADE"), index=True)
    zip_code: Mapped[str] = mapped_column(String(32), default="00000")
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    cadence_minutes: Mapped[int] = mapped_column(Integer, default=360)
    run_mode: Mapped[str] = mapped_column(String(32), default="scheduled")
    threshold_type: Mapped[str] = mapped_column(String(64), default="price_drop_percent")
    threshold_value: Mapped[float] = mapped_column(Float, default=5.0)
    cooldown_minutes: Mapped[int] = mapped_column(Integer, default=720)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    health_status: Mapped[str] = mapped_column(String(32), default="healthy", index=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    backoff_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure_kind: Mapped[str | None] = mapped_column(String(64), nullable=True)
    manual_intervention_required: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    target: Mapped[WatchTarget] = relationship()


class WatchGroup(Base):
    __tablename__ = "watch_groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    zip_code: Mapped[str] = mapped_column(String(32), default="00000")
    cadence_minutes: Mapped[int] = mapped_column(Integer, default=360)
    threshold_type: Mapped[str] = mapped_column(String(64), default="price_below")
    threshold_value: Mapped[float] = mapped_column(Float, default=0.0)
    cooldown_minutes: Mapped[int] = mapped_column(Integer, default=240)
    recipient_email: Mapped[str] = mapped_column(String(255))
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    health_status: Mapped[str] = mapped_column(String(32), default="healthy", index=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    backoff_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure_kind: Mapped[str | None] = mapped_column(String(64), nullable=True)
    manual_intervention_required: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class WatchGroupMember(Base):
    __tablename__ = "watch_group_members"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    watch_group_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("watch_groups.id", ondelete="CASCADE"),
        index=True,
    )
    watch_target_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("watch_targets.id", ondelete="CASCADE"),
        index=True,
    )
    title_snapshot: Mapped[str] = mapped_column(Text)
    candidate_key: Mapped[str] = mapped_column(Text)
    brand_hint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    size_hint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    similarity_score: Mapped[float] = mapped_column(Float, default=100.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    target: Mapped[WatchTarget] = relationship()


class TaskRun(Base):
    __tablename__ = "task_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    watch_task_id: Mapped[str] = mapped_column(String(36), ForeignKey("watch_tasks.id", ondelete="CASCADE"), index=True)
    triggered_by: Mapped[str] = mapped_column(String(32), default="manual")
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifact_run_dir: Mapped[str | None] = mapped_column(Text, nullable=True)
    engine_store_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    engine_product_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class WatchGroupRun(Base):
    __tablename__ = "watch_group_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    watch_group_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("watch_groups.id", ondelete="CASCADE"),
        index=True,
    )
    triggered_by: Mapped[str] = mapped_column(String(32), default="manual")
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifact_run_dir: Mapped[str | None] = mapped_column(Text, nullable=True)
    winner_member_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("watch_group_members.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    winner_effective_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    runner_up_member_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("watch_group_members.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    runner_up_effective_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_spread: Mapped[float | None] = mapped_column(Float, nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    member_results_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class PriceObservation(Base):
    __tablename__ = "price_observations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    watch_task_id: Mapped[str] = mapped_column(String(36), ForeignKey("watch_tasks.id", ondelete="CASCADE"), index=True)
    task_run_id: Mapped[str] = mapped_column(String(36), ForeignKey("task_runs.id", ondelete="CASCADE"), index=True)
    listed_price: Mapped[float] = mapped_column(Float)
    original_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    availability: Mapped[str] = mapped_column(String(32), default="available")
    title_snapshot: Mapped[str] = mapped_column(Text)
    unit_price_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str] = mapped_column(Text)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    parser_version: Mapped[str] = mapped_column(String(64), default="legacy")


class NotificationRule(Base):
    __tablename__ = "notification_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    watch_task_id: Mapped[str] = mapped_column(String(36), ForeignKey("watch_tasks.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String(32), default="email")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    cooldown_minutes: Mapped[int] = mapped_column(Integer, default=720)
    recipient_email: Mapped[str] = mapped_column(String(255))
    template_key: Mapped[str] = mapped_column(String(64), default="price-alert")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class DeliveryEvent(Base):
    __tablename__ = "delivery_events"
    __table_args__ = (
        CheckConstraint(
            "watch_task_id IS NOT NULL OR watch_group_id IS NOT NULL",
            name="ck_delivery_events_owner_ref",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    watch_task_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("watch_tasks.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    watch_group_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("watch_groups.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    task_run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("task_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    watch_group_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("watch_group_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(64))
    channel: Mapped[str] = mapped_column(String(32), default="email")
    recipient: Mapped[str] = mapped_column(String(255))
    template_key: Mapped[str] = mapped_column(String(64), default="price-alert")
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_payload_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    bounced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class StoreAdapterBinding(Base):
    __tablename__ = "store_adapter_bindings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    store_key: Mapped[str] = mapped_column(String(64), unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    adapter_class: Mapped[str] = mapped_column(String(255))


class CashbackQuote(Base):
    __tablename__ = "cashback_quotes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    watch_task_id: Mapped[str] = mapped_column(String(36), ForeignKey("watch_tasks.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(64))
    merchant_key: Mapped[str] = mapped_column(String(128))
    rate_type: Mapped[str] = mapped_column(String(32))
    rate_value: Mapped[float] = mapped_column(Float)
    conditions_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class EffectivePriceSnapshot(Base):
    __tablename__ = "effective_price_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    watch_task_id: Mapped[str] = mapped_column(String(36), ForeignKey("watch_tasks.id", ondelete="CASCADE"), index=True)
    task_run_id: Mapped[str] = mapped_column(String(36), ForeignKey("task_runs.id", ondelete="CASCADE"), index=True)
    listed_price: Mapped[float] = mapped_column(Float)
    cashback_amount: Mapped[float] = mapped_column(Float, default=0.0)
    effective_price: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    previous_listed_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    delta_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    delta_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_new_low: Mapped[bool] = mapped_column(Boolean, default=False)
    anomaly_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class CanonicalProduct(Base):
    __tablename__ = "canonical_products"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    normalized_title: Mapped[str] = mapped_column(Text)
    brand: Mapped[str | None] = mapped_column(String(255), nullable=True)
    size_hint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ProductCandidate(Base):
    __tablename__ = "product_candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    canonical_product_id: Mapped[str] = mapped_column(String(36), ForeignKey("canonical_products.id", ondelete="CASCADE"), index=True)
    watch_task_id: Mapped[str] = mapped_column(String(36), ForeignKey("watch_tasks.id", ondelete="CASCADE"), index=True)
    merchant_key: Mapped[str] = mapped_column(String(128))
    title_snapshot: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text)
    similarity_score: Mapped[float] = mapped_column(Float, default=0.0)
