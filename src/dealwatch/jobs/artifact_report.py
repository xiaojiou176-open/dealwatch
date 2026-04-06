from __future__ import annotations

import argparse
import html
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Final

from dealwatch.infra.config import DEFAULT_REPORTS_DIR, DEFAULT_RUNS_DIR

#########################################################
# Constants
#########################################################
_RUNS_DIR: Final[Path] = DEFAULT_RUNS_DIR
_REPORT_DIR: Final[Path] = DEFAULT_REPORTS_DIR
_FAILURE_INDEX: Final[str] = "failures_index.ndjson"
_BLOCKED_INDEX: Final[str] = "blocked_index.ndjson"
_DATE_FORMAT: Final[str] = "%Y-%m-%d"
_DEFAULT_LOOKBACK_DAYS: Final[int] = 7
_DEFAULT_TOP_K: Final[int] = 5


#########################################################
# Artifact Report
#########################################################
@dataclass(slots=True)
class ArtifactReportJob:
    runs_dir: Path = _RUNS_DIR
    output_dir: Path = _REPORT_DIR
    lookback_days: int = _DEFAULT_LOOKBACK_DAYS
    top_k: int = _DEFAULT_TOP_K
    logger: logging.Logger = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.runs_dir, Path):
            self.runs_dir = Path(self.runs_dir)
        if not isinstance(self.output_dir, Path):
            self.output_dir = Path(self.output_dir)
        self.logger = logging.getLogger(__name__)

    def run(self) -> Path | None:
        if not self.runs_dir.exists():
            self.logger.info("Runs directory not found: %s", self.runs_dir)
            return None

        cutoff = datetime.now(timezone.utc) - timedelta(days=self.lookback_days)
        report = self._build_report(cutoff)
        if report is None:
            self.logger.info("No artifact data to report.")
            return None

        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.logger.exception("Failed to create report output dir: %s", exc)
            return None

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        json_path = self.output_dir / f"artifact_report_{stamp}.json"
        html_path = self.output_dir / f"artifact_report_{stamp}.html"

        try:
            json_path.write_text(
                json.dumps(report, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            self.logger.exception("Failed to write artifact report json: %s", exc)
            return None

        try:
            html_path.write_text(self._render_html(report), encoding="utf-8")
        except OSError as exc:
            self.logger.exception("Failed to write artifact report html: %s", exc)
            return None

        return html_path

    #########################################################
    # Internal
    #########################################################
    def _build_report(self, cutoff: datetime) -> dict | None:
        total_failures = 0
        total_blocked = 0
        per_store: dict[str, int] = {}
        per_reason: dict[str, int] = {}
        per_keyword: dict[str, int] = {}
        failure_urls: dict[str, int] = {}
        blocked_urls: dict[str, int] = {}
        per_day: list[dict] = []

        scanned = 0
        for path in sorted(self.runs_dir.iterdir()):
            if not path.is_dir():
                continue
            run_date = self._parse_run_date(path.name)
            if run_date is None:
                continue
            if run_date < cutoff.date():
                continue

            scanned += 1
            failures = self._load_index(path / _FAILURE_INDEX)
            blocked = self._load_index(path / _BLOCKED_INDEX)

            day_failures = len(failures)
            day_blocked = len(blocked)
            total_failures += day_failures
            total_blocked += day_blocked

            for entry in failures:
                store_id = str(entry.get("store_id") or "unknown")
                reason = str(entry.get("reason") or "unknown")
                url = str(entry.get("url") or "")
                per_store[store_id] = per_store.get(store_id, 0) + 1
                per_reason[reason] = per_reason.get(reason, 0) + 1
                if url:
                    failure_urls[url] = failure_urls.get(url, 0) + 1

            for entry in blocked:
                keyword = str(entry.get("keyword") or "unknown")
                url = str(entry.get("url") or "")
                per_keyword[keyword] = per_keyword.get(keyword, 0) + 1
                if url:
                    blocked_urls[url] = blocked_urls.get(url, 0) + 1

            per_day.append(
                {
                    "date": run_date.isoformat(),
                    "failures": day_failures,
                    "blocked": day_blocked,
                }
            )

        if scanned == 0 and total_failures == 0 and total_blocked == 0:
            return None

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "lookback_days": self.lookback_days,
            "runs_scanned": scanned,
            "totals": {
                "failures": total_failures,
                "blocked": total_blocked,
            },
            "per_day": per_day,
            "top_stores": self._top_items(per_store),
            "top_reasons": self._top_items(per_reason),
            "top_keywords": self._top_items(per_keyword),
            "top_failure_urls": self._top_items(failure_urls),
            "top_blocked_urls": self._top_items(blocked_urls),
        }

    @staticmethod
    def _parse_run_date(name: str) -> datetime.date | None:
        try:
            return datetime.strptime(name, _DATE_FORMAT).date()
        except ValueError:
            return None

    def _load_index(self, path: Path) -> list[dict]:
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
            self.logger.warning("Failed to read index %s: %s", path, exc)

        return entries

    def _top_items(self, counts: dict[str, int]) -> list[dict]:
        top = sorted(
            [{"key": key, "count": count} for key, count in counts.items()],
            key=lambda item: item["count"],
            reverse=True,
        )
        return top[: max(self.top_k, 1)]

    def _render_html(self, report: dict) -> str:
        totals = report.get("totals", {})
        per_day = report.get("per_day", [])

        day_rows = "\n".join(
            (
                "<tr>"
                f"<td>{html.escape(item.get('date', ''))}</td>"
                f"<td>{item.get('failures', 0)}</td>"
                f"<td>{item.get('blocked', 0)}</td>"
                "</tr>"
            )
            for item in per_day
        )

        def _render_list(items):
            return "\n".join(
                (
                    "<tr>"
                    f"<td>{html.escape(item.get('key', ''))}</td>"
                    f"<td>{item.get('count', 0)}</td>"
                    "</tr>"
                )
                for item in items
            )

        return (
            "<html><head><meta charset=\"utf-8\"/>"
            "<style>"
            "body{font-family:Arial,Helvetica,sans-serif;margin:20px;color:#222;}"
            "table{border-collapse:collapse;width:100%;}"
            "th,td{border:1px solid #ddd;padding:8px;text-align:left;font-size:14px;}"
            "th{background:#f2f2f2;}"
            "</style></head><body>"
            "<h1>Artifact Report</h1>"
            f"<p>Total Failures: {totals.get('failures', 0)}</p>"
            f"<p>Total Blocked: {totals.get('blocked', 0)}</p>"
            "<h2>Per Day</h2>"
            "<table>"
            "<tr><th>Date</th><th>Failures</th><th>Blocked</th></tr>"
            f"{day_rows}"
            "</table>"
            "<h2>Top Stores</h2>"
            "<table>"
            "<tr><th>Store</th><th>Count</th></tr>"
            f"{_render_list(report.get('top_stores', []))}"
            "</table>"
            "<h2>Top Reasons</h2>"
            "<table>"
            "<tr><th>Reason</th><th>Count</th></tr>"
            f"{_render_list(report.get('top_reasons', []))}"
            "</table>"
            "<h2>Top Blocked Keywords</h2>"
            "<table>"
            "<tr><th>Keyword</th><th>Count</th></tr>"
            f"{_render_list(report.get('top_keywords', []))}"
            "</table>"
            "<h2>Top Failure URLs</h2>"
            "<table>"
            "<tr><th>URL</th><th>Count</th></tr>"
            f"{_render_list(report.get('top_failure_urls', []))}"
            "</table>"
            "<h2>Top Blocked URLs</h2>"
            "<table>"
            "<tr><th>URL</th><th>Count</th></tr>"
            f"{_render_list(report.get('top_blocked_urls', []))}"
            "</table>"
            "</body></html>"
        )


#########################################################
# CLI
#########################################################
def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate artifact summary report.")
    parser.add_argument("--days", type=int, default=_DEFAULT_LOOKBACK_DAYS, help="Lookback days.")
    parser.add_argument("--top", type=int, default=_DEFAULT_TOP_K, help="Top K list size.")
    parser.add_argument("--runs-dir", default="", help="Runs directory path.")
    parser.add_argument("--output-dir", default="", help="Report output directory.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    runs_dir = Path(args.runs_dir) if args.runs_dir else _RUNS_DIR
    output_dir = Path(args.output_dir) if args.output_dir else _REPORT_DIR
    job = ArtifactReportJob(
        runs_dir=runs_dir,
        output_dir=output_dir,
        lookback_days=max(args.days, 1),
        top_k=max(args.top, 1),
    )
    raise SystemExit(job.run() is None)


if __name__ == "__main__":
    main()
