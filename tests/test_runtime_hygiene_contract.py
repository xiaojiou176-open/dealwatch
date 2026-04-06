from __future__ import annotations

import json
from pathlib import Path

import scripts.audit_runtime_footprint as audit_script
import scripts.cleanup_local_rebuildables as cleanup_script


def _touch(path: Path, *, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _entry_map(entries: list[audit_script.AuditEntry]) -> dict[str, audit_script.AuditEntry]:
    return {entry.path: entry for entry in entries}


def test_collect_entries_classifies_repo_local_targets(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(audit_script, "ROOT", tmp_path)
    _touch(tmp_path / ".venv" / "pyvenv.cfg", text="venv")
    _touch(tmp_path / ".runtime-cache" / "logs" / "dealwatch.log", text="log")
    _touch(
        tmp_path / ".runtime-cache" / "runs" / "watch-tasks" / "task-1" / "summary.json",
        text="{}",
    )
    _touch(tmp_path / ".runtime-cache" / "browser-identity" / "index.html", text="<html></html>")
    _touch(tmp_path / ".runtime-cache" / "operator" / "browser-debug" / "bundle.json", text="{}")
    _touch(tmp_path / "build" / "lib" / "dealwatch.py", text="compiled")
    _touch(tmp_path / "frontend" / "dist" / "index.html", text="<html></html>")
    _touch(tmp_path / ".pytest_cache" / "state", text="cache")
    _touch(tmp_path / ".legacy-runtime" / "data" / "dealwatch.db", text="legacy")

    entries, missing_count = audit_script.collect_entries()
    entry_map = _entry_map(entries)

    assert ".venv" in entry_map
    assert entry_map[".venv"].classification == "dependency_rebuildable"
    assert entry_map[".venv"].cleanup_lane == "cleanup_local_rebuildables_heavy"

    assert ".runtime-cache/logs" in entry_map
    assert entry_map[".runtime-cache/logs"].classification == "runtime_evidence"
    assert entry_map[".runtime-cache/logs"].cleanup_lane == "maintenance"

    assert ".runtime-cache/runs" in entry_map
    assert entry_map[".runtime-cache/runs"].classification == "runtime_evidence"
    assert entry_map[".runtime-cache/runs"].cleanup_lane == "maintenance"

    assert ".runtime-cache/browser-identity" in entry_map
    assert entry_map[".runtime-cache/browser-identity"].classification == "operator_evidence"
    assert entry_map[".runtime-cache/browser-identity"].cleanup_lane == "keep"

    assert ".runtime-cache/operator" in entry_map
    assert entry_map[".runtime-cache/operator"].classification == "operator_evidence"
    assert entry_map[".runtime-cache/operator"].cleanup_lane == "keep"

    assert "build" in entry_map
    assert entry_map["build"].classification == "disposable_generated"
    assert entry_map["build"].cleanup_lane == "cleanup_local_rebuildables"

    assert "frontend/dist" in entry_map
    assert entry_map["frontend/dist"].classification == "disposable_generated"
    assert entry_map["frontend/dist"].cleanup_lane == "cleanup_local_rebuildables"

    assert ".legacy-runtime" in entry_map
    assert entry_map[".legacy-runtime"].classification == "legacy_bridge"
    assert entry_map[".legacy-runtime"].cleanup_lane == "keep"

    assert missing_count == 2


def test_build_summary_and_render_json_handle_missing_targets(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(audit_script, "ROOT", tmp_path)
    external_cache = tmp_path / ".external-cache"
    monkeypatch.setattr(audit_script, "EXTERNAL_CACHE_DIR", external_cache)
    monkeypatch.setattr(audit_script, "PERSISTENT_BROWSER_ROOT", external_cache / "browser" / "chrome-user-data")
    _touch(tmp_path / "build" / "artifact.txt", text="artifact")

    summary = audit_script.build_summary()

    assert summary.matched_count == 1
    assert summary.missing_count == len(audit_script.AUDIT_TARGETS) - 1
    assert summary.classification_totals["disposable_generated"] > 0
    assert summary.classification_totals["dependency_rebuildable"] == 0
    assert summary.entries[0].path == "build"

    payload = json.loads(audit_script.render_json(summary))
    assert payload["scope"] == "repo-owned-internal-and-external"
    assert payload["matched_count"] == 1
    assert payload["missing_count"] == len(audit_script.AUDIT_TARGETS) - 1
    assert payload["entries"][0]["path"] == "build"
    assert payload["entries"][0]["cleanup_lane"] == "cleanup_local_rebuildables"


def test_cleanup_local_rebuildables_defaults_include_build(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cleanup_script, "ROOT", tmp_path)
    _touch(tmp_path / ".pytest_cache" / "state")
    _touch(tmp_path / ".runtime-cache" / "operator" / "temp" / "note.txt")
    _touch(tmp_path / ".runtime-cache" / "browser-identity" / "index.html")
    _touch(tmp_path / "build" / "lib" / "dealwatch.py")
    _touch(tmp_path / "frontend" / "dist" / "index.html")
    _touch(tmp_path / ".runtime-cache" / "logs" / "dealwatch.log")
    _touch(tmp_path / ".runtime-cache" / "runs" / "watch-tasks" / "run.json")
    _touch(tmp_path / ".pnpm-store" / "v10" / "keep")
    _touch(tmp_path / ".venv" / "pyvenv.cfg")
    _touch(tmp_path / "frontend" / "node_modules" / ".bin" / "vite")

    default_targets = cleanup_script.collect_targets(include_heavy=False)
    heavy_targets = cleanup_script.collect_targets(include_heavy=True)

    default_paths = {target.rel_path for target in default_targets}
    heavy_paths = {target.rel_path for target in heavy_targets}

    assert "build" in default_paths
    assert ".pytest_cache" in default_paths
    assert "frontend/dist" in default_paths
    assert ".runtime-cache/operator/temp" in default_paths
    assert ".runtime-cache/browser-identity" not in default_paths
    assert ".pnpm-store" not in default_paths
    assert ".runtime-cache/logs" not in default_paths
    assert ".runtime-cache/runs" not in default_paths
    assert ".venv" in heavy_paths
    assert "frontend/node_modules" in heavy_paths


def test_collect_entries_includes_external_cache_dir_when_present(monkeypatch, tmp_path: Path) -> None:
    external_cache = tmp_path / ".external-cache"
    _touch(external_cache / "browser" / "bundle.json", text="{}")
    _touch(external_cache / "browser" / "chrome-user-data" / "Local State", text="{}")
    monkeypatch.setattr(audit_script, "ROOT", tmp_path)
    monkeypatch.setattr(audit_script, "EXTERNAL_CACHE_DIR", external_cache)
    monkeypatch.setattr(audit_script, "PERSISTENT_BROWSER_ROOT", external_cache / "browser" / "chrome-user-data")

    entries, _missing_count = audit_script.collect_entries()
    entry_map = _entry_map(entries)

    assert str(external_cache) in entry_map
    assert entry_map[str(external_cache)].classification == "external_owned_cache"
    assert str(external_cache / "browser" / "chrome-user-data") in entry_map
    assert entry_map[str(external_cache / "browser" / "chrome-user-data")].classification == "persistent_browser_profile"
    assert entry_map[str(external_cache / "browser" / "chrome-user-data")].cleanup_lane == "keep"
