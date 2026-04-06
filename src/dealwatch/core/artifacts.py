from __future__ import annotations

import csv
import html
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Final, List

from dealwatch.core.models import DealEvent


#########################################################
# Constants
#########################################################
_PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_DEFAULT_BASE_DIR: Final[Path] = _PROJECT_ROOT / ".runtime-cache" / "runs"
_DATE_FORMAT: Final[str] = "%Y-%m-%d"
_MAX_TEXT_FIELD: Final[int] = 500
_DASHBOARD_NAME: Final[str] = "index.html"
_FAILURE_INDEX_NAME: Final[str] = "failures_index.ndjson"
_BLOCKED_INDEX_NAME: Final[str] = "blocked_index.ndjson"


#########################################################
# Artifact Manager
#########################################################
@dataclass(slots=True)
class ArtifactManager:
    base_dir: Path = _DEFAULT_BASE_DIR
    logger: logging.Logger = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.base_dir, Path):
            self.base_dir = Path(self.base_dir)
        self.logger = logging.getLogger(__name__)

    def get_run_dir(self) -> Path:
        run_date = datetime.now(timezone.utc).strftime(_DATE_FORMAT)
        run_dir = self.base_dir / run_date
        try:
            run_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.logger.exception("Failed to create run directory: %s", exc)
            raise
        return run_dir

    def save_deals(
        self,
        deals: List[DealEvent],
        store_id: str,
        total_checked: int | None = None,
    ) -> Path:
        run_dir = self.get_run_dir()

        sorted_deals = sorted(
            deals,
            key=lambda item: item.drop_pct,
            reverse=True,
        )

        if total_checked is None:
            total_checked = len(deals)

        payload = {
            "run_time": datetime.now(timezone.utc).isoformat(),
            "total_checked": total_checked,
            "confirmed_count": len(sorted_deals),
            "deals": [deal.to_dict() for deal in sorted_deals],
        }

        json_path = run_dir / f"{store_id}_confirmed.json"
        csv_path = run_dir / f"{store_id}_confirmed.csv"

        try:
            with json_path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
        except OSError as exc:
            self.logger.exception("Failed to write JSON artifact: %s", exc)
            raise

        try:
            self._write_csv(csv_path, sorted_deals)
        except OSError as exc:
            self.logger.exception("Failed to write CSV artifact: %s", exc)
            raise

        try:
            self._write_dashboard(run_dir)
        except Exception as exc:
            self.logger.warning("Failed to build dashboard: %s", exc)

        return json_path

    #########################################################
    # Internal
    #########################################################
    def _write_csv(self, path: Path, deals: List[DealEvent]) -> None:
        fieldnames = [
            "store_id",
            "product_key",
            "title",
            "url",
            "price",
            "original_price",
            "last_price",
            "drop_amount",
            "drop_pct",
            "is_new_low",
            "fetch_at",
            "region",
            "currency",
            "is_member",
            "unit_price_info",
        ]

        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()

            for deal in deals:
                offer = deal.offer
                context = offer.context
                writer.writerow(
                    {
                        "store_id": offer.store_id,
                        "product_key": offer.product_key,
                        "title": self._clip_text(offer.title),
                        "url": self._clip_text(offer.url),
                        "price": offer.price,
                        "original_price": offer.original_price,
                        "last_price": deal.last_price,
                        "drop_amount": deal.drop_amount,
                        "drop_pct": deal.drop_pct,
                        "is_new_low": deal.is_new_low,
                        "fetch_at": offer.fetch_at.isoformat(),
                        "region": context.region,
                        "currency": context.currency,
                        "is_member": context.is_member,
                        "unit_price_info": json.dumps(
                            offer.unit_price_info,
                            ensure_ascii=False,
                        ),
                    }
                )

    @staticmethod
    def _clip_text(value: str) -> str:
        text = str(value)
        if len(text) <= _MAX_TEXT_FIELD:
            return text
        return text[:_MAX_TEXT_FIELD]

    #########################################################
    # Dashboard
    #########################################################
    def _write_dashboard(self, run_dir: Path) -> Path:
        dashboard_path = run_dir / _DASHBOARD_NAME
        html_content = self._build_dashboard_html(run_dir)
        dashboard_path.write_text(html_content, encoding="utf-8")
        return dashboard_path

    def _build_dashboard_html(self, run_dir: Path) -> str:
        deals = self._load_deal_summaries(run_dir)
        failures = self._load_failure_index(run_dir)
        blocked = self._load_blocked_index(run_dir)

        deals_rows = "\n".join(
            (
                "<tr>"
                f"<td>{html.escape(item['store_id'])}</td>"
                f"<td>{item['confirmed_count']}</td>"
                f"<td>{item['total_checked']}</td>"
                f"<td><a href=\"{html.escape(item['json_path'])}\">JSON</a></td>"
                f"<td><a href=\"{html.escape(item['csv_path'])}\">CSV</a></td>"
                "</tr>"
            )
            for item in deals
        )

        failure_rows = "\n".join(
            (
                "<tr>"
                f"<td>{html.escape(entry.get('captured_at', ''))}</td>"
                f"<td>{html.escape(entry.get('store_id', ''))}</td>"
                f"<td>{html.escape(entry.get('reason', ''))}</td>"
                f"<td><a href=\"{html.escape(entry.get('html_path', ''))}\">HTML</a></td>"
                f"<td><a href=\"{html.escape(entry.get('screenshot_path', ''))}\">PNG</a></td>"
                f"<td>{self._render_optional_link(entry.get('text_path', ''), 'Text')}</td>"
                f"<td>{html.escape(entry.get('url', ''))}</td>"
                "</tr>"
            )
            for entry in failures
        )

        blocked_rows = "\n".join(
            (
                "<tr>"
                f"<td>{html.escape(entry.get('captured_at', ''))}</td>"
                f"<td>{html.escape(entry.get('keyword', ''))}</td>"
                f"<td><a href=\"{html.escape(entry.get('content_path', ''))}\">HTML</a></td>"
                f"<td><a href=\"{html.escape(entry.get('screenshot_path', ''))}\">PNG</a></td>"
                f"<td>{html.escape(entry.get('url', ''))}</td>"
                "</tr>"
            )
            for entry in blocked
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
            "<h1>DealWatch Run Dashboard</h1>"
            "<h2>Confirmed Deals</h2>"
            "<table>"
            "<tr><th>Store</th><th>Confirmed</th><th>Total Checked</th><th>JSON</th><th>CSV</th></tr>"
            f"{deals_rows}"
            "</table>"
            "<h2>Failures</h2>"
            "<table>"
            "<tr><th>Time</th><th>Store</th><th>Reason</th><th>HTML</th><th>Screenshot</th><th>Text</th><th>URL</th></tr>"
            f"{failure_rows}"
            "</table>"
            "<h2>Blocked</h2>"
            "<table>"
            "<tr><th>Time</th><th>Keyword</th><th>HTML</th><th>Screenshot</th><th>URL</th></tr>"
            f"{blocked_rows}"
            "</table>"
            "</body></html>"
        )

    def _load_deal_summaries(self, run_dir: Path) -> list[dict]:
        summaries: list[dict] = []
        for json_path in run_dir.glob("*_confirmed.json"):
            try:
                payload = json.loads(json_path.read_text(encoding="utf-8"))
            except Exception as exc:
                self.logger.warning("Failed to read %s: %s", json_path, exc)
                continue

            store_id = json_path.stem.replace("_confirmed", "")
            summaries.append(
                {
                    "store_id": store_id,
                    "confirmed_count": int(payload.get("confirmed_count", 0)),
                    "total_checked": int(payload.get("total_checked", 0)),
                    "json_path": json_path.name,
                    "csv_path": json_path.with_suffix(".csv").name,
                }
            )

        return sorted(summaries, key=lambda item: item["store_id"])

    def _load_failure_index(self, run_dir: Path) -> list[dict]:
        index_path = run_dir / _FAILURE_INDEX_NAME
        if not index_path.exists():
            return []

        entries: list[dict] = []
        try:
            for line in index_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    self.logger.warning("Failed to parse failure index line: %s", exc)
        except OSError as exc:
            self.logger.warning("Failed to read failure index: %s", exc)

        return entries

    @staticmethod
    def _render_optional_link(path: str, label: str) -> str:
        safe_path = str(path or "").strip()
        if not safe_path:
            return ""
        return f"<a href=\"{html.escape(safe_path)}\">{html.escape(label)}</a>"

    def _load_blocked_index(self, run_dir: Path) -> list[dict]:
        index_path = run_dir / _BLOCKED_INDEX_NAME
        if not index_path.exists():
            return []

        entries: list[dict] = []
        try:
            for line in index_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    self.logger.warning("Failed to parse blocked index line: %s", exc)
        except OSError as exc:
            self.logger.warning("Failed to read blocked index: %s", exc)

        return entries
