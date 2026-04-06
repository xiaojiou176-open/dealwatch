from __future__ import annotations

import argparse
import asyncio
import difflib
import html
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable, Final
from urllib.parse import urlsplit

from dealwatch.infra.config import DEFAULT_RUNS_DIR, Settings
from dealwatch.infra.playwright_client import PlaywrightClient
from dealwatch.infra.retry_budget import RetryBudget
from dealwatch.stores.base_adapter import BaseStoreAdapter


#########################################################
# Constants
#########################################################
_RUNS_DIR: Final[Path] = DEFAULT_RUNS_DIR
_FAILURE_INDEX: Final[str] = "failures_index.ndjson"
_REPLAY_DIR: Final[str] = "replays"
_DEFAULT_CONCURRENCY: Final[int] = 4
_DEFAULT_RETRY_BUDGET: Final[int] = 20
_DEFAULT_MAX_RETRIES: Final[int] = 2
_DEFAULT_REPORT_NAME: Final[str] = "replay_report.html"
_DEFAULT_REPORT_JSON: Final[str] = "replay_report.json"
_RETRY_BASE_DELAY: Final[float] = 0.2


#########################################################
# Failure Replay
#########################################################
@dataclass(slots=True)
class FailureReplayJob:
    runs_dir: Path = _RUNS_DIR
    headless: bool = True
    proxy_server: str | None = None
    storage_state_path: Path | None = None
    max_entries: int = 50
    diff_context_lines: int = 3
    concurrency: int = _DEFAULT_CONCURRENCY
    retry_budget: int | RetryBudget | None = _DEFAULT_RETRY_BUDGET
    max_retries: int = _DEFAULT_MAX_RETRIES
    build_report: bool = True
    fetcher: Callable[[str], Awaitable[str]] | None = None
    logger: logging.Logger = field(init=False, repr=False)
    _retry_budget: RetryBudget | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        if not isinstance(self.runs_dir, Path):
            self.runs_dir = Path(self.runs_dir)
        self.logger = logging.getLogger(__name__)
        if isinstance(self.retry_budget, RetryBudget):
            self._retry_budget = self.retry_budget
        elif self.retry_budget is None or int(self.retry_budget) <= 0:
            self._retry_budget = None
        else:
            self._retry_budget = RetryBudget(int(self.retry_budget))

    async def run(self, run_date: str | None = None) -> Path | None:
        run_dir = self._resolve_run_dir(run_date)
        if run_dir is None:
            self.logger.error("No run directory found.")
            return None

        index_path = run_dir / _FAILURE_INDEX
        if not index_path.exists():
            self.logger.warning("Failure index not found: %s", index_path)
            return None

        entries = self._load_failure_index(index_path)
        if not entries:
            self.logger.info("No failure entries to replay.")
            return None

        output_dir = run_dir / _REPLAY_DIR
        output_dir.mkdir(parents=True, exist_ok=True)
        index_md = output_dir / "replay_index.md"
        index_json = output_dir / "replay_index.ndjson"

        settings = Settings()
        storage_state = self.storage_state_path or BaseStoreAdapter._build_storage_state_path(
            settings.ZIP_CODE,
            settings.STORAGE_STATE_DIR,
        )

        if self.fetcher is not None:
            results = await self._replay_entries(
                entries,
                run_dir,
                output_dir,
                fetcher=self.fetcher,
            )
            self._write_indices(results, index_md, index_json)
            if self.build_report:
                self._write_report(output_dir, results)
            return output_dir

        async with PlaywrightClient(
            headless=self.headless,
            storage_state_path=storage_state,
            proxy_server=self.proxy_server,
            retry_budget=settings.PLAYWRIGHT_RETRY_BUDGET or None,
            runs_dir=self.runs_dir,
        ) as client:
            results = await self._replay_entries(
                entries,
                run_dir,
                output_dir,
                fetcher=lambda url: client.fetch_page(url, return_page=False),
            )
            self._write_indices(results, index_md, index_json)
            if self.build_report:
                self._write_report(output_dir, results)

        return output_dir

    #########################################################
    # Internal
    #########################################################
    def _resolve_run_dir(self, run_date: str | None) -> Path | None:
        if run_date:
            candidate = self.runs_dir / run_date
            if candidate.exists():
                return candidate
            self.logger.error("Run directory does not exist: %s", candidate)
            return None

        if not self.runs_dir.exists():
            return None

        candidates = sorted(
            [path for path in self.runs_dir.iterdir() if path.is_dir()],
            key=lambda path: path.name,
            reverse=True,
        )
        return candidates[0] if candidates else None

    def _load_failure_index(self, path: Path) -> list[dict]:
        entries: list[dict] = []
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    self.logger.warning("Invalid failure index line: %s", exc)
        except OSError as exc:
            self.logger.warning("Failed to read failure index: %s", exc)
        return entries

    async def _replay_entries(
        self,
        entries: list[dict],
        run_dir: Path,
        output_dir: Path,
        fetcher: Callable[[str], Awaitable[str]],
    ) -> list[dict]:
        results: list[dict] = []
        semaphore = asyncio.Semaphore(max(1, self.concurrency))

        async def _run_entry(entry: dict) -> dict | None:
            async with semaphore:
                return await self._replay_single(entry, run_dir, output_dir, fetcher)

        tasks: list[asyncio.Task] = []
        count = 0
        for entry in entries:
            if count >= self.max_entries:
                break
            url = str(entry.get("url") or "").strip()
            if not url:
                continue
            count += 1
            tasks.append(asyncio.create_task(_run_entry(entry)))

        if not tasks:
            return results

        finished = await asyncio.gather(*tasks)
        for item in finished:
            if item is not None:
                results.append(item)

        return results

    async def _replay_single(
        self,
        entry: dict,
        run_dir: Path,
        output_dir: Path,
        fetcher: Callable[[str], Awaitable[str]],
    ) -> dict | None:
        url = str(entry.get("url") or "").strip()
        if not url:
            return None

        archive_path = entry.get("html_path", "")
        archived_html = ""
        full_archive_path = self._resolve_archive_path(run_dir, archive_path)
        if full_archive_path is not None and full_archive_path.exists():
            try:
                archived_html = full_archive_path.read_text(encoding="utf-8")
            except OSError as exc:
                self.logger.warning("Failed to read archived html: %s", exc)

        try:
            current_html = await self._fetch_with_retry(url, fetcher)
        except RuntimeError as exc:
            if "Retry budget exhausted" in str(exc):
                return {
                    "url": url,
                    "status": "budget_exhausted",
                    "error": str(exc),
                    "captured_at": self._now_stamp(),
                    "archive_html": archive_path or "",
                }
            raise
        except Exception as exc:
            self.logger.warning("Replay fetch failed: %s", exc)
            return {
                "url": url,
                "status": "fetch_failed",
                "error": str(exc),
                "captured_at": self._now_stamp(),
                "archive_html": archive_path or "",
            }

        current_html = str(current_html)
        diff_text = self._build_diff(archived_html, current_html)
        diff_lines = len(diff_text.splitlines()) if diff_text else 0
        diff_excerpt = self._build_diff_excerpt(diff_text)
        stamp = self._now_stamp()
        url_hash = hashlib.md5(url.encode("utf-8")).hexdigest()[:8]
        current_path = output_dir / f"current_{stamp}_{url_hash}.html"
        diff_path = output_dir / f"diff_{stamp}_{url_hash}.txt"

        try:
            current_path.write_text(current_html, encoding="utf-8")
        except OSError as exc:
            self.logger.warning("Failed to write current html: %s", exc)

        try:
            diff_path.write_text(diff_text, encoding="utf-8")
        except OSError as exc:
            self.logger.warning("Failed to write diff: %s", exc)

        return {
            "url": url,
            "status": "replayed",
            "captured_at": stamp,
            "current_html": current_path.name,
            "diff_path": diff_path.name,
            "archive_html": archive_path or "",
            "diff_lines": diff_lines,
            "diff_excerpt": diff_excerpt,
        }

    def _build_diff(self, old_html: str, new_html: str) -> str:
        old_lines = self._normalize_html(old_html).splitlines()
        new_lines = self._normalize_html(new_html).splitlines()
        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile="archived",
            tofile="current",
            lineterm="",
            n=self.diff_context_lines,
        )
        return "\n".join(diff)

    @staticmethod
    def _build_diff_excerpt(diff_text: str, max_lines: int = 6) -> str:
        if not diff_text:
            return ""
        lines = diff_text.splitlines()
        return "\n".join(lines[: max(max_lines, 1)])

    @staticmethod
    def _normalize_html(text: str) -> str:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines)

    @staticmethod
    def _now_stamp() -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    @staticmethod
    def _format_index_line(entry: dict) -> str:
        return (
            f"- {entry.get('captured_at', '')} "
            f"{entry.get('status', '')} "
            f"[diff]({entry.get('diff_path', '')}) "
            f"[current]({entry.get('current_html', '')}) "
            f"{entry.get('url', '')}\n"
        )

    def _write_indices(self, results: list[dict], index_md: Path, index_json: Path) -> None:
        for result in results:
            try:
                with index_json.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(result, ensure_ascii=False) + "\n")
            except OSError as exc:
                self.logger.warning("Failed to write replay index json: %s", exc)

            try:
                with index_md.open("a", encoding="utf-8") as handle:
                    handle.write(self._format_index_line(result))
            except OSError as exc:
                self.logger.warning("Failed to write replay index md: %s", exc)

    def _write_report(self, output_dir: Path, results: list[dict]) -> Path:
        report_path = output_dir / _DEFAULT_REPORT_NAME
        report_json_path = output_dir / _DEFAULT_REPORT_JSON
        report_data = self._build_report_data(results)
        status_counts = report_data.get("status_counts", {})

        rows = "\n".join(
            (
                "<tr>"
                f"<td>{html.escape(str(item.get('captured_at', '')))}</td>"
                f"<td>{html.escape(str(item.get('status', '')))}</td>"
                f"<td>{html.escape(str(item.get('diff_lines', '')))}</td>"
                f"<td><pre>{html.escape(str(item.get('diff_excerpt', '')))}</pre></td>"
                f"<td><a href=\"{html.escape(str(item.get('diff_path', '')))}\">diff</a></td>"
                f"<td><a href=\"{html.escape(str(item.get('current_html', '')))}\">current</a></td>"
                f"<td><a href=\"{html.escape(str(item.get('archive_html', '')))}\">archive</a></td>"
                f"<td>{html.escape(str(item.get('url', '')))}</td>"
                "</tr>"
            )
            for item in results
        )

        summary = " ".join(
            f"{html.escape(str(status))}={count}" for status, count in status_counts.items()
        )

        domain_rows = "\n".join(
            (
                "<tr>"
                f"<td>{html.escape(str(item.get('domain', '')))}</td>"
                f"<td>{html.escape(str(item.get('count', '')))}</td>"
                "</tr>"
            )
            for item in report_data.get("top_domains", [])
        )

        report_html = (
            "<html><head><meta charset=\"utf-8\"/>"
            "<style>"
            "body{font-family:Arial,Helvetica,sans-serif;margin:20px;color:#222;}"
            "table{border-collapse:collapse;width:100%;}"
            "th,td{border:1px solid #ddd;padding:8px;text-align:left;font-size:14px;}"
            "th{background:#f2f2f2;}"
            "</style></head><body>"
            "<h1>Failure Replay Report</h1>"
            f"<p>Summary: {summary}</p>"
            f"<p>Total Entries: {html.escape(str(report_data.get('total_entries', 0)))}</p>"
            f"<p>Retry Budget Used: {html.escape(str(report_data.get('retry_budget_used', 0)))}</p>"
            "<table>"
            "<tr><th>Time</th><th>Status</th><th>Diff Lines</th><th>Diff Excerpt</th>"
            "<th>Diff</th><th>Current</th><th>Archive</th><th>URL</th></tr>"
            f"{rows}"
            "</table>"
            "<h2>Top Domains</h2>"
            "<table>"
            "<tr><th>Domain</th><th>Count</th></tr>"
            f"{domain_rows}"
            "</table>"
            "</body></html>"
        )

        report_path.write_text(report_html, encoding="utf-8")
        report_json_path.write_text(
            json.dumps(report_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return report_path

    def _build_report_data(self, results: list[dict]) -> dict:
        status_counts: dict[str, int] = {}
        domain_counts: dict[str, int] = {}
        diff_values: list[int] = []

        for item in results:
            status = str(item.get("status") or "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1

            url = str(item.get("url") or "")
            domain = urlsplit(url).netloc
            if domain:
                domain_counts[domain] = domain_counts.get(domain, 0) + 1

            if status == "replayed":
                try:
                    diff_values.append(int(item.get("diff_lines", 0)))
                except (TypeError, ValueError):
                    diff_values.append(0)

        avg_diff = 0.0
        if diff_values:
            avg_diff = round(sum(diff_values) / len(diff_values), 2)

        retry_budget_used = 0
        retry_budget_initial = None
        retry_budget_remaining = None
        if self._retry_budget is not None:
            retry_budget_initial = self._retry_budget.total
            retry_budget_remaining = self._retry_budget.remaining
            retry_budget_used = self._retry_budget.used()

        top_domains = sorted(
            [{"domain": domain, "count": count} for domain, count in domain_counts.items()],
            key=lambda item: item["count"],
            reverse=True,
        )[:5]

        return {
            "generated_at": self._now_stamp(),
            "total_entries": len(results),
            "status_counts": status_counts,
            "top_domains": top_domains,
            "diff_lines": {
                "min": min(diff_values) if diff_values else 0,
                "max": max(diff_values) if diff_values else 0,
                "avg": avg_diff,
            },
            "retry_budget_initial": retry_budget_initial,
            "retry_budget_remaining": retry_budget_remaining,
            "retry_budget_used": retry_budget_used,
        }

    def _consume_retry_budget(self) -> bool:
        if self._retry_budget is None:
            return True
        return self._retry_budget.consume()

    async def _fetch_with_retry(
        self,
        url: str,
        fetcher: Callable[[str], Awaitable[str]],
    ) -> str:
        attempts = 0
        while True:
            try:
                return await fetcher(url)
            except Exception as exc:
                attempts += 1
                if attempts > self.max_retries:
                    raise
                if not self._consume_retry_budget():
                    raise RuntimeError("Retry budget exhausted") from exc
                await asyncio.sleep(_RETRY_BASE_DELAY * attempts)

    @staticmethod
    def _resolve_archive_path(run_dir: Path, archive_path: str | None) -> Path | None:
        if not archive_path:
            return None
        candidate = Path(archive_path)
        if candidate.is_absolute():
            return None
        try:
            resolved_run = run_dir.resolve()
            resolved_path = (run_dir / candidate).resolve()
        except OSError:
            return None
        if not resolved_path.is_relative_to(resolved_run):
            return None
        return resolved_path


#########################################################
# CLI
#########################################################
def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay failed pages.")
    parser.add_argument("--run-date", default="", help="Run date (YYYY-MM-DD).")
    parser.add_argument("--max", type=int, default=50, help="Max replay entries.")
    parser.add_argument("--concurrency", type=int, default=_DEFAULT_CONCURRENCY, help="Replay concurrency.")
    parser.add_argument("--retries", type=int, default=_DEFAULT_MAX_RETRIES, help="Retries per URL.")
    parser.add_argument("--retry-budget", type=int, default=_DEFAULT_RETRY_BUDGET, help="Total retry budget.")
    parser.add_argument("--no-report", action="store_true", help="Skip HTML report.")
    parser.add_argument("--headless", action="store_true", help="Use headless browser.")
    parser.add_argument("--proxy", default="", help="Proxy server.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    job = FailureReplayJob(
        headless=bool(args.headless),
        proxy_server=args.proxy or None,
        max_entries=max(args.max, 1),
        concurrency=max(args.concurrency, 1),
        max_retries=max(args.retries, 0),
        retry_budget=args.retry_budget,
        build_report=not args.no_report,
    )
    run_date = args.run_date.strip() or None
    asyncio.run(job.run(run_date))


if __name__ == "__main__":
    main()
