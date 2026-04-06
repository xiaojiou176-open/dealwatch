# DealWatch Recommendation Adjudication / Override / Feedback

## Purpose

This document defines the first formal adjudication, override, and feedback loop for DealWatch recommendation shadow artifacts.

In plain English:

- Prompt 5 gave the repo an internal recommendation shadow artifact
- Prompt 6 defined the adjudication contract
- Prompt 7 built a maintainer-facing loop that actually records whether that shadow call was right, wrong, too early, or too quiet
- Prompt 8 now uses that loop on representative cross-type samples instead of pretending repeated pears history alone is enough calibration breadth
- this file turns "some maintainer disagreed later" into a real repo-local review contract

Use this document when the question is:

> "Who is allowed to judge a recommendation shadow call, how is the decision recorded, and what exactly counts as a wrong call?"

## Status

> **Status:** active internal-only adjudication / feedback contract for the inherited Prompt 8 recommendation lane, refreshed during total closeout `Prompt 1`.  
> Numbering note: current total closeout program `Prompt 1 — Recommendation Final Repo-Side Closeout` is refreshing the inherited Prompt 8 continuation stage after the earlier Prompt 7 evaluation campaign. These are linked stages, not competing truth sources.

This file does not authorize a public recommendation workflow.

## Current workspace truth

The active adjudication workspace is:

```text
.runtime-cache/operator/recommendation-evaluation-v1/
```

Current repo-local review truth in that workspace:

- `11` artifacts now have maintainer adjudication
- `0` artifacts remain `pending_internal_review`
- the disagreement map is no longer a starter packet: `abstain_when_should_speak: 3`, `speak_when_should_abstain: 3`
- `confirmed: 5` and `overridden: 6` now prove the loop is active on the full current v1 corpus, but they still do **not** prove launch-grade calibration

## Boundary

This loop is intentionally maintainer-facing.

It exists to help the repo learn from recommendation shadow outputs.

It does **not** exist to:

- let end users vote on recommendation quality
- create a public moderation system
- expose a recommendation feedback UI
- turn AI self-correction into a source of truth

## Current repo truth

The current repo-local review loop already has a concrete internal seam:

- service method: `ProductService.record_recommendation_shadow_review()`
- review ledger: `RUNS_DIR/compare-evidence/recommendation_shadow_reviews.ndjson`
- shadow artifact mutation: the recorded review is mirrored back into `recommendation_shadow.json`
- monitoring summary consumption: `create_recommendation_shadow_monitoring_summary()` reads the review state and disagreement buckets
- replay consumption: `create_recommendation_replay_manifest()` attaches the latest review/adjudication context to replay entries

That means the repo already has a real internal review log.

This document defines how to use it consistently.

## Minimum review loop

The current v1 review loop is:

1. a compare-evidence package produces `recommendation_shadow.json`
2. a maintainer or internal operator reviews the shadow call against later deterministic evidence
3. the repo records the judgment in `recommendation_shadow_reviews.ndjson`
4. the repo mirrors the latest review state back into the shadow artifact
5. monitoring and replay artifacts read that state back out

Think of it like grading an exam:

- the original answer sheet stays on file
- the grade note is appended to the grading ledger
- later summaries read both the answer sheet and the grade record

## Review authority

Allowed reviewers in this phase:

- maintainers
- internal operators

Not allowed in this phase:

- end users
- public crowd feedback
- AI-only automatic self-correction without a deterministic record

## Review artifact / ledger contract v1

Each review record written to `recommendation_shadow_reviews.ndjson` must include:

| Field | Meaning |
| --- | --- |
| `review_contract_version` | contract marker for the review record |
| `recorded_at` | when the adjudication was recorded |
| `artifact_id` | the recommendation shadow artifact being reviewed |
| `surface_anchor` | current deterministic surface anchor |
| `shadow_contract_version` | the shadow artifact contract version under review |
| `reviewer` | who reviewed the artifact |
| `decision` | `confirmed`, `overridden`, or `rejected` |
| `reason_code` | short machine-readable reason |
| `outcome_category` | wrong-call or agreement category |
| `agreement_bucket` | normalized monitoring/replay bucket |
| `verdict_at_review_time` | what the shadow artifact originally said |
| `expected_verdict` | what the reviewer believes should have happened |
| `actual_verdict` | what the repo currently records after review |
| `observed_outcome` | what later deterministic evidence showed |
| `notes` | optional human-readable reviewer note |
| `follow_up_action` | optional next action |
| `evidence_refs` | optional explicit evidence anchors |
| `deterministic_truth_anchor` | compare evidence anchor copied from the shadow artifact |

## Review state meanings

The current review state vocabulary is:

| State | Meaning |
| --- | --- |
| `pending_internal_review` | no human adjudication has closed the loop yet |
| `confirmed` | the reviewer agreed the shadow call was directionally right |
| `overridden` | the reviewer changed the call while keeping the artifact in the review set |
| `rejected` | the reviewer judged the call unfit to trust as-is |

Important rule:

> `pending_internal_review` is unresolved debt, not soft approval and not a timeout-based APPROVE.

## Wrong-call taxonomy

The v1 adjudication loop should use these categories when the shadow lane is wrong:

| Category | Meaning |
| --- | --- |
| `false_positive` | the shadow spoke too strongly in a direction that later evidence did not support |
| `false_negative` | the shadow stayed too conservative when later evidence supported the stronger verdict |
| `abstain_when_should_speak` | the shadow emitted `insufficient_evidence`, but later deterministic evidence showed it should have made a call |
| `speak_when_should_abstain` | the shadow issued a verdict when it should have stayed in abstention |

Agreement categories may also be recorded:

- `correct_verdict`
- `correct_abstention`

Implementation note:

> the repo currently normalizes older shorthand codes such as `abstain_should_speak` and `speak_should_abstain` into the canonical spellings above

## What gets reviewed

The minimum internal review should look at:

- the deterministic compare evidence anchor
- the shadow verdict and abstention state
- the shadow basis and evidence refs
- the later deterministic outcome that the maintainer is using as a correction reference

That means the reviewer is not grading vibes.

The reviewer is grading:

> did this shadow call match what the deterministic evidence later justified?

## What "override" means here

An override is not a public user action.

In this phase it simply means:

- the maintainer believes the shadow verdict needs correction
- the repo records that disagreement explicitly
- replay/monitoring can count the disagreement instead of silently burying it

## Feedback loop outputs

The v1 feedback loop feeds two downstream internal artifacts:

1. **Replay manifest**
   - attaches the latest adjudication context to replay entries
2. **Monitoring summary**
   - counts review states and disagreement buckets over time

This is enough to answer the next practical question:

> are we mostly agreeing with shadow, or are we repeatedly overriding the same kind of mistake?

## What this loop still does not claim

This contract does **not** claim:

- a finished public feedback system
- a multi-user moderation model
- automated correction of live product behavior
- recommendation launch readiness

It only claims:

> the repo now has a real place to record when the internal shadow call was confirmed, overridden, or rejected

## Promotion boundary

Even with adjudication / override / feedback v1 in place, recommendation remains blocked from public launch until the repo also has:

- replay/evaluation evidence over time
- internal monitoring summaries that accumulate real history
- explicit public wording rules
- a future launch review based on evidence, not optimism

## Current phase summary

The honest Prompt 8 posture is:

> DealWatch can now record internal recommendation disagreements in a real repo-local ledger  
> DealWatch still cannot show recommendation as a public user feature
