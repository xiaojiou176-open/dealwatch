# Runtime Hygiene

## Why this exists

DealWatch now treats runtime hygiene as part of the product contract, not as an afterthought.

In plain language:

- `.runtime-cache/` is the product workbench
- `.runtime-cache/operator/` is the repo-owned operator evidence namespace
- `.legacy-runtime/` is the deprecated SQLite bridge namespace
- `.pnpm-store/` is the canonical repo-local dependency store
- shared machine caches such as `~/.cache/uv` or `~/Library/Caches/ms-playwright` are **not** part of the default cleanup execution path

The goal is to keep repo-local rebuildables and runtime leftovers under control **without** pretending that shared machine-wide caches belong to this repo alone.

Host / process safety is part of that same contract:

- DealWatch must never "clean the room" by killing broad host processes or driving desktop UI.
- If the repo cannot prove a browser/profile/process belongs to DealWatch, the correct answer is "leave it alone and record the blocker."
- `python3 scripts/verify_host_process_safety.py` is the repo gate that keeps `killall`, `pkill`, broad `kill -9`, `osascript`, `System Events`, `loginwindow`, and direct signal helpers out of executable paths.
- `scripts/clean.py` is no longer a valid cleanup path; it now hard-fails so wide-delete reset behavior cannot wipe protected DealWatch evidence.

## Canonical namespaces

- Product runtime artifacts: `.runtime-cache/`
- Operator artifacts: `.runtime-cache/operator/`
- Legacy bridge namespace: `.legacy-runtime/`
- Canonical pnpm store: `.pnpm-store/`

`frontend/.pnpm-store/` is drift and should not exist after the canonical store rule is in place.

DealWatch keeps the repo-local namespace deliberately small:

- `.runtime-cache/`
- `.runtime-cache/operator/`
- `.legacy-runtime/`
- `.pnpm-store/`

Repo-owned external lightweight caches live under:

- `~/.cache/dealwatch/`

If a path lives outside those roots, treat it as shared-layer or machine-wide until proven otherwise.

## Path classes

Use the same four labels everywhere instead of inventing one-off wording:

- `runtime evidence`: product logs and run artifacts under `.runtime-cache/`
- `operator evidence`: maintainer-facing bundles and preserved review material under `.runtime-cache/operator/`
- `dependency rebuildable`: repo-local dependency copies such as `.venv`, `.pnpm-store`, and `frontend/node_modules`
- `disposable generated`: rebuildable output such as `build/`, `frontend/dist`, and `.pytest_cache`

`build/` is now part of the default repo-local rebuildables cleanup path.

## Product maintenance entrypoint

Use the product maintenance command for runtime logs, reports, and watch-task runs:

```bash
PYTHONPATH=src uv run python -m dealwatch maintenance --dry-run
PYTHONPATH=src uv run python -m dealwatch maintenance --apply
```

This command is allowed to touch only:

- `.runtime-cache/logs`
- `.runtime-cache/runs`
- `.runtime-cache/runs/reports`
- `.runtime-cache/operator/**`
- `~/.cache/dealwatch/**`

It must not touch:

- `.git`
- shared external caches
- `.legacy-runtime`

## Repo-local rebuildables cleanup

Use the dedicated cleanup script when you want to reclaim rebuildable local artifacts:

```bash
python3 scripts/audit_runtime_footprint.py
python3 scripts/audit_runtime_footprint.py --format json
python3 scripts/cleanup_local_rebuildables.py --dry-run
python3 scripts/cleanup_local_rebuildables.py --apply
python3 scripts/cleanup_local_rebuildables.py --apply --heavy
```

Default cleanup set:

- `.pytest_cache`
- `.runtime-cache/operator/temp`
- `.runtime-cache/operator/smoke`
- `build/`
- `frontend/dist`

Heavy cleanup set:

- `.venv`
- `frontend/node_modules`
- `frontend/.pnpm-store`

The heavy set is intentionally opt-in because it trades disk space for rebuild time.

The legacy `scripts/clean.py` entrypoint is intentionally no longer part of any cleanup sequence. Use the canonical maintenance / rebuildable / operator cleanup commands instead of reviving a wide-delete shortcut.

## Operator evidence cleanup

Use the dedicated operator-evidence cleanup script when you want the second-wave hygiene pass for `.runtime-cache/operator/`:

```bash
python3 scripts/cleanup_operator_artifacts.py --dry-run
python3 scripts/cleanup_operator_artifacts.py --apply
```

Policy:

- keep exactly one latest `gif-frames*` directory by mtime
- delete the other `gif-frames*` directories as duplicate PNG evidence bundles
- preserve `gemini-audit/`
- preserve `*.patch`, `*.tgz`, `*history*`, and `*release*` evidence files

This script does not touch `temp/` or `smoke/`; those remain part of the rebuildables cleanup path.

## Cache budget

DealWatch now keeps a single lightweight cache budget:

- `CACHE_BUDGET_BYTES=4294967296` by default
- scope:
  - `.runtime-cache/**`
  - `~/.cache/dealwatch/**`
- protected keep path inside that external root:
  - `~/.cache/dealwatch/browser/chrome-user-data/**`
- not in scope:
  - `.venv`
  - `.pnpm-store`
  - `frontend/node_modules`
  - `.legacy-runtime`
  - shared machine-wide caches

Budget enforcement happens after TTL cleanup. If the repo is still over budget but only protected evidence remains, maintenance records `budget_exceeded_but_protected` instead of deleting protected evidence.

The dedicated browser root is special:

- `~/.cache/dealwatch/browser/chrome-user-data/**` is a persistent browser workspace
- it does **not** participate in TTL cleanup
- it does **not** participate in cache budget reclamation
- it does **not** belong in rebuildable cleanup
- before the one-time migration into this root, fully quit any real Google Chrome process still using the default root under `~/Library/Application Support/Google/Chrome`

## Shared external layers

The following are still audit targets, but **not** v1 cleanup execution targets:

- `~/.cache/uv`
- `~/.npm`
- `~/.cache/pre-commit`
- `~/Library/Caches/ms-playwright`
- `~/.cache/node/corepack`
- `<macOS temp cache dir>`
- Docker build cache / images / volumes

If a future cleanup wave wants to touch them, that work must be scoped as shared-layer cleanup, not repo-local cleanup.
Do not mislabel shared-layer reclaim as repo reclaim.

## Cleanup sequence

1. Stop API / worker / frontend dev processes that may hold repo-local paths open.
2. Run:

   ```bash
   python3 scripts/audit_runtime_footprint.py
   PYTHONPATH=src uv run python -m dealwatch maintenance --dry-run
   python3 scripts/cleanup_local_rebuildables.py --dry-run
   ```

3. Apply low-risk repo-local cleanup first.
4. Apply heavy cleanup only if you accept dependency rebuild time.
5. Rebuild:

   ```bash
   uv sync --frozen --group dev
   cd frontend && corepack enable && pnpm install --frozen-lockfile
   ```

6. Verify:

   ```bash
   ./scripts/test.sh -q
   ./scripts/smoke_product_hermetic.sh
   python3 scripts/verify_host_process_safety.py
   python3 scripts/verify_root_allowlist.py
   python3 scripts/verify_tracked_artifacts.py
   PYTHONPATH=src uv run python -m dealwatch maintenance --dry-run
   ```

## What should never be confused

- `can rebuild` does not mean `should delete right now`
- `large` does not mean `garbage`
- `external` does not mean `unrelated`
- `shared` does not mean `safe to clean during repo maintenance`
