from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from dealwatch.jobs.maintenance import MaintenanceJob, MaintenanceSummary


class _DummyRepo:
    def __init__(self) -> None:
        self.cleaned = False
        self.vacuumed = False

    async def cleanup_price_history(self, older_than_days: int = 180) -> int:
        self.cleaned = True
        return 1

    async def vacuum(self) -> None:
        self.vacuumed = True


class _ErrorRepo:
    async def cleanup_price_history(self, older_than_days: int = 180) -> int:
        raise RuntimeError("boom")

    async def vacuum(self) -> None:
        raise RuntimeError("boom")


def _make_run_dir(base: Path, dt: datetime) -> Path:
    run_dir = base / dt.strftime("%Y-%m-%d")
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _make_watch_task_run_dir(
    base: Path,
    *,
    task_id: str,
    run_id: str,
    finished_at: datetime | None,
) -> Path:
    run_dir = base / "watch-tasks" / task_id / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "run": {
            "id": run_id,
            "finished_at": finished_at.isoformat() if finished_at else None,
            "started_at": finished_at.isoformat() if finished_at else None,
        },
        "observation": {
            "observed_at": finished_at.isoformat() if finished_at else None,
        },
    }
    (run_dir / "task_run_summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return run_dir


def _make_reports_dir(base: Path) -> Path:
    reports_dir = base / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    return reports_dir


def _make_backups_dir(base: Path) -> Path:
    backups_dir = base / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)
    return backups_dir


def _make_log(logs_dir: Path, name: str, *, age_days: int) -> Path:
    path = logs_dir / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x", encoding="utf-8")
    timestamp = (datetime.now(timezone.utc) - timedelta(days=age_days)).timestamp()
    os.utime(path, (timestamp, timestamp))
    return path


def test_parse_run_date_invalid() -> None:
    assert MaintenanceJob._parse_run_date("not-a-date") is None


@pytest.mark.asyncio
async def test_maintenance_cleanup_dated_runs_and_legacy_db(tmp_path: Path) -> None:
    repo = _DummyRepo()
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()

    old_date = datetime.now(timezone.utc) - timedelta(days=40)
    new_date = datetime.now(timezone.utc) - timedelta(days=5)

    old_path = _make_run_dir(runs_dir, old_date)
    new_path = _make_run_dir(runs_dir, new_date)

    job = MaintenanceJob(repo=repo, runs_dir=runs_dir, runs_keep_days=30)
    summary = await job.run()

    assert old_path.exists() is False
    assert new_path.exists() is True
    assert repo.cleaned is True
    assert repo.vacuumed is True
    assert any(action.path == old_path for action in summary.actions)


@pytest.mark.asyncio
async def test_cleanup_watch_task_runs_by_summary_timestamp_and_remove_empty_task_dir(
    tmp_path: Path,
) -> None:
    repo = _DummyRepo()
    runs_dir = tmp_path / "runs"
    old_finished = datetime.now(timezone.utc) - timedelta(days=45)
    new_finished = datetime.now(timezone.utc) - timedelta(days=2)
    old_run = _make_watch_task_run_dir(
        runs_dir,
        task_id="task-old",
        run_id="run-old",
        finished_at=old_finished,
    )
    new_run = _make_watch_task_run_dir(
        runs_dir,
        task_id="task-new",
        run_id="run-new",
        finished_at=new_finished,
    )

    job = MaintenanceJob(
        repo=repo,
        runs_dir=runs_dir,
        dry_run=False,
        clean_runtime=True,
        clean_legacy=False,
    )
    summary = await job.run()

    assert old_run.exists() is False
    assert old_run.parent.exists() is False
    assert new_run.exists() is True
    kinds = {action.kind for action in summary.actions}
    assert "watch-task-run" in kinds
    assert "watch-task-task-dir" in kinds


@pytest.mark.asyncio
async def test_cleanup_watch_task_runs_dry_run_keeps_files(tmp_path: Path) -> None:
    repo = _DummyRepo()
    runs_dir = tmp_path / "runs"
    old_run = _make_watch_task_run_dir(
        runs_dir,
        task_id="task-old",
        run_id="run-old",
        finished_at=datetime.now(timezone.utc) - timedelta(days=45),
    )

    job = MaintenanceJob(
        repo=repo,
        runs_dir=runs_dir,
        dry_run=True,
        clean_runtime=True,
        clean_legacy=False,
    )
    summary = await job.run()

    assert old_run.exists() is True
    assert any(action.path == old_run and action.applied is False for action in summary.actions)


def test_cleanup_runs_missing_dir(tmp_path: Path) -> None:
    repo = _DummyRepo()
    job = MaintenanceJob(repo=repo, runs_dir=tmp_path / "missing")
    summary = MaintenanceSummary(dry_run=False)
    job._cleanup_runs(summary)


def test_cleanup_runs_delete_failure(monkeypatch, tmp_path: Path) -> None:
    repo = _DummyRepo()
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    old_date = datetime.now(timezone.utc) - timedelta(days=40)
    old_path = _make_run_dir(runs_dir, old_date)

    def _raise(path):
        raise OSError("boom")

    monkeypatch.setattr(shutil, "rmtree", _raise)
    job = MaintenanceJob(repo=repo, runs_dir=runs_dir, runs_keep_days=30)
    summary = MaintenanceSummary(dry_run=False)
    job._cleanup_runs(summary)
    assert old_path.exists() is True


def test_cleanup_reports_by_stamp(tmp_path: Path) -> None:
    repo = _DummyRepo()
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    reports_dir = _make_reports_dir(runs_dir)

    old_stamp = (datetime.now(timezone.utc) - timedelta(days=40)).strftime("%Y%m%d_%H%M%S")
    new_stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    old_file = reports_dir / f"run_report_{old_stamp}.html"
    new_file = reports_dir / f"run_report_{new_stamp}.html"
    old_file.write_text("old", encoding="utf-8")
    new_file.write_text("new", encoding="utf-8")

    job = MaintenanceJob(repo=repo, runs_dir=runs_dir, reports_keep_days=30, clean_legacy=False)
    summary = MaintenanceSummary(dry_run=False)
    job._cleanup_reports(summary)

    assert old_file.exists() is False
    assert new_file.exists() is True


def test_cleanup_reports_mtime_fallback(tmp_path: Path) -> None:
    repo = _DummyRepo()
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    reports_dir = _make_reports_dir(runs_dir)

    custom_file = reports_dir / "custom_report.html"
    custom_file.write_text("x", encoding="utf-8")
    old_time = (datetime.now(timezone.utc) - timedelta(days=40)).timestamp()
    os.utime(custom_file, (old_time, old_time))

    job = MaintenanceJob(repo=repo, runs_dir=runs_dir, reports_keep_days=30, clean_legacy=False)
    summary = MaintenanceSummary(dry_run=False)
    job._cleanup_reports(summary)

    assert custom_file.exists() is False


def test_cleanup_reports_delete_failure(monkeypatch, tmp_path: Path) -> None:
    repo = _DummyRepo()
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    reports_dir = _make_reports_dir(runs_dir)

    old_stamp = (datetime.now(timezone.utc) - timedelta(days=40)).strftime("%Y%m%d_%H%M%S")
    old_file = reports_dir / f"run_report_{old_stamp}.json"
    old_file.write_text("old", encoding="utf-8")

    def _raise(*_args, **_kwargs):
        raise OSError("boom")

    monkeypatch.setattr(Path, "unlink", _raise)
    job = MaintenanceJob(repo=repo, runs_dir=runs_dir, reports_keep_days=30, clean_legacy=False)
    summary = MaintenanceSummary(dry_run=False)
    job._cleanup_reports(summary)
    assert old_file.exists() is True


def test_parse_report_timestamp_invalid() -> None:
    assert MaintenanceJob._parse_report_timestamp("nope.html") is None


def test_cleanup_backups_by_stamp(tmp_path: Path) -> None:
    repo = _DummyRepo()
    backups_dir = _make_backups_dir(tmp_path)

    old_stamp = (datetime.now(timezone.utc) - timedelta(days=40)).strftime("%Y%m%d_%H%M%S")
    new_stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    old_file = backups_dir / f"dealwatch_{old_stamp}.db"
    new_file = backups_dir / f"dealwatch_{new_stamp}.db"
    old_file.write_text("old", encoding="utf-8")
    new_file.write_text("new", encoding="utf-8")

    job = MaintenanceJob(
        repo=repo,
        backups_dir=backups_dir,
        backups_keep_days=30,
        clean_runtime=False,
        clean_legacy=True,
    )
    summary = MaintenanceSummary(dry_run=False)
    job._cleanup_backups(summary)

    assert old_file.exists() is False
    assert new_file.exists() is True


def test_cleanup_backups_mtime_fallback(tmp_path: Path) -> None:
    repo = _DummyRepo()
    backups_dir = _make_backups_dir(tmp_path)

    custom_file = backups_dir / "custom.db"
    custom_file.write_text("x", encoding="utf-8")
    old_time = (datetime.now(timezone.utc) - timedelta(days=40)).timestamp()
    os.utime(custom_file, (old_time, old_time))

    job = MaintenanceJob(
        repo=repo,
        backups_dir=backups_dir,
        backups_keep_days=30,
        clean_runtime=False,
        clean_legacy=True,
    )
    summary = MaintenanceSummary(dry_run=False)
    job._cleanup_backups(summary)

    assert custom_file.exists() is False


def test_cleanup_logs_keeps_active_file_and_prunes_old_rotated(tmp_path: Path) -> None:
    repo = _DummyRepo()
    logs_dir = tmp_path / "logs"
    active_log = _make_log(logs_dir, "dealwatch.log", age_days=40)
    rotated_old = _make_log(logs_dir, "dealwatch.log.1", age_days=40)
    rotated_new = _make_log(logs_dir, "dealwatch.log.2", age_days=2)

    job = MaintenanceJob(
        repo=repo,
        logs_dir=logs_dir,
        log_retention_days=14,
        clean_runtime=True,
        clean_legacy=False,
    )
    summary = MaintenanceSummary(dry_run=False)
    job._cleanup_logs(summary)

    assert active_log.exists() is True
    assert rotated_old.exists() is False
    assert rotated_new.exists() is True
    assert any(action.path == rotated_old for action in summary.actions)


@pytest.mark.asyncio
async def test_legacy_cleanup_does_not_touch_runtime_namespace(tmp_path: Path) -> None:
    repo = _DummyRepo()
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    runtime_old = _make_run_dir(runs_dir, datetime.now(timezone.utc) - timedelta(days=50))
    backups_dir = _make_backups_dir(tmp_path)
    old_backup = backups_dir / "dealwatch_20240101_000000.db"
    old_backup.write_text("backup", encoding="utf-8")
    old_time = (datetime.now(timezone.utc) - timedelta(days=40)).timestamp()
    os.utime(old_backup, (old_time, old_time))

    job = MaintenanceJob(
        repo=repo,
        runs_dir=runs_dir,
        backups_dir=backups_dir,
        clean_runtime=False,
        clean_legacy=True,
        backups_keep_days=30,
    )
    await job.run()

    assert runtime_old.exists() is True
    assert old_backup.exists() is False


@pytest.mark.asyncio
async def test_cleanup_price_history_error() -> None:
    repo = _ErrorRepo()
    job = MaintenanceJob(repo=repo)
    summary = MaintenanceSummary(dry_run=False)
    await job._cleanup_price_history(summary)


@pytest.mark.asyncio
async def test_vacuum_db_error() -> None:
    repo = _ErrorRepo()
    job = MaintenanceJob(repo=repo)
    summary = MaintenanceSummary(dry_run=False)
    await job._vacuum_db(summary)


@pytest.mark.asyncio
async def test_budget_cleanup_reclaims_operator_and_external_cache(tmp_path: Path) -> None:
    runtime_root = tmp_path / ".runtime-cache"
    runs_dir = runtime_root / "runs"
    logs_dir = runtime_root / "logs"
    operator_dir = runtime_root / "operator"
    external_cache_dir = tmp_path / ".external-cache"

    _make_log(logs_dir, "dealwatch.log", age_days=0)
    (operator_dir / "temp").mkdir(parents=True, exist_ok=True)
    (operator_dir / "temp" / "stale.txt").write_text("x" * 1024, encoding="utf-8")
    (external_cache_dir / "browser-debug").mkdir(parents=True, exist_ok=True)
    (external_cache_dir / "browser-debug" / "bundle.json").write_text(
        "x" * 2048,
        encoding="utf-8",
    )

    job = MaintenanceJob(
        repo=None,
        runs_dir=runs_dir,
        logs_dir=logs_dir,
        operator_dir=operator_dir,
        external_cache_dir=external_cache_dir,
        cache_budget_bytes=1_500,
        clean_runtime=True,
        clean_legacy=False,
    )
    summary = await job.run()

    assert (operator_dir / "temp").exists() is False
    assert (external_cache_dir / "browser-debug").exists() is False
    assert any(action.kind == "cache-budget" for action in summary.actions)
    assert any(note.startswith("cache_budget_exceeded_by_bytes=") for note in summary.notes)


@pytest.mark.asyncio
async def test_budget_cleanup_reports_protected_when_no_candidates(tmp_path: Path) -> None:
    runtime_root = tmp_path / ".runtime-cache"
    runs_dir = runtime_root / "runs"
    logs_dir = runtime_root / "logs"
    operator_dir = runtime_root / "operator"

    _make_log(logs_dir, "dealwatch.log", age_days=0)
    (operator_dir / "gemini-audit").mkdir(parents=True, exist_ok=True)
    (operator_dir / "gemini-audit" / "proof.json").write_text("x" * 4096, encoding="utf-8")

    job = MaintenanceJob(
        repo=None,
        runs_dir=runs_dir,
        logs_dir=logs_dir,
        operator_dir=operator_dir,
        external_cache_dir=tmp_path / ".external-cache",
        cache_budget_bytes=1_000,
        clean_runtime=True,
        clean_legacy=False,
    )
    summary = await job.run()

    assert (operator_dir / "gemini-audit").exists() is True
    assert "budget_exceeded_but_protected" in summary.notes


@pytest.mark.asyncio
async def test_budget_cleanup_preserves_persistent_browser_root(tmp_path: Path) -> None:
    runtime_root = tmp_path / ".runtime-cache"
    runs_dir = runtime_root / "runs"
    logs_dir = runtime_root / "logs"
    operator_dir = runtime_root / "operator"
    external_cache_dir = tmp_path / ".external-cache"
    dedicated_browser_root = external_cache_dir / "browser" / "chrome-user-data"
    dedicated_browser_root.mkdir(parents=True, exist_ok=True)
    (dedicated_browser_root / "Local State").write_text("{}", encoding="utf-8")
    (external_cache_dir / "temp").mkdir(parents=True, exist_ok=True)
    (external_cache_dir / "temp" / "stale.txt").write_text("x" * 2048, encoding="utf-8")

    job = MaintenanceJob(
        repo=None,
        runs_dir=runs_dir,
        logs_dir=logs_dir,
        operator_dir=operator_dir,
        external_cache_dir=external_cache_dir,
        cache_budget_bytes=100,
        clean_runtime=True,
        clean_legacy=False,
    )
    summary = await job.run()

    assert dedicated_browser_root.exists() is True
    assert (external_cache_dir / "temp").exists() is False
    assert "budget_exceeded_but_protected" not in summary.notes
