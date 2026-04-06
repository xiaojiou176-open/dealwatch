from __future__ import annotations

from pathlib import Path

import scripts.verify_host_process_safety as guard


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_scan_repository_flags_shell_primitives(tmp_path: Path) -> None:
    _write(
        tmp_path / "scripts" / "bad.sh",
        "\n".join(
            [
                "killall Google Chrome",
                "pkill -f dealwatch",
                "kill -9 12345",
            ]
        ),
    )

    findings = guard.scan_repository(tmp_path)

    assert any("scripts/bad.sh:1" in item and "`killall`" in item for item in findings)
    assert any("scripts/bad.sh:2" in item and "`pkill`" in item for item in findings)
    assert any("scripts/bad.sh:3" in item and "`kill_minus_nine`" in item for item in findings)


def test_scan_repository_flags_direct_signal_and_desktop_automation(tmp_path: Path) -> None:
    _write(
        tmp_path / "src" / "bad.ts",
        "\n".join(
            [
                "process.kill(child.pid, 'SIGTERM');",
                "const script = 'tell application \"System Events\" to key code 36';",
                "const cmd = 'osascript -e ' + script;",
            ]
        ),
    )
    _write(
        tmp_path / ".github" / "workflows" / "bad.yml",
        "run: echo loginwindow && echo AppleEvent",
    )

    findings = guard.scan_repository(tmp_path)

    assert any("src/bad.ts:1" in item and "`process_kill`" in item for item in findings)
    assert any("src/bad.ts:2" in item and "`system_events`" in item for item in findings)
    assert any("src/bad.ts:3" in item and "`osascript`" in item for item in findings)
    assert any(".github/workflows/bad.yml:1" in item and "`loginwindow_force_quit`" in item for item in findings)
    assert any(".github/workflows/bad.yml:1" in item and "`appleevent`" in item for item in findings)


def test_scan_repository_ignores_markdown_and_self_exempt_paths(tmp_path: Path) -> None:
    _write(tmp_path / "README.md", "killall should stay document-only here")
    _write(tmp_path / "docs" / "notes.md", "osascript and System Events are documented, not executed")
    _write(tmp_path / "scripts" / "verify_host_process_safety.py", "killall\nosascript\n")
    _write(tmp_path / "tests" / "test_host_process_safety_contract.py", "pkill\n")

    findings = guard.scan_repository(tmp_path)

    assert findings == []
