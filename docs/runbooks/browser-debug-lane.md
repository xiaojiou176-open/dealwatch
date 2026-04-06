# DealWatch Browser Debug Lane

## Purpose

This runbook records the maintainer-only browser debug lane for DealWatch.

In plain English:

- the product mainline still uses `storage_state_<zip>.json`
- the browser debug lane is the repair bay for real browser/session truth
- repo-owned bootstrap proof is **not** the same thing as a real authenticated profile proof

Use this file when the question is:

> "What does `probe-live` / `diagnose-live` / `support-bundle` actually prove, and what still needs an external browser/session condition?"

## Scope

This lane is:

- maintainer-only
- repo-local
- evidence-first
- complementary to the lightweight `storage_state` mainline

This lane is **not**:

- the default product runtime
- a public/builder promise
- a hosted browser-control product
- a license to kill shared Chrome processes or drive the desktop with AppleScript

## Host safety boundary

The browser debug lane is a repair bay, not a force-quit hammer.

- Do not add `killall`, `pkill`, broad `kill -9`, `osascript`, `System Events`, `loginwindow`, or AppleEvent-based app control to DealWatch browser helpers.
- Do not "recover" the lane by guessing which Chrome process looks close enough; only reuse or inspect a browser instance once DealWatch ownership is proved.
- If ownership is ambiguous or the listener is missing, stop and record the external blocker instead of escalating to host-wide cleanup.
- If the machine already has more than six browser instances, do not open another DealWatch Chrome lane just to try one more time; finish non-browser work or wait for current owners to recover their lanes first.
- Run `python3 scripts/verify_host_process_safety.py` after browser-lane changes so CI can enforce the same boundary.

## Mainline vs debug lane

| Lane | What it is for | What it proves |
| --- | --- | --- |
| `storage_state` mainline | normal product scraping and repeatable runtime fetches | the lightweight product path can reuse stored browser state |
| browser debug lane | attach, diagnose, and preserve real browser/session evidence | which browser/session/page the maintainer actually attached to, and what still blocks real authenticated proof |

## Commands

```bash
PYTHONPATH=src uv run python -m dealwatch probe-live
PYTHONPATH=src uv run python -m dealwatch diagnose-live
PYTHONPATH=src uv run python -m dealwatch support-bundle
```

Think of them like three instruments in the same repair bay:

- `probe-live`: quick truth probe
- `diagnose-live`: full structured diagnosis
- `support-bundle`: preserve the current diagnosis plus the currently open browser-lane pages for later review

## Environment contract

The formal browser debug contract is:

- `CHROME_ATTACH_MODE`
- `CHROME_CDP_URL`
- `CHROME_REMOTE_DEBUG_PORT`
- `CHROME_USER_DATA_DIR`
- `CHROME_PROFILE_NAME`
- `CHROME_PROFILE_DIRECTORY`
- `CHROME_START_URL`
- `CHROME_OBSERVE_MS`
- `BROWSER_DEBUG_BUNDLE_DIR`

## Attach modes

| Mode | Meaning | Best use |
| --- | --- | --- |
| `browser` | attach to an existing browser-level CDP target | real Chrome listener already exists |
| `page` | attach and focus on current-page truth | current page/session inspection |
| `persistent` | launch a persistent context against a user-data directory | repo-owned bootstrap proof or requested profile attach |

## Status vocabulary

`diagnose-live` now classifies browser state more narrowly than a generic failure bucket:

- `attach_failed`
- `profile_mismatch`
- `login_required`
- `existing_browser_session`
- `not_open`
- `public_or_unknown`

In plain English:

- `attach_failed` means the lane could not attach at all
- `profile_mismatch` means you reached Chrome, but not the requested profile
- `login_required` means you reached a page, but auth/session proof is still missing
- `existing_browser_session` means a real page is already open and attached
- `not_open` means attach worked, but there is no meaningful current page yet
- `public_or_unknown` means a page is reachable, but this is still not the same as authenticated proof

## Fresh repo-owned proof

The current repo-local baseline already proves the lane itself is alive:

```bash
./scripts/test.sh -q tests/test_browser_debug.py tests/test_playwright_client.py
CHROME_ATTACH_MODE=persistent \
CHROME_USER_DATA_DIR=<temp-dir> \
CHROME_PROFILE_NAME=dealwatch \
CHROME_PROFILE_DIRECTORY=<chrome-profile-directory> \
CHROME_START_URL=https://example.com \
.venv/bin/python -m dealwatch diagnose-live
```

Current honest result:

- targeted browser tests pass
- `persistent + CHROME_START_URL` returns `status = public_or_unknown`
- `current_page.source = bootstrapped_page`

That means:

> the repair bay can start its own test page

It does **not** mean:

> the repo has already proved a real authenticated profile/session

## What still requires external conditions

The remaining blocker is now much narrower than "browser lane missing":

- a real reachable Chrome debug listener
- or a real requested profile contract
- or a real authenticated session for the target site

If those inputs are missing, the honest stop line is external to repo code.

## Profile contract

The real DealWatch Chrome profile contract is now stricter than before:

- `CHROME_USER_DATA_DIR`
- `CHROME_PROFILE_NAME`
- `CHROME_PROFILE_DIRECTORY`

All three must be present together for a requested real profile attach.

What `diagnose-live` now checks:

- the user-data directory exists
- the requested profile directory exists inside that user-data directory
- Chrome `Local State` maps that directory back to the requested display name

If any one of those checks fails, treat it as a profile-contract problem first, not as proof that the repo lacks a browser debug lane.

For the real `dealwatch` profile, the old shared Chrome root is now deprecated:

- `CHROME_USER_DATA_DIR` must point at the dedicated DealWatch browser root
- it must not point at `~/Library/Application Support/Google/Chrome`

The dedicated DealWatch browser root is:

```text
~/.cache/dealwatch/browser/chrome-user-data/
```

The preferred long-term attach mode is:

```text
CHROME_ATTACH_MODE=browser
CHROME_CDP_URL=http://127.0.0.1:9333
```

Use `persistent` only for bootstrap proof or migration-time checks. Do not keep second-launching the real DealWatch profile from the shared Chrome root.

## One-time migration

Use the repo-owned migration script to clone the real `dealwatch` profile into the dedicated browser root:

```bash
# First, fully quit any real Google Chrome process still using the default root
# under ~/Library/Application Support/Google/Chrome.
python3 scripts/migrate_dealwatch_chrome_profile.py --dry-run
python3 scripts/migrate_dealwatch_chrome_profile.py --apply
python3 scripts/check_runtime_env.py --target startup --env-file .env
```

Do not run the migration while the default Chrome root is still live. The migration script intentionally refuses that state because it risks copying a moving profile and carrying a whole-building Chrome lock into the new workspace.

The migration script copies only:

- `Local State`
- the discovered real `dealwatch` profile directory

It does not copy:

- the whole default Chrome root
- `SingletonLock`
- `SingletonCookie`
- `SingletonSocket`

The same script updates the local repo `.env` so the dedicated browser contract becomes active immediately after migration.

## Long-term single-instance workflow

After migration, the preferred workflow is:

1. launch one dedicated DealWatch Chrome instance
2. keep that instance running
3. let both human operators and automation attach to it over CDP

Use the repo-owned launcher:

```bash
./scripts/launch_dealwatch_chrome.sh
```

If you only need to repair the human-facing browser lane anchors without relaunching Chrome, use:

```bash
python3 scripts/open_dealwatch_account_pages.py --env-file .env
```

If you want a lightweight report of the current session surface after attach, use:

```bash
PYTHONPATH=src .venv/bin/python scripts/report_dealwatch_login_state.py --env-file .env --json
```

Treat this instance like a long-lived studio, not a disposable scratch browser:

- some retail sites still issue session-shaped auth cookies, so migration into a new dedicated root may require one fresh manual sign-in before the new workspace becomes the trusted browser
- reuse the same dedicated instance whenever possible instead of repeatedly quitting and relaunching it
- avoid hard-killing the dedicated Chrome process; abrupt termination can drop session-shaped auth state even when persistent cookies remain on disk
- `diagnose-live` / `probe-live` should inspect the existing browser session, not close or reset the attached real profile

## Window identity layer

The canonical DealWatch lane now includes a repo-owned identity tab under:

```text
.runtime-cache/browser-identity/index.html
```

This tab is the human-facing window identity layer for the dedicated browser lane:

- title format: `<repo-label> · <cdp-port> · browser lane`
- favicon: generated monogram badge
- accent: stable hash color by default, or `DEALWATCH_BROWSER_IDENTITY_ACCENT`
- label override: `DEALWATCH_BROWSER_IDENTITY_LABEL`

The launcher writes the identity tab before Chrome opens, then re-ensures it over CDP whenever the canonical instance is reused. It also opens canonical account/order pages instead of defaulting to login pages, so the browser lane reads more like "current session truth" and less like "maybe signed out, maybe not."

Do automate:

- identity page generation
- title / favicon / accent
- best-effort `file://` identity target creation
- canonical account page opening / re-ensure

Do not automate:

- pinned tab state
- Chrome private avatar/theme internals
- Dock label/icon hacks

If you want the identity tab to stay visually anchored, pin it manually once.

## Canonical account pages and login-state truth

Use the canonical account pages as the first truth probe before you trust a homepage impression:

- `Target`: `https://www.target.com/account`
- `Safeway`: `https://www.safeway.com/customer-account/account-dashboard`
- `Walmart`: `https://www.walmart.com/account`
- `Weee`: `https://www.sayweee.com/zh/account`

Why this matters:

- homepages can look "normal" before hydration finishes
- some stores show only weak greeting hints on the homepage
- account / order surfaces usually expose a clearer state split:
  - `account_page_logged_in`
  - `homepage_logged_in`
  - `reauth_required`

The repo-owned helpers now follow that rule:

- `./scripts/launch_dealwatch_chrome.sh`
  - opens or reuses the dedicated lane, writes the identity tab, and ensures the canonical account pages exist
- `python3 scripts/open_dealwatch_account_pages.py --env-file .env`
  - repairs the canonical tab set without relaunching Chrome
  - a stale Safeway sign-in tab does not count as the canonical account target; the helper now reopens the requested dashboard target instead of pretending the sign-in gate is already the final page
- `PYTHONPATH=src .venv/bin/python scripts/report_dealwatch_login_state.py --env-file .env --json`
  - reuses matching existing account tabs first, then falls back to a temporary canonical probe only when the matching tab is missing
  - reports the current store state using canonical account probes instead of homepage guesses
  - if one store probe fails, that store now degrades to `unknown` with an `error` field instead of collapsing the whole report into a fake lane-attach failure

## Current operator-only capability clues

These are fresh browser-debug observations, not public product claims:

- `Target` account pages expose `__NEXT_DATA__`, store/address DOM markers, and stable read surfaces such as `guest_profile_details` plus `redsky_aggregations`.
- `Walmart` account pages expose `__NEXT_DATA__` and multiple `orchestra/home/graphql/*` read queries tied to account and membership modules.
- `Safeway` sign-in / reauth paths expose `bin/safeway/unified/userinfo` plus `abs/pub/xapi/preload/webpreload/storeflags/*` style read surfaces.
- `Weee` account pages expose strong `data-testid` DOM anchors and a stable order-history route under `/account/my_orders`.

How to use these clues honestly:

- use them to strengthen operator debugging, session truth, and future store-capability investigation
- do not promote them into "officially supported private API integrations" until a repo-owned contract and tests exist
- keep account-page truth and live/browser truth separate from public capability claims

## Support bundle path

Support bundles write under:

```text
.runtime-cache/operator/browser-debug/
```

These bundles are repo-local operator evidence. They are not public proof artifacts.

## Guardrails

- Do not describe this lane as a public or builder-facing browser API.
- Do not treat `persistent + CHROME_START_URL` as authenticated proof.
- Do not collapse listener/profile/session issues back into one vague `attach_failed` story.
- Do not move DealWatch's business truth into the browser debug lane.

## Current closeout reading

The current honest closeout statement is:

> repo-owned browser debug lane = not a blocker  
> real authenticated browser/session proof = still external-condition-shaped
