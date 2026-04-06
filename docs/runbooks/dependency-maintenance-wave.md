# Dependency Maintenance Wave

## Why this exists

DealWatch keeps dependency upgrades in a **separate maintenance wave** so product closure, runtime hardening, or public-surface work does not get buried under a burst of unrelated automation PRs.

In plain language:

- product / closure rounds answer "is the repo truthful and shippable right now?"
- dependency waves answer "which upgrades should we absorb next, together, on purpose?"

Those are different jobs and should not share the same branch pile.

## The repository rule

1. Dependabot version-update PRs are treated as **maintenance intake**, not as part of product or closure integration by default.
2. The repository groups Dependabot PRs by ecosystem so the default wave is small and reviewable.
3. During a release, closure, or governance-hardening round, unrelated automation PRs should be closed or postponed instead of being mixed into the active integration branch.
4. Security advisories are the exception:
   - fix immediately if the default branch is actually vulnerable
   - dismiss with a recorded reason if the alert is already fixed, dev-only, or outside the live runtime path

## Expected cadence

- Dependabot is scheduled weekly in `America/Los_Angeles`.
- The goal is one grouped PR per ecosystem wave:
  - backend Python / `uv`
  - frontend npm
  - GitHub Actions
  - Docker

## Triage order

1. **Security first**
   - Is the default branch actually vulnerable?
   - If yes, fix or patch first.
   - If no, dismiss with a precise rationale.

2. **Runtime-facing upgrades next**
   - framework/runtime dependencies
   - infra/toolchain dependencies that affect CI, builds, or deploys

3. **Tooling and polish last**
   - dev-only packages
   - non-critical UI tooling

## What not to do

- Do not merge a burst of unrelated Dependabot PRs into a closure round just to make the queue look smaller.
- Do not leave dozens of open automation PRs sitting beside a repo-closure branch and still call the collaboration surface "clean".
- Do not dismiss security alerts without a concrete reason tied to code, runtime path, or patched default-branch state.

## Minimal maintenance-wave checklist

Before merging a grouped dependency PR:

```bash
./scripts/test.sh -q
python3 scripts/verify_public_surface.py
python3 scripts/verify_site_surface.py
python3 scripts/verify_docs_contract.py
python3 scripts/verify_root_allowlist.py
python3 scripts/verify_tracked_artifacts.py
python3 scripts/verify_runtime_diagnostics.py
python3 scripts/verify_english_boundary.py
```

If the wave changes public-facing assets or UI:

```bash
python3 scripts/verify_social_preview_asset.py
python3 scripts/verify_social_preview_matrix.py
```

## Related files

- `.github/dependabot.yml`
- `CONTRIBUTING.md`
- `scripts/verify_remote_github_state.py`
- `scripts/print_remote_repo_settings_checklist.py`
