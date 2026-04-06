from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import html
import json
import logging
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from dealwatch.core.models import AnomalyReason, Offer
from dealwatch.core.rules import RulesEngine
from dealwatch.builder_contract import (
    build_builder_client_config_payload,
    build_builder_client_configs_payload,
    build_builder_starter_pack_payload,
)
from dealwatch.compare.matching import build_candidate_key, build_candidate_snapshot, build_match_details
from dealwatch.domain.enums import (
    DeliveryStatus,
    FailureKind,
    HealthStatus,
    ResolutionStatus,
    TaskRunStatus,
    ThresholdType,
    WatchTaskStatus,
)
from dealwatch.infra.config import PROJECT_ROOT, Settings, settings
from dealwatch.infra.playwright_client import PlaywrightClient
from dealwatch.infra.retry_budget import RetryBudget
from dealwatch.persistence.models import (
    CashbackQuote,
    CanonicalProduct,
    DeliveryEvent,
    EffectivePriceSnapshot,
    NotificationRule,
    PriceObservation,
    ProductCandidate,
    StoreAdapterBinding,
    TaskRun,
    User,
    UserPreference,
    WatchGroup,
    WatchGroupMember,
    WatchGroupRun,
    WatchTarget,
    WatchTask,
)
from dealwatch.providers.cashback import CashbackMonitorProvider, CashbackProvider, CashbackQuotePayload
from dealwatch.providers.email import (
    EmailDispatchPayload,
    EmailProvider,
    PostmarkEmailProvider,
    SmtpFallbackEmailProvider,
)
from dealwatch.runtime_preflight import is_placeholder, load_settings_values, validate_runtime
from dealwatch.stores import STORE_CAPABILITY_REGISTRY, STORE_REGISTRY
from dealwatch.stores.base_adapter import SkipParse

from .ai_integration import AiNarrativeService
from .store_onboarding import build_store_onboarding_cockpit
from .urls import resolve_store_for_url


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalize_unexpected_runtime_error(_: Exception) -> tuple[str, str]:
    return ("unexpected_runtime_error", "unexpected_runtime_error")


SMOKE_ARTIFACTS_DIR = PROJECT_ROOT / ".runtime-cache" / "operator" / "smoke"


@dataclass
class ProductService:
    session_factory: async_sessionmaker[AsyncSession]
    settings: Settings = field(default_factory=lambda: settings)
    cashback_provider: CashbackProvider | None = None
    email_provider: EmailProvider | None = None
    ai_service: AiNarrativeService | None = None
    logger: Any = field(init=False, repr=False)
    rules: RulesEngine = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.rules = RulesEngine(
            min_drop_amount=self.settings.RULE_MIN_DROP_AMOUNT,
            min_drop_pct=self.settings.RULE_MIN_DROP_PCT,
            anomaly_min_samples=self.settings.ANOMALY_MIN_SAMPLES,
            anomaly_iqr_multiplier=self.settings.ANOMALY_IQR_MULTIPLIER,
            anomaly_zscore_threshold=self.settings.ANOMALY_ZSCORE_THRESHOLD,
            anomaly_zero_var_pct=self.settings.ANOMALY_ZERO_VAR_PCT,
            anomaly_zero_var_abs=self.settings.ANOMALY_ZERO_VAR_ABS,
        )
        if self.cashback_provider is None:
            self.cashback_provider = CashbackMonitorProvider()
        if self.email_provider is None:
            token = self.settings.POSTMARK_SERVER_TOKEN.get_secret_value().strip()
            self.email_provider = PostmarkEmailProvider(self.settings) if token else SmtpFallbackEmailProvider(self.settings)
        if self.ai_service is None:
            self.ai_service = AiNarrativeService(settings=self.settings)

    async def bootstrap_owner(self, session: AsyncSession) -> User:
        owner = await session.scalar(select(User).where(User.role == "owner"))
        if owner is None:
            owner = User(
                email=self.settings.OWNER_EMAIL,
                display_name=self.settings.OWNER_DISPLAY_NAME,
                role="owner",
                status="active",
            )
            session.add(owner)
            await session.flush()
        await self._ensure_owner_preference(session, owner)
        return owner

    async def get_notification_settings(self, session: AsyncSession) -> dict[str, Any]:
        owner = await self.bootstrap_owner(session)
        preference = await self._ensure_owner_preference(session, owner)
        rule = await self._get_default_rule(session, owner.id)
        return {
            "default_recipient_email": preference.default_email_recipient,
            "cooldown_minutes": rule.cooldown_minutes if rule is not None else preference.notification_cooldown_minutes,
            "notifications_enabled": rule.enabled if rule is not None else preference.notifications_enabled,
        }

    async def get_notification_settings_readonly(self, session: AsyncSession) -> dict[str, Any]:
        owner = await session.scalar(select(User).where(User.role == "owner").limit(1))
        preference = await session.get(UserPreference, owner.id) if owner is not None else None
        rule = await self._get_default_rule(session, owner.id) if owner is not None else None
        return {
            "default_recipient_email": (
                rule.recipient_email
                if rule is not None
                else (
                    preference.default_email_recipient
                    if preference is not None
                    else self.settings.OWNER_EMAIL
                )
            ),
            "cooldown_minutes": (
                rule.cooldown_minutes
                if rule is not None
                else (
                    preference.notification_cooldown_minutes
                    if preference is not None
                    else self.settings.DEFAULT_NOTIFICATION_COOLDOWN_MINUTES
                )
            ),
            "notifications_enabled": (
                rule.enabled if rule is not None else (preference.notifications_enabled if preference is not None else True)
            ),
        }

    async def update_notification_settings(
        self,
        session: AsyncSession,
        *,
        default_recipient_email: str,
        cooldown_minutes: int,
        notifications_enabled: bool,
    ) -> dict[str, Any]:
        owner = await self.bootstrap_owner(session)
        preference = await self._ensure_owner_preference(session, owner)
        preference.default_email_recipient = default_recipient_email
        preference.notification_cooldown_minutes = cooldown_minutes
        preference.notifications_enabled = notifications_enabled

        rules = list(
            (
                await session.scalars(
                    select(NotificationRule)
                    .join(WatchTask, NotificationRule.watch_task_id == WatchTask.id)
                    .where(WatchTask.user_id == owner.id)
                )
            ).all()
        )
        tasks = list((await session.scalars(select(WatchTask).where(WatchTask.user_id == owner.id))).all())
        groups = list((await session.scalars(select(WatchGroup).where(WatchGroup.user_id == owner.id))).all())
        for task in tasks:
            task.cooldown_minutes = cooldown_minutes
        for group in groups:
            group.cooldown_minutes = cooldown_minutes
            group.recipient_email = default_recipient_email
            group.notifications_enabled = notifications_enabled
        for rule in rules:
            rule.recipient_email = default_recipient_email
            rule.cooldown_minutes = cooldown_minutes
            rule.enabled = notifications_enabled
        await session.flush()
        return await self.get_notification_settings(session)

    async def list_notification_events(
        self,
        session: AsyncSession,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        rows = list(
            (
                await session.scalars(
                    select(DeliveryEvent).order_by(desc(DeliveryEvent.id)).limit(max(int(limit), 1))
                )
            ).all()
        )
        return [
            {
                "id": item.id,
                "watch_task_id": item.watch_task_id,
                "watch_group_id": item.watch_group_id,
                "provider": item.provider,
                "status": item.status,
                "recipient": item.recipient,
                "message_id": item.provider_message_id,
                "created_at": item.created_at.isoformat(),
                "sent_at": item.sent_at.isoformat() if item.sent_at else None,
                "delivered_at": item.delivered_at.isoformat() if item.delivered_at else None,
                "bounced_at": item.bounced_at.isoformat() if item.bounced_at else None,
            }
            for item in rows
        ]

    async def list_store_bindings(self, session: AsyncSession) -> list[dict[str, Any]]:
        rows = list((await session.scalars(select(StoreAdapterBinding).order_by(StoreAdapterBinding.store_key))).all())
        results: list[dict[str, Any]] = []
        for row in rows:
            capability = STORE_CAPABILITY_REGISTRY.get(row.store_key)
            results.append(
                {
                    "store_key": row.store_key,
                    "enabled": row.enabled,
                    "adapter_class": row.adapter_class,
                    "support_channel": "official" if capability is not None else "limited",
                    "support_tier": capability.support_tier if capability is not None else "official_in_progress",
                    "support_reason_codes": list(capability.support_reason_codes) if capability is not None else [],
                    "next_step_codes": list(capability.next_step_codes) if capability is not None else [],
                    "contract_test_paths": list(capability.contract_test_paths) if capability is not None else [],
                    "discovery_mode": capability.discovery_mode if capability is not None else "unknown",
                    "parse_mode": capability.parse_mode if capability is not None else "unknown",
                    "region_sensitive": capability.region_sensitive if capability is not None else True,
                    "cashback_supported": capability.cashback_supported if capability is not None else False,
                    "supports_compare_intake": capability.supports_compare_intake if capability is not None else False,
                    "supports_watch_task": capability.supports_watch_task if capability is not None else False,
                    "supports_watch_group": capability.supports_watch_group if capability is not None else False,
                    "supports_recovery": capability.supports_recovery if capability is not None else False,
                }
            )
        return results

    async def get_store_onboarding_cockpit(self, session: AsyncSession) -> dict[str, Any]:
        bindings = await self.list_store_bindings(session)
        return build_store_onboarding_cockpit(bindings=bindings)

    async def get_builder_starter_pack(self, session: AsyncSession | None = None) -> dict[str, Any]:
        del session
        return build_builder_starter_pack_payload()

    async def get_builder_client_config(
        self,
        client: str,
        session: AsyncSession | None = None,
    ) -> dict[str, Any]:
        del session
        return build_builder_client_config_payload(client)

    async def get_builder_client_configs(
        self,
        session: AsyncSession | None = None,
    ) -> dict[str, Any]:
        del session
        return build_builder_client_configs_payload()

    async def get_runtime_readiness(self, session: AsyncSession) -> dict[str, Any]:
        checked_at = utcnow().isoformat()
        checks: list[dict[str, Any]] = []

        await session.execute(select(1))
        database_backend = str(self.settings.DATABASE_URL).split(":", 1)[0]
        checks.append(
            self._build_readiness_check(
                key="database",
                label="Database",
                severity="required",
                status="ready" if self.settings.DATABASE_URL.startswith("postgresql") else "warning",
                reason="database_connection_ok"
                if self.settings.DATABASE_URL.startswith("postgresql")
                else "database_not_postgresql",
                message=(
                    "The product database connection is available and the runtime uses PostgreSQL."
                    if self.settings.DATABASE_URL.startswith("postgresql")
                    else "Database session is reachable, but the current runtime is not using PostgreSQL."
                ),
                checked_at=checked_at,
                detail={"database_backend": database_backend},
            )
        )

        owner = await session.scalar(select(User).where(User.role == "owner").limit(1))
        checks.append(
            self._build_readiness_check(
                key="owner",
                label="Owner bootstrap",
                severity="advisory",
                status="ready" if owner is not None else "warning",
                reason="owner_present" if owner is not None else "owner_missing",
                message=(
                    f"Owner record {owner.email} is present."
                    if owner is not None
                    else "No owner record exists yet. Run bootstrap-owner or trigger the first owner bootstrap path."
                ),
                checked_at=checked_at,
                detail={
                    "owner_email": owner.email if owner is not None else None,
                    "owner_status": owner.status if owner is not None else None,
                },
            )
        )

        bindings = await self.list_store_bindings(session)
        enabled_bindings = [item for item in bindings if item["enabled"]]
        compare_enabled = [item["store_key"] for item in enabled_bindings if item["supports_compare_intake"]]
        checks.append(
            self._build_readiness_check(
                key="stores",
                label="Store runtime switches",
                severity="required",
                status="ready" if enabled_bindings else "blocked",
                reason="stores_enabled" if enabled_bindings else "no_enabled_stores",
                message=(
                    f"{len(enabled_bindings)} enabled store runtime switch(es) are ready."
                    if enabled_bindings
                    else "No enabled store runtime switches are currently available."
                ),
                checked_at=checked_at,
                detail={
                    "enabled_store_count": len(enabled_bindings),
                    "enabled_store_keys": [item["store_key"] for item in enabled_bindings],
                    "enabled_bound_store_keys": [item["store_key"] for item in enabled_bindings],
                    "compare_enabled_store_keys": compare_enabled,
                },
            )
        )

        checks.append(await self._build_notification_readiness_check(session, checked_at=checked_at))

        values = load_settings_values(self.settings)
        startup_checks, startup_warnings = validate_runtime(values, target="startup")
        relevant_warnings = [item for item in startup_warnings if item.key != "USE_LLM"]
        blockers = [item.key for item in startup_checks if not item.ok]
        checks.append(
            self._build_readiness_check(
                key="startup_preflight",
                label="Runtime preflight",
                severity="required",
                status="blocked" if blockers else ("warning" if relevant_warnings else "ready"),
                reason=(
                    "runtime_preflight_failed"
                    if blockers
                    else ("runtime_preflight_warning" if relevant_warnings else "runtime_preflight_ok")
                ),
                message=(
                    f"Startup preflight reported blockers for: {', '.join(blockers)}."
                    if blockers
                    else (
                        f"Startup preflight passed with {len(relevant_warnings)} warning(s)."
                        if relevant_warnings
                        else "Startup preflight passed."
                    )
                ),
                checked_at=checked_at,
                detail={
                    "blocker_keys": blockers,
                    "warning_keys": [item.key for item in relevant_warnings],
                },
            )
        )

        checks.append(self._build_smoke_readiness_check(checked_at=checked_at))

        blocked_count = sum(1 for item in checks if item["status"] == "blocked")
        warning_count = sum(1 for item in checks if item["status"] == "warning")
        required_ready_count = sum(
            1 for item in checks if item["severity"] == "required" and item["status"] == "ready"
        )
        overall_status = "blocked" if blocked_count else ("degraded" if warning_count else "ready")
        database = next(item for item in checks if item["key"] == "database")
        owner = next(item for item in checks if item["key"] == "owner")
        stores = next(item for item in checks if item["key"] == "stores")
        notifications = next(item for item in checks if item["key"] == "notifications")
        startup_preflight = next(item for item in checks if item["key"] == "startup_preflight")
        smoke = next(item for item in checks if item["key"] == "smoke")
        return {
            "status": overall_status,
            "ready": blocked_count == 0 and warning_count == 0,
            "checked_at": checked_at,
            "headline": "Check the runtime contract before you trust the next run.",
            "generated_at": checked_at,
            "overall_status": overall_status,
            "required_ready_count": required_ready_count,
            "warning_count": warning_count,
            "blocked_count": blocked_count,
            "database": database,
            "owner_existence": owner,
            "store_bindings": stores,
            "notification_path": notifications,
            "startup_preflight": startup_preflight,
            "smoke_evidence": smoke,
            "checks": checks,
        }

    async def get_attention_inbox(self, session: AsyncSession) -> dict[str, Any]:
        checked_at = utcnow().isoformat()
        tasks = list(
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
        groups = list(
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

        task_items = [await self._build_task_attention_item(session, task) for task in tasks]
        group_items = [await self._build_watch_group_attention_item(session, group) for group in groups]
        task_items.sort(key=self._attention_sort_key)
        group_items.sort(key=self._attention_sort_key)
        return {
            "generated_at": checked_at,
            "total_items": len(task_items) + len(group_items),
            "tasks": task_items,
            "groups": group_items,
            "task_items": task_items,
            "group_items": group_items,
        }

    async def update_store_binding(
        self,
        session: AsyncSession,
        *,
        store_key: str,
        enabled: bool,
    ) -> dict[str, Any]:
        binding = await session.scalar(
            select(StoreAdapterBinding).where(StoreAdapterBinding.store_key == store_key).limit(1)
        )
        if binding is None:
            raise ValueError("store_binding_not_found")
        binding.enabled = bool(enabled)
        await session.flush()
        capability = STORE_CAPABILITY_REGISTRY.get(binding.store_key)
        return {
            "store_key": binding.store_key,
            "enabled": binding.enabled,
            "adapter_class": binding.adapter_class,
            "discovery_mode": capability.discovery_mode if capability is not None else "unknown",
            "parse_mode": capability.parse_mode if capability is not None else "unknown",
            "region_sensitive": capability.region_sensitive if capability is not None else True,
            "cashback_supported": capability.cashback_supported if capability is not None else False,
            "supports_compare_intake": capability.supports_compare_intake if capability is not None else False,
        }

    async def get_recovery_inbox(self, session: AsyncSession) -> dict[str, Any]:
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
        task_items = [await self._build_task_attention_item(session, task) for task in task_rows]
        group_items = [await self._build_watch_group_attention_item(session, group) for group in group_rows]
        task_items.sort(key=self._attention_sort_key)
        group_items.sort(key=self._attention_sort_key)
        ai_copilot = await self._build_recovery_ai_copilot(task_items=task_items, group_items=group_items)
        return {
            "generated_at": utcnow().isoformat(),
            "total_items": len(task_items) + len(group_items),
            "tasks": task_items,
            "groups": group_items,
            "task_items": task_items,
            "group_items": group_items,
            "ai_copilot": ai_copilot,
        }

    async def create_watch_task(
        self,
        session: AsyncSession,
        *,
        submitted_url: str,
        zip_code: str,
        cadence_minutes: int,
        threshold_type: str,
        threshold_value: float,
        cooldown_minutes: int,
        recipient_email: str,
        compare_handoff: dict[str, Any] | None = None,
    ) -> WatchTask:
        owner = await self.bootstrap_owner(session)
        preference = await self._ensure_owner_preference(session, owner)
        task_zip_code = self._normalize_task_zip_code(
            zip_code,
            fallback=preference.default_zip_code or self.settings.ZIP_CODE,
        )
        target = await self._resolve_or_create_watch_target(session, owner.id, submitted_url)

        task = WatchTask(
            user_id=owner.id,
            watch_target_id=target.id,
            zip_code=task_zip_code,
            status=WatchTaskStatus.ACTIVE.value,
            cadence_minutes=max(int(cadence_minutes), 5),
            threshold_type=threshold_type,
            threshold_value=float(threshold_value),
            cooldown_minutes=max(int(cooldown_minutes), 0),
            next_run_at=utcnow(),
        )
        session.add(task)
        await session.flush()
        if compare_handoff is not None:
            await self._persist_compare_handoff(
                session,
                task=task,
                target=target,
                compare_handoff=compare_handoff,
            )
        session.add(
            NotificationRule(
                watch_task_id=task.id,
                channel="email",
                enabled=True,
                cooldown_minutes=max(int(cooldown_minutes), 0),
                recipient_email=recipient_email or preference.default_email_recipient,
                template_key="watch-threshold-hit",
            )
        )
        await session.flush()
        return task

    async def create_watch_group(
        self,
        session: AsyncSession,
        *,
        title: str | None,
        zip_code: str,
        cadence_minutes: int,
        threshold_type: str,
        threshold_value: float,
        cooldown_minutes: int,
        recipient_email: str,
        notifications_enabled: bool,
        candidates: list[dict[str, Any]],
    ) -> WatchGroup:
        owner = await self.bootstrap_owner(session)
        preference = await self._ensure_owner_preference(session, owner)
        group_zip_code = self._normalize_task_zip_code(
            zip_code,
            fallback=preference.default_zip_code or self.settings.ZIP_CODE,
        )
        cleaned_candidates = [item for item in candidates if str(item.get("submitted_url") or "").strip()]
        if len(cleaned_candidates) < 2:
            raise ValueError("at_least_two_group_candidates_required")
        for item in cleaned_candidates:
            resolved = resolve_store_for_url(str(item["submitted_url"]))
            if not resolved.supported:
                raise ValueError(resolved.error_code or "watch_group_candidate_not_supported")
            capability = STORE_CAPABILITY_REGISTRY.get(resolved.store_key)
            if capability is None or not capability.supports_watch_group:
                raise ValueError("watch_group_candidate_not_supported")
            if not await self._is_store_binding_enabled(session, resolved.store_key):
                raise ValueError("store_disabled")

        default_title = str(title or "").strip()
        if not default_title:
            first_title = str(cleaned_candidates[0].get("title_snapshot") or "").strip()
            default_title = first_title or "Compare Watch Group"

        group = WatchGroup(
            user_id=owner.id,
            title=default_title,
            status=WatchTaskStatus.ACTIVE.value,
            zip_code=group_zip_code,
            cadence_minutes=max(int(cadence_minutes), 5),
            threshold_type=threshold_type,
            threshold_value=float(threshold_value),
            cooldown_minutes=max(int(cooldown_minutes), 0),
            recipient_email=recipient_email or preference.default_email_recipient,
            notifications_enabled=bool(notifications_enabled),
            next_run_at=utcnow(),
        )
        session.add(group)
        await session.flush()

        for item in cleaned_candidates:
            target = await self._resolve_or_create_watch_target(session, owner.id, str(item["submitted_url"]))
            member = WatchGroupMember(
                watch_group_id=group.id,
                watch_target_id=target.id,
                title_snapshot=str(item.get("title_snapshot") or target.product_url),
                candidate_key=str(item.get("candidate_key") or "").strip()
                or build_candidate_key(
                    str(item.get("title_snapshot") or target.product_url),
                    brand=item.get("brand_hint"),
                    size_hint=item.get("size_hint"),
                ),
                brand_hint=(str(item.get("brand_hint")).strip() or None) if item.get("brand_hint") is not None else None,
                size_hint=(str(item.get("size_hint")).strip() or None) if item.get("size_hint") is not None else None,
                similarity_score=float(item.get("similarity_score") or 100.0),
                is_active=True,
            )
            session.add(member)

        await session.flush()
        return group

    async def list_watch_tasks(self, session: AsyncSession) -> list[dict[str, Any]]:
        tasks = list((await session.scalars(select(WatchTask).order_by(desc(WatchTask.created_at)))).all())
        return [await self._build_task_summary(session, task) for task in tasks]

    async def get_watch_task_detail(self, session: AsyncSession, task_id: str) -> dict[str, Any]:
        task = await session.scalar(select(WatchTask).where(WatchTask.id == task_id).with_for_update())
        if task is None:
            raise ValueError("watch_task_not_found")

        target = await session.get(WatchTarget, task.watch_target_id)
        observations = list(
            (
                await session.scalars(
                    select(PriceObservation)
                    .where(PriceObservation.watch_task_id == task.id)
                    .order_by(desc(PriceObservation.observed_at))
                    .limit(50)
                )
            ).all()
        )
        runs = list(
            (
                await session.scalars(
                    select(TaskRun).where(TaskRun.watch_task_id == task.id).order_by(desc(TaskRun.created_at)).limit(20)
                )
            ).all()
        )
        deliveries = list(
            (
                await session.scalars(
                    select(DeliveryEvent)
                    .where(DeliveryEvent.watch_task_id == task.id)
                    .order_by(desc(DeliveryEvent.created_at))
                    .limit(20)
                )
            ).all()
        )
        cashback_quotes = list(
            (
                await session.scalars(
                    select(CashbackQuote)
                    .where(CashbackQuote.watch_task_id == task.id)
                    .order_by(desc(CashbackQuote.collected_at))
                    .limit(5)
                )
            ).all()
        )
        effective_prices = list(
            (
                await session.scalars(
                    select(EffectivePriceSnapshot)
                    .where(EffectivePriceSnapshot.watch_task_id == task.id)
                    .order_by(desc(EffectivePriceSnapshot.computed_at))
                    .limit(50)
                )
            ).all()
        )
        latest_observation = observations[0] if observations else None
        latest_effective = effective_prices[0] if effective_prices else None
        compare_context = await self._get_compare_context(session, task.id)
        rule = await session.scalar(
            select(NotificationRule)
            .where(NotificationRule.watch_task_id == task.id)
            .order_by(desc(NotificationRule.updated_at), desc(NotificationRule.created_at))
            .limit(1)
        )
        title = latest_observation.title_snapshot if latest_observation is not None else (target.product_url if target else "Pending first fetch")

        return {
            "task": {
                "id": task.id,
                "title": title,
                "status": task.status,
                "store_key": target.store_key if target else None,
                "submitted_url": target.submitted_url if target else None,
                "normalized_url": target.normalized_url if target else None,
                "product_url": target.product_url if target else None,
                "threshold_type": task.threshold_type,
                "threshold_value": task.threshold_value,
                "zip_code": task.zip_code,
                "cooldown_minutes": rule.cooldown_minutes if rule is not None else task.cooldown_minutes,
                "cadence_minutes": task.cadence_minutes,
                "next_run_at": task.next_run_at.isoformat() if task.next_run_at else None,
                "last_run_at": task.last_run_at.isoformat() if task.last_run_at else None,
                "last_listed_price": latest_observation.listed_price if latest_observation else None,
                "last_effective_price": latest_effective.effective_price if latest_effective else None,
                "last_run_status": runs[0].status if runs else None,
                "recipient_email": rule.recipient_email if rule is not None else self.settings.OWNER_EMAIL,
                "health_status": task.health_status,
                "consecutive_failures": task.consecutive_failures,
                "backoff_until": task.backoff_until.isoformat() if task.backoff_until else None,
                "last_failure_kind": task.last_failure_kind,
                "manual_intervention_required": task.manual_intervention_required,
            },
            "observations": [
                {
                    "id": item.id,
                    "listed_price": item.listed_price,
                    "original_price": item.original_price,
                    "currency": item.currency,
                    "availability": item.availability,
                    "title_snapshot": item.title_snapshot,
                    "unit_price_raw": item.unit_price_raw,
                    "source_url": item.source_url,
                    "observed_at": item.observed_at.isoformat(),
                }
                for item in observations
            ],
            "runs": [
                {
                    "id": item.id,
                    "status": item.status,
                    "triggered_by": item.triggered_by,
                    "started_at": item.started_at.isoformat() if item.started_at else None,
                    "finished_at": item.finished_at.isoformat() if item.finished_at else None,
                    "error_code": item.error_code,
                    "error_message": item.error_message,
                    "artifact_run_dir": item.artifact_run_dir,
                    "artifact_evidence": self._read_artifact_evidence(item),
                }
                for item in runs
            ],
            "delivery_events": [
                {
                    "id": item.id,
                    "status": item.status,
                    "provider": item.provider,
                    "recipient": item.recipient,
                    "message_id": item.provider_message_id,
                    "created_at": item.created_at.isoformat(),
                    "sent_at": item.sent_at.isoformat() if item.sent_at else None,
                    "delivered_at": item.delivered_at.isoformat() if item.delivered_at else None,
                    "bounced_at": item.bounced_at.isoformat() if item.bounced_at else None,
                }
                for item in deliveries
            ],
            "cashback_quotes": [
                {
                    "provider": item.provider,
                    "merchant_key": item.merchant_key,
                    "rate_type": item.rate_type,
                    "rate_value": item.rate_value,
                    "conditions_text": item.conditions_text,
                    "source_url": item.source_url,
                    "confidence": item.confidence,
                    "collected_at": item.collected_at.isoformat(),
                }
                for item in cashback_quotes
            ],
            "effective_prices": [
                {
                    "listed_price": item.listed_price,
                    "cashback_amount": item.cashback_amount,
                    "effective_price": item.effective_price,
                    "currency": item.currency,
                    "computed_at": item.computed_at.isoformat(),
                }
                for item in effective_prices
            ],
            "compare_context": compare_context,
            "latest_signal": (
                {
                    "previous_listed_price": latest_effective.previous_listed_price,
                    "delta_amount": latest_effective.delta_amount,
                    "delta_pct": latest_effective.delta_pct,
                    "is_new_low": latest_effective.is_new_low,
                    "anomaly_reason": latest_effective.anomaly_reason,
                    "decision_reason": latest_effective.decision_reason,
                }
                if latest_effective is not None
                else None
            ),
        }

    async def update_watch_task(self, session: AsyncSession, task_id: str, **updates: Any) -> WatchTask:
        task = await session.get(WatchTask, task_id)
        if task is None:
            raise ValueError("watch_task_not_found")

        rule = await session.scalar(
            select(NotificationRule)
            .where(NotificationRule.watch_task_id == task.id)
            .order_by(desc(NotificationRule.updated_at), desc(NotificationRule.created_at))
            .limit(1)
        )
        for key, value in updates.items():
            if value is None:
                continue
            if key == "recipient_email":
                if rule is not None:
                    rule.recipient_email = value
                continue
            if key == "zip_code":
                value = self._normalize_task_zip_code(
                    str(value),
                    fallback=task.zip_code or self.settings.ZIP_CODE,
                )
            if key == "cooldown_minutes" and rule is not None:
                rule.cooldown_minutes = int(value)
            if hasattr(task, key):
                setattr(task, key, value)

        if task.status == WatchTaskStatus.ACTIVE.value and task.next_run_at is None:
            task.next_run_at = utcnow() + timedelta(minutes=task.cadence_minutes)
        if task.status == WatchTaskStatus.ACTIVE.value:
            task.manual_intervention_required = False
            if task.health_status == HealthStatus.NEEDS_ATTENTION.value:
                task.health_status = HealthStatus.HEALTHY.value
            task.backoff_until = None
        await session.flush()
        return task

    async def list_watch_groups(self, session: AsyncSession) -> list[dict[str, Any]]:
        groups = list((await session.scalars(select(WatchGroup).order_by(desc(WatchGroup.created_at)))).all())
        return [await self._build_watch_group_summary(session, group) for group in groups]

    async def get_watch_group_detail(self, session: AsyncSession, group_id: str) -> dict[str, Any]:
        group = await session.get(WatchGroup, group_id)
        if group is None:
            raise ValueError("watch_group_not_found")

        members = list(
            (
                await session.scalars(
                    select(WatchGroupMember)
                    .where(WatchGroupMember.watch_group_id == group.id)
                    .order_by(desc(WatchGroupMember.created_at))
                )
            ).all()
        )
        runs = list(
            (
                await session.scalars(
                    select(WatchGroupRun)
                    .where(WatchGroupRun.watch_group_id == group.id)
                    .order_by(desc(WatchGroupRun.created_at))
                    .limit(20)
                )
            ).all()
        )
        deliveries = list(
            (
                await session.scalars(
                    select(DeliveryEvent)
                    .where(DeliveryEvent.watch_group_id == group.id)
                    .order_by(desc(DeliveryEvent.created_at))
                    .limit(20)
                )
            ).all()
        )

        latest_run = runs[0] if runs else None
        latest_results = []
        if latest_run is not None and latest_run.member_results_json:
            latest_results = list(latest_run.member_results_json.get("results", []))
        latest_result_map = {str(item.get("member_id")): item for item in latest_results}
        member_map = {member.id: member for member in members}

        winner_member = None
        if latest_run is not None and latest_run.winner_member_id:
            winner_member = next((item for item in members if item.id == latest_run.winner_member_id), None)
        decision_explain = self._build_watch_group_decision_explain(
            group=group,
            latest_run=latest_run,
            latest_results=latest_results,
            member_map=member_map,
        )
        ai_decision_explain = await self._build_watch_group_ai_decision_explain(
            group=group,
            decision_explain=decision_explain,
        )

        return {
            "group": {
                "id": group.id,
                "title": group.title,
                "status": group.status,
                "zip_code": group.zip_code,
                "cadence_minutes": group.cadence_minutes,
                "threshold_type": group.threshold_type,
                "threshold_value": group.threshold_value,
                "cooldown_minutes": group.cooldown_minutes,
                "recipient_email": group.recipient_email,
                "notifications_enabled": group.notifications_enabled,
                "next_run_at": group.next_run_at.isoformat() if group.next_run_at else None,
                "last_run_at": group.last_run_at.isoformat() if group.last_run_at else None,
                "last_success_at": group.last_success_at.isoformat() if group.last_success_at else None,
                "last_error_code": group.last_error_code,
                "last_error_message": group.last_error_message,
                "health_status": group.health_status,
                "consecutive_failures": group.consecutive_failures,
                "backoff_until": group.backoff_until.isoformat() if group.backoff_until else None,
                "last_failure_kind": group.last_failure_kind,
                "manual_intervention_required": group.manual_intervention_required,
                "member_count": len(members),
                "current_winner_member_id": latest_run.winner_member_id if latest_run else None,
                "current_winner_title": winner_member.title_snapshot if winner_member is not None else None,
                "current_winner_effective_price": latest_run.winner_effective_price if latest_run else None,
                "price_spread": latest_run.price_spread if latest_run else None,
                "decision_reason": latest_run.decision_reason if latest_run else None,
            },
            "decision_explain": decision_explain,
            "ai_decision_explain": ai_decision_explain,
            "members": [
                {
                    "id": member.id,
                    "watch_target_id": member.watch_target_id,
                    "title_snapshot": member.title_snapshot,
                    "candidate_key": member.candidate_key,
                    "brand_hint": member.brand_hint,
                    "size_hint": member.size_hint,
                    "similarity_score": member.similarity_score,
                    "is_current_winner": latest_run.winner_member_id == member.id if latest_run else False,
                    "latest_result": latest_result_map.get(member.id),
                }
                for member in members
            ],
            "runs": [
                {
                    "id": item.id,
                    "status": item.status,
                    "started_at": item.started_at.isoformat() if item.started_at else None,
                    "finished_at": item.finished_at.isoformat() if item.finished_at else None,
                    "error_message": item.error_message,
                    "winner_member_id": item.winner_member_id,
                    "winner_effective_price": item.winner_effective_price,
                    "runner_up_member_id": item.runner_up_member_id,
                    "runner_up_effective_price": item.runner_up_effective_price,
                    "price_spread": item.price_spread,
                    "decision_reason": item.decision_reason,
                    "member_results": list((item.member_results_json or {}).get("results", [])),
                    "artifact_run_dir": item.artifact_run_dir,
                }
                for item in runs
            ],
            "deliveries": [
                {
                    "id": item.id,
                    "provider": item.provider,
                    "recipient": item.recipient,
                    "status": item.status,
                    "created_at": item.created_at.isoformat(),
                    "sent_at": item.sent_at.isoformat() if item.sent_at else None,
                    "delivered_at": item.delivered_at.isoformat() if item.delivered_at else None,
                    "bounced_at": item.bounced_at.isoformat() if item.bounced_at else None,
                }
                for item in deliveries
            ],
        }

    async def update_watch_group(self, session: AsyncSession, group_id: str, **updates: Any) -> WatchGroup:
        group = await session.get(WatchGroup, group_id)
        if group is None:
            raise ValueError("watch_group_not_found")

        for key, value in updates.items():
            if value is None:
                continue
            if key == "zip_code":
                value = self._normalize_task_zip_code(str(value), fallback=group.zip_code or self.settings.ZIP_CODE)
            if hasattr(group, key):
                setattr(group, key, value)

        if group.status == WatchTaskStatus.ACTIVE.value and group.next_run_at is None:
            group.next_run_at = utcnow() + timedelta(minutes=group.cadence_minutes)
        if group.status == WatchTaskStatus.ACTIVE.value:
            group.manual_intervention_required = False
            if group.health_status == HealthStatus.NEEDS_ATTENTION.value:
                group.health_status = HealthStatus.HEALTHY.value
            group.backoff_until = None
        await session.flush()
        return group

    async def compare_product_urls(
        self,
        *,
        submitted_urls: list[str],
        zip_code: str,
        session: AsyncSession | None = None,
    ) -> dict[str, Any]:
        cleaned = [str(item).strip() for item in submitted_urls if str(item).strip()]
        if len(cleaned) < 2:
            raise ValueError("at_least_two_urls_required")

        comparisons: list[dict[str, Any]] = []
        for submitted_url in cleaned:
            resolved = resolve_store_for_url(submitted_url)
            if not resolved.supported:
                comparisons.append(
                    {
                        "submitted_url": submitted_url,
                        "supported": False,
                        "store_key": None if resolved.store_key == "unsupported" else resolved.store_key,
                        "normalized_url": resolved.normalized_url,
                        "error_code": resolved.error_code or "unsupported_store_host",
                        "support_contract": self._build_compare_support_contract(
                            store_key=None if resolved.store_key == "unsupported" else resolved.store_key,
                            intake_status=(
                                "unsupported_store_host"
                                if resolved.store_key == "unsupported"
                                else "unsupported_store_path"
                            ),
                        ),
                    }
                )
                continue
            if session is not None and not await self._is_store_binding_enabled(session, resolved.store_key):
                comparisons.append(
                    {
                        "submitted_url": submitted_url,
                        "supported": False,
                        "store_key": resolved.store_key,
                        "normalized_url": resolved.product_url,
                        "error_code": "store_disabled",
                        "support_contract": self._build_compare_support_contract(
                            store_key=resolved.store_key,
                            intake_status="store_disabled",
                        ),
                    }
                )
                continue

            offer = await self._fetch_offer(resolved.product_url, resolved.store_key, zip_code=zip_code)
            if offer is None:
                comparisons.append(
                    {
                        "submitted_url": submitted_url,
                        "supported": True,
                        "store_key": resolved.store_key,
                        "normalized_url": resolved.product_url,
                        "fetch_succeeded": False,
                        "error_code": "offer_fetch_failed",
                        "support_contract": self._build_compare_support_contract(
                            store_key=resolved.store_key,
                            intake_status="offer_fetch_failed",
                        ),
                    }
                )
                continue

            size_hint = str(offer.unit_price_info.get("raw") or "").strip() or None
            brand_hint = str(offer.unit_price_info.get("brand") or "").strip() or None
            snapshot = build_candidate_snapshot(
                offer.title,
                brand=brand_hint,
                size_hint=size_hint,
                product_key=offer.product_key,
            )
            comparisons.append(
                {
                    "submitted_url": submitted_url,
                    "supported": True,
                    "store_key": resolved.store_key,
                    "normalized_url": resolved.product_url,
                    "fetch_succeeded": True,
                    "candidate_key": snapshot.candidate_key,
                    "brand_hint": snapshot.brand_hint,
                    "size_hint": snapshot.size_hint,
                    "match_snapshot": snapshot,
                    "offer": offer.to_dict(),
                    "support_contract": self._build_compare_support_contract(
                        store_key=resolved.store_key,
                        intake_status="supported",
                    ),
                }
            )

        successful = [item for item in comparisons if item.get("fetch_succeeded")]
        matches: list[dict[str, Any]] = []
        for index, left in enumerate(successful):
            for right in successful[index + 1 :]:
                details = build_match_details(left["match_snapshot"], right["match_snapshot"])
                matches.append(
                    {
                        "left_store_key": left["store_key"],
                        "left_product_key": left["offer"]["product_key"],
                        "right_store_key": right["store_key"],
                        "right_product_key": right["offer"]["product_key"],
                        **details,
                    }
                )

        matches.sort(key=lambda item: item["score"], reverse=True)
        for item in comparisons:
            item.pop("match_snapshot", None)
        compare_result = {
            "submitted_count": len(cleaned),
            "resolved_count": len(successful),
            "comparisons": comparisons,
            "matches": matches,
        }
        compare_evidence = self._build_compare_evidence_truth(
            submitted_urls=cleaned,
            zip_code=zip_code,
            compare_result=compare_result,
        )
        ai_explain = await self._build_compare_ai_explain(compare_evidence)
        return {
            **compare_result,
            "compare_evidence": compare_evidence,
            "recommended_next_step_hint": compare_evidence["recommended_next_step_hint"],
            "risk_notes": compare_evidence["risk_notes"],
            "risk_note_items": compare_evidence["risk_note_items"],
            "ai_explain": ai_explain,
        }

    async def create_compare_evidence_package(
        self,
        *,
        submitted_urls: list[str],
        zip_code: str,
        compare_result: dict[str, Any] | None = None,
        session: AsyncSession | None = None,
    ) -> dict[str, Any]:
        # Shadow artifacts must stay anchored to server-computed compare truth, not caller-supplied payloads.
        compare_result = await self.compare_product_urls(
            submitted_urls=submitted_urls,
            zip_code=zip_code,
            session=session,
        )
        self._validate_compare_preview_result(compare_result)
        package_id = str(uuid4())
        compare_evidence = compare_result.get("compare_evidence")
        if not isinstance(compare_evidence, dict):
            compare_evidence = self._build_compare_evidence_truth(
                submitted_urls=submitted_urls,
                zip_code=zip_code,
                compare_result=compare_result,
            )
        payload = self._build_compare_evidence_payload(
            package_id=package_id,
            compare_evidence=compare_evidence,
        )
        recommendation_shadow = self._build_compare_recommendation_shadow_payload(
            package_id=package_id,
            compare_evidence=compare_evidence,
        )
        artifact_dir = self._prepare_compare_evidence_dir(package_id)
        json_path = artifact_dir / "compare_evidence.json"
        html_path = artifact_dir / "compare_evidence.html"
        shadow_json_path = artifact_dir / "recommendation_shadow.json"
        shadow_html_path = artifact_dir / "recommendation_shadow.html"
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        html_path.write_text(self._render_compare_evidence_html(payload), encoding="utf-8")
        shadow_json_path.write_text(json.dumps(recommendation_shadow, ensure_ascii=False, indent=2), encoding="utf-8")
        shadow_html_path.write_text(
            self._render_compare_recommendation_shadow_html(recommendation_shadow),
            encoding="utf-8",
        )
        self._write_recommendation_replay_manifest_artifact()
        self._write_recommendation_shadow_monitoring_summary_artifact()
        return payload

    async def create_compare_evidence_artifact(
        self,
        session: AsyncSession,
        *,
        submitted_urls: list[str],
        zip_code: str,
    ) -> dict[str, Any]:
        return await self.create_compare_evidence_package(
            submitted_urls=submitted_urls,
            zip_code=zip_code,
            session=session,
        )

    async def list_compare_evidence_packages(self, *, limit: int = 10) -> dict[str, Any]:
        base_dir = self.settings.RUNS_DIR / "compare-evidence"
        if not base_dir.exists():
            return {"packages": []}
        packages: list[dict[str, Any]] = []
        for summary_path in base_dir.glob("*/compare_evidence.json"):
            try:
                payload = json.loads(summary_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if "summary" in payload:
                packages.append(payload["summary"])
        packages.sort(key=lambda item: item.get("created_at") or "", reverse=True)
        return {"packages": packages[:limit]}

    async def list_compare_evidence_artifacts(
        self,
        _session: AsyncSession | None = None,
        *,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        payload = await self.list_compare_evidence_packages(limit=limit)
        return list(payload.get("packages", []))

    async def record_recommendation_shadow_review(
        self,
        *,
        artifact_id: str,
        reviewer: str,
        decision: str,
        reason_code: str,
        outcome_category: str,
        observed_outcome: str,
        notes: str | None = None,
        follow_up_action: str | None = None,
        expected_verdict: str | None = None,
        actual_verdict: str | None = None,
        evidence_refs: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        allowed_decisions = {"confirmed", "overridden", "rejected"}
        allowed_outcomes = {
            "correct_verdict",
            "correct_abstention",
            "false_positive",
            "false_negative",
            "abstain_when_should_speak",
            "speak_when_should_abstain",
            "abstain_should_speak",
            "speak_should_abstain",
        }
        if decision not in allowed_decisions or outcome_category not in allowed_outcomes:
            raise ValueError("recommendation_shadow_review_invalid")
        if not reviewer.strip() or not reason_code.strip() or not observed_outcome.strip():
            raise ValueError("recommendation_shadow_review_invalid")

        shadow_payload = self._read_recommendation_shadow_payload(artifact_id)
        if shadow_payload is None:
            raise ValueError("recommendation_shadow_not_found")

        recommendation = shadow_payload.get("shadow_recommendation")
        if not isinstance(recommendation, dict):
            raise ValueError("recommendation_shadow_invalid")
        verdict_at_review_time = str(recommendation.get("verdict") or "").strip()
        if not verdict_at_review_time:
            raise ValueError("recommendation_shadow_invalid")

        recorded_at = utcnow().isoformat()
        normalized_outcome_category = self._normalize_recommendation_shadow_outcome_category(outcome_category)
        agreement_bucket = self._classify_recommendation_shadow_agreement(normalized_outcome_category)
        review_record = {
            "review_contract_version": "v1",
            "recorded_at": recorded_at,
            "artifact_id": str(shadow_payload.get("artifact_id") or artifact_id),
            "surface_anchor": str(shadow_payload.get("surface_anchor") or "compare_preview"),
            "shadow_contract_version": str(shadow_payload.get("shadow_contract_version") or "v1"),
            "reviewer": reviewer.strip(),
            "decision": decision,
            "reason_code": reason_code.strip(),
            "outcome_category": normalized_outcome_category,
            "agreement_bucket": agreement_bucket,
            "verdict_at_review_time": verdict_at_review_time,
            "expected_verdict": expected_verdict,
            "actual_verdict": actual_verdict or verdict_at_review_time,
            "observed_outcome": observed_outcome.strip(),
            "notes": notes.strip() if notes else None,
            "follow_up_action": follow_up_action.strip() if follow_up_action else None,
            "evidence_refs": list(evidence_refs or []),
            "deterministic_truth_anchor": dict(shadow_payload.get("deterministic_truth_anchor") or {}),
        }

        review_log_path = self._recommendation_shadow_review_log_path()
        review_log_path.parent.mkdir(parents=True, exist_ok=True)
        with review_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(review_record, ensure_ascii=False))
            handle.write("\n")

        shadow_payload["review"] = {
            "state": decision,
            "owner": reviewer.strip(),
            "reason_code": reason_code.strip(),
            "notes": notes.strip() if notes else None,
            "observed_outcome": observed_outcome.strip(),
            "recorded_at": recorded_at,
            "outcome_category": normalized_outcome_category,
            "follow_up_action": follow_up_action.strip() if follow_up_action else None,
        }
        monitoring = dict(shadow_payload.get("monitoring") or {})
        monitoring["review_state"] = decision
        monitoring["review_reason_code"] = reason_code.strip()
        monitoring["outcome_category"] = normalized_outcome_category
        monitoring["agreement_bucket"] = agreement_bucket
        monitoring["review_recorded_at"] = recorded_at
        shadow_payload["monitoring"] = monitoring
        shadow_payload["review_log_path"] = str(review_log_path)

        shadow_path = self._recommendation_shadow_artifact_path(artifact_id)
        if shadow_path is None:
            raise ValueError("recommendation_shadow_not_found")
        shadow_path.write_text(json.dumps(shadow_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        shadow_html_path = shadow_path.with_name("recommendation_shadow.html")
        shadow_html_path.write_text(self._render_compare_recommendation_shadow_html(shadow_payload), encoding="utf-8")
        self._write_recommendation_replay_manifest_artifact()
        self._write_recommendation_shadow_monitoring_summary_artifact()
        return review_record

    async def get_compare_evidence_package(self, package_id: str) -> dict[str, Any]:
        payload = self._read_compare_evidence_payload(package_id)
        if payload is None:
            raise ValueError("compare_evidence_package_not_found")
        return payload

    async def create_recommendation_shadow_monitoring_summary(self) -> dict[str, Any]:
        return self._write_recommendation_shadow_monitoring_summary_artifact()

    async def create_recommendation_replay_manifest(self) -> dict[str, Any]:
        return self._write_recommendation_replay_manifest_artifact()

    async def get_compare_evidence_artifact(
        self,
        _session: AsyncSession | None,
        artifact_id: str,
    ) -> dict[str, Any]:
        return await self.get_compare_evidence_package(artifact_id)

    async def get_compare_evidence_package_html(self, package_id: str) -> str:
        artifact_dir = self.settings.RUNS_DIR / "compare-evidence" / package_id
        html_path = artifact_dir / "compare_evidence.html"
        if not html_path.is_file():
            raise ValueError("compare_evidence_package_not_found")
        return html_path.read_text(encoding="utf-8")

    async def run_watch_task(self, session: AsyncSession, task_id: str, *, triggered_by: str = "manual") -> TaskRun:
        task = await session.get(WatchTask, task_id)
        if task is None:
            raise ValueError("watch_task_not_found")
        if task.status == WatchTaskStatus.PAUSED.value:
            raise ValueError("watch_task_paused")
        await self._ensure_watch_task_not_running(session, task.id)

        target = await session.get(WatchTarget, task.watch_target_id)
        if target is None:
            raise ValueError("watch_target_not_found")

        owner = await session.get(User, task.user_id)
        if owner is None:
            raise ValueError("owner_not_found")
        preference = await self._ensure_owner_preference(session, owner)
        zip_code = self._normalize_task_zip_code(
            task.zip_code,
            fallback=preference.default_zip_code or self.settings.ZIP_CODE,
        )

        previous_observation = await session.scalar(
            select(PriceObservation)
            .where(PriceObservation.watch_task_id == task.id)
            .order_by(desc(PriceObservation.observed_at))
            .limit(1)
        )
        history_prices = list(
            (
                await session.scalars(
                    select(PriceObservation.listed_price)
                    .where(PriceObservation.watch_task_id == task.id)
                    .order_by(desc(PriceObservation.observed_at))
                    .limit(max(int(self.settings.ANOMALY_MAX_SAMPLES), 10))
                )
            ).all()
        )

        run = TaskRun(
            watch_task_id=task.id,
            triggered_by=triggered_by,
            status=TaskRunStatus.RUNNING.value,
            started_at=utcnow(),
            engine_store_key=target.store_key,
        )
        session.add(run)
        await session.flush()
        await session.commit()

        try:
            self._prepare_task_run_artifact_dir(task, run)
            if not await self._is_store_binding_enabled(session, target.store_key):
                raise ValueError("store_disabled")
            offer = await self._fetch_offer(target.product_url, target.store_key, zip_code=zip_code)
            if offer is None:
                raise ValueError("offer_not_parsed")

            run.engine_product_key = offer.product_key
            observation = PriceObservation(
                watch_task_id=task.id,
                task_run_id=run.id,
                listed_price=offer.price,
                original_price=offer.original_price,
                currency=offer.context.currency,
                availability="available",
                title_snapshot=offer.title,
                unit_price_raw=str(offer.unit_price_info.get("raw", "")) or None,
                source_url=offer.url,
                observed_at=offer.fetch_at,
                parser_version=f"{target.store_key}-v1",
            )
            session.add(observation)

            cashback_amount = 0.0
            cashback_quote = await self._fetch_cashback_quote(task, target)
            if cashback_quote is not None:
                session.add(cashback_quote)
                if cashback_quote.rate_type == "percent":
                    cashback_amount = round(offer.price * cashback_quote.rate_value / 100.0, 2)
                else:
                    cashback_amount = cashback_quote.rate_value
            effective_price = max(offer.price - cashback_amount, 0.0)
            signal = self._build_task_price_signal(
                history_prices=history_prices,
                previous_observation=previous_observation,
                observation=observation,
                effective_price=effective_price,
            )
            session.add(
                EffectivePriceSnapshot(
                    watch_task_id=task.id,
                    task_run_id=run.id,
                    listed_price=offer.price,
                    cashback_amount=cashback_amount,
                    effective_price=effective_price,
                    currency=offer.context.currency,
                    previous_listed_price=signal["previous_listed_price"],
                    delta_amount=signal["delta_amount"],
                    delta_pct=signal["delta_pct"],
                    is_new_low=signal["is_new_low"],
                    anomaly_reason=signal["anomaly_reason"],
                    decision_reason=signal["decision_reason"],
                    computed_at=utcnow(),
                )
            )

            self._apply_task_success_state(task)
            run.status = TaskRunStatus.SUCCEEDED.value
            run.finished_at = utcnow()
            await session.flush()

            deliveries: list[DeliveryEvent] = []
            if self._should_notify(task, previous_observation, observation, effective_price):
                deliveries = await self._dispatch_notifications(session, task, run, observation, effective_price)
            if any(item.status == DeliveryStatus.FAILED.value for item in deliveries):
                task.health_status = HealthStatus.DEGRADED.value
                task.last_failure_kind = FailureKind.DELIVERY_FAILED.value
                task.last_error_code = FailureKind.DELIVERY_FAILED.value
                task.last_error_message = "delivery_failed"
                await session.flush()
            self._safe_write_task_run_artifact(
                task=task,
                target=target,
                run=run,
                observation=observation,
                cashback_quote=cashback_quote,
                effective_price=effective_price,
                deliveries=deliveries,
            )
            return run
        except SkipParse as exc:
            run.status = TaskRunStatus.BLOCKED.value
            run.error_code = exc.reason.value
            run.error_message = exc.reason.value
            run.finished_at = utcnow()
            self._apply_task_failure_state(
                task,
                failure_kind=FailureKind.BLOCKED,
                error_code=exc.reason.value,
                error_message=exc.reason.value,
            )
            await session.flush()
            self._safe_write_task_run_artifact(task=task, target=target, run=run)
            return run
        except ValueError as exc:
            if str(exc) == "store_disabled":
                run.status = TaskRunStatus.BLOCKED.value
                run.error_code = "store_disabled"
                run.error_message = "store_disabled"
                run.finished_at = utcnow()
                self._apply_task_failure_state(
                    task,
                    failure_kind=FailureKind.BLOCKED,
                    error_code="store_disabled",
                    error_message="store_disabled",
                )
                await session.flush()
                self._safe_write_task_run_artifact(task=task, target=target, run=run)
                return run
            raise
        except Exception as exc:
            self.logger.exception("Watch task run failed.")
            error_code, error_message = normalize_unexpected_runtime_error(exc)
            run.status = TaskRunStatus.FAILED.value
            run.error_code = error_code
            run.error_message = error_message
            run.finished_at = utcnow()
            self._apply_task_failure_state(
                task,
                failure_kind=FailureKind.FETCH_FAILED
                if error_code == "offer_not_parsed"
                else FailureKind.UNEXPECTED_RUNTIME_ERROR,
                error_code=error_code,
                error_message=error_message,
            )
            await session.flush()
            self._safe_write_task_run_artifact(task=task, target=target, run=run)
            return run

    async def run_watch_group(
        self,
        session: AsyncSession,
        group_id: str,
        *,
        triggered_by: str = "manual",
    ) -> WatchGroupRun:
        group = await session.scalar(select(WatchGroup).where(WatchGroup.id == group_id).with_for_update())
        if group is None:
            raise ValueError("watch_group_not_found")
        if group.status == WatchTaskStatus.PAUSED.value:
            raise ValueError("watch_group_paused")
        await self._ensure_watch_group_not_running(session, group.id)

        members = list(
            (
                await session.scalars(
                    select(WatchGroupMember)
                    .where(WatchGroupMember.watch_group_id == group.id, WatchGroupMember.is_active.is_(True))
                    .order_by(desc(WatchGroupMember.created_at))
                )
            ).all()
        )
        if not members:
            raise ValueError("watch_group_has_no_members")

        previous_run = await session.scalar(
            select(WatchGroupRun)
            .where(WatchGroupRun.watch_group_id == group.id)
            .order_by(desc(WatchGroupRun.created_at))
            .limit(1)
        )

        run = WatchGroupRun(
            watch_group_id=group.id,
            triggered_by=triggered_by,
            status=TaskRunStatus.RUNNING.value,
            started_at=utcnow(),
        )
        session.add(run)
        await session.flush()
        await session.commit()

        try:
            self._prepare_watch_group_run_artifact_dir(group, run)
            results: list[dict[str, Any]] = []
            for member in members:
                target = await session.get(WatchTarget, member.watch_target_id)
                if target is None:
                    results.append(
                        {
                            "member_id": member.id,
                            "status": TaskRunStatus.FAILED.value,
                            "error_code": "watch_target_not_found",
                            "error_message": "watch_target_not_found",
                        }
                    )
                    continue
                if not await self._is_store_binding_enabled(session, target.store_key):
                    results.append(
                        {
                            "member_id": member.id,
                            "watch_target_id": target.id,
                            "store_key": target.store_key,
                            "title_snapshot": member.title_snapshot,
                            "candidate_key": member.candidate_key,
                            "status": TaskRunStatus.BLOCKED.value,
                            "error_code": "store_disabled",
                            "error_message": "store_disabled",
                        }
                    )
                    continue

                try:
                    offer = await self._fetch_offer(target.product_url, target.store_key, zip_code=group.zip_code)
                    if offer is None:
                        raise ValueError("offer_not_parsed")
                    cashback_quote = await self._fetch_cashback_quote_for_target(target.store_key, target.product_url)
                    cashback_amount = 0.0
                    if cashback_quote is not None:
                        if cashback_quote["rate_type"] == "percent":
                            cashback_amount = round(offer.price * float(cashback_quote["rate_value"]) / 100.0, 2)
                        else:
                            cashback_amount = float(cashback_quote["rate_value"])
                    effective_price = max(offer.price - cashback_amount, 0.0)
                    results.append(
                        {
                            "member_id": member.id,
                            "watch_target_id": target.id,
                            "store_key": target.store_key,
                            "title_snapshot": offer.title,
                            "candidate_key": member.candidate_key,
                            "listed_price": offer.price,
                            "effective_price": effective_price,
                            "cashback_amount": cashback_amount,
                            "source_url": offer.url,
                            "observed_at": offer.fetch_at.isoformat(),
                            "status": TaskRunStatus.SUCCEEDED.value,
                            "cashback_quote": cashback_quote,
                        }
                    )
                except SkipParse as exc:
                    results.append(
                        {
                            "member_id": member.id,
                            "watch_target_id": target.id,
                            "store_key": target.store_key,
                            "title_snapshot": member.title_snapshot,
                            "candidate_key": member.candidate_key,
                            "status": TaskRunStatus.BLOCKED.value,
                            "error_code": exc.reason.value,
                            "error_message": exc.reason.value,
                        }
                    )
                except Exception as exc:
                    self.logger.exception("Watch group member run failed.")
                    error_code, error_message = normalize_unexpected_runtime_error(exc)
                    results.append(
                        {
                            "member_id": member.id,
                            "watch_target_id": target.id,
                            "store_key": target.store_key,
                            "title_snapshot": member.title_snapshot,
                            "candidate_key": member.candidate_key,
                            "status": TaskRunStatus.FAILED.value,
                            "error_code": error_code,
                            "error_message": error_message,
                        }
                    )

            successful = [item for item in results if item["status"] == TaskRunStatus.SUCCEEDED.value]
            if not successful:
                run.member_results_json = {"results": results}
                run.status = (
                    TaskRunStatus.BLOCKED.value
                    if any(item["status"] == TaskRunStatus.BLOCKED.value for item in results)
                    else TaskRunStatus.FAILED.value
                )
                run.error_code = "watch_group_no_successful_candidates"
                run.error_message = "watch_group_no_successful_candidates"
                run.finished_at = utcnow()
                self._apply_watch_group_failure_state(
                    group,
                    failure_kind=FailureKind.BLOCKED
                    if run.status == TaskRunStatus.BLOCKED.value
                    else FailureKind.FETCH_FAILED,
                    error_code=run.error_code,
                    error_message=run.error_message,
                )
                await session.flush()
                self._safe_write_watch_group_run_artifact(group=group, run=run, member_results=results, deliveries=[])
                return run

            successful.sort(
                key=lambda item: (
                    float(item["effective_price"]),
                    float(item["listed_price"]),
                    str(item["store_key"]),
                )
            )
            winner = successful[0]
            runner_up = successful[1] if len(successful) > 1 else None
            decision_reason = self._build_group_decision_reason(previous_run, winner, runner_up)

            run.status = TaskRunStatus.SUCCEEDED.value
            run.finished_at = utcnow()
            run.member_results_json = {"results": results}
            run.winner_member_id = str(winner["member_id"])
            run.winner_effective_price = float(winner["effective_price"])
            run.runner_up_member_id = str(runner_up["member_id"]) if runner_up is not None else None
            run.runner_up_effective_price = (
                float(runner_up["effective_price"]) if runner_up is not None else None
            )
            run.price_spread = (
                round(float(runner_up["effective_price"]) - float(winner["effective_price"]), 2)
                if runner_up is not None
                else None
            )
            run.decision_reason = decision_reason

            self._apply_watch_group_success_state(group)
            deliveries: list[DeliveryEvent] = []
            if self._should_notify_group(group, previous_run, winner):
                deliveries = await self._dispatch_group_notifications(
                    session,
                    group,
                    run,
                    winner,
                    decision_reason=decision_reason,
                )
            if any(item.status == DeliveryStatus.FAILED.value for item in deliveries):
                group.health_status = HealthStatus.DEGRADED.value
                group.last_failure_kind = FailureKind.DELIVERY_FAILED.value
                group.last_error_code = FailureKind.DELIVERY_FAILED.value
                group.last_error_message = "delivery_failed"
            await session.flush()
            self._safe_write_watch_group_run_artifact(
                group=group,
                run=run,
                member_results=results,
                deliveries=deliveries,
            )
            return run
        except Exception as exc:
            self.logger.exception("Watch group run failed.")
            error_code, error_message = normalize_unexpected_runtime_error(exc)
            run.status = TaskRunStatus.FAILED.value
            run.error_code = error_code
            run.error_message = error_message
            run.finished_at = utcnow()
            self._apply_watch_group_failure_state(
                group,
                failure_kind=FailureKind.UNEXPECTED_RUNTIME_ERROR,
                error_code=error_code,
                error_message=error_message,
            )
            await session.flush()
            self._safe_write_watch_group_run_artifact(group=group, run=run, member_results=[], deliveries=[])
            return run

    async def process_due_tasks(self) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            due_tasks = list(
                (
                    await session.scalars(
                        select(WatchTask).where(
                            WatchTask.status == WatchTaskStatus.ACTIVE.value,
                            WatchTask.next_run_at.is_not(None),
                            WatchTask.next_run_at <= utcnow(),
                            WatchTask.manual_intervention_required.is_(False),
                            or_(WatchTask.backoff_until.is_(None), WatchTask.backoff_until <= utcnow()),
                        )
                    )
                ).all()
            )

        results: list[dict[str, Any]] = []
        for task in due_tasks:
            async with self.session_factory() as session:
                run = await self.run_watch_task(session, task.id, triggered_by="scheduler")
                await session.commit()
                results.append({"task_id": task.id, "run_id": run.id, "status": run.status})
        return results

    async def process_due_watch_groups(self) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            due_groups = list(
                (
                    await session.scalars(
                        select(WatchGroup).where(
                            WatchGroup.status == WatchTaskStatus.ACTIVE.value,
                            WatchGroup.next_run_at.is_not(None),
                            WatchGroup.next_run_at <= utcnow(),
                            WatchGroup.manual_intervention_required.is_(False),
                            or_(WatchGroup.backoff_until.is_(None), WatchGroup.backoff_until <= utcnow()),
                        )
                    )
                ).all()
            )

        results: list[dict[str, Any]] = []
        for group in due_groups:
            async with self.session_factory() as session:
                run = await self.run_watch_group(session, group.id, triggered_by="scheduler")
                await session.commit()
                results.append({"group_id": group.id, "run_id": run.id, "status": run.status})
        return results

    async def _build_task_summary(self, session: AsyncSession, task: WatchTask) -> dict[str, Any]:
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

    async def _build_watch_group_summary(self, session: AsyncSession, group: WatchGroup) -> dict[str, Any]:
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

    async def _build_task_attention_item(self, session: AsyncSession, task: WatchTask) -> dict[str, Any]:
        summary = await self._build_task_summary(session, task)
        reason, recommended_action = self._build_attention_guidance(
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

    async def _build_watch_group_attention_item(
        self,
        session: AsyncSession,
        group: WatchGroup,
    ) -> dict[str, Any]:
        summary = await self._build_watch_group_summary(session, group)
        reason, recommended_action = self._build_attention_guidance(
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

    async def _fetch_offer(self, product_url: str, store_key: str, *, zip_code: str) -> Offer | None:
        adapter_cls = STORE_REGISTRY.get(store_key)
        if adapter_cls is None:
            raise ValueError("unsupported_target")

        copied = self.settings.model_copy(update={"ZIP_CODE": zip_code})
        retry_budget = RetryBudget(copied.PLAYWRIGHT_RETRY_BUDGET) if copied.PLAYWRIGHT_RETRY_BUDGET > 0 else None
        async with PlaywrightClient(
            headless=copied.PLAYWRIGHT_HEADLESS,
            storage_state_path=copied.build_storage_state_path(zip_code),
            proxy_server=copied.PROXY_SERVER or None,
            block_stylesheets=copied.PLAYWRIGHT_BLOCK_STYLESHEETS,
            retry_budget=retry_budget,
            runs_dir=copied.RUNS_DIR,
        ) as client:
            adapter = adapter_cls(client, copied)
            return await adapter.parse_product(product_url)

    async def _fetch_cashback_quote(self, task: WatchTask, target: WatchTarget) -> CashbackQuote | None:
        quote = await self._fetch_cashback_quote_for_target(target.store_key, target.product_url)
        if quote is None:
            return None
        return CashbackQuote(
            watch_task_id=task.id,
            provider=str(quote["provider"]),
            merchant_key=str(quote["merchant_key"]),
            rate_type=str(quote["rate_type"]),
            rate_value=float(quote["rate_value"]),
            conditions_text=quote["conditions_text"],
            source_url=str(quote["source_url"]),
            confidence=float(quote["confidence"]),
            collected_at=utcnow(),
        )

    async def _persist_compare_handoff(
        self,
        session: AsyncSession,
        *,
        task: WatchTask,
        target: WatchTarget,
        compare_handoff: dict[str, Any],
    ) -> None:
        store_key = str(compare_handoff.get("store_key") or "").strip()
        if store_key and store_key != target.store_key:
            raise ValueError("compare_handoff_store_mismatch")

        title_snapshot = str(compare_handoff.get("title_snapshot") or "").strip()
        if not title_snapshot:
            raise ValueError("compare_handoff_missing_title")

        snapshot = build_candidate_snapshot(
            title_snapshot,
            brand=compare_handoff.get("brand_hint"),
            size_hint=compare_handoff.get("size_hint"),
        )
        if not snapshot.normalized_title:
            raise ValueError("compare_handoff_invalid_candidate")

        canonical_matches = list(
            (
                await session.scalars(
                    select(CanonicalProduct).where(CanonicalProduct.normalized_title == snapshot.normalized_title)
                )
            ).all()
        )
        canonical = next(
            (
                item
                for item in canonical_matches
                if item.brand == snapshot.brand_hint and item.size_hint == snapshot.size_hint
            ),
            None,
        )
        if canonical is None:
            canonical = CanonicalProduct(
                normalized_title=snapshot.normalized_title,
                brand=snapshot.brand_hint,
                size_hint=snapshot.size_hint,
                created_at=utcnow(),
            )
            session.add(canonical)
            await session.flush()

        candidate = await session.scalar(
            select(ProductCandidate)
            .where(ProductCandidate.watch_task_id == task.id)
            .order_by(desc(ProductCandidate.similarity_score), desc(ProductCandidate.id))
            .limit(1)
        )
        if candidate is None:
            candidate = ProductCandidate(
                canonical_product_id=canonical.id,
                watch_task_id=task.id,
                merchant_key=target.store_key,
                title_snapshot=title_snapshot,
                source_url=target.product_url,
                similarity_score=100.0,
            )
            session.add(candidate)
            await session.flush()
            return

        candidate.canonical_product_id = canonical.id
        candidate.merchant_key = target.store_key
        candidate.title_snapshot = title_snapshot
        candidate.source_url = target.product_url
        candidate.similarity_score = 100.0
        await session.flush()

    async def _get_compare_context(self, session: AsyncSession, task_id: str) -> dict[str, Any] | None:
        candidate = await session.scalar(
            select(ProductCandidate)
            .where(ProductCandidate.watch_task_id == task_id)
            .order_by(desc(ProductCandidate.similarity_score), desc(ProductCandidate.id))
            .limit(1)
        )
        if candidate is None:
            return None

        canonical = await session.get(CanonicalProduct, candidate.canonical_product_id)
        brand_hint = canonical.brand if canonical is not None else None
        size_hint = canonical.size_hint if canonical is not None else None
        return {
            "candidate_key": build_candidate_key(
                candidate.title_snapshot,
                brand=brand_hint,
                size_hint=size_hint,
            ),
            "title_snapshot": candidate.title_snapshot,
            "merchant_key": candidate.merchant_key,
            "brand_hint": brand_hint,
            "size_hint": size_hint,
            "similarity_score": candidate.similarity_score,
            "canonical_product_id": canonical.id if canonical is not None else None,
            "source_url": candidate.source_url,
        }

    async def _resolve_or_create_watch_target(
        self,
        session: AsyncSession,
        owner_id: str,
        submitted_url: str,
    ) -> WatchTarget:
        resolved = resolve_store_for_url(submitted_url)
        if not resolved.supported:
            raise ValueError(resolved.error_code or "unsupported_store_host")
        if not await self._is_store_binding_enabled(session, resolved.store_key):
            raise ValueError("store_disabled")

        target = await session.scalar(
            select(WatchTarget).where(
                WatchTarget.user_id == owner_id,
                WatchTarget.normalized_url == resolved.normalized_url,
            )
        )
        if target is None:
            target = WatchTarget(
                user_id=owner_id,
                submitted_url=submitted_url,
                normalized_url=resolved.normalized_url,
                product_url=resolved.product_url,
                store_key=resolved.store_key,
                target_type="product_url",
                resolution_status=ResolutionStatus.RESOLVED.value,
            )
            session.add(target)
            await session.flush()
        return target

    async def _is_store_binding_enabled(self, session: AsyncSession, store_key: str) -> bool:
        binding = await session.scalar(
            select(StoreAdapterBinding).where(StoreAdapterBinding.store_key == store_key).limit(1)
        )
        if binding is None:
            return True
        return bool(binding.enabled)

    def _should_notify(
        self,
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

    def _should_notify_group(
        self,
        group: WatchGroup,
        previous_run: WatchGroupRun | None,
        winner: dict[str, Any],
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

    async def _dispatch_notifications(
        self,
        session: AsyncSession,
        task: WatchTask,
        run: TaskRun,
        observation: PriceObservation,
        effective_price: float,
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
            if latest_delivery is not None and latest_delivery.created_at >= utcnow() - timedelta(minutes=rule.cooldown_minutes):
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
                metadata={"subject_date": utcnow().strftime("%Y-%m-%d")},
            )
            event = DeliveryEvent(
                watch_task_id=task.id,
                task_run_id=run.id,
                provider="unknown",
                channel="email",
                recipient=rule.recipient_email,
                template_key=rule.template_key,
                status=DeliveryStatus.QUEUED.value,
                created_at=utcnow(),
            )
            session.add(event)
            await session.flush()
            try:
                result = await self.email_provider.send(payload) if self.email_provider is not None else None
                if result is None:
                    raise RuntimeError("email_provider_unavailable")
                event.provider = result.provider
                event.status = DeliveryStatus.SENT.value
                event.provider_message_id = result.message_id
                event.provider_payload_json = result.payload
                event.sent_at = utcnow()
            except Exception as exc:
                event.status = DeliveryStatus.FAILED.value
                event.provider = "smtp"
                event.provider_payload_json = {"error": str(exc)}
            await session.flush()
            deliveries.append(event)
        return deliveries

    async def _dispatch_group_notifications(
        self,
        session: AsyncSession,
        group: WatchGroup,
        run: WatchGroupRun,
        winner: dict[str, Any],
        *,
        decision_reason: str,
    ) -> list[DeliveryEvent]:
        if not group.notifications_enabled:
            return []

        latest_delivery = await session.scalar(
            select(DeliveryEvent)
            .where(DeliveryEvent.watch_group_id == group.id, DeliveryEvent.recipient == group.recipient_email)
            .order_by(desc(DeliveryEvent.created_at))
            .limit(1)
        )
        if latest_delivery is not None and latest_delivery.created_at >= utcnow() - timedelta(minutes=group.cooldown_minutes):
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
            metadata={"subject_date": utcnow().strftime("%Y-%m-%d")},
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
            created_at=utcnow(),
        )
        session.add(event)
        await session.flush()
        try:
            result = await self.email_provider.send(payload) if self.email_provider is not None else None
            if result is None:
                raise RuntimeError("email_provider_unavailable")
            event.provider = result.provider
            event.status = DeliveryStatus.SENT.value
            event.provider_message_id = result.message_id
            event.provider_payload_json = result.payload
            event.sent_at = utcnow()
        except Exception as exc:
            event.status = DeliveryStatus.FAILED.value
            event.provider = "smtp"
            event.provider_payload_json = {"error": str(exc)}
        await session.flush()
        return [event]

    def _prepare_task_run_artifact_dir(self, task: WatchTask, run: TaskRun) -> Path:
        artifact_dir = self.settings.RUNS_DIR / "watch-tasks" / task.id / run.id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        run.artifact_run_dir = str(artifact_dir)
        return artifact_dir

    def _prepare_watch_group_run_artifact_dir(self, group: WatchGroup, run: WatchGroupRun) -> Path:
        artifact_dir = self.settings.RUNS_DIR / "watch-groups" / group.id / run.id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        run.artifact_run_dir = str(artifact_dir)
        return artifact_dir

    def _read_artifact_evidence(self, run: TaskRun) -> dict[str, Any] | None:
        if not run.artifact_run_dir:
            return None

        artifact_dir = Path(run.artifact_run_dir)
        summary_path = artifact_dir / "task_run_summary.json"
        evidence: dict[str, Any] = {
            "summary_path": str(summary_path),
            "summary_exists": summary_path.is_file(),
            "captured_at": run.finished_at.isoformat() if run.finished_at else (run.started_at.isoformat() if run.started_at else None),
            "title_snapshot": None,
            "listed_price": None,
            "effective_price": None,
            "source_url": None,
            "delivery_count": 0,
            "latest_delivery_status": None,
            "has_cashback_quote": False,
        }
        if not summary_path.is_file():
            return evidence

        try:
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self.logger.exception("Failed to read task run artifact summary.")
            return evidence

        observation = payload.get("observation") or {}
        deliveries = payload.get("delivery_events") or []
        evidence.update(
            {
                "title_snapshot": observation.get("title_snapshot"),
                "listed_price": observation.get("listed_price"),
                "effective_price": payload.get("effective_price"),
                "source_url": observation.get("source_url"),
                "delivery_count": len(deliveries),
                "latest_delivery_status": deliveries[0].get("status") if deliveries else None,
                "has_cashback_quote": payload.get("cashback_quote") is not None,
            }
        )
        return evidence

    def _prepare_compare_evidence_dir(self, package_id: str) -> Path:
        artifact_dir = self.settings.RUNS_DIR / "compare-evidence" / package_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        return artifact_dir

    def _prepare_recommendation_shadow_monitoring_dir(self) -> Path:
        artifact_dir = self.settings.RUNS_DIR / "compare-evidence" / "_shadow-monitoring"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        return artifact_dir

    def _recommendation_replay_manifest_path(self) -> Path:
        return self._prepare_recommendation_shadow_monitoring_dir() / "recommendation_replay_manifest.json"

    def _write_recommendation_replay_manifest_artifact(self) -> dict[str, Any]:
        payload = self._build_recommendation_replay_manifest_payload()
        json_path = self._recommendation_replay_manifest_path()
        payload["artifact_path"] = str(json_path)
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    def _write_recommendation_shadow_monitoring_summary_artifact(self) -> dict[str, Any]:
        payload = self._build_recommendation_shadow_monitoring_summary_payload()
        artifact_dir = self._prepare_recommendation_shadow_monitoring_dir()
        json_path = artifact_dir / "recommendation_shadow_summary.json"
        html_path = artifact_dir / "recommendation_shadow_summary.html"
        payload["artifact_path"] = str(json_path)
        payload["html_path"] = str(html_path)
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        html_path.write_text(self._render_recommendation_shadow_monitoring_summary_html(payload), encoding="utf-8")
        return payload

    def _normalize_compare_evidence_package_id(self, package_id: str) -> str | None:
        try:
            return str(UUID(str(package_id)))
        except ValueError:
            return None

    def _read_compare_evidence_payload(self, package_id: str) -> dict[str, Any] | None:
        normalized_id = self._normalize_compare_evidence_package_id(package_id)
        if normalized_id is None:
            return None
        payload_path = self.settings.RUNS_DIR / "compare-evidence" / normalized_id / "compare_evidence.json"
        if not payload_path.is_file():
            return None
        try:
            return json.loads(payload_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self.logger.exception("Failed to read compare evidence package.")
            return None

    def _recommendation_shadow_artifact_path(self, artifact_id: str) -> Path | None:
        normalized_id = self._normalize_compare_evidence_package_id(artifact_id)
        if normalized_id is None:
            return None
        shadow_path = self.settings.RUNS_DIR / "compare-evidence" / normalized_id / "recommendation_shadow.json"
        return shadow_path if shadow_path.is_file() else None

    def _read_recommendation_shadow_payload(self, artifact_id: str) -> dict[str, Any] | None:
        shadow_path = self._recommendation_shadow_artifact_path(artifact_id)
        if shadow_path is None:
            return None
        try:
            payload = json.loads(shadow_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self.logger.exception("Failed to read recommendation shadow artifact.")
            return None
        return payload if isinstance(payload, dict) else None

    def _recommendation_shadow_review_log_path(self) -> Path:
        return self.settings.RUNS_DIR / "compare-evidence" / "recommendation_shadow_reviews.ndjson"

    def _load_recommendation_shadow_review_records(self) -> list[dict[str, Any]]:
        review_log_path = self._recommendation_shadow_review_log_path()
        if not review_log_path.is_file():
            return []
        records: list[dict[str, Any]] = []
        try:
            for line in review_log_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                payload = json.loads(line)
                if isinstance(payload, dict):
                    records.append(payload)
        except (OSError, json.JSONDecodeError):
            self.logger.exception("Failed to read recommendation shadow review log.")
            return []
        return records

    def _build_recommendation_replay_manifest_payload(self) -> dict[str, Any]:
        base_dir = self.settings.RUNS_DIR / "compare-evidence"
        latest_review_by_artifact: dict[str, dict[str, Any]] = {}
        for record in self._load_recommendation_shadow_review_records():
            artifact_id = str(record.get("artifact_id") or "").strip()
            if artifact_id:
                latest_review_by_artifact[artifact_id] = record

        entries: list[dict[str, Any]] = []
        total_candidates = 0
        included_count = 0
        skipped_count = 0

        if base_dir.exists():
            for package_dir in sorted(
                (path for path in base_dir.iterdir() if path.is_dir() and not path.name.startswith("_")),
                key=lambda path: path.name,
            ):
                compare_path = package_dir / "compare_evidence.json"
                if not compare_path.is_file():
                    continue
                total_candidates += 1
                artifact_id = package_dir.name
                shadow_path = package_dir / "recommendation_shadow.json"
                compare_html_path = package_dir / "compare_evidence.html"
                shadow_html_path = package_dir / "recommendation_shadow.html"
                entry: dict[str, Any] = {
                    "artifact_id": artifact_id,
                    "included": False,
                    "skip_reason": None,
                    "replay_source": {
                        "surface_anchor": "unknown",
                        "compare_evidence_path": str(compare_path),
                        "compare_evidence_html_path": str(compare_html_path),
                        "shadow_artifact_path": str(shadow_path),
                        "shadow_html_path": str(shadow_html_path),
                        "review_log_path": str(self._recommendation_shadow_review_log_path()),
                    },
                }

                try:
                    compare_payload = json.loads(compare_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    entry["skip_reason"] = "invalid_compare_evidence_payload"
                    entries.append(entry)
                    skipped_count += 1
                    continue

                if not shadow_path.is_file():
                    entry["skip_reason"] = "missing_shadow_artifact"
                    entries.append(entry)
                    skipped_count += 1
                    continue

                try:
                    shadow_payload = json.loads(shadow_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    entry["skip_reason"] = "invalid_shadow_artifact"
                    entries.append(entry)
                    skipped_count += 1
                    continue

                if not self._is_valid_recommendation_shadow_payload(shadow_payload):
                    entry["skip_reason"] = "shadow_contract_invalid"
                    entries.append(entry)
                    skipped_count += 1
                    continue

                if str(shadow_payload.get("shadow_contract_version") or "") != "v1":
                    entry["skip_reason"] = "unsupported_shadow_contract_version"
                    entries.append(entry)
                    skipped_count += 1
                    continue

                surface_anchor = str(shadow_payload.get("surface_anchor") or "").strip()
                if surface_anchor not in self._allowed_recommendation_shadow_surface_anchors():
                    entry["skip_reason"] = "unsupported_surface_anchor"
                    entries.append(entry)
                    skipped_count += 1
                    continue

                deterministic_truth_anchor = dict(shadow_payload.get("deterministic_truth_anchor") or {})
                if str(deterministic_truth_anchor.get("artifact_path") or "") != str(compare_path):
                    entry["skip_reason"] = "deterministic_truth_anchor_mismatch"
                    entries.append(entry)
                    skipped_count += 1
                    continue

                compare_summary = dict(compare_payload.get("summary") or {})
                recommendation = dict(shadow_payload.get("shadow_recommendation") or {})
                monitoring = dict(shadow_payload.get("monitoring") or {})
                review = dict(shadow_payload.get("review") or {})
                review_record = latest_review_by_artifact.get(str(shadow_payload.get("artifact_id") or artifact_id), {})

                entry.update(
                    {
                        "included": True,
                        "shadow_contract_version": str(shadow_payload.get("shadow_contract_version") or "v1"),
                        "surface_anchor": surface_anchor,
                        "status": str(shadow_payload.get("status") or "unknown"),
                        "verdict": str(recommendation.get("verdict") or "unknown"),
                        "abstention_active": bool((recommendation.get("abstention") or {}).get("active")),
                        "abstention_code": (
                            (recommendation.get("abstention") or {}).get("code")
                            or monitoring.get("abstention_code")
                        ),
                        "basis": list(recommendation.get("basis") or []),
                        "uncertainty_notes": list(recommendation.get("uncertainty_notes") or []),
                        "evidence_refs": list(recommendation.get("evidence_refs") or []),
                        "monitoring": monitoring,
                        "compare_summary": {
                            "saved_at": compare_summary.get("saved_at"),
                            "recommended_next_step_hint": compare_summary.get("recommended_next_step_hint"),
                            "submitted_count": compare_summary.get("submitted_count"),
                            "resolved_count": compare_summary.get("resolved_count"),
                            "successful_candidate_count": compare_summary.get("successful_candidate_count"),
                            "strongest_match_score": compare_summary.get("strongest_match_score"),
                            "risk_notes": compare_summary.get("risk_notes"),
                        },
                        "review_state": str(
                            review_record.get("decision")
                            or review.get("state")
                            or monitoring.get("review_state")
                            or "pending_internal_review"
                        ),
                        "adjudication": {
                            "recorded_at": review_record.get("recorded_at"),
                            "reviewer": review_record.get("reviewer"),
                            "decision": review_record.get("decision"),
                            "reason_code": review_record.get("reason_code"),
                            "outcome_category": review_record.get("outcome_category"),
                            "agreement_bucket": review_record.get("agreement_bucket"),
                            "expected_verdict": review_record.get("expected_verdict"),
                            "actual_verdict": review_record.get("actual_verdict"),
                            "observed_outcome": review_record.get("observed_outcome"),
                        },
                    }
                )
                entry["replay_source"]["surface_anchor"] = surface_anchor
                entries.append(entry)
                included_count += 1

        entries.sort(key=lambda item: str((item.get("compare_summary") or {}).get("saved_at") or ""), reverse=True)
        return {
            "artifact_kind": "recommendation_replay_manifest",
            "replay_contract_version": "v1",
            "storage_scope": "runtime_local_artifact",
            "mode": "internal_only_replay",
            "visibility": "internal_only",
            "generated_at": utcnow().isoformat(),
            "source_directory": str(base_dir),
            "source_review_log_path": str(self._recommendation_shadow_review_log_path()),
            "source_of_truth_note": (
                "This replay manifest indexes repo-local compare evidence plus recommendation shadow artifacts for internal "
                "evaluation. It must stay out of public API, UI, and MCP contracts."
            ),
            "admission_rules": [
                "compare_evidence.json exists",
                "recommendation_shadow.json exists",
                "shadow_contract_version == v1",
                "surface_anchor is an approved internal evaluation anchor",
                "deterministic_truth_anchor.artifact_path matches compare_evidence.json",
            ],
            "skip_rules": [
                "invalid_compare_evidence_payload",
                "missing_shadow_artifact",
                "invalid_shadow_artifact",
                "shadow_contract_invalid",
                "unsupported_shadow_contract_version",
                "unsupported_surface_anchor",
                "deterministic_truth_anchor_mismatch",
            ],
            "summary": {
                "total_candidates": total_candidates,
                "included_count": included_count,
                "skipped_count": skipped_count,
            },
            "entries": entries,
        }

    @staticmethod
    def _classify_recommendation_shadow_agreement(outcome_category: str) -> str:
        normalized = ProductService._normalize_recommendation_shadow_outcome_category(outcome_category)
        if normalized in {"correct_verdict", "correct_abstention"}:
            return "agreement"
        return normalized

    @staticmethod
    def _normalize_recommendation_shadow_outcome_category(outcome_category: str) -> str:
        return {
            "abstain_should_speak": "abstain_when_should_speak",
            "speak_should_abstain": "speak_when_should_abstain",
        }.get(outcome_category, outcome_category)

    @staticmethod
    def _allowed_recommendation_shadow_surface_anchors() -> set[str]:
        return {
            "compare_preview",
            "watch_group_run_summary",
            "watch_task_run_summary",
        }

    @staticmethod
    def _is_valid_recommendation_shadow_payload(payload: dict[str, Any]) -> bool:
        return (
            isinstance(payload, dict)
            and payload.get("artifact_kind") == "recommendation_shadow"
            and isinstance(payload.get("shadow_recommendation"), dict)
            and isinstance(payload.get("monitoring"), dict)
            and isinstance(payload.get("review"), dict)
        )

    def _build_recommendation_shadow_monitoring_summary_payload(self) -> dict[str, Any]:
        base_dir = self.settings.RUNS_DIR / "compare-evidence"
        review_records = self._load_recommendation_shadow_review_records()
        verdict_distribution: Counter[str] = Counter()
        evidence_strength_buckets: Counter[str] = Counter()
        review_state_buckets: Counter[str] = Counter()
        abstention_code_buckets: Counter[str] = Counter()
        disagreement_buckets: Counter[str] = Counter()
        recent_artifacts: list[dict[str, Any]] = []
        total_artifacts = 0
        valid_shadow_artifact_count = 0
        issued_verdict_count = 0
        abstention_count = 0
        invalid_artifact_count = 0
        skipped_artifact_count = 0
        review_pending_count = 0
        reviewed_count = 0

        if base_dir.exists():
            for package_dir in sorted(
                (path for path in base_dir.iterdir() if path.is_dir() and not path.name.startswith("_")),
                key=lambda path: path.name,
            ):
                compare_path = package_dir / "compare_evidence.json"
                if not compare_path.is_file():
                    continue
                total_artifacts += 1
                shadow_path = package_dir / "recommendation_shadow.json"
                if not shadow_path.is_file():
                    skipped_artifact_count += 1
                    continue
                try:
                    shadow_payload = json.loads(shadow_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    invalid_artifact_count += 1
                    continue
                if not self._is_valid_recommendation_shadow_payload(shadow_payload):
                    invalid_artifact_count += 1
                    continue

                valid_shadow_artifact_count += 1
                recommendation = shadow_payload["shadow_recommendation"]
                monitoring = shadow_payload["monitoring"]
                review = shadow_payload["review"]
                verdict = str(recommendation.get("verdict") or "unknown")
                status = str(shadow_payload.get("status") or "unknown")
                review_state = str(review.get("state") or monitoring.get("review_state") or "unknown")
                evidence_strength = str(monitoring.get("evidence_strength") or "unknown")
                abstention_code = monitoring.get("abstention_code")
                disagreement_code = (
                    str(
                        monitoring.get("agreement_bucket")
                        or review.get("outcome_category")
                        or review.get("reason_code")
                        or "unspecified_disagreement"
                    )
                    if review_state in {"overridden", "rejected"}
                    else None
                )

                verdict_distribution[verdict] += 1
                evidence_strength_buckets[evidence_strength] += 1
                review_state_buckets[review_state] += 1
                if abstention_code:
                    abstention_code_buckets[str(abstention_code)] += 1
                if disagreement_code:
                    disagreement_buckets[disagreement_code] += 1

                if status == "issued":
                    issued_verdict_count += 1
                elif status == "abstained":
                    abstention_count += 1

                if review_state == "pending_internal_review":
                    review_pending_count += 1
                elif review_state in {"confirmed", "overridden", "rejected"}:
                    reviewed_count += 1

                recent_artifacts.append(
                    {
                        "artifact_id": str(shadow_payload.get("artifact_id") or package_dir.name),
                        "saved_at": shadow_payload.get("saved_at"),
                        "status": status,
                        "verdict": verdict,
                        "review_state": review_state,
                        "evidence_strength": evidence_strength,
                        "abstention_code": abstention_code,
                        "disagreement_code": disagreement_code,
                        "artifact_path": str(shadow_path),
                    }
                )

        recent_artifacts.sort(key=lambda item: str(item.get("saved_at") or ""), reverse=True)
        generated_at = utcnow().isoformat()
        review_records = self._load_recommendation_shadow_review_records()
        return {
            "artifact_kind": "recommendation_shadow_monitoring",
            "monitoring_contract_version": "v1",
            "storage_scope": "runtime_local_artifact",
            "mode": "internal_only_monitoring",
            "visibility": "internal_only",
            "generated_at": generated_at,
            "source_directory": str(base_dir),
            "review_log_path": str(self._recommendation_shadow_review_log_path()),
            "review_record_count": len(review_records),
            "source_of_truth_note": (
                "This monitoring summary is derived from repo-local recommendation shadow artifacts and must not be treated "
                "as user-visible product truth."
            ),
            "future_launch_blocked": True,
            "review_log_path": str(self._recommendation_shadow_review_log_path()),
            "review_record_count": len(review_records),
            "summary": {
                "total_artifacts": total_artifacts,
                "valid_shadow_artifact_count": valid_shadow_artifact_count,
                "issued_verdict_count": issued_verdict_count,
                "abstention_count": abstention_count,
                "invalid_artifact_count": invalid_artifact_count,
                "skipped_artifact_count": skipped_artifact_count,
                "invalid_or_skipped_count": invalid_artifact_count + skipped_artifact_count,
                "review_pending_count": review_pending_count,
                "reviewed_count": reviewed_count,
                "verdict_distribution": dict(sorted(verdict_distribution.items())),
                "evidence_strength_buckets": dict(sorted(evidence_strength_buckets.items())),
                "review_state_buckets": dict(sorted(review_state_buckets.items())),
                "abstention_code_buckets": dict(sorted(abstention_code_buckets.items())),
                "disagreement_buckets": dict(sorted(disagreement_buckets.items())),
            },
            "recent_artifacts": recent_artifacts[:20],
        }

    @staticmethod
    def _validate_compare_preview_result(compare_result: dict[str, Any]) -> None:
        if not isinstance(compare_result, dict):
            raise ValueError("compare_result_invalid")
        if not isinstance(compare_result.get("comparisons"), list):
            raise ValueError("compare_result_invalid")
        if not isinstance(compare_result.get("matches"), list):
            raise ValueError("compare_result_invalid")
        if "submitted_count" not in compare_result or "resolved_count" not in compare_result:
            raise ValueError("compare_result_invalid")

    def _build_compare_evidence_truth(
        self,
        *,
        submitted_urls: list[str],
        zip_code: str,
        compare_result: dict[str, Any],
    ) -> dict[str, Any]:
        comparisons = list(compare_result.get("comparisons", []))
        matches = list(compare_result.get("matches", []))
        successful = [item for item in comparisons if item.get("fetch_succeeded")]
        group_ready = [
            item
            for item in successful
            if bool((item.get("support_contract") or {}).get("can_create_watch_group"))
        ]
        unsupported = [item for item in comparisons if not item.get("supported", True)]
        failed_fetch = [
            item
            for item in comparisons
            if item.get("supported", True) and not item.get("fetch_succeeded", False)
        ]
        strongest_match_score = max((float(item.get("score") or 0.0) for item in matches), default=0.0)
        if len(successful) <= 0:
            recommended_next_step_hint = {
                "action": "retry_compare",
                "reason_code": "no_successful_candidates",
                "summary": "No candidate resolved successfully yet, so rerun compare before saving anything durable.",
                "successful_candidate_count": len(successful),
                "strongest_match_score": strongest_match_score,
            }
        elif len(successful) == 1:
            recommended_next_step_hint = {
                "action": "create_watch_task",
                "reason_code": "single_resolved_candidate",
                "summary": "Only one candidate resolved successfully, so a single watch task is the safest next step.",
                "successful_candidate_count": len(successful),
                "strongest_match_score": strongest_match_score,
            }
        elif len(group_ready) == 1:
            recommended_next_step_hint = {
                "action": "create_watch_task",
                "reason_code": "single_group_capable_candidate",
                "summary": (
                    "Multiple rows resolved, but only one row is currently eligible for a compare-aware watch group, "
                    "so a single watch task is the safest durable next step."
                ),
                "successful_candidate_count": len(successful),
                "strongest_match_score": strongest_match_score,
            }
        elif len(group_ready) >= 2 and strongest_match_score >= 80:
            recommended_next_step_hint = {
                "action": "create_watch_group",
                "reason_code": "multi_candidate_strong_match",
                "summary": "Multiple candidates resolved and the strongest match signal is strong, so keep them together as a watch group.",
                "successful_candidate_count": len(successful),
                "strongest_match_score": strongest_match_score,
            }
        elif len(group_ready) < 2:
            recommended_next_step_hint = {
                "action": "review_before_save",
                "reason_code": "group_capability_gap",
                "summary": (
                    "Rows resolved successfully, but the current store-capability contract does not yet support a "
                    "compare-aware watch group for enough of them."
                ),
                "successful_candidate_count": len(successful),
                "strongest_match_score": strongest_match_score,
            }
        else:
            recommended_next_step_hint = {
                "action": "review_before_save",
                "reason_code": "multi_candidate_weak_match",
                "summary": "More than one candidate resolved, but the strongest match signal is weak enough that you should review before saving.",
                "successful_candidate_count": len(successful),
                "strongest_match_score": strongest_match_score,
            }

        risk_note_items: list[dict[str, Any]] = []
        if unsupported:
            risk_note_items.append(
                {
                    "code": "unsupported_inputs_present",
                    "message": f"{len(unsupported)} URL(s) are unsupported.",
                }
            )
        if failed_fetch:
            risk_note_items.append(
                {
                    "code": "failed_fetch_candidates_present",
                    "message": f"{len(failed_fetch)} candidate(s) failed to fetch.",
                }
            )
        if len(successful) < 2:
            risk_note_items.append(
                {
                    "code": "limited_successful_candidates",
                    "message": "There are fewer than two successful candidates, so a compare-aware group may not be justified yet.",
                }
            )
        if matches and strongest_match_score < 80:
            risk_note_items.append(
                {
                    "code": "match_confidence_not_high",
                    "message": "The strongest match score is still below the high-confidence range.",
                }
            )

        return {
            "submitted_inputs": list(submitted_urls),
            "zip_code": zip_code,
            "submitted_count": int(compare_result.get("submitted_count") or len(submitted_urls)),
            "resolved_count": int(compare_result.get("resolved_count") or len(successful)),
            "comparisons": comparisons,
            "matches": matches,
            "recommended_next_step_hint": recommended_next_step_hint,
            "risk_notes": [item["message"] for item in risk_note_items],
            "risk_note_items": risk_note_items,
            "successful_candidate_count": len(successful),
            "strongest_match_score": strongest_match_score,
        }

    def _build_compare_support_contract(
        self,
        *,
        store_key: str | None,
        intake_status: str,
    ) -> dict[str, Any]:
        capability = STORE_CAPABILITY_REGISTRY.get(store_key) if store_key is not None else None
        support_tier = capability.support_tier if capability is not None else "limited_unofficial"
        support_channel = "official" if capability is not None else "limited"
        missing_capabilities = []
        if capability is not None:
            missing_capabilities = [
                capability_name
                for capability_name, enabled in (
                    ("compare_intake", capability.supports_compare_intake),
                    ("watch_task", capability.supports_watch_task),
                    ("watch_group", capability.supports_watch_group),
                    ("recovery", capability.supports_recovery),
                    ("cashback", capability.cashback_supported),
                )
                if not enabled
            ]

        summary = (
            "This row is on the full official product path. Compare intake, watch creation, compare-aware groups, "
            "recovery, and cashback-aware review are all available once live offer evidence is present."
        )
        next_step = "Review the compare evidence, then create either a single watch task or a compare-aware watch group."
        can_create_watch_task = capability.supports_watch_task if capability is not None else False
        can_create_watch_group = capability.supports_watch_group if capability is not None else False
        cashback_supported = capability.cashback_supported if capability is not None else False
        notifications_supported = can_create_watch_task or can_create_watch_group

        if intake_status == "unsupported_store_host":
            summary = (
                "This host is not in the official DealWatch store registry yet. "
                "The row can stay in compare review and repo-local evidence, but it cannot become live watch state."
            )
            next_step = "Keep it as compare evidence only, or submit a URL from an officially supported store."
            can_create_watch_task = False
            can_create_watch_group = False
            cashback_supported = False
            notifications_supported = False
            missing_capabilities = ["official_store_registry", "watch_task", "watch_group", "recovery", "cashback"]
        elif intake_status == "unsupported_store_path":
            summary = (
                "The store host is recognized, but this URL shape is not an officially supported product path yet. "
                "DealWatch can keep it in compare review and local evidence, but not as live watch state."
            )
            next_step = "Submit a supported product-detail URL for this store, or keep this row as compare evidence only."
            can_create_watch_task = False
            can_create_watch_group = False
            cashback_supported = False
            notifications_supported = False
        elif intake_status == "store_disabled":
            summary = (
                "This store is part of the official registry, but its runtime binding is currently disabled. "
                "The row can stay in compare review and evidence, but live watch actions are paused."
            )
            next_step = "Re-enable the store binding before creating a watch task or watch group from this row."
            can_create_watch_task = False
            can_create_watch_group = False
            cashback_supported = False
            notifications_supported = False
        elif intake_status == "offer_fetch_failed":
            summary = (
                "The store and URL path are supported, but this compare run did not fetch live offer evidence. "
                "Until fetch succeeds, keep the row as review/evidence instead of durable watch state."
            )
            next_step = "Retry compare or inspect the store/runtime condition before saving live watch state."
            can_create_watch_task = False
            can_create_watch_group = False
            cashback_supported = False
            notifications_supported = False
        elif support_tier == "official_full":
            summary = (
                "This row is on the full official store path. "
                "Compare intake, single-watch, compare-aware watch group, recovery, and cashback all sit inside the current repo-local product path."
            )
            next_step = (
                "If multiple strong rows survive compare, keep them together as a watch group. "
                "If only one row survives cleanly, a single watch task is still the safest durable next step."
            )
        elif support_tier == "official_partial":
            if can_create_watch_group:
                summary = (
                    "This row is on an officially supported but still partial store path. "
                    "Compare intake, single-watch flow, and compare-aware watch groups are available, "
                    "while recovery and cashback closure still remain intentionally limited."
                )
                next_step = (
                    "Use the currently supported compare, single-watch, or compare-aware watch-group path, "
                    "and keep recovery/cashback claims deferred until those capabilities are truly landed."
                )
            else:
                summary = (
                    "This row is on an officially supported but still partial store path. "
                    "Compare intake and single-watch flow are available, while broader group/recovery closure is still limited."
                )
                next_step = "Use the currently supported compare or single-watch path, and do not overclaim missing store capabilities."
        elif support_tier == "official_in_progress":
            summary = (
                "This store is in official onboarding progress, so the repo can describe the path but should not market it as full support yet."
            )
            next_step = "Keep the store parked until contract tests, runtime checks, and product-path coverage are ready."

        return {
            "support_channel": support_channel,
            "store_support_tier": support_tier,
            "support_reason_codes": list(capability.support_reason_codes) if capability is not None else [],
            "next_step_codes": list(capability.next_step_codes) if capability is not None else [],
            "intake_status": intake_status,
            "summary": summary,
            "next_step": next_step,
            "can_save_compare_evidence": True,
            "can_create_watch_task": can_create_watch_task and intake_status == "supported",
            "can_create_watch_group": can_create_watch_group and intake_status == "supported",
            "cashback_supported": cashback_supported and intake_status == "supported",
            "notifications_supported": notifications_supported and intake_status == "supported",
            "missing_capabilities": missing_capabilities,
        }

    def _build_compare_evidence_payload(
        self,
        *,
        package_id: str,
        compare_evidence: dict[str, Any],
    ) -> dict[str, Any]:
        comparisons = list(compare_evidence.get("comparisons", []))
        matches = list(compare_evidence.get("matches", []))
        recommended_next_step_hint = dict(compare_evidence.get("recommended_next_step_hint") or {})
        risk_note_items = list(compare_evidence.get("risk_note_items", []))
        risk_notes = list(compare_evidence.get("risk_notes", []))

        headline = str(recommended_next_step_hint.get("summary") or "Compare evidence package")
        saved_at = utcnow().isoformat()
        artifact_dir = self.settings.RUNS_DIR / "compare-evidence" / package_id
        summary = {
            "artifact_id": package_id,
            "artifact_kind": "compare_evidence",
            "storage_scope": "runtime_local_artifact",
            "created_at": saved_at,
            "saved_at": saved_at,
            "headline": headline,
            "recommended_next_step_hint": recommended_next_step_hint,
            "submitted_inputs": list(compare_evidence.get("submitted_inputs", [])),
            "submitted_count": int(compare_evidence.get("submitted_count") or 0),
            "resolved_count": int(compare_evidence.get("resolved_count") or 0),
            "successful_candidate_count": int(compare_evidence.get("successful_candidate_count") or 0),
            "strongest_match_score": float(compare_evidence.get("strongest_match_score") or 0.0),
            "risk_notes": risk_notes,
            "risk_note_items": risk_note_items,
            "artifact_path": str(artifact_dir / "compare_evidence.json"),
            "html_path": str(artifact_dir / "compare_evidence.html"),
            "detail_url": f"/api/compare/evidence/{package_id}",
            "html_url": f"/api/compare/evidence-packages/{package_id}/html",
        }
        return {
            "artifact_id": package_id,
            "artifact_kind": "compare_evidence",
            "storage_scope": "runtime_local_artifact",
            "saved_at": saved_at,
            "artifact_path": summary["artifact_path"],
            "html_path": summary["html_path"],
            "source_of_truth_note": "This evidence pack is a runtime/local artifact and does not become PostgreSQL product source of truth.",
            "submitted_inputs": list(compare_evidence.get("submitted_inputs", [])),
            "zip_code": compare_evidence.get("zip_code"),
            "submitted_count": summary["submitted_count"],
            "resolved_count": summary["resolved_count"],
            "comparisons": comparisons,
            "matches": matches,
            "recommended_next_step_hint": recommended_next_step_hint,
            "risk_notes": risk_notes,
            "risk_note_items": risk_note_items,
            "summary": summary,
        }

    def _build_compare_recommendation_shadow_payload(
        self,
        *,
        package_id: str,
        compare_evidence: dict[str, Any],
    ) -> dict[str, Any]:
        recommended_next_step_hint = dict(compare_evidence.get("recommended_next_step_hint") or {})
        risk_note_items = list(compare_evidence.get("risk_note_items", []))
        risk_notes = list(compare_evidence.get("risk_notes", []))
        successful_candidate_count = int(compare_evidence.get("successful_candidate_count") or 0)
        strongest_match_score = float(compare_evidence.get("strongest_match_score") or 0.0)
        reason_code = str(recommended_next_step_hint.get("reason_code") or "compare_shadow_unknown")
        action = str(recommended_next_step_hint.get("action") or "review_before_save")

        verdict = "recheck_later"
        basis = [
            str(
                recommended_next_step_hint.get("summary")
                or "Deterministic compare evidence remains the primary review surface."
            )
        ]
        uncertainty_notes = [
            "Internal-only shadow artifact: deterministic compare evidence remains the source of truth."
        ]
        abstention = {
            "active": False,
            "code": None,
            "reason": None,
        }

        evidence_strength = "strong_compare_wait"
        if reason_code in {"no_successful_candidates", "single_resolved_candidate", "single_group_capable_candidate"}:
            verdict = "insufficient_evidence"
            abstention = {
                "active": True,
                "code": reason_code,
                "reason": (
                    "The compare step does not yet have enough cross-store evidence to make an honest purchase-timing call."
                ),
            }
            basis.append(
                "Cross-store compare context is still incomplete, so this shadow artifact abstains instead of forcing a recommendation."
            )
            evidence_strength = "insufficient_compare_context"
        elif reason_code == "multi_candidate_strong_match":
            verdict = "wait"
            basis.append(
                "Multiple candidates still look plausibly comparable, so keeping them under watch is safer than turning compare evidence into a buy-now claim."
            )
        else:
            verdict = "recheck_later"
            basis.append(
                "The compare evidence still needs another review or rerun before an internal reviewer should trust a stronger recommendation."
            )
            evidence_strength = "needs_recheck"

        if successful_candidate_count <= 0:
            uncertainty_notes.append("No candidate resolved successfully in this compare run.")
        elif successful_candidate_count < 2:
            uncertainty_notes.append("Fewer than two successful candidates survived compare.")
        if strongest_match_score < 80:
            uncertainty_notes.append(
                f"Strongest match score is only {strongest_match_score:.1f}, which is below the current high-confidence compare range."
            )
        uncertainty_notes.extend(risk_notes)
        uncertainty_notes = list(dict.fromkeys(note for note in uncertainty_notes if note))

        evidence_refs = [
            {
                "code": reason_code,
                "label": "Deterministic next-step reason",
                "anchor": "compare_evidence.recommended_next_step_hint.reason_code",
            },
            {
                "code": action,
                "label": "Deterministic next-step action",
                "anchor": "compare_evidence.recommended_next_step_hint.action",
            },
            {
                "code": f"successful_candidate_count:{successful_candidate_count}",
                "label": "Successful candidate count",
                "anchor": "compare_evidence.successful_candidate_count",
            },
            {
                "code": "strongest_match_score",
                "label": f"Strongest match score {strongest_match_score:.1f}",
                "anchor": "compare_evidence.strongest_match_score",
            },
        ]
        for item in risk_note_items[:3]:
            evidence_refs.append(
                {
                    "code": str(item.get("code") or "compare_risk"),
                    "label": str(item.get("message") or "Compare risk note"),
                    "anchor": "compare_evidence.risk_note_items",
                }
            )

        saved_at = utcnow().isoformat()
        artifact_dir = self.settings.RUNS_DIR / "compare-evidence" / package_id
        status = "abstained" if abstention["active"] else "issued"
        review_seed_suggestion = "correct_abstention" if abstention["active"] else "correct_verdict"
        return {
            "artifact_id": package_id,
            "artifact_kind": "recommendation_shadow",
            "shadow_contract_version": "v1",
            "storage_scope": "runtime_local_artifact",
            "mode": "internal_only_shadow",
            "visibility": "internal_only",
            "surface_anchor": "compare_preview",
            "saved_at": saved_at,
            "artifact_path": str(artifact_dir / "recommendation_shadow.json"),
            "html_path": str(artifact_dir / "recommendation_shadow.html"),
            "review_use_cases": ["internal_review", "replay", "compare"],
            "verdict_vocabulary": ["buy_now", "wait", "recheck_later", "insufficient_evidence"],
            "status": status,
            "deterministic_truth_anchor": {
                "artifact_kind": "compare_evidence",
                "artifact_path": str(artifact_dir / "compare_evidence.json"),
                "html_path": str(artifact_dir / "compare_evidence.html"),
                "note": (
                    "This shadow artifact is advisory-only for internal review and must stay subordinate to deterministic compare evidence."
                ),
            },
            "review": {
                "state": "pending_internal_review",
                "owner": None,
                "reason_code": None,
                "notes": None,
                "observed_outcome": None,
            },
            "monitoring": {
                "input_profile": "compare_preview_only",
                "evidence_strength": evidence_strength,
                "abstention_code": abstention["code"],
                "review_state": "pending_internal_review",
                "future_launch_blocked": True,
                "review_seed_suggestion": review_seed_suggestion,
            },
            "shadow_recommendation": {
                "verdict": verdict,
                "basis": basis,
                "uncertainty_notes": uncertainty_notes,
                "abstention": abstention,
                "evidence_refs": evidence_refs,
            },
        }

    async def _build_compare_ai_explain(self, compare_evidence: dict[str, Any]) -> dict[str, Any]:
        matches = list(compare_evidence.get("matches", []))
        strongest_match = matches[0] if matches else None
        next_step = dict(compare_evidence.get("recommended_next_step_hint") or {})
        evidence_refs = [
            {
                "code": str(next_step.get("reason_code") or "compare_next_step"),
                "label": "Recommended next-step reason",
                "anchor": "recommended_next_step_hint.reason_code",
            },
            {
                "code": str(next_step.get("action") or "review_compare"),
                "label": "Recommended next-step action",
                "anchor": "recommended_next_step_hint.action",
            },
        ]
        if strongest_match is not None:
            evidence_refs.append(
                {
                    "code": "strongest_match_score",
                    "label": (
                        f"{strongest_match.get('left_store_key')} vs {strongest_match.get('right_store_key')}"
                    ),
                    "anchor": "matches[0].score",
                }
            )
        for item in list(compare_evidence.get("risk_note_items", []))[:3]:
            evidence_refs.append(
                {
                    "code": str(item.get("code") or "compare_risk"),
                    "label": "Compare risk note",
                    "anchor": "risk_note_items",
                }
            )

        bullets = [
            (
                f"{int(compare_evidence.get('resolved_count') or 0)} of "
                f"{int(compare_evidence.get('submitted_count') or 0)} candidates resolved successfully."
            ),
            str(next_step.get("summary") or "Review the deterministic compare evidence before deciding."),
        ]
        if strongest_match is not None:
            bullets.append(
                f"Strongest pair score is {float(strongest_match.get('score') or 0.0):.1f}."
            )
        return await self.ai_service.build(
            enabled=bool(self.settings.AI_COMPARE_EXPLAIN_ENABLED),
            label="AI Compare Explainer",
            title="Should these candidates stay together?",
            summary=str(next_step.get("summary") or "Compare finished without a durable AI explanation."),
            bullets=bullets,
            evidence_refs=evidence_refs,
            caution_notes=list(compare_evidence.get("risk_notes", [])),
        )

    async def _build_watch_group_ai_decision_explain(
        self,
        *,
        group: WatchGroup,
        decision_explain: dict[str, Any],
    ) -> dict[str, Any]:
        winner = decision_explain.get("winner") or {}
        runner_up = decision_explain.get("runner_up") or {}
        evidence_refs = [
            {
                "code": str((decision_explain.get("reason") or {}).get("code") or "group_decision_reason"),
                "label": "Decision reason",
                "anchor": "decision_explain.reason.code",
            },
            {
                "code": str(winner.get("member_id") or "no_winner"),
                "label": "Winner anchor",
                "anchor": "decision_explain.winner.member_id",
            },
        ]
        if runner_up.get("member_id"):
            evidence_refs.append(
                {
                    "code": str(runner_up.get("member_id")),
                    "label": "Runner-up anchor",
                    "anchor": "decision_explain.runner_up.member_id",
                }
            )
        for item in list(decision_explain.get("risk_note_items", []))[:3]:
            evidence_refs.append(
                {
                    "code": str(item.get("code") or "group_risk"),
                    "label": "Decision risk note",
                    "anchor": "decision_explain.risk_note_items",
                }
            )

        bullets = [
            str(decision_explain.get("headline") or "No group decision is available yet."),
            f"Current reliability is {decision_explain.get('reliability') or 'unknown'}.",
        ]
        if winner.get("title"):
            bullets.append(f"Winner candidate: {winner['title']}.")
        skip_reason = None if winner.get("member_id") else "No latest successful group winner exists yet."
        return await self.ai_service.build(
            enabled=bool(self.settings.AI_GROUP_EXPLAIN_ENABLED),
            label="AI Watch Group Decision Explainer",
            title=f"Why {group.title} currently prefers this winner",
            summary=str(decision_explain.get("headline") or "No group decision is available yet."),
            bullets=bullets,
            evidence_refs=evidence_refs,
            caution_notes=list(decision_explain.get("risk_notes", [])),
            skip_reason=skip_reason,
        )

    async def _build_recovery_ai_copilot(
        self,
        *,
        task_items: list[dict[str, Any]],
        group_items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        total_items = len(task_items) + len(group_items)
        evidence_refs = [
            {
                "code": f"total_items:{total_items}",
                "label": "Recovery inbox size",
                "anchor": "total_items",
            }
        ]
        top_items = [*task_items[:2], *group_items[:2]]
        for item in top_items[:4]:
            evidence_refs.append(
                {
                    "code": f"{item['kind']}:{item['id']}",
                    "label": str(item.get("last_error_code") or item.get("reason") or item["title"]),
                    "anchor": f"{item['kind']}_items",
                }
            )

        bullets = [
            f"{len(task_items)} task item(s) and {len(group_items)} group item(s) currently need attention."
        ]
        bullets.extend(str(item.get("recommended_action")) for item in top_items[:3])
        caution_notes = list(
            dict.fromkeys(str(item.get("reason")) for item in top_items if item.get("reason"))
        )
        skip_reason = "Recovery inbox is empty, so no AI recovery advice is needed right now." if total_items == 0 else None
        return await self.ai_service.build(
            enabled=bool(self.settings.AI_RECOVERY_COPILOT_ENABLED),
            label="AI Health Recovery Copilot",
            title="Where the operator should recover the runtime next",
            summary=(
                "The recovery inbox is empty."
                if total_items == 0
                else f"{total_items} recovery item(s) currently need review."
            ),
            bullets=bullets,
            evidence_refs=evidence_refs,
            caution_notes=caution_notes,
            skip_reason=skip_reason,
        )

    def _render_compare_evidence_html(self, payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        comparisons = payload.get("comparisons", [])
        matches = payload.get("matches", [])
        comparison_rows = "\n".join(
            (
                "<tr>"
                f"<td>{html.escape(str(item.get('store_key') or 'unknown'))}</td>"
                f"<td>{html.escape(str(item.get('submitted_url') or ''))}</td>"
                f"<td>{html.escape(str(item.get('candidate_key') or ''))}</td>"
                f"<td>{'yes' if item.get('fetch_succeeded') else 'no'}</td>"
                f"<td>{html.escape(str((item.get('offer') or {}).get('title') or ''))}</td>"
                f"<td>{html.escape(str(item.get('error_code') or ''))}</td>"
                "</tr>"
            )
            for item in comparisons
        )
        match_rows = "\n".join(
            (
                "<tr>"
                f"<td>{html.escape(str(item.get('left_store_key') or ''))}</td>"
                f"<td>{html.escape(str(item.get('right_store_key') or ''))}</td>"
                f"<td>{float(item.get('score') or 0.0):.1f}</td>"
                f"<td>{html.escape(', '.join(item.get('why_like') or []))}</td>"
                f"<td>{html.escape(', '.join(item.get('why_unlike') or []))}</td>"
                "</tr>"
            )
            for item in matches
        )
        submitted_urls = "".join(
            f"<li>{html.escape(str(item))}</li>"
            for item in payload.get("submitted_inputs", [])
        )
        risk_notes = "".join(
            f"<li>{html.escape(str(item))}</li>"
            for item in summary.get("risk_notes", [])
        )
        return (
            "<html><head><meta charset=\"utf-8\"/>"
            "<style>"
            "body{font-family:Arial,Helvetica,sans-serif;margin:24px;color:#1f2937;}"
            "table{border-collapse:collapse;width:100%;margin-top:16px;}"
            "th,td{border:1px solid #d1d5db;padding:8px;text-align:left;font-size:14px;vertical-align:top;}"
            "th{background:#f3f4f6;}"
            ".summary{background:#f8fafc;border:1px solid #e5e7eb;border-radius:16px;padding:16px;margin-bottom:20px;}"
            ".eyebrow{font-size:12px;text-transform:uppercase;letter-spacing:.12em;color:#b45309;font-weight:700;}"
            "</style></head><body>"
            "<div class=\"summary\">"
            "<div class=\"eyebrow\">Compare Evidence Artifact</div>"
            f"<h1>{html.escape(summary['headline'])}</h1>"
            f"<p>Saved at {html.escape(summary['saved_at'])}. Recommended next step: {html.escape(summary['recommended_next_step_hint']['action'])}.</p>"
            f"<p>Submitted {summary['submitted_count']} URL(s), resolved {summary['resolved_count']} candidate(s), strongest match score {float(summary['strongest_match_score'] or 0.0):.1f}.</p>"
            "</div>"
            "<h2>Input</h2>"
            f"<p>ZIP code: {html.escape(str(payload.get('zip_code') or ''))}</p>"
            f"<ul>{submitted_urls}</ul>"
            "<h2>Risk Notes</h2>"
            f"<ul>{risk_notes or '<li>No additional risk notes.</li>'}</ul>"
            "<h2>Candidate Results</h2>"
            "<table><tr><th>Store</th><th>Submitted URL</th><th>Candidate Key</th><th>Fetched</th><th>Title</th><th>Error</th></tr>"
            f"{comparison_rows}</table>"
            "<h2>Match Signals</h2>"
            "<table><tr><th>Left</th><th>Right</th><th>Score</th><th>Why Like</th><th>Why Unlike</th></tr>"
            f"{match_rows}</table>"
            "</body></html>"
        )

    def _render_compare_recommendation_shadow_html(self, payload: dict[str, Any]) -> str:
        recommendation = payload["shadow_recommendation"]
        review = payload.get("review") or {}
        monitoring = payload.get("monitoring") or {}
        evidence_refs = "".join(
            (
                "<tr>"
                f"<td>{html.escape(str(item.get('code') or ''))}</td>"
                f"<td>{html.escape(str(item.get('label') or ''))}</td>"
                f"<td>{html.escape(str(item.get('anchor') or ''))}</td>"
                "</tr>"
            )
            for item in recommendation.get("evidence_refs", [])
        )
        basis_items = "".join(
            f"<li>{html.escape(str(item))}</li>"
            for item in recommendation.get("basis", [])
        )
        uncertainty_items = "".join(
            f"<li>{html.escape(str(item))}</li>"
            for item in recommendation.get("uncertainty_notes", [])
        )
        abstention = recommendation.get("abstention") or {}
        abstention_summary = "No abstention gate is active for this shadow verdict."
        if abstention.get("active"):
            abstention_summary = (
                f"Abstention active: {html.escape(str(abstention.get('code') or 'shadow_abstention'))} - "
                f"{html.escape(str(abstention.get('reason') or 'No abstention reason provided.'))}"
            )
        review_summary = (
            f"Review state: {html.escape(str(review.get('state') or 'pending_internal_review'))}. "
            f"Agreement bucket: {html.escape(str(monitoring.get('agreement_bucket') or 'pending'))}."
        )
        return (
            "<html><head><meta charset=\"utf-8\"/>"
            "<style>"
            "body{font-family:Arial,Helvetica,sans-serif;margin:24px;color:#1f2937;}"
            "table{border-collapse:collapse;width:100%;margin-top:16px;}"
            "th,td{border:1px solid #d1d5db;padding:8px;text-align:left;font-size:14px;vertical-align:top;}"
            "th{background:#f3f4f6;}"
            ".summary{background:#fff7ed;border:1px solid #fdba74;border-radius:16px;padding:16px;margin-bottom:20px;}"
            ".eyebrow{font-size:12px;text-transform:uppercase;letter-spacing:.12em;color:#b45309;font-weight:700;}"
            "</style></head><body>"
            "<div class=\"summary\">"
            "<div class=\"eyebrow\">Internal Recommendation Shadow Artifact</div>"
            f"<h1>{html.escape(str(recommendation['verdict']))}</h1>"
            f"<p>Saved at {html.escape(str(payload['saved_at']))}. This is internal-only and does not change the public compare contract.</p>"
            f"<p>{html.escape(str(payload['deterministic_truth_anchor']['note']))}</p>"
            f"<p>{abstention_summary}</p>"
            f"<p>{review_summary}</p>"
            "</div>"
            "<h2>Basis</h2>"
            f"<ul>{basis_items}</ul>"
            "<h2>Uncertainty</h2>"
            f"<ul>{uncertainty_items}</ul>"
            "<h2>Evidence Refs</h2>"
            "<table><tr><th>Code</th><th>Label</th><th>Anchor</th></tr>"
            f"{evidence_refs}</table>"
            "</body></html>"
        )

    def _render_recommendation_shadow_monitoring_summary_html(self, payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        recent_rows = "\n".join(
            (
                "<tr>"
                f"<td>{html.escape(str(item.get('artifact_id') or ''))}</td>"
                f"<td>{html.escape(str(item.get('saved_at') or ''))}</td>"
                f"<td>{html.escape(str(item.get('status') or ''))}</td>"
                f"<td>{html.escape(str(item.get('verdict') or ''))}</td>"
                f"<td>{html.escape(str(item.get('review_state') or ''))}</td>"
                f"<td>{html.escape(str(item.get('evidence_strength') or ''))}</td>"
                f"<td>{html.escape(str(item.get('abstention_code') or ''))}</td>"
                f"<td>{html.escape(str(item.get('disagreement_code') or ''))}</td>"
                "</tr>"
            )
            for item in payload.get("recent_artifacts", [])
        )

        def _render_bucket_rows(items: dict[str, Any]) -> str:
            return "".join(
                "<tr>"
                f"<td>{html.escape(str(key))}</td>"
                f"<td>{html.escape(str(value))}</td>"
                "</tr>"
                for key, value in items.items()
            )

        return (
            "<html><head><meta charset=\"utf-8\"/>"
            "<style>"
            "body{font-family:Arial,Helvetica,sans-serif;margin:24px;color:#1f2937;}"
            "table{border-collapse:collapse;width:100%;margin-top:16px;}"
            "th,td{border:1px solid #d1d5db;padding:8px;text-align:left;font-size:14px;vertical-align:top;}"
            "th{background:#f3f4f6;}"
            ".summary{background:#eff6ff;border:1px solid #93c5fd;border-radius:16px;padding:16px;margin-bottom:20px;}"
            ".eyebrow{font-size:12px;text-transform:uppercase;letter-spacing:.12em;color:#1d4ed8;font-weight:700;}"
            ".grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;}"
            "</style></head><body>"
            "<div class=\"summary\">"
            "<div class=\"eyebrow\">Internal Recommendation Shadow Monitoring</div>"
            "<h1>Recommendation Shadow Summary</h1>"
            f"<p>Generated at {html.escape(str(payload['generated_at']))}. This summary is internal-only and does not change any public API, UI, or MCP contract.</p>"
            f"<p>Total artifacts {summary['total_artifacts']}, valid shadow artifacts {summary['valid_shadow_artifact_count']}, issued verdicts {summary['issued_verdict_count']}, abstentions {summary['abstention_count']}.</p>"
            f"<p>Invalid artifacts {summary['invalid_artifact_count']}, skipped artifacts {summary['skipped_artifact_count']}, pending review {summary['review_pending_count']}, reviewed {summary['reviewed_count']}.</p>"
            f"<p>Invalid or skipped combined {summary['invalid_or_skipped_count']}. Review records captured {payload.get('review_record_count', 0)}.</p>"
            "</div>"
            "<div class=\"grid\">"
            "<div><h2>Verdict Distribution</h2><table><tr><th>Verdict</th><th>Count</th></tr>"
            f"{_render_bucket_rows(summary.get('verdict_distribution', {}))}</table></div>"
            "<div><h2>Evidence Strength</h2><table><tr><th>Bucket</th><th>Count</th></tr>"
            f"{_render_bucket_rows(summary.get('evidence_strength_buckets', {}))}</table></div>"
            "<div><h2>Review States</h2><table><tr><th>State</th><th>Count</th></tr>"
            f"{_render_bucket_rows(summary.get('review_state_buckets', {}))}</table></div>"
            "<div><h2>Disagreement Buckets</h2><table><tr><th>Code</th><th>Count</th></tr>"
            f"{_render_bucket_rows(summary.get('disagreement_buckets', {}))}</table></div>"
            "</div>"
            "<h2>Recent Artifacts</h2>"
            "<table><tr><th>Artifact</th><th>Saved At</th><th>Status</th><th>Verdict</th><th>Review State</th><th>Evidence Strength</th><th>Abstention Code</th><th>Disagreement</th></tr>"
            f"{recent_rows}</table>"
            "</body></html>"
        )

    def _write_task_run_artifact(
        self,
        *,
        task: WatchTask,
        target: WatchTarget,
        run: TaskRun,
        observation: PriceObservation | None = None,
        cashback_quote: CashbackQuote | None = None,
        effective_price: float | None = None,
        deliveries: list[DeliveryEvent] | None = None,
    ) -> None:
        artifact_dir = Path(run.artifact_run_dir) if run.artifact_run_dir else self._prepare_task_run_artifact_dir(task, run)
        payload = {
            "task": {
                "id": task.id,
                "status": task.status,
                "threshold_type": task.threshold_type,
                "threshold_value": task.threshold_value,
                "zip_code": task.zip_code,
                "cadence_minutes": task.cadence_minutes,
                "cooldown_minutes": task.cooldown_minutes,
            },
            "target": {
                "submitted_url": target.submitted_url,
                "normalized_url": target.normalized_url,
                "product_url": target.product_url,
                "store_key": target.store_key,
            },
            "run": {
                "id": run.id,
                "triggered_by": run.triggered_by,
                "status": run.status,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "finished_at": run.finished_at.isoformat() if run.finished_at else None,
                "error_code": run.error_code,
                "error_message": run.error_message,
                "artifact_run_dir": str(artifact_dir),
                "engine_store_key": run.engine_store_key,
                "engine_product_key": run.engine_product_key,
            },
            "observation": (
                {
                    "title_snapshot": observation.title_snapshot,
                    "listed_price": observation.listed_price,
                    "original_price": observation.original_price,
                    "currency": observation.currency,
                    "source_url": observation.source_url,
                    "observed_at": observation.observed_at.isoformat(),
                    "unit_price_raw": observation.unit_price_raw,
                }
                if observation is not None
                else None
            ),
            "cashback_quote": (
                {
                    "provider": cashback_quote.provider,
                    "merchant_key": cashback_quote.merchant_key,
                    "rate_type": cashback_quote.rate_type,
                    "rate_value": cashback_quote.rate_value,
                    "conditions_text": cashback_quote.conditions_text,
                    "source_url": cashback_quote.source_url,
                    "confidence": cashback_quote.confidence,
                    "collected_at": cashback_quote.collected_at.isoformat(),
                }
                if cashback_quote is not None
                else None
            ),
            "effective_price": effective_price,
            "delivery_events": [
                {
                    "id": item.id,
                    "provider": item.provider,
                    "recipient": item.recipient,
                    "status": item.status,
                    "template_key": item.template_key,
                    "created_at": item.created_at.isoformat(),
                    "sent_at": item.sent_at.isoformat() if item.sent_at else None,
                    "delivered_at": item.delivered_at.isoformat() if item.delivered_at else None,
                    "bounced_at": item.bounced_at.isoformat() if item.bounced_at else None,
                }
                for item in (deliveries or [])
            ],
        }
        (artifact_dir / "task_run_summary.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _safe_write_task_run_artifact(
        self,
        *,
        task: WatchTask,
        target: WatchTarget,
        run: TaskRun,
        observation: PriceObservation | None = None,
        cashback_quote: CashbackQuote | None = None,
        effective_price: float | None = None,
        deliveries: list[DeliveryEvent] | None = None,
    ) -> None:
        try:
            self._write_task_run_artifact(
                task=task,
                target=target,
                run=run,
                observation=observation,
                cashback_quote=cashback_quote,
                effective_price=effective_price,
                deliveries=deliveries,
            )
        except Exception:
            self.logger.exception("Failed to write watch task run artifact.")

    def _write_watch_group_run_artifact(
        self,
        *,
        group: WatchGroup,
        run: WatchGroupRun,
        member_results: list[dict[str, Any]],
        deliveries: list[DeliveryEvent],
    ) -> None:
        artifact_dir = (
            Path(run.artifact_run_dir)
            if run.artifact_run_dir
            else self._prepare_watch_group_run_artifact_dir(group, run)
        )
        payload = {
            "group": {
                "id": group.id,
                "title": group.title,
                "status": group.status,
                "zip_code": group.zip_code,
                "cadence_minutes": group.cadence_minutes,
                "threshold_type": group.threshold_type,
                "threshold_value": group.threshold_value,
                "cooldown_minutes": group.cooldown_minutes,
                "recipient_email": group.recipient_email,
                "notifications_enabled": group.notifications_enabled,
                "health_status": group.health_status,
            },
            "run": {
                "id": run.id,
                "triggered_by": run.triggered_by,
                "status": run.status,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "finished_at": run.finished_at.isoformat() if run.finished_at else None,
                "error_code": run.error_code,
                "error_message": run.error_message,
                "artifact_run_dir": str(artifact_dir),
                "winner_member_id": run.winner_member_id,
                "winner_effective_price": run.winner_effective_price,
                "runner_up_member_id": run.runner_up_member_id,
                "runner_up_effective_price": run.runner_up_effective_price,
                "price_spread": run.price_spread,
                "decision_reason": run.decision_reason,
            },
            "member_results": member_results,
            "delivery_events": [
                {
                    "id": item.id,
                    "provider": item.provider,
                    "recipient": item.recipient,
                    "status": item.status,
                    "template_key": item.template_key,
                    "created_at": item.created_at.isoformat(),
                    "sent_at": item.sent_at.isoformat() if item.sent_at else None,
                    "delivered_at": item.delivered_at.isoformat() if item.delivered_at else None,
                    "bounced_at": item.bounced_at.isoformat() if item.bounced_at else None,
                }
                for item in deliveries
            ],
        }
        (artifact_dir / "group_run_summary.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _safe_write_watch_group_run_artifact(
        self,
        *,
        group: WatchGroup,
        run: WatchGroupRun,
        member_results: list[dict[str, Any]],
        deliveries: list[DeliveryEvent],
    ) -> None:
        try:
            self._write_watch_group_run_artifact(
                group=group,
                run=run,
                member_results=member_results,
                deliveries=deliveries,
            )
        except Exception:
            self.logger.exception("Failed to write watch group run artifact.")

    async def _build_notification_readiness_check(
        self,
        session: AsyncSession,
        *,
        checked_at: str,
    ) -> dict[str, Any]:
        values = load_settings_values(self.settings)
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
        return self._build_readiness_check(
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

    def _build_smoke_readiness_check(self, *, checked_at: str) -> dict[str, Any]:
        smoke_dir = self._get_smoke_artifact_dir()
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
        return self._build_readiness_check(
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

    def _get_smoke_artifact_dir(self) -> Path:
        return SMOKE_ARTIFACTS_DIR

    @staticmethod
    def _build_readiness_check(
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

    def _attention_sort_key(self, item: dict[str, Any]) -> tuple[Any, ...]:
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

    async def _ensure_owner_preference(self, session: AsyncSession, owner: User) -> UserPreference:
        preference = await session.get(UserPreference, owner.id)
        if preference is None:
            preference = UserPreference(
                user_id=owner.id,
                timezone="America/Los_Angeles",
                currency="USD",
                default_zip_code=self.settings.ZIP_CODE,
                default_check_interval_minutes=self.settings.DEFAULT_TASK_CADENCE_MINUTES,
                default_email_recipient=self.settings.OWNER_EMAIL,
                notification_cooldown_minutes=self.settings.DEFAULT_NOTIFICATION_COOLDOWN_MINUTES,
                notifications_enabled=True,
            )
            session.add(preference)
            await session.flush()
        return preference

    async def _ensure_watch_task_not_running(self, session: AsyncSession, task_id: str) -> None:
        running = await session.scalar(
            select(TaskRun)
            .where(TaskRun.watch_task_id == task_id, TaskRun.status == TaskRunStatus.RUNNING.value)
            .order_by(desc(TaskRun.created_at))
            .limit(1)
        )
        if running is not None:
            raise ValueError("watch_task_already_running")

    async def _ensure_watch_group_not_running(self, session: AsyncSession, group_id: str) -> None:
        running = await session.scalar(
            select(WatchGroupRun)
            .where(WatchGroupRun.watch_group_id == group_id, WatchGroupRun.status == TaskRunStatus.RUNNING.value)
            .order_by(desc(WatchGroupRun.created_at))
            .limit(1)
        )
        if running is not None:
            raise ValueError("watch_group_already_running")

    async def _fetch_cashback_quote_for_target(self, store_key: str, product_url: str) -> dict[str, Any] | None:
        if self.cashback_provider is None:
            return None
        capability = STORE_CAPABILITY_REGISTRY.get(store_key)
        if capability is None or not capability.cashback_supported:
            return None
        adapter_cls = STORE_REGISTRY.get(store_key)
        if adapter_cls is None:
            return None
        quote = await self.cashback_provider.fetch_quote(
            CashbackQuotePayload(
                merchant_key=adapter_cls.get_cashback_merchant_key(),
                product_url=product_url,
            )
        )
        if quote is None:
            return None
        return {
            "provider": quote.provider,
            "merchant_key": quote.merchant_key,
            "rate_type": quote.rate_type,
            "rate_value": quote.rate_value,
            "conditions_text": quote.conditions_text,
            "source_url": quote.source_url,
            "confidence": quote.confidence,
        }

    def _build_task_price_signal(
        self,
        *,
        history_prices: list[float],
        previous_observation: PriceObservation | None,
        observation: PriceObservation,
        effective_price: float,
    ) -> dict[str, Any]:
        previous_listed_price = previous_observation.listed_price if previous_observation is not None else None
        delta_amount = None
        delta_pct = None
        if previous_listed_price is not None and previous_listed_price > 0:
            delta_amount = round(previous_listed_price - observation.listed_price, 2)
            delta_pct = round((delta_amount / previous_listed_price) * 100.0, 2)

        clean_history = [round(float(price), 2) for price in history_prices if price is not None and float(price) > 0]
        historical_low = min(clean_history) if clean_history else None
        is_new_low = historical_low is not None and round(observation.listed_price, 2) < historical_low
        is_anomaly, anomaly_reason = self.rules.is_anomalous_price(observation.listed_price, clean_history)

        reasons: list[str] = []
        if is_new_low:
            reasons.append("new_low")
        if anomaly_reason is not None and is_anomaly:
            reasons.append(f"anomaly:{anomaly_reason.value}")
        if delta_amount is not None and delta_amount > 0:
            reasons.append(f"price_drop:{delta_amount:.2f}")
        if effective_price < observation.listed_price:
            reasons.append("cashback_improved_effective_price")
        if not reasons:
            reasons.append("tracked_observation")

        return {
            "previous_listed_price": previous_listed_price,
            "delta_amount": delta_amount,
            "delta_pct": delta_pct,
            "is_new_low": is_new_low,
            "anomaly_reason": anomaly_reason.value if isinstance(anomaly_reason, AnomalyReason) else None,
            "decision_reason": ", ".join(reasons),
        }

    def _build_group_decision_reason(
        self,
        previous_run: WatchGroupRun | None,
        winner: dict[str, Any],
        runner_up: dict[str, Any] | None,
    ) -> str:
        if previous_run is not None and previous_run.winner_member_id and previous_run.winner_member_id != winner["member_id"]:
            return "winner_changed_to_lower_effective_price"
        if runner_up is None:
            return "single_successful_candidate"
        if float(winner["effective_price"]) < float(winner["listed_price"]):
            return "lowest_effective_price_with_cashback"
        return "lowest_effective_price"

    def _build_watch_group_decision_explain(
        self,
        *,
        group: WatchGroup,
        latest_run: WatchGroupRun | None,
        latest_results: list[dict[str, Any]],
        member_map: dict[str, WatchGroupMember],
    ) -> dict[str, Any]:
        def _decision_summary(code: str | None) -> str | None:
            summaries = {
                "winner_changed_to_lower_effective_price": "A different candidate won because it now has the lower effective price.",
                "single_successful_candidate": "Only one candidate finished successfully in the latest run.",
                "lowest_effective_price_with_cashback": "The winner has the lowest effective price after cashback.",
                "lowest_effective_price": "The winner has the lowest effective price among successful candidates.",
            }
            return summaries.get(str(code), code)

        def _member_snapshot(member_id: str | None, result_map: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
            if not member_id:
                return None
            result = result_map.get(member_id)
            member = member_map.get(member_id)
            if member is None:
                return None
            title_snapshot = result.get("title_snapshot") if result else member.title_snapshot
            return {
                "member_id": member.id,
                "title": title_snapshot,
                "title_snapshot": title_snapshot,
                "candidate_key": member.candidate_key,
                "store_key": result.get("store_key") if result else None,
                "listed_price": result.get("listed_price") if result else None,
                "effective_price": result.get("effective_price") if result else None,
                "cashback_amount": result.get("cashback_amount") if result else None,
                "status": result.get("status") if result else None,
            }

        def _build_loss_reasons(winner: dict[str, Any] | None, runner_up: dict[str, Any] | None) -> list[dict[str, Any]]:
            if winner is None or runner_up is None:
                return []
            winner_effective = float(winner.get("effective_price") or 0.0)
            runner_effective = float(runner_up.get("effective_price") or 0.0)
            winner_listed = float(winner.get("listed_price") or 0.0)
            runner_listed = float(runner_up.get("listed_price") or 0.0)
            if runner_effective > winner_effective:
                delta = round(runner_effective - winner_effective, 2)
                return [
                    {
                        "field": "effective_price",
                        "winner_value": winner_effective,
                        "runner_up_value": runner_effective,
                        "delta": delta,
                        "summary": f"Runner-up effective price is ${delta:.2f} higher.",
                    }
                ]
            if runner_listed > winner_listed:
                delta = round(runner_listed - winner_listed, 2)
                return [
                    {
                        "field": "listed_price",
                        "winner_value": winner_listed,
                        "runner_up_value": runner_listed,
                        "delta": delta,
                        "summary": f"Runner-up listed price is ${delta:.2f} higher.",
                    }
                ]
            return [
                {
                    "field": "store_key",
                    "winner_value": str(winner.get("store_key") or ""),
                    "runner_up_value": str(runner_up.get("store_key") or ""),
                    "delta": None,
                    "summary": "Effective and listed prices tied, so the stable store-key tie-breaker kept the winner first.",
                }
            ]

        if latest_run is None:
            return {
                "headline": "No group decision yet.",
                "decision_reason": None,
                "reason": {"code": None, "summary": None},
                "sort_basis": "effective_price_then_listed_price",
                "winner": None,
                "runner_up": None,
                "comparison": None,
                "spread": None,
                "member_outcomes": [],
                "candidate_outcomes": {
                    "successful_count": 0,
                    "blocked_count": 0,
                    "failed_count": 0,
                },
                "reliability": "weak",
                "risk_notes": ["Run the group once before trusting any current winner."],
                "risk_note_items": [
                    {
                        "code": "no_latest_run",
                        "message": "Run the group once before trusting any current winner.",
                    }
                ],
            }

        result_map = {str(item.get("member_id")): item for item in latest_results}
        successful = [item for item in latest_results if item.get("status") == TaskRunStatus.SUCCEEDED.value]
        blocked = [item for item in latest_results if item.get("status") == TaskRunStatus.BLOCKED.value]
        failed = [item for item in latest_results if item.get("status") == TaskRunStatus.FAILED.value]
        winner = _member_snapshot(latest_run.winner_member_id, result_map)
        runner_up = _member_snapshot(latest_run.runner_up_member_id, result_map)
        comparison = None
        if winner is not None and runner_up is not None:
            comparison = {
                "price_spread": latest_run.price_spread,
                "effective_price_delta": round(
                    float(runner_up["effective_price"] or 0.0) - float(winner["effective_price"] or 0.0),
                    2,
                ),
                "listed_price_delta": round(
                    float(runner_up["listed_price"] or 0.0) - float(winner["listed_price"] or 0.0),
                    2,
                ),
                "cashback_delta": round(
                    float(winner["cashback_amount"] or 0.0) - float(runner_up["cashback_amount"] or 0.0),
                    2,
                ),
            }

        risk_note_items: list[dict[str, Any]] = []
        if latest_run.status != TaskRunStatus.SUCCEEDED.value:
            risk_note_items.append(
                {
                    "code": "latest_run_not_successful",
                    "message": "The latest group run did not finish successfully.",
                }
            )
        if len(successful) < 2:
            risk_note_items.append(
                {
                    "code": "limited_successful_candidates",
                    "message": "This decision is based on fewer than two successful candidates.",
                }
            )
        if blocked:
            risk_note_items.append(
                {
                    "code": "blocked_candidates_present",
                    "message": "At least one candidate was blocked during the latest run.",
                }
            )
        if failed:
            risk_note_items.append(
                {
                    "code": "failed_candidates_present",
                    "message": "At least one candidate failed during the latest run.",
                }
            )
        if latest_run.price_spread is not None and float(latest_run.price_spread) <= 0.5:
            risk_note_items.append(
                {
                    "code": "close_price_spread",
                    "message": "The top two candidates are close on effective price, so small changes may flip the winner.",
                }
            )
        if group.manual_intervention_required:
            risk_note_items.append(
                {
                    "code": "operator_attention_required",
                    "message": "Operator attention is currently required before trusting automation again.",
                }
            )
        risk_notes = [item["message"] for item in risk_note_items]

        if latest_run.status != TaskRunStatus.SUCCEEDED.value or group.manual_intervention_required:
            reliability = "weak"
        elif blocked or failed or len(successful) < 2 or group.health_status != HealthStatus.HEALTHY.value:
            reliability = "caution"
        else:
            reliability = "strong"

        if winner is None:
            headline = "No current winner is available."
        elif runner_up is None:
            headline = f"{winner['title']} is the only successful candidate from the latest run."
        else:
            headline = (
                f"{winner['title']} currently leads {runner_up['title']} by "
                f"${float(latest_run.price_spread or 0.0):.2f} on effective price."
            )

        member_outcomes: list[dict[str, Any]] = []
        seen_member_ids: set[str] = set()
        for result in latest_results:
            member_id = str(result.get("member_id"))
            member = member_map.get(member_id)
            seen_member_ids.add(member_id)
            if member_id == latest_run.winner_member_id:
                outcome = "winner"
            elif member_id == latest_run.runner_up_member_id:
                outcome = "runner_up"
            elif result.get("status") == TaskRunStatus.SUCCEEDED.value:
                outcome = "considered"
            else:
                outcome = str(result.get("status") or "unknown")
            member_outcomes.append(
                {
                    "member_id": member_id,
                    "title_snapshot": result.get("title_snapshot") or (member.title_snapshot if member is not None else None),
                    "candidate_key": member.candidate_key if member is not None else result.get("candidate_key"),
                    "store_key": result.get("store_key"),
                    "status": result.get("status"),
                    "outcome": outcome,
                    "listed_price": result.get("listed_price"),
                    "effective_price": result.get("effective_price"),
                }
            )
        for member_id, member in member_map.items():
            if member_id in seen_member_ids:
                continue
            member_outcomes.append(
                {
                    "member_id": member_id,
                    "title_snapshot": member.title_snapshot,
                    "candidate_key": member.candidate_key,
                    "store_key": None,
                    "status": "missing_latest_result",
                    "outcome": "missing_latest_result",
                    "listed_price": None,
                    "effective_price": None,
                }
            )

        return {
            "headline": headline,
            "decision_reason": latest_run.decision_reason,
            "reason": {
                "code": latest_run.decision_reason,
                "summary": _decision_summary(latest_run.decision_reason),
            },
            "sort_basis": "effective_price_then_listed_price",
            "winner": winner,
            "runner_up": (
                {
                    **runner_up,
                    "loss_reasons": _build_loss_reasons(winner, runner_up),
                }
                if runner_up is not None
                else None
            ),
            "comparison": comparison,
            "spread": (
                {
                    "amount": latest_run.price_spread,
                    "currency": "USD",
                }
                if latest_run.price_spread is not None
                else None
            ),
            "member_outcomes": member_outcomes,
            "candidate_outcomes": {
                "successful_count": len(successful),
                "blocked_count": len(blocked),
                "failed_count": len(failed),
            },
            "reliability": reliability,
            "risk_notes": risk_notes,
            "risk_note_items": risk_note_items,
        }

    def _apply_task_success_state(self, task: WatchTask) -> None:
        task.last_run_at = utcnow()
        task.last_success_at = utcnow()
        task.last_error_code = None
        task.last_error_message = None
        task.status = WatchTaskStatus.ACTIVE.value
        task.next_run_at = utcnow() + timedelta(minutes=task.cadence_minutes)
        task.health_status = HealthStatus.HEALTHY.value
        task.consecutive_failures = 0
        task.backoff_until = None
        task.last_failure_kind = None
        task.manual_intervention_required = False

    def _apply_task_failure_state(
        self,
        task: WatchTask,
        *,
        failure_kind: FailureKind,
        error_code: str,
        error_message: str,
    ) -> None:
        task.last_run_at = utcnow()
        task.last_error_code = error_code
        task.last_error_message = error_message
        task.consecutive_failures += 1
        task.last_failure_kind = failure_kind.value
        task.backoff_until = self._build_backoff_until(task.consecutive_failures, failure_kind=failure_kind)
        if failure_kind == FailureKind.BLOCKED:
            task.health_status = HealthStatus.BLOCKED.value
            task.manual_intervention_required = True
            task.status = WatchTaskStatus.ERROR.value
        elif task.consecutive_failures >= 3:
            task.health_status = HealthStatus.NEEDS_ATTENTION.value
            task.manual_intervention_required = True
            task.status = WatchTaskStatus.ERROR.value
        else:
            task.health_status = HealthStatus.DEGRADED.value
            task.manual_intervention_required = False
            task.status = WatchTaskStatus.ACTIVE.value
            task.next_run_at = task.backoff_until

    def _apply_watch_group_success_state(self, group: WatchGroup) -> None:
        group.last_run_at = utcnow()
        group.last_success_at = utcnow()
        group.last_error_code = None
        group.last_error_message = None
        group.status = WatchTaskStatus.ACTIVE.value
        group.next_run_at = utcnow() + timedelta(minutes=group.cadence_minutes)
        group.health_status = HealthStatus.HEALTHY.value
        group.consecutive_failures = 0
        group.backoff_until = None
        group.last_failure_kind = None
        group.manual_intervention_required = False

    def _apply_watch_group_failure_state(
        self,
        group: WatchGroup,
        *,
        failure_kind: FailureKind,
        error_code: str,
        error_message: str,
    ) -> None:
        group.last_run_at = utcnow()
        group.last_error_code = error_code
        group.last_error_message = error_message
        group.consecutive_failures += 1
        group.last_failure_kind = failure_kind.value
        group.backoff_until = self._build_backoff_until(group.consecutive_failures, failure_kind=failure_kind)
        if failure_kind == FailureKind.BLOCKED:
            group.health_status = HealthStatus.BLOCKED.value
            group.manual_intervention_required = True
            group.status = WatchTaskStatus.ERROR.value
        elif group.consecutive_failures >= 3:
            group.health_status = HealthStatus.NEEDS_ATTENTION.value
            group.manual_intervention_required = True
            group.status = WatchTaskStatus.ERROR.value
        else:
            group.health_status = HealthStatus.DEGRADED.value
            group.manual_intervention_required = False
            group.status = WatchTaskStatus.ACTIVE.value
            group.next_run_at = group.backoff_until

    def _build_backoff_until(self, failures: int, *, failure_kind: FailureKind) -> datetime:
        if failure_kind == FailureKind.BLOCKED:
            minutes = min(max(failures, 1) * 120, 1440)
        else:
            minutes = min(max(failures, 1) * 30, 360)
        return utcnow() + timedelta(minutes=minutes)

    @staticmethod
    def _build_attention_guidance(
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

    @staticmethod
    def _normalize_task_zip_code(value: str | None, *, fallback: str) -> str:
        cleaned = str(value or "").strip()
        if cleaned:
            return cleaned
        fallback_cleaned = str(fallback or "").strip()
        return fallback_cleaned or "00000"

    async def _get_default_rule(self, session: AsyncSession, user_id: str) -> NotificationRule | None:
        return await session.scalar(
            select(NotificationRule)
            .join(WatchTask, NotificationRule.watch_task_id == WatchTask.id)
            .where(WatchTask.user_id == user_id)
            .order_by(desc(NotificationRule.updated_at), desc(NotificationRule.created_at))
            .limit(1)
        )
