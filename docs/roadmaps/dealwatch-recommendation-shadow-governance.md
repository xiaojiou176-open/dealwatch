# DealWatch Recommendation Shadow Governance

## Purpose

This document turns recommendation from a vague deferred idea into a governed internal shadow capability.

In plain English:

- DealWatch still does **not** ship user-visible purchase timing advice today
- the repo can, however, start producing recommendation-shaped internal artifacts
- those artifacts must stay bounded, reviewable, abstention-aware, and clearly subordinate to deterministic product truth

Use this document when the question is:

> "What recommendation inputs are allowed, when must the system abstain, what does a shadow artifact look like, and what evidence would be required before any user-visible launch is reconsidered?"

## Status

> **Status:** active governance contract for the current recommendation shadow phase.  
> Current prompt mapping: current total closeout program `Prompt 1 — Recommendation Final Repo-Side Closeout` is auditing and refreshing the inherited Prompt 8 recommendation evidence lane after repo-local Prompt 7, while historical execution-program `Prompt 8 — Recommendation governance + shadow mode` remains the inherited baseline stage.

This file is a governance and shadow-phase contract.

Recommendation is still **not user-ready**.
It does **not** claim that DealWatch has launched a public `Buy now / Wait / Re-check later` surface.

## Companion continuation artifacts

The current governance contract now has three companion documents for the next internal-only wave:

- [`docs/roadmaps/dealwatch-recommendation-replay-eval.md`](./dealwatch-recommendation-replay-eval.md)
- [`docs/roadmaps/dealwatch-recommendation-adjudication-feedback.md`](./dealwatch-recommendation-adjudication-feedback.md)
- [`docs/roadmaps/dealwatch-recommendation-shadow-monitoring.md`](./dealwatch-recommendation-shadow-monitoring.md)
- [`docs/roadmaps/dealwatch-recommendation-launch-readiness-dossier.md`](./dealwatch-recommendation-launch-readiness-dossier.md)

## Current workspace truth

The active internal-only workspace for this continuation is:

```text
.runtime-cache/operator/recommendation-evaluation-v1/
```

The current governed snapshot in that workspace is:

- `13 total` replay items
- `11 included` valid shadow artifacts
- `5 issued`, `6 abstained`, `2 invalid_or_skipped`
- `11 reviewed`, `0 pending`
- disagreement buckets are now deeper than a starter packet: `abstain_when_should_speak: 3`, `speak_when_should_abstain: 3`
- the native compare-origin lane is already at `single_pattern_runtime_ceiling`: `30` available rows collapse to `1` unique pattern / `1` store pair / `1` source-url pair family, so `29` repeated rows are dropped instead of being miscounted as breadth

Seeded, runtime-derived, and harvested native compare-origin evidence remain **internal experiment truth only**. None of them upgrades recommendation into public product maturity.

## Why this file exists

The current repo already has strong evidence-reading surfaces:

- deterministic compare evidence
- compare-aware watch-group decision explanation
- task-level effective-price and latest-signal truth
- deterministic recovery guidance plus optional AI recovery narration

What the repo did **not** have yet was the rulebook that says:

- which signals recommendation is allowed to read
- which signals recommendation must never overread
- when recommendation must abstain
- how shadow outputs should be recorded and reviewed
- what must be true before recommendation can graduate beyond shadow mode

Without that rulebook, recommendation would drift into theater:

- either a fake public shell on top of existing signals
- or a hidden AI-overreach path that sounds more certain than the evidence warrants

## Locked boundaries for this phase

These are non-negotiable in the current shadow phase:

- `DealWatch` remains the only live product name
- recommendation remains **not user-visible**
- recommendation remains **advisory-only**
- deterministic product truth remains authoritative
- AI output remains a secondary readable layer, not a primary evidence source
- the current public operating story remains `local-first + GitHub Pages`
- docs and tracked governance artifacts stay English-canonical
- write-side MCP stays deferred
- recommendation does not become a proxy for a hosted copilot or autonomous buyer

## Shadow scope

The current shadow phase is intentionally narrow.

### In scope now

- internal-only recommendation artifacts
- repo-local artifact generation
- abstention-aware verdict vocabulary
- evidence refs and uncertainty notes
- internal review, override, and wrong-call recording contract
- replay/evaluation contract for compare-preview shadow artifacts
- repo-local review ledger and monitoring summary artifacts
- shadow monitoring fields that can later support readiness review

### Explicitly out of scope now

- user-visible recommendation cards
- public API recommendation fields
- public README / proof claims that recommendation is already shipped
- automatic purchase execution
- write-side MCP
- SDK or hosted-platform packaging

## Recommendation truth inputs

Recommendation is only allowed to read signals that already belong to DealWatch's deterministic product truth.

Think of this like a judge reading the official case file:

- court records are allowed
- hallway gossip is not

### Allowed deterministic inputs

| Input family | Current repo anchors | What the signal may support | What it must not overclaim |
| --- | --- | --- | --- |
| Compare Preview evidence | `compare_product_urls()`, `compare_evidence`, `recommended_next_step_hint`, `risk_note_items`, compare-support contract | intake confidence, candidate count, supportability, strongest pair score, compare-stage uncertainty | purchase timing by itself |
| Watch-group decision truth | `decision_explain`, winner vs runner-up, `price_spread`, `reliability`, candidate outcomes | basket-relative strength, operational reliability, current winner explanation | universal "buy now" timing without a recommendation-specific evaluation contract |
| Task price truth | task detail `effective_prices`, `latest_signal`, `is_new_low`, `delta_amount`, anomaly reason | whether the tracked item is moving, whether price history looks stronger or weaker | cross-store purchase timing without compare context |
| Recovery / health truth | recovery inbox deterministic reason, `recommended_action`, health/backoff/manual-intervention state | whether automation trust is degraded enough to block any recommendation call | purchase desirability |
| Store support truth | manifest, onboarding cockpit, compare support contract | whether a row is even eligible for durable product-path reasoning | recommendation confidence on unsupported or evidence-only rows |

### Allowed AI inputs

AI is allowed to contribute only as a secondary readable layer.

That means:

- `ai_explain`
- `ai_decision_explain`
- `ai_recovery_copilot`

may be copied into the shadow artifact as readable context, but they must never become the primary reason a recommendation verdict is issued.

### Disallowed inputs

The following must not drive recommendation verdicts in this phase:

- AI-only reasoning without a deterministic anchor
- unsupported-host or unsupported-path rows as if they were live watch truth
- single-task signals presented as purchase timing truth after compare context has already been lost
- undocumented heuristics typed directly into UI copy
- public-site prose, README copy, or operator intuition as substitute evidence
- live/deployment assumptions that are not backed by repo-local truth

## Shadow output vocabulary

Recommendation shadow artifacts use the following vocabulary:

| Verdict | Meaning in shadow mode | User-visible now? |
| --- | --- | --- |
| `buy_now` | The evidence would support a purchase-timing push **if** future readiness gates are met | No |
| `wait` | The evidence would support deferring purchase **if** future readiness gates are met | No |
| `recheck_later` | The current safest call is to gather more durable evidence before any purchase-timing conclusion | No |
| `insufficient_evidence` | The system must abstain because the current evidence file is not strong enough for a recommendation verdict | No |

Important rule:

> This is shadow vocabulary, not a public product contract.

In the current Compare Preview-first shadow anchor, the reachable safe subset is intentionally conservative:

- `wait`
- `recheck_later`
- `insufficient_evidence`

In this phase, `wait` does **not** mean:

> "the product is now certain about purchase timing"

It means:

> "the compare evidence is strong enough to keep watching instead of upgrading the current state into a buy-now claim"

`buy_now` remains part of the governed vocabulary, but it should not be issued from compare-only shadow unless a later phase adds recommendation-specific evaluation, override loops, and stronger timing evidence.

## Silence vs abstention

Shadow mode needs two different "do not overclaim" behaviors.

Think of them like:

- **abstention** = the reviewer writes "not enough evidence" in the file
- **silence** = the reviewer does not pin that note onto the public wall

### `insufficient_evidence` abstention

Recommendation must emit `insufficient_evidence` when an internal artifact is being generated but the evidence file does not justify a verdict.

Minimum abstention triggers:

- fewer than two successful compare candidates for a compare-stage shadow call
- no durable compare context and no approved substitute context
- unsupported / disabled / fetch-failed rows dominate the evidence
- recommendation would rely on AI prose rather than deterministic anchors
- recommendation would need price-history or feedback signals that are not present in the current truth set
- automation trust is degraded enough that health/recovery state is still unsettled

### Silence

Recommendation must remain silent on these surfaces in the current phase:

- user-visible WebUI pages
- public GitHub Pages surfaces
- public API response contracts
- MCP tool outputs
- README / proof / FAQ launch language

In plain English:

> shadow artifacts may exist in the filing cabinet, but they are not yet allowed onto the storefront signs.

## First shadow anchor

The safest first anchor is **Compare Preview evidence**, not Task detail and not Watch Group detail.

Why:

- Compare Preview is where the operator is still reviewing evidence, not acting on a durable "winner means buy" interpretation
- compare evidence can already be saved as repo-local runtime artifacts
- this anchor keeps recommendation subordinate to evidence review instead of letting it masquerade as the product's final answer

### Why not Watch Group first?

Watch Group detail is stronger than compare for basket ranking, but it is also easier to misread:

- a current winner is not the same thing as a purchase-timing verdict
- a basket leader can still be fragile, close-spread, or operationally noisy

### Why not Task detail first?

Task detail sees price history well, but it loses the contested compare context that recommendation should still respect.

## Shadow artifact contract v1

Every shadow artifact must carry these minimum fields:

| Field | Meaning |
| --- | --- |
| `shadow_contract_version` | versioned contract marker for replay/review |
| `mode` | must state internal-only shadow posture |
| `surface_anchor` | which deterministic surface produced the artifact |
| `status` | `issued` or `abstained` |
| `verdict` | shadow vocabulary value |
| `summary` | short human-readable explanation |
| `basis` | deterministic signals that were actually read |
| `uncertainty_notes` | what is still missing or fragile |
| `abstention` | abstention code/message when status is not a positive issued call |
| `evidence_refs` | machine-readable refs to the deterministic anchors |
| `review` | internal review/adjudication state |
| `monitoring` | counters/tags used for later replay and readiness evaluation |

### Artifact placement rule

The current shadow artifact must be repo-local and colocated with compare evidence artifacts.

That means:

- it may live beside `compare_evidence.json`
- it must not become PostgreSQL product source of truth
- it must not require a public API field to discover it

## Override, feedback, and adjudication contract

Recommendation cannot become trustworthy unless the repo can remember when the internal call was wrong.

The shadow-phase contract therefore requires an explicit review loop, even if the first code slice only marks that loop as pending.

Minimum review fields:

- `review.state`: `pending_internal_review`, `confirmed`, `overridden`, or `rejected`
- `review.owner`: who reviewed the call
- `review.reason_code`: why the reviewer agreed or overruled the call
- `review.notes`: short human-readable explanation
- `review.observed_outcome`: what later evidence showed

Override authority in this phase:

- maintainers or internal operators only
- never end users
- never AI auto-self-correction without a deterministic record

## Monitoring contract

Shadow mode is only useful if it leaves an audit trail.

At minimum, monitoring must be able to answer:

- how many shadow artifacts were issued
- how many abstained
- which abstention codes dominate
- which verdicts were later overridden
- whether the artifact had enough evidence coverage to justify review

Minimum monitoring tags:

- `input_profile` (for example `compare_preview_only`)
- `evidence_strength` (for example `strong_compare`, `weak_compare`, `missing_history`)
- `abstention_code`
- `review_state`
- `future_launch_blocked` (must remain true in this phase)

## Promotion gate to future user-visible consideration

Recommendation remains blocked from user-visible launch until the repo can prove all of the following:

1. recommendation-specific evaluation exists
   - replay or benchmark
   - false-positive / false-negative framing
   - calibration review
2. abstention behavior is tested and honest
3. override and wrong-call review loops are real, not only documented
4. monitoring can report shadow quality over time
5. UI wording is explicitly subordinate to deterministic evidence
6. public docs, API, tests, and runtime truth all agree on the same boundary

## Repo truth anchor map

Each contract above must stay anchored to current repo truth, not hand-wavy intent.

| Contract area | Primary repo truth anchors |
| --- | --- |
| Locked boundary and prompt mapping | [`docs/roadmaps/dealwatch-decision-memo.md`](./dealwatch-decision-memo.md), [`docs/roadmaps/dealwatch-post-archive-execution-program.md`](./dealwatch-post-archive-execution-program.md), [`docs/roadmaps/dealwatch-recommendation-readiness-gate.md`](./dealwatch-recommendation-readiness-gate.md), [`README.md`](../../README.md) |
| Allowed / disallowed input truth | [`src/dealwatch/application/services.py`](../../src/dealwatch/application/services.py), [`src/dealwatch/api/schemas.py`](../../src/dealwatch/api/schemas.py), [`tests/test_product_service.py`](../../tests/test_product_service.py), [`tests/test_product_api.py`](../../tests/test_product_api.py) |
| Shadow vocabulary and abstention split | [`docs/roadmaps/dealwatch-recommendation-readiness-gate.md`](./dealwatch-recommendation-readiness-gate.md), [`docs/roadmaps/dealwatch-decision-memo.md`](./dealwatch-decision-memo.md), [`README.md`](../../README.md) |
| Override / feedback / adjudication | [`docs/roadmaps/dealwatch-api-mcp-substrate-phase1.md`](./dealwatch-api-mcp-substrate-phase1.md), [`AGENTS.md`](../../AGENTS.md), [`tests/test_product_service.py`](../../tests/test_product_service.py) |
| Monitoring / artifact placement / future readiness | [`AGENTS.md`](../../AGENTS.md), [`docs/integrations/README.md`](../integrations/README.md), [`docs/roadmaps/dealwatch-api-mcp-substrate-phase1.md`](./dealwatch-api-mcp-substrate-phase1.md), [`docs/roadmaps/dealwatch-recommendation-readiness-gate.md`](./dealwatch-recommendation-readiness-gate.md) |

## Current phase summary

The current shadow phase is intentionally conservative.

That is a feature, not a bug.

It means DealWatch can start learning from recommendation-shaped internal artifacts without pretending the product already knows how to tell users when to buy.

The repo's current honest posture is:

> governed shadow can start  
> user-visible recommendation remains blocked
