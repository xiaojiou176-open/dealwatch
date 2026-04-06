# DealWatch API / MCP Substrate Phase 1

## Status

> **Status:** active phase-1.1 reference for developers and agent-builders.
> This is the formal builder-facing contract for the current DealWatch API / MCP substrate.
> It describes what an external builder can consume **today** from a local-first runtime.
> It does **not** claim hosted maturity, SDK packaging, multi-tenant auth, write-side MCP, or public recommendation support.

## What this document is for

Think of this file as the front desk for the current DealWatch builder story.

It answers four practical questions:

1. which doors are real today
2. which doors are safe to treat as phase-1 stable
3. which doors exist in code but are still deferred or internal-only
4. what a new builder should read or run first

This is intentionally a **builder contract**, not a hosted platform page and not an SDK launch page.

## Audience and non-audience

### Intended readers

1. **Developers**
   - people calling the local DealWatch runtime over HTTP
2. **Agent-builders**
   - people wiring a local MCP client or automation loop against DealWatch read surfaces
  - common examples today: Claude Code, Codex, OpenHands, OpenCode, OpenClaw, or a custom MCP/API client

### Not the intended promise set

This page is **not** written for:

- casual end users
- hosted SaaS buyers
- builders expecting packaged SDKs or generated client support
- builders expecting write-side remote control or operator-safe mutation

## One-screen summary

| Reader | Start here | Safe first move | Do not assume |
| --- | --- | --- | --- |
| HTTP-first developer | local API server + OpenAPI | `GET /api/health` -> `GET /api/runtime/readiness` -> `POST /api/compare/preview` | hosted auth, durable write stability, every discovered route is public promise |
| MCP-first builder | `list-tools --json` + stdio server | inspect tool inventory -> `get_runtime_readiness` -> `compare_preview` | write-side MCP, maintenance automation, hosted control plane, SDK maturity |

## The honest runtime model

Phase 1 still assumes the current repo truth:

- product data lives in PostgreSQL via `DATABASE_URL`
- the product is still **local-first**, not a hosted public control plane
- owner bootstrap exists, but stays owner-scoped
- the MCP layer is intentionally **read-only**
- `PRODUCT_AUTO_CREATE_SCHEMA` is a temporary bootstrap bridge, not a public migration story

In plain English:

> DealWatch already has a real front door.
> It does not yet have a hotel-style hosted reception desk with keys for many tenants.

## Local runtime entrypoints

```bash
PYTHONPATH=src uv run python -m dealwatch --help
PYTHONPATH=src uv run python -m dealwatch builder-starter-pack --json
PYTHONPATH=src uv run python -m dealwatch server
PYTHONPATH=src uv run python -m dealwatch worker
PYTHONPATH=src uv run python -m dealwatch.mcp list-tools --json
PYTHONPATH=src uv run python -m dealwatch.mcp client-starters --json
PYTHONPATH=src uv run python -m dealwatch.mcp serve --transport stdio
```

## Builder onboarding order

### HTTP-first path

1. start the API server
2. open `/openapi.json` or `/docs`
3. call `GET /api/health`
4. call `GET /api/runtime/readiness`
5. call `POST /api/compare/preview`
6. only after that, inspect read detail routes such as watch tasks, watch groups, notifications, recovery, and store cockpit

### MCP-first path

1. run `python -m dealwatch.mcp list-tools --json`
2. register `python -m dealwatch.mcp serve --transport stdio`
3. call `get_runtime_readiness`
4. call `compare_preview`
5. if the compare result is useful, move to detail reads such as watch tasks, watch groups, recovery inbox, notification settings, store bindings, and store onboarding cockpit

That order matters for the same reason a workshop visit starts at the front bench before you walk into the back room:

- readiness tells you whether the runtime is healthy enough to trust
- compare preview tells you whether the product target is even worth turning into durable state
- detail reads only make sense after you know the runtime and compare story are usable

## Phase-1 stability rules

A surface is treated as **phase-1 stable** here only when all of the following are true:

- it already ships in `src/dealwatch/api/app.py` or `src/dealwatch/mcp/server.py`
- it fits the current local-first, single-owner runtime truth
- it is read-only, or in the special case of compare preview, it does **not** create durable product state
- we can point to one canonical route or tool name for new integrations

A surface is **not** stable here when any of the following are true:

- it mutates durable product state
- it triggers operational side effects
- it depends on bootstrap, provider callbacks, or secret-bearing internals
- it is only an alias or compatibility route
- it exists in code, but the repo is not yet ready to stand behind it as a builder-facing promise

## Stable now

### Stable CLI and discovery surfaces

| Surface | Status | Why it is safe now |
| --- | --- | --- |
| `python -m dealwatch --help` | stable now | prints the builder-relevant command banner with a normal help exit path |
| `python -m dealwatch builder-starter-pack --json` | stable now | prints the repo-owned builder contract without requiring an already running server |
| `python -m dealwatch server` | stable now | boots the HTTP runtime builders consume |
| `python -m dealwatch worker` | stable now for local bring-up | useful when a builder wants the full runtime loop running locally |
| `python -m dealwatch.mcp list-tools --json` | stable now | fastest honest MCP inventory surface |
| `python -m dealwatch.mcp client-starters --json` | stable now | prints repo-owned local launch snippets and prompt anchors for named clients |
| `python -m dealwatch.mcp serve --transport stdio` | stable now | canonical local stdio MCP launch path |

### Stable HTTP surfaces

Canonical route names for new integrations are listed below.
Compatibility aliases may exist in code, but new builders should learn the canonical names first.

| Canonical route | Phase-1 status | Why |
| --- | --- | --- |
| `GET /api/health` | stable now | quickest runtime liveness check |
| `GET /api/runtime/readiness` | stable now | first safe runtime truth check |
| `POST /api/compare/preview` | stable now | compare-first preview without durable writes |
| `GET /api/watch-tasks` | stable now | read current watch task inventory |
| `GET /api/watch-tasks/{task_id}` | stable now | read one task detail |
| `GET /api/watch-groups` | stable now | read current watch group inventory |
| `GET /api/watch-groups/{group_id}` | stable now | read one compare-aware group detail |
| `GET /api/notifications` | stable now | inspect recent delivery events |
| `GET /api/settings/notifications` | stable now | read effective notification settings |
| `GET /api/recovery-inbox` | stable now | inspect recovery truth |
| `GET /api/settings/store-bindings` | stable now | inspect store capability metadata and runtime switches |
| `GET /api/settings/store-onboarding-cockpit` | stable now | inspect store onboarding cockpit truth |

### Stable MCP tool surface

| Tool name | Phase-1 status | What it gives a builder |
| --- | --- | --- |
| `compare_preview` | stable now | compare-first preview without durable writes |
| `list_watch_tasks` | stable now | watch task inventory |
| `get_watch_task_detail` | stable now | one task detail |
| `list_watch_groups` | stable now | watch group inventory |
| `get_watch_group_detail` | stable now | one group detail |
| `get_runtime_readiness` | stable now | runtime readiness truth |
| `get_recovery_inbox` | stable now | recovery queue truth |
| `list_notifications` | stable now | recent delivery events |
| `get_notification_settings` | stable now | effective notification settings |
| `list_store_bindings` | stable now | store capability metadata and switches |
| `get_store_onboarding_cockpit` | stable now | store onboarding cockpit truth |

## Deferred or internal-only

### Deferred for builder-facing phase 1

These surfaces may exist in code, but builders should not treat them as part of the first stable entrance layer yet.

| Surface | Current state | Why it is not part of the phase-1 front door |
| --- | --- | --- |
| compare evidence artifact lifecycle | present in HTTP only | useful repo capability, but not part of the current minimal builder onboarding path |
| `run-due` CLI | present | operational side effect, not a safe builder default |
| write-capable watch/group HTTP mutations | present | durable state mutation belongs outside the read-first phase-1 contract |

### Internal-only

| Surface | Why it stays internal-only |
| --- | --- |
| `python -m dealwatch maintenance --dry-run|--apply` | runtime hygiene tool, not builder API |
| `python -m dealwatch bootstrap-owner` | owner bootstrap path gated by `OWNER_BOOTSTRAP_TOKEN` |
| Postmark webhook route and provider-secret plumbing | provider callback internals, not generic builder auth |
| legacy bridge commands | deprecated SQLite bridge maintenance, outside the product-facing builder story |

## Operator danger paths that are outside the builder promise

Treat these as back-room operator paths, not front-desk builder surfaces:

- maintenance
- cleanup and rebuildable runtime hygiene
- owner bootstrap
- provider webhook / delivery credentials
- legacy SQLite bridge commands
- write-side task or group mutation flows

## Discovery pointers and repo anchors

Once the API server is running, FastAPI exposes:

- `/openapi.json`
- `/docs`
- `/redoc`

Use them as discovery aids, not as the only source of truth for what DealWatch promises to builders.

If you want exact repo anchors instead of prose, use:

| Need | Canonical repo anchor |
| --- | --- |
| HTTP route inventory | `src/dealwatch/api/app.py` |
| named request/response models | `src/dealwatch/api/schemas.py` |
| MCP tool registry | `src/dealwatch/mcp/server.py` |
| MCP CLI entrypoint | `src/dealwatch/mcp/__main__.py` |
| CLI discovery and bootstrap paths | `src/dealwatch/cli.py` |
| environment contract | `.env.example` |
| builder starter pack | `docs/integrations/README.md` |
| builder examples | `docs/integrations/examples/README.md` |
| builder prompt snippets | `docs/integrations/prompt-starters.md` |

## Builder starter assets

The repo-owned starter pack lives under [`docs/integrations/README.md`](../integrations/README.md).

Use it when you need:

- the shortest builder quick path
- starter JSON payloads
- a repo-owned `list-tools` snapshot
- per-client starter prompts

The stable contract is **not** a vendor-specific config wrapper.
The stable contract is:

- the local stdio launch command
- the read-only MCP tool inventory
- the stable read HTTP surface
- the local-first, single-owner, no-SDK, no-write-side boundary

## Ecosystem framing

Claude Code, Codex, OpenHands, OpenCode, OpenClaw, and similar clients are best understood as **consumers** of DealWatch.

That means you can honestly say:

- DealWatch exposes a read-only API / MCP surface those clients can consume

Do **not** flip the relationship and say:

- DealWatch runs on Claude Code
- DealWatch is built on Codex
- OpenHands, OpenCode, or OpenClaw is the runtime base

## Ownership and auth boundary

DealWatch currently behaves like a **single-owner, local-first runtime**, not a multi-tenant hosted platform.

Important consequences:

- `DATABASE_URL` is runtime wiring, not an end-user API key
- `OWNER_BOOTSTRAP_TOKEN` is owner setup only, not a general builder credential
- `POSTMARK_WEBHOOK_TOKEN` is provider callback verification, not a general API token
- `POSTMARK_SERVER_TOKEN` is provider plumbing, not DealWatch API auth
- the current API surface does **not** establish a generic bearer-token or tenant auth contract

The practical rule is simple:

> if a value exists to bootstrap the owner, bind the database, or verify a provider callback, do not reinterpret it as proof that hosted auth is already solved
