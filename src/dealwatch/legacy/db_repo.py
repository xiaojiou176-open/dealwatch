from __future__ import annotations

import asyncio
import logging
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import AsyncIterator, Final

import aiosqlite

from dealwatch.core.models import Offer, RunStats
from dealwatch.infra.config import Settings, migrate_default_legacy_storage, settings
from dealwatch.infra import migrations


#########################################################
# SQL Constants
#########################################################
_SQLITE_TIMEOUT: Final[int] = 30
_BUSY_TIMEOUT_MS: Final[int] = _SQLITE_TIMEOUT * 1000
_RETRY_ATTEMPTS: Final[int] = 3
_RETRY_DELAY_BASE: Final[float] = 0.2
_SCHEMA_AUDIT_TABLE_SQL: Final[str] = """
SELECT name FROM sqlite_master WHERE type='table';
"""
_REQUIRED_SCHEMA: Final[dict[str, set[str]]] = {
    "schema_version": {"id", "version", "applied_at"},
    "products": {"id", "store_id", "product_key", "url", "title", "last_updated"},
    "price_history": {
        "id",
        "store_id",
        "product_key",
        "price",
        "original_price",
        "context_hash",
        "timestamp",
    },
    "runs": {
        "id",
        "store_id",
        "start_time",
        "discovered_count",
        "parsed_count",
        "error_count",
        "confirmed_deals_count",
        "skipped_count",
    },
}

_CREATE_SCHEMA_VERSION_TABLE: Final[str] = """
CREATE TABLE IF NOT EXISTS schema_version (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    version INTEGER NOT NULL,
    applied_at TEXT NOT NULL
);
"""

_SELECT_SCHEMA_VERSION: Final[str] = """
SELECT version FROM schema_version WHERE id = 1;
"""

_INSERT_SCHEMA_VERSION: Final[str] = """
INSERT INTO schema_version (id, version, applied_at)
VALUES (1, ?, ?);
"""

_UPDATE_SCHEMA_VERSION: Final[str] = """
UPDATE schema_version SET version = ?, applied_at = ? WHERE id = 1;
"""

_CREATE_PRODUCTS_TABLE: Final[str] = """
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id TEXT NOT NULL,
    product_key TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    last_updated TEXT NOT NULL
);
"""

_CREATE_PRICE_HISTORY_TABLE: Final[str] = """
CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id TEXT NOT NULL,
    product_key TEXT NOT NULL,
    price REAL NOT NULL,
    original_price REAL,
    context_hash TEXT NOT NULL,
    timestamp TEXT NOT NULL
);
"""

_CREATE_PRODUCTS_INDEX: Final[str] = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_products_store_product
ON products (store_id, product_key);
"""

_CREATE_PRICE_HISTORY_INDEX: Final[str] = """
CREATE INDEX IF NOT EXISTS idx_price_history_store_product_context_time
ON price_history (store_id, product_key, context_hash, timestamp DESC);
"""

_CREATE_RUNS_TABLE: Final[str] = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id TEXT NOT NULL,
    start_time TEXT NOT NULL,
    discovered_count INTEGER NOT NULL,
    parsed_count INTEGER NOT NULL,
    error_count INTEGER NOT NULL,
    confirmed_deals_count INTEGER NOT NULL,
    skipped_count INTEGER NOT NULL DEFAULT 0
);
"""

_CREATE_RUNS_INDEX: Final[str] = """
CREATE INDEX IF NOT EXISTS idx_runs_store_time
ON runs (store_id, start_time DESC);
"""

_UPSERT_PRODUCT: Final[str] = """
INSERT OR REPLACE INTO products
    (store_id, product_key, url, title, last_updated)
VALUES (?, ?, ?, ?, ?);
"""

_INSERT_PRICE_POINT: Final[str] = """
INSERT INTO price_history
    (store_id, product_key, price, original_price, context_hash, timestamp)
VALUES (?, ?, ?, ?, ?, ?);
"""

_SELECT_LAST_PRICE: Final[str] = """
SELECT price
FROM price_history
WHERE store_id = ? AND product_key = ? AND context_hash = ?
ORDER BY timestamp DESC
LIMIT 1;
"""

_SELECT_LAST_PRICE_RECENT: Final[str] = """
SELECT price
FROM price_history
WHERE store_id = ? AND product_key = ? AND context_hash = ? AND timestamp >= ?
ORDER BY timestamp DESC
LIMIT 1;
"""

_SELECT_HISTORICAL_LOW: Final[str] = """
SELECT MIN(price) AS min_price
FROM price_history
WHERE store_id = ? AND product_key = ? AND context_hash = ?;
"""

_SELECT_PRICE_SERIES: Final[str] = """
SELECT price
FROM price_history
WHERE store_id = ? AND product_key = ? AND context_hash = ? AND timestamp >= ?
ORDER BY timestamp DESC
LIMIT ?;
"""

_SELECT_PRODUCT_STORE_COUNT: Final[str] = """
SELECT COUNT(DISTINCT store_id) AS store_count, MIN(store_id) AS store_id
FROM products
WHERE product_key = ?;
"""

_INSERT_RUN: Final[str] = """
INSERT INTO runs
    (store_id, start_time, discovered_count, parsed_count, error_count, confirmed_deals_count, skipped_count)
VALUES (?, ?, ?, ?, ?, ?, ?);
"""

_SELECT_RUNS_RECENT: Final[str] = """
SELECT store_id, start_time, discovered_count, parsed_count, error_count, confirmed_deals_count, skipped_count
FROM runs
ORDER BY start_time DESC
LIMIT ?;
"""
_DELETE_OLD_PRICE_HISTORY: Final[str] = """
WITH ranked AS (
    SELECT
        id,
        store_id,
        product_key,
        context_hash,
        price,
        timestamp,
        ROW_NUMBER() OVER (
            PARTITION BY store_id, product_key, context_hash
            ORDER BY timestamp DESC, id DESC
        ) AS rn_latest,
        ROW_NUMBER() OVER (
            PARTITION BY store_id, product_key, context_hash
            ORDER BY price ASC, timestamp DESC, id DESC
        ) AS rn_low
    FROM price_history
),
keep_ids AS (
    SELECT id FROM ranked WHERE rn_latest = 1
    UNION
    SELECT id FROM ranked WHERE rn_low = 1
)
DELETE FROM price_history
WHERE timestamp < ?
  AND id NOT IN (SELECT id FROM keep_ids);
"""

_ALTER_PRICE_HISTORY_ADD_STORE: Final[str] = """
ALTER TABLE price_history ADD COLUMN store_id TEXT NOT NULL DEFAULT 'legacy';
"""

_BACKFILL_PRICE_HISTORY_STORE: Final[str] = """
WITH unique_products AS (
    SELECT product_key, MIN(store_id) AS store_id
    FROM products
    GROUP BY product_key
    HAVING COUNT(DISTINCT store_id) = 1
)
UPDATE price_history
SET store_id = (
    SELECT store_id
    FROM unique_products up
    WHERE up.product_key = price_history.product_key
)
WHERE store_id = 'legacy';
"""

_ALTER_RUNS_ADD_SKIPPED: Final[str] = """
ALTER TABLE runs ADD COLUMN skipped_count INTEGER NOT NULL DEFAULT 0;
"""

#########################################################
# Repository
#########################################################
class DatabaseRepository:
    def __init__(self, db_path: Path | str | None = None) -> None:
        self._logger = logging.getLogger(__name__)
        self._db_path = self._resolve_db_path(db_path)
        migrate_default_legacy_storage(db_path=self._db_path, backups_dir=settings.BACKUPS_DIR)
        self._logger.warning(
            "DatabaseRepository uses the deprecated SQLite legacy bridge at %s; product runtime should use PostgreSQL.",
            self._db_path,
        )

        try:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._logger.exception("Failed to create database directory: %s", exc)
            raise

        # Schema initialization is async; call initialize() before use.

    async def initialize(self) -> None:
        await self._initialize_schema()

    #########################################################
    # Public API
    #########################################################
    @property
    def db_path(self) -> Path:
        return self._db_path

    async def backup_db(self, backup_dir: Path | None = None) -> Path | None:
        target_dir = backup_dir or settings.BACKUPS_DIR

        def _backup() -> Path | None:
            if not self._db_path.exists():
                self._logger.warning("Database file does not exist: %s", self._db_path)
                return None

            try:
                target_dir.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                self._logger.exception("Failed to create backup dir: %s", exc)
                return None

            stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            backup_path = target_dir / f"{self._db_path.stem}_{stamp}{self._db_path.suffix}"

            try:
                with sqlite3.connect(str(self._db_path)) as source:
                    with sqlite3.connect(str(backup_path)) as dest:
                        source.backup(dest)
            except sqlite3.Error as exc:
                self._logger.exception("Failed to backup database: %s", exc)
                return None

            return backup_path

        return await asyncio.to_thread(_backup)

    async def audit_schema(self) -> list[str]:
        issues: list[str] = []

        try:
            async with self._connect() as conn:
                cursor = await conn.execute(_SCHEMA_AUDIT_TABLE_SQL)
                rows = await cursor.fetchall()
                tables = {row["name"] for row in rows}

                for table, required_cols in _REQUIRED_SCHEMA.items():
                    if table not in tables:
                        issues.append(f"missing_table:{table}")
                        continue

                    cursor = await conn.execute(f"PRAGMA table_info({table});")
                    columns = {row["name"] for row in await cursor.fetchall()}
                    missing = sorted(required_cols - columns)
                    for col in missing:
                        issues.append(f"missing_column:{table}.{col}")
        except sqlite3.Error as exc:
            self._logger.exception("Failed to audit schema: %s", exc)
            issues.append("schema_audit_failed")

        return issues
    async def upsert_product(self, offer: Offer) -> None:
        payload = (
            offer.store_id,
            offer.product_key,
            offer.url,
            offer.title,
            offer.fetch_at.isoformat(),
        )

        try:
            async with self._connect() as conn:
                await self._execute_with_retry(conn, _UPSERT_PRODUCT, payload)
        except sqlite3.Error as exc:
            self._logger.exception("Failed to upsert product: %s", exc)
            raise

    async def insert_price_point(self, offer: Offer) -> None:
        self._validate_price_point(offer)
        context_hash = offer.context.get_hash()
        payload = (
            offer.store_id,
            offer.product_key,
            offer.price,
            offer.original_price,
            context_hash,
            offer.fetch_at.isoformat(),
        )

        try:
            async with self._connect() as conn:
                await self._execute_with_retry(conn, _INSERT_PRICE_POINT, payload)
        except sqlite3.Error as exc:
            self._logger.exception("Failed to insert price point: %s", exc)
            raise

    async def insert_run_stats(self, stats: RunStats) -> None:
        payload = (
            stats.store_id,
            stats.start_time.isoformat(),
            stats.discovered_count,
            stats.parsed_count,
            stats.error_count,
            stats.confirmed_deals_count,
            stats.skipped_count,
        )

        try:
            async with self._connect() as conn:
                await self._execute_with_retry(conn, _INSERT_RUN, payload)
        except sqlite3.Error as exc:
            self._logger.exception("Failed to insert run stats: %s", exc)
            raise

    async def get_recent_runs(self, limit: int = 50) -> list[RunStats]:
        safe_limit = max(int(limit), 1)
        try:
            async with self._connect() as conn:
                cursor = await self._execute_with_retry(
                    conn,
                    _SELECT_RUNS_RECENT,
                    (safe_limit,),
                )
                rows = await cursor.fetchall()
        except sqlite3.Error as exc:
            self._logger.exception("Failed to fetch recent runs: %s", exc)
            return []

        runs: list[RunStats] = []
        for row in rows:
            try:
                runs.append(
                    RunStats(
                        store_id=str(row["store_id"]),
                        start_time=datetime.fromisoformat(str(row["start_time"])),
                        discovered_count=int(row["discovered_count"] or 0),
                        parsed_count=int(row["parsed_count"] or 0),
                        error_count=int(row["error_count"] or 0),
                        confirmed_deals_count=int(row["confirmed_deals_count"] or 0),
                        skipped_count=int(row["skipped_count"] or 0),
                    )
                )
            except Exception as exc:
                self._logger.warning("Failed to parse run stats row: %s", exc)
                continue

        return runs

    async def cleanup_price_history(self, older_than_days: int = 180) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        cutoff_iso = cutoff.isoformat()

        try:
            async with self._connect() as conn:
                cursor = await self._execute_with_retry(
                    conn,
                    _DELETE_OLD_PRICE_HISTORY,
                    (cutoff_iso,),
                )
                return cursor.rowcount
        except sqlite3.Error as exc:
            self._logger.exception("Failed to cleanup price history: %s", exc)
            raise

    async def vacuum(self) -> None:
        try:
            async with aiosqlite.connect(
                str(self._db_path),
                timeout=_SQLITE_TIMEOUT,
                isolation_level=None,
            ) as conn:
                await conn.execute("VACUUM;")
        except sqlite3.Error as exc:
            self._logger.exception("Failed to vacuum database: %s", exc)
            raise

    async def close(self) -> None:
        """No-op placeholder for compatibility with callers."""
        return None

    async def get_last_price(
        self,
        store_id: str,
        product_key: str,
        context_hash: str,
        max_age_days: int | None = None,
    ) -> float | None:
        """Return the most recent historical price for a product context."""
        effective_age = settings.PRICE_HISTORY_KEEP_DAYS if max_age_days is None else max_age_days
        cutoff_iso: str | None = None
        if effective_age and effective_age > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(days=effective_age)
            cutoff_iso = cutoff.isoformat()

        try:
            async with self._connect() as conn:
                if cutoff_iso is None:
                    cursor = await self._execute_with_retry(
                        conn,
                        _SELECT_LAST_PRICE,
                        (store_id, product_key, context_hash),
                    )
                else:
                    cursor = await self._execute_with_retry(
                        conn,
                        _SELECT_LAST_PRICE_RECENT,
                        (store_id, product_key, context_hash, cutoff_iso),
                    )
                row = await cursor.fetchone()
                if (
                    row is None
                    and settings.ENABLE_LEGACY_FALLBACK
                    and await self._can_use_legacy_fallback(conn, store_id, product_key)
                ):
                    if cutoff_iso is None:
                        cursor = await self._execute_with_retry(
                            conn,
                            _SELECT_LAST_PRICE,
                            ("legacy", product_key, context_hash),
                        )
                    else:
                        cursor = await self._execute_with_retry(
                            conn,
                            _SELECT_LAST_PRICE_RECENT,
                            ("legacy", product_key, context_hash, cutoff_iso),
                        )
                    row = await cursor.fetchone()
                    if row is not None:
                        self._logger.info(
                            "Using explicitly enabled legacy fallback bridge for store=%s product=%s",
                            store_id,
                            product_key,
                        )
        except sqlite3.Error as exc:
            self._logger.exception("Failed to fetch last price: %s", exc)
            return None

        if row is None:
            return None

        return float(row["price"])

    async def get_historical_low(
        self,
        store_id: str,
        product_key: str,
        context_hash: str,
    ) -> float | None:
        """Return the historical low price for a product context."""
        try:
            async with self._connect() as conn:
                cursor = await self._execute_with_retry(
                    conn,
                    _SELECT_HISTORICAL_LOW,
                    (store_id, product_key, context_hash),
                )
                row = await cursor.fetchone()
                if (
                    (row is None or row["min_price"] is None)
                    and settings.ENABLE_LEGACY_FALLBACK
                    and await self._can_use_legacy_fallback(conn, store_id, product_key)
                ):
                    cursor = await self._execute_with_retry(
                        conn,
                        _SELECT_HISTORICAL_LOW,
                        ("legacy", product_key, context_hash),
                    )
                    row = await cursor.fetchone()
        except sqlite3.Error as exc:
            self._logger.exception("Failed to fetch historical low: %s", exc)
            return None

        if row is None or row["min_price"] is None:
            return None

        return float(row["min_price"])

    async def get_price_series(
        self,
        store_id: str,
        product_key: str,
        context_hash: str,
        lookback_days: int = 90,
        limit: int = 30,
    ) -> list[float]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        cutoff_iso = cutoff.isoformat()

        try:
            async with self._connect() as conn:
                cursor = await self._execute_with_retry(
                    conn,
                    _SELECT_PRICE_SERIES,
                    (store_id, product_key, context_hash, cutoff_iso, limit),
                )
                rows = await cursor.fetchall()
        except sqlite3.Error as exc:
            self._logger.exception("Failed to fetch price series: %s", exc)
            return []

        return [float(row["price"]) for row in rows if row["price"] is not None]

    async def get_schema_version(self) -> int | None:
        try:
            async with self._connect() as conn:
                cursor = await conn.execute(_SELECT_SCHEMA_VERSION)
                row = await cursor.fetchone()
        except sqlite3.Error as exc:
            self._logger.exception("Failed to fetch schema version: %s", exc)
            return None

        if row is None:
            return None
        return int(row["version"])

    async def check_schema_version(self) -> str | None:
        expected = migrations.get_schema_version_target()
        current = await self.get_schema_version()
        if current is None:
            return "schema_version_missing"
        if current != expected:
            return f"schema_version_mismatch:{current}->{expected}"
        return None

    #########################################################
    # Internal
    #########################################################
    @staticmethod
    def _resolve_db_path(db_path: Path | str | None) -> Path:
        if db_path is None:
            return settings.DB_PATH

        return Settings._normalize_path(db_path)

    async def _initialize_schema(self) -> None:
        try:
            async with self._connect() as conn:
                await conn.execute(_CREATE_SCHEMA_VERSION_TABLE)
                await conn.execute(_CREATE_PRODUCTS_TABLE)
                await conn.execute(_CREATE_PRICE_HISTORY_TABLE)
                await self._ensure_price_history_store_id(conn)
                await conn.execute(_CREATE_PRODUCTS_INDEX)
                await conn.execute(_CREATE_PRICE_HISTORY_INDEX)
                await conn.execute(_CREATE_RUNS_TABLE)
                await self._ensure_runs_skipped_count(conn)
                await conn.execute(_CREATE_RUNS_INDEX)
                await self._ensure_schema_version(conn)
        except sqlite3.Error as exc:
            self._logger.exception("Failed to initialize database schema: %s", exc)
            raise

    async def _apply_pragmas(self, conn: aiosqlite.Connection) -> None:
        await conn.execute("PRAGMA journal_mode=WAL;")
        await conn.execute(f"PRAGMA busy_timeout={_BUSY_TIMEOUT_MS};")

    @asynccontextmanager
    async def _connect(self) -> AsyncIterator[aiosqlite.Connection]:
        conn = await aiosqlite.connect(
            str(self._db_path),
            timeout=_SQLITE_TIMEOUT,
        )
        conn.row_factory = aiosqlite.Row

        try:
            await self._apply_pragmas(conn)
            yield conn
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise
        finally:
            await conn.close()

    async def _ensure_price_history_store_id(
        self,
        conn: aiosqlite.Connection,
    ) -> None:
        cursor = await conn.execute("PRAGMA table_info(price_history);")
        rows = await cursor.fetchall()
        columns = [row["name"] for row in rows]
        if "store_id" in columns:
            return

        await conn.execute(_ALTER_PRICE_HISTORY_ADD_STORE)
        try:
            await conn.execute(_BACKFILL_PRICE_HISTORY_STORE)
        except sqlite3.Error as exc:
            self._logger.warning("Failed to backfill price_history store_id: %s", exc)

    async def _ensure_runs_skipped_count(
        self,
        conn: aiosqlite.Connection,
    ) -> None:
        cursor = await conn.execute("PRAGMA table_info(runs);")
        rows = await cursor.fetchall()
        columns = [row["name"] for row in rows]
        if "skipped_count" in columns:
            return

        await conn.execute(_ALTER_RUNS_ADD_SKIPPED)

    async def _ensure_schema_version(self, conn: aiosqlite.Connection) -> None:
        cursor = await conn.execute(_SELECT_SCHEMA_VERSION)
        row = await cursor.fetchone()
        if row is None:
            detected = await self._detect_schema_version(conn)
            await conn.execute(
                _INSERT_SCHEMA_VERSION,
                (detected, datetime.now(timezone.utc).isoformat()),
            )
            current = detected
        else:
            current = int(row["version"])

        target = migrations.get_schema_version_target()
        if current >= target:
            return

        await self._apply_migrations(conn, current, target)

    async def _detect_schema_version(self, conn: aiosqlite.Connection) -> int:
        version = 1

        cursor = await conn.execute("PRAGMA table_info(price_history);")
        rows = await cursor.fetchall()
        columns = {row["name"] for row in rows}
        if "store_id" in columns:
            version = max(version, 2)

        cursor = await conn.execute("PRAGMA table_info(runs);")
        rows = await cursor.fetchall()
        columns = {row["name"] for row in rows}
        if "skipped_count" in columns:
            version = max(version, 3)

        return version

    async def _apply_migrations(
        self,
        conn: aiosqlite.Connection,
        current: int,
        target: int,
    ) -> None:
        for next_version in range(current + 1, target + 1):
            if next_version == 2:
                await self._ensure_price_history_store_id(conn)
            if next_version == 3:
                await self._ensure_runs_skipped_count(conn)

            await conn.execute(
                _UPDATE_SCHEMA_VERSION,
                (next_version, datetime.now(timezone.utc).isoformat()),
            )

    async def _can_use_legacy_fallback(
        self,
        conn: aiosqlite.Connection,
        store_id: str,
        product_key: str,
    ) -> bool:
        if store_id == "legacy":
            return False

        try:
            cursor = await self._execute_with_retry(
                conn,
                _SELECT_PRODUCT_STORE_COUNT,
                (product_key,),
            )
            row = await cursor.fetchone()
        except sqlite3.Error as exc:
            self._logger.warning(
                "Failed to check product uniqueness for legacy fallback: %s",
                exc,
            )
            return False

        if row is None:
            return False

        store_count = int(row["store_count"] or 0)
        unique_store = str(row["store_id"] or "").strip()

        return store_count == 1 and unique_store == store_id

    async def _execute_with_retry(
        self,
        conn: aiosqlite.Connection,
        sql: str,
        params: tuple[object, ...],
    ) -> aiosqlite.Cursor:
        for attempt in range(1, _RETRY_ATTEMPTS + 1):
            try:
                return await conn.execute(sql, params)
            except sqlite3.OperationalError as exc:
                if not self._is_locked_error(exc):
                    raise
                if attempt >= _RETRY_ATTEMPTS:
                    raise
                await asyncio.sleep(_RETRY_DELAY_BASE * attempt)

        raise RuntimeError("SQLite retry reached unreachable state")

    @staticmethod
    def _is_locked_error(exc: sqlite3.OperationalError) -> bool:
        message = str(exc).lower()
        return "locked" in message or "busy" in message

    def _validate_price_point(self, offer: Offer) -> None:
        if offer.price < 0:
            raise ValueError("price_must_be_non_negative")
        if offer.original_price is not None and offer.original_price < offer.price:
            raise ValueError("original_price_lt_price")
