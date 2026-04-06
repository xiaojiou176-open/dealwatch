from dealwatch.stores.target.adapter import TargetAdapter
from dealwatch.stores.ranch99.adapter import Ranch99Adapter
from dealwatch.stores.safeway.adapter import SafewayAdapter
from dealwatch.stores.walmart.adapter import WalmartAdapter
from dealwatch.stores.weee.adapter import WeeeAdapter
from dealwatch.stores.manifest import (
    OFFICIAL_SUPPORT_TIERS,
    STORE_CAPABILITY_REGISTRY,
    build_next_onboarding_step,
    build_runtime_binding_summary,
    build_store_support_summary,
    derive_missing_capabilities,
    derive_runtime_binding_blockers,
    is_runtime_binding_eligible,
)


#########################################################
# Store Registry
#########################################################
STORE_REGISTRY = {
    Ranch99Adapter.store_id: Ranch99Adapter,
    SafewayAdapter.store_id: SafewayAdapter,
    TargetAdapter.store_id: TargetAdapter,
    WalmartAdapter.store_id: WalmartAdapter,
    WeeeAdapter.store_id: WeeeAdapter,
}


__all__ = [
    "OFFICIAL_SUPPORT_TIERS",
    "STORE_REGISTRY",
    "STORE_CAPABILITY_REGISTRY",
    "build_next_onboarding_step",
    "build_runtime_binding_summary",
    "build_store_support_summary",
    "derive_missing_capabilities",
    "derive_runtime_binding_blockers",
    "is_runtime_binding_eligible",
]
