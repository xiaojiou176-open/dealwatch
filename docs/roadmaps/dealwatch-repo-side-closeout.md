# DealWatch Repo-Side Closeout

## Purpose

This document records what the repository and Git history prove after the April 5 dual-mainline re-check, the browser/account hardening package through PR `#70`, the builder/public distribution landing in PR `#74`, the later final-push closeout merge in PR `#76`, and the package publish-surface guard landing in PR `#79`.

In plain English:

- the old Wave 3 through Wave 6 repo-side work was re-audited instead of being trusted by archive wording alone
- the browser identity layer and host/process safety package are landed on `main`
- the builder/public distribution slice is landed on `main`, the later browser truth plus official MCP Registry reality follow-up is landed through PR `#76` / `c38470c`, and package publish-surface guarding is now landed through PR `#79` / `efde917`
- repo truth, Git/GitHub truth, live/public truth, and browser/session truth remain separate ledgers
- only real external blockers stay visible

This is not a hosted-runtime success claim. Render/live proof still lives in the separate live-truth ledger.

## Current Verdict

> **Repo-side verdict:** `the latest merged head on main is PR #79 / efde917, and it now carries the package publish-surface guard on top of the earlier PR #76 browser truth sync and PR #74 builder/public distribution landing; Git/GitHub closeout is clean at the repo-owned layer, while live Render proof, external listing or registry publication, and GitHub UI-only social preview selection remain the only external blockers in this ledger`.

That is the honest call because:

- the April 3 master-wave baseline still stands
- PR `#60` through PR `#79` now form the merged closeout foundation
- the builder/public distribution landing remains merged on `main` through PR `#74`
- merge commit `efde917` now carries the package publish-surface guard on top of the earlier PR `#76` browser truth sync, MCP Registry reality note, and PR `#74` asset landing
- fresh local verification is green for builder contract sync, site/public/docs verifiers, host/process safety, frontend build, targeted builder tests, and the full repository baseline
- Git/GitHub closure is now back in sync because secret scanning no longer shows open alerts after the two historical PR-body locations were independently verified as invalid (`401`) and resolved as `revoked`
- those alerts were historical PR-body locations, not current source-file leaks in the working tree

## Current Truth Snapshot

| Field | Current value |
| --- | --- |
| Date | `2026-04-06` |
| Fresh merged-main baseline | `main` is aligned with `origin/main` at `efde917`; PR `#79` is merged; one worktree remains |
| Recent truth-sync delivery branch | `codex/final-package-gate` |
| Working tree | clean on `main` after fast-forwarding the merged PR `#79` tip and cleaning stale local delivery branches |
| Open PRs | `0` |
| Open issues | `0` |
| Open Dependabot alerts | `0` |
| Open code-scanning alerts | `0` |
| Open secret-scanning alerts | `0` |
| Worktrees | `1` |
| Latest runtime-affecting repo-side package on `main` | `efde917` = PR `#79` merge of the package publish-surface guard follow-up on top of the earlier browser/distribution work |
| Latest merged head on `main` | `efde917` = PR `#79` merge of package publish-surface gating |
| Current builder/public distribution delivery tip | `efde917` = package-gate follow-up on top of the earlier PR `#76` and PR `#74` landings |
| GitHub review gate on `main` | required pull-request reviews = `true`; required checks = `test`, `frontend`, `governance`, `product-smoke`, `CodeQL`, `secret-hygiene` |

Recent landing points that matter for the current closeout story:

- `7c37a91` = dedicated Chrome root closeout on `main`
- `8a599a3` = browser identity layer first landing slice
- `41986b0` = authenticated surface / diagnose refinement
- `d54fa33` = host/process safety contract enforcement
- `ffdcc0f` = direct clean-refusal test coverage
- `e28d811` = PR `#60` merge to `main`
- `de64900` = repo/live closeout ledger sync
- `4420fe3` = signed tip governance tail
- `e8561a6` = live-probe-scope clarification
- `d02e269` = retriggered governance/checks tail landed on `main`
- `df29a1d` = final landed-truth ledger rewrite
- `e15d84d` = signed retrigger for the final closeout docs tail
- `8a7b5c2` = pending-final-gate wording snapshot captured in the closeout branch history
- `bec5447` = final gate evidence clarification
- `56e725e` = PR `#63` merge that lands the final docs-only closeout sync on `main`
- `330d343` = PR `#64` merge that syncs final repo and live truth
- `0745d1d` = PR `#65` merge that refreshes the live browser truth after the dedicated lane came back
- `7228137` = PR `#66` merge that hardens diagnostics and truth guards
- `1b35b57` = PR `#67` merge that preserves per-site probe error details
- `b284feb` = PR `#68` merge that syncs the closeout ledgers to the later landed truth
- `73b5c44` = PR `#69` merge that tightens account-lane determinism
- `08479e0` = PR `#70` merge that restores Weee account truth and deduplicates browser open-page summaries
- `2977d96` = PR `#74` merge that lands native distribution candidates on `main`
- `c38470c` = PR `#76` merge that lands final browser truth sync and official MCP Registry reality wording on `main`
- `efde917` = PR `#79` merge that lands the package publish-surface guard on `main`

## Truth Layers

| Layer | What it means now |
| --- | --- |
| Repo truth | What the repository implements, documents, and verifies locally today |
| Git/GitHub truth | What is landed on `main` / `origin/main`, including PR/branch/worktree closure |
| Live/public truth | What fresh external probes can currently reach |
| Browser truth | What the repo-owned debug lane and current session probes prove |
| External blocker | Anything that still needs deploy access, live platform control, or human reauth |

## Repo-Side Landed Scope

### Old multi-wave mainline

- Wave 3 closeout tail remains landed
- Wave 4 product-maturity baseline remains landed
- Wave 5 convergence remains landed
- Wave 6 builder/public amplification remains landed inside the current honest scope

Fresh re-check outcome:

- the remaining ship-now builder/public tail was bounded and sync-shaped, not a new platform scope jump
- builder/public guards still pass in the current merged state
- explicit defers remain explicit defers; they were not reopened by fresh evidence
- the bounded builder-facing sync now keeps three truths aligned:
  - root CLI help separates runtime, builder discovery, operator-only maintainer, and legacy bridge paths
  - repo-owned skill cards use the same copyable `PYTHONPATH=src uv run ...` launch commands as the rest of the builder pack
  - OpenHands / OpenCode / OpenClaw now mark `official_wrapper_documented` wherever the repo-owned recipes already treat their wrapper syntax as officially documented

### Post-063496e builder/public/distribution slice on merged `main`

The later merged follow-up adds a new repo-owned distribution layer without pretending official listing closure:

- shared native bundle candidate under `plugins/dealwatch-builder-pack/`
- Claude Code repo marketplace file at `.claude-plugin/marketplace.json`
- Codex repo marketplace file at `.agents/plugins/marketplace.json`
- per-client official-surface / candidate / listing-status metadata in `src/dealwatch/builder_contract.py` and the public JSON mirrors
- frontdoor wording tightened around:
  - human path vs machine path
  - native bundle candidates where the platform actually supports them
  - listing-prep assets vs official listing
  - OpenHands skill-registry wording, OpenCode ecosystem wording, and OpenClaw ClawHub wording

Fresh merged-main evidence for this slice:

- `.venv/bin/pytest -q tests/test_builder_public_boundary.py tests/test_mcp_server.py` → pass (`26 passed`)
- `python3 scripts/verify_builder_public_boundary.py` → pass
- `python3 scripts/verify_builder_contract_sync.py` → pass
- `python3 scripts/verify_site_surface.py` → pass
- `python3 scripts/verify_public_surface.py` → pass
- `python3 scripts/verify_docs_contract.py` → pass
- `python3 scripts/verify_host_process_safety.py` → pass
- `pnpm -C frontend build` → pass (Node engine warning only)
- `./scripts/test.sh -q` → pass (`573 passed, 1 skipped`)
- `git diff --check` → pass

### Newly landed through PR `#60`

- browser identity page under `.runtime-cache/browser-identity/index.html`
- canonical account-page opener for Target / Safeway / Walmart / Weee
- login-state reporter with `homepage_logged_in`, `account_page_logged_in`, and `reauth_required`
- `diagnose-live` account-surface refinement
- host/process safety contract guard via:
  - `scripts/verify_host_process_safety.py`
  - CI governance
  - pre-commit
  - `scripts/clean.py` hard refusal
  - browser-instance ceiling in the launcher

### New closeout-tail state after PR `#60`

- repo-side closeout ledger sync through `d02e269` is landed on `main`
- the stricter final truth rewrite is now also landed on `main` through PR `#63`, and later refreshed through PR `#64`, PR `#65`, PR `#66`, PR `#67`, PR `#68`, PR `#69`, PR `#70`, and later docs-only wording resyncs, including:
  - `df29a1d`
  - `e15d84d`
  - `8a7b5c2`
  - `bec5447`
  - `56e725e`
  - `330d343`
  - `0745d1d`
  - `7228137`
  - `1b35b57`
  - `b284feb`
  - `73b5c44`
  - `08479e0`
- no additional docs-only closeout tail remains outstanding at the repo-ref level
- this ledger now separates the latest runtime-affecting package from the latest docs-only sync so a docs refresh does not instantly make the runtime verdict stale again

## Fresh Evidence

| Command / probe | Result | Meaning |
| --- | --- | --- |
| `git status --short --branch && git branch -vv && git worktree list` | pass | `main` is clean, aligned with `origin/main`, and the repo still uses one worktree |
| `git log --oneline --decorate -n 12` | pass | shows PR `#79` / `efde917` above the earlier PR `#76`, PR `#74`, and PR `#70` landing points, with `main` as the only remaining remote branch |
| `git worktree list` | pass | one worktree only |
| `gh pr list --state open` + `gh issue list --state open` | pass | open PR count = `0`, open issue count = `0` |
| `GITHUB_TOKEN="$(gh auth token)" python3 scripts/verify_remote_github_state.py` | pass | remote About/branch/workflow/label/release/discussion surfaces align with the repo contract; keep the token shell-substituted and never paste raw token values into docs, PR bodies, or comments |
| `gh api 'repos/xiaojiou176-open/dealwatch/dependabot/alerts?state=open&per_page=100' --jq 'length'` | pass | `0` open Dependabot alerts |
| `gh api 'repos/xiaojiou176-open/dealwatch/code-scanning/alerts?state=open&per_page=100' --jq 'length'` | pass | `0` open code-scanning alerts |
| `gh api 'repos/xiaojiou176-open/dealwatch/secret-scanning/alerts?state=open&per_page=100' --jq 'length'` | pass | `0` open secret-scanning alerts remain after historical PR-body alerts `#3` and `#4` were resolved as `revoked`; the current working tree still has no source-file leak |
| `./scripts/test.sh -q tests/test_browser_debug.py tests/test_launch_dealwatch_chrome.py tests/test_browser_instance_identity.py tests/test_browser_login_state.py tests/test_open_dealwatch_account_pages.py tests/test_clean_script.py tests/test_host_process_safety_contract.py` | pass | targeted browser/governance package is green (`49 passed`) |
| `python3 scripts/verify_host_process_safety.py` | pass | dangerous host/process primitives remain blocked |
| `python3 scripts/verify_public_surface.py` | pass | public wording/governance guard stays aligned |
| `python3 scripts/verify_docs_contract.py` | pass | docs contract still matches repo guard expectations |
| `python3 scripts/verify_site_surface.py` | pass | site structure guard stays aligned |
| `python3 scripts/verify_builder_contract_sync.py` | pass | builder contract snapshots stay aligned |
| `pnpm -C frontend build` | pass with non-blocking engine warning | frontend still builds under the merged state |
| `git diff --check` | pass | no whitespace/conflict-marker drift |
| `python3 scripts/cleanup_local_rebuildables.py --dry-run` | pass | only disposable local outputs are reclaimable |
| `python3 scripts/audit_runtime_footprint.py` | pass | persistent browser profile and operator evidence remain correctly classified |
| `PYTHONPATH=src .venv/bin/python -m dealwatch maintenance --dry-run` | pass | repo-owned maintenance contract still holds |
| `gh pr checks 60` | pass | all required checks green before merge |
| `gh pr view 60 --json state,mergedAt,mergeCommit,...` | pass | PR `#60` merged at `2026-04-05T14:13:43Z` as `e28d811` |
| public GitHub check-suite probe on `d02e269` | pass | fresh required check suites attached and completed for the first closeout-tail landing |
| `git push git@github.com:xiaojiou176-open/dealwatch.git HEAD:refs/heads/codex/closeout-truth-sync-apr5` | pass | the final docs-only closeout branch was published for review rather than forced directly onto protected `main` |
| `git push git@github.com:xiaojiou176-open/dealwatch.git main:main` after `d02e269` | pass | the first closeout tail landed on protected `main` once fresh required checks existed |
| PR `#63` merge to `main` | pass | the final docs-only closeout sync is now landed on `main` as `56e725e` |
| PR `#64` merge to `main` | pass | repo/live closeout truth was refreshed on `main` as `330d343` |
| PR `#65` merge to `main` | pass | live/browser closeout truth was refreshed again on `main` as `0745d1d` |
| PR `#66` merge to `main` | pass | diagnostics and truth guards were hardened on `main` as `7228137` |
| PR `#67` merge to `main` | pass | per-site probe error handling was hardened on `main` as `1b35b57` |
| PR `#68` merge to `main` | pass | closeout ledgers were synced to the later landed truth on `main` as `b284feb` |
| PR `#69` merge to `main` | pass | account-lane determinism was tightened on `main` as `73b5c44` |
| PR `#70` merge to `main` | pass | Weee truth and browser open-page deduplication were refreshed on `main` as `08479e0` |
| `git push git@github.com:xiaojiou176-open/dealwatch.git --delete codex/closeout-truth-sync-r2` | pass | stale experimental remote branch removed |
| `git ls-remote --heads origin` | pass | remote heads now show only `main` |

## Resource Hygiene Status

### Cleaned / closed

- PR `#60` is merged
- the local repo still uses one retained worktree
- stale experimental remote branch `codex/closeout-truth-sync-r2` is deleted

### Kept on purpose

- `.venv`
- `.pnpm-store`
- `frontend/node_modules`
- `.runtime-cache/logs`
- `.runtime-cache/runs`
- `.runtime-cache/operator`
- `.runtime-cache/browser-identity`
- `~/.cache/dealwatch/browser/chrome-user-data`

These remain because they are canonical dependencies, runtime/operator evidence, or the dedicated persistent browser workspace.

### Rebuildable / disposable

- `.pytest_cache`
- `frontend/dist`

These are safe to reclaim through repo-owned cleanup entrypoints when needed.

## Exact Remaining Blockers

1. Render live truth is still externally blocked:
   - `https://dealwatch-api.onrender.com/api/health` returns `404`
   - `https://dealwatch-webui.onrender.com/` returns `404`
2. Official listing / registry / marketplace publication still depends on external owner / publish control planes even though the repo-owned candidate assets are already landed.
3. GitHub UI-only social preview selection remains outside repo-file control.

## Explicit Defers

These are not unfinished repo-local tasks. They remain deliberate non-ship decisions.

- public recommendation UI / API / MCP launch
- write-side MCP
- hosted SaaS story
- formal SDK story
- official listing claims on Claude Code / Codex / OpenHands / OpenCode / OpenClaw before the platform-native submission flow actually lands
- deeper private API promotion without a stable contract

## Final Repo-Side Call

> DealWatch is no longer only in a “browser package + docs sync” phase.
>
> The builder/public/distribution package is landed on `main` through PR `#74`, the later final-push closeout follow-up is landed through PR `#76` / `c38470c`, and the package publish-surface guard is now landed through PR `#79` / `efde917`.
> The latest merged closeout follow-up on `main` is now PR `#79` / `efde917`, which adds a persistent CI/package guard on top of the earlier browser truth and distribution work.
> The remaining blockers are no longer product-implementation blockers:
> they are live deployment truth (`Render 404`), external listing / registry publication steps, and GitHub UI-only social preview selection.
