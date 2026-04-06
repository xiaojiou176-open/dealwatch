# DealWatch Post-Archive Execution Program

## Purpose

This document turns the archive-level decisions into a worker-ready execution program.

In plain English:

- the archive already locked the strategy
- later Workers should not reopen the same debates
- this file translates the archive outcome into a staged execution program with explicit boundaries

Use this file when the question is:

> "What should the next Worker do, in what order, and what must stay deferred?"

## Relationship To Other Docs

| Document | Role |
| --- | --- |
| `docs/roadmaps/dealwatch-decision-memo.md` | Strategic SSOT |
| `docs/roadmaps/dealwatch-post-archive-execution-program.md` | Worker-ready staged execution sequence |
| `docs/roadmaps/dealwatch-master-delivery-plan.md` | Historical wave blueprint |
| `docs/roadmaps/dealwatch-repo-side-closeout.md` | Repo-side implementation truth |
| `docs/roadmaps/dealwatch-live-truth-closeout.md` | Live/deployment truth |
| `docs/roadmaps/dealwatch-recommendation-readiness-gate.md` | Recommendation defer gate |

## Program Rules

- Do not reopen product naming, AI posture, or deployment posture without fresh evidence.
- Keep DealWatch compare-first, local-first, and recommendation-deferred.
- Keep bilingual work infrastructure-first: no new scattered bilingual literals.
- Keep SDK out of the current promise set.
- Keep write-side MCP deferred.

## Continuation Note

This document is still the historical worker-ready execution sequence for the post-archive continuation.

The active master chain has now moved forward:

- Wave 3 closeout tail
- Wave 4 browser strengthening + product maturity
- Wave 5 Switchyard first slice + final convergence
- Wave 6 amplification

Use `.agents/Tasks/TASK_BOARD-2026-04-03-master-wave3-tail-through-wave6.md` as the live local execution ledger for that chain.

In plain English:

> this file still explains how the repo got here,
> but the current knife is no longer only Prompt 8 recommendation breadth work.

## Current Focus — Wave 3 Tail Sync Through Wave 6 Convergence

The current repo-local knife is no longer "run another recommendation-only continuation wave."

That work already paid off:

- recommendation docs now agree on the current v1 workspace truth
- the native breadth ceiling is already formalized as `single_pattern_runtime_ceiling`
- the review queue is already closed at `11 reviewed`, `0 pending`
- Walmart has already moved past C1 into the current product-path `official_full` truth
- the browser debug lane and Switchyard explain seam are already landed repo-side

The current focus is narrower and more honest:

1. sync all live ledgers and public-facing repo docs to the currently landed `22a551b` reality
2. keep recommendation internal-only and explicitly stop at the current external-data-shaped ceiling
3. keep Walmart `official_full` only for the current supported PDP path, with broad discovery still deferred
4. keep the browser debug lane classified as repo-owned success, not a missing lane
5. keep the Switchyard seam described as explain-only service-first, not a Big Bang brain swap
6. convert Wave 6's infinite ideas into explicit defer now rather than fuzzy future debt

Minimum done signal for this focus:

- the master task board and execution ledger both speak from `22a551b` + fresh `2026-04-04` evidence
- README / public proof docs stop contradicting manifest/runtime truth
- GitHub Pages, Render, browser-session, and Git authorization remain split into separate truth layers
- recommendation remains public-silent while current ceiling and review-queue closure stay explicit
- Wave 6 finite surfaces are marked either `shipped now` or `explicit defer now`

## Current Prompt Packet Lineage

| Prompt | Theme | Goal | Current status |
| --- | --- | --- | --- |
| Prompt 1 | Direction lock + public-story alignment | Freeze the post-archive boundaries so later waves stop reopening strategy | `inherited baseline` |
| Prompt 2 | Builder Surface Pack | Turn the existing API / read-only MCP / CLI surfaces into a first builder-consumable layer | `inherited dirty-tree work` |
| Prompt 3 | Store Expansion Foundation | Formalize official store tiers, limited-support compare contract, and cockpit v2 | `repo-local foundation landed` |
| Prompt 4 | Safeway C2/C3 Closure | Close the Safeway group/recovery/cashback truth as far as repo-local evidence honestly allows | `repo-local closure landed` |
| Prompt 5 | Recommendation Governance + Shadow | Turn recommendation from defer-only language into governed internal shadow without public launch | `repo-local governance/shadow landed` |
| Prompt 6 | Recommendation Evaluation / Replay / Adjudication | Turn shadow into an internal decision experiment system with replay, review, override, and monitoring | `repo-local contracts + internal artifacts landed` |
| Prompt 7 | Recommendation Evaluation Campaign + Launch Readiness Dossier | Turn replay/adjudication/monitoring contracts into a real internal evidence packet with seeded starter replay, harvested native compare-origin replay, non-seeded runtime corpus expansion, maintainer workflow, and launch-readiness verdict | `landed as inherited baseline` |
| Prompt 8 | Recommendation Source Diversity Expansion + Calibration Breadth Hardening | Measure native compare-origin source diversity directly, switch harvesting to breadth-first selection, and write the current runtime ceiling as formal evidence when only repeated depth remains | `active wave` |

## Historical Program Lineage

| Prompt | Theme | Goal | Current status |
| --- | --- | --- | --- |
| Prompt 1 | Decision formalization + public-story alignment | Write the locked strategy into durable repo artifacts and align docs/public wording | `done for repo-local phase` |
| Prompt 2 | i18n substrate | Build the shared bilingual foundation before translating surfaces | `done for substrate / in_progress for migration depth` |
| Prompt 3 | WebUI bilingual Wave A1 | Migrate core product surfaces onto the i18n substrate | `in_progress` |
| Prompt 4 | Public site bilingual Wave A2 | Migrate public Pages surfaces without forking a second translation system | `in_progress` |
| Prompt 5 | API / MCP substrate phase 1 | Stabilize developer/agent-builder contract surfaces without inventing an SDK product | `in_progress` |
| Prompt 6 | Safeway C1 | Land compare + task support for the next grocery-tier store | `repo-local landed` |
| Prompt 7 | Safeway C2/C3 | Land group/recovery/cashback closure for Safeway | `repo-local closure landed` |
| Prompt 8 | Recommendation governance + shadow mode | Build governance and shadow surfaces without launching recommendation | `repo-local governance/shadow landed` |
| Prompt 9 | Final closeout + execution plan v2 | Produce the next durable handoff after this program is complete | `not started` |

## Prompt Details

### Prompt 1 — Decision formalization + public-story alignment

Goal:

- create durable strategic artifacts
- align README/roadmaps/closeout docs with the locked boundaries
- separate repo truth from live/deployment truth without reintroducing Render as the default story

Minimum done signal:

- `docs/roadmaps/dealwatch-decision-memo.md` exists
- all top-level closeout docs point to the decision memo
- public-facing docs stay honest about local-first, AI-enhanced, read-only-MCP, and recommendation-deferred posture

### Prompt 2 — i18n substrate

Goal:

- create shared locale state, message catalogs, and translation helpers
- stop bilingual work from becoming scattered literals

Minimum done signal:

- a shared substrate exists for `en` and `zh-CN`
- later Workers can migrate pages without inventing a second system

### Prompt 3 — WebUI bilingual Wave A1

Goal:

- migrate the core product spine onto the i18n substrate

Priority order:

1. `AppShell`
2. `ComparePage`
3. `TaskListPage`
4. `NotificationSettingsPage`
5. `WatchGroupDetailPage`
6. `TaskDetailPage`

Current progress:

- the substrate is already live
- migration has already deepened on `AppShell`, `ComparePage`, `TaskListPage`, `NotificationSettingsPage`, `WatchGroupDetailPage`, and `TaskDetailPage`
- the current slice now covers route-level copy, key CTA, major loading/error/empty states, and broader locale-sensitive formatting
- several pages now carry page-local bilingual fallback maps for not-yet-promoted shared keys, so the user-visible surface is ahead of the shared-catalog completeness
- `ComparePage` has now also promoted AI status copy, compare-form validation copy, and compare evidence / default-group labels into the shared-catalog path
- the latest closure slice also removed the remaining core-WebUI reliance on borrowed `site.*` wording for task/group/settings/detail surfaces; those areas now use page-owned shared keys for AI panel copy, ZIP/run labels, runtime/cockpit helper copy, task signal labels, and watch-group candidate labels
- the same closure slice also moved `ComparePage` saved-package guidance, group-lock hints, and pair-evidence bridge wording into shared keys
- `TaskDetailPage` now routes hero badges, source-label copy, latest-signal labels, fallback decision guidance, and compare-context labels through shared keys instead of borrowing unrelated site wording
- `WatchGroupDetailPage` now routes hero operational framing, candidate metadata, AI panel framing, and recent-runs explanation through shared keys, and `TaskListPage` / `NotificationSettingsPage` now carry deeper recovery + cockpit wording on their own shared branches
- `ComparePage` no longer renders user-visible compare copy through direct `draft(locale, COMPARE_COPY...)` calls; the visible surface now resolves through the shared-key helper path, with fallback logic pushed down into the helper layer
- the latest Core Surface Closure pass also re-verified `0` shared-key mismatches across `AppShell`, `ComparePage`, `TaskListPage`, `NotificationSettingsPage`, `WatchGroupDetailPage`, and `TaskDetailPage`
- the remaining biggest hotspot is now the smaller long-tail of deep `ComparePage` copy in the saved-package / candidate-evidence / group-builder zone plus later bridge cleanup, not generic label drift across the rest of the core product spine

### Prompt 4 — Public site bilingual Wave A2

Goal:

- migrate public Pages surfaces while keeping docs/runbooks English canonical

Priority pages:

- `site/index.html`
- `site/compare-preview.html`
- `site/proof.html`
- `site/faq.html`
- `site/use-cases.html`
- supporting public pages after the core set is stable

Current progress:

- `site/index.html`, `site/compare-preview.html`, `site/proof.html`, `site/faq.html`, `site/use-cases.html`, and `site/compare-vs-tracker.html` now all resolve against the shared catalogs through `site/i18n.js`
- the latest Core Surface Closure pass re-verified `0` shared-key mismatches across those six public pages
- key-mismatch auditing against the shared site catalogs is now `0` for the checked core public pages plus `site/compare-vs-tracker.html`
- repo-local HTTP serving confirms the homepage and its shared-catalog payloads still respond normally in the current closure wave
- `site/compare-preview.html` passed a real browser spot-check in both `zh-CN` and `en`, confirming locale switching and deep body copy rendering at runtime
- `site/compare-vs-tracker.html` passed a real browser spot-check in both `zh-CN` and `en`, confirming locale switching across the hero and comparison table plus successful screenshot loading
- `site/compare-vs-tracker.html` now carries shared-catalog-backed comparison, builder-facing MCP/API wording, and proof CTA copy instead of remaining a hardcoded English explainer
- `tests/test_e2e.py::test_public_comparison_page_switches_locale_and_keeps_assets` now gives the public comparison page a durable Playwright pytest guard for locale switching, builder-facing heading copy, metadata, and screenshot loading
- `tests/test_e2e.py::test_webui_compare_locale_validation_follows_locale_switch` now gives the WebUI compare surface a durable Playwright pytest guard for locale switching across local validation errors
- `tests/test_i18n_surface_alignment.py` now gives the compare-first surfaces a repo-owned catalog-alignment guard: it verifies `ComparePage` `compare.*` keys and `compare-vs-tracker.html` `site.comparisonPage.*` keys against the shared catalogs, and it also locks the key metadata bindings on the comparison page
- the shared site i18n substrate now also owns JSON-LD for `index`, `faq`, and `compare-vs-tracker`, so SEO-facing structured data is no longer trapped in a separate static-English channel
- `proof.html` now also participates in the same structured-data path, with shared-catalog-backed `TechArticle` schema plus a dedicated Playwright locale-switch check
- `compare-preview.html` now also participates in the same structured-data path, with shared-catalog-backed `WebPage` schema plus a dedicated Playwright locale-switch check
- public structured data is now hardened in two layers: initial English HTML schema/metadata baselines stay aligned for non-JS crawlers, and runtime locale switching can still replace those payloads with `zh-CN`
- the current remaining gap is no longer "is there a bilingual mechanism?" but "how much of the deeper shared catalog wording should still be promoted before the next wave"; this specific closure slice did not need a second site-html fork because the checked core pages were already fully catalog-backed

### Prompt 5 — API / MCP substrate phase 1

Goal:

- stabilize public API contract
- stabilize read-only MCP contract
- write developer / agent-builder docs
- make ownership/auth boundary explicit without pretending multi-tenant platform maturity

Current progress:

- `docs/roadmaps/dealwatch-api-mcp-substrate-phase1.md` is now a stronger developer / agent-builder first reference rather than only a roadmap artifact
- the doc now names stable HTTP surfaces, stable MCP tools, ownership/auth boundaries, minimal usage examples, route/schema pointers, and stable-vs-deferred-vs-internal distinctions
- the write-side/platform maturity story remains explicitly deferred

### Prompt 6 — Safeway C1

Goal:

- add Safeway compare-first intake and single-task support

Current progress:

- `src/dealwatch/stores/safeway/` now has adapter / discovery / parser files plus explicit out-of-stock handling and richer parser debug reasons
- direct Safeway-specific tests now cover discovery posture, parser failure semantics, adapter handoff, and provider URL resolution, on top of the broader contract/service/API coverage
- manifest and store registry now include Safeway
- targeted contract/service/API verification for the C1 slice is now passing
- the completion gate is now explicit before full C1 claims are allowed

Constraint:

- do not claim full store closure until contract, registry, tests, and smoke all agree

### Prompt 7 — Safeway C2/C3

Goal:

- extend Safeway to group, recovery, and cashback semantics

Constraint:

- no hacky store-specific contract pollution

Current progress:

- Safeway now clears repo-owned watch-group coverage instead of only compare/task coverage
- the same closure slice now proves recovery visibility for failed Safeway watch groups instead of leaving recovery as a roadmap noun
- capability truth, cockpit truth, and compare-support truth now converge on Safeway as `official_full`
- discovery still stays `manual-product-url-only`, but that is now documented as discovery posture rather than a blocker for the current product path

### Prompt 8 — Recommendation governance + shadow mode

Goal:

- move recommendation from vague defer to governed shadow capability

Constraint:

- recommendation must remain non-user-visible

Current progress:

- `docs/roadmaps/dealwatch-recommendation-shadow-governance.md` now acts as the formal governance contract for allowed inputs, shadow vocabulary, abstention, override/adjudication, and monitoring
- `docs/roadmaps/dealwatch-recommendation-readiness-gate.md` now separates `user-ready = NOT READY` from `internal-shadow = READY UNDER GOVERNANCE`
- compare evidence package generation now writes repo-local `recommendation_shadow.json/html` sidecars without changing the public compare API contract
- compare/API tests explicitly keep `shadow_recommendation` out of public response bodies while still asserting that the repo-local shadow files exist
- the current safest first anchor remains Compare Preview / compare evidence, not Watch Group detail or Task detail
- fresh verification has now rerun on the integrated diff: targeted shadow tests passed, `pnpm -C frontend build` passed, `./scripts/test.sh -q` passed, and `git diff --check` passed
- blocker-only review initially found a shadow truth-anchor blocker, then approved once compare/shadow package generation was forced back onto server-recomputed compare truth

### Prompt 9 — Final closeout + execution plan v2

Goal:

- consolidate the results of Prompt 1~8
- update the roadmap and closeout truth
- write the next execution plan so future Workers do not need archive archaeology

## Current Progress Snapshot

Current convergence snapshot:

- builder-facing API / CLI / read-only MCP surfaces are landed and verifiable
- the Store Onboarding Cockpit plus manifest/runtime tests now carry the real store contract
- Walmart now clears the current compare/task/group/recovery/cashback product path for supported PDP URLs
- recommendation governance has moved from vague defer into a bounded internal-only experiment lane, and the current stop line is now formal rather than hand-wavy
- the browser debug lane is repo-owned and healthy; authenticated browser proof remains external-condition-shaped
- the Switchyard seam is landed only as an explain-only service-first slice
- GitHub Pages now serves the current compare-first public story, while Render still does not confirm the hosted blueprint story

## Current Closure Priority

The current repo-local wave is no longer about opening new store fronts or pretending a new product launch is one prompt away.

It is now about honest convergence:

1. keep recommendation internal-only and stop at the already-proven native breadth ceiling
2. keep Walmart current-product-path full without overclaiming discovery breadth
3. keep browser lane success and authenticated browser proof as two separate facts
4. keep Switchyard framed as explain-only first slice rather than full compat
5. keep public Pages / README / proof surfaces in sync with the landed repo truth
6. keep infinite ecosystem ideas out of the active backlog unless they are explicitly re-entered with a bounded scope

In plain English:

> the next good wave is "finish the closeout truth and stop at real external blockers"
> not "reopen strategy because the repo already looks strong"

## Explicit Non-Goals For This Program

This program does **not** authorize:

- an `.ai` rename
- a hosted SaaS repositioning
- a browser extension-first pivot
- a write-side MCP launch
- a user-visible recommendation launch
- an SDK product marketing surface

## Handoff Rule

Later Workers should start from this file plus the decision memo, not from raw archive reconstruction, unless fresh evidence shows those documents are outdated.
