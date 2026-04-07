from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from dealwatch.domain.enums import FailureKind, HealthStatus
from dealwatch.infra.config import Settings
from dealwatch.persistence.models import (
    DeliveryEvent,
    EffectivePriceSnapshot,
    PriceObservation,
    TaskRun,
    WatchGroup,
    WatchGroupMember,
    WatchGroupRun,
    WatchTarget,
    WatchTask,
)
from dealwatch.runtime_preflight import is_placeholder, load_settings_values


def build_backoff_until(
    failures: int,
    *,
    failure_kind: FailureKind,
    now_fn: Callable[[], datetime],
) -> datetime:
    if failure_kind == FailureKind.BLOCKED:
        minutes = min(max(failures, 1) * 120, 1440)
    else:
        minutes = min(max(failures, 1) * 30, 360)
    return now_fn() + timedelta(minutes=minutes)


def build_attention_guidance(
    *,
    kind: str,
    health_status: str,
    manual_intervention_required: bool,
    last_failure_kind: str | None,
    last_error_code: str | None,
    last_error_message: str | None,
) -> tuple[str, str]:
    if last_error_code == "store_disabled":
        return (
            "The store runtime switch is disabled for this monitor.",
            "Open Settings, re-enable the store runtime switch, then rerun it manually.",
        )
    if last_error_code == "watch_group_no_successful_candidates":
        return (
            "The latest group run finished without any successful candidate.",
            "Inspect member results, fix the failing candidate path, then rerun the group.",
        )
    if last_failure_kind == FailureKind.DELIVERY_FAILED.value:
        return (
            "Recent delivery attempts failed even though runtime execution continued.",
            "Check notification settings and recent delivery events before rerunning.",
        )
    if last_error_code == "offer_not_parsed":
        return (
            "The latest fetch did not produce a parseable offer.",
            "Inspect the latest run evidence, confirm the source page still parses, then rerun manually.",
        )
    if last_error_code == "unexpected_runtime_error":
        return (
            "The latest run ended in an unexpected runtime error.",
            "Inspect the latest run details and artifact evidence before retrying.",
        )
    if manual_intervention_required:
        return (
            "Automation is paused until an operator reviews the latest failure.",
            f"Inspect the {kind} detail view, address the blocker, then rerun manually.",
        )
    if health_status == HealthStatus.DEGRADED.value:
        return (
            "Recent failures pushed this monitor into a degraded state.",
            "Review the last failure and only rerun once the likely cause is understood.",
        )
    fallback_reason = last_error_message or last_error_code or "Recent runtime state requires operator review."
    return (
        fallback_reason,
        f"Inspect the {kind} detail view for the latest run history and decide whether to rerun now.",
    )


def build_readiness_check(
    *,
    key: str,
    label: str,
    severity: str,
    status: str,
    reason: str,
    message: str,
    checked_at: str,
    detail: dict[str, Any],
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "severity": severity,
        "status": status,
        "reason": reason,
        "message": message,
        "summary": message,
        "checked_at": checked_at,
        "detail": detail,
        "metadata": detail,
    }


def build_smoke_readiness_check(
    *,
    smoke_dir: Path,
    checked_at: str,
) -> dict[str, Any]:
    expected_files = ["api-smoke.log", "worker-smoke.log"]
    smoke_logs = [path for path in smoke_dir.rglob("*.log")] if smoke_dir.exists() else []
    latest_log = max(smoke_logs, key=lambda path: path.stat().st_mtime) if smoke_logs else None
    found_names = {path.name for path in smoke_logs}
    has_complete_pair = all(name in found_names for name in expected_files)
    latest_log_at = (
        datetime.fromtimestamp(latest_log.stat().st_mtime, tz=timezone.utc).isoformat()
        if latest_log is not None
        else None
    )
    return build_readiness_check(
        key="smoke",
        label="Repo-local smoke evidence",
        severity="advisory",
        status="ready" if has_complete_pair else "warning",
        reason="smoke_evidence_complete" if has_complete_pair else "smoke_evidence_partial_or_missing",
        message=(
            "API and worker smoke artifacts are both present."
            if has_complete_pair
            else "Smoke evidence is missing or incomplete. Run ./scripts/smoke_product_hermetic.sh to capture a fresh end-to-end pair."
        ),
        checked_at=checked_at,
        detail={
            "smoke_log_count": len(smoke_logs),
            "latest_log_path": str(latest_log) if latest_log is not None else None,
            "latest_log_at": latest_log_at,
            "expected_files": expected_files,
        },
    )


async def build_notification_readiness_check(
    session: AsyncSession,
    *,
    settings: Settings,
    checked_at: str,
) -> dict[str, Any]:
    values = load_settings_values(settings)
    postmark_token = values.get("POSTMARK_SERVER_TOKEN", "").strip()
    smtp_host = values.get("SMTP_HOST", "").strip()
    smtp_user = values.get("SMTP_USER", "").strip()
    smtp_password = values.get("SMTP_PASSWORD", "").strip()
    has_postmark = bool(postmark_token and not is_placeholder(postmark_token))
    has_smtp = bool(
        smtp_host
        and smtp_user
        and smtp_password
        and not any(is_placeholder(item) for item in (smtp_host, smtp_user, smtp_password))
    )
    latest_delivery = await session.scalar(
        select(DeliveryEvent).order_by(desc(DeliveryEvent.created_at)).limit(1)
    )
    provider_mode = "postmark" if has_postmark else ("smtp" if has_smtp else "none")
    return build_readiness_check(
        key="notifications",
        label="Notification path",
        severity="advisory",
        status="ready" if provider_mode != "none" else "warning",
        reason="notification_provider_configured" if provider_mode != "none" else "notification_provider_missing",
        message=(
            f"{provider_mode.upper()} delivery is configured."
            if provider_mode != "none"
            else "No real email delivery provider is configured yet."
        ),
        checked_at=checked_at,
        detail={
            "provider_mode": provider_mode,
            "latest_delivery_status": latest_delivery.status if latest_delivery is not None else None,
            "latest_delivery_at": latest_delivery.created_at.isoformat() if latest_delivery is not None else None,
        },
    )


def attention_sort_key(item: dict[str, Any]) -> tuple[Any, ...]:
    priority = {
        HealthStatus.BLOCKED.value: 0,
        HealthStatus.NEEDS_ATTENTION.value: 1,
        HealthStatus.DEGRADED.value: 2,
        HealthStatus.HEALTHY.value: 3,
    }
    return (
        0 if item["manual_intervention_required"] else 1,
        priority.get(item["health_status"], 9),
        item["backoff_until"] or "9999-12-31T23:59:59+00:00",
        item["title"].lower(),
    )


async def collect_attention_items(
    session: AsyncSession,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    task_rows = list(
        (
            await session.scalars(
                select(WatchTask)
                .where(
                    or_(
                        WatchTask.manual_intervention_required.is_(True),
                        WatchTask.health_status != HealthStatus.HEALTHY.value,
                        WatchTask.backoff_until.is_not(None),
                        WatchTask.last_error_code.is_not(None),
                        WatchTask.last_failure_kind.is_not(None),
                    )
                )
                .order_by(desc(WatchTask.updated_at))
            )
        ).all()
    )
    group_rows = list(
        (
            await session.scalars(
                select(WatchGroup)
                .where(
                    or_(
                        WatchGroup.manual_intervention_required.is_(True),
                        WatchGroup.health_status != HealthStatus.HEALTHY.value,
                        WatchGroup.backoff_until.is_not(None),
                        WatchGroup.last_error_code.is_not(None),
                        WatchGroup.last_failure_kind.is_not(None),
                    )
                )
                .order_by(desc(WatchGroup.updated_at))
            )
        ).all()
    )

    task_items = [await build_task_attention_item(session, task) for task in task_rows]
    group_items = [await build_watch_group_attention_item(session, group) for group in group_rows]
    task_items.sort(key=attention_sort_key)
    group_items.sort(key=attention_sort_key)
    return task_items, group_items


async def build_task_summary(session: AsyncSession, task: WatchTask) -> dict[str, Any]:
    target = await session.get(WatchTarget, task.watch_target_id)
    latest_observation = await session.scalar(
        select(PriceObservation)
        .where(PriceObservation.watch_task_id == task.id)
        .order_by(desc(PriceObservation.observed_at))
        .limit(1)
    )
    latest_effective = await session.scalar(
        select(EffectivePriceSnapshot)
        .where(EffectivePriceSnapshot.watch_task_id == task.id)
        .order_by(desc(EffectivePriceSnapshot.computed_at))
        .limit(1)
    )
    latest_run = await session.scalar(
        select(TaskRun).where(TaskRun.watch_task_id == task.id).order_by(desc(TaskRun.created_at)).limit(1)
    )
    return {
        "id": task.id,
        "title": latest_observation.title_snapshot if latest_observation is not None else (target.product_url if target else "Pending first fetch"),
        "normalized_url": target.normalized_url if target else None,
        "store_key": target.store_key if target else None,
        "status": task.status,
        "zip_code": task.zip_code,
        "cadence_minutes": task.cadence_minutes,
        "next_run_at": task.next_run_at.isoformat() if task.next_run_at else None,
        "last_listed_price": latest_observation.listed_price if latest_observation else None,
        "last_effective_price": latest_effective.effective_price if latest_effective else None,
        "last_run_status": latest_run.status if latest_run else None,
        "health_status": task.health_status,
        "backoff_until": task.backoff_until.isoformat() if task.backoff_until else None,
        "manual_intervention_required": task.manual_intervention_required,
    }


async def build_watch_group_summary(session: AsyncSession, group: WatchGroup) -> dict[str, Any]:
    latest_run = await session.scalar(
        select(WatchGroupRun)
        .where(WatchGroupRun.watch_group_id == group.id)
        .order_by(desc(WatchGroupRun.created_at))
        .limit(1)
    )
    member_count = len(
        list(
            (
                await session.scalars(
                    select(WatchGroupMember).where(
                        WatchGroupMember.watch_group_id == group.id,
                        WatchGroupMember.is_active.is_(True),
                    )
                )
            ).all()
        )
    )
    winner_title = None
    if latest_run is not None and latest_run.winner_member_id:
        winner_member = await session.get(WatchGroupMember, latest_run.winner_member_id)
        winner_title = winner_member.title_snapshot if winner_member is not None else None
    return {
        "id": group.id,
        "title": group.title,
        "status": group.status,
        "health_status": group.health_status,
        "zip_code": group.zip_code,
        "cadence_minutes": group.cadence_minutes,
        "next_run_at": group.next_run_at.isoformat() if group.next_run_at else None,
        "last_run_at": group.last_run_at.isoformat() if group.last_run_at else None,
        "last_run_status": latest_run.status if latest_run is not None else None,
        "member_count": member_count,
        "winner_title": winner_title,
        "winner_effective_price": latest_run.winner_effective_price if latest_run is not None else None,
        "price_spread": latest_run.price_spread if latest_run is not None else None,
        "backoff_until": group.backoff_until.isoformat() if group.backoff_until else None,
        "manual_intervention_required": group.manual_intervention_required,
    }


async def build_task_attention_item(session: AsyncSession, task: WatchTask) -> dict[str, Any]:
    summary = await build_task_summary(session, task)
    reason, recommended_action = build_attention_guidance(
        kind="task",
        health_status=task.health_status,
        manual_intervention_required=task.manual_intervention_required,
        last_failure_kind=task.last_failure_kind,
        last_error_code=task.last_error_code,
        last_error_message=task.last_error_message,
    )
    return {
        "kind": "task",
        "id": task.id,
        "title": summary["title"],
        "status": task.status,
        "health_status": task.health_status,
        "manual_intervention_required": task.manual_intervention_required,
        "next_run_at": summary["next_run_at"],
        "backoff_until": task.backoff_until.isoformat() if task.backoff_until else None,
        "last_run_status": summary["last_run_status"],
        "consecutive_failures": task.consecutive_failures,
        "last_failure_kind": task.last_failure_kind,
        "last_error_code": task.last_error_code,
        "last_error_message": task.last_error_message,
        "reason": reason,
        "recommended_action": recommended_action,
    }


async def build_watch_group_attention_item(
    session: AsyncSession,
    group: WatchGroup,
) -> dict[str, Any]:
    summary = await build_watch_group_summary(session, group)
    reason, recommended_action = build_attention_guidance(
        kind="group",
        health_status=group.health_status,
        manual_intervention_required=group.manual_intervention_required,
        last_failure_kind=group.last_failure_kind,
        last_error_code=group.last_error_code,
        last_error_message=group.last_error_message,
    )
    return {
        "kind": "group",
        "id": group.id,
        "title": group.title,
        "status": group.status,
        "health_status": group.health_status,
        "manual_intervention_required": group.manual_intervention_required,
        "next_run_at": summary["next_run_at"],
        "backoff_until": group.backoff_until.isoformat() if group.backoff_until else None,
        "last_run_status": summary["last_run_status"],
        "consecutive_failures": group.consecutive_failures,
        "last_failure_kind": group.last_failure_kind,
        "last_error_code": group.last_error_code,
        "last_error_message": group.last_error_message,
        "reason": reason,
        "recommended_action": recommended_action,
    }
