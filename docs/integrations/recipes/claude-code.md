# DealWatch Recipe For Claude Code

## Honest status

- DealWatch launch record: `repo-verified`
- Claude Code wrapper syntax: `official_wrapper_documented`
- Recipe kind: `official`
- Current posture: `local-first`, `read-only-first`, `compare-first`
- Official docs: `https://docs.anthropic.com/en/docs/claude-code/mcp`

## Repo-owned launch command

```bash
PYTHONPATH=src uv run python -m dealwatch.mcp serve --transport stdio
```

## Claude Code wrapper example

Claude Code's MCP docs currently describe both:

- project-scoped `.mcp.json` with `mcpServers`, `command`, `args`, and `env`
- `claude mcp add --transport stdio --scope project <name> -- <command> [args...]`

When the config file lives at the repo root, the current DealWatch translation looks like:

```json
{
  "mcpServers": {
    "dealwatch": {
      "command": "uv",
      "args": ["run", "python", "-m", "dealwatch.mcp", "serve", "--transport", "stdio"],
      "env": {
        "PYTHONPATH": "src"
      }
    }
  }
}
```

The same example lives in repo-owned form at [`../examples/claude-code.mcp.json`](../examples/claude-code.mcp.json).

If you prefer the Claude Code CLI path, the current documented command shape translates to:

```bash
claude mcp add --transport stdio --scope project -e PYTHONPATH=src \
  dealwatch -- uv run python -m dealwatch.mcp serve --transport stdio
```

## Evidence basis

- Official docs: <https://docs.anthropic.com/en/docs/claude-code/mcp>
- Verified wrapper surface in those docs:
  - `.mcp.json`
  - `mcpServers`
  - `command`
  - `args`
  - `env`
  - `claude mcp add --transport stdio`

## Safe-first flow

1. `get_runtime_readiness`
2. `get_builder_starter_pack`
3. `compare_preview`
4. `list_watch_tasks` or `list_watch_groups`
5. `get_recovery_inbox` or `get_store_onboarding_cockpit`

## Stop line

Do not translate this recipe into:

- write-side MCP
- hosted auth
- official plugin wording
- builder-facing recommendation wording
