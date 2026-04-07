from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from dealwatch.domain.enums import DeliveryStatus, ThresholdType
from dealwatch.persistence.models import (
    DeliveryEvent,
    NotificationRule,
    PriceObservation,
    TaskRun,
    WatchGroup,
    WatchGroupRun,
    WatchTask,
)
from dealwatch.providers.email import EmailDispatchPayload, EmailProvider


def should_notify_task(
    task: WatchTask,
    previous_observation: PriceObservation | None,
    observation: PriceObservation,
    effective_price: float,
) -> bool:
    threshold_type = ThresholdType(task.threshold_type)
    if threshold_type == ThresholdType.PRICE_BELOW:
        return observation.listed_price <= task.threshold_value
    if threshold_type == ThresholdType.EFFECTIVE_PRICE_BELOW:
        return effective_price <= task.threshold_value
    if previous_observation is None or previous_observation.listed_price <= 0:
        return False
    drop_pct = ((previous_observation.listed_price - observation.listed_price) / previous_observation.listed_price) * 100
    return drop_pct >= task.threshold_value


def should_notify_group(
    group: WatchGroup,
    previous_run: WatchGroupRun | None,
    winner: dict[str, object],
) -> bool:
    if not group.notifications_enabled:
        return False

    threshold_type = ThresholdType(group.threshold_type)
    listed_price = float(winner["listed_price"])
    effective_price = float(winner["effective_price"])
    if threshold_type == ThresholdType.PRICE_BELOW:
        return listed_price <= group.threshold_value
    if threshold_type == ThresholdType.EFFECTIVE_PRICE_BELOW:
        return effective_price <= group.threshold_value
    if previous_run is None or previous_run.winner_effective_price is None or previous_run.winner_effective_price <= 0:
        return False
    drop_pct = ((previous_run.winner_effective_price - effective_price) / previous_run.winner_effective_price) * 100
    return drop_pct >= group.threshold_value


async def dispatch_task_notifications(
    session: AsyncSession,
    *,
    task: WatchTask,
    run: TaskRun,
    observation: PriceObservation,
    effective_price: float,
    email_provider: EmailProvider | None,
    now_fn: Callable[[], datetime],
) -> list[DeliveryEvent]:
    deliveries: list[DeliveryEvent] = []
    rules = list(
        (
            await session.scalars(
                select(NotificationRule).where(NotificationRule.watch_task_id == task.id, NotificationRule.enabled.is_(True))
            )
        ).all()
    )
    for rule in rules:
        latest_delivery = await session.scalar(
            select(DeliveryEvent)
            .where(DeliveryEvent.watch_task_id == task.id, DeliveryEvent.recipient == rule.recipient_email)
            .order_by(desc(DeliveryEvent.created_at))
            .limit(1)
        )
        if latest_delivery is not None and latest_delivery.created_at >= now_fn() - timedelta(minutes=rule.cooldown_minutes):
            continue

        payload = EmailDispatchPayload(
            recipient=rule.recipient_email,
            subject=f"DealWatch alert for task #{task.id}",
            template_key=rule.template_key,
            html_body=(
                f"<h1>DealWatch Alert</h1>"
                f"<p>{observation.title_snapshot}</p>"
                f"<p>Listed price: ${observation.listed_price:.2f}</p>"
                f"<p>Effective price: ${effective_price:.2f}</p>"
                f"<p>Source: {observation.source_url}</p>"
            ),
            metadata={"subject_date": now_fn().strftime("%Y-%m-%d")},
        )
        event = DeliveryEvent(
            watch_task_id=task.id,
            task_run_id=run.id,
            provider="unknown",
            channel="email",
            recipient=rule.recipient_email,
            template_key=rule.template_key,
            status=DeliveryStatus.QUEUED.value,
            created_at=now_fn(),
        )
        session.add(event)
        await session.flush()
        try:
            result = await email_provider.send(payload) if email_provider is not None else None
            if result is None:
                raise RuntimeError("email_provider_unavailable")
            event.provider = result.provider
            event.status = DeliveryStatus.SENT.value
            event.provider_message_id = result.message_id
            event.provider_payload_json = result.payload
            event.sent_at = now_fn()
        except Exception as exc:
            event.status = DeliveryStatus.FAILED.value
            event.provider = "smtp"
            event.provider_payload_json = {"error": str(exc)}
        await session.flush()
        deliveries.append(event)
    return deliveries


async def dispatch_group_notifications(
    session: AsyncSession,
    *,
    group: WatchGroup,
    run: WatchGroupRun,
    winner: dict[str, object],
    decision_reason: str,
    email_provider: EmailProvider | None,
    now_fn: Callable[[], datetime],
) -> list[DeliveryEvent]:
    if not group.notifications_enabled:
        return []

    latest_delivery = await session.scalar(
        select(DeliveryEvent)
        .where(DeliveryEvent.watch_group_id == group.id, DeliveryEvent.recipient == group.recipient_email)
        .order_by(desc(DeliveryEvent.created_at))
        .limit(1)
    )
    if latest_delivery is not None and latest_delivery.created_at >= now_fn() - timedelta(minutes=group.cooldown_minutes):
        return []

    payload = EmailDispatchPayload(
        recipient=group.recipient_email,
        subject=f"DealWatch group alert for group #{group.id}",
        template_key="watch-group-threshold-hit",
        html_body=(
            f"<h1>DealWatch Group Alert</h1>"
            f"<p>{winner['title_snapshot']}</p>"
            f"<p>Store: {winner['store_key']}</p>"
            f"<p>Listed price: ${float(winner['listed_price']):.2f}</p>"
            f"<p>Effective price: ${float(winner['effective_price']):.2f}</p>"
            f"<p>Decision reason: {decision_reason}</p>"
        ),
        metadata={"subject_date": now_fn().strftime("%Y-%m-%d")},
    )
    event = DeliveryEvent(
        watch_task_id=None,
        watch_group_id=group.id,
        task_run_id=None,
        watch_group_run_id=run.id,
        provider="unknown",
        channel="email",
        recipient=group.recipient_email,
        template_key="watch-group-threshold-hit",
        status=DeliveryStatus.QUEUED.value,
        created_at=now_fn(),
    )
    session.add(event)
    await session.flush()
    try:
        result = await email_provider.send(payload) if email_provider is not None else None
        if result is None:
            raise RuntimeError("email_provider_unavailable")
        event.provider = result.provider
        event.status = DeliveryStatus.SENT.value
        event.provider_message_id = result.message_id
        event.provider_payload_json = result.payload
        event.sent_at = now_fn()
    except Exception as exc:
        event.status = DeliveryStatus.FAILED.value
        event.provider = "smtp"
        event.provider_payload_json = {"error": str(exc)}
    await session.flush()
    return [event]
