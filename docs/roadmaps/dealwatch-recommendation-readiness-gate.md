# DealWatch Recommendation Readiness Gate

## Purpose

This document records the current recommendation launch boundary for DealWatch.

In plain English:

- a narrow local Compare Preview recommendation surface is now shipped
- broader user-visible recommendation is still blocked
- internal shadow mode is now allowed to start under a strict contract
- later Workers should not confuse "compare-preview advisory-ready" or "shadow-ready" with broader launch readiness

Use this document when the question is:

> "What recommendation surface is actually shipped now, what still stays blocked, and what exactly is allowed next?"

## Status

> **Status:** `compare-preview-public-advisory-v1 = SHIPPED`, `broader-user-launch = NOT READY`, `internal-shadow = READY UNDER GOVERNANCE`.
> Prompt mapping truth: current total closeout program `Prompt 1 — Recommendation Final Repo-Side Closeout` is refreshing the inherited Prompt 8 recommendation lane after the earlier Prompt 7 evaluation campaign. Historical execution-program `Prompt 9` remains the later closeout stage. These labels describe one sequence, not competing truth sources.

This gate is a launch-boundary document, not a marketing page.

## What changed in this wave

Previous gate truth was:

- recommendation was blocked
- the repo still lacked recommendation-specific governance, abstention, and monitoring language

Current gate truth is:

- a narrow Compare Preview recommendation surface is now allowed in the local runtime compare flow
- broader recommendation is **still blocked from user-visible launch**
- the repo now has a formal governance contract in [`docs/roadmaps/dealwatch-recommendation-shadow-governance.md`](./dealwatch-recommendation-shadow-governance.md)
- internal shadow artifacts may now start as repo-local, internal-only outputs
- Prompt 7 already moved recommendation from governed shadow into a real internal evaluation campaign with seeded starter replay, harvested native compare-origin cases, non-seeded runtime corpus expansion, adjudication workflow, monitoring totals, and a launch-readiness dossier
- Prompt 8 now adds breadth-first harvesting plus explicit source-diversity accounting, so the repo can say when native compare-origin growth is still only one repeated pattern instead of broader calibration evidence
- the maintainer-facing operator loop now lives in [`docs/runbooks/recommendation-shadow-operations.md`](../runbooks/recommendation-shadow-operations.md)

Current workspace truth for this gate is:

- default internal workspace: `.runtime-cache/operator/recommendation-evaluation-v1`
- current repo-local snapshot: `13 total`, `11 included`, `5 issued`, `6 abstained`, `2 invalid_or_skipped`
- current review queue: `11 reviewed`, `0 pending`
- current disagreement buckets in this fully adjudicated v1 workspace are: `abstain_when_should_speak: 3`, `speak_when_should_abstain: 3`
- the native compare-origin lane has an evidence-backed ceiling: `30` available histories collapse to `1` unique pattern / `1` unique store pair / `1` unique source-url pair family, with `29` repeated rows dropped and `top share = 1.0`

## Current decision

### Compare Preview public advisory v1

**Status: SHIPPED**

DealWatch now ships one narrow recommendation surface:

- the local runtime Compare Preview result
- the paired compare evidence review artifact

This first public contract is intentionally conservative:

- deterministic compare evidence stays primary
- abstention is first-class
- the verdict subset is `wait`, `recheck_later`, or `insufficient_evidence`
- `buy_now` remains blocked in compare-only v1
- users still choose whether to save evidence, create a watch task, or create a watch group

### Broader recommendation expansion

**Status: NOT READY**

DealWatch should still **not** ship broader recommendation surfaces in this wave.

That means:

- no task-detail recommendation surface
- no watch-group recommendation surface
- no builder or MCP recommendation tool
- no README / proof / FAQ wording that implies autonomous or cross-surface buy/wait parity
- no static GitHub Pages sample page that pretends to run the live local recommendation card

### Internal shadow recommendation

**Status: READY UNDER GOVERNANCE**

DealWatch may now start generating internal-only recommendation shadow artifacts, as long as all of the following remain true:

- the artifact stays repo-local
- the artifact remains subordinate to deterministic truth
- abstention is first-class
- the artifact is reviewable and replayable
- public surfaces remain silent

This does **not** mean "recommendation is suddenly launch-ready."

The current internal stop line has moved forward:

- the v1 workspace no longer carries repo-local review debt for the current corpus (`11 reviewed`, `0 pending`)
- the disagreement map is now deeper than a starter packet, but it still only spans two disagreement classes across the current narrow corpus
- the native compare-origin breadth ceiling is now proven, and the corpus is still too concentrated to justify launch language
- the canonical campaign report now reads `native_compare_origin_source_case_kind = runtime_compare_evidence_package`, which means the machine has finally produced a fresh runtime compare-evidence package through the compare mainline
- even after that forward step, the current honest native pool still collapses to one acceptable pattern once obviously mismatched weak-compare packages are filtered back out

The recommendation lane only becomes "mostly real external blockers" after both of these are true:

1. the repo-local review debt is either adjudicated or intentionally superseded by a broader rerun with the same honest contract
2. widening recommendation breadth would genuinely require new live compare-origin families beyond the current `single_pattern_runtime_ceiling`

For the current v1 workspace, those two conditions now hold:

- the repo-local review debt has been adjudicated to `11 reviewed`, `0 pending`
- the next meaningful breadth increase still depends on new live compare-origin families beyond the repeated pears pair
- the next best candidate pair is now narrowed to `safeway + target` fairlife, where a fresh Target self-test now succeeds again but Safeway still returns an Incapsula block page on the automated Playwright path
- the current machine also has no live DealWatch-owned dedicated Chrome lane under `~/.cache/dealwatch/browser/chrome-user-data`, so this turn has no separate repo-owned session lane to claim as an alternate green path

That means the lane is now **mostly external-blocker-shaped for breadth growth**, while still remaining firmly blocked from any broader recommendation launch beyond Compare Preview v1.

### Current broader-expansion-only blocker pack

The current blocker is smaller than it was in earlier waves.

It is no longer:

- a repo-side compare-evidence ingestion gap
- a repo-side review continuity gap
- a question about whether Compare Preview advisory v1 shipped

It is now:

- current native harvesting now uses `runtime_compare_evidence_package`
- the native compare-origin pool still lands at only `1` acceptable pattern in the fresh canonical rerun
- the current corpus is still maintainer-scoped mixed internal evidence, not broader public-calibration evidence
- future expansion to task/group/MCP/builder/static pages would still need more native compare-origin families, more stable disagreement buckets, and broader calibration evidence than the current compare-preview slice

The next honest runtime candidate remains the Safeway + Target fairlife pair:

- that pair now genuinely produces a fresh runtime compare-evidence package
- the fresh rerun therefore no longer fails on missing native compare-evidence ingestion or fallback source kind

What still fails to expand breadth beyond that first accepted native family is now more specific:

- the old `weee + ranch99` pears lane can fetch again on the Weee side after the repo-side parser fix, but the Ranch99 URL has drifted into a different product and is no longer an honest second family
- `target + walmart` still collapses to one successful row because Walmart returns a blocked-page path
- `safeway + target` eggs still collapses because Safeway continues to return an Incapsula block page on that product path

So the repo-side question is no longer "did we wire the lane correctly?"

It is now:

> can the repo obtain a second acceptable native compare-evidence family without cheating, and without counting obvious weak mismatches or blocked-page half-runs as breadth?

## What is already true

The current repo already supports strong evidence-reading surfaces:

- Compare Preview returns deterministic compare evidence, pair scores, and `recommended_next_step_hint`
- compare evidence can already be saved as runtime-local artifact packages
- Watch Group detail returns deterministic `decision_explain` plus optional AI narration
- Task detail returns effective-price history, latest-signal deltas, `is_new_low`, and anomaly reasons
- Recovery Inbox returns deterministic operator guidance plus optional AI recovery narration

These are meaningful decision-support signals.

They are still **not** the same as a broadly shipped purchase-timing contract.

## Gate table

| Gate | Current repo truth | Broader launch verdict | Internal shadow verdict |
| --- | --- | --- | --- |
| Deterministic evidence exists | Compare, group, task, and recovery evidence are real | Compare Preview v1 may speak conservatively; broader launch still not sufficient by itself | sufficient to start shadow |
| Recommendation governance exists | governance, abstention, monitoring, and review contracts now exist | still not enough for broader launch alone | pass |
| Abstention contract exists | `insufficient_evidence` and silence boundaries are now explicit | required and active in Compare Preview v1, but still not broader-launch sufficient alone | pass |
| Internal artifact path exists | repo-local compare-evidence-side shadow artifact can exist | must stay hidden from public contract | pass |
| Override / feedback loop is live | repo-local review recording and review log now exist, but the loop is still maintainer-facing | fail for broader launch | pass |
| Recommendation-specific evaluation exists | Prompt 7 proved the replay/adjudication workflow; Prompt 8 now proves the current native compare-origin runtime pool is still a single concentrated pattern (`30` available rows, `1` unique pattern, `1` unique store pair, top pattern share `1.0`) | fail for broader launch | pass for internal evidence continuation |
| Public UI/API boundary is protected | recommendation is now limited to Compare Preview plus compare evidence review, while wider surfaces remain silent | pass | pass |

## Why user-visible launch is still blocked

### 1. Recommendation-specific evaluation is still missing

The repo verifies:

- compare evidence correctness
- watch-group decision explanation
- runtime recovery guidance

It still does **not** verify:

- purchase-timing correctness
- false-positive cost
- false-negative cost
- calibration over replayed history

Without those, a public recommendation surface would look more confident than the repo can honestly defend.

### 2. Shadow review is not the same as user trust

Internal shadow artifacts are like internal scorecards.

They help the team learn:

- what the system would have said
- what it abstained on
- what later evidence proved wrong

That is useful.

It is still not the same as telling users to act on those calls.

### 3. The product still must keep deterministic truth in charge

Current deterministic truth answers questions like:

- did the compare resolve?
- who won the basket?
- was the latest price a new low?
- is the runtime healthy enough to trust automation?

Recommendation crosses into a different question:

- should a human act now?

That question needs stricter evaluation and remediation than current explain-only surfaces.

## Why internal shadow can start now

Internal shadow is now allowed because the repo can finally do all of these safely:

1. identify allowed deterministic inputs
2. keep AI subordinate
3. abstain explicitly instead of forcing a verdict
4. generate a repo-local artifact for review and replay
5. keep public surfaces silent

In plain English:

> we can now practice in the gym
> but we are still not walking onto the public stage

## Shadow admission criteria

An internal shadow artifact is allowed only when all of the following are true:

1. the source surface is an approved deterministic anchor
   - current safest first anchor: Compare Preview evidence
2. the artifact uses only governed inputs
3. the artifact includes:
   - verdict
   - basis
   - uncertainty or abstention
   - evidence refs
   - review state
4. the artifact remains runtime-local
5. no public contract is changed to surface recommendation as shipped truth

## Current safest first surface

The safest first surface remains **Compare Preview**.

Why:

- it is still the evidence-review step
- the operator has not yet committed to a durable winner as purchase advice
- compare evidence already has a repo-local artifact path
- future breadth growth should now prefer real runtime compare-evidence packages over reconstructed watch-group fallbacks whenever those packages exist

### Not approved as first shadow anchors

- **Watch Group detail**
  Too easy to overread basket leadership as purchase timing.
- **Task detail**
  Strong history, but weaker contested compare context.

## Required silence

Beyond the shipped Compare Preview advisory slice, recommendation must stay silent in:

- user-facing WebUI routes outside the local Compare Preview and compare evidence review flow
- GitHub Pages static sample screens
- public API response models outside compare preview / compare evidence review
- MCP and builder read surfaces
- public README / proof / FAQ wording that would imply autonomous or cross-surface buy/wait parity

If any of those wider surfaces starts rendering recommendation as if it is already broadly shipped, this gate has been violated.

## Required abstention

Shadow mode must emit `insufficient_evidence` instead of forcing a verdict when:

- the current evidence set is too thin
- compare confidence is weak
- durable timing evidence is missing
- store support is only evidence-only / limited
- runtime trust is degraded
- the call would depend on AI prose rather than deterministic anchors

## Promotion checklist before any broader recommendation expansion

Recommendation must stay blocked from broader expansion until the repo can answer all of these with code, tests, and product language:

1. What deterministic rule stack produces the recommendation?
2. What explicit abstention rules stop false certainty?
3. Where can maintainers record overrides and wrong calls?
4. How will the repo measure false-positive and false-negative cost?
5. What monitoring shows shadow quality over time?
6. How will UI wording stay subordinate to deterministic truth?
7. Which new real cross-store compare-evidence families exist beyond the repeated pears pair, so broader expansion is not still anchored to `runtime_group_summary_fallback`

## Current phase summary

The current repo is no longer at:

> "recommendation is forbidden because nothing is defined"

It is now at:

> "recommendation is shipped as a narrow Compare Preview advisory surface, governed enough for internal shadow, and still not honest enough for broader user-visible launch"

More specifically for the current broader-expansion blocker:

> "Target is no longer the repo-side blocker for the next candidate pair; Safeway's current live automated fetch path and the absence of a repo-local session lane are the remaining blockers to generating the next real native family on this machine"
