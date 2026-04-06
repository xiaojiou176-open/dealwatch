# DealWatch Live Truth Closeout

## Purpose

This ledger records what the outside world can reach after the April 6 hard-cut.

In plain English:

- the rebuilt public repo is now the canonical public entry
- GitHub Pages still serves the repo-owned public proof surface
- Render still does not prove that the blueprint is live
- this file is about **reachable public surfaces**, not repo-owned engineering claims

For the full hard-cut split, use the dated overlay:

- [`docs/roadmaps/dealwatch-closeout-overlay-2026-04-06.md`](./dealwatch-closeout-overlay-2026-04-06.md)

## Current Live/Public Verdict

> **Live/public verdict:** the rebuilt canonical GitHub repository and GitHub Pages surfaces are reachable, while the Render API and WebUI still return `404`, so the remaining blockers stay on the external platform side.

## Fresh Live/Public Matrix

| Surface | Fresh live truth after hard-cut | Status |
| --- | --- | --- |
| Canonical GitHub repo | `https://github.com/xiaojiou176/dealwatch` is reachable | Pass |
| GitHub Pages root | `https://xiaojiou176.github.io/dealwatch/` returns `200` | Pass |
| GitHub Pages proof | `https://xiaojiou176.github.io/dealwatch/proof.html` returns `200` | Pass |
| GitHub Pages FAQ | `https://xiaojiou176.github.io/dealwatch/faq.html` returns `200` | Pass |
| Old public repo entry | no longer serves the retired old public repo | Pass |
| Render API | `https://dealwatch-api.onrender.com/api/health` returns `404` | Blocked |
| Render WebUI | `https://dealwatch-webui.onrender.com/` returns `404` | Blocked |
| GitHub social preview selection | still requires GitHub UI confirmation | External/UI-only |

## Exact Remaining External Blockers

1. Render API still returns `404`.
2. Render WebUI still returns `404`.
3. GitHub social preview selection still requires UI confirmation.

## What This File Does Not Claim

- it does not claim hosted runtime success
- it does not claim GitHub UI-only settings were auto-verified
- it does not claim archive-object search caches have fully expired on GitHub’s side unless directly re-proven

## Related Ledgers

- [`docs/roadmaps/dealwatch-closeout-overlay-2026-04-06.md`](./dealwatch-closeout-overlay-2026-04-06.md)
- [`docs/roadmaps/dealwatch-repo-side-closeout.md`](./dealwatch-repo-side-closeout.md)
