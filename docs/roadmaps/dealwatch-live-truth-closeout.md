# DealWatch Live Truth Closeout

## Purpose

This document records what the outside world and the current browser/session probes prove after the April 5 dual-mainline re-check, the later browser/account truth sync landed in PR `#76`, and the current April 6 rerun.

In plain English:

- the repo-side browser identity layer is landed on `main`
- the browser truth follow-up is now landed on `main` through PR `#76`, so the Safeway existing-tab account truth is no longer only a branch-local or pending-PR claim
- this file answers what is actually reachable or attachable right now
- repo truth, Git/GitHub truth, live/public truth, and browser/session truth stay separate

This ledger does not open new product scope.

## Current Verdict

> **Verdict:** `GitHub Pages remains reachable, Render remains blocked at 404, and browser truth now confirms Safeway account-page login in the existing dedicated lane instead of downgrading it behind a fresh temporary probe.`

Why this is the honest call:

- the repo-side browser lane is landed and reusable
- Git/GitHub delivery is now closed at the repo-ref level: `main` is aligned, one worktree remains, and no extra remote delivery branch is left
- GitHub Pages root / proof / FAQ still respond with `200`
- Render URLs still respond with `404`
- all four canonical account tabs now have confirmed account-page session truth in the current dedicated lane
- Safeway still has a narrower caveat: a forced fresh temporary probe can redirect to `sign-in`, so temporary-probe recovery is weaker than the stronger existing-tab truth

## Truth Layers

| Layer | Meaning in the current closeout pass |
| --- | --- |
| Repo truth | What the merged repository implements and verifies locally |
| Git/GitHub truth | What is landed on `main` / `origin/main` and whether branch / worktree closure is complete at the repo-ref level |
| Live truth | What a fresh external probe can reach right now |
| Browser truth | What the current repo-owned browser lane and session probes prove |
| External blocker | What still needs deploy access, live platform control, or human reauth |

## Live Truth Matrix

| Surface | Repo truth | Fresh live/browser truth | Status | Classification |
| --- | --- | --- | --- | --- |
| GitHub Pages root | Static proof/home surface exists in `site/` | `https://xiaojiou176-open.github.io/dealwatch/` returned `200` in this turn | Pass | Reachable public root |
| GitHub Pages proof page | Proof surface exists in `site/proof.html` | `https://xiaojiou176-open.github.io/dealwatch/proof.html` returned `200` in this turn | Pass | Reachable public proof page |
| GitHub Pages FAQ | FAQ surface exists in `site/faq.html` | `https://xiaojiou176-open.github.io/dealwatch/faq.html` returned `200` in this turn | Pass | Reachable public FAQ page |
| Render API | `render.yaml` still declares `dealwatch-api` and `/api/health` | `https://dealwatch-api.onrender.com/api/health` returned `404 Not Found` in this turn | Blocked | Live deployment still not proving the repo blueprint |
| Render WebUI | `render.yaml` still declares `dealwatch-webui` | `https://dealwatch-webui.onrender.com/` returned `404 Not Found` in this turn | Blocked | Live deployment still not proving the repo blueprint |
| MCP public claim boundary | repo code exposes `14` read-only tools | no fresh public page contradicted the local-first/read-only story in this turn | Supported with boundary | Repo truth supports the claim; live proof remains non-hosted |
| Recommendation defer | repo docs still keep `NOT READY` explicit | no fresh reachable public surface showed a shipped buy/wait recommendation path | Supported | Honest defer still holds |
| Browser lane availability | dedicated browser root and CDP contract are landed | `diagnose-live` attached to the existing dedicated lane on port `9333` and returned `existing_browser_session` with confirmed profile truth | Pass | Repo-owned browser lane currently works |
| Target browser truth | canonical Target account page probe exists | reporter now shows `account_page_logged_in` on `https://www.target.com/account` | Pass | Authenticated account-page truth confirmed |
| Walmart browser truth | canonical Walmart account page probe exists | reporter now shows `account_page_logged_in`; `diagnose-live` current page is `https://www.walmart.com/account` | Pass | Authenticated account-page truth confirmed |
| Weee browser truth | canonical Weee account page probe exists | reporter now shows `account_page_logged_in` on `https://www.sayweee.com/zh/account/my_orders` | Pass | Authenticated account-page truth confirmed |
| Safeway browser truth | canonical Safeway account page probe exists | reporter now shows `account_page_logged_in` from the existing dashboard tab at `https://www.safeway.com/customer-account/account-dashboard`; a forced fresh temporary probe can still redirect to `sign-in` | Pass with caveat | Current dedicated-lane truth is authenticated; fresh temporary-probe recovery remains weaker |

## Deployment / Render Reality

### What the repo says

- `render.yaml` still defines:
  - `dealwatch-api`
  - `dealwatch-worker`
  - `dealwatch-webui`
- API health check path remains `/api/health`
- static site publish path remains `frontend/dist`

### What the fresh live probe says on April 6

| URL | Result | Meaning |
| --- | --- | --- |
| `https://dealwatch-api.onrender.com/api/health` | `404 Not Found` | Live API truth is still not confirmed |
| `https://dealwatch-webui.onrender.com/` | `404 Not Found` | Live WebUI truth is still not confirmed |

### Deployment closeout conclusion

The repository still contains a Render blueprint, but the currently reachable Render URLs do not prove that the blueprint is live and healthy today.

That means:

- repo truth: confirmed
- live Render truth: not confirmed
- blocker type: external blocker, not missing repo implementation

## Browser / Session Reality

### What is freshly proven now

- the dedicated DealWatch lane can be launched or reused with repo-owned tooling
- `PYTHONPATH=src .venv/bin/python -m dealwatch diagnose-live` currently returns:
  - `status = existing_browser_session`
  - `confirmation_status = confirmed`
  - `current_page = https://www.walmart.com/account`
- `scripts/report_dealwatch_login_state.py --json` currently returns:
  - Target = `account_page_logged_in`
  - Safeway = `account_page_logged_in`
  - Walmart = `account_page_logged_in`
  - Weee = `account_page_logged_in`
  - Safeway source = `existing_tab`
  - a forced fresh temporary probe can still redirect Safeway to `https://www.safeway.com/account/sign-in.html`

### What is not yet proven

- the dedicated lane does not prove that every future fresh Safeway temporary probe will stay authenticated
- the remaining gap is temporary-probe stability, not whether the current dedicated Safeway account tab is logged in
- any broader claim about durable fresh-tab recovery still needs a stronger external check or an explicitly approved lane intervention

### Capability boundary

Fresh site/account-page probes also exposed hydration, DOM, and network clues for Target, Walmart, Safeway, and Weee.

Those clues are:

- operator evidence
- future capability candidates

They are not yet:

- formal public/store contracts
- broader product-mainline pricing/support claims

## Fresh Checks In This Turn

### Repo/browser checks

| Command | Result | Notes |
| --- | --- | --- |
| `PYTHONPATH=src .venv/bin/python -m dealwatch diagnose-live` | Pass | `existing_browser_session`, profile truth `confirmed`, current page = Walmart account |
| `PYTHONPATH=src .venv/bin/python scripts/report_dealwatch_login_state.py --env-file .env --json` | Pass | Target/Safeway/Walmart/Weee all report `account_page_logged_in` from the existing dedicated lane tabs |
| `PYTHONPATH=src .venv/bin/python scripts/report_dealwatch_login_state.py --env-file .env --json --prefer-existing-tabs` | Pass | same strongest existing-tab truth; the flag is now only a backward-compatible alias |
| `PYTHONPATH=src .venv/bin/python -m dealwatch support-bundle` | Pass | wrote a fresh browser support bundle and preserved the current `open_pages` set plus the confirmed lane contract |
| `python3 scripts/verify_host_process_safety.py` | Pass | host/process guard still holds |
| `./scripts/test.sh -q tests/test_browser_debug.py tests/test_launch_dealwatch_chrome.py tests/test_browser_instance_identity.py tests/test_browser_login_state.py tests/test_open_dealwatch_account_pages.py tests/test_clean_script.py tests/test_host_process_safety_contract.py` | Pass | targeted browser/governance package is green (`49 passed`) |

### Live/public probes

| Probe | Result | Key output |
| --- | --- | --- |
| root Pages probe | Pass | `https://xiaojiou176-open.github.io/dealwatch/` → `200` |
| proof Pages probe | Pass | `https://xiaojiou176-open.github.io/dealwatch/proof.html` → `200` |
| FAQ Pages probe | Pass | `https://xiaojiou176-open.github.io/dealwatch/faq.html` → `200` |
| Render API probe | Blocked | `https://dealwatch-api.onrender.com/api/health` → `404` |
| Render WebUI probe | Blocked | `https://dealwatch-webui.onrender.com/` → `404` |
| `git status --short --branch && git branch -vv && git worktree list` | Pass | `main` is aligned with `origin/main`, the working tree is clean, and one worktree remains |
| `git log --oneline --decorate -n 12` + `git ls-remote --heads origin` | Pass | PR `#76` / `c38470c` is now the latest merged head on `main`, and remote heads now show only `main` |

These fresh public probes confirm reachability in this turn.
They do not claim that every body/title fragment on GitHub Pages was exhaustively diff-audited again today.

## Exact Remaining Blockers

### External blockers

1. The configured Render URLs still return `404`, so live deployment truth remains unconfirmed.
2. GitHub UI-only social preview selection remains outside repo-file control.

### Git / GitHub closeout note

Git/GitHub closeout is clean in the current repo-owned evidence:

- `main` is aligned to `origin/main`
- the browser package from PR `#60` is merged
- the final docs-only closeout sync is merged through PR `#63`
- the later closeout-truth refreshes are merged through PR `#64`, PR `#65`, and PR `#68`
- the browser diagnostics and login-state reporter hardening are merged through PR `#66`, PR `#67`, PR `#69`, and PR `#70`
- the builder/public distribution landing is merged through PR `#74`
- the later browser truth plus official MCP Registry reality sync is merged through PR `#76` / `c38470c`
- one worktree remains
- `git ls-remote --heads origin` currently shows only `main`
- `gh pr list --state open` and `gh issue list --state open` both return `0`
- open Dependabot alerts = `0`
- open code-scanning alerts = `0`
- open secret-scanning alerts = `0`; historical PR-body alerts `#3` and `#4` are now resolved as `revoked`

This ledger now separates the latest runtime-affecting browser package from the latest docs-only closeout sync so a wording refresh does not instantly stale the browser/runtime verdict.

That means the remaining blockers in this ledger are:

- live/deployment/session blockers
- GitHub UI-only social preview selection

## Final Verdict

> **`GitHub Pages still reachable, Render still blocked at 404, and browser truth now confirms all four canonical account tabs in the current dedicated lane, including Safeway`**

This is not `CLOSED_CLEAN` at the overall live/public layer, because live deployment truth still diverges from the repo blueprint and GitHub UI-only social preview selection still sits outside repo-file control.

It is also not a vague “browser still broken”.

It is specifically:

- repo-side truth: strong and landed
- Git/GitHub closeout at the merged-main level is no longer the main blocker in this ledger
- browser truth: confirmed for Target, Safeway, Walmart, and Weee in the current dedicated lane
- exact blockers narrowed to:
  - Render live endpoints returning `404`
  - GitHub UI-only social preview selection
