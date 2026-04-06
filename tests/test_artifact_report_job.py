import json
from datetime import datetime, timedelta, timezone

from dealwatch.jobs.artifact_report import ArtifactReportJob


def _write_ndjson(path, entries) -> None:
    lines = [json.dumps(entry) for entry in entries]
    content = "\n".join(lines)
    if content:
        content += "\n"
    path.write_text(content, encoding="utf-8")


def _make_run_dir(base, date_value) -> str:
    run_dir = base / date_value.strftime("%Y-%m-%d")
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def test_artifact_report_job_generates(tmp_path) -> None:
    runs_dir = tmp_path / "runs"
    output_dir = tmp_path / "reports"
    now = datetime.now(timezone.utc).date()

    day1 = _make_run_dir(runs_dir, now)
    day2 = _make_run_dir(runs_dir, now - timedelta(days=1))

    _write_ndjson(
        day1 / "failures_index.ndjson",
        [
            {"store_id": "weee", "reason": "parse", "url": "https://example.com/a"},
            {"store_id": "weee", "reason": "parse", "url": "https://example.com/b"},
        ],
    )
    _write_ndjson(
        day2 / "failures_index.ndjson",
        [
            {"store_id": "ttm", "reason": "timeout", "url": "https://example.com/c"},
        ],
    )
    _write_ndjson(
        day1 / "blocked_index.ndjson",
        [
            {"keyword": "access denied", "url": "https://example.com/a"},
            {"keyword": "access denied", "url": "https://example.com/b"},
        ],
    )
    _write_ndjson(
        day2 / "blocked_index.ndjson",
        [
            {"keyword": "captcha", "url": "https://example.com/c"},
        ],
    )

    job = ArtifactReportJob(
        runs_dir=runs_dir,
        output_dir=output_dir,
        lookback_days=7,
        top_k=1,
    )
    html_path = job.run()

    assert html_path is not None
    assert output_dir.exists() is True

    json_files = list(output_dir.glob("artifact_report_*.json"))
    html_files = list(output_dir.glob("artifact_report_*.html"))
    assert json_files
    assert html_files

    payload = json.loads(json_files[0].read_text(encoding="utf-8"))
    assert payload["totals"]["failures"] == 3
    assert payload["totals"]["blocked"] == 3
    assert payload["top_stores"][0]["key"] == "weee"
    assert payload["top_stores"][0]["count"] == 2
    assert payload["top_reasons"][0]["key"] == "parse"
    assert payload["top_keywords"][0]["key"] == "access denied"
    assert payload["top_keywords"][0]["count"] == 2
    assert len(payload["per_day"]) == 2


def test_artifact_report_job_missing_runs_dir(tmp_path) -> None:
    job = ArtifactReportJob(runs_dir=tmp_path / "missing", output_dir=tmp_path / "reports")
    assert job.run() is None


def test_artifact_report_job_no_recent_data(tmp_path) -> None:
    runs_dir = tmp_path / "runs"
    output_dir = tmp_path / "reports"

    old_date = datetime.now(timezone.utc).date() - timedelta(days=10)
    day_old = _make_run_dir(runs_dir, old_date)
    _write_ndjson(day_old / "failures_index.ndjson", [{"store_id": "weee"}])

    job = ArtifactReportJob(
        runs_dir=runs_dir,
        output_dir=output_dir,
        lookback_days=1,
        top_k=3,
    )
    assert job.run() is None


def test_artifact_report_job_invalid_index_line(tmp_path) -> None:
    runs_dir = tmp_path / "runs"
    output_dir = tmp_path / "reports"
    day = _make_run_dir(runs_dir, datetime.now(timezone.utc).date())
    (day / "failures_index.ndjson").write_text("invalid\n", encoding="utf-8")

    job = ArtifactReportJob(
        runs_dir=runs_dir,
        output_dir=output_dir,
        lookback_days=3,
        top_k=0,
    )
    html_path = job.run()

    assert html_path is not None
    json_files = list(output_dir.glob("artifact_report_*.json"))
    assert json_files
    payload = json.loads(json_files[0].read_text(encoding="utf-8"))
    assert payload["totals"]["failures"] == 0
    assert payload["totals"]["blocked"] == 0


def test_artifact_report_job_str_paths_and_parse(tmp_path) -> None:
    runs_dir = tmp_path / "runs"
    output_dir = tmp_path / "reports"
    day = _make_run_dir(runs_dir, datetime.now(timezone.utc).date())
    _write_ndjson(day / "failures_index.ndjson", [{"store_id": "weee"}])

    job = ArtifactReportJob(
        runs_dir=str(runs_dir),
        output_dir=str(output_dir),
        lookback_days=3,
        top_k=1,
    )
    html_path = job.run()

    assert html_path is not None
    assert job.runs_dir == runs_dir
    assert job.output_dir == output_dir
    assert ArtifactReportJob._parse_run_date("not-a-date") is None


def test_artifact_report_job_output_dir_failure(monkeypatch, tmp_path) -> None:
    runs_dir = tmp_path / "runs"
    output_dir = tmp_path / "reports"
    day = _make_run_dir(runs_dir, datetime.now(timezone.utc).date())
    _write_ndjson(day / "failures_index.ndjson", [{"store_id": "weee"}])

    original_mkdir = type(output_dir).mkdir

    def _mkdir(self, *args, **kwargs):
        if self == output_dir:
            raise OSError("boom")
        return original_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(type(output_dir), "mkdir", _mkdir, raising=False)

    job = ArtifactReportJob(runs_dir=runs_dir, output_dir=output_dir, lookback_days=3)
    assert job.run() is None


def test_artifact_report_job_write_failures(monkeypatch, tmp_path) -> None:
    runs_dir = tmp_path / "runs"
    output_dir = tmp_path / "reports"
    day = _make_run_dir(runs_dir, datetime.now(timezone.utc).date())
    _write_ndjson(day / "failures_index.ndjson", [{"store_id": "weee"}])

    original_write = type(output_dir).write_text

    def _write_text(self, *args, **kwargs):
        if self.suffix == ".json":
            raise OSError("no json")
        return original_write(self, *args, **kwargs)

    monkeypatch.setattr(type(output_dir), "write_text", _write_text, raising=False)

    job = ArtifactReportJob(runs_dir=runs_dir, output_dir=output_dir, lookback_days=3)
    assert job.run() is None


def test_artifact_report_job_html_write_failure(monkeypatch, tmp_path) -> None:
    runs_dir = tmp_path / "runs"
    output_dir = tmp_path / "reports"
    day = _make_run_dir(runs_dir, datetime.now(timezone.utc).date())
    _write_ndjson(day / "failures_index.ndjson", [{"store_id": "weee"}])

    original_write = type(output_dir).write_text

    def _write_text(self, *args, **kwargs):
        if self.suffix == ".html":
            raise OSError("no html")
        return original_write(self, *args, **kwargs)

    monkeypatch.setattr(type(output_dir), "write_text", _write_text, raising=False)

    job = ArtifactReportJob(runs_dir=runs_dir, output_dir=output_dir, lookback_days=3)
    assert job.run() is None


def test_artifact_report_job_load_index_os_error(monkeypatch, tmp_path) -> None:
    runs_dir = tmp_path / "runs"
    day = _make_run_dir(runs_dir, datetime.now(timezone.utc).date())
    index_path = day / "failures_index.ndjson"
    index_path.write_text("{\"store_id\":\"weee\"}\\n", encoding="utf-8")

    def _raise(*args, **kwargs):
        raise OSError("boom")

    monkeypatch.setattr(type(index_path), "read_text", _raise, raising=False)

    job = ArtifactReportJob(runs_dir=runs_dir)
    entries = job._load_index(index_path)
    assert entries == []


def test_artifact_report_job_cli_main(monkeypatch, tmp_path) -> None:
    runs_dir = tmp_path / "runs"
    output_dir = tmp_path / "reports"
    day = _make_run_dir(runs_dir, datetime.now(timezone.utc).date())
    _write_ndjson(day / "failures_index.ndjson", [{"store_id": "weee"}])

    def _run(self):
        return output_dir / "artifact_report_test.html"

    monkeypatch.setattr(ArtifactReportJob, "run", _run)
    monkeypatch.setenv("PYTHONHASHSEED", "0")
    import sys

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "artifact_report",
            "--days",
            "7",
            "--top",
            "3",
            "--runs-dir",
            str(runs_dir),
            "--output-dir",
            str(output_dir),
        ],
    )

    from dealwatch.jobs import artifact_report

    try:
        artifact_report.main()
    except SystemExit as exc:
        assert exc.code == 0
