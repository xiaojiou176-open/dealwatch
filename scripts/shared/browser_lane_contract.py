from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
DEFAULT_DEDICATED_CHROME_USER_DATA_DIR = str(
    Path("~/.cache/dealwatch/browser/chrome-user-data").expanduser()
)
DEFAULT_SHARED_CHROME_ROOT = str(
    Path("~/Library/Application Support/Google/Chrome").expanduser()
)
LEGACY_SHARED_CHROME_ROOT_SUFFIX = "/Library/Application Support/Google/Chrome"


@dataclass(frozen=True, slots=True)
class BrowserLaneContract:
    env_file: Path
    cdp_url: str
    remote_debug_port: int
    user_data_dir: str
    profile_name: str
    profile_directory: str


def load_values(env_file: Path) -> dict[str, str]:
    payload: dict[str, str] = {}
    if env_file.exists():
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in raw_line:
                continue
            key, value = raw_line.split("=", 1)
            payload[key.strip()] = value.strip().strip('"').strip("'")
    for key, value in os.environ.items():
        payload[key] = value
    return payload


def _normalize_browser_root(value: str | None) -> str | None:
    if not value:
        return None
    return str(Path(value).expanduser())


def is_legacy_shared_chrome_root(value: str | None) -> bool:
    normalized = _normalize_browser_root(value)
    if not normalized:
        return False
    normalized = normalized.replace("\\", "/")
    return normalized == DEFAULT_SHARED_CHROME_ROOT or normalized.endswith(
        LEGACY_SHARED_CHROME_ROOT_SUFFIX
    )


def resolve_contract(
    values: dict[str, str],
    *,
    env_file: Path,
    caller_name: str,
) -> BrowserLaneContract:
    user_data_dir = str(values.get("CHROME_USER_DATA_DIR", "")).strip()
    profile_name = str(values.get("CHROME_PROFILE_NAME", "")).strip()
    profile_directory = str(values.get("CHROME_PROFILE_DIRECTORY", "")).strip()
    if not (user_data_dir and profile_name and profile_directory):
        raise SystemExit(
            f"{caller_name} refused: CHROME_USER_DATA_DIR, CHROME_PROFILE_NAME, and CHROME_PROFILE_DIRECTORY must all be configured."
        )
    normalized_user_data_dir = _normalize_browser_root(user_data_dir) or user_data_dir
    if profile_name == "dealwatch" and is_legacy_shared_chrome_root(normalized_user_data_dir):
        raise SystemExit(
            f"{caller_name} refused: CHROME_USER_DATA_DIR must not point at the legacy shared Chrome root when CHROME_PROFILE_NAME=dealwatch. Migrate to {DEFAULT_DEDICATED_CHROME_USER_DATA_DIR} and reuse the dedicated DealWatch browser lane instead."
        )
    remote_debug_port = int(str(values.get("CHROME_REMOTE_DEBUG_PORT", "")).strip() or "9333")
    cdp_url = str(values.get("CHROME_CDP_URL", "")).strip() or f"http://127.0.0.1:{remote_debug_port}"
    return BrowserLaneContract(
        env_file=env_file,
        cdp_url=cdp_url.rstrip("/"),
        remote_debug_port=remote_debug_port,
        user_data_dir=normalized_user_data_dir,
        profile_name=profile_name,
        profile_directory=profile_directory,
    )
