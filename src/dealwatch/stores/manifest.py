from __future__ import annotations

from dataclasses import dataclass


OFFICIAL_SUPPORT_TIERS = {
    "official_full",
    "official_partial",
    "official_in_progress",
}

PRODUCT_PATH_CAPABILITY_FIELDS = (
    "supports_compare_intake",
    "supports_watch_task",
    "supports_watch_group",
    "supports_recovery",
    "cashback_supported",
)
RUNTIME_BINDING_REQUIRED_FIELDS = (
    "supports_compare_intake",
    "supports_watch_task",
)


@dataclass(frozen=True, slots=True)
class StoreCapability:
    store_id: str
    support_tier: str
    default_enabled: bool
    support_reason_codes: tuple[str, ...]
    next_step_codes: tuple[str, ...]
    contract_test_paths: tuple[str, ...]
    discovery_mode: str
    parse_mode: str
    region_sensitive: bool
    cashback_supported: bool
    supports_compare_intake: bool
    supports_watch_task: bool
    supports_watch_group: bool
    supports_recovery: bool


def derive_missing_capabilities(capability: StoreCapability | None) -> tuple[str, ...]:
    if capability is None:
        return ("manifest_entry",)

    return tuple(
        capability_name
        for capability_name, enabled in (
            ("compare_intake", capability.supports_compare_intake),
            ("watch_task", capability.supports_watch_task),
            ("watch_group", capability.supports_watch_group),
            ("recovery", capability.supports_recovery),
            ("cashback", capability.cashback_supported),
        )
        if not enabled
    )


def derive_runtime_binding_blockers(capability: StoreCapability | None) -> tuple[str, ...]:
    if capability is None:
        return ("manifest_entry",)

    blockers: list[str] = []
    if capability.support_tier == "official_in_progress":
        blockers.append("official_onboarding_in_progress")
    if not capability.supports_compare_intake:
        blockers.append("compare_intake_not_ready")
    if not capability.supports_watch_task:
        blockers.append("watch_task_not_ready")
    return tuple(blockers)


def is_runtime_binding_eligible(capability: StoreCapability | None) -> bool:
    return not derive_runtime_binding_blockers(capability)


def build_store_support_summary(
    capability: StoreCapability | None,
    *,
    enabled: bool | None = None,
) -> str | None:
    if capability is None:
        return None

    runtime_switch_note = ""
    if enabled is False and is_runtime_binding_eligible(capability):
        if capability.default_enabled:
            runtime_switch_note = " Runtime activation still depends on the active ENABLED_STORES allowlist."
        else:
            runtime_switch_note = " Runtime activation stays off by default until the store is explicitly listed in ENABLED_STORES."

    if capability.support_tier == "official_full":
        discovery_note = (
            " Discovery still stays conservative at manual-product-url-only, but that is treated as discovery posture,"
            " not as a missing current product-path capability."
            if capability.discovery_mode == "manual-product-url-only"
            else ""
        )
        return (
            "Official full support: compare intake, single watch task, compare-aware watch group, "
            "recovery, cashback-aware evaluation, and the current runtime contract are all available."
            f"{discovery_note}{runtime_switch_note}"
        )

    if capability.support_tier == "official_partial":
        missing = ", ".join(derive_missing_capabilities(capability))
        return (
            "Official partial support: the store is real on the product path, but some major capability "
            f"areas are still intentionally missing ({missing}).{runtime_switch_note}"
        )

    blockers = ", ".join(derive_runtime_binding_blockers(capability))
    return (
        "Official onboarding is in progress: the store has entered repo truth, "
        "but it is not yet ready to market as a complete product-path store."
        f" Keep it out of ENABLED_STORES until the runtime binding blockers close ({blockers})."
    )


def build_next_onboarding_step(
    capability: StoreCapability | None,
    *,
    enabled: bool | None = None,
) -> str | None:
    if capability is None:
        return None

    blockers = derive_runtime_binding_blockers(capability)
    if blockers:
        blocker_labels = ", ".join(blockers)
        return f"Keep the store out of ENABLED_STORES until the runtime binding blockers close: {blocker_labels}."

    missing = derive_missing_capabilities(capability)
    if not missing:
        if enabled is False:
            if capability.default_enabled:
                return "The store is runtime-ready; update the active ENABLED_STORES allowlist if you want this environment to turn it on."
            return "After verification, add the store to ENABLED_STORES to opt it into the live runtime binding."
        return "Keep contract tests, runtime verification, and documentation aligned as the full-support baseline."

    missing_labels = ", ".join(missing)
    return f"Close the remaining product-path capability gaps before widening the store claim: {missing_labels}."


def build_runtime_binding_summary(
    capability: StoreCapability | None,
    *,
    enabled: bool | None = None,
) -> str | None:
    if capability is None:
        return None

    blockers = derive_runtime_binding_blockers(capability)
    if blockers:
        blocker_labels = ", ".join(blockers)
        return (
            "This store is not runtime-binding eligible yet. "
            f"Keep default_enabled off until the blockers close: {blocker_labels}."
        )

    if capability.default_enabled:
        if enabled is False:
            return (
                "This store is runtime-binding eligible and enabled by default when ENABLED_STORES is unset, "
                "but the current environment allowlist is leaving it off."
            )
        return "This store is runtime-binding eligible and enabled by default when ENABLED_STORES is unset."

    return (
        "This store is runtime-binding eligible but disabled by default. "
        "An explicit ENABLED_STORES allowlist entry is required before live runtime binding turns on."
    )


STORE_CAPABILITY_REGISTRY: dict[str, StoreCapability] = {
    "target": StoreCapability(
        store_id="target",
        support_tier="official_full",
        default_enabled=True,
        support_reason_codes=(),
        next_step_codes=(),
        contract_test_paths=(
            "tests/test_adapter_contracts.py",
            "tests/test_target_discovery.py",
            "tests/test_target_parser.py",
            "tests/test_target_adapter.py",
            "tests/test_product_providers.py",
        ),
        discovery_mode="sitemap-http",
        parse_mode="playwright-product-page",
        region_sensitive=True,
        cashback_supported=True,
        supports_compare_intake=True,
        supports_watch_task=True,
        supports_watch_group=True,
        supports_recovery=True,
    ),
    "ranch99": StoreCapability(
        store_id="ranch99",
        support_tier="official_full",
        default_enabled=True,
        support_reason_codes=(),
        next_step_codes=(),
        contract_test_paths=(
            "tests/test_adapter_contracts.py",
            "tests/test_ranch99_discovery.py",
            "tests/test_ranch99_parser.py",
            "tests/test_ranch99_adapter.py",
            "tests/test_product_providers.py",
        ),
        discovery_mode="sitemap-http",
        parse_mode="playwright-product-page",
        region_sensitive=True,
        cashback_supported=True,
        supports_compare_intake=True,
        supports_watch_task=True,
        supports_watch_group=True,
        supports_recovery=True,
    ),
    "weee": StoreCapability(
        store_id="weee",
        support_tier="official_full",
        default_enabled=True,
        support_reason_codes=(),
        next_step_codes=(),
        contract_test_paths=(
            "tests/test_adapter_contracts.py",
            "tests/test_weee_discovery.py",
            "tests/test_weee_parser.py",
            "tests/test_weee_adapter.py",
            "tests/test_product_providers.py",
        ),
        discovery_mode="playwright-category-scroll",
        parse_mode="playwright-product-page",
        region_sensitive=True,
        cashback_supported=True,
        supports_compare_intake=True,
        supports_watch_task=True,
        supports_watch_group=True,
        supports_recovery=True,
    ),
    "safeway": StoreCapability(
        store_id="safeway",
        support_tier="official_full",
        default_enabled=True,
        support_reason_codes=(),
        next_step_codes=(),
        contract_test_paths=(
            "tests/test_adapter_contracts.py",
            "tests/test_safeway_discovery.py",
            "tests/test_safeway_parser.py",
            "tests/test_safeway_adapter.py",
            "tests/test_product_providers.py",
            "tests/test_product_service.py",
            "tests/test_product_api.py",
        ),
        discovery_mode="manual-product-url-only",
        parse_mode="playwright-product-page-jsonld",
        region_sensitive=True,
        cashback_supported=True,
        supports_compare_intake=True,
        supports_watch_task=True,
        supports_watch_group=True,
        supports_recovery=True,
    ),
    "walmart": StoreCapability(
        store_id="walmart",
        support_tier="official_full",
        default_enabled=False,
        support_reason_codes=(),
        next_step_codes=(),
        contract_test_paths=(
            "tests/test_adapter_contracts.py",
            "tests/test_product_providers.py",
            "tests/test_walmart_discovery.py",
            "tests/test_walmart_parser.py",
            "tests/test_walmart_adapter.py",
            "tests/test_product_service.py",
            "tests/test_product_api.py",
        ),
        discovery_mode="manual-product-url-only",
        parse_mode="playwright-product-page-jsonld",
        region_sensitive=True,
        cashback_supported=True,
        supports_compare_intake=True,
        supports_watch_task=True,
        supports_watch_group=True,
        supports_recovery=True,
    ),
}
