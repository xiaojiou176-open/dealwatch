# DealWatch Safeway C1 -> C2/C3 Closure

## Purpose

This document now records the full repo-local Safeway closure arc.

In plain English:

- Safeway started as a real C1 compare/task slice
- this file now also captures the Prompt-4 / historical-Prompt-7 closure pass
- the repo can now say what Safeway honestly supports without hiding behind `official_partial`

## Prompt Mapping

- Current conversation program: `Prompt 4`
- Historical execution-program stage: `Prompt 7 — Safeway C2/C3`

These are the same wave, not two competing truth sources.

## Closure Outcome

Safeway now closes as:

- `support_tier = official_full`

That does **not** mean “Safeway now has broad crawl parity.”

It means the current DealWatch product path is repo-locally covered for Safeway:

- compare-first intake for product-detail URLs
- single watch task creation and run-now execution
- compare-aware watch group creation and run-now execution
- recovery inbox visibility for failed/blocked Safeway paths
- cashback-aware price evaluation through the existing runtime path

## What Landed Across C1 + C2/C3

### Store files

- `src/dealwatch/stores/safeway/adapter.py`
- `src/dealwatch/stores/safeway/discovery.py`
- `src/dealwatch/stores/safeway/parser.py`
- `src/dealwatch/stores/safeway/__init__.py`

### Registry / capability truth

- `src/dealwatch/stores/manifest.py`
- `src/dealwatch/stores/__init__.py`
- `src/dealwatch/application/services.py`
- `src/dealwatch/application/store_onboarding.py`
- `src/dealwatch/api/schemas.py`
- `Safeway` now carries `support_tier = official_full`

### Test coverage

- `tests/test_safeway_discovery.py`
- `tests/test_safeway_parser.py`
- `tests/test_safeway_adapter.py`
- `tests/test_product_providers.py`
- `tests/test_adapter_contracts.py`
- `tests/test_product_service.py`
- `tests/test_product_api.py`

## Honest Capability Boundary

What Safeway can now honestly claim:

- compare-first URL intake works for supported product-detail URLs
- compare preview can resolve Safeway as a full official store lane
- single-target resolution can normalize and persist a Safeway product URL
- single watch task resolution and run-now execution work on the current product path
- compare-aware watch groups can be created from Safeway product-detail URLs and run to a winner
- Safeway watch-group runs can land `lowest_effective_price_with_cashback` when the cashback path returns evidence
- failed Safeway watch-group runs surface back into the recovery inbox instead of disappearing into opaque runtime failure
- parser out-of-stock classification remains explicitly protected

What Safeway still does **not** claim:

- broad discovery/deal crawling
- category-page or promo-hub ingestion as an official stable path
- live/public proof beyond the normal repo-local verification envelope

## Discovery Posture

Current discovery posture remains intentionally conservative:

- `discovery_mode = manual-product-url-only`

That is still true after C2/C3 closure.

In plain English:

> Safeway is full on the **current product path**,
> but we are still not pretending broad crawl/discovery maturity.

What `manual-product-url-only` means in practice:

- `discover_deals()` intentionally returns no crawl inventory
- the stable path is a user- or task-provided Safeway product-detail URL
- category pages, promo hubs, and broad crawl/deal coverage remain separate future work, not blockers for the current product path

## Verification For This Slice

The minimum verification set for this closure is:

- `./scripts/test.sh -q tests/test_safeway_discovery.py tests/test_safeway_parser.py tests/test_safeway_adapter.py tests/test_product_providers.py`
- `./scripts/test.sh -q tests/test_adapter_contracts.py tests/test_product_service.py tests/test_product_api.py`
- `python3 scripts/verify_store_capability_registry.py`

Current verification status for the repo-local closure:

- `./scripts/test.sh -q tests/test_safeway_discovery.py tests/test_safeway_parser.py tests/test_safeway_adapter.py tests/test_product_providers.py tests/test_adapter_contracts.py tests/test_product_service.py tests/test_product_api.py` passed (`77 passed`)
- `python3 scripts/verify_store_capability_registry.py` passed
- `pnpm -C frontend build` passed
- `git diff --check` passed
- `./scripts/test.sh -q` passed (`414 passed, 1 skipped`)

The C2/C3 closure evidence this file now carries is:

- a Safeway watch group can be created and run successfully as a repo-owned test
- the winning reason can resolve to `lowest_effective_price_with_cashback`
- a failed Safeway watch group can reappear in the recovery inbox as a repo-owned test

The whole-repo verification pack has now been rerun on the closure diff.

## Next Step After This Closure

Safeway is no longer the main blocker.

The next natural knife is now:

1. the next official-store onboarding wave, or
2. recommendation governance / shadow work, or
3. explicit live/public promotion work once separately authorized
