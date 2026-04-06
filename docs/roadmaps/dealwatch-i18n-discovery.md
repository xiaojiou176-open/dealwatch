# DealWatch i18n Discovery

## Purpose

This document is the Prompt 2 discovery and guardrail note for bilingual product work.

In plain English:

- it confirms the current repo does **not** already have a reusable i18n substrate
- it identifies where hardcoded user-facing copy is most concentrated today
- it records the safest first move so later Workers do not spread scattered bilingual literals

This document is a discovery artifact, not the final implementation.

## Current Verdict

> **Current verdict:** no existing i18n substrate is present today.  
> The next safe step is to build one shared translation system before translating product pages.

## Evidence Summary

### What exists today

- Public pages use static English HTML with `lang="en"`.
- WebUI pages contain hardcoded English user-facing copy directly inside Preact components.
- Some existing `localStorage` usage already exists, but only for compare evidence package persistence, not for locale state.

### What does not exist today

- no locale state
- no translation provider
- no message catalog
- no locale persistence for UI language
- no shared translation helper used across `frontend/` and `site/`

## Hotspot Inventory

### Highest-risk WebUI hotspots

These files carry dense user-facing copy and are the most likely places for scattered bilingual literals to spread if Prompt 2 is skipped:

- `frontend/src/components/AppShell.tsx`
- `frontend/src/pages/ComparePage.tsx`
- `frontend/src/pages/TaskListPage.tsx`
- `frontend/src/pages/WatchGroupDetailPage.tsx`
- `frontend/src/pages/NotificationSettingsPage.tsx`

### Secondary hotspot: public site

These files are static public pages and would drift quickly if bilingual support were implemented by copying whole HTML files:

- `site/index.html`
- `site/compare-preview.html`
- `site/proof.html`
- `site/faq.html`
- `site/use-cases.html`
- `site/compare-vs-tracker.html`
- `site/quick-start.html`
- `site/community.html`
- `site/404.html`

### Locale-sensitive formatting already visible

- `frontend/src/components/PriceHistoryChart.tsx` currently hardcodes `en-US` formatting, so Prompt 2 should treat formatting helpers as part of the substrate rather than only translating text.

## Locked Constraints

- Repo/docs/runbooks remain English canonical.
- Product-facing surfaces may become bilingual.
- Bilingual implementation must be systematic i18n, not scattered literals.
- WebUI and `site/` must not drift into two unrelated translation systems.
- Prompt 2 should build shared substrate first; Prompt 3/4 should migrate pages onto it.

## Recommended First Step

### Required substrate pieces

Prompt 2 should start by creating:

1. a shared message catalog shape for `en` and `zh-CN`
2. locale state and persistence for the WebUI
3. a lightweight lookup/helper layer for product copy
4. locale-aware formatting helpers where current code hardcodes English formatting
5. one shared source-of-truth strategy so `frontend/` and `site/` do not fork into two translation systems

### Recommended migration order

After the substrate exists, migrate in this order:

1. `AppShell` and navigation
2. `ComparePage`
3. `TaskListPage` / recovery surfaces
4. `WatchGroupDetailPage`
5. `NotificationSettingsPage`
6. public `site/` pages

This keeps the compare-first product spine bilingual before the broader public surface.

## Explicit Non-Goals

Prompt 2 should **not**:

- translate every page immediately
- clone static HTML files into language-specific duplicates
- introduce one i18n system for `frontend/` and another for `site/`
- market bilingual support before the substrate exists

## Done Signal For Discovery

This discovery is complete when later Workers can answer these questions without rereading the whole repo:

- Does a reusable i18n substrate already exist? `No`
- Where are the highest-risk hardcoded copy hotspots? `AppShell + main WebUI pages, then site pages`
- What is the safest first implementation move? `Build a shared i18n substrate before any page-level translation`
