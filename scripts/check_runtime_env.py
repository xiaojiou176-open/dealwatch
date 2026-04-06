from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PLACEHOLDER_VALUES = {
    "",
    "change-me",
    "owner@example.com",
    "dealwatch@example.com",
    "__required_database_url__",
    "__required_owner_email__",
    "__required_owner_bootstrap_token__",
    "__required_app_base_url__",
    "__required_webui_origin__",
    "__required_zip_code__",
    "__required_postmark_from_email__",
    "__optional_postmark_server_token__",
}
_RUNTIME_CACHE_DRIFT_SEGMENT = ".runtime-cache/cache"
_EMITTED_RUNTIME_WARNING_KEYS = {"DB_PATH", "BACKUPS_DIR"}
_DEFAULT_SHARED_CHROME_ROOT = str(
    Path("~/Library/Application Support/Google/Chrome").expanduser()
)
_LEGACY_SHARED_CHROME_ROOT_SUFFIX = "/Library/Application Support/Google/Chrome"


def _normalize_browser_root(value: str) -> str:
    return str(Path(value).expanduser())


def _is_legacy_shared_chrome_root(value: str) -> bool:
    normalized = _normalize_browser_root(value).replace("\\", "/")
    return normalized == _DEFAULT_SHARED_CHROME_ROOT or normalized.endswith(_LEGACY_SHARED_CHROME_ROOT_SUFFIX)


@dataclass(slots=True)
class CheckResult:
    ok: bool
    key: str
    message: str
    severity: str = "error"


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_values(env_file: Path | None) -> dict[str, str]:
    values: dict[str, str] = {}
    if env_file is not None:
        values.update(parse_env_file(env_file))
    for key, value in os.environ.items():
        values[key] = value
    return values


def load_settings_values(settings_obj: Any) -> dict[str, str]:
    payload: dict[str, str] = {}
    for key, value in settings_obj.model_dump().items():
        if hasattr(value, "get_secret_value"):
            payload[key] = value.get_secret_value()
        elif value is None:
            payload[key] = ""
        else:
            payload[key] = str(value)
    return payload


def is_placeholder(value: str) -> bool:
    normalized = value.strip().lower()
    return normalized in PLACEHOLDER_VALUES or normalized.startswith("__required_") or normalized.startswith("__optional_")


def is_truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def validate_runtime(values: dict[str, str], *, target: str) -> tuple[list[CheckResult], list[CheckResult]]:
    checks: list[CheckResult] = []
    warnings: list[CheckResult] = []
    allow_placeholder_identity = target in {"ci-smoke", "startup"}
    allow_placeholder_bootstrap = target == "startup"

    def require(key: str, message: str) -> None:
        value = values.get(key, "")
        if allow_placeholder_identity and key in {"OWNER_EMAIL", "POSTMARK_FROM_EMAIL"}:
            checks.append(CheckResult(ok=bool(value.strip()), key=key, message=message))
            return
        if allow_placeholder_bootstrap and key == "OWNER_BOOTSTRAP_TOKEN":
            checks.append(CheckResult(ok=bool(value.strip()), key=key, message=message))
            return
        if allow_placeholder_identity and key == "ZIP_CODE":
            checks.append(CheckResult(ok=bool(value.strip()), key=key, message=message))
            return
        checks.append(CheckResult(ok=bool(value and not is_placeholder(value)), key=key, message=message))

    require("DATABASE_URL", "A real PostgreSQL connection string is required.")
    require("OWNER_EMAIL", "A real owner email is required.")
    require("OWNER_BOOTSTRAP_TOKEN", "A real owner bootstrap token is required.")
    require("APP_BASE_URL", "A public API URL is required.")
    require("WEBUI_DEV_URL", "A public frontend origin is required. Despite the legacy name, this value is used for production CORS.")
    require("ZIP_CODE", "A default ZIP code is required.")
    require("ENABLED_STORES", "At least one enabled store must be declared.")

    database_url = values.get("DATABASE_URL", "")
    if database_url:
        checks.append(
            CheckResult(
                ok=database_url.startswith("postgresql"),
                key="DATABASE_URL",
                message="The runtime must use PostgreSQL, not SQLite or another protocol.",
            )
        )
        if target == "render":
            checks.append(
                CheckResult(
                    ok="localhost" not in database_url and "127.0.0.1" not in database_url,
                    key="DATABASE_URL",
                    message="A Render production connection string must not point at localhost/127.0.0.1.",
                )
            )

    for key in ("APP_BASE_URL", "WEBUI_DEV_URL"):
        value = values.get(key, "")
        if value:
            if target in {"ci-smoke", "startup"}:
                checks.append(
                    CheckResult(
                        ok=value.startswith("http://") or value.startswith("https://"),
                        key=key,
                        message=f"{target} URLs must still be explicit HTTP(S) URLs.",
                    )
                )
                continue
            checks.append(
                CheckResult(
                    ok=value.startswith("https://") and "localhost" not in value and "127.0.0.1" not in value,
                    key=key,
                    message="Production URLs must be public HTTPS URLs, not localhost addresses.",
                )
            )

    zip_code = values.get("ZIP_CODE", "")
    if zip_code:
        if target == "startup" and zip_code == "00000":
            warnings.append(
                CheckResult(
                    ok=True,
                    key="ZIP_CODE",
                    message="Local startup still uses the placeholder ZIP code 00000; switch to a real local ZIP for more realistic task execution.",
                    severity="warning",
                )
            )
        else:
            checks.append(
                CheckResult(
                    ok=zip_code != "00000",
                    key="ZIP_CODE",
                    message="ZIP_CODE must not remain the placeholder value 00000.",
                )
            )

    postmark_token = values.get("POSTMARK_SERVER_TOKEN", "")
    smtp_host = values.get("SMTP_HOST", "")
    smtp_user = values.get("SMTP_USER", "")
    smtp_password = values.get("SMTP_PASSWORD", "")
    has_postmark = bool(postmark_token and not is_placeholder(postmark_token))
    has_smtp = bool(smtp_host and smtp_user and smtp_password and not any(is_placeholder(v) for v in (smtp_host, smtp_user, smtp_password)))
    if target == "startup":
        if not (has_postmark or has_smtp):
            warnings.append(
                CheckResult(
                    ok=True,
                    key="notifications",
                    message="Local startup currently has no real delivery provider configured; this is allowed unless you want local real email delivery via Postmark or SMTP.",
                    severity="warning",
                )
            )
    elif target == "ci-smoke":
        warnings.append(
            CheckResult(
                ok=True,
                key="notifications",
                message="ci-smoke does not require a real delivery provider.",
                severity="warning",
            )
        )
    else:
        checks.append(
            CheckResult(
                ok=has_postmark or has_smtp,
                key="notifications",
                message="At least one real notification path is required: Postmark or a complete SMTP configuration.",
            )
        )
    if has_postmark:
        require("POSTMARK_FROM_EMAIL", "A real sender address is required when Postmark is enabled.")
    if has_smtp and not has_postmark:
        warnings.append(CheckResult(ok=True, key="notifications", message="SMTP fallback is active. Long term, the preferred primary path is still Postmark.", severity="warning"))

    worker_poll_seconds = values.get("WORKER_POLL_SECONDS", "")
    if worker_poll_seconds:
        try:
            checks.append(
                CheckResult(
                    ok=int(worker_poll_seconds) >= 10,
                    key="WORKER_POLL_SECONDS",
                    message="WORKER_POLL_SECONDS must be an integer greater than or equal to 10.",
                )
            )
        except ValueError:
            checks.append(
                CheckResult(ok=False, key="WORKER_POLL_SECONDS", message="WORKER_POLL_SECONDS must be an integer.")
            )

    def _validate_int_range(key: str, *, minimum: int, maximum: int | None = None, message: str) -> None:
        raw = values.get(key, "")
        if not raw:
            return
        try:
            numeric = int(raw)
        except ValueError:
            checks.append(CheckResult(ok=False, key=key, message=f"{key} must be an integer."))
            return
        ok = numeric >= minimum and (maximum is None or numeric <= maximum)
        checks.append(CheckResult(ok=ok, key=key, message=message))

    _validate_int_range(
        "LOG_MAX_BYTES",
        minimum=1,
        message="LOG_MAX_BYTES must be an integer greater than or equal to 1.",
    )
    _validate_int_range(
        "LOG_BACKUP_COUNT",
        minimum=1,
        message="LOG_BACKUP_COUNT must be an integer greater than or equal to 1.",
    )
    _validate_int_range(
        "LOG_RETENTION_DAYS",
        minimum=1,
        message="LOG_RETENTION_DAYS must be an integer greater than or equal to 1.",
    )
    _validate_int_range(
        "CACHE_BUDGET_BYTES",
        minimum=1,
        message="CACHE_BUDGET_BYTES must be an integer greater than or equal to 1.",
    )
    _validate_int_range(
        "MAINTENANCE_HOUR_LOCAL",
        minimum=0,
        maximum=23,
        message="MAINTENANCE_HOUR_LOCAL must be between 0 and 23.",
    )
    _validate_int_range(
        "MAINTENANCE_MINUTE_LOCAL",
        minimum=0,
        maximum=59,
        message="MAINTENANCE_MINUTE_LOCAL must be between 0 and 59.",
    )

    db_path = values.get("DB_PATH", "")
    if _RUNTIME_CACHE_DRIFT_SEGMENT in db_path:
        warnings.append(
            CheckResult(
                ok=True,
                key="DB_PATH",
                message="DB_PATH still points into .runtime-cache/cache; legacy bridge paths should live under .legacy-runtime.",
                severity="warning",
            )
        )

    backups_dir = values.get("BACKUPS_DIR", "")
    if _RUNTIME_CACHE_DRIFT_SEGMENT in backups_dir:
        warnings.append(
            CheckResult(
                ok=True,
                key="BACKUPS_DIR",
                message="BACKUPS_DIR still points into .runtime-cache/cache; legacy bridge backups should live under .legacy-runtime.",
                severity="warning",
            )
        )

    profile_contract_values = {
        "CHROME_USER_DATA_DIR": values.get("CHROME_USER_DATA_DIR", "").strip(),
        "CHROME_PROFILE_NAME": values.get("CHROME_PROFILE_NAME", "").strip(),
        "CHROME_PROFILE_DIRECTORY": values.get("CHROME_PROFILE_DIRECTORY", "").strip(),
    }
    if any(profile_contract_values.values()) and not all(profile_contract_values.values()):
        checks.append(
            CheckResult(
                ok=False,
                key="browser_profile_contract",
                message="CHROME_USER_DATA_DIR, CHROME_PROFILE_NAME, and CHROME_PROFILE_DIRECTORY must be set together when the real Chrome profile contract is used.",
            )
        )
    if (
        all(profile_contract_values.values())
        and profile_contract_values["CHROME_PROFILE_NAME"] == "dealwatch"
        and _is_legacy_shared_chrome_root(profile_contract_values["CHROME_USER_DATA_DIR"])
    ):
        checks.append(
            CheckResult(
                ok=False,
                key="browser_profile_root",
                message="The legacy shared Chrome root is no longer allowed for the dealwatch profile. Migrate to ~/.cache/dealwatch/browser/chrome-user-data and use the dedicated single-instance CDP attach path.",
            )
        )

    if is_truthy(values.get("USE_LLM", "false")):
        require("LLM_API_KEY", "LLM_API_KEY is required when USE_LLM is enabled.")
    else:
        warnings.append(
            CheckResult(
                ok=True,
                key="USE_LLM",
                message="Local LLM is currently disabled; this is allowed. If you want local AI features, set USE_LLM=true and provide LLM_API_KEY.",
                severity="warning",
            )
        )

    return checks, warnings


def render_report(checks: list[CheckResult], warnings: list[CheckResult], *, env_source: str, target: str) -> str:
    lines = [
        "DealWatch Runtime Preflight",
        f"target={target}",
        f"source={env_source}",
        "",
    ]
    for result in checks:
        marker = "[x]" if result.ok else "[ ]"
        lines.append(f"{marker} {result.key}: {result.message}")
    if warnings:
        lines.append("")
        lines.append("Warnings:")
        for warning in warnings:
            lines.append(f"- {warning.key}: {warning.message}")
    blockers = [result for result in checks if not result.ok]
    lines.append("")
    lines.append(f"blockers={len(blockers)} warnings={len(warnings)}")
    if blockers:
        unique_keys = list(dict.fromkeys(result.key for result in blockers))
        lines.append("missing_or_invalid=" + ", ".join(unique_keys))
    return "\n".join(lines)


def ensure_runtime_contract(target: str, env_file: Path | None = None) -> None:
    values = load_values(env_file)
    checks, warnings = validate_runtime(values, target=target)
    blockers = [result for result in checks if not result.ok]
    if blockers:
        unique_keys = ",".join(dict.fromkeys(result.key for result in blockers))
        raise RuntimeError(f"runtime_preflight_failed:{target}:{unique_keys}")
    for warning in warnings:
        if warning.key not in _EMITTED_RUNTIME_WARNING_KEYS:
            continue
        print(f"WARNING [{target}] {warning.key}: {warning.message}", file=sys.stderr)


def ensure_runtime_contract_from_settings(settings_obj: Any, target: str) -> None:
    values = load_settings_values(settings_obj)
    checks, warnings = validate_runtime(values, target=target)
    blockers = [result for result in checks if not result.ok]
    if blockers:
        unique_keys = ",".join(dict.fromkeys(result.key for result in blockers))
        raise RuntimeError(f"runtime_preflight_failed:{target}:{unique_keys}")
    for warning in warnings:
        if warning.key not in _EMITTED_RUNTIME_WARNING_KEYS:
            continue
        print(f"WARNING [{target}] {warning.key}: {warning.message}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description="DealWatch runtime environment preflight")
    parser.add_argument("--env-file", type=Path, default=None, help="Path to a dotenv-style file to validate")
    parser.add_argument("--target", default="render", choices=["render", "generic", "ci-smoke", "startup"], help="Validation profile")
    args = parser.parse_args()

    if args.env_file is not None and not args.env_file.exists():
        print(f"ERROR: env file not found: {args.env_file}", file=sys.stderr)
        return 2

    values = load_values(args.env_file)
    checks, warnings = validate_runtime(values, target=args.target)
    env_source = str(args.env_file) if args.env_file is not None else "process-env"
    print(render_report(checks, warnings, env_source=env_source, target=args.target))
    return 0 if all(result.ok for result in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
