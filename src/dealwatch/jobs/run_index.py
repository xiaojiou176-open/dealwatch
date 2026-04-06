from __future__ import annotations

import argparse
import html
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Final

from dealwatch.infra.config import DEFAULT_RUNS_DIR

#########################################################
# Constants
#########################################################
_RUNS_DIR: Final[Path] = DEFAULT_RUNS_DIR
_DATE_FORMAT: Final[str] = "%Y-%m-%d"
_DEFAULT_LOOKBACK_DAYS: Final[int] = 14
_INDEX_JSON: Final[str] = "runs_index.json"
_INDEX_HTML: Final[str] = "index.html"
_FAILURE_INDEX: Final[str] = "failures_index.ndjson"
_BLOCKED_INDEX: Final[str] = "blocked_index.ndjson"
_REPORT_DIR: Final[str] = "reports"


#########################################################
# Run Index Job
#########################################################
@dataclass(slots=True)
class RunIndexJob:
    runs_dir: Path = _RUNS_DIR
    lookback_days: int = _DEFAULT_LOOKBACK_DAYS
    logger: logging.Logger = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.runs_dir, Path):
            self.runs_dir = Path(self.runs_dir)
        self.logger = logging.getLogger(__name__)

    def run(self) -> Path | None:
        if not self.runs_dir.exists():
            self.logger.info("Runs directory not found: %s", self.runs_dir)
            return None

        cutoff = datetime.now(timezone.utc).date() - timedelta(days=self.lookback_days)
        index = self._build_index(cutoff)
        if index is None:
            self.logger.info("No run data to index.")
            return None

        json_path = self.runs_dir / _INDEX_JSON
        html_path = self.runs_dir / _INDEX_HTML

        try:
            json_path.write_text(
                json.dumps(index, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            self.logger.exception("Failed to write runs index json: %s", exc)
            return None

        try:
            html_path.write_text(self._render_html(index), encoding="utf-8")
        except OSError as exc:
            self.logger.exception("Failed to write runs index html: %s", exc)
            return None

        return html_path

    #########################################################
    # Internal
    #########################################################
    def _build_index(self, cutoff_date: datetime.date) -> dict | None:
        rows: list[dict] = []
        total_failures = 0
        total_blocked = 0
        total_confirmed = 0
        total_checked = 0
        reports = self._load_reports()

        for path in sorted(self.runs_dir.iterdir(), reverse=True):
            if not path.is_dir():
                continue
            run_date = self._parse_run_date(path.name)
            if run_date is None:
                continue
            if run_date < cutoff_date:
                continue

            deal_summary = self._load_deal_summary(path)
            failures = self._count_index(path / _FAILURE_INDEX)
            blocked = self._count_index(path / _BLOCKED_INDEX)

            total_failures += failures
            total_blocked += blocked
            total_confirmed += deal_summary["confirmed"]
            total_checked += deal_summary["checked"]

            rows.append(
                {
                    "date": run_date.isoformat(),
                    "confirmed": deal_summary["confirmed"],
                    "checked": deal_summary["checked"],
                    "failures": failures,
                    "blocked": blocked,
                    "stores": deal_summary["stores"],
                    "dashboard": f"{path.name}/index.html",
                }
            )

        if not rows:
            return None

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "lookback_days": self.lookback_days,
            "totals": {
                "confirmed": total_confirmed,
                "checked": total_checked,
                "failures": total_failures,
                "blocked": total_blocked,
            },
            "reports": reports,
            "runs": rows,
        }

    @staticmethod
    def _parse_run_date(name: str) -> datetime.date | None:
        try:
            return datetime.strptime(name, _DATE_FORMAT).date()
        except ValueError:
            return None

    def _load_deal_summary(self, run_dir: Path) -> dict:
        confirmed_total = 0
        checked_total = 0
        per_store: list[dict] = []

        for json_path in run_dir.glob("*_confirmed.json"):
            try:
                payload = json.loads(json_path.read_text(encoding="utf-8"))
            except Exception as exc:
                self.logger.warning("Failed to read %s: %s", json_path, exc)
                continue

            store_id = json_path.stem.replace("_confirmed", "")
            confirmed = int(payload.get("confirmed_count", 0))
            checked = int(payload.get("total_checked", 0))
            confirmed_total += confirmed
            checked_total += checked
            per_store.append(
                {
                    "store_id": store_id,
                    "confirmed": confirmed,
                    "checked": checked,
                }
            )

        per_store = sorted(per_store, key=lambda item: item["store_id"])
        return {
            "confirmed": confirmed_total,
            "checked": checked_total,
            "stores": per_store,
        }

    def _count_index(self, path: Path) -> int:
        if not path.exists():
            return 0

        count = 0
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    json.loads(line)
                except json.JSONDecodeError:
                    continue
                count += 1
        except OSError as exc:
            self.logger.warning("Failed to read index %s: %s", path, exc)
        return count

    def _load_reports(self) -> dict:
        reports_dir = self.runs_dir / _REPORT_DIR
        replay_reports = self._load_replay_reports()
        if not reports_dir.exists() and not replay_reports:
            return {}

        run_reports = sorted(reports_dir.glob("run_report_*.html"), reverse=True) if reports_dir.exists() else []
        artifact_reports = (
            sorted(reports_dir.glob("artifact_report_*.html"), reverse=True)
            if reports_dir.exists()
            else []
        )
        audit_reports = (
            sorted(reports_dir.glob("artifact_audit_*.html"), reverse=True)
            if reports_dir.exists()
            else []
        )

        return {
            "run_reports": [self._safe_rel_path(path) for path in run_reports[:5]],
            "artifact_reports": [self._safe_rel_path(path) for path in artifact_reports[:5]],
            "audit_reports": [self._safe_rel_path(path) for path in audit_reports[:5]],
            "replay_reports": [self._safe_rel_path(path) for path in replay_reports[:5]],
        }

    def _load_replay_reports(self) -> list[Path]:
        replay_reports: list[Path] = []
        if not self.runs_dir.exists():
            return replay_reports
        for run_dir in sorted(self.runs_dir.iterdir(), reverse=True):
            if not run_dir.is_dir():
                continue
            candidate = run_dir / "replays" / "replay_report.html"
            if candidate.exists():
                replay_reports.append(candidate)
        return replay_reports

    def _safe_rel_path(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.runs_dir))
        except ValueError:
            return str(path)

    def _render_html(self, index: dict) -> str:
        totals = index.get("totals", {})
        runs = index.get("runs", [])
        reports = index.get("reports", {})

        report_rows = ""
        if reports:
            report_rows = "\n".join(
                (
                    "<li>"
                    f"<a href=\"{html.escape(path)}\">{html.escape(path)}</a>"
                    "</li>"
                )
                for path in (
                    reports.get("run_reports", [])
                    + reports.get("artifact_reports", [])
                    + reports.get("audit_reports", [])
                    + reports.get("replay_reports", [])
                )
            )

        run_rows = "\n".join(
            (
                "<tr>"
                f"<td>{html.escape(item.get('date', ''))}</td>"
                f"<td>{item.get('confirmed', 0)}</td>"
                f"<td>{item.get('checked', 0)}</td>"
                f"<td>{item.get('failures', 0)}</td>"
                f"<td>{item.get('blocked', 0)}</td>"
                f"<td><a href=\"{html.escape(item.get('dashboard', ''))}\">Dashboard</a></td>"
                f"<td>{self._render_store_cell(item.get('stores', []))}</td>"
                "</tr>"
            )
            for item in runs
        )

        return (
            "<html><head><meta charset=\"utf-8\"/>"
            "<style>"
            "body{font-family:Arial,Helvetica,sans-serif;margin:20px;color:#222;}"
            "table{border-collapse:collapse;width:100%;margin-bottom:24px;}"
            "th,td{border:1px solid #ddd;padding:8px;text-align:left;font-size:14px;}"
            "th{background:#f2f2f2;}"
            "h2{margin-top:24px;}"
            "</style></head><body>"
            "<h1>DealWatch Runs Index</h1>"
            f"<p>Total Confirmed: {totals.get('confirmed', 0)}</p>"
            f"<p>Total Checked: {totals.get('checked', 0)}</p>"
            f"<p>Total Failures: {totals.get('failures', 0)}</p>"
            f"<p>Total Blocked: {totals.get('blocked', 0)}</p>"
            "<h2>Recent Reports</h2>"
            "<ul>"
            f"{report_rows}"
            "</ul>"
            "<h2>Runs</h2>"
            "<table>"
            "<tr><th>Date</th><th>Confirmed</th><th>Checked</th><th>Failures</th>"
            "<th>Blocked</th><th>Dashboard</th><th>Stores</th></tr>"
            f"{run_rows}"
            "</table>"
            "</body></html>"
        )

    @staticmethod
    def _render_store_cell(stores: list[dict]) -> str:
        if not stores:
            return ""
        parts = [
            f"{html.escape(item.get('store_id', ''))}:"
            f"{item.get('confirmed', 0)}/{item.get('checked', 0)}"
            for item in stores
        ]
        return html.escape(" | ".join(parts))


#########################################################
# CLI
#########################################################

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate runs index dashboard.")
    parser.add_argument("--days", type=int, default=_DEFAULT_LOOKBACK_DAYS, help="Lookback days.")
    parser.add_argument("--runs-dir", default="", help="Runs directory path.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    runs_dir = Path(args.runs_dir) if args.runs_dir else _RUNS_DIR
    job = RunIndexJob(
        runs_dir=runs_dir,
        lookback_days=max(args.days, 1),
    )
    raise SystemExit(job.run() is None)


if __name__ == "__main__":
    main()
