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
_DEFAULT_LOOKBACK_DAYS: Final[int] = 14
_DEFAULT_SAMPLE_LIMIT: Final[int] = 10

_FAILURE_FIELDS: Final[tuple[str, ...]] = ("html_path", "screenshot_path", "text_path", "meta_path")
_BLOCKED_FIELDS: Final[tuple[str, ...]] = ("content_path", "screenshot_path")


#########################################################
# Artifact Audit
#########################################################
@dataclass(slots=True)
class ArtifactAuditJob:
    runs_dir: Path = _RUNS_DIR
    output_dir: Path = _REPORT_DIR
    lookback_days: int = _DEFAULT_LOOKBACK_DAYS
    sample_limit: int = _DEFAULT_SAMPLE_LIMIT
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

        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=self.lookback_days)).date()
        report = self._build_report(cutoff_date)
        if report is None:
            self.logger.info("No artifact audit data to report.")
            return None

        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.logger.exception("Failed to create report output dir: %s", exc)
            return None

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        json_path = self.output_dir / f"artifact_audit_{stamp}.json"
        html_path = self.output_dir / f"artifact_audit_{stamp}.html"

        try:
            json_path.write_text(
                json.dumps(report, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            self.logger.exception("Failed to write artifact audit json: %s", exc)
            return None

        try:
            html_path.write_text(self._render_html(report), encoding="utf-8")
        except OSError as exc:
            self.logger.exception("Failed to write artifact audit html: %s", exc)
            return None

        return html_path

    #########################################################
    # Internal
    #########################################################
    def _build_report(self, cutoff_date: datetime.date) -> dict | None:
        total_failures = 0
        total_blocked = 0
        missing_counts = {"failure": {key: 0 for key in _FAILURE_FIELDS}, "blocked": {key: 0 for key in _BLOCKED_FIELDS}}
        invalid_lines = {"failure": 0, "blocked": 0}
        per_day: list[dict] = []
        samples: list[dict] = []

        scanned = 0
        for path in sorted(self.runs_dir.iterdir()):
            if not path.is_dir():
                continue
            run_date = self._parse_run_date(path.name)
            if run_date is None:
                continue
            if run_date < cutoff_date:
                continue

            scanned += 1
            failure_stats = self._audit_index(
                run_dir=path,
                index_name=_FAILURE_INDEX,
                required_fields=_FAILURE_FIELDS,
                sample_bucket=samples,
                sample_limit=self.sample_limit,
                kind="failure",
            )
            blocked_stats = self._audit_index(
                run_dir=path,
                index_name=_BLOCKED_INDEX,
                required_fields=_BLOCKED_FIELDS,
                sample_bucket=samples,
                sample_limit=self.sample_limit,
                kind="blocked",
            )

            total_failures += failure_stats["total"]
            total_blocked += blocked_stats["total"]

            for key, value in failure_stats["missing"].items():
                missing_counts["failure"][key] += value
            for key, value in blocked_stats["missing"].items():
                missing_counts["blocked"][key] += value

            invalid_lines["failure"] += failure_stats["invalid_lines"]
            invalid_lines["blocked"] += blocked_stats["invalid_lines"]

            per_day.append(
                {
                    "date": run_date.isoformat(),
                    "failures": failure_stats["total"],
                    "blocked": blocked_stats["total"],
                    "missing_failure": failure_stats["missing"],
                    "missing_blocked": blocked_stats["missing"],
                    "invalid_lines": {
                        "failure": failure_stats["invalid_lines"],
                        "blocked": blocked_stats["invalid_lines"],
                    },
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
                "missing": missing_counts,
                "invalid_lines": invalid_lines,
            },
            "per_day": per_day,
            "samples": samples,
        }

    @staticmethod
    def _parse_run_date(name: str) -> datetime.date | None:
        try:
            return datetime.strptime(name, _DATE_FORMAT).date()
        except ValueError:
            return None

    def _audit_index(
        self,
        run_dir: Path,
        index_name: str,
        required_fields: tuple[str, ...],
        sample_bucket: list[dict],
        sample_limit: int,
        kind: str,
    ) -> dict:
        index_path = run_dir / index_name
        missing = {key: 0 for key in required_fields}
        invalid_lines = 0
        total = 0

        if not index_path.exists():
            return {
                "total": 0,
                "missing": missing,
                "invalid_lines": 0,
            }

        try:
            for line in index_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    invalid_lines += 1
                    continue

                total += 1
                for field_name in required_fields:
                    raw = str(entry.get(field_name, "")).strip()
                    if not raw:
                        missing[field_name] += 1
                        self._append_sample(sample_bucket, sample_limit, kind, run_dir, field_name, entry, "missing_path")
                        continue

                    resolved = self._resolve_entry_path(run_dir, raw)
                    if resolved is None or not resolved.exists():
                        missing[field_name] += 1
                        self._append_sample(sample_bucket, sample_limit, kind, run_dir, field_name, entry, raw)
        except OSError as exc:
            self.logger.warning("Failed to read index %s: %s", index_path, exc)

        return {
            "total": total,
            "missing": missing,
            "invalid_lines": invalid_lines,
        }

    @staticmethod
    def _resolve_entry_path(run_dir: Path, raw: str) -> Path | None:
        if not raw:
            return None
        path = Path(raw)
        if path.is_absolute():
            return path
        return run_dir / path

    @staticmethod
    def _append_sample(
        bucket: list[dict],
        limit: int,
        kind: str,
        run_dir: Path,
        field_name: str,
        entry: dict,
        raw_path: str,
    ) -> None:
        if len(bucket) >= max(limit, 0):
            return
        bucket.append(
            {
                "kind": kind,
                "run_dir": run_dir.name,
                "field": field_name,
                "url": str(entry.get("url", "")),
                "path": raw_path,
            }
        )

    def _render_html(self, report: dict) -> str:
        totals = report.get("totals", {})
        per_day = report.get("per_day", [])
        samples = report.get("samples", [])

        day_rows = "\n".join(
            (
                "<tr>"
                f"<td>{html.escape(item.get('date', ''))}</td>"
                f"<td>{item.get('failures', 0)}</td>"
                f"<td>{item.get('blocked', 0)}</td>"
                f"<td>{item.get('invalid_lines', {}).get('failure', 0)}</td>"
                f"<td>{item.get('invalid_lines', {}).get('blocked', 0)}</td>"
                "</tr>"
            )
            for item in per_day
        )

        sample_rows = "\n".join(
            (
                "<tr>"
                f"<td>{html.escape(item.get('run_dir', ''))}</td>"
                f"<td>{html.escape(item.get('kind', ''))}</td>"
                f"<td>{html.escape(item.get('field', ''))}</td>"
                f"<td>{html.escape(item.get('path', ''))}</td>"
                f"<td>{html.escape(item.get('url', ''))}</td>"
                "</tr>"
            )
            for item in samples
        )

        missing = totals.get("missing", {})
        missing_failure = missing.get("failure", {})
        missing_blocked = missing.get("blocked", {})
        invalid = totals.get("invalid_lines", {})

        return (
            "<html><head><meta charset=\"utf-8\"/>"
            "<style>"
            "body{font-family:Arial,Helvetica,sans-serif;margin:20px;color:#222;}"
            "table{border-collapse:collapse;width:100%;margin-bottom:24px;}"
            "th,td{border:1px solid #ddd;padding:8px;text-align:left;font-size:14px;}"
            "th{background:#f2f2f2;}"
            "h2{margin-top:24px;}"
            "</style></head><body>"
            "<h1>Artifact Audit Report</h1>"
            f"<p>Total Failures: {totals.get('failures', 0)}</p>"
            f"<p>Total Blocked: {totals.get('blocked', 0)}</p>"
            f"<p>Invalid Failure Lines: {invalid.get('failure', 0)}</p>"
            f"<p>Invalid Blocked Lines: {invalid.get('blocked', 0)}</p>"
            "<h2>Missing Failure Artifacts</h2>"
            "<table>"
            "<tr><th>HTML</th><th>Screenshot</th><th>Text</th><th>Meta</th></tr>"
            f"<tr><td>{missing_failure.get('html_path', 0)}</td>"
            f"<td>{missing_failure.get('screenshot_path', 0)}</td>"
            f"<td>{missing_failure.get('text_path', 0)}</td>"
            f"<td>{missing_failure.get('meta_path', 0)}</td></tr>"
            "</table>"
            "<h2>Missing Blocked Artifacts</h2>"
            "<table>"
            "<tr><th>Content</th><th>Screenshot</th></tr>"
            f"<tr><td>{missing_blocked.get('content_path', 0)}</td>"
            f"<td>{missing_blocked.get('screenshot_path', 0)}</td></tr>"
            "</table>"
            "<h2>Per Day</h2>"
            "<table>"
            "<tr><th>Date</th><th>Failures</th><th>Blocked</th><th>Invalid Fail</th><th>Invalid Blocked</th></tr>"
            f"{day_rows}"
            "</table>"
            "<h2>Samples</h2>"
            "<table>"
            "<tr><th>Run</th><th>Kind</th><th>Field</th><th>Path</th><th>URL</th></tr>"
            f"{sample_rows}"
            "</table>"
            "</body></html>"
        )


#########################################################
# CLI
#########################################################

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit run artifacts integrity.")
    parser.add_argument("--days", type=int, default=_DEFAULT_LOOKBACK_DAYS, help="Lookback days.")
    parser.add_argument("--runs-dir", default="", help="Runs directory path.")
    parser.add_argument("--output-dir", default="", help="Report output directory.")
    parser.add_argument("--sample-limit", type=int, default=_DEFAULT_SAMPLE_LIMIT, help="Sample size for missing artifacts.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    runs_dir = Path(args.runs_dir) if args.runs_dir else _RUNS_DIR
    output_dir = Path(args.output_dir) if args.output_dir else _REPORT_DIR
    job = ArtifactAuditJob(
        runs_dir=runs_dir,
        output_dir=output_dir,
        lookback_days=max(args.days, 1),
        sample_limit=max(args.sample_limit, 0),
    )
    raise SystemExit(job.run() is None)


if __name__ == "__main__":
    main()
