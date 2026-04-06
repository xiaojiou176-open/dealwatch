import json
from datetime import datetime, timezone
from pathlib import Path

from dealwatch.jobs.artifact_audit import ArtifactAuditJob


def _write_ndjson(path: Path, entries: list[dict]) -> None:
    content = "\n".join(json.dumps(entry) for entry in entries)
    if content:
        content += "\n"
    path.write_text(content, encoding="utf-8")


def _make_run_dir(base: Path, date_value: datetime.date) -> Path:
    run_dir = base / date_value.strftime("%Y-%m-%d")
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def test_artifact_audit_job_generates(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    output_dir = tmp_path / "reports"
    today = datetime.now(timezone.utc).date()

    run_dir = _make_run_dir(runs_dir, today)
    failure_dir = run_dir / "failures" / "weee"
    failure_dir.mkdir(parents=True, exist_ok=True)
    blocked_dir = run_dir / "blocked"
    blocked_dir.mkdir(parents=True, exist_ok=True)

    html_path = failure_dir / "a.html"
    html_path.write_text("<html></html>", encoding="utf-8")
    screenshot_path = failure_dir / "a.png"
    screenshot_path.write_text("png", encoding="utf-8")
    text_path = failure_dir / "a.txt"
    text_path.write_text("text", encoding="utf-8")
    meta_path = failure_dir / "a.json"
    meta_path.write_text("{}", encoding="utf-8")

    _write_ndjson(
        run_dir / "failures_index.ndjson",
        [
            {
                "url": "https://example.com/a",
                "html_path": str(html_path.relative_to(run_dir)),
                "screenshot_path": str(screenshot_path.relative_to(run_dir)),
                "text_path": str(text_path.relative_to(run_dir)),
                "meta_path": str(meta_path.relative_to(run_dir)),
            },
            {
                "url": "https://example.com/b",
                "html_path": "failures/weee/missing.html",
                "screenshot_path": "failures/weee/missing.png",
                "text_path": "failures/weee/missing.txt",
                "meta_path": "failures/weee/missing.json",
            },
        ],
    )
    _write_ndjson(
        run_dir / "blocked_index.ndjson",
        [
            {
                "url": "https://example.com/c",
                "content_path": "blocked/missing.html",
                "screenshot_path": "blocked/missing.png",
            }
        ],
    )

    job = ArtifactAuditJob(
        runs_dir=runs_dir,
        output_dir=output_dir,
        lookback_days=7,
        sample_limit=5,
    )
    html_report = job.run()

    assert html_report is not None
    json_files = list(output_dir.glob("artifact_audit_*.json"))
    assert json_files

    payload = json.loads(json_files[0].read_text(encoding="utf-8"))
    assert payload["totals"]["failures"] == 2
    assert payload["totals"]["blocked"] == 1
    assert payload["totals"]["missing"]["failure"]["html_path"] == 1
    assert payload["totals"]["missing"]["failure"]["text_path"] == 1
    assert payload["totals"]["missing"]["blocked"]["content_path"] == 1
    assert payload["samples"]


def test_artifact_audit_job_missing_runs_dir(tmp_path: Path) -> None:
    job = ArtifactAuditJob(runs_dir=tmp_path / "missing")
    assert job.run() is None


def test_artifact_audit_job_invalid_lines(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    output_dir = tmp_path / "reports"
    run_dir = _make_run_dir(runs_dir, datetime.now(timezone.utc).date())
    (run_dir / "failures_index.ndjson").write_text("invalid\n", encoding="utf-8")

    job = ArtifactAuditJob(runs_dir=runs_dir, output_dir=output_dir, lookback_days=3)
    html_report = job.run()

    assert html_report is not None
    json_files = list(output_dir.glob("artifact_audit_*.json"))
    payload = json.loads(json_files[0].read_text(encoding="utf-8"))
    assert payload["totals"]["invalid_lines"]["failure"] == 1


def test_artifact_audit_job_output_write_failure(monkeypatch, tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    output_dir = tmp_path / "reports"
    run_dir = _make_run_dir(runs_dir, datetime.now(timezone.utc).date())
    _write_ndjson(run_dir / "failures_index.ndjson", [{"url": "https://example.com"}])

    original_write = Path.write_text

    def _write_text(self, *args, **kwargs):
        if self.suffix == ".json":
            raise OSError("boom")
        return original_write(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", _write_text)

    job = ArtifactAuditJob(runs_dir=runs_dir, output_dir=output_dir)
    assert job.run() is None


def test_artifact_audit_job_parse_run_date_invalid() -> None:
    assert ArtifactAuditJob._parse_run_date("not-a-date") is None


def test_artifact_audit_job_str_paths_and_absolute_resolution(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    output_dir = tmp_path / "reports"
    run_dir = _make_run_dir(runs_dir, datetime.now(timezone.utc).date())

    abs_path = tmp_path / "abs.html"
    abs_path.write_text("<html></html>", encoding="utf-8")

    _write_ndjson(
        run_dir / "failures_index.ndjson",
        [
            {
                "url": "https://example.com",
                "html_path": str(abs_path),
                "screenshot_path": "",
                "text_path": "",
                "meta_path": "",
            }
        ],
    )

    job = ArtifactAuditJob(runs_dir=str(runs_dir), output_dir=str(output_dir), lookback_days=3)
    html_report = job.run()

    assert html_report is not None
    assert job.runs_dir == runs_dir
    assert job.output_dir == output_dir
    assert ArtifactAuditJob._resolve_entry_path(run_dir, str(abs_path)) == abs_path


def test_artifact_audit_job_output_dir_failure(monkeypatch, tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    output_dir = tmp_path / "reports"
    run_dir = _make_run_dir(runs_dir, datetime.now(timezone.utc).date())
    _write_ndjson(run_dir / "failures_index.ndjson", [{"url": "https://example.com"}])

    original_mkdir = Path.mkdir

    def _mkdir(self, *args, **kwargs):
        if self == output_dir:
            raise OSError("boom")
        return original_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", _mkdir)

    job = ArtifactAuditJob(runs_dir=runs_dir, output_dir=output_dir)
    assert job.run() is None


def test_artifact_audit_job_html_write_failure(monkeypatch, tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    output_dir = tmp_path / "reports"
    run_dir = _make_run_dir(runs_dir, datetime.now(timezone.utc).date())
    _write_ndjson(run_dir / "failures_index.ndjson", [{"url": "https://example.com"}])

    original_write = Path.write_text

    def _write_text(self, *args, **kwargs):
        if self.suffix == ".html":
            raise OSError("boom")
        return original_write(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", _write_text)

    job = ArtifactAuditJob(runs_dir=runs_dir, output_dir=output_dir)
    assert job.run() is None


def test_artifact_audit_job_sample_limit_zero(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    output_dir = tmp_path / "reports"
    run_dir = _make_run_dir(runs_dir, datetime.now(timezone.utc).date())
    _write_ndjson(
        run_dir / "failures_index.ndjson",
        [
            {
                "url": "https://example.com",
                "html_path": "missing.html",
                "screenshot_path": "missing.png",
                "text_path": "missing.txt",
                "meta_path": "missing.json",
            }
        ],
    )

    job = ArtifactAuditJob(runs_dir=runs_dir, output_dir=output_dir, sample_limit=0)
    html_report = job.run()

    assert html_report is not None
    json_files = list(output_dir.glob("artifact_audit_*.json"))
    payload = json.loads(json_files[0].read_text(encoding="utf-8"))
    assert payload["samples"] == []


def test_artifact_audit_job_no_valid_runs(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    (runs_dir / "note.txt").write_text("x", encoding="utf-8")
    (runs_dir / "not-a-date").mkdir()

    job = ArtifactAuditJob(runs_dir=runs_dir, output_dir=tmp_path / "reports", lookback_days=3)
    assert job.run() is None


def test_artifact_audit_job_empty_lines_and_os_error(monkeypatch, tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    output_dir = tmp_path / "reports"
    run_dir = _make_run_dir(runs_dir, datetime.now(timezone.utc).date())
    index_path = run_dir / "failures_index.ndjson"
    index_path.write_text("\n\n", encoding="utf-8")

    def _raise(*args, **kwargs):
        raise OSError("boom")

    monkeypatch.setattr(Path, "read_text", _raise)

    job = ArtifactAuditJob(runs_dir=runs_dir, output_dir=output_dir, lookback_days=3)
    html_report = job.run()

    assert html_report is not None


def test_artifact_audit_job_resolve_entry_path_empty() -> None:
    assert ArtifactAuditJob._resolve_entry_path(Path("/tmp"), "") is None


def test_artifact_audit_job_cli_main(monkeypatch, tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    output_dir = tmp_path / "reports"
    run_dir = _make_run_dir(runs_dir, datetime.now(timezone.utc).date())
    _write_ndjson(run_dir / "failures_index.ndjson", [{"url": "https://example.com"}])

    def _run(self):
        return output_dir / "artifact_audit_test.html"

    monkeypatch.setattr(ArtifactAuditJob, "run", _run)
    import sys

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "artifact_audit",
            "--days",
            "7",
            "--runs-dir",
            str(runs_dir),
            "--output-dir",
            str(output_dir),
            "--sample-limit",
            "2",
        ],
    )

    from dealwatch.jobs import artifact_audit

    try:
        artifact_audit.main()
    except SystemExit as exc:
        assert exc.code == 0
