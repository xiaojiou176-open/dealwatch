# DealWatch Recommendation Shadow Operations

## Purpose

This runbook defines the smallest honest maintainer workflow for Prompt 8:

- seed or refresh an internal-only replay campaign
- inspect which recommendation shadow artifacts still need review
- record a maintainer adjudication
- confirm that the review ledger, shadow artifact, and monitoring summary all moved together

Use this file when the practical question is:

> "How do I actually review one recommendation shadow call without pretending the broader recommendation roadmap is already ready just because Compare Preview advisory v1 now exists?"

## Status

> **Status:** active internal-only Prompt 8 runbook.  
> This is a maintainer/operator workflow that continues behind the shipped Compare Preview advisory slice; it is not a broader launch brief.

## Boundary

This workflow is intentionally narrow.

It is for:

- maintainers
- internal operators
- repo-local replay / adjudication work

It is not for:

- public UI feedback
- public API review endpoints
- end-user voting
- launch claims

## Workspace model

The current Prompt 8 continuation uses a repo-local runtime-evaluation workspace so the experiment does not have to pretend recommendation is already public, while still letting us ingest non-seeded repo-local evidence.

Default workspace:

```text
.runtime-cache/operator/recommendation-evaluation-v1/
  recommendation-evaluation.db
  runs/
    compare-evidence/
      <artifact-id>/
      _shadow-monitoring/
```

Think of this like a practice room:

- the product runtime path stays protected
- the experiment still writes real repo-local artifacts
- maintainers can rerun and inspect the same dossier inputs without public drift

Current queue truth in this default workspace:

- `13 total` artifacts
- `11` replay-included shadow artifacts
- `5 issued`, `6 abstained`, `2 invalid_or_skipped`
- `11 reviewed`, `0 pending`
- disagreement buckets now read: `abstain_when_should_speak: 3`, `speak_when_should_abstain: 3`
- native compare-origin breadth is currently ceiling-bound: `30` available rows collapse to `1` unique pattern, so `29` repeats are dropped instead of being counted as new breadth

## Step 1 — Seed or refresh the replay campaign

Use the campaign script to create the first small deterministic corpus or to refresh the report over an existing workspace.

The current full Prompt 8 mixed corpus command is:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_recommendation_evaluation_campaign.py \
  --workspace .runtime-cache/operator/recommendation-evaluation-v1 \
  --reset-workspace \
  --seed-fixture-corpus \
  --import-runtime-corpus \
  --harvest-native-compare-origin \
  --native-compare-repeat-budget 0 \
  --runtime-runs-dir .runtime-cache/runs
```

Why `--native-compare-repeat-budget 0` matters:

- Prompt 8 is trying to measure breadth honestly
- the current native compare-origin runtime pool is still dominated by one repeated smoke-test pears pair
- this flag keeps one representative case per detected pattern instead of letting repeated history masquerade as broader coverage

Use the runtime-only path when you explicitly want to skip the seeded starter lab:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_recommendation_evaluation_campaign.py \
  --workspace .runtime-cache/operator/recommendation-evaluation-v1 \
  --reset-workspace \
  --import-runtime-corpus \
  --runtime-runs-dir .runtime-cache/runs
```

Seed the old deterministic starter batch only when you explicitly want a fixture-only lab:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_recommendation_evaluation_campaign.py \
  --workspace .runtime-cache/operator/recommendation-evaluation-v1 \
  --reset-workspace \
  --seed-fixture-corpus
```

Refresh an existing workspace without importing more source artifacts:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_recommendation_evaluation_campaign.py \
  --workspace .runtime-cache/operator/recommendation-evaluation-v1
```

What this writes:

- `runs/compare-evidence/<artifact-id>/compare_evidence.json`
- `runs/compare-evidence/<artifact-id>/recommendation_shadow.json`
- `runs/compare-evidence/_shadow-monitoring/recommendation_replay_manifest.json`
- `runs/compare-evidence/_shadow-monitoring/recommendation_shadow_summary.json`
- `runs/compare-evidence/_shadow-monitoring/recommendation_replay_campaign_v1.json`
- `runs/compare-evidence/_shadow-monitoring/recommendation_replay_campaign_v1.md`

## Step 2 — List pending internal reviews

Use the review script in discovery mode before recording a judgment.

```bash
PYTHONPATH=src .venv/bin/python scripts/review_recommendation_shadow.py \
  --workspace .runtime-cache/operator/recommendation-evaluation-v1 \
  --list-pending
```

If you want a maintainer-readable queue snapshot instead of raw JSON, add `--format text`:

```bash
PYTHONPATH=src .venv/bin/python scripts/review_recommendation_shadow.py \
  --workspace .runtime-cache/operator/recommendation-evaluation-v1 \
  --list-pending \
  --format text
```

The output tells you:

- which artifact ids are still `pending_internal_review`
- which `surface_anchor` each case came from
- which `review_seed_suggestion` is the safest starting judgment for that case
- what the current internal verdict is
- where the shadow JSON/HTML file lives
- what the current queue snapshot looks like (`reviewed`, `pending`, `issued`, `abstained`)
- which disagreement buckets are already accumulating and which are still absent

For the current canonical workspace, the honest first reading is:

- `reviewed = 11`
- `pending = 0`
- `issued = 5`
- `abstained = 6`
- disagreement buckets are already explicit and fully queue-closed: `abstain_when_should_speak = 3`, `speak_when_should_abstain = 3`

## Step 3 — Inspect the artifact you want to grade

For one chosen `artifact_id`, inspect these files:

- `runs/compare-evidence/<artifact-id>/compare_evidence.html`
- `runs/compare-evidence/<artifact-id>/recommendation_shadow.html`
- `runs/compare-evidence/_shadow-monitoring/recommendation_replay_campaign_v1.md`

In plain English:

- the compare evidence file is the case file
- the shadow file is the answer sheet
- the campaign report is the class scoreboard

## Step 4 — Record the review verdict

Example: record a false positive override against one artifact.

```bash
PYTHONPATH=src .venv/bin/python scripts/review_recommendation_shadow.py \
  --workspace .runtime-cache/operator/recommendation-evaluation-v1 \
  --artifact-id <artifact-id> \
  --reviewer maintainer \
  --decision overridden \
  --reason-code false_positive \
  --outcome-category false_positive \
  --expected-verdict recheck_later \
  --actual-verdict wait \
  --observed-outcome "Later deterministic evidence favored a more cautious recheck_later call." \
  --notes "The original internal wait verdict was too aggressive for this evidence package." \
  --follow-up-action "Keep collecting stronger timing evidence before future launch review."
```

Optional evidence refs can be attached with repeated `--evidence-ref` flags:

```bash
--evidence-ref "post_review_outcome|Later observed outcome|review.observed_outcome"
```

When you record a disagreement bucket such as `false_positive`, `false_negative`, `abstain_when_should_speak`, or `speak_when_should_abstain`, the script now expects a deeper adjudication packet:

- `--expected-verdict`
- `--actual-verdict`
- at least one of `--notes`, `--follow-up-action`, or `--evidence-ref`

That rule is there to keep the review ledger reusable later. In plain English: if the maintainer is saying "the shadow was wrong," the record now has to explain what the better call was and what evidence justified that correction.

If you want the command to print a maintainer-readable status summary instead of raw JSON, add `--format text`:

```bash
PYTHONPATH=src .venv/bin/python scripts/review_recommendation_shadow.py \
  --workspace .runtime-cache/operator/recommendation-evaluation-v1 \
  --artifact-id <artifact-id> \
  --reviewer maintainer \
  --decision overridden \
  --reason-code false_positive \
  --outcome-category false_positive \
  --expected-verdict recheck_later \
  --actual-verdict wait \
  --observed-outcome "Later deterministic evidence favored a more cautious recheck_later call." \
  --notes "The original internal wait verdict was too aggressive for this evidence package." \
  --follow-up-action "Keep collecting stronger timing evidence before future launch review." \
  --format text
```

If you prefer `uv`, the same commands may be run as `PYTHONPATH=src uv run python ...` inside the repo root.

Supported wrong-call vocabulary stays aligned with the Prompt 6 contracts:

- `false_positive`
- `false_negative`
- `abstain_when_should_speak`
- `speak_when_should_abstain`
- `correct_verdict`
- `correct_abstention`

For the current Prompt 8 continuation, `speak_when_should_abstain` is especially important:

> the shadow said something on a smoke-triggered runtime case
> the maintainer judged that this case should have stayed quiet instead

## Step 5 — Confirm that the loop really moved

After a successful review write, confirm all three layers changed:

1. `runs/compare-evidence/recommendation_shadow_reviews.ndjson`
2. `runs/compare-evidence/<artifact-id>/recommendation_shadow.json`
3. `runs/compare-evidence/_shadow-monitoring/recommendation_shadow_summary.json`

What should be true now:

- the ledger has a new ndjson row
- the shadow artifact `review.state` is no longer `pending_internal_review`
- the monitoring summary updates `review_state_buckets` and, when applicable, `disagreement_buckets`
- the text summary makes the current review debt easy to read without opening JSON by hand
- disagreement cases now carry enough verdict-correction detail to be useful in later calibration review

## Minimum honest reading rule

This workflow proves:

- the repo can seed a recommendation replay corpus
- the repo can harvest a small native compare-origin corpus from runtime-discovered compare pairs
- the repo can now report when the available native compare-origin pool is still one repeated pattern instead of broader coverage
- the repo can import non-seeded runtime task/group patterns into the same evaluation workspace
- a maintainer can record a review
- replay and monitoring can read that review back out

This workflow does **not** prove:

- public recommendation launch readiness
- real-world calibration quality
- enough historical evidence for `buy_now`

It also does **not** mean "only external blockers remain."

With the current workspace now at `11 reviewed`, `0 pending`, the immediate repo-local review debt for this corpus is closed. The next honest blocker is broader native compare-origin diversity, not another pass over the same repeated pears family.

## Troubleshooting

### No pending reviews appear

Likely reasons:

- the workspace has not been seeded or imported yet
- only skipped/invalid artifacts exist
- all included artifacts were already reviewed

Fix:

1. rerun the campaign with `--import-runtime-corpus` or `--seed-fixture-corpus`, or
2. inspect `recommendation_replay_manifest.json` for `skip_reason`

### The review command says the artifact is missing

The chosen `artifact_id` must exist under the same workspace that you passed to the review command.

Fix:

- double-check the `--workspace`
- rerun `--list-pending`

### Monitoring did not change

The review command itself refreshes replay and monitoring artifacts after writing the ledger row.

If the summary still looks stale:

1. rerun the campaign refresh command without `--seed-fixture-corpus`
2. inspect `recommendation_shadow_reviews.ndjson`

## Current phase summary

Prompt 8 operations mean:

> DealWatch can now run a mixed internal recommendation campaign, measure native source diversity honestly, and record maintainer adjudication in a real repo-local loop.

It still means:

> recommendation remains internal-only and blocked from public launch discussion until the evidence base is much stronger.
