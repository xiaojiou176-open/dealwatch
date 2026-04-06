# DealWatch Closeout Overlay (2026-04-06)

## Purpose

This is the dated SSOT for the April 6 hard-cut.

Use this file when you need the exact split between:

- what the old local history used to look like
- what the rebuilt canonical repo now looks like
- what GitHub remote truth says after cutover
- what still remains on the external platform side

## One-Line Summary

> The old local mainline was preserved into a private archive, a new clean public canonical repo took over `xiaojiou176/dealwatch`, the public release surface was reduced to a single reissued `v0.1.2`, and the remaining blockers are now external Render `404` plus GitHub UI-only social preview confirmation.

## Archive / Context Says

The old canonical repo had:

- 24 commits on `main`
- a merge commit (`88bd6dd`)
- multiple review/process-noise commits such as `sign off` / `review-fix`
- stale closeout docs and stale public-entry narratives

That history is preserved for rollback and forensic reference, but it is no longer the public canonical history.

## Repo-Local Says

The rebuilt canonical repo now has:

- `<= 8` semantic commits on `main`
- no merge commits
- no `sign off` / review-noise commits
- re-landed governance gates, hook path, and closeout ledgers
- one canonical public release surface: `v0.1.2`

The rebuilt repo still does **not** claim:

- hosted Render success
- social preview UI confirmation

## Git Remote Says

Current Git/GitHub truth after cutover:

| Field | Value |
| --- | --- |
| canonical repo | `xiaojiou176/dealwatch` |
| archive repo | `xiaojiou176/dealwatch-archive-20260406` |
| archive visibility | private |
| remote heads on canonical repo | `main` only |
| open PRs | `0` |
| open issues | `0` |
| open Dependabot alerts | `0` |
| open code-scanning alerts | `0` |
| open secret-scanning alerts | `0` |
| public release set | `v0.1.2` only |

## GitHub / Platform Says

The rebuilt canonical repo has:

- public visibility
- Discussions enabled
- Pages configured for workflow publishing
- labels restored
- topics restored
- secret scanning enabled
- secret scanning push protection enabled
- private vulnerability reporting enabled
- branch protection restored with 9 required checks

## Live / Public Says

Fresh public probes after cutover say:

- `https://github.com/xiaojiou176/dealwatch` is reachable
- `https://xiaojiou176.github.io/dealwatch/` is reachable
- `https://xiaojiou176.github.io/dealwatch/proof.html` is reachable
- `https://xiaojiou176.github.io/dealwatch/faq.html` is reachable
- `https://dealwatch-api.onrender.com/api/health` still returns `404`
- `https://dealwatch-webui.onrender.com/` still returns `404`

## Four-Ledger Split

| Ledger | Current call |
| --- | --- |
| repo-side engineering | clean after hard-cut |
| delivery landed | clean once new canonical repo is pushed and verified |
| git closure | clean once archive/private + new canonical + branch protection + zero open PRs all hold |
| external blocker | Render `404` and social preview UI-only confirmation |
