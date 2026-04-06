# DealWatch Master Delivery Plan

## Purpose

This document turns the explored backlog into one maintainable delivery blueprint.

It is intentionally split into:

- current repo truth
- ordering rules
- wave plan
- master backlog

The goal is not to re-argue every thread. The goal is to make later implementation prompts unambiguous.

## Prompt 6 Repo-Side Closeout Note

Prompt 1~5 created the product surfaces. Prompt 6 is the repo-side formal closeout pass.

- Use [`docs/roadmaps/dealwatch-decision-memo.md`](./dealwatch-decision-memo.md) for the post-archive strategic SSOT and locked boundaries.
- Use [`docs/roadmaps/dealwatch-repo-side-closeout.md`](./dealwatch-repo-side-closeout.md) for the current working-tree capability map and fresh verification ledger.
- Keep reading this file as the delivery blueprint and ordering document, not as the final live-truth verifier.
- Deployment/live-environment truth, especially Render alignment and the final role of `PRODUCT_AUTO_CREATE_SCHEMA`, remains intentionally outside this roadmap closeout and belongs to Prompt 7.

## Current Truth Snapshot

### Facts

- DealWatch is a compare-first grocery/deal monitoring product runtime.
- The current mainline is `Compare Preview -> Watch Task / Watch Group -> worker/manual run -> effective price / health / notification -> WebUI`.
- PostgreSQL via `DATABASE_URL` is the product source of truth.
- Legacy SQLite remains a bridge/import path, not the live product mainline.
- Current live store path supports `weee`, `ranch99`, and `target`.
- A thin mainline AI explanation layer now exists for compare, watch-group decisions, and recovery inbox guidance.
- A thin read-only MCP server now exists and wraps existing product truth through a local-first transport layer.
- Health, backoff, and manual-intervention signals already exist in the task/group model and service layer.
- Runtime preflight and product smoke exist as scripts and startup checks, but they are not yet productized into an operator-facing runtime surface.

### Inferences

- Wave 1 should productize existing runtime signals before adding new intelligence layers.
- The lowest-risk path is to reuse `ProductService`, existing models, existing scripts, and the current Task Board route rather than creating parallel abstractions.
- Later-wave AI and MCP work should sit on top of a cleaner operational state model, not precede it.

### To Confirm Later

- When the public Render deployment returns, verify whether deployment still actively depends on `PRODUCT_AUTO_CREATE_SCHEMA=true`.
- Decide whether later-wave MCP should stay local/owner-only first or go directly to authenticated remote transport.

## Ordering Rules

1. Foundation before flourish.
2. Product truth before landing-page claims.
3. Operator recovery before AI assistance.
4. Existing runtime semantics before new parallel abstractions.
5. Read-only exposure before write-heavy automation.

## Wave Overview

| Wave | Theme | Outcome |
| --- | --- | --- |
| Wave 1 | Foundation productization + operator visibility | Runtime Readiness and Needs Attention become real product surfaces |
| Wave 2 | Truth cleanup + explainability core | Decision reason, delivery truth, and deployment/runtime drift become clearer and safer |
| Wave 3 | AI mainline explainers + recovery copilot | Compare, group, and recovery now gain optional AI explanation layers without replacing core logic |
| Wave 4 | Extensibility + thin MCP + deployment truth cleanup | New store onboarding, read-mostly agent access, and remaining runtime truth cleanup become practical |
| Wave 5 | Recommendation bets + AI distribution layer | Higher-risk intelligence and AI growth surfaces get validated on top of a stable core |

## Master Backlog

| Name | Category | Current Status | Repo Footprint | Dependencies | Recommended Wave | Impact | Risk | Why This Order |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Runtime Readiness Dashboard | Foundation productization | Partial: real signals exist, no unified API/UI | `src/dealwatch/api`, `src/dealwatch/application/services.py`, `scripts/check_runtime_env.py`, `scripts/smoke_product*.sh`, `frontend/src/pages/TaskListPage.tsx` | Existing runtime preflight, owner existence, store bindings, smoke evidence | Wave 1 | High | Medium | First-run clarity reduces support cost and makes every later wave easier to validate |
| Needs Attention / Recovery Inbox | Recovery / operations UX | Partial: health fields exist, no unified triage surface | `src/dealwatch/application/services.py`, `src/dealwatch/persistence/models.py`, `frontend/src/pages/TaskListPage.tsx`, `frontend/src/pages/WatchGroupDetailPage.tsx` | Existing task/group health fields and run history | Wave 1 | High | Medium | This turns hidden operational state into a usable operator loop before adding intelligence layers |
| Operational State Aggregation Backbone | Stability / infra / deployment truth cleanup | Missing: signals are fragmented across services/scripts/routes | `src/dealwatch/application/services.py`, `src/dealwatch/api/app.py`, `frontend/src/lib/api.ts`, `frontend/src/types.ts` | Readiness + inbox shape agreement | Wave 1 | High | Medium | Both Wave 1 features need a shared aggregation layer; doing it once avoids duplicate ad hoc surfaces |
| Watch Group Decision Explainer Upgrade | Explainability | Prompt 2 landed: deterministic `decision_explain` now drives a clearer group decision surface | `src/dealwatch/application/services.py`, `frontend/src/pages/WatchGroupDetailPage.tsx`, `tests/test_product_api.py`, `tests/test_product_service.py` | Stable group runs and richer operator-facing context | Wave 2 | High | Low | It builds directly on already-landed compare-aware runtime and makes the core differentiator easier to trust |
| Notification Delivery Truth & Alert History Polish | Recovery / operations UX | Partial: `DeliveryEvent` and global notifications page exist, but not recovery-centered history | `src/dealwatch/persistence/models.py`, `src/dealwatch/api/app.py`, `frontend/src/pages/NotificationSettingsPage.tsx` | Wave 1 operational surfaces | Wave 2 | Medium | Low | After inbox/readiness exist, delivery history becomes much more actionable |
| Deployment Truth Cleanup (`PRODUCT_AUTO_CREATE_SCHEMA`, Render drift, smoke evidence semantics) | Stability / infra / deployment truth cleanup | Partial: runtime path no longer depends on bootstrap bridge, deploy examples still carry it | `src/dealwatch/persistence/session.py`, `render.yaml`, `.env*.example`, docs/runbooks | Wave 1 readiness visibility | Wave 2 | Medium | Medium | Readiness will surface the drift, so the next step is to actually clean the drift up |
| Shareable Compare Evidence Pack | Explainability | Prompt 2 MVP landed as runtime/local compare evidence artifact, not a new product SoT table | `src/dealwatch/application/services.py`, `src/dealwatch/api/app.py`, `frontend/src/pages/ComparePage.tsx`, `site/`, compare response shape, artifact patterns | Compare result stability and UI explainability groundwork | Wave 2 | High | Medium | It lets users save and revisit compare evidence without turning compare preview into a hosted sharing platform |
| Compare / Group Decision UX Polish | Explainability | Prompt 2 landed: ComparePage and WatchGroupDetailPage now foreground decisions, risks, and next-step CTA | `frontend/src/pages/ComparePage.tsx`, `frontend/src/pages/WatchGroupDetailPage.tsx`, `frontend/src/lib/api.ts`, `frontend/src/types.ts` | Wave 2 explain/data contracts | Wave 2 | High | Low | Once explain and evidence exist, the next leverage is turning them into product-readable pages instead of field stacks |
| AI Compare Explainer | AI mainline integration | Prompt 3 landed: compare preview now returns an optional AI explanation envelope built on deterministic compare evidence | `src/dealwatch/application/ai_integration.py`, `src/dealwatch/application/services.py`, `frontend/src/pages/ComparePage.tsx` | Wave 2 compare evidence + feature-flagged AI layer | Wave 3 | High | Medium | It explains the compare-first intake without letting AI replace the deterministic next-step logic |
| AI Watch Group Decision Explainer | AI mainline integration | Prompt 3 landed: group detail now returns an optional AI explanation envelope on top of `decision_explain` | `src/dealwatch/application/ai_integration.py`, `src/dealwatch/application/services.py`, `frontend/src/pages/WatchGroupDetailPage.tsx` | Wave 2 `decision_explain` + feature-flagged AI layer | Wave 3 | High | Medium | It strengthens the repo's clearest differentiator while keeping winner selection deterministic |
| AI Health / Recovery Copilot | AI mainline integration | Prompt 3 landed: recovery inbox now returns an optional AI copilot envelope while keeping deterministic reason/action anchors | `src/dealwatch/application/ai_integration.py`, `src/dealwatch/application/services.py`, `frontend/src/pages/TaskListPage.tsx` | Wave 1 recovery inbox + feature-flagged AI layer | Wave 3 | Medium | Medium | It helps operators triage issues faster without letting AI mutate health or retry logic |
| Store Onboarding Cockpit | Store extensibility | Prompt 4 landed: settings surface now exposes capability matrix, binding truth, onboarding checklist, and verification refs | `src/dealwatch/application/store_onboarding.py`, `src/dealwatch/api/app.py`, `frontend/src/pages/NotificationSettingsPage.tsx`, `docs/runbooks/store-onboarding-contract.md` | Stable operational surfaces and existing store contract files | Wave 4 | Medium | Medium | It makes store growth legible without pretending onboarding is fully automated |
| Thin MCP Layer | MCP exposure | Prompt 4 landed: read-only MCP server wraps existing product truth and lists tools through a local-first server entrypoint | `src/dealwatch/mcp/`, `src/dealwatch/application/services.py`, `src/dealwatch/api/deps.py`, `tests/test_mcp_server.py` | Stable read-mostly runtime surfaces and explicit safety boundary | Wave 4 | Medium | Medium | MCP now adapts a stable runtime instead of becoming a second backend |
| Buy / Wait Recommendation | Recommendation / intelligence bets | Prompt 5 gate says NOT READY; explicitly deferred until recommendation-specific evaluation, override, abstention, and monitoring exist | `docs/roadmaps/dealwatch-recommendation-readiness-gate.md`, compare/group/task decision surfaces | Stable explanations and trust surfaces plus recommendation-specific governance | Wave 5 | Medium | High | Recommendation is still higher-risk because it starts making decisions for the user, not just explaining state |
| AI Landing / SEO / Messaging Upgrade | Brand / landing / SEO / AI messaging | Prompt 5 landed: README, homepage, compare preview, proof, FAQ, use-cases, and `llms.txt` now express the AI-enhanced compare-first product more clearly | `README.md`, `site/`, proof pages, release/docs surfaces | Real AI-enabled product features to talk about | Wave 5 | Medium | Medium | Messaging now follows shipped product truth rather than brand hype |
| Shared Operator Mode / Light Collaboration Labels | Foundation productization | Suggestion only; single-owner runtime is the real current model | `users`, `user_preferences`, future notifications/inbox surfaces | Stable operator state, explicit auth/product decision | Wave 5 | Low | High | Collaboration is a broader product shift and should not distort the current single-owner control-cabin path early |

## Wave Definitions

### Wave 1 — Foundation Productization

Must land now:

- Runtime Readiness Dashboard
- Needs Attention / Recovery Inbox
- Shared operational aggregation surfaces
- Task board and roadmap truth

Success looks like:

- a first-run user can tell what is missing
- an operator can tell what needs intervention now
- task vs group distinctions remain explicit
- the UI uses real backend signals rather than hard-coded states

### Wave 2 — Truth Cleanup + Explainability Core

Must clarify:

- why a group winner is the winner
- what delivery truth currently says
- what deployment/runtime truth is still drifting

Prompt 2 completion note:

- deterministic `decision_explain` is now present in group detail
- compare evidence now has a runtime/local artifact MVP with create/list/detail paths
- ComparePage and WatchGroupDetailPage now foreground decisions, risks, and saved evidence review

### Wave 3 — AI Mainline Explainers + Recovery Copilot

Must add:

- AI explanation on top of compare evidence
- AI explanation on top of group decision truth
- AI recovery copilot on top of recovery inbox evidence

Prompt 3 completion note:

- compare preview now returns `ai_explain` on top of deterministic compare evidence
- watch group detail now returns `ai_decision_explain` on top of deterministic `decision_explain`
- recovery inbox now returns `ai_copilot` while keeping deterministic `reason` and `recommended_action` primary
- AI is feature-flagged, optional, and non-blocking when disabled or unavailable

### Wave 4 — Extensibility + MCP + Deployment Truth Cleanup

Must enable:

- safer store growth
- read-mostly agent access to runtime state
- cleanup of remaining deployment/runtime truth drift now that operator and AI surfaces are visible

Prompt 4 completion note:

- Notification Settings now acts as a Store Onboarding Cockpit powered by real store capability and binding truth
- a thin read-only MCP server now exposes compare, watch, runtime, notification, and store cockpit truth
- write-side MCP actions are intentionally deferred so Wave 4 stays local-first and low-risk

### Wave 5 — Recommendation + Distribution Bets

Must validate:

- whether decision assistance should move from explanation to recommendation
- whether AI distribution/messaging genuinely helps once AI is real product value, not just branding

Prompt 5 completion note:

- README and public pages now present DealWatch as an AI-enhanced compare-first grocery price intelligence product
- AI messaging is now tied to real compare explanation, watch-group explanation, recovery guidance, store cockpit, and read-only MCP capabilities
- `Buy / Wait Recommendation` was explicitly reviewed and deferred behind a recommendation-readiness gate instead of being shipped as a shell

## Explicit Deferrals After Wave 3

Still not in scope after this wave:

- MCP server implementation
- domain rename / `.ai` rename
- major auth or multi-user shift
- recommendation-style AI that starts deciding for the user
- major brand / SEO revamp before the next product wave is proven
