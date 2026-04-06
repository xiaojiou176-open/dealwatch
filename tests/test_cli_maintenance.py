from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import dealwatch.cli as cli


def _make_watch_task_run_dir(
    base: Path,
    *,
    task_id: str,
    run_id: str,
    finished_at: datetime,
) -> Path:
    run_dir = base / "watch-tasks" / task_id / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "run": {
            "id": run_id,
            "finished_at": finished_at.isoformat(),
            "started_at": finished_at.isoformat(),
        }
    }
    (run_dir / "task_run_summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return run_dir


def _make_log(logs_dir: Path, name: str, *, age_days: int) -> Path:
    path = logs_dir / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x", encoding="utf-8")
    timestamp = (datetime.now(timezone.utc) - timedelta(days=age_days)).timestamp()
    os.utime(path, (timestamp, timestamp))
    return path


def test_product_maintenance_cli_dry_run_and_apply(monkeypatch, tmp_path, capsys) -> None:
    runs_dir = tmp_path / "runs"
    logs_dir = tmp_path / "logs"
    old_run = _make_watch_task_run_dir(
        runs_dir,
        task_id="task-old",
        run_id="run-old",
        finished_at=datetime.now(timezone.utc) - timedelta(days=45),
    )
    old_log = _make_log(logs_dir, "dealwatch.log.1", age_days=40)

    monkeypatch.setattr(cli.settings, "RUNS_DIR", runs_dir)
    monkeypatch.setattr(cli.settings, "LOGS_DIR", logs_dir)
    monkeypatch.setattr(cli.settings, "OPERATOR_ARTIFACTS_DIR", tmp_path / "operator")
    monkeypatch.setattr(cli.settings, "EXTERNAL_CACHE_DIR", tmp_path / ".external-cache")
    monkeypatch.setattr(cli.settings, "MAINTENANCE_LOCK_PATH", tmp_path / "maintenance.lock")
    monkeypatch.setattr(cli.settings, "RUNS_KEEP_DAYS", 30)
    monkeypatch.setattr(cli.settings, "REPORTS_KEEP_DAYS", 30)
    monkeypatch.setattr(cli.settings, "LOG_RETENTION_DAYS", 14)
    monkeypatch.setattr(cli.settings, "CACHE_BUDGET_BYTES", 4_294_967_296)

    assert asyncio.run(cli._run_product_maintenance(["--dry-run"])) == 0
    dry_run_output = capsys.readouterr().out
    assert "mode=dry-run" in dry_run_output
    assert str(old_run) in dry_run_output
    assert str(old_log) in dry_run_output
    assert old_run.exists() is True
    assert old_log.exists() is True

    assert asyncio.run(cli._run_product_maintenance(["--apply"])) == 0
    apply_output = capsys.readouterr().out
    assert "mode=apply" in apply_output
    assert old_run.exists() is False
    assert old_run.parent.exists() is False
    assert old_log.exists() is False


def test_legacy_maintenance_cli_does_not_touch_runtime_namespace(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    created: list[object] = []

    class _Repo:
        def __init__(self, db_path: Path | str) -> None:
            self.db_path = Path(db_path)
            self.cleaned = False
            self.vacuumed = False
            created.append(self)

        async def initialize(self) -> None:
            return None

        async def close(self) -> None:
            return None

        async def cleanup_price_history(self, older_than_days: int = 180) -> int:
            self.cleaned = True
            return 5

        async def vacuum(self) -> None:
            self.vacuumed = True

    runs_dir = tmp_path / "runs"
    runtime_old = runs_dir / "2026-01-01"
    runtime_old.mkdir(parents=True, exist_ok=True)
    backups_dir = tmp_path / "legacy-backups"
    backups_dir.mkdir(parents=True, exist_ok=True)
    old_backup = backups_dir / "dealwatch_20240101_000000.db"
    old_backup.write_text("backup", encoding="utf-8")
    old_time = (datetime.now(timezone.utc) - timedelta(days=40)).timestamp()
    os.utime(old_backup, (old_time, old_time))

    monkeypatch.setattr(cli, "DatabaseRepository", _Repo)
    monkeypatch.setattr(cli.settings, "DB_PATH", tmp_path / "legacy" / "dealwatch.db")
    monkeypatch.setattr(cli.settings, "RUNS_DIR", runs_dir)
    monkeypatch.setattr(cli.settings, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(cli.settings, "OPERATOR_ARTIFACTS_DIR", tmp_path / "operator")
    monkeypatch.setattr(cli.settings, "EXTERNAL_CACHE_DIR", tmp_path / ".external-cache")
    monkeypatch.setattr(cli.settings, "MAINTENANCE_LOCK_PATH", tmp_path / "maintenance.lock")
    monkeypatch.setattr(cli.settings, "BACKUPS_DIR", backups_dir)
    monkeypatch.setattr(cli.settings, "RUNS_KEEP_DAYS", 30)
    monkeypatch.setattr(cli.settings, "REPORTS_KEEP_DAYS", 30)
    monkeypatch.setattr(cli.settings, "BACKUPS_KEEP_DAYS", 30)
    monkeypatch.setattr(cli.settings, "PRICE_HISTORY_KEEP_DAYS", 180)
    monkeypatch.setattr(cli.settings, "LOG_RETENTION_DAYS", 14)
    monkeypatch.setattr(cli.settings, "CACHE_BUDGET_BYTES", 4_294_967_296)

    assert asyncio.run(cli._run_legacy_maintenance([])) == 0
    capsys.readouterr()

    assert runtime_old.exists() is True
    assert old_backup.exists() is False
    assert created
    assert created[0].cleaned is True
    assert created[0].vacuumed is True


def test_product_maintenance_budget_enforcement_deletes_operator_and_external_cache(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    runs_dir = tmp_path / ".runtime-cache" / "runs"
    logs_dir = tmp_path / ".runtime-cache" / "logs"
    operator_temp = tmp_path / ".runtime-cache" / "operator" / "temp"
    external_temp = tmp_path / "external-cache" / "temp"
    operator_temp.mkdir(parents=True, exist_ok=True)
    external_temp.mkdir(parents=True, exist_ok=True)
    (operator_temp / "note.txt").write_text("x" * 200, encoding="utf-8")
    (external_temp / "bundle.json").write_text("x" * 200, encoding="utf-8")

    monkeypatch.setattr(cli.settings, "RUNS_DIR", runs_dir)
    monkeypatch.setattr(cli.settings, "LOGS_DIR", logs_dir)
    monkeypatch.setattr(cli.settings, "OPERATOR_ARTIFACTS_DIR", tmp_path / ".runtime-cache" / "operator")
    monkeypatch.setattr(cli.settings, "EXTERNAL_CACHE_DIR", tmp_path / "external-cache")
    monkeypatch.setattr(cli.settings, "MAINTENANCE_LOCK_PATH", tmp_path / "maintenance.lock")
    monkeypatch.setattr(cli.settings, "RUNS_KEEP_DAYS", 30)
    monkeypatch.setattr(cli.settings, "REPORTS_KEEP_DAYS", 30)
    monkeypatch.setattr(cli.settings, "LOG_RETENTION_DAYS", 14)
    monkeypatch.setattr(cli.settings, "CACHE_BUDGET_BYTES", 100)

    assert asyncio.run(cli._run_product_maintenance(["--apply"])) == 0
    output = capsys.readouterr().out

    assert "cache_budget_exceeded_by_bytes=" in output
    assert operator_temp.exists() is False
    assert external_temp.exists() is False


def test_product_maintenance_budget_exceeded_but_protected_records_note(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    runs_dir = tmp_path / ".runtime-cache" / "runs"
    logs_dir = tmp_path / ".runtime-cache" / "logs"
    operator_dir = tmp_path / ".runtime-cache" / "operator"
    operator_dir.mkdir(parents=True, exist_ok=True)
    (operator_dir / "keep.patch").write_text("x" * 200, encoding="utf-8")

    monkeypatch.setattr(cli.settings, "RUNS_DIR", runs_dir)
    monkeypatch.setattr(cli.settings, "LOGS_DIR", logs_dir)
    monkeypatch.setattr(cli.settings, "OPERATOR_ARTIFACTS_DIR", operator_dir)
    monkeypatch.setattr(cli.settings, "EXTERNAL_CACHE_DIR", tmp_path / "external-cache")
    monkeypatch.setattr(cli.settings, "MAINTENANCE_LOCK_PATH", tmp_path / "maintenance.lock")
    monkeypatch.setattr(cli.settings, "RUNS_KEEP_DAYS", 30)
    monkeypatch.setattr(cli.settings, "REPORTS_KEEP_DAYS", 30)
    monkeypatch.setattr(cli.settings, "LOG_RETENTION_DAYS", 14)
    monkeypatch.setattr(cli.settings, "CACHE_BUDGET_BYTES", 100)

    assert asyncio.run(cli._run_product_maintenance(["--dry-run"])) == 0
    output = capsys.readouterr().out

    assert "budget_exceeded_but_protected" in output
