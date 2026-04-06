#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"
DEFAULT_SOURCE_ROOT = Path("~/Library/Application Support/Google/Chrome").expanduser()
DEFAULT_TARGET_ROOT = Path("~/.cache/dealwatch/browser/chrome-user-data").expanduser()
EXPECTED_PROFILE_NAME = "dealwatch"
DEFAULT_REMOTE_DEBUG_PORT = 9333
PROFILE_KEYS = (
    "CHROME_USER_DATA_DIR",
    "CHROME_PROFILE_NAME",
    "CHROME_PROFILE_DIRECTORY",
    "CHROME_ATTACH_MODE",
    "CHROME_CDP_URL",
    "CHROME_REMOTE_DEBUG_PORT",
)
SINGLETON_FILES = ("SingletonLock", "SingletonCookie", "SingletonSocket")


@dataclass(frozen=True, slots=True)
class ChromeProfileSource:
    source_root: Path
    local_state_path: Path
    profile_name: str
    profile_directory: str
    profile_path: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Clone the real DealWatch Chrome profile into the dedicated repo-owned browser root."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Show the migration plan without copying files.")
    mode.add_argument("--apply", action="store_true", help="Copy Local State + the real DealWatch profile and update the local .env.")
    parser.add_argument(
        "--env-file",
        default=str(DEFAULT_ENV_FILE),
        help="Path to the local .env file that should receive the DealWatch Chrome contract.",
    )
    parser.add_argument(
        "--target-root",
        default=str(DEFAULT_TARGET_ROOT),
        help="Dedicated Chrome user-data root for DealWatch.",
    )
    parser.add_argument(
        "--remote-debug-port",
        type=int,
        default=DEFAULT_REMOTE_DEBUG_PORT,
        help="Remote debugging port to write into the local DealWatch browser contract.",
    )
    return parser.parse_args()


def discover_source() -> ChromeProfileSource:
    local_state_path = DEFAULT_SOURCE_ROOT / "Local State"
    if not local_state_path.is_file():
        raise SystemExit(f"DealWatch Chrome migration failed: missing Local State at {local_state_path}")

    payload = json.loads(local_state_path.read_text(encoding="utf-8"))
    info_cache = payload.get("profile", {}).get("info_cache", {})
    if not isinstance(info_cache, dict):
        raise SystemExit("DealWatch Chrome migration failed: Chrome Local State has no profile info_cache")

    profile_directory = ""
    for directory, raw_info in info_cache.items():
        if isinstance(raw_info, dict) and str(raw_info.get("name") or "").strip() == EXPECTED_PROFILE_NAME:
            profile_directory = str(directory)
            break
    if not profile_directory:
        raise SystemExit("DealWatch Chrome migration failed: could not locate the 'dealwatch' profile in Local State")

    profile_path = DEFAULT_SOURCE_ROOT / profile_directory
    if not profile_path.is_dir():
        raise SystemExit(
            f"DealWatch Chrome migration failed: discovered profile directory does not exist: {profile_path}"
        )

    return ChromeProfileSource(
        source_root=DEFAULT_SOURCE_ROOT,
        local_state_path=local_state_path,
        profile_name=EXPECTED_PROFILE_NAME,
        profile_directory=profile_directory,
        profile_path=profile_path,
    )


def detect_active_default_chrome_processes() -> list[str]:
    result = subprocess.run(
        ["ps", "-axo", "pid=,comm=,args="],
        check=True,
        capture_output=True,
        text=True,
    )
    matches: list[str] = []
    source_root_text = str(DEFAULT_SOURCE_ROOT)
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split(None, 2)
        if len(parts) < 3:
            continue
        pid, command_name, args = parts
        if command_name != "Google" and command_name != "Google Chrome":
            # ps truncates comm, but real Chrome main processes still start with Google/Google Chrome.
            continue
        if "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" not in args:
            continue
        if "--user-data-dir=" in args and source_root_text not in args:
            continue
        matches.append(f"{pid} {command_name} {args}")
    return matches


def ensure_target_root_ready(target_root: Path) -> None:
    if target_root.exists():
        entries = [child for child in target_root.iterdir()]
        if entries:
            raise SystemExit(
                f"DealWatch Chrome migration failed: target root already exists and is not empty: {target_root}"
            )
    else:
        target_root.parent.mkdir(parents=True, exist_ok=True)


def remove_singletons(target_root: Path) -> list[Path]:
    removed: list[Path] = []
    for name in SINGLETON_FILES:
        candidate = target_root / name
        if candidate.exists():
            candidate.unlink()
            removed.append(candidate)
    return removed


def update_env_file(
    *,
    env_file: Path,
    target_root: Path,
    profile_directory: str,
    remote_debug_port: int,
) -> None:
    if env_file.exists():
        lines = env_file.read_text(encoding="utf-8").splitlines()
    else:
        lines = []
    desired = {
        "CHROME_USER_DATA_DIR": f"\"{target_root}\"",
        "CHROME_PROFILE_NAME": EXPECTED_PROFILE_NAME,
        "CHROME_PROFILE_DIRECTORY": profile_directory,
        "CHROME_ATTACH_MODE": "browser",
        "CHROME_CDP_URL": f"http://127.0.0.1:{remote_debug_port}",
        "CHROME_REMOTE_DEBUG_PORT": str(remote_debug_port),
    }
    remaining = set(desired)
    updated_lines: list[str] = []
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line else ""
        if key in desired:
            updated_lines.append(f"{key}={desired[key]}")
            remaining.discard(key)
        else:
            updated_lines.append(line)
    if updated_lines and updated_lines[-1].strip():
        updated_lines.append("")
    for key in PROFILE_KEYS:
        if key in remaining:
            updated_lines.append(f"{key}={desired[key]}")
    env_file.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")


def render_summary(
    *,
    mode: str,
    source: ChromeProfileSource,
    target_root: Path,
    env_file: Path,
    remote_debug_port: int,
    active_processes: list[str],
) -> str:
    lines = [
        "DealWatch Chrome profile migration",
        f"mode={mode}",
        f"source_root={source.source_root}",
        f"source_profile_name={source.profile_name}",
        f"source_profile_directory={source.profile_directory}",
        f"target_root={target_root}",
        f"target_profile_directory={source.profile_directory}",
        f"env_file={env_file}",
        f"remote_debug_port={remote_debug_port}",
        f"source_process_blockers={len(active_processes)}",
        "copy_plan=Local State + source profile only",
        "singleton_policy=remove target-root SingletonLock/SingletonCookie/SingletonSocket",
    ]
    for line in active_processes:
        lines.append(f"- active_default_chrome={line}")
    return "\n".join(lines)


def apply_migration(
    *,
    source: ChromeProfileSource,
    target_root: Path,
    env_file: Path,
    remote_debug_port: int,
) -> None:
    target_root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source.local_state_path, target_root / "Local State")
    shutil.copytree(source.profile_path, target_root / source.profile_directory)
    remove_singletons(target_root)
    update_env_file(
        env_file=env_file,
        target_root=target_root,
        profile_directory=source.profile_directory,
        remote_debug_port=remote_debug_port,
    )


def main() -> int:
    args = parse_args()
    source = discover_source()
    target_root = Path(args.target_root).expanduser()
    env_file = Path(args.env_file).expanduser()
    active_processes = detect_active_default_chrome_processes()
    print(
        render_summary(
            mode="dry-run" if args.dry_run else "apply",
            source=source,
            target_root=target_root,
            env_file=env_file,
            remote_debug_port=args.remote_debug_port,
            active_processes=active_processes,
        )
    )
    if active_processes:
        raise SystemExit(
            "DealWatch Chrome migration refused: the default Chrome user-data root is still in use by active Chrome processes."
        )
    ensure_target_root_ready(target_root)
    if args.apply:
        apply_migration(
            source=source,
            target_root=target_root,
            env_file=env_file,
            remote_debug_port=args.remote_debug_port,
        )
        print("status=applied")
    else:
        print("status=planned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
