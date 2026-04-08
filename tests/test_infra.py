import builtins
import logging
from pathlib import Path

from sqlalchemy import select

import dealwatch.persistence.session as session_module
import dealwatch.infra.config as config_module
import dealwatch.server as server
from dealwatch.infra.config import (
    Settings,
    load_enabled_stores_from_yaml,
    _load_enabled_stores_legacy,
    configure_logging,
)
from dealwatch.infra.mailer import EmailNotifier
import dealwatch.infra.mailer as mailer
from dealwatch.legacy.db_repo import DatabaseRepository
from dealwatch.persistence.models import StoreAdapterBinding
from dealwatch.persistence.store_bindings import sync_store_adapter_bindings
from dealwatch.infra import playwright_client
from dealwatch.infra.retry_budget import RetryBudget
from dealwatch.stores import STORE_REGISTRY
import pytest


def test_config_normalize_enabled_stores_string() -> None:
    settings = Settings(ENABLED_STORES="weee, ttm; foo")
    assert settings.ENABLED_STORES == ["weee", "ttm", "foo"]


def test_config_normalize_enabled_stores_list() -> None:
    settings = Settings(ENABLED_STORES=["weee", " ", "ttm"])
    assert settings.ENABLED_STORES == ["weee", "ttm"]


def test_config_normalize_enabled_stores_none() -> None:
    settings = Settings(ENABLED_STORES=None)
    assert settings.ENABLED_STORES == []


def test_config_normalize_enabled_stores_other_type() -> None:
    settings = Settings(ENABLED_STORES=123)
    assert settings.ENABLED_STORES == []


def test_load_enabled_stores_from_yaml(tmp_path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("enabled_stores: [weee, ttm]\n", encoding="utf-8")
    enabled = load_enabled_stores_from_yaml(path)
    assert enabled == ["weee", "ttm"]


def test_load_enabled_stores_with_schema_fields(tmp_path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        """
enabled_stores: [weee, ttm]
anomaly_enabled: true
anomaly_mark_only: false
rule_min_drop_amount: 0.1
playwright_retry_budget: 10
""".strip(),
        encoding="utf-8",
    )
    enabled = load_enabled_stores_from_yaml(path)
    assert enabled == ["weee", "ttm"]


def test_load_enabled_stores_legacy(tmp_path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        """
enabled_stores:
  - weee
  - ttm
""".strip(),
        encoding="utf-8",
    )
    logger = logging.getLogger("test")
    enabled = _load_enabled_stores_legacy(path, logger)
    assert enabled == ["weee", "ttm"]


def test_config_db_path_normalization(tmp_path) -> None:
    settings = Settings(DB_PATH=".runtime-cache/cache/data/dealwatch.db")
    assert settings.DB_PATH.is_absolute() is True


def test_migrate_default_legacy_storage_moves_previous_default_paths(tmp_path, monkeypatch) -> None:
    old_db_path = tmp_path / ".runtime-cache" / "cache" / "data" / "dealwatch.db"
    old_backup_dir = tmp_path / ".runtime-cache" / "cache" / "backups"
    new_db_path = tmp_path / ".legacy-runtime" / "data" / "dealwatch.db"
    new_backup_dir = tmp_path / ".legacy-runtime" / "backups"

    old_db_path.parent.mkdir(parents=True, exist_ok=True)
    old_backup_dir.mkdir(parents=True, exist_ok=True)
    old_db_path.write_text("legacy-db", encoding="utf-8")
    (old_backup_dir / "backup.sqlite").write_text("backup", encoding="utf-8")

    monkeypatch.setattr(config_module, "DEFAULT_PREVIOUS_DB_PATH", old_db_path)
    monkeypatch.setattr(config_module, "DEFAULT_PREVIOUS_BACKUPS_DIR", old_backup_dir)
    monkeypatch.setattr(config_module, "DEFAULT_DB_PATH", new_db_path)
    monkeypatch.setattr(config_module, "DEFAULT_BACKUPS_DIR", new_backup_dir)
    monkeypatch.setattr(config_module.settings, "DB_PATH", new_db_path)
    monkeypatch.setattr(config_module.settings, "BACKUPS_DIR", new_backup_dir)

    config_module.migrate_default_legacy_storage()

    assert new_db_path.read_text(encoding="utf-8") == "legacy-db"
    assert (new_backup_dir / "backup.sqlite").read_text(encoding="utf-8") == "backup"
    assert old_db_path.exists() is False
    assert old_backup_dir.exists() is False


def test_migrate_default_legacy_storage_matches_relative_default_equivalent_paths(tmp_path, monkeypatch) -> None:
    old_db_path = tmp_path / ".runtime-cache" / "cache" / "data" / "dealwatch.db"
    old_backup_dir = tmp_path / ".runtime-cache" / "cache" / "backups"
    new_db_path = tmp_path / ".legacy-runtime" / "data" / "dealwatch.db"
    new_backup_dir = tmp_path / ".legacy-runtime" / "backups"

    old_db_path.parent.mkdir(parents=True, exist_ok=True)
    old_backup_dir.mkdir(parents=True, exist_ok=True)
    old_db_path.write_text("legacy-db", encoding="utf-8")
    (old_backup_dir / "backup.sqlite").write_text("backup", encoding="utf-8")

    monkeypatch.setattr(config_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(config_module, "DEFAULT_PREVIOUS_DB_PATH", old_db_path)
    monkeypatch.setattr(config_module, "DEFAULT_PREVIOUS_BACKUPS_DIR", old_backup_dir)
    monkeypatch.setattr(config_module, "DEFAULT_DB_PATH", new_db_path)
    monkeypatch.setattr(config_module, "DEFAULT_BACKUPS_DIR", new_backup_dir)

    config_module.migrate_default_legacy_storage(
        db_path=Path(".legacy-runtime/data/dealwatch.db"),
        backups_dir=Path(".legacy-runtime/backups"),
    )

    assert new_db_path.read_text(encoding="utf-8") == "legacy-db"
    assert (new_backup_dir / "backup.sqlite").read_text(encoding="utf-8") == "backup"
    assert old_db_path.exists() is False
    assert old_backup_dir.exists() is False


def test_database_repository_normalizes_relative_db_path_to_default_location(tmp_path, monkeypatch) -> None:
    new_db_path = tmp_path / ".legacy-runtime" / "data" / "dealwatch.db"
    new_backup_dir = tmp_path / ".legacy-runtime" / "backups"

    monkeypatch.setattr(config_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(config_module, "DEFAULT_DB_PATH", new_db_path)
    monkeypatch.setattr(config_module, "DEFAULT_BACKUPS_DIR", new_backup_dir)
    monkeypatch.setattr(config_module.settings, "BACKUPS_DIR", Path(".legacy-runtime/backups"))

    repo = DatabaseRepository(db_path=Path(".legacy-runtime/data/dealwatch.db"))

    assert repo.db_path == new_db_path
    assert repo.db_path.is_absolute() is True


def test_config_load_invalid_yaml(tmp_path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("enabled_stores: [", encoding="utf-8")
    enabled = load_enabled_stores_from_yaml(path)
    assert enabled == []


def test_config_load_missing_yaml(tmp_path) -> None:
    path = tmp_path / "missing.yaml"
    enabled = load_enabled_stores_from_yaml(path)
    assert enabled == []


def test_config_load_yaml_import_error(monkeypatch, tmp_path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        """
enabled_stores:
  - weee
""".strip(),
        encoding="utf-8",
    )
    original_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "yaml":
            raise ImportError("no yaml")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    enabled = load_enabled_stores_from_yaml(path)
    assert enabled == ["weee"]


def test_config_load_yaml_non_dict(tmp_path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("[]", encoding="utf-8")
    enabled = load_enabled_stores_from_yaml(path)
    assert enabled == []


def test_config_load_yaml_extra_keys(tmp_path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        """
enabled_stores:
  - weee
unknown_key: 1
""".strip(),
        encoding="utf-8",
    )
    enabled = load_enabled_stores_from_yaml(path)
    assert enabled == []


def test_config_load_legacy_inline_unsupported(tmp_path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("enabled_stores: weee", encoding="utf-8")
    logger = logging.getLogger("test")
    enabled = _load_enabled_stores_legacy(path, logger)
    assert enabled == []


def test_config_load_legacy_inline_list(tmp_path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        "\n\nenabled_stores: [weee, ttm]\n",
        encoding="utf-8",
    )
    logger = logging.getLogger("test")
    enabled = _load_enabled_stores_legacy(path, logger)
    assert enabled == ["weee", "ttm"]


def test_config_load_legacy_read_error(monkeypatch, tmp_path) -> None:
    path = tmp_path / "config.yaml"

    def _raise(self, *args, **kwargs):
        raise OSError("boom")

    monkeypatch.setattr(Path, "read_text", _raise)
    logger = logging.getLogger("test")
    enabled = _load_enabled_stores_legacy(path, logger)
    assert enabled == []


def test_config_load_legacy_stop_on_new_section(tmp_path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        """
enabled_stores:
  - weee
other: 1
  - ttm
""".strip(),
        encoding="utf-8",
    )
    logger = logging.getLogger("test")
    enabled = _load_enabled_stores_legacy(path, logger)
    assert enabled == ["weee"]


def test_configure_logging_unknown() -> None:
    configure_logging("UNKNOWN")


@pytest.mark.asyncio
async def test_sync_store_adapter_bindings_populates_live_registry(tmp_path) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'bindings.db'}"
    factory = session_module.create_session_factory(db_url)
    await session_module.init_product_database(db_url, factory)
    config_module.settings.ENABLED_STORES = []
    await sync_store_adapter_bindings(factory)

    async with factory() as session:
        rows = list((await session.scalars(select(StoreAdapterBinding))).all())
        assert {row.store_key for row in rows} == set(STORE_REGISTRY)
        enabled_map = {row.store_key: row.enabled for row in rows}
        assert enabled_map == {
            "weee": True,
            "ranch99": True,
            "target": True,
            "safeway": True,
            "walmart": False,
        }


@pytest.mark.asyncio
async def test_sync_store_adapter_bindings_respects_enabled_stores_setting(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'bindings-filtered.db'}"
    factory = session_module.create_session_factory(db_url)
    await session_module.init_product_database(db_url, factory)
    monkeypatch.setattr(config_module.settings, "ENABLED_STORES", ["weee"])

    await sync_store_adapter_bindings(factory)

    async with factory() as session:
        rows = list((await session.scalars(select(StoreAdapterBinding))).all())
        enabled_map = {row.store_key: row.enabled for row in rows}
        assert enabled_map == {store_key: store_key == "weee" for store_key in STORE_REGISTRY}


@pytest.mark.asyncio
async def test_sync_store_adapter_bindings_uses_explicit_settings_object(tmp_path) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'bindings-explicit.db'}"
    factory = session_module.create_session_factory(db_url)
    await session_module.init_product_database(db_url, factory)
    local_settings = Settings(DATABASE_URL=db_url, ENABLED_STORES=["ranch99"])

    await sync_store_adapter_bindings(factory, local_settings)

    async with factory() as session:
        rows = list((await session.scalars(select(StoreAdapterBinding))).all())
        enabled_map = {row.store_key: row.enabled for row in rows}
        assert enabled_map == {store_key: store_key == "ranch99" for store_key in STORE_REGISTRY}


def test_configure_logging_writes_runtime_log(tmp_path, monkeypatch) -> None:
    log_dir = tmp_path / "logs"
    monkeypatch.setattr(config_module.settings, "LOGS_DIR", log_dir)
    configure_logging("INFO")
    logger = logging.getLogger("dealwatch.test")
    logger.info("runtime-log-check")
    log_file = log_dir / "dealwatch.log"
    assert log_file.exists() is True
    assert "runtime-log-check" in log_file.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_init_product_database_uses_migrations_for_postgres(monkeypatch) -> None:
    called: dict[str, str] = {}

    def _fake_upgrade(database_url: str) -> None:
        called["database_url"] = database_url

    monkeypatch.setattr(session_module, "run_product_migrations", _fake_upgrade)
    await session_module.init_product_database(
        Settings(
            DATABASE_URL="postgresql+psycopg://dealwatch:dealwatch@localhost:15432/dealwatch",
            PRODUCT_AUTO_CREATE_SCHEMA=False,
        )
    )
    assert called["database_url"].startswith("postgresql+psycopg://")


@pytest.mark.asyncio
async def test_init_product_database_skips_sqlite_when_bootstrap_disabled(tmp_path) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'disabled.db'}"
    await session_module.init_product_database(
        Settings(DATABASE_URL=db_url, PRODUCT_AUTO_CREATE_SCHEMA=False)
    )
    assert (tmp_path / "disabled.db").exists() is False


@pytest.mark.asyncio
async def test_init_product_database_creates_missing_sqlite_parent_dir(tmp_path) -> None:
    db_path = tmp_path / "nested" / "product.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"

    await session_module.init_product_database(
        Settings(DATABASE_URL=db_url, PRODUCT_AUTO_CREATE_SCHEMA=True)
    )

    assert db_path.parent.exists() is True
    assert db_path.exists() is True


def test_should_stamp_existing_schema_from_tables() -> None:
    assert session_module._should_stamp_existing_schema_from_tables({"users"}) is True
    assert session_module._should_stamp_existing_schema_from_tables({"users", "alembic_version"}) is False
    assert session_module._should_stamp_existing_schema_from_tables(set()) is False


def test_session_module_import_loads_product_metadata() -> None:
    expected = {"users", "watch_groups", "store_adapter_bindings"}
    assert expected.issubset(set(session_module.Base.metadata.tables))


def test_settings_redacted_masks_secret() -> None:
    settings = Settings(LLM_API_KEY="secret")
    payload = settings.redacted()
    assert payload["LLM_API_KEY"] == "***"


def test_settings_support_render_port() -> None:
    settings = Settings(PORT=10000, API_PORT=8000)
    assert settings.PORT == 10000
    assert settings.API_PORT == 8000


def test_retry_budget_consume() -> None:
    budget = RetryBudget(2)
    assert budget.consume() is True
    assert budget.consume() is True
    assert budget.consume() is False
    assert budget.used() == 2


def test_mailer_parse_smtp_host() -> None:
    host, port = EmailNotifier._parse_smtp_host("smtp.example.com:465")
    assert host == "smtp.example.com"
    assert port == 465

    host, port = EmailNotifier._parse_smtp_host("smtp.example.com")
    assert host == "smtp.example.com"
    assert port == 587


def test_mailer_resolve_recipients_env(monkeypatch) -> None:
    monkeypatch.setenv("SMTP_TO", "a@example.com, b@example.com")
    assert EmailNotifier._resolve_recipients("sender@example.com") == [
        "a@example.com",
        "b@example.com",
    ]

    monkeypatch.setenv("SMTP_TO", "")
    assert EmailNotifier._resolve_recipients("sender@example.com") == [
        "sender@example.com"
    ]


def test_server_prefers_render_port(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_run(app_path: str, host: str, port: int, reload: bool) -> None:
        captured["app_path"] = app_path
        captured["host"] = host
        captured["port"] = port
        captured["reload"] = reload

    monkeypatch.setattr(server.uvicorn, "run", _fake_run)
    monkeypatch.setattr(server.settings, "API_HOST", "0.0.0.0")
    monkeypatch.setattr(server.settings, "API_PORT", 8000)
    monkeypatch.setattr(server.settings, "PORT", 10000)

    server.main()

    assert captured == {
        "app_path": "dealwatch.server:app",
        "host": "0.0.0.0",
        "port": 10000,
        "reload": False,
    }


def test_playwright_proxy_config() -> None:
    proxy_user = "proxy-user"
    proxy_password = "proxy-pass"
    proxy = playwright_client.PlaywrightClient._build_proxy_config(
        f"http://{proxy_user}:{proxy_password}@proxy.example.com:8080"
    )
    assert proxy == {
        "server": "http://proxy.example.com:8080",
        "username": proxy_user,
        "password": proxy_password,
    }

    proxy = playwright_client.PlaywrightClient._build_proxy_config("proxy.example.com:8080")
    assert proxy == {"server": "http://proxy.example.com:8080"}


def test_playwright_blocked_content_detection() -> None:
    assert playwright_client.PlaywrightClient._is_blocked_content("Access Denied") is True
    assert playwright_client.PlaywrightClient._is_blocked_content("welcome page") is False


def test_playwright_compute_backoff_monotonic(monkeypatch) -> None:
    monkeypatch.setattr(playwright_client.random, "uniform", lambda *_: 0.0)
    first = playwright_client._compute_backoff(1)
    second = playwright_client._compute_backoff(2)
    assert second >= first


def test_mailer_send_custom_report_success(monkeypatch) -> None:
    settings = Settings(SMTP_HOST="smtp.example.com:587", SMTP_USER="sender@example.com")
    notifier = EmailNotifier(settings)
    calls: list[tuple] = []

    def _send(self, *args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setattr(EmailNotifier, "_send_smtp", _send)

    notifier.send_custom_report("<b>ok</b>", "Subject", "2026-01-01")
    assert len(calls) == 1


def test_mailer_send_custom_report_retry(monkeypatch) -> None:
    settings = Settings(SMTP_HOST="smtp.example.com:587", SMTP_USER="sender@example.com")
    notifier = EmailNotifier(settings)
    calls = {"count": 0}

    def _send(self, *args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("fail")

    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setattr(EmailNotifier, "_send_smtp", _send)

    notifier.send_custom_report("<b>ok</b>", "Subject", "2026-01-01")
    assert calls["count"] == 2


def test_mailer_send_daily_report(monkeypatch) -> None:
    settings = Settings(SMTP_HOST="smtp.example.com:587", SMTP_USER="sender@example.com")
    notifier = EmailNotifier(settings)
    called: dict[str, str] = {}

    def _send_custom(self, html_content: str, subject: str, subject_date: str) -> None:
        called["subject"] = subject
        called["date"] = subject_date

    monkeypatch.setattr(EmailNotifier, "send_custom_report", _send_custom)

    notifier.send_daily_report("<b>ok</b>", "2026-01-01")
    assert "DealWatch Daily Report" in called["subject"]
    assert called["date"] == "2026-01-01"


def test_mailer_send_custom_report_no_recipients(monkeypatch) -> None:
    settings = Settings(SMTP_HOST="smtp.example.com:587", SMTP_USER="")
    notifier = EmailNotifier(settings)
    monkeypatch.setenv("SMTP_TO", "")
    calls = {"count": 0}

    def _send(self, *args, **kwargs):
        calls["count"] += 1

    monkeypatch.setattr(EmailNotifier, "_send_smtp", _send)
    notifier.send_custom_report("<b>ok</b>", "Subject", "2026-01-01")
    assert calls["count"] == 0


def test_mailer_send_custom_report_uses_smtp_pass(monkeypatch) -> None:
    settings = Settings(SMTP_HOST="smtp.example.com:587", SMTP_USER="sender@example.com")
    notifier = EmailNotifier(settings)
    captured: dict[str, str] = {}

    def _send(self, *args, **kwargs):
        captured["password"] = kwargs["password"]

    monkeypatch.setenv("SMTP_PASSWORD", "")
    monkeypatch.setenv("SMTP_PASS", "fallback")
    monkeypatch.setattr(EmailNotifier, "_send_smtp", _send)

    notifier.send_custom_report("<b>ok</b>", "Subject", "2026-01-01")
    assert captured["password"] == "fallback"


def test_mailer_send_custom_report_retry_exhausted(monkeypatch) -> None:
    settings = Settings(SMTP_HOST="smtp.example.com:587", SMTP_USER="sender@example.com")
    notifier = EmailNotifier(settings)
    calls = {"count": 0}

    def _send(self, *args, **kwargs):
        calls["count"] += 1
        raise RuntimeError("fail")

    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setattr(EmailNotifier, "_send_smtp", _send)
    monkeypatch.setattr(mailer.time, "sleep", lambda *_: None)

    notifier.send_custom_report("<b>ok</b>", "Subject", "2026-01-01")
    assert calls["count"] == 3


def test_mailer_resolve_recipients_empty(monkeypatch) -> None:
    monkeypatch.setenv("SMTP_TO", "")
    assert EmailNotifier._resolve_recipients("") == []


def test_mailer_send_custom_report_missing_host() -> None:
    settings = Settings(SMTP_HOST="", SMTP_USER="sender@example.com")
    notifier = EmailNotifier(settings)
    notifier.send_custom_report("<b>ok</b>", "Subject", "2026-01-01")


def test_mailer_send_smtp_flow(monkeypatch) -> None:
    settings = Settings(SMTP_HOST="smtp.example.com:587", SMTP_USER="sender@example.com")
    notifier = EmailNotifier(settings)
    events: dict[str, object] = {}
    smtp_test_password = "example-smtp-passphrase"

    class _DummySMTP:
        def __init__(self, host: str, port: int, timeout: int) -> None:
            events["host"] = host
            events["port"] = port
            events["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def ehlo(self) -> None:
            events["ehlo"] = True

        def has_extn(self, name: str) -> bool:
            return name == "starttls"

        def starttls(self, context=None) -> None:
            events["starttls"] = True

        def login(self, username: str, password: str) -> None:
            events["login"] = (username, password)

        def send_message(self, message, from_addr: str, to_addrs: list[str]) -> None:
            events["sent"] = True

    monkeypatch.setattr(mailer.smtplib, "SMTP", _DummySMTP)

    notifier._send_smtp(
        host="smtp.example.com",
        port=587,
        sender="sender@example.com",
        recipients=["rcpt@example.com"],
        message=object(),
        username="sender@example.com",
        password=smtp_test_password,
    )
    assert events.get("sent") is True


def test_mailer_send_smtp_raises(monkeypatch) -> None:
    settings = Settings(SMTP_HOST="smtp.example.com:587", SMTP_USER="sender@example.com")
    notifier = EmailNotifier(settings)
    smtp_test_password = "example-smtp-passphrase"

    class _BadSMTP:
        def __init__(self, host: str, port: int, timeout: int) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def ehlo(self) -> None:
            return None

        def has_extn(self, name: str) -> bool:
            return False

        def login(self, username: str, password: str) -> None:
            return None

        def send_message(self, message, from_addr: str, to_addrs: list[str]) -> None:
            raise mailer.smtplib.SMTPException("fail")

    monkeypatch.setattr(mailer.smtplib, "SMTP", _BadSMTP)

    with pytest.raises(mailer.smtplib.SMTPException):
        notifier._send_smtp(
            host="smtp.example.com",
            port=587,
            sender="sender@example.com",
            recipients=["rcpt@example.com"],
            message=object(),
            username="sender@example.com",
            password=smtp_test_password,
        )
