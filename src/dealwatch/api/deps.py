from __future__ import annotations

from collections.abc import AsyncIterator
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker

from dealwatch.application import ProductService
from dealwatch.persistence.session import dispose_session_factory, get_session_factory, init_product_database
from dealwatch.persistence.store_bindings import sync_store_adapter_bindings
from dealwatch.infra.config import settings
from dealwatch.runtime_preflight import ensure_runtime_contract_from_settings


_SERVICE: ProductService | None = None
_RUNTIME_FACTORY: async_sessionmaker[AsyncSession] | None = None


def _session_factory_database_url(
    factory: async_sessionmaker[AsyncSession] | None,
) -> str | None:
    if factory is None:
        return None

    bind = factory.kw.get("bind")
    if bind is None:
        return None

    return str(bind.url)


async def _ensure_runtime_factory_matches_settings() -> None:
    global _SERVICE, _RUNTIME_FACTORY

    expected_url = settings.DATABASE_URL
    if _session_factory_database_url(_RUNTIME_FACTORY) == expected_url:
        return

    if _SERVICE is not None:
        await dispose_session_factory(_SERVICE.session_factory)
        _SERVICE = None
    await dispose_session_factory(_RUNTIME_FACTORY)
    _RUNTIME_FACTORY = get_session_factory(expected_url)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
        await dispose_session_factory(factory)


async def prepare_product_runtime() -> None:
    global _RUNTIME_FACTORY
    ensure_runtime_contract_from_settings(settings, "startup")
    await _ensure_runtime_factory_matches_settings()
    if _RUNTIME_FACTORY is None:
        _RUNTIME_FACTORY = get_session_factory(settings.DATABASE_URL)
    await init_product_database(session_factory=_RUNTIME_FACTORY)
    await sync_store_adapter_bindings(cast(async_sessionmaker[AsyncSession], _RUNTIME_FACTORY), settings)


async def shutdown_product_runtime() -> None:
    global _SERVICE, _RUNTIME_FACTORY
    if _SERVICE is not None:
        await dispose_session_factory(_SERVICE.session_factory)
        _SERVICE = None
    await dispose_session_factory(_RUNTIME_FACTORY)
    _RUNTIME_FACTORY = None


def get_product_service() -> ProductService:
    global _SERVICE, _RUNTIME_FACTORY
    if _SERVICE is None:
        if _session_factory_database_url(_RUNTIME_FACTORY) != settings.DATABASE_URL:
            _RUNTIME_FACTORY = get_session_factory(settings.DATABASE_URL)
        _SERVICE = ProductService(session_factory=cast(async_sessionmaker[AsyncSession], _RUNTIME_FACTORY))
    return _SERVICE
