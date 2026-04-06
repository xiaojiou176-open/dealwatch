from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.migrate_dealwatch_chrome_profile as migration_script


def _write_source_profile(root: Path, *, profile_directory: str = "Profile 21") -> migration_script.ChromeProfileSource:
    local_state = root / "Local State"
    local_state.parent.mkdir(parents=True, exist_ok=True)
    local_state.write_text(
        json.dumps(
            {
                "profile": {
                    "info_cache": {
                        profile_directory: {"name": "dealwatch"},
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    profile_path = root / profile_directory
    (profile_path / "Preferences").parent.mkdir(parents=True, exist_ok=True)
    (profile_path / "Preferences").write_text("{}", encoding="utf-8")
    return migration_script.ChromeProfileSource(
        source_root=root,
        local_state_path=local_state,
        profile_name="dealwatch",
        profile_directory=profile_directory,
        profile_path=profile_path,
    )


def test_detect_active_default_chrome_processes_filters_non_default_user_data_dir(monkeypatch) -> None:
    class _Result:
        stdout = "\n".join(
            [
                "1234 Google /Applications/Google Chrome.app/Contents/MacOS/Google Chrome --remote-debugging-port=9222",
                "5678 Google /Applications/Google Chrome.app/Contents/MacOS/Google Chrome --user-data-dir=/tmp/not-dealwatch-root",
                "9012 Python <uv-executable> run something --chrome-path /Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            ]
        )

    monkeypatch.setattr(migration_script.subprocess, "run", lambda *args, **kwargs: _Result())

    matches = migration_script.detect_active_default_chrome_processes()

    assert len(matches) == 1
    assert "--remote-debugging-port=9222" in matches[0]


def test_ensure_target_root_ready_rejects_non_empty_directory(tmp_path: Path) -> None:
    target_root = tmp_path / "chrome-user-data"
    target_root.mkdir(parents=True)
    (target_root / "sentinel").write_text("x", encoding="utf-8")

    with pytest.raises(SystemExit, match="target root already exists and is not empty"):
        migration_script.ensure_target_root_ready(target_root)


def test_apply_migration_copies_profile_and_writes_env(tmp_path: Path) -> None:
    source = _write_source_profile(tmp_path / "source-root")
    target_root = tmp_path / "target-root"
    env_file = tmp_path / ".env"

    migration_script.apply_migration(
        source=source,
        target_root=target_root,
        env_file=env_file,
        remote_debug_port=9333,
    )

    assert (target_root / "Local State").is_file() is True
    assert (target_root / "Profile 21" / "Preferences").is_file() is True
    payload = env_file.read_text(encoding="utf-8")
    assert 'CHROME_USER_DATA_DIR="' in payload
    assert "CHROME_PROFILE_NAME=dealwatch" in payload
    assert "CHROME_PROFILE_DIRECTORY=Profile 21" in payload
    assert "CHROME_ATTACH_MODE=browser" in payload
    assert "CHROME_CDP_URL=http://127.0.0.1:9333" in payload
    assert "CHROME_REMOTE_DEBUG_PORT=9333" in payload


def test_update_env_file_overwrites_existing_contract_keys(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "CHROME_USER_DATA_DIR=/tmp/old",
                "CHROME_PROFILE_NAME=old-profile",
                "CHROME_PROFILE_DIRECTORY=Profile 9",
                "CHROME_ATTACH_MODE=persistent",
                "OTHER_KEY=value",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    migration_script.update_env_file(
        env_file=env_file,
        target_root=tmp_path / "chrome-user-data",
        profile_directory="Profile 21",
        remote_debug_port=9333,
    )

    payload = env_file.read_text(encoding="utf-8")
    assert 'CHROME_USER_DATA_DIR="' in payload
    assert "CHROME_PROFILE_NAME=dealwatch" in payload
    assert "CHROME_PROFILE_DIRECTORY=Profile 21" in payload
    assert "CHROME_ATTACH_MODE=browser" in payload
    assert "CHROME_CDP_URL=http://127.0.0.1:9333" in payload
    assert "OTHER_KEY=value" in payload
