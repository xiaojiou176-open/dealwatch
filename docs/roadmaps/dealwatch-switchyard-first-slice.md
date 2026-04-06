# DealWatch Switchyard First Slice

## Purpose

This document records the current Switchyard seam for DealWatch.

In plain English:

- DealWatch already has a real AI explanation seam
- the first Switchyard slice only swaps the provider supply path behind that seam
- DealWatch still keeps business truth, recommendation truth, store truth, and operator truth locally

Use this file when the question is:

> "What is already connected to Switchyard today, what stays in DealWatch, and what must still be written as planned?"

## Current verdict

> **Status:** explain-only, service-first, first slice landed.

This is **not** a Big Bang brain swap.

## What is connected today

Current code anchors:

- `src/dealwatch/application/ai_integration.py`
- `src/dealwatch/infra/config.py`
- `tests/test_ai_integration.py`

Current repo contract:

- `AI_PROVIDER=switchyard_service`
- `AI_BASE_URL=<switchyard-runtime-base>`
- `AI_SWITCHYARD_PROVIDER=<provider-name>`
- `AI_SWITCHYARD_LANE=byok|web`
- `AI_MODEL=<model-name>`

Current behavior:

- DealWatch keeps the existing `AiNarrativeService` envelope contract
- Switchyard provides the remote explanation output for that envelope
- the first slice powers explanation lanes only

## What the current request shape looks like

The current first slice sends a service request that contains:

- provider
- model
- serialized narrative input
- a strict system instruction that preserves deterministic DealWatch truth
- low-temperature, bounded-token generation settings

The current lane split is:

- `byok` -> `POST /v1/runtime/byok/invoke`
- `web` -> `POST /v1/runtime/invoke`

## What stays inside DealWatch

DealWatch still owns:

- compare evidence
- recommendation governance and stop lines
- watch-task and watch-group business truth
- store capability truth
- recovery and operator truth
- public/builder-facing honesty boundaries

In plain English:

> Switchyard is the generator room, not the store manager, cashier, and inventory system.

## What this first slice does not claim

The current first slice does **not** prove:

- full DealWatch runtime has moved to Switchyard
- recommendation has moved to Switchyard
- Switchyard now owns DealWatch business logic
- Switchyard already has fully real Claude Code / Codex / OpenHands / OpenCode compatibility for this workflow
- MCP compatibility is already complete
- SDK maturity or hosted auth has arrived

Anything in those areas must still be written as `planned`, not `shipped`.

## Graceful degrade contract

The first slice keeps the existing degrade rules:

- provider unavailable -> explanation returns `unavailable`
- user action required -> explanation returns `unavailable` with honest guidance
- fake provider remains available for deterministic contract tests
- deterministic product surfaces remain usable even if the remote AI provider fails

## Why this is the right first slice

This first slice is intentionally narrow because it changes the power source without moving the walls:

- the explanation seam already existed
- the surrounding product contract already existed
- the deterministic truth anchors already existed

That makes the first slice honest.

## Current stop line

The current honest stop line is:

- service-first explain provider slice = real
- broader brain swap = still planned
- compat claims beyond the current tested explain contract = still planned

## Verification

Minimum fresh checks:

```bash
./scripts/test.sh -q tests/test_ai_integration.py
./scripts/test.sh -q
git diff --check
```

## Handoff rule

Later workers should keep this ordering:

1. preserve DealWatch business truth
2. preserve the existing AI envelope contract
3. move provider/runtime concerns behind the seam incrementally
4. only claim the next Switchyard compatibility layer after code/tests/docs all support it
