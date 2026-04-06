from __future__ import annotations

import asyncio
import logging
from uuid import uuid4

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from dealwatch.application import ProductService
from dealwatch.infra.config import clear_log_context, set_log_context, settings
from dealwatch.persistence.store_bindings import sync_store_adapter_bindings
from dealwatch.jobs.maintenance import MaintenanceJob, maintenance_lock
from dealwatch.persistence.session import create_session_factory, init_product_database
from dealwatch.runtime_preflight import ensure_runtime_contract_from_settings


async def _run_due_tasks(service: ProductService) -> None:
    set_log_context(service_name="worker", correlation_id=f"worker-tick-{uuid4()}")
    try:
        await service.process_due_tasks()
        await service.process_due_watch_groups()
    finally:
        clear_log_context()


async def _run_housekeeping() -> None:
    logger = logging.getLogger(__name__)
    set_log_context(service_name="worker", correlation_id=f"worker-housekeeping-{uuid4()}")
    try:
        lock_path = settings.MAINTENANCE_LOCK_PATH
        with maintenance_lock(lock_path) as acquired:
            if not acquired:
                logger.info("Housekeeping skipped because the maintenance lock is busy: %s", lock_path)
                return
            summary = await MaintenanceJob(
                repo=None,
                runs_dir=settings.RUNS_DIR,
                logs_dir=settings.LOGS_DIR,
                operator_dir=settings.OPERATOR_ARTIFACTS_DIR,
                external_cache_dir=settings.EXTERNAL_CACHE_DIR,
                runs_keep_days=settings.RUNS_KEEP_DAYS,
                reports_keep_days=settings.REPORTS_KEEP_DAYS,
                log_retention_days=settings.LOG_RETENTION_DAYS,
                cache_budget_bytes=settings.CACHE_BUDGET_BYTES,
                dry_run=False,
                clean_runtime=True,
                clean_legacy=False,
            ).run()
            logger.info(
                "Housekeeping completed: matched=%s estimated_reclaim_bytes=%s",
                summary.matched_count,
                summary.estimated_bytes,
            )
    finally:
        clear_log_context()


async def run_once() -> int:
    set_log_context(service_name="worker", correlation_id=f"worker-run-once-{uuid4()}")
    ensure_runtime_contract_from_settings(settings, "startup")
    session_factory = create_session_factory(settings.DATABASE_URL)
    await init_product_database(settings, session_factory)
    await sync_store_adapter_bindings(session_factory, settings)
    service = ProductService(session_factory=session_factory, settings=settings)
    try:
        await service.process_due_tasks()
        await service.process_due_watch_groups()
        return 0
    finally:
        clear_log_context()


async def run_worker() -> None:
    set_log_context(service_name="worker", correlation_id="worker-main")
    ensure_runtime_contract_from_settings(settings, "startup")
    session_factory = create_session_factory(settings.DATABASE_URL)
    await init_product_database(settings, session_factory)
    await sync_store_adapter_bindings(session_factory, settings)
    service = ProductService(session_factory=session_factory, settings=settings)

    scheduler = AsyncIOScheduler(timezone="America/Los_Angeles")
    scheduler.add_job(
        _run_due_tasks,
        trigger="interval",
        seconds=max(int(settings.WORKER_POLL_SECONDS), 10),
        kwargs={"service": service},
        id="dealwatch-due-tasks",
        replace_existing=True,
    )
    if settings.MAINTENANCE_ENABLED:
        scheduler.add_job(
            _run_housekeeping,
            trigger="cron",
            hour=int(settings.MAINTENANCE_HOUR_LOCAL),
            minute=int(settings.MAINTENANCE_MINUTE_LOCAL),
            id="dealwatch-housekeeping",
            replace_existing=True,
        )
    scheduler.start()
    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        scheduler.shutdown(wait=False)


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
