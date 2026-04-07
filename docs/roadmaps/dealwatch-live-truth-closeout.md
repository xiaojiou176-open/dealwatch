# DealWatch Live Truth Closeout

## Purpose

This ledger records what the outside world can reach after the April 6 hard-cut.

In plain English:

- the rebuilt public repo is now the canonical public entry
- GitHub Pages still serves the repo-owned public proof surface
- Render still does not prove that the blueprint is live
- this file is about **reachable public surfaces**, not repo-owned engineering claims

Use this reading order so the current live truth stays separate from the dated hard-cut snapshot:

- this file = current reachable public/live truth
- [`docs/roadmaps/dealwatch-repo-side-closeout.md`](./dealwatch-repo-side-closeout.md) = current repo-owned truth
- [`docs/roadmaps/dealwatch-closeout-overlay-2026-04-06.md`](./dealwatch-closeout-overlay-2026-04-06.md) = dated audit snapshot

For the full hard-cut split, use the dated overlay:

- [`docs/roadmaps/dealwatch-closeout-overlay-2026-04-06.md`](./dealwatch-closeout-overlay-2026-04-06.md)

## Current Live/Public Verdict

> **Live/public verdict:** the rebuilt canonical GitHub repository, GitHub Pages surfaces, and the
> GitHub social preview image are all reachable from fresh evidence, while the Render API and WebUI
> still return `404`; PyPI no longer resolves the `dealwatch` JSON API, so the remaining blockers
> stay on the external platform side.

## Fresh Live/Public Matrix

| Surface | Fresh live truth after hard-cut | Status |
| --- | --- | --- |
| Canonical GitHub repo | `https://github.com/xiaojiou176-open/dealwatch` is reachable | Pass |
| GitHub Pages root | `https://xiaojiou176-open.github.io/dealwatch/` returns `200` | Pass |
| GitHub Pages proof | `https://xiaojiou176-open.github.io/dealwatch/proof.html` returns `200` | Pass |
| GitHub Pages FAQ | `https://xiaojiou176-open.github.io/dealwatch/faq.html` returns `200` | Pass |
| Old public repo entry | no longer serves the retired old public repo | Pass |
| Render API | `https://dealwatch-api.onrender.com/api/health` returns `404` | Blocked |
| Render WebUI | `https://dealwatch-webui.onrender.com/` returns `404` | Blocked |
| GitHub social preview selection | GraphQL now reports `usesCustomOpenGraphImage=true` and returns the custom repository image URL | Pass |
| PyPI package surface | `https://pypi.org/pypi/dealwatch/json` now returns `404`; the browser-facing project URL still falls behind a generic client-challenge page and does not provide project-specific proof | Cleared at authoritative API layer |

## Exact Remaining External Blockers

1. Render API still returns `404`.
2. Render WebUI still returns `404`.

## What This File Does Not Claim

- it does not claim hosted runtime success
- it does not claim every GitHub UI-only setting can be controlled from repo files alone
- it does not claim archive-object search caches have fully expired on GitHub’s side unless directly re-proven

## Related Ledgers

- [`docs/roadmaps/dealwatch-closeout-overlay-2026-04-06.md`](./dealwatch-closeout-overlay-2026-04-06.md)
- [`docs/roadmaps/dealwatch-repo-side-closeout.md`](./dealwatch-repo-side-closeout.md)
