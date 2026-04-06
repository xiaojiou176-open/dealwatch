from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select

from dealwatch.application.services import ProductService
from dealwatch.core.models import Offer, PriceContext
from dealwatch.infra.config import Settings
from dealwatch.persistence.models import DeliveryEvent, PriceObservation, TaskRun, WatchTask
from dealwatch.persistence.session import get_session_factory, init_product_database
from dealwatch.persistence.store_bindings import sync_store_adapter_bindings
from dealwatch.providers.cashback.base import CashbackQuoteResult
from dealwatch.providers.email.base import EmailDispatchResult


class _SmokeCashbackProvider:
    async def fetch_quote(self, payload: Any) -> CashbackQuoteResult:
        return CashbackQuoteResult(
            provider="cashbackmonitor",
            merchant_key=payload.merchant_key,
            rate_type="percent",
            rate_value=8.0,
            conditions_text="smoke-test",
            source_url="https://example.com/cashback",
            confidence=0.9,
        )


class _SmokeEmailProvider:
    async def send(self, payload: Any) -> EmailDispatchResult:
        return EmailDispatchResult(
            provider="smoke-email",
            status="sent",
            message_id="smoke-message-1",
            payload={"recipient": payload.recipient, "template_key": payload.template_key},
        )


async def _fake_fetch_offer(*_: Any, **__: Any) -> Offer:
    product_url = str(__.get("product_url") or (_[0] if _ else ""))
    hostname = urlparse(product_url).hostname or ""
    if hostname == "www.99ranch.com" or hostname.endswith(".99ranch.com"):
        return Offer(
            store_id="ranch99",
            product_key="smoke-ranch-pears",
            title="Smoke Test Pears 3 ct",
            url="https://www.99ranch.com/product-details/1615424/8899/078895126389",
            price=4.49,
            original_price=5.29,
            fetch_at=datetime.now(timezone.utc),
            context=PriceContext(region="98004"),
            unit_price_info={"raw": "3 ct"},
        )
    return Offer(
        store_id="weee",
        product_key="smoke-5869",
        title="Smoke Test Pears 3ct",
        url="https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
        price=4.2,
        original_price=5.5,
        fetch_at=datetime.now(timezone.utc),
        context=PriceContext(region="98004"),
        unit_price_info={"raw": "3ct"},
    )


async def main() -> int:
    base_settings = Settings()
    runtime_settings = Settings(
        DATABASE_URL=base_settings.DATABASE_URL,
        OWNER_EMAIL=base_settings.OWNER_EMAIL,
        OWNER_DISPLAY_NAME=base_settings.OWNER_DISPLAY_NAME,
        OWNER_BOOTSTRAP_TOKEN=base_settings.OWNER_BOOTSTRAP_TOKEN,
        SMTP_HOST="",
        ZIP_CODE=base_settings.ZIP_CODE or "98004",
        POSTMARK_FROM_EMAIL=base_settings.POSTMARK_FROM_EMAIL,
        POSTMARK_MESSAGE_STREAM=base_settings.POSTMARK_MESSAGE_STREAM,
        PRODUCT_AUTO_CREATE_SCHEMA=base_settings.PRODUCT_AUTO_CREATE_SCHEMA,
        ENABLED_STORES=["weee", "ranch99"],
    )

    await init_product_database(runtime_settings)
    session_factory = get_session_factory(runtime_settings.DATABASE_URL)
    await sync_store_adapter_bindings(session_factory, runtime_settings)
    service = ProductService(
        session_factory=session_factory,
        settings=runtime_settings,
        cashback_provider=_SmokeCashbackProvider(),
        email_provider=_SmokeEmailProvider(),
    )
    service._fetch_offer = _fake_fetch_offer  # type: ignore[method-assign]

    async with session_factory() as session:
        owner = await service.bootstrap_owner(session)
        await session.commit()
        owner_id = owner.id

    async with session_factory() as session:
        task = await service.create_watch_task(
            session,
            submitted_url="https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
            zip_code=runtime_settings.ZIP_CODE or "98004",
            cadence_minutes=60,
            threshold_type="price_below",
            threshold_value=4.5,
            cooldown_minutes=30,
            recipient_email=runtime_settings.OWNER_EMAIL,
            compare_handoff={
                "title_snapshot": "Smoke Test Pears 3ct",
                "store_key": "weee",
                "candidate_key": "smoke test pears 3ct | 3 ct",
                "brand_hint": None,
                "size_hint": "3ct",
            },
        )
        await session.commit()
        task_id = task.id

    async with session_factory() as session:
        run = await service.run_watch_task(session, task_id, triggered_by="smoke")
        await session.commit()
        run_id = run.id

    async with session_factory() as session:
        group = await service.create_watch_group(
            session,
            title="Smoke Test Group",
            zip_code=runtime_settings.ZIP_CODE or "98004",
            cadence_minutes=60,
            threshold_type="effective_price_below",
            threshold_value=4.5,
            cooldown_minutes=30,
            recipient_email=runtime_settings.OWNER_EMAIL,
            notifications_enabled=True,
            candidates=[
                {
                    "submitted_url": "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
                    "title_snapshot": "Smoke Test Pears 3ct",
                    "store_key": "weee",
                    "candidate_key": "smoke test pears 3ct | 3 ct",
                },
                {
                    "submitted_url": "https://www.99ranch.com/product-details/1615424/8899/078895126389",
                    "title_snapshot": "Smoke Test Pears 3 ct",
                    "store_key": "ranch99",
                    "candidate_key": "smoke test pears 3 ct | 3 ct",
                },
            ],
        )
        await session.commit()
        group_id = group.id

    async with session_factory() as session:
        group_run = await service.run_watch_group(session, group_id, triggered_by="smoke")
        await session.commit()
        group_run_id = group_run.id

    async with session_factory() as session:
        task = await session.get(WatchTask, task_id)
        run = await session.get(TaskRun, run_id)
        observation = await session.scalar(
            select(PriceObservation).where(PriceObservation.watch_task_id == task_id).limit(1)
        )
        delivery = await session.scalar(
            select(DeliveryEvent).where(DeliveryEvent.watch_task_id == task_id).limit(1)
        )
        if task is None or run is None or observation is None or delivery is None:
            raise RuntimeError("product_smoke_incomplete")
        if task.user_id != owner_id:
            raise RuntimeError("product_smoke_owner_mismatch")
        if task.zip_code != (runtime_settings.ZIP_CODE or "98004"):
            raise RuntimeError("product_smoke_task_zip_mismatch")
        if not run.artifact_run_dir:
            raise RuntimeError("product_smoke_missing_artifact_run_dir")

        artifact_dir = Path(run.artifact_run_dir)
        summary_path = artifact_dir / "task_run_summary.json"
        if not artifact_dir.is_dir() or not summary_path.is_file():
            raise RuntimeError("product_smoke_missing_artifact_files")
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if summary["run"]["id"] != run_id:
            raise RuntimeError("product_smoke_artifact_run_id_mismatch")
        if summary["task"]["zip_code"] != task.zip_code:
            raise RuntimeError("product_smoke_artifact_zip_mismatch")
        if summary["delivery_events"][0]["status"] != delivery.status:
            raise RuntimeError("product_smoke_artifact_delivery_mismatch")
        detail = await service.get_watch_task_detail(session, task_id)
        if detail["compare_context"] is None:
            raise RuntimeError("product_smoke_missing_compare_context")
        group_detail = await service.get_watch_group_detail(session, group_id)
        if group_detail["group"]["member_count"] != 2:
            raise RuntimeError("product_smoke_group_member_count_mismatch")
        if not group_detail["group"]["current_winner_effective_price"]:
            raise RuntimeError("product_smoke_missing_group_winner")
        if not group_run.artifact_run_dir:
            raise RuntimeError("product_smoke_missing_group_artifact_run_dir")

    print(
        "SMOKE_OK",
        f"task_id={task_id}",
        f"run_id={run_id}",
        f"group_id={group_id}",
        f"group_run_id={group_run_id}",
        f"artifact_run_dir={run.artifact_run_dir}",
        f"price={observation.listed_price}",
        f"delivery={delivery.status}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
