from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Iterable

from dealwatch.core.ai_analyzer import AIAnalyzer
from dealwatch.core.artifacts import ArtifactManager
from dealwatch.api.deps import get_product_service, prepare_product_runtime
from dealwatch.builder_contract import list_client_ids
from dealwatch.core.models import RunStats
from dealwatch.core.pipeline import MonitoringPipeline
from dealwatch.infra.config import load_enabled_stores_from_yaml, settings
from dealwatch.infra.browser_debug import diagnose_browser_debug, probe_browser_debug, write_browser_support_bundle
from dealwatch.infra.mailer import EmailNotifier
from dealwatch.infra.obs.health_check import HealthMonitor
from dealwatch.infra.playwright_client import PlaywrightClient
from dealwatch.infra.retry_budget import RetryBudget
from dealwatch.jobs.maintenance import MaintenanceJob, maintenance_lock
from dealwatch.legacy.db_repo import DatabaseRepository
from dealwatch.persistence.session import session_scope
from dealwatch.server import main as server_main
from dealwatch.stores import STORE_REGISTRY
from dealwatch.worker.main import main as worker_main, run_once as worker_run_once

RUNTIME_COMMANDS = (
    "server",
    "worker",
    "run-due",
)
BUILDER_DISCOVERY_COMMANDS = (
    "builder-starter-pack",
    "builder-client-config",
)
OPERATOR_ONLY_COMMANDS = (
    "bootstrap-owner",
    "maintenance",
    "probe-live",
    "diagnose-live",
    "support-bundle",
)
LEGACY_BRIDGE_COMMANDS = ("legacy-import", "legacy-maintenance")
LEGACY_ALIAS = "legacy"


def _command_help() -> str:
    runtime_lines = {
        "server": "Run the FastAPI product API.",
        "worker": "Run the APScheduler product worker.",
        "run-due": "Execute due product tasks once.",
    }
    builder_lines = {
        "builder-starter-pack": "Print the repo-owned read-only builder contract as JSON.",
        "builder-client-config": "Print one or all repo-owned builder client config exports.",
    }
    operator_lines = {
        "bootstrap-owner": "Bootstrap the product owner in PostgreSQL.",
        "maintenance": "Run product runtime maintenance for .runtime-cache.",
        "probe-live": "Maintainer-only browser debug lane probe.",
        "diagnose-live": "Maintainer-only browser debug lane diagnosis.",
        "support-bundle": "Write a maintainer-only browser debug support bundle.",
    }
    legacy_lines = {
        "legacy-import": "Run the deprecated SQLite bridge importer.",
        "legacy-maintenance": "Run the deprecated SQLite bridge maintenance tasks.",
        LEGACY_ALIAS: "Deprecated alias for the legacy bridge commands.",
    }
    return "".join(
        [
            "Runtime commands:\n",
            *[f"  {command:<18} {runtime_lines[command]}\n" for command in RUNTIME_COMMANDS],
            "\n",
            "Builder discovery commands:\n",
            *[
                f"  {command:<18} {builder_lines[command]}\n"
                for command in BUILDER_DISCOVERY_COMMANDS
            ],
            "\n",
            "Operator-only maintainer commands:\n",
            *[
                f"  {command:<18} {operator_lines[command]}\n"
                for command in OPERATOR_ONLY_COMMANDS
            ],
            "\n",
            "Legacy bridge commands:\n",
            *[
                f"  {command:<18} {legacy_lines[command]}\n"
                for command in (*LEGACY_BRIDGE_COMMANDS, LEGACY_ALIAS)
            ],
        ]
    )


def _print_main_help(stream: object) -> None:
    print("Usage: python -m dealwatch <command> [...].", file=stream)
    print("", file=stream)
    print(_command_help(), file=stream)


def _parse_legacy_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="DealWatch legacy SQLite bridge importer (deprecated)"
    )
    parser.add_argument(
        "--store",
        action="append",
        default=[],
        help="Import only specific store IDs from the deprecated SQLite bridge (repeat or comma-separated).",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Deprecated alias switch for bridge maintenance; prefer legacy-maintenance.",
    )
    parser.add_argument(
        "--zip",
        default="",
        help="Override ZIP code for the legacy bridge run (also switches storage_state to storage_state_{zip}.json).",
    )
    return parser.parse_args(argv)


def _parse_legacy_maintenance_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="DealWatch legacy SQLite bridge maintenance (deprecated)"
    )
    return parser.parse_args(argv)


def _parse_bootstrap_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DealWatch owner bootstrap")
    parser.add_argument("--email", default=settings.OWNER_EMAIL)
    parser.add_argument("--display-name", default=settings.OWNER_DISPLAY_NAME)
    parser.add_argument("--token", default="")
    return parser.parse_args(argv)


def _parse_maintenance_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="DealWatch product runtime maintenance"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Show which runtime objects would be cleaned without deleting them.",
    )
    mode.add_argument(
        "--apply",
        action="store_true",
        help="Delete matched runtime maintenance targets.",
    )
    return parser.parse_args(argv)


def _parse_builder_starter_pack_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DealWatch builder starter pack")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON output instead of a plain-text summary.",
    )
    return parser.parse_args(argv)


def _parse_builder_client_config_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DealWatch builder client config export")
    parser.add_argument(
        "client",
        nargs="?",
        choices=tuple(list_client_ids()),
        help="Client key such as claude-code, codex, openhands, opencode, or openclaw.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Emit the repo-owned config export bundle for every supported client.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON output instead of the raw example config body.",
    )
    args = parser.parse_args(argv)
    if bool(args.client) == bool(args.all):
        parser.error("builder-client-config requires exactly one of <client> or --all")
    return args


def _parse_browser_debug_args(argv: list[str], *, description: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON output. JSON is the default and recommended for maintainer tooling.",
    )
    return parser.parse_args(argv)


def _normalize_store_args(values: Iterable[str]) -> list[str]:
    results: list[str] = []
    for value in values:
        for item in str(value).split(","):
            item = item.strip()
            if item:
                results.append(item)
    return results


#########################################################
# Main
#########################################################
async def _run_legacy_import(argv: list[str], *, deprecated_alias: bool = False) -> int:
    logger = logging.getLogger(__name__)
    args = _parse_legacy_args(argv)
    if args.cleanup:
        return await _run_legacy_maintenance([], deprecated_alias=True)

    if deprecated_alias:
        logger.warning(
            "The 'legacy' command is deprecated. Use 'legacy-import' for the explicit SQLite bridge path."
        )
    logger.warning("Running deprecated SQLite bridge import; product commands use PostgreSQL instead.")

    if args.zip:
        settings.ZIP_CODE = str(args.zip).strip()

    requested = _normalize_store_args(args.store)
    config_enabled = load_enabled_stores_from_yaml()
    enabled = requested or config_enabled or settings.ENABLED_STORES or list(STORE_REGISTRY.keys())

    if not enabled:
        logger.error("No enabled stores configured.")
        return 1

    repo = DatabaseRepository(settings.DB_PATH)
    await repo.initialize()
    artifacts = ArtifactManager(base_dir=settings.RUNS_DIR)
    notifier = EmailNotifier(settings)
    analyzer = AIAnalyzer(settings)
    health = HealthMonitor(repo, notifier)

    subject_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    all_deals = []
    total_checked_all = 0

    try:
        storage_state_path = settings.build_storage_state_path()
        retry_budget = (
            RetryBudget(settings.PLAYWRIGHT_RETRY_BUDGET)
            if settings.PLAYWRIGHT_RETRY_BUDGET and settings.PLAYWRIGHT_RETRY_BUDGET > 0
            else None
        )
        async with PlaywrightClient(
            headless=settings.PLAYWRIGHT_HEADLESS,
            storage_state_path=storage_state_path,
            proxy_server=settings.PROXY_SERVER or None,
            block_stylesheets=settings.PLAYWRIGHT_BLOCK_STYLESHEETS,
            retry_budget=retry_budget,
            runs_dir=settings.RUNS_DIR,
        ) as client:
            pipeline = MonitoringPipeline(repo, client, settings)

            for store_id in enabled:
                adapter_cls = STORE_REGISTRY.get(store_id)
                if adapter_cls is None:
                    logger.warning("Store '%s' is not registered.", store_id)
                    continue

                start_time = datetime.now(timezone.utc)
                deals = []

                try:
                    adapter = adapter_cls(client, settings)
                    deals = await pipeline.run_store(adapter)
                except Exception as exc:
                    logger.exception("Store run failed for %s: %s", store_id, exc)

                stats = pipeline.last_stats
                if stats is None or stats.store_id != store_id:
                    stats = RunStats(
                        store_id=store_id,
                        start_time=start_time,
                        discovered_count=0,
                        parsed_count=0,
                        error_count=1,
                        confirmed_deals_count=len(deals),
                    )

                await health.record_run(stats)
                try:
                    run_dir = artifacts.get_run_dir()
                except Exception as exc:
                    logger.warning("Failed to resolve run dir for health check: %s", exc)
                    run_dir = None

                issues = await health.evaluate(
                    stats,
                    failed_urls=pipeline.last_failed_urls,
                    error_snippet=pipeline.last_error_snippet,
                    run_dir=run_dir,
                )

                if "IP_RESTRICTED" in issues:
                    logger.error(
                        "IP restriction detected for %s; skipping artifacts.",
                        store_id,
                    )
                    continue

                store_checked = stats.discovered_count
                total_checked_all += store_checked

                try:
                    artifacts.save_deals(
                        deals,
                        store_id,
                        total_checked=store_checked,
                    )
                except Exception as exc:
                    logger.exception("Failed to save artifacts for %s: %s", store_id, exc)

                all_deals.extend(deals)

            try:
                await client.save_state()
            except Exception as exc:
                logger.exception("Failed to save storage state: %s", exc)

        if all_deals:
            combined_path = artifacts.save_deals(
                all_deals,
                "all",
                total_checked=total_checked_all,
            )
            html_summary = await analyzer.analyze(combined_path)
            await asyncio.to_thread(
                notifier.send_daily_report,
                html_summary,
                subject_date,
            )
        else:
            logger.info("No confirmed deals found; skipping AI summary and email.")
    finally:
        await repo.close()

    return 0


async def _run_legacy_maintenance(argv: list[str], *, deprecated_alias: bool = False) -> int:
    logger = logging.getLogger(__name__)
    _parse_legacy_maintenance_args(argv)
    if deprecated_alias:
        logger.warning(
            "The 'legacy' command is deprecated. Use 'legacy-maintenance' for the explicit SQLite bridge maintenance path."
        )
    logger.warning("Running deprecated SQLite bridge maintenance; product commands use PostgreSQL instead.")
    repo = DatabaseRepository(settings.DB_PATH)
    try:
        await repo.initialize()
        job = MaintenanceJob(
            repo=repo,
            runs_dir=settings.RUNS_DIR,
            logs_dir=settings.LOGS_DIR,
            operator_dir=settings.OPERATOR_ARTIFACTS_DIR,
            external_cache_dir=settings.EXTERNAL_CACHE_DIR,
            backups_dir=settings.BACKUPS_DIR,
            price_history_keep_days=settings.PRICE_HISTORY_KEEP_DAYS,
            runs_keep_days=settings.RUNS_KEEP_DAYS,
            reports_keep_days=settings.REPORTS_KEEP_DAYS,
            backups_keep_days=settings.BACKUPS_KEEP_DAYS,
            log_retention_days=settings.LOG_RETENTION_DAYS,
            cache_budget_bytes=settings.CACHE_BUDGET_BYTES,
            clean_runtime=False,
            clean_legacy=True,
        )
        summary = await job.run()
        print(summary.render_text())
        return 0
    finally:
        await repo.close()


async def _run_product_maintenance(argv: list[str]) -> int:
    args = _parse_maintenance_args(argv)
    logger = logging.getLogger(__name__)
    lock_path = settings.MAINTENANCE_LOCK_PATH

    with maintenance_lock(lock_path) as acquired:
        if not acquired:
            logger.warning("Product maintenance skipped because the maintenance lock is busy: %s", lock_path)
            print("DealWatch maintenance\nstatus=skipped\nreason=lock-busy")
            return 0

        job = MaintenanceJob(
            repo=None,
            runs_dir=settings.RUNS_DIR,
            logs_dir=settings.LOGS_DIR,
            operator_dir=settings.OPERATOR_ARTIFACTS_DIR,
            external_cache_dir=settings.EXTERNAL_CACHE_DIR,
            runs_keep_days=settings.RUNS_KEEP_DAYS,
            reports_keep_days=settings.REPORTS_KEEP_DAYS,
            log_retention_days=settings.LOG_RETENTION_DAYS,
            cache_budget_bytes=settings.CACHE_BUDGET_BYTES,
            dry_run=args.dry_run,
            clean_runtime=True,
            clean_legacy=False,
        )
        summary = await job.run()
        print(summary.render_text())
        return 0


async def _run_legacy(argv: list[str]) -> int:
    args = _parse_legacy_args(argv)
    if args.cleanup:
        return await _run_legacy_maintenance([], deprecated_alias=True)
    filtered_argv = [value for value in argv if value != "--cleanup"]
    return await _run_legacy_import(filtered_argv, deprecated_alias=True)


async def _bootstrap_owner(argv: list[str]) -> int:
    args = _parse_bootstrap_args(argv)
    configured_token = settings.OWNER_BOOTSTRAP_TOKEN.get_secret_value().strip()
    if not configured_token:
        raise RuntimeError("OWNER_BOOTSTRAP_TOKEN is not configured")
    if args.token != configured_token:
        raise RuntimeError("owner_bootstrap_token_invalid")
    await prepare_product_runtime()
    settings.OWNER_EMAIL = args.email
    settings.OWNER_DISPLAY_NAME = args.display_name
    async with session_scope() as session:
        service = get_product_service()
        owner = await service.bootstrap_owner(session)
    print(f"Bootstrapped owner user: {owner.email}")
    return 0


async def _run_builder_starter_pack(argv: list[str]) -> int:
    args = _parse_builder_starter_pack_args(argv)
    payload = await get_product_service().get_builder_starter_pack()
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("DealWatch builder starter pack")
        print(f"surface_version={payload['surface_version']}")
        print(f"public_builder_page={payload['public_builder_page']}")
        print(f"builder_pack={payload['docs']['builder_pack']}")
        print(f"skill_pack={payload['skill_pack']['path']}")
        print(f"mcp_client_starters={payload['launch_contract']['mcp_client_starters']}")
    return 0


async def _run_builder_client_config(argv: list[str]) -> int:
    args = _parse_builder_client_config_args(argv)
    service = get_product_service()
    payload = (
        await service.get_builder_client_configs()
        if args.all
        else await service.get_builder_client_config(args.client)
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        if args.all:
            print("DealWatch builder client config bundle")
            print(f"client_count={payload['client_count']}")
            for item in payload["clients"]:
                print(f"- {item['client']}: {item['wrapper_example_path']}")
        else:
            print(payload["wrapper_example_content"], end="")
            if not payload["wrapper_example_content"].endswith("\n"):
                print("")
    return 0


async def _run_probe_live(argv: list[str]) -> int:
    _parse_browser_debug_args(argv, description="DealWatch maintainer browser debug probe")
    payload = await probe_browser_debug(settings)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


async def _run_diagnose_live(argv: list[str]) -> int:
    _parse_browser_debug_args(argv, description="DealWatch maintainer browser debug diagnosis")
    payload = await diagnose_browser_debug(settings)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


async def _run_support_bundle(argv: list[str]) -> int:
    _parse_browser_debug_args(argv, description="DealWatch maintainer browser debug support bundle")
    diagnosis = await diagnose_browser_debug(settings)
    bundle = write_browser_support_bundle(settings, diagnosis)
    print(json.dumps(bundle, ensure_ascii=False, indent=2))
    return 0


def main() -> None:
    if len(sys.argv) <= 1:
        _print_main_help(sys.stderr)
        raise SystemExit(2)

    command = sys.argv[1]
    if command in {"-h", "--help", "help"}:
        _print_main_help(sys.stdout)
        return
    if command == "server":
        server_main()
        return
    if command == "worker":
        worker_main()
        return
    if command == "run-due":
        raise SystemExit(asyncio.run(worker_run_once()))
    if command == "builder-starter-pack":
        raise SystemExit(asyncio.run(_run_builder_starter_pack(sys.argv[2:])))
    if command == "builder-client-config":
        raise SystemExit(asyncio.run(_run_builder_client_config(sys.argv[2:])))
    if command == "bootstrap-owner":
        raise SystemExit(asyncio.run(_bootstrap_owner(sys.argv[2:])))
    if command == "maintenance":
        raise SystemExit(asyncio.run(_run_product_maintenance(sys.argv[2:])))
    if command == "probe-live":
        raise SystemExit(asyncio.run(_run_probe_live(sys.argv[2:])))
    if command == "diagnose-live":
        raise SystemExit(asyncio.run(_run_diagnose_live(sys.argv[2:])))
    if command == "support-bundle":
        raise SystemExit(asyncio.run(_run_support_bundle(sys.argv[2:])))
    if command == "legacy-import":
        raise SystemExit(asyncio.run(_run_legacy_import(sys.argv[2:])))
    if command == "legacy-maintenance":
        raise SystemExit(asyncio.run(_run_legacy_maintenance(sys.argv[2:])))
    if command == LEGACY_ALIAS:
        raise SystemExit(asyncio.run(_run_legacy(sys.argv[2:])))

    print(f"Unknown DealWatch command: {command}.", file=sys.stderr)
    print("", file=sys.stderr)
    _print_main_help(sys.stderr)
    raise SystemExit(2)


if __name__ == "__main__":
    main()
