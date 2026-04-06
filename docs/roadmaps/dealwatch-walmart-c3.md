# DealWatch Walmart C3

## Purpose

This document records the current repo-local Walmart C3 truth.

In plain English:

- the historical next-store packet picked Walmart as the next official store
- C1 gave Walmart compare-first intake and watch-task support
- C2 gave Walmart watch-group parity
- C3 closes recovery and cashback for the current product path

Use this file when the question is:

> "What can Walmart honestly do today, and what is still deliberately not being claimed?"

## Current verdict

> **Status:** `official_full` for the current product path, with conservative discovery posture.

That sentence has an important boundary:

- current product path = yes
- broad discovery / marketplace maturity = not claimed

## Current capability truth

Current manifest-backed truth:

- `support_tier = official_full`
- `default_enabled = false`
- `supports_compare_intake = true`
- `supports_watch_task = true`
- `supports_watch_group = true`
- `supports_recovery = true`
- `cashback_supported = true`
- `discovery_mode = manual-product-url-only`

## Supported URL shapes

Supported Walmart PDP shapes:

- `https://www.walmart.com/ip/<item_id>`
- `https://www.walmart.com/ip/<slug>/<item_id>`

Both normalize to:

- `https://www.walmart.com/ip/<item_id>`

## Still deferred

The following still remain outside the current Walmart claim:

- broad category/deal crawl
- marketplace / seller-matrix maturity
- unsupported host/path shapes masquerading as live task support

Examples that are still intentionally unsupported:

- `https://www.walmart.com/ip/<slug>` without a numeric item id
- `https://www.walmart.com/browse/...`
- `https://www.walmart.com/reviews/product/...`
- `https://www.walmart.com/search?...`
- non-`www.walmart.com` hosts that mimic the same path

## Evidence anchors

Primary repo anchors:

- `src/dealwatch/stores/manifest.py`
- `src/dealwatch/stores/walmart/discovery.py`
- `src/dealwatch/stores/walmart/adapter.py`
- `src/dealwatch/stores/walmart/parser.py`
- `docs/runbooks/store-onboarding-contract.md`
- `docs/roadmaps/dealwatch-next-store-decision-packet.md`

Primary test anchors:

- `tests/test_walmart_discovery.py`
- `tests/test_walmart_parser.py`
- `tests/test_walmart_adapter.py`
- `tests/test_product_service.py`
- `tests/test_product_api.py`

## Why `official_full` is honest here

The store contract now aligns across:

- manifest capability fields
- runtime binding / cockpit truth
- compare intake and watch-task normalization
- watch-group execution
- recovery inbox visibility
- cashback-aware effective-price evaluation

That is enough to say:

> Walmart is full for the current product path

It is not enough to say:

> Walmart has broad discovery or marketplace maturity

## Verification

Minimum fresh checks:

```bash
python3 scripts/verify_store_capability_registry.py
./scripts/test.sh -q tests/test_walmart_discovery.py tests/test_walmart_parser.py tests/test_walmart_adapter.py tests/test_adapter_contracts.py tests/test_product_service.py tests/test_product_api.py
```

## Handoff rule

Future store work should treat Walmart like Safeway on one key point:

> conservative discovery posture does not cancel honest current-path support

If a future wave wants broader Walmart discovery or marketplace maturity, that must be a new explicit wave, not a silent wording creep.
