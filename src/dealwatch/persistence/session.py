from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url
from sqlalchemy import create_engine, inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from dealwatch.infra.config import Settings, settings
from dealwatch.persistence.base import Base
from dealwatch.persistence import models as _models  # noqa: F401


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"
logger = logging.getLogger(__name__)
PRODUCT_TABLES = {
    "canonical_products",
    "cashback_quotes",
    "effective_price_snapshots",
    "product_candidates",
    "store_adapter_bindings",
    "users",
    "user_preferences",
    "watch_targets",
    "watch_tasks",
    "watch_groups",
    "watch_group_members",
    "task_runs",
    "watch_group_runs",
    "price_observations",
    "notification_rules",
    "delivery_events",
}


def _ensure_sqlite_database_parent(database_url: str) -> None:
    if not database_url.startswith("sqlite"):
        return

    url = make_url(database_url)
    database = url.database
    if not database or database == ":memory:" or database.startswith("file:"):
        return

    Path(database).expanduser().parent.mkdir(parents=True, exist_ok=True)


def _sqlite_engine_kwargs(database_url: str) -> dict[str, object]:
    if not database_url.startswith("sqlite"):
        return {}

    url = make_url(database_url)
    database = url.database
    if not database or database == ":memory:" or database.startswith("file:"):
        return {}

    # File-backed sqlite engines do not benefit from pooled connections in this repo,
    # and NullPool avoids leaving worker threads behind across test/event-loop teardown.
    return {"poolclass": NullPool}


async def dispose_session_factory(factory: async_sessionmaker[AsyncSession] | None) -> None:
    if factory is None:
        return

    bind = factory.kw.get("bind")
    if bind is None:
        return

    await bind.dispose()


def create_session_factory(database_url: str | None = None) -> async_sessionmaker[AsyncSession]:
    effective_database_url = database_url or settings.DATABASE_URL
    _ensure_sqlite_database_parent(effective_database_url)
    engine = create_async_engine(
        effective_database_url,
        future=True,
        pool_pre_ping=True,
        **_sqlite_engine_kwargs(effective_database_url),
    )
    return async_sessionmaker(engine, expire_on_commit=False)


def get_session_factory(database_url: str | None = None) -> async_sessionmaker[AsyncSession]:
    return create_session_factory(database_url)


def run_product_migrations(database_url: str) -> None:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    if should_stamp_existing_schema(database_url):
        command.stamp(config, "head")
        return
    command.upgrade(config, "head")


def should_stamp_existing_schema(database_url: str) -> bool:
    engine = create_engine(database_url)
    try:
        inspector = sa_inspect(engine)
        table_names = set(inspector.get_table_names())
        return _should_stamp_existing_schema_from_tables(table_names)
    finally:
        engine.dispose()


def _should_stamp_existing_schema_from_tables(table_names: set[str]) -> bool:
    has_product_tables = any(name in PRODUCT_TABLES for name in table_names)
    has_alembic_version = "alembic_version" in table_names
    return has_product_tables and not has_alembic_version


async def init_product_database(
    app_settings: Settings | str | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    effective_settings = app_settings or settings
    if isinstance(effective_settings, str):
        factory = session_factory or create_session_factory(effective_settings)
        auto_create_schema = True
        database_url = effective_settings
        logger.warning(
            "Bootstrapping from a raw sqlite database URL uses the temporary schema bridge."
        )
    else:
        factory = session_factory or create_session_factory(effective_settings.DATABASE_URL)
        auto_create_schema = effective_settings.PRODUCT_AUTO_CREATE_SCHEMA
        database_url = effective_settings.DATABASE_URL

    if database_url.startswith("sqlite"):
        if not auto_create_schema:
            logger.info(
                "Skipping sqlite schema bootstrap because PRODUCT_AUTO_CREATE_SCHEMA is disabled."
            )
            return
        logger.warning(
            "Bootstrapping sqlite schema via PRODUCT_AUTO_CREATE_SCHEMA. This is a temporary bridge, not the default product path."
        )
        async with factory() as session:
            async with session.bind.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        return

    await session_factory_sync_bridge(database_url)


async def session_factory_sync_bridge(database_url: str) -> None:
    await _run_sync_migrations(database_url)


async def _run_sync_migrations(database_url: str) -> None:
    import asyncio

    await asyncio.to_thread(run_product_migrations, database_url)


@asynccontextmanager
async def session_scope(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> AsyncIterator[AsyncSession]:
    factory = session_factory or create_session_factory()
    async with factory() as session:
        yield session
