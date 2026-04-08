from __future__ import annotations

from pathlib import Path

import scripts.check_runtime_env as check_runtime_env
from scripts.shared.browser_lane_contract import DEFAULT_SHARED_CHROME_ROOT


def test_parse_env_file_reads_key_values(tmp_path: Path) -> None:
    env_path = tmp_path / ".env.production"
    env_path.write_text(
        "DATABASE_URL=postgresql+psycopg://db\nOWNER_EMAIL=owner@example.com\n# comment\nZIP_CODE=98004\n",
        encoding="utf-8",
    )
    payload = check_runtime_env.parse_env_file(env_path)
    assert payload["DATABASE_URL"] == "postgresql+psycopg://db"
    assert payload["ZIP_CODE"] == "98004"


def test_validate_runtime_accepts_complete_render_payload() -> None:
    payload = {
        "DATABASE_URL": "postgresql+psycopg://user:pass@db.example.invalid/dealwatch",
        "OWNER_EMAIL": "alerts@example.com",
        "OWNER_BOOTSTRAP_TOKEN": "super-secret-token",
        "APP_BASE_URL": "https://dealwatch-api.onrender.com",
        "WEBUI_DEV_URL": "https://dealwatch-webui.onrender.com",
        "ZIP_CODE": "98004",
        "POSTMARK_FROM_EMAIL": "alerts@example.com",
        "POSTMARK_SERVER_TOKEN": "pm-token",
        "ENABLED_STORES": "weee",
        "WORKER_POLL_SECONDS": "60",
        "CACHE_BUDGET_BYTES": "4294967296",
        "USE_LLM": "false",
    }
    checks, warnings = check_runtime_env.validate_runtime(payload, target="render")
    assert all(result.ok for result in checks)
    assert all(item.key != "SENTRY_DSN" for item in warnings)


def test_validate_runtime_rejects_placeholders() -> None:
    payload = {
        "DATABASE_URL": "postgresql+psycopg://dealwatch:dealwatch@localhost:15432/dealwatch",
        "OWNER_EMAIL": "owner@example.com",
        "OWNER_BOOTSTRAP_TOKEN": "change-me",
        "APP_BASE_URL": "http://localhost:8000",
        "WEBUI_DEV_URL": "http://localhost:5173",
        "ZIP_CODE": "00000",
        "POSTMARK_FROM_EMAIL": "dealwatch@example.com",
        "POSTMARK_SERVER_TOKEN": "",
        "SMTP_HOST": "",
        "SMTP_USER": "",
        "SMTP_PASSWORD": "",
        "ENABLED_STORES": "weee",
        "WORKER_POLL_SECONDS": "5",
        "CACHE_BUDGET_BYTES": "0",
        "USE_LLM": "false",
    }
    checks, _warnings = check_runtime_env.validate_runtime(payload, target="render")
    assert any(result.key == "OWNER_BOOTSTRAP_TOKEN" and not result.ok for result in checks)
    assert any(result.key == "notifications" and not result.ok for result in checks)
    assert any(result.key == "CACHE_BUDGET_BYTES" and not result.ok for result in checks)


def test_validate_runtime_accepts_ci_smoke_payload() -> None:
    payload = {
        "DATABASE_URL": "postgresql+psycopg://dealwatch:dealwatch@127.0.0.1:15432/dealwatch",
        "OWNER_EMAIL": "owner@example.com",
        "OWNER_BOOTSTRAP_TOKEN": "smoke-token",
        "APP_BASE_URL": "http://127.0.0.1:8000",
        "WEBUI_DEV_URL": "http://localhost:5173",
        "ZIP_CODE": "98004",
        "POSTMARK_FROM_EMAIL": "dealwatch@example.com",
        "POSTMARK_MESSAGE_STREAM": "outbound",
        "ENABLED_STORES": "weee",
        "WORKER_POLL_SECONDS": "60",
        "CACHE_BUDGET_BYTES": "4294967296",
        "USE_LLM": "false",
    }
    checks, warnings = check_runtime_env.validate_runtime(payload, target="ci-smoke")
    assert all(result.ok for result in checks)
    assert any(item.key == "notifications" for item in warnings)


def test_validate_runtime_accepts_startup_payload() -> None:
    payload = {
        "DATABASE_URL": "postgresql+psycopg://dealwatch:dealwatch@127.0.0.1:15432/dealwatch",
        "OWNER_EMAIL": "owner@example.com",
        "OWNER_BOOTSTRAP_TOKEN": "change-me",
        "APP_BASE_URL": "http://127.0.0.1:8000",
        "WEBUI_DEV_URL": "http://localhost:5173",
        "ZIP_CODE": "98102",
        "ENABLED_STORES": "weee",
        "CACHE_BUDGET_BYTES": "4294967296",
        "USE_LLM": "false",
        "POSTMARK_SERVER_TOKEN": "",
        "SMTP_HOST": "",
        "SMTP_USER": "",
        "SMTP_PASSWORD": "",
    }
    checks, warnings = check_runtime_env.validate_runtime(payload, target="startup")
    assert all(result.ok for result in checks)
    assert any(item.key == "notifications" for item in warnings)
    assert all(item.key != "ZIP_CODE" for item in warnings)
    notifications_warning = next(item for item in warnings if item.key == "notifications")
    llm_warning = next(item for item in warnings if item.key == "USE_LLM")
    assert "allowed unless you want local real email delivery" in notifications_warning.message
    assert "Local LLM is currently disabled" in llm_warning.message


def test_validate_runtime_warns_on_legacy_path_drift() -> None:
    payload = {
        "DATABASE_URL": "postgresql+psycopg://dealwatch:dealwatch@127.0.0.1:15432/dealwatch",
        "OWNER_EMAIL": "owner@example.com",
        "OWNER_BOOTSTRAP_TOKEN": "change-me",
        "APP_BASE_URL": "http://127.0.0.1:8000",
        "WEBUI_DEV_URL": "http://localhost:5173",
        "ZIP_CODE": "00000",
        "ENABLED_STORES": "weee",
        "CACHE_BUDGET_BYTES": "4294967296",
        "USE_LLM": "false",
        "DB_PATH": ".runtime-cache/cache/data/dealwatch.db",
        "BACKUPS_DIR": ".runtime-cache/cache/backups",
    }
    _checks, warnings = check_runtime_env.validate_runtime(payload, target="startup")
    warning_keys = {item.key for item in warnings}
    assert "DB_PATH" in warning_keys
    assert "BACKUPS_DIR" in warning_keys


def test_validate_runtime_warns_on_placeholder_zip_only_when_startup_zip_is_default() -> None:
    payload = {
        "DATABASE_URL": "postgresql+psycopg://dealwatch:dealwatch@127.0.0.1:15432/dealwatch",
        "OWNER_EMAIL": "owner@example.com",
        "OWNER_BOOTSTRAP_TOKEN": "change-me",
        "APP_BASE_URL": "http://127.0.0.1:8000",
        "WEBUI_DEV_URL": "http://localhost:5173",
        "ZIP_CODE": "00000",
        "ENABLED_STORES": "weee",
        "CACHE_BUDGET_BYTES": "4294967296",
        "USE_LLM": "false",
    }
    _checks, warnings = check_runtime_env.validate_runtime(payload, target="startup")
    zip_warning = next(item for item in warnings if item.key == "ZIP_CODE")
    assert "placeholder ZIP code 00000" in zip_warning.message


def test_validate_runtime_rejects_partial_browser_profile_contract() -> None:
    payload = {
        "DATABASE_URL": "postgresql+psycopg://dealwatch:dealwatch@127.0.0.1:15432/dealwatch",
        "OWNER_EMAIL": "owner@example.com",
        "OWNER_BOOTSTRAP_TOKEN": "change-me",
        "APP_BASE_URL": "http://127.0.0.1:8000",
        "WEBUI_DEV_URL": "http://localhost:5173",
        "ZIP_CODE": "98102",
        "ENABLED_STORES": "weee",
        "CACHE_BUDGET_BYTES": "4294967296",
        "USE_LLM": "false",
        "CHROME_USER_DATA_DIR": DEFAULT_SHARED_CHROME_ROOT,
        "CHROME_PROFILE_NAME": "dealwatch",
        "CHROME_PROFILE_DIRECTORY": "",
    }

    checks, _warnings = check_runtime_env.validate_runtime(payload, target="startup")

    assert any(result.key == "browser_profile_contract" and not result.ok for result in checks)


def test_validate_runtime_rejects_legacy_shared_chrome_root_for_dealwatch() -> None:
    payload = {
        "DATABASE_URL": "postgresql+psycopg://dealwatch:dealwatch@127.0.0.1:15432/dealwatch",
        "OWNER_EMAIL": "owner@example.com",
        "OWNER_BOOTSTRAP_TOKEN": "change-me",
        "APP_BASE_URL": "http://127.0.0.1:8000",
        "WEBUI_DEV_URL": "http://localhost:5173",
        "ZIP_CODE": "98102",
        "ENABLED_STORES": "weee",
        "CACHE_BUDGET_BYTES": "4294967296",
        "USE_LLM": "false",
        "CHROME_USER_DATA_DIR": DEFAULT_SHARED_CHROME_ROOT,
        "CHROME_PROFILE_NAME": "dealwatch",
        "CHROME_PROFILE_DIRECTORY": "Profile 21",
    }

    checks, _warnings = check_runtime_env.validate_runtime(payload, target="startup")

    assert any(result.key == "browser_profile_root" and not result.ok for result in checks)


def test_validate_runtime_accepts_dedicated_chrome_root_contract() -> None:
    payload = {
        "DATABASE_URL": "postgresql+psycopg://dealwatch:dealwatch@127.0.0.1:15432/dealwatch",
        "OWNER_EMAIL": "owner@example.com",
        "OWNER_BOOTSTRAP_TOKEN": "change-me",
        "APP_BASE_URL": "http://127.0.0.1:8000",
        "WEBUI_DEV_URL": "http://localhost:5173",
        "ZIP_CODE": "98102",
        "ENABLED_STORES": "weee",
        "CACHE_BUDGET_BYTES": "4294967296",
        "USE_LLM": "false",
        "CHROME_USER_DATA_DIR": "~/.cache/dealwatch/browser/chrome-user-data",
        "CHROME_PROFILE_NAME": "dealwatch",
        "CHROME_PROFILE_DIRECTORY": "Profile 21",
    }

    checks, _warnings = check_runtime_env.validate_runtime(payload, target="startup")

    assert not any(result.key == "browser_profile_root" and not result.ok for result in checks)
