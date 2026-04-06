from __future__ import annotations

import subprocess
from pathlib import Path

import scripts.clean as clean_script


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "clean.py"


def _touch(path: Path, *, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_clean_script_refuses_and_preserves_protected_runtime_paths(capsys, tmp_path: Path) -> None:
    runtime_dir = tmp_path / ".runtime-cache"
    legacy_dir = tmp_path / ".legacy-runtime"
    operator_dir = runtime_dir / "operator"
    smoke_dir = operator_dir / "smoke"
    temp_dir = operator_dir / "temp"

    _touch(runtime_dir / "browser-identity" / "index.html", text="<html></html>")
    _touch(runtime_dir / "logs" / "dealwatch.log")
    _touch(runtime_dir / "runs" / "watch-tasks" / "run.json", text="{}")
    _touch(legacy_dir / "data" / "dealwatch.db", text="sqlite")
    _touch(smoke_dir / "keep.txt")
    _touch(temp_dir / "keep.txt")

    exit_code = clean_script.main()
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "legacy wide-delete entrypoint is no longer allowed" in captured.err
    assert (runtime_dir / "browser-identity" / "index.html").exists()
    assert (runtime_dir / "logs" / "dealwatch.log").exists()
    assert (runtime_dir / "runs" / "watch-tasks" / "run.json").exists()
    assert (legacy_dir / "data" / "dealwatch.db").exists()
    assert (smoke_dir / "keep.txt").exists()
    assert (temp_dir / "keep.txt").exists()


def test_clean_script_direct_execution_refuses_with_message() -> None:
    result = subprocess.run(
        [str(SCRIPT)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "legacy wide-delete entrypoint is no longer allowed" in result.stderr
