from __future__ import annotations

import contextvars
import logging
import shutil
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Annotated
from typing import Final
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


#########################################################
# Paths & Defaults
#########################################################
PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
DEFAULT_RUNTIME_DIR: Final[Path] = PROJECT_ROOT / ".runtime-cache"
DEFAULT_CACHE_DIR: Final[Path] = DEFAULT_RUNTIME_DIR / "cache"
DEFAULT_OPERATOR_DIR: Final[Path] = DEFAULT_RUNTIME_DIR / "operator"
DEFAULT_PREVIOUS_LEGACY_DATA_DIR: Final[Path] = DEFAULT_CACHE_DIR / "data"
DEFAULT_PREVIOUS_BACKUPS_DIR: Final[Path] = DEFAULT_CACHE_DIR / "backups"
DEFAULT_RUNS_DIR: Final[Path] = DEFAULT_RUNTIME_DIR / "runs"
DEFAULT_REPORTS_DIR: Final[Path] = DEFAULT_RUNS_DIR / "reports"
DEFAULT_STORAGE_STATE_DIR: Final[Path] = DEFAULT_CACHE_DIR / "state"
DEFAULT_LOGS_DIR: Final[Path] = DEFAULT_RUNTIME_DIR / "logs"
DEFAULT_MAINTENANCE_LOCK_PATH: Final[Path] = DEFAULT_RUNTIME_DIR / "maintenance.lock"
DEFAULT_EXTERNAL_CACHE_DIR: Final[Path] = Path("~/.cache/dealwatch").expanduser()
DEFAULT_DEDICATED_CHROME_USER_DATA_DIR: Final[Path] = (
    DEFAULT_EXTERNAL_CACHE_DIR / "browser" / "chrome-user-data"
)
DEFAULT_BROWSER_DEBUG_BUNDLE_DIR: Final[Path] = DEFAULT_OPERATOR_DIR / "browser-debug"
DEFAULT_LEGACY_DIR: Final[Path] = PROJECT_ROOT / ".legacy-runtime"
DEFAULT_LEGACY_DATA_DIR: Final[Path] = DEFAULT_LEGACY_DIR / "data"
DEFAULT_LEGACY_BACKUPS_DIR: Final[Path] = DEFAULT_LEGACY_DIR / "backups"
DEFAULT_DB_PATH: Final[Path] = DEFAULT_LEGACY_DATA_DIR / "dealwatch.db"
DEFAULT_BACKUPS_DIR: Final[Path] = DEFAULT_LEGACY_BACKUPS_DIR
DEFAULT_PREVIOUS_DB_PATH: Final[Path] = DEFAULT_PREVIOUS_LEGACY_DATA_DIR / "dealwatch.db"
DEFAULT_ENV_FILE: Final[Path] = PROJECT_ROOT / ".env"
DEFAULT_CONFIG_FILE: Final[Path] = PROJECT_ROOT / "config.yaml"

LOG_FORMAT: Final[str] = "%(asctime)s | %(levelname)s | %(service_name)s | %(correlation_id)s | %(name)s | %(message)s"
DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"
DEFAULT_SERVICE_NAME: Final[str] = "dealwatch"
DEFAULT_CORRELATION_ID: Final[str] = "-"
_SERVICE_NAME_VAR: Final[contextvars.ContextVar[str]] = contextvars.ContextVar(
    "dealwatch_service_name",
    default=DEFAULT_SERVICE_NAME,
)
_CORRELATION_ID_VAR: Final[contextvars.ContextVar[str]] = contextvars.ContextVar(
    "dealwatch_correlation_id",
    default=DEFAULT_CORRELATION_ID,
)


#########################################################
# Settings
#########################################################
class Settings(BaseSettings):
    DB_PATH: Path = Field(default=DEFAULT_DB_PATH)
    DATABASE_URL: str = "postgresql+psycopg://dealwatch:dealwatch@localhost:5432/dealwatch"
    RUNS_DIR: Path = Field(default=DEFAULT_RUNS_DIR)
    REPORTS_DIR: Path = Field(default=DEFAULT_REPORTS_DIR)
    STORAGE_STATE_DIR: Path = Field(default=DEFAULT_STORAGE_STATE_DIR)
    BACKUPS_DIR: Path = Field(default=DEFAULT_BACKUPS_DIR)
    LOGS_DIR: Path = Field(default=DEFAULT_LOGS_DIR)
    OPERATOR_ARTIFACTS_DIR: Path = Field(default=DEFAULT_OPERATOR_DIR)
    EXTERNAL_CACHE_DIR: Path = Field(default=DEFAULT_EXTERNAL_CACHE_DIR)
    BROWSER_DEBUG_BUNDLE_DIR: Path = Field(default=DEFAULT_BROWSER_DEBUG_BUNDLE_DIR)
    MAINTENANCE_LOCK_PATH: Path = Field(default=DEFAULT_MAINTENANCE_LOCK_PATH)
    PLAYWRIGHT_HEADLESS: bool = True
    CHROME_CDP_URL: str = ""
    CHROME_REMOTE_DEBUG_PORT: int = 9222
    CHROME_USER_DATA_DIR: str = ""
    CHROME_PROFILE_NAME: str = ""
    CHROME_PROFILE_DIRECTORY: str = ""
    CHROME_ATTACH_MODE: str = "browser"
    CHROME_START_URL: str = ""
    CHROME_OBSERVE_MS: int = 750
    ZIP_CODE: str = "00000"
    LLM_API_KEY: SecretStr = SecretStr("")
    USE_LLM: bool = False
    AI_PROVIDER: str = "disabled"
    AI_MODEL: str = ""
    AI_BASE_URL: str = ""
    AI_SWITCHYARD_PROVIDER: str = ""
    AI_SWITCHYARD_LANE: str = "byok"
    AI_TIMEOUT_SECONDS: float = 8.0
    AI_COMPARE_EXPLAIN_ENABLED: bool = False
    AI_GROUP_EXPLAIN_ENABLED: bool = False
    AI_RECOVERY_COPILOT_ENABLED: bool = False
    SMTP_HOST: str = "localhost"
    SMTP_USER: str = ""
    POSTMARK_SERVER_TOKEN: SecretStr = SecretStr("")
    POSTMARK_WEBHOOK_TOKEN: SecretStr = SecretStr("")
    POSTMARK_MESSAGE_STREAM: str = "outbound"
    OWNER_EMAIL: str = "owner@example.com"
    OWNER_DISPLAY_NAME: str = "DealWatch Owner"
    OWNER_BOOTSTRAP_TOKEN: SecretStr = SecretStr("")
    APP_BASE_URL: str = "http://127.0.0.1:8000"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    PORT: int | None = None
    WEBUI_DEV_URL: str = "http://127.0.0.1:5173"
    PRODUCT_AUTO_CREATE_SCHEMA: bool = Field(
        default=False,
        description="Temporary SQLite/bootstrap bridge. Disabled by default for the product runtime.",
    )
    POSTMARK_FROM_EMAIL: str = "dealwatch@example.com"
    LOG_LEVEL: str = "INFO"
    LOG_MAX_BYTES: int = 1_000_000
    LOG_BACKUP_COUNT: int = 5
    LOG_RETENTION_DAYS: int = 14
    CACHE_BUDGET_BYTES: int = 4_294_967_296
    ENABLED_STORES: Annotated[list[str], NoDecode] = Field(default_factory=list)
    PROXY_SERVER: str = ""
    PLAYWRIGHT_BLOCK_STYLESHEETS: bool = True
    ENABLE_LEGACY_FALLBACK: bool = Field(
        default=False,
        description="Deprecated SQLite read fallback bridge. Disabled unless explicitly re-enabled.",
    )
    RULE_MIN_DROP_AMOUNT: float = 0.05
    RULE_MIN_DROP_PCT: float = 1.0
    VALIDATOR_MIN_PRICE: float = 0.0
    VALIDATOR_MAX_PRICE: float = 1000.0
    VALIDATOR_MIN_TITLE_LENGTH: int = 6
    ANOMALY_ENABLED: bool = True
    ANOMALY_MARK_ONLY: bool = False
    ANOMALY_LOOKBACK_DAYS: int = 90
    ANOMALY_MAX_SAMPLES: int = 30
    ANOMALY_MIN_SAMPLES: int = 8
    ANOMALY_IQR_MULTIPLIER: float = 3.0
    ANOMALY_ZSCORE_THRESHOLD: float = 4.0
    ANOMALY_ZERO_VAR_PCT: float = 0.5
    ANOMALY_ZERO_VAR_ABS: float = 1.0
    PLAYWRIGHT_RETRY_BUDGET: int = 0
    PRICE_HISTORY_KEEP_DAYS: int = 180
    RUNS_KEEP_DAYS: int = 30
    REPORTS_KEEP_DAYS: int = 30
    BACKUPS_KEEP_DAYS: int = 30
    WORKER_POLL_SECONDS: int = 60
    MAINTENANCE_ENABLED: bool = True
    MAINTENANCE_HOUR_LOCAL: int = 3
    MAINTENANCE_MINUTE_LOCAL: int = 15
    DEFAULT_TASK_CADENCE_MINUTES: int = 720
    DEFAULT_NOTIFICATION_COOLDOWN_MINUTES: int = 240
    DEFAULT_THRESHOLD_TYPE: str = "price_below"

    model_config = SettingsConfigDict(
        env_file=DEFAULT_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @staticmethod
    def _normalize_path(value: Path | str) -> Path:
        if isinstance(value, Path):
            raw_path = value.expanduser()
        else:
            raw_path = Path(value).expanduser()

        if raw_path.is_absolute():
            return raw_path

        return (PROJECT_ROOT / raw_path).resolve()

    @field_validator("DB_PATH", mode="before")
    @classmethod
    def _validate_db_path(cls, value: Path | str) -> Path:
        return cls._normalize_path(value)

    @field_validator(
        "RUNS_DIR",
        "REPORTS_DIR",
        "STORAGE_STATE_DIR",
        "BACKUPS_DIR",
        "LOGS_DIR",
        "OPERATOR_ARTIFACTS_DIR",
        "EXTERNAL_CACHE_DIR",
        "BROWSER_DEBUG_BUNDLE_DIR",
        "MAINTENANCE_LOCK_PATH",
        mode="before",
    )
    @classmethod
    def _validate_path_fields(cls, value: Path | str) -> Path:
        return cls._normalize_path(value)

    @field_validator("ENABLED_STORES", mode="before")
    @classmethod
    def _normalize_enabled_stores(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            raw = value.replace(";", ",")
            return [item.strip() for item in raw.split(",") if item.strip()]
        if isinstance(value, (list, tuple, set)):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    @field_validator("CACHE_BUDGET_BYTES", mode="before")
    @classmethod
    def _validate_cache_budget_bytes(cls, value: object) -> int:
        if value is None or str(value).strip() == "":
            return 4_294_967_296
        numeric = int(value)
        if numeric < 1:
            raise ValueError("CACHE_BUDGET_BYTES must be greater than or equal to 1.")
        return numeric

    def build_storage_state_path(self, zip_code: str | None = None) -> Path:
        raw_zip = str(zip_code or self.ZIP_CODE or "").strip()
        safe = "".join(ch for ch in raw_zip if ch.isalnum())
        if not safe:
            safe = "default"
        return self.STORAGE_STATE_DIR / f"storage_state_{safe}.json"

    def build_operator_artifact_path(self, *parts: str) -> Path:
        path = self.OPERATOR_ARTIFACTS_DIR
        for part in parts:
            path /= part
        return path

    def build_external_cache_path(self, *parts: str) -> Path:
        path = self.EXTERNAL_CACHE_DIR
        for part in parts:
            path /= part
        return path

    def redacted(self) -> dict[str, object]:
        payload = self.model_dump()
        for key in ("LLM_API_KEY", "POSTMARK_SERVER_TOKEN", "POSTMARK_WEBHOOK_TOKEN", "OWNER_BOOTSTRAP_TOKEN"):
            secret = payload.get(key)
            if isinstance(secret, SecretStr):
                payload[key] = "***"
            elif secret:
                payload[key] = "***"
        return payload


#########################################################
# Logging
#########################################################
_LEVEL_MAP: Final[dict[str, int]] = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
}


def configure_logging(log_level: str) -> None:
    normalized = str(log_level).upper().strip()
    level = _LEVEL_MAP.get(normalized, logging.INFO)
    settings.LOGS_DIR.mkdir(parents=True, exist_ok=True)

    class _RuntimeContextFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            record.service_name = _SERVICE_NAME_VAR.get()
            record.correlation_id = _CORRELATION_ID_VAR.get()
            return True

    runtime_filter = _RuntimeContextFilter()
    handlers: list[logging.Handler] = [
        logging.StreamHandler(),
        RotatingFileHandler(
            settings.LOGS_DIR / "dealwatch.log",
            maxBytes=max(int(settings.LOG_MAX_BYTES), 1),
            backupCount=max(int(settings.LOG_BACKUP_COUNT), 1),
            encoding="utf-8",
        ),
    ]
    for handler in handlers:
        handler.addFilter(runtime_filter)

    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        datefmt=DATE_FORMAT,
        handlers=handlers,
        force=True,
    )


def set_log_context(*, service_name: str | None = None, correlation_id: str | None = None) -> None:
    if service_name is not None:
        _SERVICE_NAME_VAR.set(service_name)
    if correlation_id is not None:
        _CORRELATION_ID_VAR.set(correlation_id)


def clear_log_context() -> None:
    _SERVICE_NAME_VAR.set(DEFAULT_SERVICE_NAME)
    _CORRELATION_ID_VAR.set(DEFAULT_CORRELATION_ID)


#########################################################
# Config Schema
#########################################################
class ConfigFile(BaseModel):
    enabled_stores: list[str] = Field(default_factory=list)
    database_url: str | None = None
    zip_code: str | None = None
    proxy_server: str | None = None
    playwright_headless: bool | None = None
    playwright_block_stylesheets: bool | None = None
    playwright_retry_budget: int | None = None
    rule_min_drop_amount: float | None = None
    rule_min_drop_pct: float | None = None
    validator_min_price: float | None = None
    validator_max_price: float | None = None
    validator_min_title_length: int | None = None
    anomaly_enabled: bool | None = None
    anomaly_mark_only: bool | None = None
    anomaly_lookback_days: int | None = None
    anomaly_max_samples: int | None = None
    anomaly_min_samples: int | None = None
    anomaly_iqr_multiplier: float | None = None
    anomaly_zscore_threshold: float | None = None
    anomaly_zero_var_pct: float | None = None
    anomaly_zero_var_abs: float | None = None
    price_history_keep_days: int | None = None
    runs_keep_days: int | None = None
    reports_keep_days: int | None = None
    worker_poll_seconds: int | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("enabled_stores", mode="before")
    @classmethod
    def _normalize_enabled_stores(cls, value: object) -> list[str]:
        return Settings._normalize_enabled_stores(value)


#########################################################
# Config Loader
#########################################################
def load_enabled_stores_from_yaml(path: Path | None = None) -> list[str]:
    target = path or DEFAULT_CONFIG_FILE
    logger = logging.getLogger(__name__)

    if not target.exists():
        return []

    try:
        import yaml
    except ImportError:
        logger.warning("PyYAML not installed, falling back to legacy parser.")
        return _load_enabled_stores_legacy(target, logger)

    try:
        raw = target.read_text(encoding="utf-8")
        data = yaml.safe_load(raw)
    except Exception as exc:
        logger.warning("Failed to parse config.yaml: %s", exc)
        return _load_enabled_stores_legacy(target, logger)

    if not isinstance(data, dict):
        return []

    try:
        config = ConfigFile.model_validate(data)
    except ValidationError as exc:
        logger.error("Invalid config.yaml schema: %s", exc)
        return []

    return Settings._normalize_enabled_stores(config.enabled_stores)


def _load_enabled_stores_legacy(
    target: Path,
    logger: logging.Logger,
) -> list[str]:
    try:
        lines = target.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        logger.warning("Failed to read config.yaml: %s", exc)
        return []

    enabled: list[str] = []
    in_list = False

    for raw in lines:
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue

        if line.startswith("enabled_stores"):
            in_list = True
            _, _, rest = line.partition(":")
            inline = rest.strip()
            if inline:
                if inline.startswith("[") and inline.endswith("]"):
                    items = [item.strip() for item in inline[1:-1].split(",")]
                    enabled = [
                        item.strip("\"'") for item in items if item.strip("\"'")
                    ]
                else:
                    logger.warning(
                        "Unsupported enabled_stores format in config.yaml"
                    )
                in_list = False
            continue

        if in_list:
            if line.startswith("-"):
                value = line[1:].strip().strip("\"'")
                if value:
                    enabled.append(value)
                continue
            if ":" in line:
                in_list = False

    return Settings._normalize_enabled_stores(enabled)


def migrate_default_legacy_storage(
    *,
    db_path: Path | str | None = None,
    backups_dir: Path | str | None = None,
) -> None:
    effective_db_path = Settings._normalize_path(db_path or settings.DB_PATH)
    effective_backups_dir = Settings._normalize_path(backups_dir or settings.BACKUPS_DIR)
    default_db_path = Settings._normalize_path(DEFAULT_DB_PATH)
    default_backups_dir = Settings._normalize_path(DEFAULT_BACKUPS_DIR)
    previous_db_path = Settings._normalize_path(DEFAULT_PREVIOUS_DB_PATH)
    previous_backups_dir = Settings._normalize_path(DEFAULT_PREVIOUS_BACKUPS_DIR)

    if effective_db_path == default_db_path and previous_db_path.exists() and not effective_db_path.exists():
        effective_db_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(previous_db_path), str(effective_db_path))

    if (
        effective_backups_dir == default_backups_dir
        and previous_backups_dir.exists()
        and not effective_backups_dir.exists()
    ):
        effective_backups_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(previous_backups_dir), str(effective_backups_dir))


#########################################################
# Singleton
#########################################################
settings = Settings()
configure_logging(settings.LOG_LEVEL)
