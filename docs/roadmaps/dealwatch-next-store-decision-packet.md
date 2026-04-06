# DealWatch Next Store Decision Packet

## Purpose

This packet answers one question before the next implementation wave begins:

> Which store should become the next official DealWatch store, and what is the minimum honest scope for that wave?

This is **not** the implementation wave itself.

## Historical note

This packet remains the historical C1 selection record.

Current repo-local Walmart truth has already moved beyond that initial boundary:

- C1 = landed historically
- C2 = landed historically for watch-group parity
- C3 = current repo-local truth for recovery + cashback closure

## Decision Summary

- Recommended next official store: `Walmart`
- Decision shape: `C1 only`
- Honest scope for the next wave:
  - compare-first intake
  - single watch task creation + run-now
  - manifest/binding/onboarding contract
  - targeted adapter/provider/service/api tests
  - smoke with explicit `ENABLED_STORES`
- Explicitly deferred from the next wave:
  - watch-group parity
  - recovery parity
  - cashback parity
  - broad category/deal crawl
  - public wording or README/proof updates

## Why Walmart Wins

### 1. It already has repo-owned priority evidence

Repo-local planning artifacts already point to `Walmart` as the next official-store wave after Safeway:

- `.agents/skills/_skill-extraction-report.md` records the stable order as `Safeway/grocery -> Walmart -> Amazon defer`
- a March 31 archive-analysis note labels `Walmart` as the second-priority target and `Amazon` as deferred
- an April 2 archive-review note lists `Walmart C1` as the suggested Prompt 4 next-store wave

That matters because a next-store packet should reduce future ambiguity, not reopen strategy from zero.

### 2. It stretches the factory without breaking the product identity

DealWatch is still a `grocery price intelligence` product, not a generic all-commerce price spider.

`Walmart` is a useful next stretch because it:

- stays close enough to grocery and household shopping behavior
- tests the store factory against higher URL and variant complexity than the current four stores
- expands coverage without immediately dragging the product into Amazon-style marketplace semantics

### 3. It is hard in a useful way

Historical repo notes already describe `Walmart` as `medium-high` difficulty because of:

- variant complexity
- seller/offer complexity
- stronger anti-bot pressure

That is exactly the kind of next wave that validates whether the store factory is real instead of Safeway-specific.

## Candidate Roster

| Candidate | Verdict | Why it is or is not next |
| --- | --- | --- |
| `Walmart` | `recommended` | Strongest repo-owned priority signal, still inside the grocery/household lane, and hard enough to validate the store factory without forcing an Amazon-scale scope jump |
| `Kroger-family grocery player (QFC / Fred Meyer)` | `not selected yet` | Product fit is attractive, but the current repo does not carry the same explicit prior-selection evidence or concrete packet-ready target definition; choosing it now would reopen strategy rather than reduce ambiguity |
| `Amazon` | `defer` | Repo-local strategy artifacts repeatedly treat it as the third-priority option; marketplace/seller complexity would pull DealWatch away from its grocery-first product boundary too early |

## Negative Evidence That Also Matters

- `rg -n "walmart|amazon|costco|fredmeyer|qfc" src tests docs --glob '!docs/integrations/**' --glob '!docs/roadmaps/dealwatch-api-mcp-substrate-phase1.md'` currently returns no direct implementation-ready product/store contract files for these candidates.
- That means the next-wave choice should favor the candidate with the clearest repo-owned decision history, not the broadest speculative possibility.

## Minimum Honest C1 Scope For Walmart

The next store implementation wave should stop at `C1`, not pretend to deliver full parity immediately.

### Required product slice

1. product-detail URL normalization and compare-first intake
2. single watch task creation
3. single watch task run-now execution
4. honest limited-support guidance for unsupported Walmart URL shapes
5. manifest + binding + cockpit + runbook alignment

### Required contract files

At minimum, the next wave should touch:

- `src/dealwatch/stores/walmart/adapter.py`
- any required parser/discovery module(s)
- `src/dealwatch/stores/manifest.py`
- `src/dealwatch/stores/__init__.py`
- `src/dealwatch/persistence/store_bindings.py` only if the factory contract itself needs widening
- `src/dealwatch/application/store_onboarding.py`
- `docs/runbooks/store-onboarding-contract.md`
- a new roadmap file for the Walmart C1 slice

### Required verification

At minimum, the next wave should pass:

```bash
python3 scripts/verify_store_capability_registry.py
./scripts/test.sh -q tests/test_adapter_contracts.py tests/test_product_api.py tests/test_product_service.py tests/test_product_providers.py
```

And because store enablement is now an explicit runtime contract, the next wave must also add:

- explicit tests for `default_enabled` behavior
- explicit `ENABLED_STORES` pinning in smoke/test paths that exercise Walmart

## Honest DoD For The Next Store Wave

`Walmart C1` is done only when:

1. the store has a real adapter and parser path
2. compare preview can normalize supported Walmart product-detail URLs
3. a watch task can be created and run against that path
4. manifest, binding logic, onboarding cockpit, verifier, runbook, and tests all agree on support tier and default enablement
5. unsupported Walmart URL shapes degrade honestly into evidence-only guidance instead of fake support
6. fresh verification passes on the exact next-wave diff

## Explicit Non-Goals For The Next Store Wave

- no watch-group parity claim yet
- no recovery parity claim yet
- no cashback parity claim yet
- no broad crawl/category discovery claim yet
- no public README/proof/FAQ launch wording
- no hosted/Render promotion work

## Handoff Note

The important thing about this packet is not just `Walmart` itself.

The more important contract is:

> future store waves must start from an explicit store-selection decision and an explicit `C1/C2/C3` scope boundary,
> not from vague intent to “support more stores.”

## Current repo-local Walmart truth

The repository originally used this same packet as the tracked truth anchor for the landed Walmart C1 slice.
Current repo-local truth is now:

- `support_tier = official_full`
- `default_enabled = false`
- `supports_compare_intake = true`
- `supports_watch_task = true`
- `supports_watch_group = true`
- `supports_recovery = true`
- `cashback_supported = true`
- `discovery_mode = manual-product-url-only`

Supported Walmart PDP URL shapes in the current repo-local slice:

- `https://www.walmart.com/ip/<item_id>`
- `https://www.walmart.com/ip/<slug>/<item_id>`

Both normalize to:

- `https://www.walmart.com/ip/<item_id>`

Still unsupported / deferred after C3:

- `https://www.walmart.com/ip/<slug>` without a numeric item id
- `https://www.walmart.com/browse/...`
- `https://www.walmart.com/reviews/product/...`
- `https://www.walmart.com/search?...`
- non-`www.walmart.com` hosts that mimic the same path
- marketplace / seller-matrix maturity

This keeps Walmart honest as a full current-product-path slice with conservative discovery posture instead of overclaiming broad discovery or marketplace maturity.
