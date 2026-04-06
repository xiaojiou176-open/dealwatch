import json
from pathlib import Path

import pytest

from dealwatch.jobs.failure_replay import FailureReplayJob


@pytest.mark.asyncio
async def test_failure_replay_job_with_fetcher(tmp_path) -> None:
    run_dir = tmp_path / "runs" / "2026-02-03"
    run_dir.mkdir(parents=True)

    archive_dir = run_dir / "failures" / "weee"
    archive_dir.mkdir(parents=True)
    archived_html = archive_dir / "a.html"
    archived_html.write_text("<html><body>old</body></html>", encoding="utf-8")

    index_path = run_dir / "failures_index.ndjson"
    entry = {
        "store_id": "weee",
        "url": "https://example.com/p1",
        "reason": "parse",
        "captured_at": "20260203_000000",
        "html_path": "failures/weee/a.html",
        "screenshot_path": "failures/weee/a.png",
    }
    index_path.write_text(json.dumps(entry) + "\n", encoding="utf-8")

    async def _fetch(url: str) -> str:
        return "<html><body>new</body></html>"

    job = FailureReplayJob(runs_dir=tmp_path / "runs", fetcher=_fetch)
    output_dir = await job.run("2026-02-03")

    assert output_dir is not None
    assert (output_dir / "replay_index.md").exists() is True
    assert (output_dir / "replay_index.ndjson").exists() is True
    assert (output_dir / "replay_report.html").exists() is True
    report_json = output_dir / "replay_report.json"
    assert report_json.exists() is True
    payload = json.loads(report_json.read_text(encoding="utf-8"))
    assert payload["total_entries"] == 1
    assert payload["status_counts"].get("replayed") == 1
    assert payload["top_domains"][0]["domain"] == "example.com"
    assert any(path.name.startswith("diff_") for path in output_dir.iterdir())
    assert any(path.name.startswith("current_") for path in output_dir.iterdir())
    html_report = (output_dir / "replay_report.html").read_text(encoding="utf-8")
    assert "Diff Excerpt" in html_report


@pytest.mark.asyncio
async def test_failure_replay_job_missing_dir(tmp_path) -> None:
    job = FailureReplayJob(runs_dir=tmp_path / "runs")
    result = await job.run("2026-02-03")
    assert result is None


@pytest.mark.asyncio
async def test_failure_replay_job_invalid_index_line(tmp_path) -> None:
    run_dir = tmp_path / "runs" / "2026-02-03"
    run_dir.mkdir(parents=True)
    index_path = run_dir / "failures_index.ndjson"
    index_path.write_text("invalid\n", encoding="utf-8")

    async def _fetch(url: str) -> str:
        return "<html></html>"

    job = FailureReplayJob(runs_dir=tmp_path / "runs", fetcher=_fetch)
    result = await job.run("2026-02-03")
    assert result is None


@pytest.mark.asyncio
async def test_failure_replay_retry_budget_exhausted(tmp_path) -> None:
    run_dir = tmp_path / "runs" / "2026-02-03"
    run_dir.mkdir(parents=True)

    index_path = run_dir / "failures_index.ndjson"
    entry = {
        "store_id": "weee",
        "url": "https://example.com/p1",
        "reason": "parse",
        "captured_at": "20260203_000000",
        "html_path": "failures/weee/a.html",
    }
    index_path.write_text(json.dumps(entry) + "\n", encoding="utf-8")

    calls = {"count": 0}

    async def _fetch(url: str) -> str:
        calls["count"] += 1
        raise RuntimeError("boom")

    job = FailureReplayJob(
        runs_dir=tmp_path / "runs",
        fetcher=_fetch,
        max_retries=2,
        retry_budget=1,
    )
    output_dir = await job.run("2026-02-03")

    assert output_dir is not None
    index_json = output_dir / "replay_index.ndjson"
    payload = json.loads(index_json.read_text(encoding="utf-8").splitlines()[0])
    assert payload["status"] == "budget_exhausted"
    assert calls["count"] >= 1

    report_json = output_dir / "replay_report.json"
    summary = json.loads(report_json.read_text(encoding="utf-8"))
    assert summary["status_counts"].get("budget_exhausted") == 1


def test_failure_replay_build_report_and_write(tmp_path) -> None:
    output_dir = tmp_path / "replays"
    output_dir.mkdir(parents=True, exist_ok=True)

    job = FailureReplayJob(runs_dir=str(tmp_path / "runs"), retry_budget=None)
    assert isinstance(job.runs_dir, Path)
    assert job._retry_budget is None
    results = [
        {
            "url": "https://example.com/a",
            "status": "replayed",
            "diff_lines": "bad",
            "captured_at": "20260203_000000",
            "diff_path": "diff_a.txt",
            "current_html": "current_a.html",
            "archive_html": "archive_a.html",
        },
        {
            "url": "https://example.com/b",
            "status": "fetch_failed",
            "diff_lines": "bad",
            "captured_at": "20260203_000001",
            "diff_path": "diff_b.txt",
            "current_html": "current_b.html",
            "archive_html": "archive_b.html",
        },
    ]

    report_path = job._write_report(output_dir, results)
    assert report_path.exists() is True
    report_json = output_dir / "replay_report.json"
    payload = json.loads(report_json.read_text(encoding="utf-8"))
    assert payload["total_entries"] == 2
    assert payload["status_counts"]["replayed"] == 1
    assert payload["status_counts"]["fetch_failed"] == 1
    assert payload["top_domains"][0]["domain"] == "example.com"
    assert payload["diff_lines"]["max"] >= payload["diff_lines"]["min"]
    assert payload["retry_budget_initial"] is None


def test_failure_replay_resolve_run_dir_latest(tmp_path) -> None:
    runs_dir = tmp_path / "runs"
    (runs_dir / "2026-02-02").mkdir(parents=True, exist_ok=True)
    (runs_dir / "2026-02-03").mkdir(parents=True, exist_ok=True)

    job = FailureReplayJob(runs_dir=runs_dir)
    resolved = job._resolve_run_dir(None)
    assert resolved is not None
    assert resolved.name == "2026-02-03"


def test_failure_replay_write_indices_error(monkeypatch, tmp_path) -> None:
    output_dir = tmp_path / "replays"
    output_dir.mkdir(parents=True, exist_ok=True)
    index_md = output_dir / "replay_index.md"
    index_json = output_dir / "replay_index.ndjson"

    job = FailureReplayJob(runs_dir=tmp_path / "runs")
    results = [{"url": "https://example.com", "status": "replayed"}]

    original_open = Path.open

    def _open(self, *args, **kwargs):
        if self.name in {"replay_index.md", "replay_index.ndjson"}:
            raise OSError("boom")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", _open)
    job._write_indices(results, index_md, index_json)


def test_failure_replay_resolve_archive_path(tmp_path) -> None:
    run_dir = tmp_path / "runs" / "2026-02-03"
    run_dir.mkdir(parents=True, exist_ok=True)
    archive_dir = run_dir / "failures"
    archive_dir.mkdir()
    file_path = archive_dir / "a.html"
    file_path.write_text("<html></html>", encoding="utf-8")

    resolved = FailureReplayJob._resolve_archive_path(run_dir, "failures/a.html")
    assert resolved == file_path
    assert FailureReplayJob._resolve_archive_path(run_dir, str(file_path)) is None
    assert FailureReplayJob._resolve_archive_path(run_dir, "../secret.txt") is None
    assert FailureReplayJob._resolve_archive_path(run_dir, "") is None


@pytest.mark.asyncio
async def test_failure_replay_fetch_with_retry_success(tmp_path) -> None:
    job = FailureReplayJob(runs_dir=tmp_path / "runs", max_retries=2, retry_budget=2)
    calls = {"count": 0}

    async def _fetch(url: str) -> str:
        calls["count"] += 1
        if calls["count"] < 2:
            raise RuntimeError("boom")
        return "<html></html>"

    content = await job._fetch_with_retry("https://example.com", _fetch)
    assert "<html>" in content


@pytest.mark.asyncio
async def test_failure_replay_fetch_with_retry_no_retry(tmp_path) -> None:
    job = FailureReplayJob(runs_dir=tmp_path / "runs", max_retries=0, retry_budget=1)

    async def _fetch(url: str) -> str:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await job._fetch_with_retry("https://example.com", _fetch)


@pytest.mark.asyncio
async def test_failure_replay_entries_skip_invalid(tmp_path) -> None:
    run_dir = tmp_path / "runs" / "2026-02-03"
    run_dir.mkdir(parents=True, exist_ok=True)
    output_dir = run_dir / "replays"
    output_dir.mkdir(parents=True, exist_ok=True)

    job = FailureReplayJob(runs_dir=tmp_path / "runs")

    async def _fetch(url: str) -> str:
        return "<html></html>"

    results = await job._replay_entries(
        entries=[{"url": ""}, {}],
        run_dir=run_dir,
        output_dir=output_dir,
        fetcher=_fetch,
    )
    assert results == []


def test_failure_replay_resolve_run_dir_missing(tmp_path) -> None:
    job = FailureReplayJob(runs_dir=tmp_path / "runs")
    assert job._resolve_run_dir("2026-02-03") is None


@pytest.mark.asyncio
async def test_failure_replay_run_with_playwright_dummy(monkeypatch, tmp_path) -> None:
    run_dir = tmp_path / "runs" / "2026-02-03"
    run_dir.mkdir(parents=True, exist_ok=True)
    index_path = run_dir / "failures_index.ndjson"
    index_path.write_text(
        json.dumps(
            {
                "url": "https://example.com/a",
                "html_path": "failures/a.html",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    class _DummyClient:
        def __init__(self, *args, **kwargs):
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def fetch_page(self, url: str, return_page: bool = False):
            return "<html></html>"

    monkeypatch.setattr("dealwatch.jobs.failure_replay.PlaywrightClient", _DummyClient)

    job = FailureReplayJob(runs_dir=tmp_path / "runs", build_report=False)
    output_dir = await job.run("2026-02-03")

    assert output_dir is not None
    assert (output_dir / "replay_index.ndjson").exists() is True


@pytest.mark.asyncio
async def test_failure_replay_replay_single_errors(monkeypatch, tmp_path) -> None:
    run_dir = tmp_path / "runs" / "2026-02-03"
    run_dir.mkdir(parents=True, exist_ok=True)
    output_dir = run_dir / "replays"
    output_dir.mkdir(parents=True, exist_ok=True)

    job = FailureReplayJob(runs_dir=tmp_path / "runs", max_retries=1, retry_budget=1)

    async def _fetch(url: str) -> str:
        raise RuntimeError("boom")

    result = await job._replay_single({}, run_dir, output_dir, _fetch)
    assert result is None

    entry = {"url": "https://example.com/a", "html_path": "failures/a.html"}

    def _raise_read(*args, **kwargs):
        raise OSError("boom")

    monkeypatch.setattr(Path, "read_text", _raise_read)

    async def _fetch_ok(url: str) -> str:
        return "<html><body>ok</body></html>"

    def _raise_write(self, *args, **kwargs):
        raise OSError("boom")

    monkeypatch.setattr(Path, "write_text", _raise_write)
    result = await job._replay_single(entry, run_dir, output_dir, _fetch_ok)
    assert result is not None


@pytest.mark.asyncio
async def test_failure_replay_replay_single_runtime_error(tmp_path) -> None:
    run_dir = tmp_path / "runs" / "2026-02-03"
    run_dir.mkdir(parents=True, exist_ok=True)
    output_dir = run_dir / "replays"
    output_dir.mkdir(parents=True, exist_ok=True)

    job = FailureReplayJob(runs_dir=tmp_path / "runs", max_retries=1, retry_budget=1)

    async def _fetch(url: str) -> str:
        raise RuntimeError("boom")

    entry = {"url": "https://example.com/a", "html_path": ""}
    with pytest.raises(RuntimeError):
        await job._replay_single(entry, run_dir, output_dir, _fetch)


def test_failure_replay_cli_main(monkeypatch, tmp_path) -> None:
    runs_dir = tmp_path / "runs" / "2026-02-03"
    runs_dir.mkdir(parents=True, exist_ok=True)
    index_path = runs_dir / "failures_index.ndjson"
    index_path.write_text(
        json.dumps({"url": "https://example.com/a"}) + "\n",
        encoding="utf-8",
    )

    async def _run(self, run_date=None):
        return runs_dir / "replays"

    monkeypatch.setattr(FailureReplayJob, "run", _run)
    import sys

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "failure_replay",
            "--run-date",
            "2026-02-03",
            "--max",
            "1",
            "--concurrency",
            "1",
            "--retries",
            "0",
            "--retry-budget",
            "0",
            "--no-report",
            "--headless",
            "--proxy",
            "http://proxy:8080",
        ],
    )

    from dealwatch.jobs import failure_replay

    failure_replay.main()
