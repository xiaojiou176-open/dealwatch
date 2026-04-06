from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from dealwatch.core.models import RunStats
from dealwatch.legacy.db_repo import DatabaseRepository
from dealwatch.jobs.run_report import RunReportJob


class _FakeRepo:
    def __init__(self, runs=None, fail_init: bool = False) -> None:
        self._runs = list(runs or [])
        self._fail_init = fail_init

    async def initialize(self) -> None:
        if self._fail_init:
            raise RuntimeError("boom")

    async def get_recent_runs(self, limit: int = 200):
        return list(self._runs)[:limit]


@pytest.mark.asyncio
async def test_run_report_job_generates(tmp_path) -> None:
    db_path = tmp_path / "dealwatch.db"
    repo = DatabaseRepository(db_path)
    await repo.initialize()

    now = datetime.now(timezone.utc)
    await repo.insert_run_stats(
        RunStats(
            store_id="weee",
            start_time=now,
            discovered_count=10,
            parsed_count=8,
            error_count=1,
            confirmed_deals_count=2,
            skipped_count=1,
        )
    )
    await repo.insert_run_stats(
        RunStats(
            store_id="weee",
            start_time=now - timedelta(days=8),
            discovered_count=10,
            parsed_count=10,
            error_count=0,
            confirmed_deals_count=3,
            skipped_count=0,
        )
    )
    await repo.insert_run_stats(
        RunStats(
            store_id="ttm",
            start_time=now - timedelta(days=1),
            discovered_count=5,
            parsed_count=5,
            error_count=0,
            confirmed_deals_count=1,
            skipped_count=0,
        )
    )

    output_dir = tmp_path / "reports"
    job = RunReportJob(
        repo=repo,
        output_dir=output_dir,
        lookback_days=7,
        limit=10,
    )
    html_path = await job.run()

    assert html_path is not None
    assert output_dir.exists() is True

    json_files = list(output_dir.glob("run_report_*.json"))
    html_files = list(output_dir.glob("run_report_*.html"))
    assert json_files
    assert html_files

    payload = json_files[0].read_text(encoding="utf-8")
    assert "\"recent\"" in payload
    assert "\"baseline\"" in payload
    assert "\"store_id\": \"weee\"" in payload
    assert "\"alerts\"" in payload


@pytest.mark.asyncio
async def test_db_repo_recent_runs_order(tmp_path) -> None:
    db_path = tmp_path / "dealwatch.db"
    repo = DatabaseRepository(db_path)
    await repo.initialize()

    now = datetime.now(timezone.utc)
    await repo.insert_run_stats(
        RunStats(
            store_id="weee",
            start_time=now - timedelta(days=1),
            discovered_count=10,
            parsed_count=8,
            error_count=1,
            confirmed_deals_count=2,
            skipped_count=1,
        )
    )
    await repo.insert_run_stats(
        RunStats(
            store_id="weee",
            start_time=now,
            discovered_count=5,
            parsed_count=5,
            error_count=0,
            confirmed_deals_count=1,
            skipped_count=0,
        )
    )

    runs = await repo.get_recent_runs(limit=2)
    assert len(runs) == 2
    assert runs[0].start_time >= runs[1].start_time


@pytest.mark.asyncio
async def test_run_report_job_init_failure(tmp_path) -> None:
    repo = _FakeRepo(fail_init=True)
    job = RunReportJob(repo=repo, output_dir=tmp_path / "reports")
    assert await job.run() is None


@pytest.mark.asyncio
async def test_run_report_job_no_recent_runs(tmp_path) -> None:
    now = datetime.now(timezone.utc)
    old_run = RunStats(
        store_id="weee",
        start_time=now - timedelta(days=10),
        discovered_count=10,
        parsed_count=9,
        error_count=0,
        confirmed_deals_count=1,
        skipped_count=0,
    )
    repo = _FakeRepo([old_run])
    job = RunReportJob(repo=repo, output_dir=tmp_path / "reports", lookback_days=3)
    assert await job.run() is None


@pytest.mark.asyncio
async def test_run_report_job_output_dir_failure(monkeypatch, tmp_path) -> None:
    now = datetime.now(timezone.utc)
    run = RunStats(
        store_id="weee",
        start_time=now,
        discovered_count=10,
        parsed_count=8,
        error_count=1,
        confirmed_deals_count=2,
        skipped_count=0,
    )
    repo = _FakeRepo([run])
    output_dir = tmp_path / "reports"

    original_mkdir = Path.mkdir

    def _mkdir(self, *args, **kwargs):
        if self == output_dir:
            raise OSError("boom")
        return original_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", _mkdir)

    job = RunReportJob(repo=repo, output_dir=output_dir, lookback_days=1)
    assert await job.run() is None


@pytest.mark.asyncio
async def test_run_report_job_json_write_failure(monkeypatch, tmp_path) -> None:
    now = datetime.now(timezone.utc)
    run = RunStats(
        store_id="weee",
        start_time=now,
        discovered_count=10,
        parsed_count=8,
        error_count=1,
        confirmed_deals_count=2,
        skipped_count=0,
    )
    repo = _FakeRepo([run])
    output_dir = tmp_path / "reports"

    original_write = Path.write_text

    def _write_text(self, *args, **kwargs):
        if self.suffix == ".json":
            raise OSError("boom")
        return original_write(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", _write_text)

    job = RunReportJob(repo=repo, output_dir=output_dir, lookback_days=1)
    assert await job.run() is None


@pytest.mark.asyncio
async def test_run_report_job_html_write_failure(monkeypatch, tmp_path) -> None:
    now = datetime.now(timezone.utc)
    run = RunStats(
        store_id="weee",
        start_time=now,
        discovered_count=10,
        parsed_count=8,
        error_count=1,
        confirmed_deals_count=2,
        skipped_count=0,
    )
    repo = _FakeRepo([run])
    output_dir = tmp_path / "reports"

    original_write = Path.write_text

    def _write_text(self, *args, **kwargs):
        if self.suffix == ".html":
            raise OSError("boom")
        return original_write(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", _write_text)

    job = RunReportJob(repo=repo, output_dir=output_dir, lookback_days=1)
    assert await job.run() is None


def test_run_report_compute_rates_edges() -> None:
    job = RunReportJob(repo=_FakeRepo())
    rates = job._compute_rates(
        {
            "discovered": 0,
            "parsed": 0,
            "errors": 0,
            "confirmed": 0,
            "skipped": 0,
        }
    )
    assert rates["parse_rate"] == 0.0
    assert rates["error_rate"] == 0.0
    assert rates["deal_rate"] == 0.0

    rates = job._compute_rates(
        {
            "discovered": 10,
            "parsed": 5,
            "errors": 2,
            "confirmed": 1,
            "skipped": 3,
        }
    )
    assert rates["parse_rate"] == round(5 / 7, 4)
    assert rates["error_rate"] == round(2 / 10, 4)
    assert rates["deal_rate"] == round(1 / 10, 4)


def test_run_report_build_report_alerts() -> None:
    job = RunReportJob(repo=_FakeRepo())
    now = datetime.now(timezone.utc)
    recent = [
        RunStats(
            store_id="weee",
            start_time=now - timedelta(hours=1),
            discovered_count=10,
            parsed_count=5,
            error_count=5,
            confirmed_deals_count=1,
            skipped_count=0,
        ),
        RunStats(
            store_id="ttm",
            start_time=now - timedelta(hours=1),
            discovered_count=5,
            parsed_count=5,
            error_count=0,
            confirmed_deals_count=1,
            skipped_count=0,
        ),
    ]
    baseline = [
        RunStats(
            store_id="weee",
            start_time=now - timedelta(days=3),
            discovered_count=10,
            parsed_count=10,
            error_count=0,
            confirmed_deals_count=5,
            skipped_count=0,
        )
    ]

    report = job._build_report(
        recent,
        baseline,
        now - timedelta(days=1),
        now - timedelta(days=4),
        now,
    )
    alert_types = {item["type"] for item in report["alerts"]}
    assert "parse_rate_drop" in alert_types
    assert "error_rate_rise" in alert_types
    assert "deal_rate_drop" in alert_types

    stores = {item["store_id"]: item for item in report["stores"]}
    assert stores["ttm"]["parse_rate_delta"] is None


def test_run_report_filter_runs_bounds() -> None:
    job = RunReportJob(repo=_FakeRepo())
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=1)
    end = now
    runs = [
        RunStats(
            store_id="weee",
            start_time=start,
            discovered_count=1,
            parsed_count=1,
            error_count=0,
            confirmed_deals_count=0,
            skipped_count=0,
        ),
        RunStats(
            store_id="weee",
            start_time=end,
            discovered_count=1,
            parsed_count=1,
            error_count=0,
            confirmed_deals_count=0,
            skipped_count=0,
        ),
    ]
    filtered = job._filter_runs(runs, start, end)
    assert len(filtered) == 1


def test_run_report_cli_success(monkeypatch, tmp_path) -> None:
    output_dir = tmp_path / "reports"

    async def _run(self):
        return output_dir / "run_report_test.html"

    monkeypatch.setattr(RunReportJob, "run", _run)
    import sys

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_report",
            "--days",
            "3",
            "--baseline-days",
            "5",
            "--limit",
            "10",
            "--output-dir",
            str(output_dir),
            "--parse-drop",
            "0.1",
            "--error-rise",
            "0.2",
            "--deal-drop",
            "0.3",
            "--db",
            str(tmp_path / "dealwatch.db"),
        ],
    )

    from dealwatch.jobs import run_report

    try:
        run_report.main()
    except SystemExit as exc:
        assert exc.code == 0


def test_run_report_cli_failure(monkeypatch, tmp_path) -> None:
    async def _run(self):
        return None

    monkeypatch.setattr(RunReportJob, "run", _run)
    import sys

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_report",
            "--days",
            "1",
            "--baseline-days",
            "1",
        ],
    )

    from dealwatch.jobs import run_report

    try:
        run_report.main()
    except SystemExit as exc:
        assert exc.code == 1
