from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from dealwatch.infra.config import Settings, settings
from dealwatch.persistence.models import StoreAdapterBinding
from dealwatch.stores import STORE_CAPABILITY_REGISTRY, STORE_REGISTRY, is_runtime_binding_eligible


async def sync_store_adapter_bindings(
    session_factory: async_sessionmaker[AsyncSession],
    app_settings: Settings = settings,
) -> None:
    async with session_factory() as session:
        existing = {
            item.store_key: item
            for item in list((await session.scalars(select(StoreAdapterBinding))).all())
        }

        for store_key, adapter_cls in STORE_REGISTRY.items():
            capability = STORE_CAPABILITY_REGISTRY.get(store_key)
            enabled_by_config = (
                store_key in app_settings.ENABLED_STORES
                if app_settings.ENABLED_STORES
                else bool(capability is not None and capability.default_enabled)
            )
            contract_eligible = is_runtime_binding_eligible(capability)
            enabled = bool(contract_eligible and enabled_by_config)
            binding = existing.get(store_key)
            if binding is None:
                binding = StoreAdapterBinding(
                    store_key=store_key,
                    enabled=enabled,
                    adapter_class=f"{adapter_cls.__module__}.{adapter_cls.__name__}",
                )
                session.add(binding)
                continue

            binding.enabled = enabled
            binding.adapter_class = f"{adapter_cls.__module__}.{adapter_cls.__name__}"

        await session.commit()
