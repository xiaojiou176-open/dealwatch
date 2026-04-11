# DealWatch Builder Integrations

## Purpose

This directory is the repo-native builder starter pack for DealWatch.

In plain English:

- the API, MCP, and CLI doors already exist
- this pack tells developers and agent-builders which door to use first
- it gives local-first examples without pretending DealWatch is already an SDK or hosted builder platform
- it includes a client config recipe ledger so wrapper honesty is part of the contract instead of tribal knowledge

Use this directory when the question is:

> "I am wiring Claude Code, Codex, OpenHands, OpenCode, OpenClaw, or a similar client to DealWatch. Where do I start, what is safe, and what should I not assume yet?"

## What this pack is

- a local-first onboarding pack
- a read-only-first builder pack
- a practical companion to [`../roadmaps/dealwatch-api-mcp-substrate-phase1.md`](../roadmaps/dealwatch-api-mcp-substrate-phase1.md)
- a place for concrete request and response shapes, starter prompts, config recipes, skill cards, and a repo-owned MCP inventory snapshot

## What this pack is not

- not an SDK release
- not a hosted multi-tenant control plane guide
- not a write-side automation guide
- not a promise that every route visible in `/openapi.json` is safe to market as stable builder surface

## Stable launch contract

Use these commands as the stable local-first launch contract:

```bash
PYTHONPATH=src uv run python -m dealwatch --help
PYTHONPATH=src uv run python -m dealwatch builder-starter-pack --json
PYTHONPATH=src uv run python -m dealwatch builder-client-config codex --json
PYTHONPATH=src uv run python -m dealwatch builder-client-config --all --json
PYTHONPATH=src uv run python -m dealwatch server
PYTHONPATH=src uv run python -m dealwatch worker
PYTHONPATH=src uv run python -m dealwatch.mcp list-tools --json
PYTHONPATH=src uv run python -m dealwatch.mcp client-starters --json
PYTHONPATH=src uv run python -m dealwatch.mcp client-config --client codex --json
PYTHONPATH=src uv run python -m dealwatch.mcp client-config --all --json
PYTHONPATH=src uv run python -m dealwatch.mcp serve --transport stdio
PYTHONPATH=src uv run python -m dealwatch.mcp serve --transport streamable-http
```

These commands mean:

- the root CLI help now separates runtime, builder discovery, operator-only maintainer, and legacy bridge paths
- the builder-facing CLI discovery banner is reachable through a normal help path
- the root CLI can print the builder contract directly as JSON
- the root CLI can also print one copyable client config export directly as JSON
- the root CLI can also print the full all-clients config bundle directly as JSON
- the current wrapper-status ledger now treats OpenHands, OpenCode, and OpenClaw as `official_wrapper_documented` because their official docs publish concrete local config shapes, not just high-level MCP mentions
- the HTTP server is up
- the local worker can be brought up when you want the full runtime loop
- the shipped MCP tool registry is inspectable, including safe-first order, categories, and argument hints
- the shipped client starter registry is inspectable, including OpenClaw and skill-card anchors
- the MCP CLI can also print one client-specific config export directly as JSON
- the MCP CLI can also print the all-clients config bundle directly as JSON
- the builder starter pack is inspectable through a repo-owned read surface
- the MCP server can be handed to local stdio-capable clients
- the MCP server can also be exposed through streamable HTTP for clients such as Codex that document a URL-based MCP path

## Builder quick path

If you are new, do this in order instead of wandering through the repo:

1. read [`../roadmaps/dealwatch-api-mcp-substrate-phase1.md`](../roadmaps/dealwatch-api-mcp-substrate-phase1.md)
2. run `PYTHONPATH=src uv run python -m dealwatch --help`
3. run `PYTHONPATH=src uv run python -m dealwatch builder-starter-pack --json`
4. run `PYTHONPATH=src uv run python -m dealwatch.mcp list-tools --json`
5. run `PYTHONPATH=src uv run python -m dealwatch.mcp client-starters --json`
6. run `PYTHONPATH=src uv run python -m dealwatch builder-client-config codex --json`
7. run `PYTHONPATH=src uv run python -m dealwatch builder-client-config --all --json`
8. inspect `GET /api/runtime/builder-starter-pack`
9. inspect `GET /api/runtime/builder-client-config/codex`
10. inspect `GET /api/runtime/builder-client-configs`
11. open [`./config-recipes.md`](./config-recipes.md) when you need client-by-client wrapper status
12. open [`./examples/README.md`](./examples/README.md)
13. open [`./skills/README.md`](./skills/README.md) if you want copyable client rule cards
14. choose one first loop:
   - HTTP-first: `GET /api/runtime/readiness` -> `GET /api/runtime/builder-starter-pack` -> `POST /api/compare/preview`
   - MCP-first: `get_runtime_readiness` -> `get_builder_starter_pack` -> `compare_preview`

That order matters.

In plain English:

- first learn the building map
- then read the door labels
- then copy a small example, exported client config, client-specific starter, config recipe, or skill card
- only then start the actual runtime conversation

## First read path

If you are new, do not start by trying to mutate the runtime.

### HTTP-first

1. `GET /api/health`
2. `GET /api/runtime/readiness`
3. `GET /api/runtime/builder-starter-pack`
4. `GET /api/runtime/builder-client-config/{client}`
5. `POST /api/compare/preview`
6. `GET /api/watch-tasks` or `GET /api/watch-groups`
7. `GET /api/recovery-inbox`
8. `GET /api/settings/notifications`
9. `GET /api/settings/store-onboarding-cockpit`

### MCP-first

1. inspect `list-tools --json`
2. `get_runtime_readiness`
3. `get_builder_starter_pack`
4. `get_builder_client_config`
5. `compare_preview`
6. `list_watch_tasks` or `list_watch_groups`
7. one detail read
8. `get_recovery_inbox`
9. `get_notification_settings` or `get_store_onboarding_cockpit`

The safe mental model is:

> check the workshop is open, read the builder contract, preview compare truth, then read what is already there

## Stable now vs deferred vs internal-only

| Tier | What belongs here now | What stays out |
| --- | --- | --- |
| Stable now | read-only MCP tools, health/readiness/recovery/notification/store reads, builder starter pack reads, compare preview, watch/group detail reads | write-side MCP, durable mutation as a builder default |
| Deferred | compare evidence artifact lifecycle, run-due automation, broader write-safe builder workflows | pretending every discovered route is already part of the front door |
| Internal-only | maintenance, owner bootstrap, provider webhook internals, legacy bridge paths, maintainer-only browser debug commands (`probe-live`, `diagnose-live`, `support-bundle`) | marketing those paths as external builder APIs |

## Client quick starts

Exact client config syntax varies across releases.

The stable part is not always the surrounding JSON or TOML wrapper.
The stable part is:

- the local stdio MCP command
- the read-only tool inventory
- the first safe tool flow
- the repo-owned recipe ledger that marks whether wrapper syntax is officially documented here or still intentionally unfrozen
- the direct client-config export surfaces that let a builder copy the current repo-owned example without opening the file tree first
- the all-clients config bundle when one agent wants the whole starter surface in a single read

| Client | Best first move | Safe first flow | What not to assume |
| --- | --- | --- | --- |
| Claude Code | register the local stdio MCP command, then read the substrate doc | `get_runtime_readiness` -> `get_builder_starter_pack` -> `compare_preview` -> `list_watch_tasks` or `list_watch_groups` | no write-side MCP, no hosted remote control plane |
| Codex | point Codex at the local runtime plus the streamable-HTTP MCP contract | `get_runtime_readiness` -> `get_builder_starter_pack` -> `compare_preview` -> one detail read | no SDK, no multi-tenant auth story |
| OpenHands | keep the client in observation mode first even though the skill submission is already filed | runtime readiness -> builder starter pack -> compare preview -> recovery or store cockpit reads | OpenHands/extensions submission is open; do not call it merged until the host accepts it |
| OpenCode | treat DealWatch as a local product truth source, not as a hosted platform service | MCP discovery -> builder starter pack -> compare preview -> watch or group detail | ecosystem-listing candidate only, no first-party store claim |
| OpenClaw | treat DealWatch as a local compare-first truth backend or workflow shell dependency, not as a runtime base | `get_runtime_readiness` -> `get_builder_starter_pack` -> `compare_preview` -> watch or group reads -> recovery or store cockpit reads | the ClawHub skill is live, but the safe first flow still starts from the same local read-only runtime |

Use the recipe ledger when you need the next level of honesty:

- [`./config-recipes.md`](./config-recipes.md)
- [`./recipes/claude-code.md`](./recipes/claude-code.md)
- [`./recipes/codex.md`](./recipes/codex.md)
- [`./recipes/openhands.md`](./recipes/openhands.md)
- [`./recipes/opencode.md`](./recipes/opencode.md)
- [`./recipes/openclaw.md`](./recipes/openclaw.md)

Use the export surfaces when you want the next level of convenience:

- `PYTHONPATH=src uv run python -m dealwatch builder-client-config codex --json`
- `PYTHONPATH=src uv run python -m dealwatch builder-client-config --all --json`
- `GET /api/runtime/builder-client-config/codex`
- `GET /api/runtime/builder-client-configs`
- `get_builder_client_config`
- `list_builder_client_configs`

## Official distribution reality by client

This is the shortest honest matrix for what the official platform surface is, what DealWatch
ships in-repo today, and what we still must **not** claim.

| Client | Official public surface | Repo-owned artifact now | Honest status today |
| --- | --- | --- | --- |
| Claude Code | official marketplace + custom marketplaces | [`plugins/dealwatch-builder-pack/.claude-plugin/plugin.json`](../../plugins/dealwatch-builder-pack/.claude-plugin/plugin.json), [`.claude-plugin/marketplace.json`](../../.claude-plugin/marketplace.json) | marketplace-submission candidate, **not officially listed** |
| Codex | Plugin Directory + repo/personal marketplace | [`plugins/dealwatch-builder-pack/.codex-plugin/plugin.json`](../../plugins/dealwatch-builder-pack/.codex-plugin/plugin.json), [`../../marketplace.json`](../../marketplace.json) | Plugin Directory candidate, **not officially listed** |
| OpenHands | global skill registry | [`./skills/openhands-readonly-builder-skill.md`](./skills/openhands-readonly-builder-skill.md) | active submission is [`OpenHands/extensions#151`](https://github.com/OpenHands/extensions/pull/151) with maintainer-requested changes; [`#152`](https://github.com/OpenHands/extensions/pull/152) is the retired predecessor |
| OpenCode | ecosystem listing | [`./recipes/opencode.md`](./recipes/opencode.md), [`./examples/opencode.jsonc`](./examples/opencode.jsonc) | ecosystem-listing candidate, **not officially listed** |
| OpenClaw | ClawHub public registry | [`./recipes/openclaw.md`](./recipes/openclaw.md), [`./skills/openclaw-readonly-builder-skill.md`](./skills/openclaw-readonly-builder-skill.md), compatible bundle assets under [`plugins/dealwatch-builder-pack/`](../../plugins/dealwatch-builder-pack/) | live on ClawHub as `dealwatch-readonly-builder` |

## Official MCP Registry reality

The protocol itself now also has an official public registry surface:

- official public surface: MCP Registry (preview)
- official docs:
  - `https://modelcontextprotocol.io/registry/about`
  - `https://modelcontextprotocol.io/registry/quickstart`
  - `https://modelcontextprotocol.io/registry/package-types`
  - `https://modelcontextprotocol.io/specification/draft/basic/server-discovery`
- repo-owned DealWatch reality today:
  - the local read-only MCP server already exists
  - the Python package metadata now includes publish-oriented `readme`, `license`, `project.urls`, and console-script entrypoints in `pyproject.toml`
  - CI now also guards that package surface through `scripts/verify_package_publish_surface.py` plus an sdist/wheel build in the main `test` lane
  - the builder docs and bundle assets already describe the local-first launch path
- honest status today:
  - public package is live on PyPI as `dealwatch==1.0.1`
  - the Official MCP Registry entry is live as `io.github.xiaojiou176-open/dealwatch`
  - the repo still stays local-first and read-only even though the registry layer is now published

In plain English:

DealWatch now has both halves of the MCP story: the product side and the registry/package side are both public.

That means the remaining stop line is no longer “publish the first package.”
It is:

- keep the active OpenHands line on `#151` until the host accepts it, while treating `#152` as a retired predecessor
- wait for directory-style host reviews such as MCP.so
- decide which additional first-party host surfaces deserve a live listing beyond the current local-first boundary

## File map

Start here:

- [`../roadmaps/dealwatch-api-mcp-substrate-phase1.md`](../roadmaps/dealwatch-api-mcp-substrate-phase1.md)
- [`./config-recipes.md`](./config-recipes.md)
- [`./examples/README.md`](./examples/README.md)
- [`./prompt-starters.md`](./prompt-starters.md)

Concrete example payloads:

- [`./examples/mcp-list-tools.response.json`](./examples/mcp-list-tools.response.json)
- [`./examples/mcp-client-starters.response.json`](./examples/mcp-client-starters.response.json)
- [`./examples/mcp-builder-starter-pack.call.json`](./examples/mcp-builder-starter-pack.call.json)
- [`./examples/compare-preview.request.json`](./examples/compare-preview.request.json)
- [`./examples/compare-preview.response.json`](./examples/compare-preview.response.json)
- [`./examples/http-builder-starter-pack.response.json`](./examples/http-builder-starter-pack.response.json)
- [`./examples/runtime-readiness.response.json`](./examples/runtime-readiness.response.json)
- [`./examples/http-watch-task-detail.response.json`](./examples/http-watch-task-detail.response.json)
- [`./examples/mcp-compare-preview.call.json`](./examples/mcp-compare-preview.call.json)
- [`./examples/mcp-runtime-readiness.call.json`](./examples/mcp-runtime-readiness.call.json)
- [`./examples/mcp-watch-task-detail.call.json`](./examples/mcp-watch-task-detail.call.json)
- [`./examples/mcp-stdio.launch.json`](./examples/mcp-stdio.launch.json)
- [`./examples/mcp-builder-client-config.call.json`](./examples/mcp-builder-client-config.call.json)
- [`./examples/mcp-builder-client-configs.call.json`](./examples/mcp-builder-client-configs.call.json)
- [`./examples/http-builder-client-config.response.json`](./examples/http-builder-client-config.response.json)
- [`./examples/http-builder-client-configs.response.json`](./examples/http-builder-client-configs.response.json)
- [`./examples/cli-builder-client-config.response.json`](./examples/cli-builder-client-config.response.json)
- [`./examples/cli-builder-client-configs.response.json`](./examples/cli-builder-client-configs.response.json)

Client wrapper example files:

- [`./examples/claude-code.mcp.json`](./examples/claude-code.mcp.json)
- [`./examples/codex-mcp-config.toml`](./examples/codex-mcp-config.toml)
- [`./examples/openhands-config.toml`](./examples/openhands-config.toml)
- [`./examples/opencode.jsonc`](./examples/opencode.jsonc)
- [`./examples/openclaw-mcp-servers.json`](./examples/openclaw-mcp-servers.json)

Per-client prompt files:

- [`./prompts/claude-code-starter.md`](./prompts/claude-code-starter.md)
- [`./prompts/codex-starter.md`](./prompts/codex-starter.md)
- [`./prompts/openclaw-starter.md`](./prompts/openclaw-starter.md)
- [`./prompts/openhands-starter.md`](./prompts/openhands-starter.md)
- [`./prompts/opencode-starter.md`](./prompts/opencode-starter.md)

Client config recipes:

- [`./recipes/claude-code.md`](./recipes/claude-code.md)
- [`./recipes/codex.md`](./recipes/codex.md)
- [`./recipes/openhands.md`](./recipes/openhands.md)
- [`./recipes/opencode.md`](./recipes/opencode.md)
- [`./recipes/openclaw.md`](./recipes/openclaw.md)

Shared prompt summary:

- [`./prompt-starters.md`](./prompt-starters.md)

Copyable builder skill card:

- [`./skills/README.md`](./skills/README.md)
- [`./skills/dealwatch-readonly-builder-skill.md`](./skills/dealwatch-readonly-builder-skill.md)

Per-client skill files:

- [`./skills/claude-code-readonly-builder-skill.md`](./skills/claude-code-readonly-builder-skill.md)
- [`./skills/codex-readonly-builder-skill.md`](./skills/codex-readonly-builder-skill.md)
- [`./skills/openhands-readonly-builder-skill.md`](./skills/openhands-readonly-builder-skill.md)
- [`./skills/opencode-readonly-builder-skill.md`](./skills/opencode-readonly-builder-skill.md)
- [`./skills/openclaw-readonly-builder-skill.md`](./skills/openclaw-readonly-builder-skill.md)

## Repo-owned builder pack, native bundle candidates, and listing-prep assets

DealWatch now ships a **repo-owned builder pack**, **native plugin bundle candidates where the
platform already supports them**, and **listing-prep assets** for the broader builder/public
frontdoor.

The honest current shape is still local-first:

- one repo-owned stdio MCP launch command
- one read-only tool inventory
- one repo-owned client starter registry plus a builder starter pack read surface
- one starter prompt file per named client
- one shared skill card plus client-specific skill cards
- one shared native bundle at [`../../plugins/dealwatch-builder-pack/`](../../plugins/dealwatch-builder-pack/) for Claude Code and Codex, plus repo marketplaces at [`../../.claude-plugin/marketplace.json`](../../.claude-plugin/marketplace.json) and [`../../marketplace.json`](../../marketplace.json)
- one crawlable public frontdoor across `builders.html`, `llms.txt`, `feed.xml`, `sitemap.xml`, and the social preview asset

Not every client has a native package today:

- Claude Code and Codex now have repo-owned native bundle artifacts
- OpenHands now has an active submission in `OpenHands/extensions#151`, but it is still waiting on host acceptance after requested changes; `#152` is a retired predecessor
- OpenCode remains an ecosystem-listing candidate
- OpenClaw now has a live ClawHub skill backed by the same compatible bundle assets and repo-native docs

Those artifacts still live in the repo as builder material first, but they no longer all stop at “candidate” status.

That is enough to make plugin packaging, listing-prep copy, and SEO frontdoor work real without pretending every host listing or hosted plugin ecosystem already exists.

## Boundary reminder

If your plan needs any of the following, you are already outside the current builder promise:

- write-side MCP
- generic remote-safe operator control
- owner bootstrap as a general auth path
- maintenance or cleanup as external builder APIs
- browser debug lane commands as external builder APIs
- webhook or provider-secret flows as generic client integration
- SDK packaging or hosted multi-tenant maturity claims
