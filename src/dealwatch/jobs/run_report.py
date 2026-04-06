from __future__ import annotations

import argparse
import asyncio
import html
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Final

from dealwatch.infra.config import DEFAULT_REPORTS_DIR, Settings
from dealwatch.legacy.db_repo import DatabaseRepository


#########################################################
# Constants
#########################################################
_DEFAULT_OUTPUT_DIR: Final[Path] = DEFAULT_REPORTS_DIR
_DEFAULT_LOOKBACK_DAYS: Final[int] = 7
_DEFAULT_BASELINE_DAYS: Final[int] = 7
_DEFAULT_LIMIT: Final[int] = 200
_DEFAULT_PARSE_DROP: Final[float] = 0.15
_DEFAULT_ERROR_RISE: Final[float] = 0.10
_DEFAULT_DEAL_DROP: Final[float] = 0.05


#########################################################
# Run Report
#########################################################
@dataclass(slots=True)
class RunReportJob:
    repo: DatabaseRepository
    output_dir: Path = _DEFAULT_OUTPUT_DIR
    lookback_days: int = _DEFAULT_LOOKBACK_DAYS
    baseline_days: int = _DEFAULT_BASELINE_DAYS
    limit: int = _DEFAULT_LIMIT
    parse_drop_threshold: float = _DEFAULT_PARSE_DROP
    error_rise_threshold: float = _DEFAULT_ERROR_RISE
    deal_drop_threshold: float = _DEFAULT_DEAL_DROP
    logger: logging.Logger = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.output_dir, Path):
            self.output_dir = Path(self.output_dir)
        self.logger = logging.getLogger(__name__)

    async def run(self) -> Path | None:
        try:
            await self.repo.initialize()
        except Exception as exc:
            self.logger.exception("Failed to initialize database: %s", exc)
            return None

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=self.lookback_days)
        baseline_start = cutoff - timedelta(days=self.baseline_days)
        runs = await self.repo.get_recent_runs(limit=self.limit)
        recent = self._filter_runs(runs, cutoff, now)
        baseline = self._filter_runs(runs, baseline_start, cutoff)

        if not recent:
            self.logger.info("No recent runs to report.")
            return None

        report = self._build_report(recent, baseline, cutoff, baseline_start, now)
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.logger.exception("Failed to create report output dir: %s", exc)
            return None

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        json_path = self.output_dir / f"run_report_{stamp}.json"
        html_path = self.output_dir / f"run_report_{stamp}.html"

        try:
            json_path.write_text(
                json.dumps(report, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            self.logger.exception("Failed to write run report json: %s", exc)
            return None

        try:
            html_path.write_text(self._render_html(report), encoding="utf-8")
        except OSError as exc:
            self.logger.exception("Failed to write run report html: %s", exc)
            return None

        return html_path

    #########################################################
    # Internal
    #########################################################
    def _build_report(
        self,
        recent_runs,
        baseline_runs,
        cutoff_recent: datetime,
        cutoff_baseline: datetime,
        now: datetime,
    ) -> dict:
        recent_totals, recent_stores = self._aggregate_runs(recent_runs)
        baseline_totals, baseline_stores = self._aggregate_runs(baseline_runs)

        baseline_map = {item["store_id"]: item for item in baseline_stores}
        alerts: list[dict] = []

        for store in recent_stores:
            baseline = baseline_map.get(store["store_id"])
            if baseline is None:
                store["parse_rate_delta"] = None
                store["error_rate_delta"] = None
                store["deal_rate_delta"] = None
                continue

            store["parse_rate_delta"] = round(
                store["parse_rate"] - baseline["parse_rate"], 4
            )
            store["error_rate_delta"] = round(
                store["error_rate"] - baseline["error_rate"], 4
            )
            store["deal_rate_delta"] = round(
                store["deal_rate"] - baseline["deal_rate"], 4
            )

            if store["parse_rate_delta"] <= -self.parse_drop_threshold:
                alerts.append(
                    {
                        "store_id": store["store_id"],
                        "type": "parse_rate_drop",
                        "value": store["parse_rate_delta"],
                    }
                )
            if store["error_rate_delta"] >= self.error_rise_threshold:
                alerts.append(
                    {
                        "store_id": store["store_id"],
                        "type": "error_rate_rise",
                        "value": store["error_rate_delta"],
                    }
                )
            if store["deal_rate_delta"] <= -self.deal_drop_threshold:
                alerts.append(
                    {
                        "store_id": store["store_id"],
                        "type": "deal_rate_drop",
                        "value": store["deal_rate_delta"],
                    }
                )

        recent_stores.sort(key=lambda item: item["error_rate"], reverse=True)
        alerts.sort(key=lambda item: abs(float(item["value"])), reverse=True)

        return {
            "generated_at": now.isoformat(),
            "lookback_days": self.lookback_days,
            "baseline_days": self.baseline_days,
            "cutoff_recent": cutoff_recent.isoformat(),
            "cutoff_baseline": cutoff_baseline.isoformat(),
            "recent": recent_totals,
            "baseline": baseline_totals,
            "stores": recent_stores,
            "alerts": alerts,
            "thresholds": {
                "parse_drop": self.parse_drop_threshold,
                "error_rise": self.error_rise_threshold,
                "deal_drop": self.deal_drop_threshold,
            },
        }

    def _aggregate_runs(self, runs: list) -> tuple[dict, list[dict]]:
        totals = {
            "runs": 0,
            "discovered": 0,
            "parsed": 0,
            "errors": 0,
            "confirmed": 0,
            "skipped": 0,
        }
        per_store: dict[str, dict] = {}

        for run in runs:
            totals["runs"] += 1
            totals["discovered"] += run.discovered_count
            totals["parsed"] += run.parsed_count
            totals["errors"] += run.error_count
            totals["confirmed"] += run.confirmed_deals_count
            totals["skipped"] += run.skipped_count

            store = per_store.setdefault(
                run.store_id,
                {
                    "store_id": run.store_id,
                    "runs": 0,
                    "discovered": 0,
                    "parsed": 0,
                    "errors": 0,
                    "confirmed": 0,
                    "skipped": 0,
                },
            )
            store["runs"] += 1
            store["discovered"] += run.discovered_count
            store["parsed"] += run.parsed_count
            store["errors"] += run.error_count
            store["confirmed"] += run.confirmed_deals_count
            store["skipped"] += run.skipped_count

        overall_rates = self._compute_rates(totals)
        totals.update(overall_rates)

        store_rows = []
        for store in per_store.values():
            store_rates = self._compute_rates(store)
            store_rows.append({**store, **store_rates})

        return totals, store_rows

    @staticmethod
    def _compute_rates(row: dict) -> dict:
        discovered = max(int(row.get("discovered", 0)), 0)
        parsed = max(int(row.get("parsed", 0)), 0)
        errors = max(int(row.get("errors", 0)), 0)
        confirmed = max(int(row.get("confirmed", 0)), 0)
        skipped = max(int(row.get("skipped", 0)), 0)

        effective_total = max(discovered - skipped, 0)
        parse_rate = parsed / effective_total if effective_total > 0 else 0.0
        error_rate = errors / discovered if discovered > 0 else 0.0
        deal_rate = confirmed / discovered if discovered > 0 else 0.0

        return {
            "parse_rate": round(parse_rate, 4),
            "error_rate": round(error_rate, 4),
            "deal_rate": round(deal_rate, 4),
        }

    def _render_html(self, report: dict) -> str:
        recent = report.get("recent", {})
        baseline = report.get("baseline", {})
        alerts = report.get("alerts", [])
        rows = "\n".join(
            (
                "<tr>"
                f"<td>{html.escape(item.get('store_id', ''))}</td>"
                f"<td>{item.get('runs', 0)}</td>"
                f"<td>{item.get('discovered', 0)}</td>"
                f"<td>{item.get('parsed', 0)}</td>"
                f"<td>{item.get('errors', 0)}</td>"
                f"<td>{item.get('confirmed', 0)}</td>"
                f"<td>{item.get('parse_rate', 0.0)}</td>"
                f"<td>{item.get('error_rate', 0.0)}</td>"
                f"<td>{item.get('deal_rate', 0.0)}</td>"
                f"<td>{item.get('parse_rate_delta')}</td>"
                f"<td>{item.get('error_rate_delta')}</td>"
                f"<td>{item.get('deal_rate_delta')}</td>"
                "</tr>"
            )
            for item in report.get("stores", [])
        )

        alert_rows = "\n".join(
            (
                "<tr>"
                f"<td>{html.escape(item.get('store_id', ''))}</td>"
                f"<td>{html.escape(item.get('type', ''))}</td>"
                f"<td>{item.get('value', '')}</td>"
                "</tr>"
            )
            for item in alerts
        )

        return (
            "<html><head><meta charset=\"utf-8\"/>"
            "<style>"
            "body{font-family:Arial,Helvetica,sans-serif;margin:20px;color:#222;}"
            "table{border-collapse:collapse;width:100%;}"
            "th,td{border:1px solid #ddd;padding:8px;text-align:left;font-size:14px;}"
            "th{background:#f2f2f2;}"
            "</style></head><body>"
            "<h1>DealWatch Run Report</h1>"
            f"<p>Recent Runs: {recent.get('runs', 0)}</p>"
            f"<p>Recent Parse Rate: {recent.get('parse_rate', 0.0)}</p>"
            f"<p>Recent Error Rate: {recent.get('error_rate', 0.0)}</p>"
            f"<p>Recent Deal Rate: {recent.get('deal_rate', 0.0)}</p>"
            f"<p>Baseline Runs: {baseline.get('runs', 0)}</p>"
            f"<p>Baseline Parse Rate: {baseline.get('parse_rate', 0.0)}</p>"
            f"<p>Baseline Error Rate: {baseline.get('error_rate', 0.0)}</p>"
            f"<p>Baseline Deal Rate: {baseline.get('deal_rate', 0.0)}</p>"
            "<table>"
            "<tr><th>Store</th><th>Runs</th><th>Discovered</th><th>Parsed</th>"
            "<th>Errors</th><th>Confirmed</th><th>Parse Rate</th>"
            "<th>Error Rate</th><th>Deal Rate</th><th>Parse Δ</th>"
            "<th>Error Δ</th><th>Deal Δ</th></tr>"
            f"{rows}"
            "</table>"
            "<h2>Alerts</h2>"
            "<table>"
            "<tr><th>Store</th><th>Type</th><th>Value</th></tr>"
            f"{alert_rows}"
            "</table>"
            "</body></html>"
        )

    @staticmethod
    def _filter_runs(runs, start: datetime, end: datetime) -> list:
        return [
            run
            for run in runs
            if run.start_time >= start and run.start_time < end
        ]


#########################################################
# CLI
#########################################################
def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate run metrics report.")
    parser.add_argument("--days", type=int, default=_DEFAULT_LOOKBACK_DAYS, help="Lookback days.")
    parser.add_argument("--baseline-days", type=int, default=_DEFAULT_BASELINE_DAYS, help="Baseline window days.")
    parser.add_argument("--limit", type=int, default=_DEFAULT_LIMIT, help="Max rows to load.")
    parser.add_argument("--output-dir", default="", help="Report output directory.")
    parser.add_argument("--parse-drop", type=float, default=_DEFAULT_PARSE_DROP, help="Parse rate drop threshold.")
    parser.add_argument("--error-rise", type=float, default=_DEFAULT_ERROR_RISE, help="Error rate rise threshold.")
    parser.add_argument("--deal-drop", type=float, default=_DEFAULT_DEAL_DROP, help="Deal rate drop threshold.")
    parser.add_argument("--db", default="", help="Override DB path.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    settings = Settings()
    if args.db:
        settings.DB_PATH = Path(args.db)

    output_dir = Path(args.output_dir) if args.output_dir else _DEFAULT_OUTPUT_DIR
    repo = DatabaseRepository(settings.DB_PATH)
    job = RunReportJob(
        repo=repo,
        output_dir=output_dir,
        lookback_days=max(args.days, 1),
        baseline_days=max(args.baseline_days, 1),
        limit=max(args.limit, 1),
        parse_drop_threshold=max(args.parse_drop, 0.0),
        error_rise_threshold=max(args.error_rise, 0.0),
        deal_drop_threshold=max(args.deal_drop, 0.0),
    )
    raise SystemExit(asyncio.run(job.run()) is None)


if __name__ == "__main__":
    main()
