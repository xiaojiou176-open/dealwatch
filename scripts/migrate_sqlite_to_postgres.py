from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime, timezone

from sqlalchemy import select

from dealwatch.application.urls import resolve_store_for_url
from dealwatch.domain.enums import ResolutionStatus, WatchTaskStatus
from dealwatch.infra.config import migrate_default_legacy_storage, settings
from dealwatch.persistence.models import (
    NotificationRule,
    PriceObservation,
    TaskRun,
    User,
    UserPreference,
    WatchTarget,
    WatchTask,
)
from dealwatch.persistence.session import create_session_factory, init_product_database


async def migrate() -> None:
    session_factory = create_session_factory(settings.DATABASE_URL)
    await init_product_database(settings, session_factory)
    migrate_default_legacy_storage(db_path=settings.DB_PATH, backups_dir=settings.BACKUPS_DIR)

    sqlite_conn = sqlite3.connect(str(settings.DB_PATH))
    sqlite_conn.row_factory = sqlite3.Row
    products = sqlite_conn.execute("SELECT store_id, product_key, url, title, last_updated FROM products").fetchall()
    price_rows = sqlite_conn.execute(
        "SELECT store_id, product_key, price, original_price, context_hash, timestamp FROM price_history ORDER BY timestamp ASC"
    ).fetchall()

    async with session_factory() as session:
        owner = await session.scalar(select(User).where(User.email == settings.OWNER_EMAIL))
        if owner is None:
            owner = User(
                email=settings.OWNER_EMAIL,
                display_name=settings.OWNER_DISPLAY_NAME,
                role="owner",
                status="active",
            )
            session.add(owner)
            await session.flush()
            session.add(
                UserPreference(
                    user_id=owner.id,
                    timezone="America/Los_Angeles",
                    currency="USD",
                    default_zip_code=settings.ZIP_CODE,
                    default_check_interval_minutes=settings.DEFAULT_TASK_CADENCE_MINUTES,
                    default_email_recipient=settings.OWNER_EMAIL,
                    notification_cooldown_minutes=settings.DEFAULT_NOTIFICATION_COOLDOWN_MINUTES,
                    notifications_enabled=True,
                )
            )
            await session.flush()

        targets_by_key: dict[tuple[str, str], tuple[WatchTarget, WatchTask]] = {}
        for row in products:
            raw_url = str(row["url"])
            resolved = resolve_store_for_url(raw_url)
            if not resolved.supported:
                continue
            target = WatchTarget(
                user_id=owner.id,
                submitted_url=raw_url,
                normalized_url=resolved.normalized_url,
                store_key=resolved.store_key,
                product_url=resolved.product_url,
                target_type="product_url",
                resolution_status=ResolutionStatus.RESOLVED.value,
            )
            session.add(target)
            await session.flush()
            task = WatchTask(
                user_id=owner.id,
                watch_target_id=target.id,
                zip_code=settings.ZIP_CODE,
                status=WatchTaskStatus.ACTIVE.value,
                cadence_minutes=settings.DEFAULT_TASK_CADENCE_MINUTES,
                threshold_type=settings.DEFAULT_THRESHOLD_TYPE,
                threshold_value=5.0,
                cooldown_minutes=settings.DEFAULT_NOTIFICATION_COOLDOWN_MINUTES,
                next_run_at=datetime.now(timezone.utc),
            )
            session.add(task)
            await session.flush()
            session.add(
                NotificationRule(
                    watch_task_id=task.id,
                    channel="email",
                    enabled=True,
                    cooldown_minutes=settings.DEFAULT_NOTIFICATION_COOLDOWN_MINUTES,
                    recipient_email=settings.OWNER_EMAIL,
                    template_key="legacy-import",
                )
            )
            await session.flush()
            targets_by_key[(str(row["store_id"]), str(row["product_key"]))] = (target, task)

        for row in price_rows:
            pair = targets_by_key.get((str(row["store_id"]), str(row["product_key"])))
            if pair is None:
                continue
            target, task = pair
            observed_at = datetime.fromisoformat(str(row["timestamp"]))
            run = TaskRun(
                watch_task_id=task.id,
                triggered_by="bootstrap",
                status="succeeded",
                started_at=observed_at,
                finished_at=observed_at,
                engine_store_key=str(row["store_id"]),
                engine_product_key=str(row["product_key"]),
            )
            session.add(run)
            await session.flush()
            session.add(
                PriceObservation(
                    watch_task_id=task.id,
                    task_run_id=run.id,
                    listed_price=float(row["price"]),
                    original_price=float(row["original_price"]) if row["original_price"] is not None else None,
                    currency="USD",
                    availability="available",
                    title_snapshot=str(row["product_key"]),
                    unit_price_raw=None,
                    source_url=target.product_url,
                    observed_at=observed_at,
                    parser_version="legacy-import",
                )
            )

        await session.commit()

    sqlite_conn.close()


def main() -> None:
    asyncio.run(migrate())


if __name__ == "__main__":
    main()
