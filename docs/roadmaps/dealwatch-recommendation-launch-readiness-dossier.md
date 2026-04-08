# DealWatch Recommendation Launch Readiness Dossier

## Purpose

This dossier records the first formal Prompt 7 answer to the question:

> "Why is DealWatch recommendation still not ready for broader public launch, and what evidence would have to improve before a future expansion discussion is honest?"

In plain English:

- Prompt 5 gave DealWatch governed internal shadow artifacts
- Prompt 6 gave the repo replay, adjudication, and monitoring contracts
- Prompt 7 turned those contracts into a real internal evidence packet with a runnable replay campaign, a maintainer review workflow, and a first honest launch-readiness verdict
- Prompt 8 hardens that lane by measuring source diversity directly and by refusing to count repeated history for the same pattern as if it were broader recommendation coverage

This is a launch-readiness dossier.

It is **not**:

- a launch proposal
- a marketing page
- a claim that every recommendation surface is now public

## Status

> **Status:** active internal-only dossier for the inherited Prompt 8 recommendation lane, refreshed during total closeout `Prompt 1`, and now interpreted as the evidence bar for broader expansion beyond the shipped Compare Preview advisory v1.
> Prompt mapping truth: current total closeout program `Prompt 1 — Recommendation Final Repo-Side Closeout` is refreshing the inherited Prompt 8 continuation wave after the earlier Prompt 7 evaluation campaign, and that evidence lane still sits before historical execution-program `Prompt 9 — Final closeout + execution plan v2`.
> These labels describe one sequence, not competing truth sources.

## Current Evidence Snapshot

The current Prompt 8 repo-local breadth-hardening run lives under:

```text
.runtime-cache/operator/recommendation-evaluation-v1/runs/compare-evidence/_shadow-monitoring/
  recommendation_replay_manifest.json
  recommendation_shadow_summary.json
  recommendation_shadow_summary.html
  recommendation_replay_campaign_v1.json
  recommendation_replay_campaign_v1.md
```

The current Prompt 8 mixed corpus now combines:

- `2` seeded compare-origin starter cases
- `1` breadth-selected native compare-origin compare-preview case
- `3` non-seeded runtime-derived watch-group cases
- `5` non-seeded runtime-derived watch-task cases

That smaller native compare-origin slice does **not** mean the runtime pool shrank.

It means Prompt 8 now measures the pool honestly:

- `30` native compare-origin candidates were available in `.runtime-cache/runs`
- those `30` rows collapsed to only `1` unique pattern
- the same `ranch99` + `weee` pears pair accounted for `100%` of the available native compare-origin pool
- Prompt 8 therefore kept `1` representative native compare-origin case and dropped `29` repeated-depth copies from the fresh replay batch

The current breadth-hardening snapshot therefore shows:

| Evidence point | Current repo-local result | Why it matters |
| --- | --- | --- |
| `total replay items` | `13` | the fresh Prompt 8 workspace now carries a smaller but more honest mixed corpus instead of padding the replay set with repeated native depth |
| `replay included count` | `11` | eleven shadow artifacts were valid and replayable in the fresh breadth-first batch |
| `issued verdict count` | `5` | the shadow lane still issues governed internal verdicts after the native slice was de-duplicated |
| `abstention count` | `6` | most runtime-derived artifacts still abstain, which remains the safer current posture |
| `invalid_or_skipped_count` | `2` | the replay layer still keeps malformed / missing artifacts visible instead of hiding them |
| `reviewed_count` | `11` | the current v1 workspace has now adjudicated every replay-included artifact instead of leaving the queue half-open |
| `review_pending_count` | `0` | repo-local review debt is no longer the current stop line for this workspace |
| `review_state_buckets` | `confirmed = 5`, `overridden = 6` | the queue is now fully closed for the current corpus, and disagreement is visible as explicit overrides instead of unresolved debt |
| `disagreement_buckets` | `abstain_when_should_speak = 3`, `speak_when_should_abstain = 3` | the workspace now carries a deeper disagreement map than a starter packet, but still only across a narrow corpus |
| `native available case count` | `30` | proves the runtime history is deeper than the selected replay slice |
| `native unique pattern count` | `1` | proves the apparent native growth is still one repeated pattern, not broader product coverage |
| `native top repeated pattern share` | `1.0` | the concentration risk is effectively total: the same pattern owns the full current native pool |
| `native dropped repeat count` | `29` | Prompt 8 now refuses to treat repeated copies of the same smoke-test pair as if they added recommendation breadth |

Historical note:

> Prompt 7's earlier reviewed workspace remains useful inherited evidence.  
> Prompt 8 does not erase that history; it reruns the current workspace with a stricter breadth-first rule so the repo can distinguish "we reviewed a lot" from "we covered enough different situations."

## What Prompt 8 Proves

### 1. Replay is now runnable, not only described

DealWatch can now run a repo-local recommendation replay campaign and produce a machine-readable campaign report.

That matters because the repo can finally answer:

- how many items entered replay
- how many issued a verdict
- how many abstained
- how many were invalid or skipped

Think of this like moving from a lab protocol on paper to actually putting the first samples into the centrifuge.

### 2. Maintainer adjudication is now operational

DealWatch now has a repo-local maintainer workflow that can:

- list pending recommendation shadow artifacts
- record a review verdict against a chosen artifact
- update the shadow artifact, review ledger, replay manifest, and monitoring summary together

The current operator workflow is documented in:

- [`docs/runbooks/recommendation-shadow-operations.md`](../runbooks/recommendation-shadow-operations.md)

### 3. The repo can now measure source diversity instead of only row count

The campaign report is no longer limited to "how many artifacts existed."

It now also records:

- how many native compare-origin candidates were available
- how many unique patterns those candidates actually represent
- how many unique store pairs and source-url pair families exist
- how concentrated the top repeated pattern is
- how many repeated-depth rows were intentionally left out of the fresh replay batch

That matters because Prompt 8 is explicitly trying to stop a false comfort pattern:

> thirty copies of one smoke-test pears pair are still one question asked thirty times

### 4. Monitoring now carries real data, not only empty schema

The monitoring summary is no longer just "a file that could exist someday."

It now reports a real Prompt 8 snapshot with:

- issued vs abstained split
- clean intake counts across the mixed seeded + native compare-origin + runtime-derived corpus
- reviewed-state split (`confirmed`, `overridden`, `pending_internal_review`)
- disagreement buckets for `speak_when_should_abstain` and `abstain_when_should_speak` in the fresh breadth-hardening slice

### 5. Maintainer adjudication is now easier to read, but still not launch evidence

Prompt 7 now gives maintainers two different ways to read the same internal lane:

- raw JSON for automation and artifact chaining
- text summaries for queue triage, readiness snapshots, and disagreement-bucket reading

Disagreement reviews are also expected to carry a deeper packet now:

- what the verdict should have been
- what verdict was actually recorded
- at least one supporting note, follow-up action, or evidence anchor

That makes the internal review log more reusable for future calibration work.

It does **not** upgrade the recommendation lane into public-launch evidence.

This is like improving the judge's scorecard in a sparring gym:

- the notes become clearer
- the correction history becomes easier to reuse
- but you still have not proven championship readiness

## What Prompt 8 Still Does Not Prove

Prompt 8 does **not** prove:

- long-range recommendation calibration
- live shopper behavior coverage
- public wording safety for user-facing recommendation
- enough adjudication depth to trust the pattern of wrong calls
- any honest basis for launching `Buy now / Wait / Re-check later` on the public product surface

In plain English:

> the repo now has a training room with scoreboards and judge notes
> it still does not have enough match history to put the fighter into a title bout

## Why Recommendation Is Still Blocked From Public Launch

### 1. The current corpus is more honest, but it is still narrow and still reconstructed

The current Prompt 8 continuation no longer hides behind raw native row count.

That is real progress.

But the current Prompt 8 corpus is still:

- partly seeded from repo-owned compare fixtures
- partly harvested from runtime-discovered native compare-origin pairs
- partly reconstructed from runtime task/group summaries
- still not the same thing as a broad native compare-preview history lane
- still narrow in source diversity because the current native compare-origin runtime pool collapses to a single repeated smoke-test pears pair
- explicitly breadth-first, which is more honest, but still proves that the current repo-local ceiling is a data-shape problem rather than a tooling problem

It is still not the same as a broad accumulated compare-origin recommendation history.

### 2. The current disagreement evidence is still too thin

The current v1 workspace no longer carries repo-local review debt: it now sits at `reviewed_count = 11` and `review_pending_count = 0`.

That does **not** mean the launch blocker disappeared.

It means the stop line moved forward:

- Prompt 7 already proved the adjudication loop can work
- Prompt 8 proved that the native compare-origin pool itself is still concentrated
- closing the queue did not magically create broader product coverage; it only removed one repo-local excuse for staying vague

It is still not enough to answer:

- whether the current repeated `speak_when_should_abstain` pattern is a smoke-test-only phenomenon or a broader product behavior
- whether `abstain_when_should_speak` stays stable once the corpus is no longer dominated by runtime-summary reconstruction
- whether any future `false_positive` cases show up outside the seeded starter lane
- how abstention quality changes across a larger replay set
- whether the newly clearer review packets converge toward stable corrective guidance across multiple maintainer passes
- whether the native compare-origin lane still says the same thing once the runtime pool stops being one repeated pears pair

### 3. The current lane is still reconstructed from runtime summaries, not native compare-origin truth

The current safest recommendation anchor still remains Compare Preview / compare evidence.

The new runtime lane is useful because it gives us non-seeded evidence.

The newly harvested native compare-origin lane is also useful because it proves the repo can re-run compare-origin evidence from runtime-discovered pairs without inventing a second recommendation system.

But that is still not the same as the broad compare-origin recommendation history we would want before launch.

The repo is still not proving public purchase timing behavior across:

- Watch Group maturity
- Task history maturity
- cross-surface wording safety

### 4. Public silence still matters

Prompt 8 strengthens the internal lane that still governs everything beyond the shipped Compare Preview advisory slice.

It does **not** authorize:

- a task/group recommendation UI card
- recommendation API fields outside compare preview / compare evidence review
- a recommendation MCP tool
- README / proof / FAQ wording that implies broader recommendation parity is shipped

## Current stop line

The honest Prompt 8 stop line is no longer "maybe the repo just needs one more local rerun."

The repo already proved the current native lane is at `single_pattern_runtime_ceiling`.

What remains is also now explicit:

- the current v1 workspace no longer carries repo-local review debt (`11 reviewed`, `0 pending`)
- disagreement evidence is deeper than before, but it still only covers two disagreement classes across a concentrated corpus
- seeded, runtime-derived, and harvested native compare-origin artifacts are still internal experiment truth, not public product maturity

This lane becomes "mostly real external blockers" only after both of these are true:

1. the repo-local review debt is adjudicated or intentionally superseded by a broader rerun under the same governance contract
2. further breadth growth genuinely requires new live compare-origin families beyond the current repeated pears pair

For the current v1 workspace, those two conditions now hold. The honest next blocker is therefore not missing review plumbing, but the lack of broader native compare-origin families beyond the repeated pears pair.

## Current Launch Verdict

### Compare Preview public advisory v1

**Verdict: SHIPPED**

Recommendation now exists as a narrow local Compare Preview advisory surface, intentionally limited to conservative compare-stage verdicts and compare evidence review.

### Broader launch

**Verdict: NOT READY**

Recommendation must remain blocked from broader public product surfaces in this phase.

### Internal experimentation

**Verdict: READY FOR FURTHER INTERNAL EVALUATION**

Prompt 8 now proves that the repo can:

- import a non-seeded runtime corpus
- harvest native compare-origin cases breadth-first instead of pretending repeated depth is broader coverage
- measure and report source diversity, concentration risk, and the current native ceiling
- keep the non-seeded runtime corpus in the same internal experiment without relabeling it as native launch evidence
- write an evidence-backed launch-readiness dossier that now names the native diversity ceiling explicitly

That is enough for internal evaluation continuity.

It is not enough for broader launch.

## Minimum Gates Before Any Future Broader-Launch Prompt

The next future broader-launch discussion should stay blocked until the repo can show all of the following:

1. a materially larger and more diverse replay corpus than the current fresh Prompt 8 `2 seeded + 1 breadth-selected native compare-origin + 8 runtime-derived` replay batch, **and** a native runtime pool that is no longer `30` copies of the same pattern
2. repeated maintainer adjudication over time once the corpus contains more than one meaningful native compare-origin pattern family
3. disagreement patterns across multiple classes, not only the current `false_positive`, `speak_when_should_abstain`, and `abstain_when_should_speak` starter modes
4. stronger recommendation-specific calibration evidence rooted in deeper native compare-origin history instead of only runtime-summary reconstruction
5. unchanged public silence until the explicit launch decision is reopened

## What Evidence Would Justify The Next Expansion Prompt

The next broader-launch discussion only becomes worth opening once Prompt 8 evidence improves in these concrete ways:

- replay is driven by a broader repo-local evidence corpus, not mainly by seeded samples, runtime-summary reconstruction, and one repeated native pair
- the native compare-origin pool shows more than the current `1` unique pattern / `1` unique store pair / `1` unique source-url pair family ceiling
- reviewed artifacts grow on top of that broader corpus instead of only re-grading repeated copies of the same smoke-test pair
- disagreement buckets keep showing stable patterns outside the current `false_positive`, `speak_when_should_abstain`, and `abstain_when_should_speak` starter modes
- deeper disagreement packets keep accumulating over time instead of appearing only in a single review sweep
- abstention remains honest under larger replay volume
- public silence checks still pass after the internal tooling grows

## Current Phase Summary

The honest Prompt 8 posture is:

> DealWatch recommendation now has a runnable mixed replay corpus, a breadth-first native compare-origin selector, and a launch-readiness dossier that can formally prove when the current repo-local native pool has hit a diversity ceiling.

It is still true that:

> recommendation has not yet earned a broader public launch discussion beyond Compare Preview advisory v1.
