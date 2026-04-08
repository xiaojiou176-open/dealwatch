# DealWatch Client Config Recipes

This file is the builder-side recipe ledger for DealWatch.

In plain English:

- `client-starters --json` tells you what DealWatch ships
- this recipe ledger tells you how far each client can be wired honestly today
- the key split is whether the client wrapper syntax is backed by current official docs and which repo-owned transport it sits on top of

Last verified: `2026-04-05`

## Status legend

| Status | What it means |
| --- | --- |
| `official_wrapper_documented` | the surrounding client wrapper shape is backed by current official client docs and the repo-owned DealWatch launch command |
| `official_local_config_documented` | the client's local config surface is documented by the official client docs, but DealWatch still only claims a local-first read-only adapter pattern |

After the current wrapper-status sync, every shipped client in this ledger now lands in the `official_wrapper_documented` bucket.

## Current recipe ledger

| Client | Wrapper status | Recipe kind | Official source | Recipe |
| --- | --- | --- | --- | --- |
| Claude Code | `official_wrapper_documented` | `official` | [Claude Code MCP docs](https://docs.anthropic.com/en/docs/claude-code/mcp) | [`recipes/claude-code.md`](./recipes/claude-code.md) |
| Codex | `official_wrapper_documented` | `official` | [OpenAI Codex MCP docs](https://developers.openai.com/codex/mcp/) | [`recipes/codex.md`](./recipes/codex.md) |
| OpenHands | `official_wrapper_documented` | `official` | [OpenHands MCP server docs](https://docs.openhands.dev/openhands/usage/cli/mcp-servers) | [`recipes/openhands.md`](./recipes/openhands.md) |
| OpenCode | `official_wrapper_documented` | `official` | [OpenCode MCP docs](https://opencode.ai/docs/mcp-servers/) | [`recipes/opencode.md`](./recipes/opencode.md) |
| OpenClaw | `official_wrapper_documented` | `official` | [OpenClaw MCP docs](https://docs.openclaw.ai/cli/mcp) | [`recipes/openclaw.md`](./recipes/openclaw.md) |

These five clients are marked `official_wrapper_documented` only because the linked official docs now publish their local wrapper/config syntax directly, not just MCP transport concepts in the abstract.

## Shared launch record

Most recipes in this directory start from the same repo-verified `stdio` launch command:

```bash
PYTHONPATH=src uv run python -m dealwatch.mcp serve --transport stdio
```

Codex is the one exception today because the official Codex docs publish a URL-first MCP wrapper. For Codex, the repo also owns:

```bash
PYTHONPATH=src uv run python -m dealwatch.mcp serve --transport streamable-http
```

with the locally verified endpoint:

```text
http://127.0.0.1:8000/mcp
```

Think of these commands like appliance plugs and the client wrappers like different wall sockets.

## Shared safe-first flow

Every recipe in this directory also keeps the same safe-first flow:

1. `get_runtime_readiness`
2. `get_builder_starter_pack`
3. `compare_preview`
4. one watch/group/runtime/store read

Concrete wrapper examples that are currently safe to mirror live under:

- [`examples/claude-code.mcp.json`](./examples/claude-code.mcp.json)
- [`examples/codex-mcp-config.toml`](./examples/codex-mcp-config.toml)
- [`examples/openhands-config.toml`](./examples/openhands-config.toml)
- [`examples/opencode.jsonc`](./examples/opencode.jsonc)
- [`examples/openclaw-mcp-servers.json`](./examples/openclaw-mcp-servers.json)

## How to read these recipes

- If a recipe says `official`, the surrounding wrapper syntax is documented by the current official client docs.
- If the client's own docs recommend a proxy, remote bridge, or production hardening layer, DealWatch still keeps its story smaller: local-first, read-only-first, compare-first.

## Boundary reminder

These recipes do **not** mean:

- every builder host already has a live first-party listing
- every client wrapper schema is frozen forever
- write-side MCP is ready
- DealWatch runs on Claude Code, Codex, OpenHands, OpenCode, or OpenClaw

The honest reading is smaller: DealWatch now has a mixed state. PyPI, the Official MCP Registry, and the ClawHub skill are live; the OpenHands/extensions and MCP.so submissions are filed; Claude Code, Codex, OpenCode, and the Chrome Web Store still remain repo-owned or pending rather than first-party live listings.
