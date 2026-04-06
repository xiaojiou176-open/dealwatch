import sqlite3
from datetime import datetime, timedelta, timezone

import aiosqlite
import pytest

from dealwatch.core.models import Offer, PriceContext, RunStats
from dealwatch.legacy.db_repo import DatabaseRepository


@pytest.mark.asyncio
async def test_db_repo_ensure_columns(tmp_path) -> None:
    db_path = tmp_path / "dealwatch.db"
    repo = DatabaseRepository(db_path)

    async with aiosqlite.connect(str(db_path)) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute(
            """
            CREATE TABLE price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_key TEXT NOT NULL,
                price REAL NOT NULL,
                original_price REAL,
                context_hash TEXT NOT NULL,
                timestamp TEXT NOT NULL
            );
            """
        )
        await conn.execute(
            """
            CREATE TABLE runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                store_id TEXT NOT NULL,
                start_time TEXT NOT NULL,
                discovered_count INTEGER NOT NULL,
                parsed_count INTEGER NOT NULL,
                error_count INTEGER NOT NULL,
                confirmed_deals_count INTEGER NOT NULL
            );
            """
        )
        await repo._ensure_price_history_store_id(conn)
        await repo._ensure_runs_skipped_count(conn)

        cursor = await conn.execute("PRAGMA table_info(price_history);")
        columns = [row[1] for row in await cursor.fetchall()]
        assert "store_id" in columns

        cursor = await conn.execute("PRAGMA table_info(runs);")
        columns = [row[1] for row in await cursor.fetchall()]
        assert "skipped_count" in columns


@pytest.mark.asyncio
async def test_db_repo_execute_with_retry_handles_lock() -> None:
    class _FakeCursor:
        def __init__(self) -> None:
            self.rowcount = 1

    class _FakeConn:
        def __init__(self) -> None:
            self.calls = 0

        async def execute(self, sql: str, params: tuple):
            self.calls += 1
            if self.calls == 1:
                raise sqlite3.OperationalError("database is locked")
            return _FakeCursor()

    repo = DatabaseRepository(":memory:")
    cursor = await repo._execute_with_retry(_FakeConn(), "SELECT 1", ())
    assert cursor.rowcount == 1


def test_db_repo_resolve_db_path(tmp_path) -> None:
    repo = DatabaseRepository(tmp_path / "dealwatch.db")
    resolved = repo._resolve_db_path(None)
    assert resolved.is_absolute() is True


@pytest.mark.asyncio
async def test_db_repo_get_last_price_no_fallback(tmp_path) -> None:
    db_path = tmp_path / "dealwatch.db"
    repo = DatabaseRepository(db_path)
    await repo.initialize()

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            INSERT INTO price_history
                (store_id, product_key, price, original_price, context_hash, timestamp)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            ("legacy", "p1", 9.99, None, "ctx", datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()

    price = await repo.get_last_price("weee", "p1", "ctx")
    assert price is None


@pytest.mark.asyncio
async def test_db_repo_basic_ops(tmp_path) -> None:
    db_path = tmp_path / "dealwatch.db"
    repo = DatabaseRepository(db_path)
    await repo.initialize()

    offer = Offer(
        store_id="weee",
        product_key="p1",
        title="Test",
        url="https://example.com",
        price=2.5,
        original_price=3.0,
        fetch_at=datetime.now(timezone.utc),
        context=PriceContext(region="00000"),
        unit_price_info={},
    )

    await repo.upsert_product(offer)
    await repo.insert_price_point(offer)

    stats = RunStats(
        store_id="weee",
        start_time=datetime.now(timezone.utc),
        discovered_count=1,
        parsed_count=1,
        error_count=0,
        confirmed_deals_count=1,
        skipped_count=0,
    )
    await repo.insert_run_stats(stats)

    last_price = await repo.get_last_price("weee", "p1", offer.context.get_hash())
    assert last_price == 2.5

    low_price = await repo.get_historical_low("weee", "p1", offer.context.get_hash())
    assert low_price == 2.5

    deleted = await repo.cleanup_price_history(older_than_days=0)
    assert isinstance(deleted, int)

    await repo.vacuum()

    version = await repo.get_schema_version()
    assert isinstance(version, int)
    assert version >= 1

    series = await repo.get_price_series(
        "weee",
        "p1",
        offer.context.get_hash(),
        lookback_days=1,
        limit=10,
    )
    assert series != []


@pytest.mark.asyncio
async def test_db_repo_last_price_respects_max_age(tmp_path) -> None:
    db_path = tmp_path / "dealwatch.db"
    repo = DatabaseRepository(db_path)
    await repo.initialize()

    context_hash = PriceContext(region="00000").get_hash()
    old_ts = datetime.now(timezone.utc) - timedelta(days=10)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            INSERT INTO price_history
                (store_id, product_key, price, original_price, context_hash, timestamp)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            ("weee", "p1", 9.99, None, context_hash, old_ts.isoformat()),
        )
        conn.commit()
    finally:
        conn.close()

    stale_price = await repo.get_last_price(
        "weee",
        "p1",
        context_hash,
        max_age_days=1,
    )
    assert stale_price is None

    fresh_price = await repo.get_last_price(
        "weee",
        "p1",
        context_hash,
        max_age_days=30,
    )
    assert fresh_price == 9.99


@pytest.mark.asyncio
async def test_db_repo_insert_price_point_validation(tmp_path) -> None:
    db_path = tmp_path / "dealwatch.db"
    repo = DatabaseRepository(db_path)
    await repo.initialize()

    offer = Offer(
        store_id="weee",
        product_key="p1",
        title="Test",
        url="https://example.com",
        price=-1.0,
        original_price=None,
        fetch_at=datetime.now(timezone.utc),
        context=PriceContext(region="00000"),
        unit_price_info={},
    )
    with pytest.raises(ValueError):
        await repo.insert_price_point(offer)

    offer.price = 2.0
    offer.original_price = 1.0
    with pytest.raises(ValueError):
        await repo.insert_price_point(offer)


@pytest.mark.asyncio
async def test_db_repo_can_use_legacy_fallback(tmp_path) -> None:
    db_path = tmp_path / "dealwatch.db"
    repo = DatabaseRepository(db_path)
    await repo.initialize()

    async with repo._connect() as conn:
        assert await repo._can_use_legacy_fallback(conn, "legacy", "p1") is False
        assert await repo._can_use_legacy_fallback(conn, "weee", "p1") is False

        await conn.execute(
            """
            INSERT INTO products
                (store_id, product_key, url, title, last_updated)
            VALUES (?, ?, ?, ?, ?);
            """,
            ("weee", "p1", "https://example.com", "Test", datetime.now(timezone.utc).isoformat()),
        )
        await conn.commit()

        assert await repo._can_use_legacy_fallback(conn, "weee", "p1") is True


@pytest.mark.asyncio
async def test_db_repo_error_paths(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "dealwatch.db"
    repo = DatabaseRepository(db_path)
    await repo.initialize()

    offer = Offer(
        store_id="weee",
        product_key="p1",
        title="Test",
        url="https://example.com",
        price=2.5,
        original_price=None,
        fetch_at=datetime.now(timezone.utc),
        context=PriceContext(region="00000"),
        unit_price_info={},
    )

    stats = RunStats(
        store_id="weee",
        start_time=datetime.now(timezone.utc),
        discovered_count=1,
        parsed_count=1,
        error_count=0,
        confirmed_deals_count=0,
        skipped_count=0,
    )

    async def _raise(*args, **kwargs):
        raise sqlite3.Error("boom")

    monkeypatch.setattr(DatabaseRepository, "_execute_with_retry", _raise)

    with pytest.raises(sqlite3.Error):
        await repo.upsert_product(offer)
    with pytest.raises(sqlite3.Error):
        await repo.insert_price_point(offer)
    with pytest.raises(sqlite3.Error):
        await repo.insert_run_stats(stats)
    with pytest.raises(sqlite3.Error):
        await repo.cleanup_price_history(older_than_days=1)


@pytest.mark.asyncio
async def test_db_repo_backup_db(tmp_path) -> None:
    db_path = tmp_path / "dealwatch.db"
    repo = DatabaseRepository(db_path)
    await repo.initialize()

    backup_dir = tmp_path / "backups"
    backup = await repo.backup_db(backup_dir)
    assert backup is not None
    assert backup.exists() is True
    assert backup.stat().st_size > 0


@pytest.mark.asyncio
async def test_db_repo_backup_db_missing(tmp_path) -> None:
    db_path = tmp_path / "missing.db"
    repo = DatabaseRepository(db_path)

    backup = await repo.backup_db(tmp_path / "backups")
    assert backup is None


@pytest.mark.asyncio
async def test_db_repo_audit_schema_missing_tables(tmp_path) -> None:
    db_path = tmp_path / "dealwatch.db"

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                store_id TEXT NOT NULL,
                product_key TEXT NOT NULL,
                url TEXT NOT NULL,
                title TEXT NOT NULL,
                last_updated TEXT NOT NULL
            );
            """
        )
        conn.commit()
    finally:
        conn.close()

    repo = DatabaseRepository(db_path)
    issues = await repo.audit_schema()
    assert "missing_table:price_history" in issues
    assert "missing_table:runs" in issues


@pytest.mark.asyncio
async def test_db_repo_audit_schema_missing_columns(tmp_path) -> None:
    db_path = tmp_path / "dealwatch.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE schema_version (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                version INTEGER NOT NULL,
                applied_at TEXT NOT NULL
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                store_id TEXT NOT NULL,
                product_key TEXT NOT NULL,
                url TEXT NOT NULL
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                store_id TEXT NOT NULL,
                product_key TEXT NOT NULL,
                price REAL NOT NULL,
                context_hash TEXT NOT NULL,
                timestamp TEXT NOT NULL
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                store_id TEXT NOT NULL,
                start_time TEXT NOT NULL,
                discovered_count INTEGER NOT NULL,
                parsed_count INTEGER NOT NULL,
                error_count INTEGER NOT NULL,
                confirmed_deals_count INTEGER NOT NULL
            );
            """
        )
        conn.commit()
    finally:
        conn.close()

    repo = DatabaseRepository(db_path)
    issues = await repo.audit_schema()
    assert "missing_column:products.title" in issues
    assert "missing_column:products.last_updated" in issues
    assert "missing_column:price_history.original_price" in issues
    assert "missing_column:runs.skipped_count" in issues


@pytest.mark.asyncio
async def test_db_repo_audit_schema_error(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "dealwatch.db"
    repo = DatabaseRepository(db_path)

    class _BadConn:
        async def __aenter__(self):
            raise sqlite3.Error("boom")

        async def __aexit__(self, exc_type, exc, tb):
            return None

    monkeypatch.setattr(DatabaseRepository, "_connect", lambda *args, **kwargs: _BadConn())
    issues = await repo.audit_schema()
    assert "schema_audit_failed" in issues


@pytest.mark.asyncio
async def test_db_repo_cleanup_price_history_keeps_recent(tmp_path) -> None:
    db_path = tmp_path / "dealwatch.db"
    repo = DatabaseRepository(db_path)
    await repo.initialize()

    now = datetime.now(timezone.utc)
    context = PriceContext(region="00000")
    offer_old = Offer(
        store_id="weee",
        product_key="p1",
        title="Old",
        url="https://example.com",
        price=5.0,
        original_price=None,
        fetch_at=now - timedelta(days=10),
        context=context,
        unit_price_info={},
    )
    offer_new = Offer(
        store_id="weee",
        product_key="p1",
        title="New",
        url="https://example.com",
        price=4.0,
        original_price=None,
        fetch_at=now - timedelta(days=1),
        context=context,
        unit_price_info={},
    )
    await repo.insert_price_point(offer_old)
    await repo.insert_price_point(offer_new)

    deleted = await repo.cleanup_price_history(older_than_days=5)
    assert isinstance(deleted, int)

    last_price = await repo.get_last_price(
        "weee",
        "p1",
        context.get_hash(),
        max_age_days=2,
    )
    assert last_price == 4.0


@pytest.mark.asyncio
async def test_db_repo_cleanup_price_history_keeps_global_low(tmp_path) -> None:
    db_path = tmp_path / "dealwatch.db"
    repo = DatabaseRepository(db_path)
    await repo.initialize()

    now = datetime.now(timezone.utc)
    context = PriceContext(region="00000")
    offer_low = Offer(
        store_id="weee",
        product_key="p2",
        title="Low",
        url="https://example.com",
        price=1.5,
        original_price=None,
        fetch_at=now - timedelta(days=10),
        context=context,
        unit_price_info={},
    )
    offer_latest = Offer(
        store_id="weee",
        product_key="p2",
        title="Latest",
        url="https://example.com",
        price=3.0,
        original_price=None,
        fetch_at=now - timedelta(days=1),
        context=context,
        unit_price_info={},
    )
    await repo.insert_price_point(offer_low)
    await repo.insert_price_point(offer_latest)

    deleted = await repo.cleanup_price_history(older_than_days=5)
    assert isinstance(deleted, int)

    last_price = await repo.get_last_price(
        "weee",
        "p2",
        context.get_hash(),
        max_age_days=30,
    )
    assert last_price == 3.0

    low_price = await repo.get_historical_low(
        "weee",
        "p2",
        context.get_hash(),
    )
    assert low_price == 1.5


@pytest.mark.asyncio
async def test_db_repo_vacuum_error(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "dealwatch.db"
    repo = DatabaseRepository(db_path)
    await repo.initialize()

    class _BadConn:
        async def __aenter__(self):
            raise sqlite3.Error("boom")

        async def __aexit__(self, exc_type, exc, tb):
            return None

    monkeypatch.setattr(aiosqlite, "connect", lambda *args, **kwargs: _BadConn())

    with pytest.raises(sqlite3.Error):
        await repo.vacuum()


@pytest.mark.asyncio
async def test_db_repo_schema_version_insert(tmp_path) -> None:
    db_path = tmp_path / "dealwatch.db"
    repo = DatabaseRepository(db_path)
    await repo.initialize()

    version = await repo.get_schema_version()
    assert version is not None


@pytest.mark.asyncio
async def test_db_repo_price_series_error(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "dealwatch.db"
    repo = DatabaseRepository(db_path)
    await repo.initialize()

    async def _raise(*args, **kwargs):
        raise sqlite3.Error("boom")

    monkeypatch.setattr(DatabaseRepository, "_execute_with_retry", _raise)

    series = await repo.get_price_series("weee", "p1", "ctx", lookback_days=1, limit=5)
    assert series == []
