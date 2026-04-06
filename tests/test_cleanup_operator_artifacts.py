from __future__ import annotations

import os
from pathlib import Path

import scripts.cleanup_operator_artifacts as cleanup_script


def _touch(path: Path, *, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_gif_dir(base: Path, name: str, *, age_offset: int) -> Path:
    path = base / ".runtime-cache" / "operator" / name
    path.mkdir(parents=True, exist_ok=True)
    for index in range(1, 4):
        _touch(path / f"compare-preview-{index:02d}.png")
    timestamp = 1_700_000_000 + age_offset
    for child in path.iterdir():
        os.utime(child, (timestamp, timestamp))
    os.utime(path, (timestamp, timestamp))
    return path


def test_collect_decisions_keeps_latest_gif_dir(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cleanup_script, "ROOT", tmp_path)
    monkeypatch.setattr(cleanup_script, "ARTIFACTS_ROOT", tmp_path / ".runtime-cache" / "operator")

    _make_gif_dir(tmp_path, "gif-frames", age_offset=1)
    _make_gif_dir(tmp_path, "gif-frames-final2", age_offset=2)
    _touch(tmp_path / ".runtime-cache" / "operator" / "gemini-audit" / "full-audit.json", text="{}")
    _touch(tmp_path / ".runtime-cache" / "operator" / "2026-03-27-release-v0.1.2.md")

    decisions = cleanup_script.collect_decisions()
    by_path = {item.rel_path: item for item in decisions}

    assert by_path[".runtime-cache/operator/gif-frames"].action == "delete"
    assert by_path[".runtime-cache/operator/gif-frames-final2"].action == "keep"


def test_apply_cleanup_deletes_only_older_gif_dirs(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cleanup_script, "ROOT", tmp_path)
    monkeypatch.setattr(cleanup_script, "ARTIFACTS_ROOT", tmp_path / ".runtime-cache" / "operator")

    _make_gif_dir(tmp_path, "gif-frames", age_offset=1)
    latest = _make_gif_dir(tmp_path, "gif-frames-final2", age_offset=2)
    _touch(tmp_path / ".runtime-cache" / "operator" / "gemini-audit" / "full-audit.json", text="{}")
    _touch(tmp_path / ".runtime-cache" / "operator" / "2026-03-27_06-22-09__pre-closure-working-tree.patch")
    _touch(tmp_path / ".runtime-cache" / "operator" / "2026-03-27-release-v0.1.2.md")

    decisions = cleanup_script.collect_decisions()
    cleanup_script.apply_cleanup(decisions)

    assert (tmp_path / ".runtime-cache" / "operator" / "gif-frames").exists() is False
    assert latest.exists() is True
    assert (tmp_path / ".runtime-cache" / "operator" / "gemini-audit").exists() is True
    assert (tmp_path / ".runtime-cache" / "operator" / "2026-03-27_06-22-09__pre-closure-working-tree.patch").exists() is True
    assert (tmp_path / ".runtime-cache" / "operator" / "2026-03-27-release-v0.1.2.md").exists() is True


def test_collect_decisions_keeps_single_gif_dir(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cleanup_script, "ROOT", tmp_path)
    monkeypatch.setattr(cleanup_script, "ARTIFACTS_ROOT", tmp_path / ".runtime-cache" / "operator")

    _make_gif_dir(tmp_path, "gif-frames-final", age_offset=1)
    decisions = cleanup_script.collect_decisions()

    assert len(decisions) == 1
    assert decisions[0].action == "keep"
