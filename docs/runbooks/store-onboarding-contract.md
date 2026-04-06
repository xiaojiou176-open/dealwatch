# Store Onboarding Contract

## Why this exists

DealWatch no longer treats “add a new store” as tribal knowledge.

In plain English:

- It used to feel like "someone who knows the repo can guess their way through a new adapter."
- It now needs to mean "a new store enters the repo together with capability metadata, contract coverage, and explicit enablement rules."

This runbook does not define "how to write elegant code." It defines:

> **What counts as a real DealWatch product-path store onboarding.**

## Minimum contract

Every new store must provide all of the following:

1. A live adapter in `src/dealwatch/stores/<store>/adapter.py`
2. A parser contract path covered by `tests/test_adapter_contracts.py`
3. An entry in `src/dealwatch/stores/manifest.py`
4. A registry entry in `src/dealwatch/stores/__init__.py`
5. A clear answer to:
   - how discovery works
   - how parsing works
   - which official support tier it currently belongs to
   - whether the store is enabled by default when `ENABLED_STORES` is unset
   - whether region matters
   - whether cashback mapping exists
   - whether compare-first intake is supported
   - whether single watch task support exists
   - whether compare-aware watch group support exists
   - whether recovery guidance/runtime recovery support exists

## Official support tiers

DealWatch now treats official store support like shelf labels, not hallway folklore.

- `official_full`: the store has capability metadata, adapter contract coverage, compare intake, single watch task, compare-aware watch group, recovery support, and cashback-aware evaluation aligned enough to claim the full current product path.
- `official_partial`: the store is real and officially supported for part of the product path, but at least one major product-path capability is still intentionally missing.
- `official_in_progress`: the store has entered the repo and the onboarding contract is being wired up, but it is not yet honest to market it as a complete product-path store.

Discovery posture is tracked separately through `discovery_mode`.

That means a store can still be `official_full` for the **current product path** even if broad crawl/category discovery remains intentionally narrow, as long as compare intake, watch task, watch group, recovery, and cashback-aware evaluation are truly covered for the supported URL shape.

## Runtime binding truth

DealWatch now treats runtime enablement as a second gate on top of support labels.

In plain English:

- `support_tier` says what the repo can honestly claim about the store path
- `default_enabled` says whether the zero-config repo-local runtime should bind the store when `ENABLED_STORES` is unset
- `StoreAdapterBinding.enabled` says whether the live runtime switch is on right now
- `ENABLED_STORES` is the operator switchboard, not the source of truth for store capability

A store is only runtime-binding eligible when all of the following are true:

1. it is not `official_in_progress`
2. compare intake is supported
3. single watch-task support is present

That means:

- `official_full` stores should be runtime-binding eligible
- `official_partial` stores may still be runtime-binding eligible for the narrower supported slice
- `official_in_progress` stores must stay out of `ENABLED_STORES` until the onboarding blockers are closed
- new stores should usually land with `default_enabled = false` until the operator has consciously opted them in

When `ENABLED_STORES` is set, it acts as an explicit allowlist. When it is unset, the manifest-level `default_enabled` flag becomes the zero-config runtime rule.
In the current runtime contract, an explicitly empty string such as `ENABLED_STORES=""` is normalized the same way as an unset value.

Tests and smoke are still required before an operator flips `ENABLED_STORES`, but runtime code should not pretend it can infer test/smoke completion by itself. The contract is:

> capability truth lives in the manifest, while the operator switch lives in `ENABLED_STORES`.

`ENABLED_STORES` is a selector, not a promotion lever:

- it may narrow the live runtime set to a smaller subset of eligible stores
- it must not promote an in-progress store into live runtime truth
- in plain English: the manifest decides which stores are allowed into the factory, and `ENABLED_STORES` only decides which already-approved lanes are switched on today

## Limited support contract

DealWatch also needs an honest answer for URLs that are not fully onboarded official stores yet.

- Unknown-host or unsupported-path URLs may still enter compare preview as **limited-support, evidence-only** rows.
- Limited-support rows may stay in compare review and repo-local compare evidence packages.
- Limited-support rows do **not** claim live watch-task creation, watch-group creation, cashback tracking, or notification delivery.
- The product must return explicit guidance that says why the row stopped early and what the next honest step is.
- A recognized store host with an unsupported URL path is different from a completely unknown host; operators should be able to see that difference.

## Capability fields

Each store capability entry must define:

- `store_id`
- `support_tier`
- `default_enabled`
- `support_reason_codes`
- `next_step_codes`
- `contract_test_paths`
- `discovery_mode`
- `parse_mode`
- `region_sensitive`
- `cashback_supported`
- `supports_compare_intake`
- `supports_watch_task`
- `supports_watch_group`
- `supports_recovery`

These fields are not decorative metadata. They are the machine-readable summary of how this store behaves inside the product.

Code semantics for those fields:

- `support_reason_codes` and `next_step_codes` should be empty for `official_full`
- `support_reason_codes` and `next_step_codes` should be explicit and non-empty for `official_partial` and `official_in_progress`
- `default_enabled` should be an explicit boolean, not an implicit guess from support tier alone
- `contract_test_paths` must include `tests/test_adapter_contracts.py` and every listed path must exist in the repo
- `official_partial` means compare-first + single-watch are real, but at least one larger product-path capability still remains intentionally missing
- `official_in_progress` means the store is visible in repo truth, but it is not yet eligible for live runtime binding

## Required tests

Before a store is considered onboarded, all of these must pass:

```bash
./scripts/test.sh -q tests/test_adapter_contracts.py
python3 scripts/verify_store_capability_registry.py
```

If the new store changes product runtime behavior, also run:

```bash
./scripts/test.sh -q
./scripts/smoke_product_hermetic.sh
```

## What is not enough

The following do **not** count as a completed store onboarding:

- only adding a parser
- only adding an adapter class
- only adding a registry entry
- only adding a screenshot or README claim
- only proving that one HTML fixture parses once

That would be like adding a new cash register to a shop without connecting power, inventory, or receipts.

It is also not enough to say "the store is supported" without saying whether that means:

- full current product-path support
- partial official support
- in-progress official onboarding
- limited compare/evidence-only support

## Rollout rule

New stores should stay disabled by default until:

1. capability metadata exists
2. adapter contract tests pass
3. compare-first intake behavior is understood
4. runtime smoke still passes
5. the operator intentionally adds the store to `ENABLED_STORES`

## Related files

- [`src/dealwatch/stores/manifest.py`](../../src/dealwatch/stores/manifest.py)
- [`src/dealwatch/stores/__init__.py`](../../src/dealwatch/stores/__init__.py)
- [`src/dealwatch/persistence/store_bindings.py`](../../src/dealwatch/persistence/store_bindings.py)
- [`tests/test_adapter_contracts.py`](../../tests/test_adapter_contracts.py)
- [`scripts/verify_store_capability_registry.py`](../../scripts/verify_store_capability_registry.py)
