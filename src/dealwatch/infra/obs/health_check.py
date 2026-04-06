from __future__ import annotations

import asyncio
import html
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from dealwatch.core.models import RunStats
from dealwatch.infra.mailer import EmailNotifier
from dealwatch.legacy.db_repo import DatabaseRepository


#########################################################
# Health Monitor
#########################################################
_BLOCKED_SIGNAL: str = "IP_RESTRICTED"
_FAILURE_INDEX_NAME: str = "failures_index.ndjson"
_BLOCKED_INDEX_NAME: str = "blocked_index.ndjson"
_ARTIFACT_SNIPPET_LIMIT: int = 5
_REPORTS_DIR_NAME: str = "reports"
_AUDIT_REPORT_PREFIX: str = "artifact_audit_"


@dataclass(slots=True)
class HealthMonitor:
    repo: DatabaseRepository
    notifier: EmailNotifier
    logger: logging.Logger = field(init=False, repr=False)
    _last_stats: RunStats | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        self.logger = logging.getLogger(__name__)

    async def record_run(self, stats: RunStats) -> None:
        self._last_stats = stats
        try:
            await self.repo.insert_run_stats(stats)
        except Exception as exc:
            self.logger.exception("Failed to persist run stats: %s", exc)

    async def evaluate(
        self,
        stats: RunStats,
        failed_urls: Optional[List[str]] = None,
        error_snippet: str | None = None,
        run_dir: Path | None = None,
    ) -> List[str]:
        self._last_stats = stats
        issues: list[str] = []

        if error_snippet and _BLOCKED_SIGNAL in error_snippet:
            issues.append(_BLOCKED_SIGNAL)

        if stats.discovered_count == 0:
            issues.append("DISCOVERY_EMPTY")
        else:
            effective_total = max(stats.discovered_count - stats.skipped_count, 0)
            if effective_total > 0:
                success_ratio = stats.parsed_count / effective_total
                if success_ratio < 0.7:
                    issues.append("PARSE_RATE_LOW")

        artifact_context = self._build_artifact_context(run_dir)
        for issue in issues:
            details = self._build_details(
                stats=stats,
                issue_type=issue,
                failed_urls=failed_urls or [],
                error_snippet=error_snippet or "",
                artifact_context=artifact_context,
            )
            await self.send_alert_email(issue, details)

        return issues

    async def send_alert_email(self, issue_type: str, details: str) -> None:
        stats = self._last_stats
        store_id = stats.store_id if stats else "unknown"
        subject_date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        subject = f"[URGENT] {store_id} {issue_type} - {subject_date}"

        html_content = (
            "<div>"
            f"<div>{details}</div>"
            "</div>"
        )

        try:
            await asyncio.to_thread(
                self.notifier.send_custom_report,
                html_content,
                subject,
                subject_date,
            )
        except Exception as exc:
            self.logger.exception("Failed to send alert email: %s", exc)

    #########################################################
    # Internal
    #########################################################
    @staticmethod
    def _build_details(
        stats: RunStats,
        issue_type: str,
        failed_urls: List[str],
        error_snippet: str,
        artifact_context: str,
    ) -> str:
        rows = [
            ("Issue", issue_type),
            ("Store", stats.store_id),
            ("Start Time", stats.start_time.isoformat()),
            ("Discovered", str(stats.discovered_count)),
            ("Parsed", str(stats.parsed_count)),
            ("Skipped", str(stats.skipped_count)),
            ("Errors", str(stats.error_count)),
            ("Confirmed Deals", str(stats.confirmed_deals_count)),
        ]

        table_rows = "".join(
            f"<tr><td>{html.escape(label)}</td><td>{html.escape(value)}</td></tr>"
            for label, value in rows
        )

        failed_section = ""
        if failed_urls:
            items = "".join(
                f"<div>{html.escape(url)}</div>" for url in failed_urls[:10]
            )
            failed_section = f"<div>Failed URLs:</div><div>{items}</div>"

        snippet_section = ""
        if error_snippet:
            snippet_section = (
                f"<div>Error Snippet:</div><div>{html.escape(error_snippet)}</div>"
            )

        artifact_section = artifact_context or ""

        return (
            "<div>"
            "<table>"
            f"{table_rows}"
            "</table>"
            f"{failed_section}"
            f"{snippet_section}"
            f"{artifact_section}"
            "</div>"
        )

    #########################################################
    # Artifact Context
    #########################################################
    def _build_artifact_context(self, run_dir: Path | None) -> str:
        if run_dir is None:
            return ""

        failures = self._load_index_entries(run_dir / _FAILURE_INDEX_NAME)
        blocked = self._load_index_entries(run_dir / _BLOCKED_INDEX_NAME)

        if not failures and not blocked:
            return ""

        failure_rows = "".join(
            f"<div>{html.escape(str(item.get('url', '')))}</div>"
            for item in failures[:_ARTIFACT_SNIPPET_LIMIT]
        )
        blocked_rows = "".join(
            (
                f"<div>{html.escape(str(item.get('keyword', '')))} "
                f"{html.escape(str(item.get('url', '')))}</div>"
            )
            for item in blocked[:_ARTIFACT_SNIPPET_LIMIT]
        )

        failure_section = (
            f"<div>Failure Artifacts ({len(failures)}):</div>{failure_rows}"
            if failures
            else ""
        )
        blocked_section = (
            f"<div>Blocked Artifacts ({len(blocked)}):</div>{blocked_rows}"
            if blocked
            else ""
        )

        audit_section = self._build_audit_section(run_dir)

        return (
            "<div>"
            f"{failure_section}"
            f"{blocked_section}"
            f"{audit_section}"
            "</div>"
        )

    def _build_audit_section(self, run_dir: Path) -> str:
        reports_dir = run_dir.parent / _REPORTS_DIR_NAME
        if not reports_dir.exists():
            return ""

        audit_reports = sorted(
            reports_dir.glob(f"{_AUDIT_REPORT_PREFIX}*.html"),
            reverse=True,
        )
        if not audit_reports:
            return ""

        latest = audit_reports[0]
        try:
            relative = latest.relative_to(run_dir.parent)
            display = str(relative)
        except ValueError:
            display = str(latest)

        return (
            "<div>Artifact Audit Report:</div>"
            f"<div><a href=\"{html.escape(display)}\">{html.escape(display)}</a></div>"
        )

    def _load_index_entries(self, path: Path) -> list[dict]:
        if not path.exists():
            return []

        entries: list[dict] = []
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        except OSError as exc:
            self.logger.warning("Failed to read artifact index %s: %s", path, exc)

        return entries
