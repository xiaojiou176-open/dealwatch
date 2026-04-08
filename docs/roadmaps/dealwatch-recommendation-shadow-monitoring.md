# DealWatch Recommendation Shadow Monitoring Contract

## Purpose

This document defines the internal-only summary view for recommendation shadow artifacts.

In plain English:

- Prompt 5 created individual shadow artifacts
- Prompt 6 defined the scoreboard contract that counts them across time
- Prompt 7 turned that scoreboard into a real campaign seam
- Prompt 8 now pairs the scoreboard with campaign-level diversity accounting so maintainers can separate breadth from repeated depth
- the scoreboard is still an internal ops artifact, not a user-facing dashboard

Use this document when the question is:

> "How many shadow artifacts exist, how many abstained, how many are still waiting for review, and which disagreement bucket is becoming the real problem?"

## Status

> **Status:** active internal-only monitoring contract for the inherited Prompt 8 recommendation lane, refreshed during total closeout `Prompt 1`.
> Numbering truth: current total closeout program `Prompt 1 — Recommendation Final Repo-Side Closeout` is refreshing the inherited Prompt 8 continuation wave after the earlier Prompt 7 evaluation campaign and still before historical execution-program `Prompt 9`.
> This is monitoring for maintainers, not a user feature and not a signal that broader recommendation launch is ready.

## Current implementation seam

The repo-local monitoring summary is currently produced by:

- `ProductService.create_recommendation_shadow_monitoring_summary()`

The generated artifacts live under:

```text
.runtime-cache/operator/recommendation-evaluation-v1/runs/compare-evidence/_shadow-monitoring/
  recommendation_shadow_summary.json
  recommendation_shadow_summary.html
```

The summary is derived from:

- compare evidence package directories under `.runtime-cache/operator/recommendation-evaluation-v1/runs/compare-evidence/`
- each colocated `recommendation_shadow.json`
- the repo-local review ledger `recommendation_shadow_reviews.ndjson`

Prompt 8 adds one more reading rule on top:

> the monitoring summary still owns the queue and disagreement scoreboard,
> but the campaign report must now also explain whether the native compare-origin lane is broad or just one repeated pattern wearing thirty different timestamps.

## Current snapshot

The current canonical workspace is:

```text
.runtime-cache/operator/recommendation-evaluation-v1/
```

The current monitoring truth in that workspace is:

- `13` total artifacts
- `11` valid replay-included shadow artifacts
- `5` issued verdicts
- `6` abstentions
- `2` invalid_or_skipped artifacts
- `11` reviewed and `0` pending
- `review_state_buckets = confirmed: 5, overridden: 6`
- `disagreement_buckets = abstain_when_should_speak: 3, speak_when_should_abstain: 3`

The paired campaign report also records the current native breadth ceiling:

- `30` available native compare-origin histories
- `1` unique pattern
- `1` unique store pair
- `1` unique source-url pair family
- `29` dropped repeats
- `top repeated pattern share = 1.0`

That ceiling is internal experiment truth, not a public maturity claim.

## Monitoring summary contract v1

The monitoring artifact must carry:

| Field | Meaning |
| --- | --- |
| `artifact_kind` | must be `recommendation_shadow_monitoring` |
| `monitoring_contract_version` | monitoring schema version |
| `storage_scope` | runtime-local storage marker |
| `mode` | internal-only monitoring mode |
| `visibility` | must remain `internal_only` |
| `generated_at` | summary generation timestamp |
| `source_directory` | artifact tree scanned for this summary |
| `review_log_path` | repo-local review ledger path |
| `review_record_count` | number of review records currently captured |
| `future_launch_blocked` | must remain `true` in this phase |
| `summary` | aggregate counters and bucket views |
| `recent_artifacts` | most recent artifact rows for operator inspection |

## Required counters

Prompt 8 monitoring must surface at least these top-level counts:

| Counter | Meaning |
| --- | --- |
| `total_artifacts` | compare-evidence artifact directories discovered |
| `issued_verdict_count` | shadow rows whose status is `issued` |
| `abstention_count` | shadow rows whose status is `abstained` |
| `invalid_or_skipped_count` | malformed or incomplete shadow rows combined |
| `review_pending_count` | shadow rows still waiting for review |
| `reviewed_count` | shadow rows already confirmed / overridden / rejected |

Prompt 8 may keep richer split counters too, such as:

- `valid_shadow_artifact_count`
- `invalid_artifact_count`
- `skipped_artifact_count`

## Required bucket views

The monitoring summary should also expose these grouped views:

| Bucket view | Why it matters |
| --- | --- |
| `verdict_distribution` | shows whether the system only abstains or actually issues governed internal calls |
| `evidence_strength_buckets` | shows whether the corpus is mostly strong compare evidence or weak/partial evidence |
| `review_state_buckets` | shows whether the repo is building review debt |
| `abstention_code_buckets` | shows why shadow most often refuses to speak |
| `disagreement_buckets` | shows which mistake class is becoming most dangerous |

### Disagreement bucket rule

Disagreement buckets must stay tied to adjudication truth.

Examples:

- `false_positive`
- `false_negative`
- `abstain_when_should_speak`
- `speak_when_should_abstain`
- `agreement`

The summary must not invent disagreement labels from vibes or prose.

Implementation note:

> the repo may still accept older shorthand labels from historical dirty-truth artifacts, but Prompt 8 canonical reporting should normalize them to `abstain_when_should_speak` and `speak_when_should_abstain`

## Recent artifact row contract

Each `recent_artifacts[]` row should carry at minimum:

| Field | Meaning |
| --- | --- |
| `artifact_id` | artifact identifier |
| `saved_at` | artifact save time |
| `status` | issued or abstained |
| `verdict` | shadow verdict |
| `review_state` | pending / confirmed / overridden / rejected |
| `evidence_strength` | monitoring evidence-strength bucket |
| `abstention_code` | abstention code when present |
| `disagreement_code` | disagreement / agreement bucket when review exists |
| `artifact_path` | repo-local path to the artifact |

## Reading rule

Monitoring summary is a health dashboard, not a launch certificate.

Correct reading:

- high abstention may mean honest caution
- low abstention may mean overconfidence
- many pending reviews may mean the repo lacks operator follow-through
- one dominant disagreement bucket may reveal the next rule-tightening target

Incorrect reading:

- "the dashboard exists, so recommendation is mature"
- "issued verdicts increased, so the system got better"
- "few disagreements means public launch is automatically safe"

## Prompt 8 breadth overlay

Prompt 8 does not ask the monitoring summary to become a second dashboard product.

It asks the internal campaign report to carry three extra honesty checks alongside the monitoring summary:

- native compare-origin unique pattern count
- native compare-origin unique store-pair / source-url-pair family counts
- concentration risk for the top repeated pattern

In plain English:

> the scoreboard still counts wins and fouls,
> but the campaign report now also checks whether the class has been taking one test thirty times.

## Explicit non-goals

This contract does **not** authorize:

- a public recommendation dashboard
- a WebUI recommendation management page
- a public API monitoring endpoint
- launch wording in README / proof / FAQ

## Evidence anchors

- [`docs/roadmaps/dealwatch-recommendation-readiness-gate.md`](./dealwatch-recommendation-readiness-gate.md)
- [`docs/roadmaps/dealwatch-recommendation-shadow-governance.md`](./dealwatch-recommendation-shadow-governance.md)
- [`docs/roadmaps/dealwatch-recommendation-adjudication-feedback.md`](./dealwatch-recommendation-adjudication-feedback.md)
- [`src/dealwatch/application/services.py`](../../src/dealwatch/application/services.py)
- [`tests/test_product_service.py`](../../tests/test_product_service.py)

## Current phase summary

Prompt 8 monitoring means:

> recommendation shadow finally has a scoreboard

It does **not** mean:

> recommendation has earned a seat on the public product surface
