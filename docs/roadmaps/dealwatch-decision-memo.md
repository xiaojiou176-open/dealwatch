# DealWatch Decision Memo

## Purpose

This memo is the post-archive strategic SSOT for the current DealWatch execution phase.

In plain English:

- it turns the newly locked conversation decisions into durable repo truth
- it separates stable direction from still-open execution work
- it tells future Workers what is already decided so they do not reopen strategy every time implementation starts

Use this document when the question is:

> "What is already decided, what is deliberately deferred, and what should the next implementation prompts actually do?"

## Status

> **Status:** active strategic SSOT for the post-archive execution phase.  
> This memo locks direction. It does **not** claim that every follow-on implementation prompt is already finished, committed, or live-deployed.

## Why this memo exists

The repository already has:

- separate maintainer closeout ledgers for repo-side and live/public truth

What was still missing was a single document that says:

- which strategic debates are already closed
- which implementation boundaries are non-negotiable
- what the next execution order should be

## Locked Decisions

| Area | Locked decision | Why it matters |
| --- | --- | --- |
| Brand | `DealWatch` remains the only live product name | We are strengthening the product story, not restarting brand identity around `.ai` naming |
| Product core | The product remains `WebUI + API + worker + PostgreSQL` | This is the engine; plugin or agent shells are optional outer layers, not the product body |
| Product shape | DealWatch stays compare-first | The product starts by validating the target before creating long-lived state |
| AI boundary | AI remains real but narrow: explanation, recovery guidance, and distribution leverage | AI helps explain evidence; it does not replace deterministic product truth or become the main product identity |
| Public operating mode | Current primary operating mode is `local-first + GitHub Pages` | The public surface should stay honest about what is reachable now without pretending there is a hosted SaaS |
| Render role | Render stays an optional blueprint, not the current guaranteed runtime story | Render drift should not silently regain mainline status just because the blueprint still exists |
| Language boundary | Repo/docs/runbooks remain English canonical; product-facing surfaces may be bilingual | Internal collaboration and tracked engineering artifacts stay single-canonical |
| i18n boundary | If bilingual product surfaces are built, they must use systematic i18n | No more scattered bilingual literals across pages or components |
| Platform boundary | Stable API contract, stable read-only MCP contract, and public developer docs come before any SDK promise | We want real integration surfaces, not platform theater |
| MCP boundary | Read-only MCP remains the active safety line | Agent access is allowed as an observation window, not as a destructive remote control |
| Recommendation boundary | Recommendation stays governance-first, compare-first, and deterministic-first. The local runtime Compare Preview advisory v1 is allowed; broader autonomous buy/wait expansion remains gated. | Evidence review and explanation are shipped, the first compare-stage recommendation surface is now explicit, and broader recommendation claims still need tighter calibration evidence |
| Store growth order | Safeway / grocery-tier expansion is next after formalization groundwork is stable | The repo should deepen the strongest product lane before broadening into riskier retailer scope |

## Explicit Non-Goals

These are intentionally **not** reopened by this memo:

- rename the repo or product to an AI-first brand
- reposition DealWatch as a hosted SaaS
- promote Render back to a default guarantee
- ship write-side MCP
- ship broader or autonomous buy / wait recommendation beyond the local Compare Preview advisory v1
- promise a formal SDK product
- turn the browser extension idea into the primary product surface

## Integration Positioning

DealWatch should relate to external agent ecosystems in the safest truthful way:

- as a product/runtime that can expose stable truth through API and read-only MCP
- as a backend that tools such as Claude Code, Codex, OpenHands, or similar clients can consume
- not as a product that needs to run "on top of" a coding-agent shell to justify its identity

In plain English:

> the right relationship is "agent clients consume DealWatch truth"  
> not "DealWatch only exists as a skin on someone else's runtime"

## Truth Layers

| Layer | Meaning here |
| --- | --- |
| Strategic truth | The direction in this memo is locked unless fresh repo evidence or user instruction explicitly changes it |
| Repo-side implementation truth | What the current working tree and docs already implement or describe |
| Local-only truth | Anything still living only in the dirty working tree and not yet protected by git history |
| Live truth | Anything that requires fresh public/deployment verification |

## Immediate Execution Order

The next implementation program should follow this order:

1. **Prompt 1: formalize and align**
   - write this memo
   - align README / roadmap / closeout language
   - keep GitHub Pages and Render wording honest
2. **Prompt 2: build the i18n substrate**
   - establish locale/messages/fallback rules before migrating pages
3. **Prompt 3-4: migrate product-facing surfaces**
   - WebUI first
   - then public Pages
4. **Prompt 5: stabilize API/MCP substrate**
   - document stable surfaces and ownership boundaries
5. **Prompt 6-7: execute Safeway growth in milestones**
   - C1 first, then C2/C3
6. **Prompt 8: recommendation governance + compare-preview bridge**
   - keep shadow governance intact while defining the narrow local Compare Preview advisory surface
7. **Prompt 9: final closeout + execution plan v2**

## What still remains open

These items are still execution work, not strategic uncertainty:

- landing the first post-archive formalization edits across docs
- building the actual i18n substrate
- migrating product-facing copy into that substrate
- deciding how far the first API/MCP documentation pass goes
- implementing and validating Safeway milestones
- growing recommendation calibration and boundary docs beyond the shipped local Compare Preview advisory v1

## Revisit Triggers

Only revisit this memo if one of these happens:

1. fresh repo evidence proves a locked statement is now false
2. a future execution prompt needs a narrower contract within these same boundaries
3. the user explicitly changes direction

If none of those happen, later Workers should treat this memo as settled strategy rather than a new brainstorming invitation.
