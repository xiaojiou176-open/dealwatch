# DealWatch Repo-Side Closeout

## Purpose

This ledger records what the rebuilt canonical repository proves after the April 6 hard-cut and the
later repo-side convergence that followed on `main`.

In plain English:

- the public canonical repo was rebuilt onto a clean linear history
- the old canonical repo is no longer the public source of truth, no online archive repo remains, and the temporary local hard-cut backups were deleted after verification
- this file only talks about **repo-owned truth**
- live Render status still belongs to the separate live-truth ledger

Use this reading order so the current truth stays short and the historical snapshots stay useful
without pretending to be today's state:

- this file = current repo-owned truth
- [`docs/roadmaps/dealwatch-live-truth-closeout.md`](./dealwatch-live-truth-closeout.md) = current reachable public/live truth
- [`docs/roadmaps/dealwatch-closeout-overlay-2026-04-06.md`](./dealwatch-closeout-overlay-2026-04-06.md) = dated hard-cut audit snapshot

Use the dated overlay when you need the full split between archive truth, rebuilt repo truth, GitHub
remote truth, and the original hard-cut-era external blockers:

- [`docs/roadmaps/dealwatch-closeout-overlay-2026-04-06.md`](./dealwatch-closeout-overlay-2026-04-06.md)

## Current Repo-Side Verdict

> **Repo-side verdict:** the canonical public repo now lives on a clean linear `main` with `11`
> current commits, no merge commits, current governance gates re-landed, and a single canonical
> public release `v0.1.2`.

That is the honest call because:

- the rebuilt repo preserves the current product tree while discarding the old process-noise history
- the rebuilt repo keeps the current public entry `xiaojiou176-open/dealwatch`
- the old public repo was retired and the temporary archive repo plus local hard-cut backups were deleted after verification
- repo-owned governance gates, hook install path, and closeout ledgers were re-landed on the clean history
- later repo-side convergence continued on the same clean linear branch instead of reintroducing merge churn

## Current Repo-Side Snapshot

| Field | Current value |
| --- | --- |
| Canonical repo | `xiaojiou176-open/dealwatch` |
| Default branch | `main` |
| Current `main` commit count | `11` |
| History shape | linear, no merge commits |
| Current head | `28b4fd1` |
| Current public release set | `v0.1.2` only |
| Old repo role | no live repo-owned archive remains; truth is preserved in the dated closeout ledgers |
| Open PRs | `0` |
| Open issues | `0` |
| Open Dependabot alerts | `0` |
| Open code-scanning alerts | `0` |
| Open secret-scanning alerts | `0` |

## History Shape

The April 6 hard-cut snapshot reduced the rebuilt canonical history to 8 semantic commits. That
still matters as an audit fact, but it is no longer the current head shape. The current linear
`main` now carries 11 semantic commits:

1. `7bff236` = `feat(core): establish compare-first runtime foundation`
2. `b9e3c29` = `feat(public): publish the static frontdoor and proof surfaces`
3. `3ebbb5b` = `feat(builder): add read-only builder distribution surfaces`
4. `0062cc4` = `chore(governance): add repository guardrails and operator verifiers`
5. `fadd79b` = `fix(security): scrub host paths and tighten publish hygiene`
6. `616a118` = `fix(governance): add final security and workflow gates`
7. `8105421` = `chore(hooks): add tracked pre-push and install path`
8. `bc606cd` = `docs(closeout): sync repo-side, live truth, and dated hard-cut overlay`
9. `bd70a82` = `fix(public): sync org-owned canonical entry and closeout truth`
10. `b0fc2fd` = `docs(closeout): clear resolved PyPI blocker`
11. `28b4fd1` = `[codex] sharpen front door and thin orchestration spine (#7)`

The dated overlay remains the place to read the original `<= 8` hard-cut snapshot without treating
that older count as today's truth.

This history must stay free of:

- merge commits
- `sign off` / `review-fix` / PR-tip noise
- old repo identity drift
- stale closeout SHA / PR narratives

## P0 GitHub Configuration Re-landed

- branch protection on `main`
- Discussions enabled
- GitHub Pages configured for workflow publishing
- labels cloned back onto the rebuilt repo
- topics restored
- secret scanning and push protection enabled
- private vulnerability reporting enabled
- current gate set restored:
  - `test`
  - `frontend`
  - `governance`
  - `product-smoke`
  - `CodeQL`
  - `secret-hygiene`
  - `Dependency Review`
  - `workflow-hygiene`
  - `trivy`

## Release Surface Contract

The rebuilt canonical repo intentionally exposes only one public release:

- `v0.1.2`

Why:

- the older public tags `v0.1.0` and `v0.1.1` previously pointed at the same non-main orphan commit
- carrying those forward would re-pollute the rebuilt public release story
- the rebuilt public repo therefore reissues `v0.1.2` as the only canonical public release

The earlier release objects and legacy tag story are no longer kept as repo-owned rollback assets. Their existence is now preserved only by the dated closeout ledgers and the external platform residue those ledgers describe.

## Historical Snapshot Boundary

The following statements are historical hard-cut facts, not current-live facts:

- `<= 8` commits on `main`
- inactive social preview custom image
- any overlay wording that still speaks from the first rebuilt snapshot rather than the current
  `28b4fd1` head

Keep those facts inside the dated overlay and hard-cut audit trail. Do not reuse them as the
current repo-side verdict.

## Remaining Repo-Side vs External Split

- **repo-side engineering:** closed
- **Git/GitHub closure:** closed on the current canonical repo and GitHub surface
- **external blockers:** Render endpoints and GitHub social preview UI selection remain outside repo-owned control

## Related Ledgers

- [`docs/roadmaps/dealwatch-closeout-overlay-2026-04-06.md`](./dealwatch-closeout-overlay-2026-04-06.md)
- [`docs/roadmaps/dealwatch-live-truth-closeout.md`](./dealwatch-live-truth-closeout.md)
