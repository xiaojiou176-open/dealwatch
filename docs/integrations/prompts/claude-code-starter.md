# DealWatch Starter Prompt For Claude Code

Use this after registering the local stdio MCP server from [`../recipes/claude-code.md`](../recipes/claude-code.md):

```bash
PYTHONPATH=src uv run python -m dealwatch.mcp serve --transport stdio
```

## Safe first objective

Use DealWatch as a read-only compare-first truth source.

## Must do

1. Call `get_runtime_readiness` first.
2. Call `get_builder_starter_pack` before deeper integration work.
3. Use `compare_preview` before assuming a URL should become durable state.
4. Prefer `list_watch_tasks`, `list_watch_groups`, `get_watch_task_detail`, `get_watch_group_detail`, `get_recovery_inbox`, and `get_store_onboarding_cockpit` for truth reads.

## Must not do

- Do not assume write-side MCP exists.
- Do not present DealWatch as a hosted SaaS.
- Do not claim recommendation is available through builder or MCP surfaces.

## Starter prompt

```text
Use DealWatch as a local-first, read-only product truth source.
First call get_runtime_readiness.
Then call get_builder_starter_pack so the current repo-owned contract is explicit.
If the runtime is healthy enough, call compare_preview before making any assumptions about product identity.
After compare_preview, stay on read-only surfaces: inspect watch tasks/groups, recovery inbox, notification settings, and store onboarding cockpit truth.
Do not assume write-side MCP, hosted auth, SDK packaging, or recommendation support.
```
