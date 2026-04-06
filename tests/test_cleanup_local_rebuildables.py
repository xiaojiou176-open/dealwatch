from __future__ import annotations

from pathlib import Path

import scripts.cleanup_local_rebuildables as cleanup_script


def _touch(path: Path, *, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_collect_targets_respects_default_and_heavy(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cleanup_script, "ROOT", tmp_path)
    _touch(tmp_path / ".pytest_cache" / "state")
    _touch(tmp_path / ".runtime-cache" / "operator" / "temp" / "note.txt")
    _touch(tmp_path / "build" / "lib" / "dealwatch.py")
    _touch(tmp_path / "frontend" / "dist" / "index.html")
    _touch(tmp_path / ".venv" / "pyvenv.cfg")
    _touch(tmp_path / "frontend" / "node_modules" / ".bin" / "vite")
    _touch(tmp_path / "frontend" / ".pnpm-store" / "v10" / "index")
    _touch(tmp_path / ".pnpm-store" / "v10" / "keep")

    default_targets = cleanup_script.collect_targets(include_heavy=False)
    heavy_targets = cleanup_script.collect_targets(include_heavy=True)

    default_paths = {target.rel_path for target in default_targets}
    heavy_paths = {target.rel_path for target in heavy_targets}

    assert ".pytest_cache" in default_paths
    assert "build" in default_paths
    assert ".venv" not in default_paths
    assert ".venv" in heavy_paths
    assert "frontend/node_modules" in heavy_paths
    assert "frontend/.pnpm-store" in heavy_paths
    assert ".pnpm-store" not in heavy_paths


def test_apply_cleanup_removes_only_selected_targets(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cleanup_script, "ROOT", tmp_path)
    _touch(tmp_path / ".pytest_cache" / "state")
    _touch(tmp_path / ".runtime-cache" / "operator" / "temp" / "note.txt")
    _touch(tmp_path / ".runtime-cache" / "operator" / "keep" / "proof.json")
    _touch(tmp_path / "build" / "lib" / "dealwatch.py")
    _touch(tmp_path / "frontend" / "dist" / "index.html")
    _touch(tmp_path / ".venv" / "pyvenv.cfg")
    _touch(tmp_path / "frontend" / "node_modules" / ".bin" / "vite")
    _touch(tmp_path / "frontend" / ".pnpm-store" / "v10" / "index")
    _touch(tmp_path / ".pnpm-store" / "v10" / "keep")

    default_targets = cleanup_script.collect_targets(include_heavy=False)
    cleanup_script.apply_cleanup(default_targets)
    assert (tmp_path / ".pytest_cache").exists() is False
    assert (tmp_path / ".runtime-cache" / "operator" / "temp").exists() is False
    assert (tmp_path / "build").exists() is False
    assert (tmp_path / "frontend" / "dist").exists() is False
    assert (tmp_path / ".venv").exists() is True
    assert (tmp_path / "frontend" / ".pnpm-store").exists() is True
    assert (tmp_path / ".runtime-cache" / "operator" / "keep").exists() is True

    heavy_targets = cleanup_script.collect_targets(include_heavy=True)
    cleanup_script.apply_cleanup(heavy_targets)
    assert (tmp_path / ".venv").exists() is False
    assert (tmp_path / "frontend" / "node_modules").exists() is False
    assert (tmp_path / "frontend" / ".pnpm-store").exists() is False
    assert (tmp_path / ".pnpm-store").exists() is True
