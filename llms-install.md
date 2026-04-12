# DealWatch MCP Install For Cline

This file is the shortest reviewer-facing install path for Cline.

In plain English:

- DealWatch is a **local-first, read-only-first** MCP server
- the current honest Cline path is **local stdio**
- this repo is **not** a hosted remote control plane and **not** a write-side automation server

## What you need first

- Python `3.11+`
- `uv` installed
- a local clone of this repository

## 1. Prepare the local repo

From the repo root:

```bash
cp .env.example .env
docker compose up -d postgres
uv sync --frozen
PYTHONPATH=src uv run python -m dealwatch.mcp list-tools --json
```

Why these two commands matter:

- `cp .env.example .env` gives the local runtime the bootstrap and database defaults it expects
- `docker compose up -d postgres` starts the local PostgreSQL service that the current MCP runtime depends on
- `uv sync --frozen` installs the exact local runtime this repo expects
- `list-tools --json` proves the MCP surface is reachable before Cline tries to launch it

If port `15432` is already occupied on your machine, start PostgreSQL on another local port and point `DATABASE_URL` at that port before you launch the MCP server.

## 2. Add the server to Cline

Cline documents MCP servers through `cline_mcp_settings.json`.
The official docs describe the file at:

```text
~/.cline/data/settings/cline_mcp_settings.json
```

Add this entry inside `mcpServers`:

```json
{
  "mcpServers": {
    "dealwatch": {
      "command": "uv",
      "args": ["run", "python", "-m", "dealwatch.mcp", "serve", "--transport", "stdio"],
      "env": {
        "PYTHONPATH": "src",
        "OWNER_BOOTSTRAP_TOKEN": "set-a-local-random-string"
      },
      "disabled": false
    }
  }
}
```

Important detail:

- open the cloned DealWatch repo as the working folder before you use the server
- the `PYTHONPATH=src` setting is required because the module is launched from this repo checkout
- `OWNER_BOOTSTRAP_TOKEN` must be a **non-empty local secret string** so the runtime preflight can start; it is a local bootstrap guard, not a public hosted credential

## 3. What success looks like

After Cline reloads MCP settings, DealWatch should appear as a local MCP server.

The first honest tool flow is:

1. `get_runtime_readiness`
2. `get_builder_starter_pack`
3. `compare_preview`
4. one read-only detail call such as watch/group/runtime truth

## 4. What not to assume

- not a hosted SaaS install
- not a write-side automation surface
- not an SDK
- not a promise that every route in the repo is part of the public Cline contract

## Troubleshooting

- If port `15432` is already occupied on your machine, start the local PostgreSQL service on another free port and point `DATABASE_URL` at that port before launching the MCP server.
- If the server exits immediately, re-run `PYTHONPATH=src uv run python -m dealwatch.mcp list-tools --json` first; that is the fastest way to confirm the local runtime and MCP surface are both reachable.

## Read next

- [`README.md`](./README.md)
- [`INTEGRATIONS.md`](./INTEGRATIONS.md)
- [`docs/integrations/README.md`](./docs/integrations/README.md)
