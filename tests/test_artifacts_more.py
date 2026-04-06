import csv
from datetime import datetime, timezone
from pathlib import Path

import pytest

from dealwatch.core.artifacts import ArtifactManager
from dealwatch.core.models import DealEvent, Offer, PriceContext


def _deal(drop_pct: float, title: str = "Item") -> DealEvent:
    offer = Offer(
        store_id="weee",
        product_key=f"p{int(drop_pct)}",
        title=title,
        url="https://example.com",
        price=1.0,
        original_price=2.0,
        fetch_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        context=PriceContext(region="00000"),
        unit_price_info={"unit": "lb", "quantity": 1.0},
    )
    return DealEvent(
        offer=offer,
        last_price=2.0,
        drop_amount=1.0,
        drop_pct=drop_pct,
        is_new_low=False,
    )


def test_artifacts_sort_and_write(tmp_path) -> None:
    manager = ArtifactManager(base_dir=tmp_path)
    deals = [_deal(5.0, "low"), _deal(20.0, "high"), _deal(10.0, "mid")]
    json_path = manager.save_deals(deals, "weee", total_checked=3)
    csv_path = json_path.with_suffix(".csv")
    dashboard_path = json_path.parent / "index.html"

    assert json_path.exists() is True
    assert csv_path.exists() is True
    assert dashboard_path.exists() is True

    with json_path.open("r", encoding="utf-8") as handle:
        payload = handle.read()
    assert "\"confirmed_count\": 3" in payload

    with csv_path.open("r", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert rows[0]["title"] == "high"
    assert rows[0]["drop_pct"] == "20.0"
    assert "unit_price_info" in rows[0]


def test_artifacts_dashboard_load_failure_index(tmp_path) -> None:
    manager = ArtifactManager(base_dir=tmp_path)
    run_dir = manager.get_run_dir()
    index_path = run_dir / "failures_index.ndjson"
    blocked_path = run_dir / "blocked_index.ndjson"
    index_path.write_text(
        "\n".join(
            [
                "{\"store_id\":\"weee\",\"url\":\"https://example.com\",\"reason\":\"boom\","
                "\"captured_at\":\"20260101_000000\",\"html_path\":\"failures/weee/a.html\","
                "\"screenshot_path\":\"failures/weee/a.png\","
                "\"text_path\":\"failures/weee/a.txt\"}",
                "invalid json",
            ]
        ),
        encoding="utf-8",
    )
    blocked_path.write_text(
        "{\"captured_at\":\"20260101_000000\",\"keyword\":\"access denied\","
        "\"content_path\":\"blocked/a.html\",\"screenshot_path\":\"blocked/a.png\","
        "\"url\":\"https://example.com\"}",
        encoding="utf-8",
    )
    html_path = manager._write_dashboard(run_dir)
    content = html_path.read_text(encoding="utf-8")
    assert "Failures" in content
    assert "Blocked" in content
    assert "weee" in content
    assert "Text" in content


def test_artifacts_clip_text_long() -> None:
    manager = ArtifactManager()
    long_text = "x" * 800
    clipped = manager._clip_text(long_text)
    assert len(clipped) == 500


def test_artifacts_get_run_dir_mkdir_failure(monkeypatch, tmp_path) -> None:
    manager = ArtifactManager(base_dir=tmp_path / "runs")

    def _raise(*args, **kwargs):
        raise OSError("boom")

    monkeypatch.setattr(Path, "mkdir", _raise)

    with pytest.raises(OSError):
        manager.get_run_dir()


def test_artifacts_save_deals_json_failure(monkeypatch, tmp_path) -> None:
    manager = ArtifactManager(base_dir=tmp_path)
    deals = [_deal(5.0, "low")]

    original_open = Path.open

    def _open(self, *args, **kwargs):
        if self.suffix == ".json":
            raise OSError("no json")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", _open)

    with pytest.raises(OSError):
        manager.save_deals(deals, "weee", total_checked=1)


def test_artifacts_save_deals_csv_failure(monkeypatch, tmp_path) -> None:
    manager = ArtifactManager(base_dir=tmp_path)
    deals = [_deal(5.0, "low")]

    def _write_csv(self, *args, **kwargs):
        raise OSError("no csv")

    monkeypatch.setattr(ArtifactManager, "_write_csv", _write_csv)

    with pytest.raises(OSError):
        manager.save_deals(deals, "weee", total_checked=1)
