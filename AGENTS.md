# DealWatch AGENTS

## Identity

- This repository is a **price-tracking product repository**
- The product runtime is:
  - FastAPI API
  - APScheduler worker
  - PostgreSQL
  - Preact WebUI
- The scraping engine remains inside the repo and is reused by the product

## Non-Negotiables

- `dealwatch` is the only live name
- No `tracker` aliases
- No `var/` runtime paths
- No new product writes to legacy SQLite as the product source of truth
- No static HTML report pretending to be the WebUI

## Runtime Truth

- Product data: PostgreSQL via `DATABASE_URL`
- Legacy import source: `.legacy-runtime/data/dealwatch.db`
- Runtime artifacts: `.runtime-cache/`
- Repo-local operator artifacts: `.runtime-cache/operator/`
- Repo-owned external cache root: `~/.cache/dealwatch/`
- Dedicated DealWatch browser root: `~/.cache/dealwatch/browser/chrome-user-data/`
- Product runtime maintenance entrypoint: `python -m dealwatch maintenance --dry-run|--apply`
- Repo-local rebuildable cleanup entrypoint: `python scripts/cleanup_local_rebuildables.py --dry-run|--apply [--heavy]`
- Runtime schema bootstrap: `PRODUCT_AUTO_CREATE_SCHEMA` is a temporary bootstrap bridge, not the long-term authoritative migration workflow

## Expected Working Areas

- `src/dealwatch/core/`, `src/dealwatch/stores/`: engine
- `src/dealwatch/persistence/`, `src/dealwatch/application/`, `src/dealwatch/api/`, `src/dealwatch/worker/`: product
- `frontend/`: WebUI

## Verification Baseline

```bash
./scripts/test.sh -q
```

## CI Layering Contract

- Repository tier: `Heavy`
- Stack shape: `Dual-runtime`
- Browser flag: `yes`
- External-proof flag: `yes`
- Required five layers:
  - `pre-commit` = fast hygiene via `pre-commit run --all-files`
  - `pre-push` = managed hook (`git diff --check`, `actionlint`, host/sensitive/artifact/root guards)
  - `hosted` = required GitHub checks on `main`
  - `nightly` = scheduled `CodeQL` plus nightly Dependabot maintenance intake
  - `manual` = hermetic smoke, credentialed remote verification, browser debug lane, and other live/platform proofs
- There is no separate `weekly` verification lane in the current contract. Any older weekly wording
  should either be treated as historical or folded into `nightly` / `manual`.

## Host / Process Safety

- Treat host-level process control as hazardous. DealWatch must never mass-match, mass-kill, or desktop-drive the shared machine just to recover repo state.
- Do **not** introduce `killall`, `pkill`, broad `kill -9`, `osascript`, `System Events`, `loginwindow`, `CGSession`, `showForceQuitPanel`, `kAEShowApplicationWindow`, `aevt,apwn`, `AppleEvent`, direct `process.kill(...)`, or direct `os.kill(...)` into repo code, tests, scripts, or CI.
- Only signal a repo-recorded positive child PID that DealWatch itself spawned.
- `scripts/clean.py` is now a forbidden legacy entrypoint. Do not resurrect wide-delete cleanup; use the canonical maintenance and cleanup commands instead.
- Browser/profile cleanup must stay on repo-owned entrypoints such as `./scripts/launch_dealwatch_chrome.sh`, `python3 scripts/open_dealwatch_account_pages.py`, `python3 scripts/cleanup_local_rebuildables.py`, and `python -m dealwatch maintenance --dry-run|--apply`; if ownership is ambiguous, refuse and report it instead of guessing.
- The repository guard for this boundary is `python3 scripts/verify_host_process_safety.py`; keep both CI and pre-commit green.

## Git / GitHub Closeout Boundary

- Default rule: do not commit, push, open PRs, merge, or delete branches/worktrees unless the current turn explicitly authorizes Git/GitHub writes.
- When the current turn **does** authorize Git/GitHub writes, the only allowed external write target is **this repository's** Git / GitHub surface.
- For this repo, default GitHub write identity is `xiaojiou176`.
- If an independent approval/review step is required, use `leilei999lei-lab` as the second account.
- Do **not** use `terryyifeng` in this repo.
- If `main` protection requires review, do not pretend a direct push is the closeout path. Use a controlled branch -> PR -> approval -> merge flow.
- Target closeout shape is: `main` as the final landing branch, one retained worktree, and no stale delivery PR/branch left half-open.
- Never force-push, hard-reset, or treat review gaps as if approval already happened.

## Browser / Profile Isolation

- This machine is a **multi-repo** environment. Do not assume any existing Chrome / Chromium window, tab, profile, or debug listener belongs to DealWatch.
- The long-term DealWatch browser contract now uses a dedicated Chrome root at `~/.cache/dealwatch/browser/chrome-user-data/`.
- Before browser work, inspect the current machine state and decide whether the target instance is provably DealWatch-owned or not.
- If the machine already has **more than 6 browser instances**, do not open another one just to "try one more time". Finish non-browser work first or wait for active owners to recover their resources.
- Only attach to a browser instance when you can prove it is DealWatch-owned:
  - repo-owned `CHROME_USER_DATA_DIR`
  - explicit DealWatch profile contract
  - or a DealWatch-created throwaway debug lane for the current turn
- A real DealWatch Chrome profile contract now requires all three values together:
  - `CHROME_USER_DATA_DIR`
  - `CHROME_PROFILE_NAME`
  - `CHROME_PROFILE_DIRECTORY`
- The old shared-root contract is deprecated for `dealwatch`; do not point `CHROME_USER_DATA_DIR` at the default macOS Google Chrome user-data root when `CHROME_PROFILE_NAME=dealwatch`.
- Before running the one-time migration into the dedicated DealWatch root, fully quit any real Google Chrome process still using the default macOS Google Chrome user-data root.
- The preferred long-term mode is one dedicated DealWatch Chrome instance plus CDP attach:
  - launch the instance against the dedicated root
  - keep it running
  - have both human operators and automation attach to it
  - do not second-launch the same root
- The canonical DealWatch browser lane now also includes a human-facing identity anchor at `.runtime-cache/browser-identity/index.html`.
  - Keep that identity tab visible when practical so humans can recognize the lane quickly.
  - Manual one-time pinning is allowed.
  - Do not automate Chrome private avatar/theme tweaks, Dock hacks, or other brittle browser-private customization.
- If you cannot prove ownership, treat that browser/profile/tab as another repo's active workspace and do not touch it.
- Do not treat an existing shared Chrome window, a random open tab, or an unknown reachable listener as DealWatch's browser just because it is there.
- Keep `storage_state` mainline and browser debug lane separate:
  - repo-owned debug bootstrap success is **not** authenticated-profile proof
  - clone/debug lane evidence is **not** raw/original profile truth
- For real authenticated profile / listener checks, 1 to 2 fresh attempts are enough. If those attempts already prove the required DealWatch-owned session/listener is absent, stop, record it as an external blocker in the closeout ledger, and do not brute-force more browser launches.
- Minimize focus stealing. Prefer non-disruptive browser actions and keep any unavoidable focus-stealing steps to the smallest possible count.
- If the current turn creates temporary `CHROME_USER_DATA_DIR`, cloned profile data, throwaway debug tabs, or repo-owned Chrome/Chromium instances, close and delete them before closeout.
- If the current turn opens tabs or windows for DealWatch, this repo owns the responsibility to close those same temporary tabs/windows before closeout.

## Resource Hygiene

- Only clean DealWatch-owned rebuildables, caches, temp directories, browser profiles, Docker artifacts, and operator byproducts.
- Repo-owned lightweight cache budget now targets `.runtime-cache/**` plus `~/.cache/dealwatch/**`.
- `~/.cache/dealwatch/browser/chrome-user-data/**` is a persistent dedicated browser workspace. Exclude it from TTL cleanup, cache budget reclamation, and rebuildable cleanup.
- `.runtime-cache/browser-identity/**` is a repo-owned browser lane identity anchor. Keep it out of rebuildable cleanup unless the browser lane itself is being intentionally rotated.
- `.serena/` is a local MCP/tool cache namespace. Keep it ignored, but do not count it as DealWatch-owned cache and do not include it in DealWatch cleanup/budget ledgers.
- Shared-layer caches such as `~/.cache/uv`, `~/.cache/pre-commit`, `~/.cache/node/corepack`, `~/Library/Caches/ms-playwright`, and `~/.npm` remain audit-only and must not be auto-cleaned by DealWatch.
- Prefer repo-owned cleanup entrypoints before ad-hoc shell deletion:
  - `python3 scripts/cleanup_local_rebuildables.py --dry-run|--apply [--heavy]`
  - `python3 scripts/audit_runtime_footprint.py`
  - `python -m dealwatch maintenance --dry-run|--apply`
- When browser/Docker/cache ownership is part of the task, load the repo-local skill `resource-hygiene-and-browser-isolation`.
- Do **not** run global cleanup like `docker system prune -a`, and do not delete containers / images / volumes you cannot prove belong to DealWatch.
- Do **not** delete shared browser caches, shared temp trees, or another repo's cloned profiles/tabs just because they look large.
- Repo-owned build outputs such as `build/`, `frontend/dist`, and `.pytest_cache` should not be left behind after verification if they are no longer needed.
- If a Docker container/image/volume or browser temp/profile cannot be proved to belong to DealWatch, record it as `ownership unknown` and leave it alone.

## External Write Safety

- Outside this repo's explicitly authorized Git / GitHub actions, do not write to Terry's other external accounts or services.
- That means no ad-hoc posting, messaging, account/profile edits, LinkedIn/Reddit/Discourse/Xiaohongshu activity, browser/bookmark/history changes, Messages/contact changes, or third-party platform writes that are not strictly required for DealWatch Git/GitHub closeout.

## Sensitive Inputs

- `DATABASE_URL`
- `OWNER_BOOTSTRAP_TOKEN`
- `POSTMARK_SERVER_TOKEN`

Never print or commit real secrets.
