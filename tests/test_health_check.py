from datetime import datetime, timezone

import pytest

from dealwatch.core.models import RunStats
from dealwatch.infra.obs.health_check import HealthMonitor


class _DummyRepo:
    async def insert_run_stats(self, stats: RunStats) -> None:
        return None


class _DummyNotifier:
    def send_custom_report(self, *args, **kwargs) -> None:
        return None


class _BadRepo:
    async def insert_run_stats(self, stats: RunStats) -> None:
        raise RuntimeError("boom")


class _BadNotifier:
    def send_custom_report(self, *args, **kwargs) -> None:
        raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_health_monitor_evaluate_issues(monkeypatch) -> None:
    stats = RunStats(
        store_id="weee",
        start_time=datetime.now(timezone.utc),
        discovered_count=0,
        parsed_count=0,
        error_count=1,
        confirmed_deals_count=0,
        skipped_count=0,
    )
    monitor = HealthMonitor(repo=_DummyRepo(), notifier=_DummyNotifier())

    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(HealthMonitor, "send_alert_email", _noop)

    issues = await monitor.evaluate(stats, error_snippet="IP_RESTRICTED:abc")
    assert "DISCOVERY_EMPTY" in issues
    assert "IP_RESTRICTED" in issues


@pytest.mark.asyncio
async def test_health_monitor_parse_rate_low(monkeypatch) -> None:
    stats = RunStats(
        store_id="weee",
        start_time=datetime.now(timezone.utc),
        discovered_count=10,
        parsed_count=5,
        error_count=1,
        confirmed_deals_count=0,
        skipped_count=0,
    )
    monitor = HealthMonitor(repo=_DummyRepo(), notifier=_DummyNotifier())

    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(HealthMonitor, "send_alert_email", _noop)

    issues = await monitor.evaluate(stats)
    assert "PARSE_RATE_LOW" in issues


@pytest.mark.asyncio
async def test_health_monitor_artifact_context(tmp_path, monkeypatch) -> None:
    stats = RunStats(
        store_id="weee",
        start_time=datetime.now(timezone.utc),
        discovered_count=0,
        parsed_count=0,
        error_count=1,
        confirmed_deals_count=0,
        skipped_count=0,
    )
    monitor = HealthMonitor(repo=_DummyRepo(), notifier=_DummyNotifier())

    run_dir = tmp_path / "runs" / "2026-02-03"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "failures_index.ndjson").write_text(
        "{\"url\":\"https://example.com/fail\"}\n",
        encoding="utf-8",
    )
    (run_dir / "blocked_index.ndjson").write_text(
        "{\"url\":\"https://example.com/blocked\",\"keyword\":\"access denied\"}\n",
        encoding="utf-8",
    )
    reports_dir = tmp_path / "runs" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "artifact_audit_20260203_000000.html").write_text(
        "<html></html>",
        encoding="utf-8",
    )

    captured: list[str] = []

    async def _capture(self, issue_type: str, details: str) -> None:
        captured.append(details)

    monkeypatch.setattr(HealthMonitor, "send_alert_email", _capture)

    issues = await monitor.evaluate(
        stats,
        error_snippet="IP_RESTRICTED:abc",
        run_dir=run_dir,
    )
    assert "DISCOVERY_EMPTY" in issues
    assert captured
    assert "Failure Artifacts" in captured[0]
    assert "Blocked Artifacts" in captured[0]
    assert "Artifact Audit Report" in captured[0]


@pytest.mark.asyncio
async def test_health_monitor_no_reports_dir(tmp_path, monkeypatch) -> None:
    stats = RunStats(
        store_id="weee",
        start_time=datetime.now(timezone.utc),
        discovered_count=0,
        parsed_count=0,
        error_count=1,
        confirmed_deals_count=0,
        skipped_count=0,
    )
    monitor = HealthMonitor(repo=_DummyRepo(), notifier=_DummyNotifier())

    run_dir = tmp_path / "runs" / "2026-02-03"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "failures_index.ndjson").write_text(
        "{\"url\":\"https://example.com/fail\"}\n",
        encoding="utf-8",
    )

    captured: list[str] = []

    async def _capture(self, issue_type: str, details: str) -> None:
        captured.append(details)

    monkeypatch.setattr(HealthMonitor, "send_alert_email", _capture)

    issues = await monitor.evaluate(
        stats,
        error_snippet="IP_RESTRICTED:abc",
        run_dir=run_dir,
    )
    assert "DISCOVERY_EMPTY" in issues
    assert captured
    assert "Artifact Audit Report" not in captured[0]


@pytest.mark.asyncio
async def test_health_monitor_send_alert(monkeypatch) -> None:
    stats = RunStats(
        store_id="weee",
        start_time=datetime.now(timezone.utc),
        discovered_count=1,
        parsed_count=1,
        error_count=0,
        confirmed_deals_count=0,
        skipped_count=0,
    )
    monitor = HealthMonitor(repo=_DummyRepo(), notifier=_DummyNotifier())
    await monitor.record_run(stats)

    async def _direct(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr("dealwatch.infra.obs.health_check.asyncio.to_thread", _direct)
    await monitor.send_alert_email("PARSE_RATE_LOW", "<div>details</div>")


@pytest.mark.asyncio
async def test_health_monitor_record_run_error() -> None:
    stats = RunStats(
        store_id="weee",
        start_time=datetime.now(timezone.utc),
        discovered_count=1,
        parsed_count=1,
        error_count=0,
        confirmed_deals_count=0,
        skipped_count=0,
    )
    monitor = HealthMonitor(repo=_BadRepo(), notifier=_DummyNotifier())
    await monitor.record_run(stats)


@pytest.mark.asyncio
async def test_health_monitor_send_alert_error(monkeypatch) -> None:
    stats = RunStats(
        store_id="weee",
        start_time=datetime.now(timezone.utc),
        discovered_count=1,
        parsed_count=1,
        error_count=0,
        confirmed_deals_count=0,
        skipped_count=0,
    )
    monitor = HealthMonitor(repo=_DummyRepo(), notifier=_BadNotifier())
    await monitor.record_run(stats)

    async def _direct(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr("dealwatch.infra.obs.health_check.asyncio.to_thread", _direct)
    await monitor.send_alert_email("PARSE_RATE_LOW", "<div>details</div>")
