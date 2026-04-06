import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dealwatch.jobs.run_index import RunIndexJob


def _write_ndjson(path: Path, entries: list[dict]) -> None:
    content = "\n".join(json.dumps(entry) for entry in entries)
    if content:
        content += "\n"
    path.write_text(content, encoding="utf-8")


def _make_run_dir(base: Path, date_value: datetime.date) -> Path:
    run_dir = base / date_value.strftime("%Y-%m-%d")
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _write_confirmed(run_dir: Path, store_id: str, confirmed: int, checked: int) -> None:
    payload = {
        "confirmed_count": confirmed,
        "total_checked": checked,
    }
    (run_dir / f"{store_id}_confirmed.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


def test_run_index_job_generates(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    reports_dir = runs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now(timezone.utc).date()
    run_today = _make_run_dir(runs_dir, today)
    run_yesterday = _make_run_dir(runs_dir, today - timedelta(days=1))

    _write_confirmed(run_today, "weee", 2, 10)
    _write_confirmed(run_today, "ttm", 1, 5)
    _write_confirmed(run_yesterday, "weee", 1, 4)

    _write_ndjson(
        run_today / "failures_index.ndjson",
        [
            {"store_id": "weee", "url": "https://example.com"},
            {"store_id": "ttm", "url": "https://example.com"},
        ],
    )
    _write_ndjson(run_yesterday / "blocked_index.ndjson", [{"keyword": "captcha"}])

    (reports_dir / "run_report_20260203_000000.html").write_text("<html></html>")
    (reports_dir / "artifact_report_20260203_000000.html").write_text("<html></html>")
    (reports_dir / "artifact_audit_20260203_000000.html").write_text("<html></html>")
    replay_dir = run_today / "replays"
    replay_dir.mkdir(parents=True, exist_ok=True)
    (replay_dir / "replay_report.html").write_text("<html></html>")

    job = RunIndexJob(runs_dir=runs_dir, lookback_days=7)
    html_path = job.run()

    assert html_path is not None
    json_path = runs_dir / "runs_index.json"
    assert json_path.exists() is True

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["totals"]["confirmed"] == 4
    assert payload["totals"]["checked"] == 19
    assert payload["totals"]["failures"] == 2
    assert payload["totals"]["blocked"] == 1
    assert payload["runs"][0]["date"] == today.isoformat()
    assert payload["reports"]["run_reports"]
    assert payload["reports"]["artifact_reports"]
    assert payload["reports"]["audit_reports"]
    assert payload["reports"]["replay_reports"]


def test_run_index_job_missing_runs_dir(tmp_path: Path) -> None:
    job = RunIndexJob(runs_dir=tmp_path / "missing")
    assert job.run() is None


def test_run_index_job_invalid_dirs_and_lines(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    (runs_dir / "not-a-date").mkdir()

    today = datetime.now(timezone.utc).date()
    run_today = _make_run_dir(runs_dir, today)
    _write_confirmed(run_today, "weee", 0, 0)
    (run_today / "failures_index.ndjson").write_text("invalid\n", encoding="utf-8")

    job = RunIndexJob(runs_dir=runs_dir, lookback_days=7)
    html_path = job.run()
    assert html_path is not None


def test_run_index_job_write_failure(monkeypatch, tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    run_today = _make_run_dir(runs_dir, datetime.now(timezone.utc).date())
    _write_confirmed(run_today, "weee", 1, 1)

    original_write = Path.write_text

    def _write_text(self, *args, **kwargs):
        if self.name == "runs_index.json":
            raise OSError("boom")
        return original_write(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", _write_text)

    job = RunIndexJob(runs_dir=runs_dir)
    assert job.run() is None


def test_run_index_job_parse_run_date_invalid() -> None:
    assert RunIndexJob._parse_run_date("bad") is None


def test_run_index_job_no_valid_runs(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    (runs_dir / "reports").mkdir()
    job = RunIndexJob(runs_dir=runs_dir, lookback_days=7)
    assert job.run() is None


def test_run_index_job_html_write_failure(monkeypatch, tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    run_today = _make_run_dir(runs_dir, datetime.now(timezone.utc).date())
    _write_confirmed(run_today, "weee", 1, 1)

    original_write = Path.write_text

    def _write_text(self, *args, **kwargs):
        if self.name == "index.html":
            raise OSError("boom")
        return original_write(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", _write_text)

    job = RunIndexJob(runs_dir=runs_dir)
    assert job.run() is None


def test_run_index_job_report_limits(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    reports_dir = runs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    for idx in range(7):
        (reports_dir / f"run_report_20260203_00000{idx}.html").write_text("<html></html>")
        (reports_dir / f"artifact_report_20260203_00000{idx}.html").write_text("<html></html>")
        (reports_dir / f"artifact_audit_20260203_00000{idx}.html").write_text("<html></html>")

    run_today = _make_run_dir(runs_dir, datetime.now(timezone.utc).date())
    _write_confirmed(run_today, "weee", 1, 1)

    job = RunIndexJob(runs_dir=runs_dir, lookback_days=7)
    html_path = job.run()
    assert html_path is not None

    payload = json.loads((runs_dir / "runs_index.json").read_text(encoding="utf-8"))
    assert len(payload["reports"]["run_reports"]) == 5
    assert len(payload["reports"]["artifact_reports"]) == 5
    assert len(payload["reports"]["audit_reports"]) == 5


def test_run_index_job_safe_rel_path(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    reports_dir = runs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    run_today = _make_run_dir(runs_dir, datetime.now(timezone.utc).date())
    _write_confirmed(run_today, "weee", 1, 1)

    job = RunIndexJob(runs_dir=runs_dir, lookback_days=7)
    rel = job._safe_rel_path(reports_dir / "run_report_20260203_000000.html")
    assert rel.startswith("reports/")

    outside = job._safe_rel_path(tmp_path / "outside.html")
    assert str(outside).endswith("outside.html")
