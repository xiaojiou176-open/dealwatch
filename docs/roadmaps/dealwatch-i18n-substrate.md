# DealWatch i18n Substrate

## Purpose

This document records the first landed Prompt 2 substrate slice.

In plain English:

- the repo now has a real locale foundation instead of only a bilingual aspiration
- the WebUI can persist and switch locale state
- shared message catalogs now exist in one source location that later site work can reuse

This document does **not** mean bilingual migration is finished. It only means the translation system now exists.

## Current Closure Update

The current repo-local wave is no longer "build the substrate."

It is "close the core surface on top of the substrate":

- keep `site/data/i18n/en.json` and `site/data/i18n/zh-CN.json` as the only product-facing bilingual SSOT
- keep the WebUI core spine and the public-site core pages on the same catalog path
- remove the last still-visible `zh-CN` placeholder-style English terms where they make the surface feel half-finished
- keep verification honest when browser tooling fails, instead of mislabeling a tool issue as a product regression

In plain English:

> the plumbing is already built.
> the current job is to make the visible faucets all feel like they belong to the same house.

## Landed Pieces

### Shared message source

- Shared catalogs now live in:
  - `site/data/i18n/en.json`
  - `site/data/i18n/zh-CN.json`
- The current design keeps one message-source location that the future public site can consume directly while the WebUI imports the same source through Vite.

### WebUI locale substrate

- `frontend/src/lib/i18n.tsx` now provides:
  - locale type and storage key
  - locale detection
  - locale persistence
  - translation lookup
  - locale-aware currency/date helpers
- `frontend/src/main.tsx` now wraps the app with `I18nProvider`.
- `frontend/src/components/AppShell.tsx` now exposes a visible language switch.
- `frontend/src/ui/App.tsx` now routes the suspense loading copy through the i18n layer.

### Locale-aware formatting started

The first substrate slice also moved some visible formatting onto locale-aware helpers:

- `frontend/src/components/PriceHistoryChart.tsx`
- `frontend/src/pages/TaskListPage.tsx`
- `frontend/src/pages/NotificationSettingsPage.tsx`
- `frontend/src/pages/WatchGroupDetailPage.tsx`
- `frontend/src/pages/ComparePage.tsx`
- `frontend/src/pages/TaskDetailPage.tsx`

This is intentionally partial. The goal was to prove the substrate and remove the hardest English-only formatting assumptions first.

### First-wave page migration now started

After the initial substrate landed, the first WebUI migration slice also began moving top-level route copy onto shared translation keys:

- `frontend/src/pages/ComparePage.tsx`
- `frontend/src/pages/TaskListPage.tsx`
- `frontend/src/pages/NotificationSettingsPage.tsx`
- `frontend/src/pages/WatchGroupDetailPage.tsx`
- `frontend/src/pages/TaskDetailPage.tsx`

Current scope is no longer only route-top shallow:

- route-level eyebrow/title/summary copy
- primary CTA labels
- selected empty/loading/error messages
- early locale-aware currency/date formatting in shared-visible areas
- deeper page-level fallback copy for task/group/notification/detail surfaces
- more shared-catalog-backed keys for task list, notification cockpit, task detail, compare decision logic, and watch-group reliability notes
- compare-page AI status labels/headlines/summaries, compare-form validation copy, and compare evidence/group-title labels now also route through shared-catalog-backed keys instead of staying hardcoded English
- the latest closure slice also removed the remaining core-WebUI habit of borrowing public-site wording for task/group/settings/detail surfaces; AI panel labels/notes, ZIP/run labels, runtime/cockpit helper copy, task signal labels, and watch-group candidate labels now all resolve through page-owned shared keys instead of `site.*` strings
- the same closure slice also moved saved-package helper copy, group-creation lock guidance, and pair-evidence comparison glue copy onto shared compare keys instead of leaving those as the last obvious route-local bridge strings
- `TaskDetailPage` now routes hero badges, source-label copy, latest-signal labels, fallback decision guidance, and compare-context labels through shared-catalog-backed keys, so the task detail spine is no longer only a headline-level bilingual shell
- `WatchGroupDetailPage` now routes the operational-summary line, ZIP/backoff hero badges, candidate metadata badges, AI panel framing, and recent-runs explanation through shared keys, so the winner/runner-up basket reads as one deeper bilingual surface instead of borrowing site wording as a bridge
- `TaskListPage` and `NotificationSettingsPage` now carry deeper recovery/cockpit wording through their own shared keys instead of leaning on unrelated site-home copy for AI/readiness/operator summaries
- the `ComparePage` render path no longer uses direct `draft(locale, COMPARE_COPY...)` fallback calls in user-visible sections; the page now resolves through shared-key helpers first, leaving fallback logic down in the helper layer instead of the visible component tree

That means the migration is already more than "header bilingual":

- the major WebUI routes now share one locale system
- several pages now use page-local bilingual fallback maps only as a bridge while the shared catalogs catch up
- the shared catalogs have now absorbed a much larger slice of `compare.*`, `groupDetail.*`, `taskDetail.*`, `taskList.*`, and `settings.cockpit.*` keys, so the bridge layer is thinner than it was in the first convergence wave
- the latest Core Surface Closure pass also re-verified `0` shared-key mismatches across `AppShell`, `ComparePage`, `TaskListPage`, `NotificationSettingsPage`, `WatchGroupDetailPage`, and `TaskDetailPage`
- the remaining biggest debt is no longer substrate absence, generic page-header migration, or missing shared keys on the core WebUI spine; it is now the smaller long-tail of `ComparePage` wording polish plus later bridge cleanup once wording stabilizes

### Prompt 4A bilingual entry now started

The static public site is no longer only "prepared for later".

The repo now has a lightweight shared-site i18n entry under:

- `site/i18n.js`

Current Prompt 4A scope:

- `site/index.html`
- `site/compare-preview.html`
- `site/compare-vs-tracker.html`
- `site/proof.html`
- `site/faq.html`

Those core pages now:

- read the same shared catalogs under `site/data/i18n/`
- persist the same `dealwatch.locale` preference key as the WebUI
- wire the top navigation + hero + first value section into the shared catalogs
- wire compare-preview sample-entry buttons, idle/loading/error status text, and the most visible sample guidance blocks into the same catalogs
- start translating the compare-preview sample entry and dynamic sample result copy through the same shared catalogs
- extend shared-catalog coverage across the deeper proof / FAQ / use-cases sections
- can now also bind JSON-LD / structured-data payloads through the same shared site substrate instead of leaving schema blocks in a static English side channel
- keep the site on the same single-catalog path instead of introducing a site-only fork

The first Prompt 4 expansion now also means:

- `site/proof.html` has entered the same bilingual entry path for top nav + hero + first-note surfaces
- `site/faq.html` has entered the same bilingual entry path for top nav + hero surfaces
- `site/use-cases.html` is now on the same shared-catalog path
- `site/compare-vs-tracker.html` is now on the same shared-catalog path for hero, comparison-table, builder-facing explanation, and proof CTA sections
- `site/index.html`, `site/faq.html`, and `site/compare-vs-tracker.html` can now bind JSON-LD via `data-i18n-json`, so SEO-facing structured data no longer has to drift in a separate static-English lane
- `site/proof.html` now also binds its `TechArticle` JSON-LD through `data-i18n-json`, so the proof surface joins the same machine-readable i18n path instead of staying a text-only bilingual page
- `site/compare-preview.html` now also binds its `WebPage` JSON-LD through `data-i18n-json`, so the first compare-first product step joins the same machine-readable i18n path
- the public pages now keep two truth layers aligned at once: the initial English HTML contains a full schema/metadata baseline for non-JS crawlers, and runtime locale switching can still replace those payloads with `zh-CN`
- the checked core public pages currently have `0` shared-key mismatches against `site/data/i18n/*.json`
- the latest Core Surface Closure pass re-verified `0` shared-key mismatches across `site/index.html`, `site/compare-preview.html`, `site/proof.html`, `site/faq.html`, `site/use-cases.html`, and `site/compare-vs-tracker.html`
- a fresh browser spot-check on `site/index.html` also confirmed zh/en switching across the homepage hero, value cards, proof blocks, and community/release sections
- a browser spot-check confirmed real locale switching on `site/compare-preview.html`
- a browser spot-check confirmed real locale switching, comparison-table switching, and screenshot loading on `site/compare-vs-tracker.html`
- repo-owned alignment tests now also verify that the structured-data bindings stay attached to the shared catalogs, and Playwright E2E now checks that the comparison-page, compare-preview-page, and proof-page schema layers switch with locale
- the public comparison page can now carry honest Claude Code / Codex / OpenHands / MCP / API wording through shared keys instead of hardcoded page-local copy
- the current closure wave did not need a second site-html migration fork: the checked core public pages were already fully shared-catalog-backed, so the honest next move was verification + guard tightening instead of churn for churn's sake

This is intentionally the smallest safe public-site slice. It is not a second translation system and it is not a full-site migration.

## Why the catalogs live under `site/data/i18n/`

This path was chosen on purpose:

- later Prompt 4 public-site work can reuse the same catalogs without inventing a second translation store
- current Prompt 2 WebUI work can still import them through Vite aliasing
- the repo now has a single visible place to review product-facing message truth

## Current Boundary

### What Prompt 2 has completed

- shared catalogs exist
- locale state exists
- locale persistence exists
- a visible language switch exists
- the WebUI has a working translation/provider substrate

### What Prompt 2 has **not** completed yet

- full page-by-page WebUI translation migration
- public site translation migration
- exhaustive locale-aware formatting across every frontend screen
- content review for every bilingual product string
- full promotion of all page-local bilingual fallback maps into the shared catalogs

## Recommended next migration order

Continue in this order:

1. finish core WebUI page migration on top of the new substrate
2. migrate remaining locale-sensitive formatting hotspots
3. move to public site bilingual migration only after the WebUI path is stable

## Fresh Verification Snapshot

Latest verification after the current convergence slice:

- `pnpm -C frontend build` passed
- `./scripts/test.sh -q` passed
- `./scripts/test.sh -q` passed in the latest Core Surface Closure run with `403 passed, 1 skipped`
- `git diff --check` passed
- `python3 scripts/verify_english_boundary.py` passed
- `python3 scripts/verify_public_surface.py` passed
- `python3 scripts/verify_site_surface.py` passed
- `python3 scripts/verify_root_allowlist.py` passed
- `node --check site/i18n.js && node --check site/demo-compare.js` passed
- strict JSON parsing for `site/data/i18n/en.json` and `site/data/i18n/zh-CN.json` passed
- shared-catalog targeted validation for the newest 41 promoted keys passed in both `en` and `zh-CN`
- a direct structure-diff audit between `en.json` and `zh-CN.json` returned `0` missing keys in either direction after the current closure fixes
- core WebUI shared-key validation across `AppShell`, `ComparePage`, `TaskListPage`, `NotificationSettingsPage`, `WatchGroupDetailPage`, and `TaskDetailPage` passed with zero missing keys
- site shared-key validation across `site/index.html`, `site/compare-preview.html`, `site/proof.html`, `site/faq.html`, and `site/use-cases.html` passed with zero missing keys
- `site/compare-vs-tracker.html` shared-key validation passed with zero missing keys
- `node --check site/i18n.js` passed
- `node --check site/demo-compare.js` passed
- site catalog JSON validation passed
- repo-local HTTP serving for the public site responded successfully, and the served `zh-CN` catalog payload exposed the current closure-wave terminology fixes
- browser spot-check evidence from earlier convergence slices still exists in the repo history, but the current environment's browser MCP paths are failing at response decoding, so this wave must explicitly treat browser-tool failure as distinct from product failure

One real compile blocker surfaced during this phase:

- `interpolate()` originally used `String.prototype.replaceAll`, which is not safe for the repo's `ES2020` target
- the helper was corrected to a compatible `split().join()` implementation before the final passing build
- after the latest catalog-shape promotions, `frontend/tsconfig.app.tsbuildinfo` had to be cleared once so `tsc -b` would stop holding onto stale JSON-module shape assumptions; after that rebuild, the frontend build returned to green

## Guardrails

- do not add new scattered bilingual literals
- do not fork a separate site-only translation system
- do not market bilingual support as finished until the major product surfaces are actually migrated
- prefer promoting high-value page-local fallback keys into the shared catalogs once their wording stabilizes
