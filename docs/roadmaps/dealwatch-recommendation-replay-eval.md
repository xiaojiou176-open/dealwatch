# DealWatch Recommendation Replay / Evaluation

## Purpose

This document defines the first formal replay and evaluation contract for DealWatch recommendation shadow artifacts.

In plain English:

- Prompt 5 already allowed the repo to write internal-only recommendation shadow artifacts
- Prompt 6 formalized replay/eval as a contract
- Prompt 7 turned that contract into a real repo-local evaluation campaign without pretending recommendation is public
- Prompt 8 now tightens that campaign by separating source diversity from repeated depth
- this file explains what counts as replay input, what gets skipped, and how the repo should measure the shadow lane honestly

Use this document when the question is:

> "How does DealWatch replay recommendation shadow artifacts, what counts as a valid replay sample, and what should an evaluation result record?"

## Status

> **Status:** active internal-only replay / evaluation contract for the inherited Prompt 8 recommendation lane, refreshed during total closeout `Prompt 1`.  
> Numbering note: current total closeout program `Prompt 1 — Recommendation Final Repo-Side Closeout` is refreshing the inherited Prompt 8 continuation stage after the earlier Prompt 7 evaluation campaign. These are linked stages, not competing truth sources.

This file is an internal experiment contract, not a brief for anything beyond the shipped Compare Preview advisory slice.

## Boundary

This contract is intentionally narrow.

It authorizes:

- replaying repo-local compare-evidence packages
- evaluating recommendation shadow verdicts against later review/adjudication records
- measuring shadow coverage and failure buckets

It does **not** authorize:

- recommendation fields outside compare preview / compare evidence review
- user-visible recommendation outside the shipped Compare Preview advisory slice
- a launch claim in README / proof / FAQ that implies broader recommendation parity
- write-side MCP or operator automation expansion

## Current repo truth

The current Prompt 8 replay lane is anchored to repo-local artifacts that already exist in code:

- compare evidence package directory: `RUNS_DIR/compare-evidence/<artifact_id>/`
- deterministic anchor: `compare_evidence.json`
- internal shadow artifact: `recommendation_shadow.json`
- replay index artifact: `RUNS_DIR/compare-evidence/_shadow-monitoring/recommendation_replay_manifest.json`
- internal review log: `RUNS_DIR/compare-evidence/recommendation_shadow_reviews.ndjson`

Primary code anchors:

- `ProductService.create_compare_evidence_package()`
- `ProductService.record_recommendation_shadow_review()`
- `ProductService.create_recommendation_replay_manifest()`

The active repo-local workspace truth for this contract is:

- default workspace: `.runtime-cache/operator/recommendation-evaluation-v1`
- current replay snapshot: `13 total`, `11 included`, `5 issued`, `6 abstained`, `2 invalid_or_skipped`
- current adjudication snapshot: `11 reviewed`, `0 pending`
- disagreement buckets in the adjudicated v1 corpus now read: `abstain_when_should_speak: 3`, `speak_when_should_abstain: 3`
- native breadth ceiling is already evidenced as `single_pattern_runtime_ceiling`: `30` available native histories collapse to `1` unique pattern / `1` store pair / `1` source-url family, with `29` repeats dropped and `top share = 1.0`
- the canonical campaign report now also writes `native_compare_origin_source_case_kind`; after the fresh DealWatch-owned live-lane recovery, the current workspace truth is `runtime_compare_evidence_package`
- Prompt 8 now also applies a minimum compare-plausibility floor for native compare-origin harvesting, so obviously weak mismatches no longer count as new breadth just because two rows fetched successfully

That means Prompt 8 is no longer grading an empty rerun. It is grading a real, still-internal corpus whose remaining problem is concentration, not lack of any replay artifacts.

## Replay corpus unit

The replay corpus unit is one compare-evidence package directory.

Think of it like one closed lab folder:

- `compare_evidence.json` is the deterministic case file
- `recommendation_shadow.json` is the internal recommendation shadow verdict
- optional review/adjudication records explain whether later evidence agreed or disagreed

The replay contract does **not** treat README copy, AI-only prose, or public site wording as replay input.

## Replay corpus admission rules

The current v1 replay manifest includes a package only when all of the following are true:

1. `compare_evidence.json` exists
2. `recommendation_shadow.json` exists
3. `shadow_contract_version == v1`
4. `surface_anchor` is one of the approved internal evaluation anchors:
   - `compare_preview`
   - `watch_group_run_summary`
   - `watch_task_run_summary`

Prompt 8 adds one more honesty rule for native compare-origin harvesting:

- breadth comes before repeat depth
- repeated history for the same pattern may still exist in the runtime pool
- but the fresh replay batch should keep one representative case per detected native pattern before it starts admitting more repeated copies
- the campaign report must state whether native harvesting came from `runtime_compare_evidence_package` or had to fall back to `runtime_group_summary_fallback`, because that difference decides whether we are grading original compare-stage answer sheets or reconstructed watch-group recap notes
- native compare-origin harvesting should also refuse obviously implausible compare packages whose strongest match signal is too weak to defend as a real product family
5. `deterministic_truth_anchor.artifact_path` matches the colocated `compare_evidence.json`

In plain English:

> replay is only allowed to grade recommendation artifacts that still point back to the same deterministic compare case file they were generated from

## Replay skip rules

The replay manifest must skip a package when any of these conditions apply:

- `invalid_compare_evidence_payload`
- `missing_shadow_artifact`
- `invalid_shadow_artifact`
- `shadow_contract_invalid`
- `unsupported_shadow_contract_version`
- `unsupported_surface_anchor`
- `deterministic_truth_anchor_mismatch`

Why this matters:

- a missing shadow file means nothing was ready to evaluate
- an invalid shadow file means the experiment output itself is broken
- an anchor mismatch means the recommendation is no longer tied to the deterministic case file it claims to describe

Those are different failure modes and must not be collapsed into one vague "bad sample" bucket.

## Replay source contract v1

Each included replay entry must expose a `replay_source` block with at least:

| Field | Meaning |
| --- | --- |
| `surface_anchor` | which deterministic surface produced the shadow artifact |
| `compare_evidence_path` | machine-readable deterministic case file |
| `compare_evidence_html_path` | browser-readable deterministic review artifact |
| `shadow_artifact_path` | machine-readable recommendation shadow artifact |
| `shadow_html_path` | browser-readable recommendation shadow artifact |
| `review_log_path` | repo-local adjudication / review ledger |

This is the replay equivalent of a lab sample chain-of-custody sheet.

The nested `replay_source.surface_anchor` must match the entry's top-level `surface_anchor`.

## Benchmark result contract v1

The current repo does not yet produce a separate fancy benchmark database.

Instead, the v1 benchmark record is the combination of:

- one included replay manifest entry
- the latest adjudication/review record for that artifact, when present

Taken together, the benchmark result must be able to record:

| Field | Where it comes from now |
| --- | --- |
| `verdict` | `recommendation_shadow.json` |
| `abstention_active` / `abstention_code` | `recommendation_shadow.json` |
| `basis` | `recommendation_shadow.json` |
| `evidence_refs` | `recommendation_shadow.json` |
| `replay_source` | replay manifest entry |
| `expected_verdict` | latest review record |
| `actual_verdict` | latest review record |
| `review_state` | review record or shadow payload |
| `outcome_category` / disagreement bucket | review record |
| `observed_outcome` | review record |

This is enough for the repo to answer the practical question:

> what did the shadow say, what evidence did it cite, and what did later review say actually happened?

## Metrics v1

The current first-pass evaluation metrics are intentionally plain.

That is good discipline, not a weakness.

The repo must at least track:

| Metric | Current v1 meaning |
| --- | --- |
| `coverage` | `included_count / total_candidates` from the replay manifest |
| `abstention_rate` | `abstention_count / valid_shadow_artifact_count` from the monitoring summary |
| `invalid_input_rate` | `(invalid_artifact_count + skipped_artifact_count) / total_artifacts` from the monitoring summary |
| `recommendation_issued_count` | `issued_verdict_count` from the monitoring summary |

Useful companion buckets in the same phase:

- `disagreement_buckets`
- `evidence_strength_buckets`
- `review_state_buckets`
- `abstention_code_buckets`

These are still internal review signals.

They are not launch KPIs.

## What counts as a benchmark disagreement

The replay/evaluation contract should treat these as first-class disagreement types:

- `false_positive`
- `false_negative`
- `abstain_when_should_speak`
- `speak_when_should_abstain`

The repo may also record agreement states such as:

- `correct_verdict`
- `correct_abstention`

## What this contract still does not prove

This contract does **not** yet prove:

- long-range calibration quality
- public wording safety
- user trust readiness
- multi-user adjudication maturity
- recommendation launch readiness

It only proves:

> the repo can now identify which shadow artifacts are replayable, which ones are invalid/skipped, and how later review should be attached to them

## Promotion boundary

Even with replay/eval v1 in place, recommendation remains blocked from user-visible launch until the repo also has:

- a durable adjudication / override loop that maintainers actually use
- monitoring evidence over time instead of only one-off samples
- product wording that stays subordinate to deterministic truth
- a future launch review that looks at accumulated shadow quality, not just code presence

## Current smaller blocker pack

The current replay/eval contract is no longer stuck on repo-local plumbing.

For the inherited Prompt 8 workspace, the narrower truth is:

- compare-evidence package ingestion for native harvesting is already wired
- reruns no longer reopen the reviewed queue as if adjudication continuity were missing
- the current report now says `native_compare_origin_source_case_kind = runtime_compare_evidence_package`
- the current honest native pool still has only one acceptable compare-origin pattern after the weakest mismatched package is filtered back out

In plain English:

> the replay lane is no longer failing because the repo forgot how to ingest or preserve review state
> it is now failing to grow because the broader native compare-origin history is still too narrow even after one fresh live compare package finally landed

## Current phase summary

The honest Prompt 8 posture is:

> DealWatch can now index and replay its recommendation shadow lane internally  
> DealWatch still cannot market recommendation as a launched product feature
