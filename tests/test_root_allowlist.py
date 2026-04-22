from __future__ import annotations

from pathlib import Path

import scripts.verify_root_allowlist as verify_script


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("placeholder", encoding="utf-8")


def test_root_allowlist_accepts_ignored_cursor_directory(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    _touch(tmp_path / "README.md")
    (tmp_path / ".cursor").mkdir()

    monkeypatch.setattr(verify_script, "ROOT", tmp_path)
    monkeypatch.setattr(verify_script, "_is_tracked", lambda path: False)
    monkeypatch.setattr(verify_script, "_tracked_under", lambda prefix: [])
    monkeypatch.setattr(
        verify_script,
        "_is_ignored",
        lambda path: path.name == ".cursor",
    )
    monkeypatch.setattr(verify_script, "_verify_runtime_namespace", lambda findings: None)
    monkeypatch.setattr(verify_script, "_verify_frontend_store", lambda findings: None)

    assert verify_script.main() == 0
    captured = capsys.readouterr()
    assert "Root allowlist verification passed." in captured.out


def test_root_allowlist_rejects_root_ds_store(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    _touch(tmp_path / "README.md")
    _touch(tmp_path / ".DS_Store")

    monkeypatch.setattr(verify_script, "ROOT", tmp_path)
    monkeypatch.setattr(verify_script, "_is_tracked", lambda path: False)
    monkeypatch.setattr(verify_script, "_tracked_under", lambda prefix: [])
    monkeypatch.setattr(verify_script, "_is_ignored", lambda path: True)
    monkeypatch.setattr(verify_script, "_verify_runtime_namespace", lambda findings: None)
    monkeypatch.setattr(verify_script, "_verify_frontend_store", lambda findings: None)

    assert verify_script.main() == 1
    captured = capsys.readouterr()
    assert "Banned root entry present: .DS_Store" in captured.out
