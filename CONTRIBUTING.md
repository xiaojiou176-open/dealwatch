# Contributing

## Start With A Useful Contribution

If you want a high-signal first contribution, start with one of these:

- Improve the public product story with clearer screenshots, captions, or FAQs.
- Expand store coverage while preserving the compare-first intake flow.
- Strengthen task detail, effective price, or notification evidence in the UI.
- Tighten docs and verification so public claims keep matching product reality.

The goal is not to add noise. The best contribution is one that makes DealWatch easier to trust, use, or extend.

## Ground Rules

- Keep the repository product-first.
- Do not reintroduce `tracker`, `src/tracker`, or `var/` runtime paths.
- Do not track `.agents/`, `.agent/`, `.codex/`, `.claude/`, `.runtime-cache/`, `logs/`, `log/`, or `*.log`.
- Do not commit secrets, local databases, browser state, or runtime artifacts.
- Do not commit host-specific absolute paths, macOS temp-path literals, or personal sample markers into tracked text files.
- Do not introduce `killall`, `pkill`, broad `kill -9`, `osascript`, `System Events`, direct `process.kill(...)`, or direct `os.kill(...)`; DealWatch must stay on repo-owned browser/runtime cleanup entrypoints.
- Do not use `scripts/clean.py`; it is a hard-stop legacy entrypoint and no longer participates in DealWatch cleanup.
- Keep changes surgical.

## Local Setup

```bash
./scripts/bootstrap.sh
cp .env.example .env
python3 scripts/install_git_hooks.py
PYTHONPATH=src uv run python -m dealwatch maintenance --dry-run
pre-commit run --all-files
```

## Canonical Toolchain

- Python: use `uv sync --frozen --group dev`; `.venv` remains the repo-local environment created and managed by uv.
- Frontend Node: use **Node 22.x** from the repository `.nvmrc`.
- Package manager: use `corepack` + `pnpm`, with the canonical repo-local store at `.pnpm-store`.

## Verification

### Required Development

DealWatch now uses a five-layer verification contract. Think of it like airport security:

- `pre-commit` = the fast bag scan
- `pre-push` = the gate before the plane leaves
- `hosted` = the heavy scanners at the terminal
- `nightly` = the overnight maintenance crew
- `manual` = the extra inspection you only request when the trip actually needs it

Use the lighter layers by default and pull in the heavier ones only when the task crosses that
boundary.

#### Pre-commit

```bash
nvm use
corepack enable
PYTHONPATH=src uv run python -m dealwatch maintenance --dry-run
pre-commit run --all-files
```

#### Pre-push

The managed hook runs automatically after `python3 scripts/install_git_hooks.py`, but this is the
effective contract it enforces:

```bash
git diff --check
actionlint .github/workflows/*.yml
python3 scripts/verify_host_process_safety.py
python3 scripts/verify_sensitive_surface.py
python3 scripts/verify_tracked_artifacts.py
python3 scripts/verify_ci_runner_contract.py
python3 scripts/verify_root_allowlist.py
```

#### Local baseline before hosted CI

Run this smaller default path before you ask GitHub Actions to judge the branch:

```bash
nvm use
corepack enable
./scripts/test.sh -q
pnpm -C frontend build
python3 scripts/verify_docs_contract.py
```

That default path is intentionally lighter than the full hosted suite. Pull in the targeted local
add-ons only when the branch actually touches that surface:

- public/docs/front door: `python3 scripts/verify_public_surface.py`, `python3 scripts/verify_site_surface.py`, `python3 scripts/verify_public_entrypoints.py`, `python3 scripts/verify_feed_surface.py`
- runtime/store contract: `python3 scripts/verify_runtime_diagnostics.py`, `python3 scripts/verify_schema_contract.py`, `python3 scripts/verify_store_capability_registry.py`
- SEO/social preview: `python3 scripts/verify_social_preview_asset.py`, `python3 scripts/verify_social_preview_matrix.py`
- distribution/browser extension: `python3 scripts/verify_browser_extension_surface.py`, `python3 scripts/build_browser_extension_bundle.py`
- boundary/governance text: `python3 scripts/verify_english_boundary.py`

#### Manual deeper confidence

Use these only when the task actually needs end-to-end runtime proof, public-surface interaction
proof, or credentialed remote truth:

```bash
./scripts/smoke_product_hermetic.sh
python3 scripts/print_remote_repo_settings_checklist.py
python3 scripts/verify_remote_github_state.py
GITHUB_TOKEN=... python3 scripts/verify_remote_github_state.py
uvx --from zizmor==1.23.1 zizmor --persona regular --no-progress .github/workflows
```

If your branch touches runtime hygiene, cache cleanup, or repo-local rebuildables, also run:

```bash
PYTHONPATH=src uv run python -m dealwatch maintenance --dry-run
python3 scripts/cleanup_local_rebuildables.py --dry-run
python3 scripts/verify_host_process_safety.py
```

### Current Required GitHub Checks On `main`

These are the branch-protection checks currently enforced on `main` by GitHub remote state:

- `governance`
- `test`
- `frontend`
- `product-smoke`
- `CodeQL`
- `secret-hygiene`
- `Dependency Review`
- `workflow-hygiene`
- `trivy`

### Credentialed Remote Verification

These commands compare the repo contract with current GitHub API-visible remote facts:

- `python3 scripts/print_remote_repo_settings_checklist.py`
- `python3 scripts/verify_remote_github_state.py`
- `python3 scripts/verify_remote_public_hygiene.py`
- `GITHUB_TOKEN=... python3 scripts/verify_remote_github_state.py`
- `GITHUB_TOKEN=... python3 scripts/verify_remote_public_hygiene.py`

The checklist script intentionally separates `expected contract`, `current remote facts`, and `manual-only` checks so the repo does not mistake an intended GitHub setup for proof that it is currently live.

With `GITHUB_TOKEN`, the remote verifier now also checks:

- the current latest release object
- the expected public discussion threads used by the site community surface
- the current open code-scanning alert count
- the current open secret-scanning alert count
- the current open Dependabot alert count
- public PR / issue / release / comment bodies for host-path and personal-marker residue

### Manual-Admin Verification

These checks still matter, but they either live in the GitHub UI or remain blind spots until you provide credentials:

- current GitHub social preview image
- current code scanning alert state when you did not provide `GITHUB_TOKEN`
- any remaining GitHub UI-only community signals that are not exposed through the authenticated verifier

The `governance` job also runs `python3 scripts/verify_feed_surface.py` so the public Atom feed keeps matching the same stable entrypoints the rest of the public surface promises.
It now also runs `python3 scripts/verify_host_process_safety.py` so dangerous host-control primitives cannot silently re-enter the repo.

### Nightly Maintenance Intake

- Dependabot now runs as nightly maintenance intake in `America/Los_Angeles`.
- Scheduled `CodeQL` stays in the same nightly class.
- Treat both as background maintenance layers, not as blockers you must reproduce on every local branch before opening a pull request.

### Optional Exploratory Verification

Use these when you are changing interaction-heavy public surfaces and want stronger local confidence:

```bash
python3 scripts/verify_public_demo_interaction.py
```

## Dependency Maintenance Wave

DealWatch treats automated dependency PRs as a **separate maintenance wave**, not as default cargo for a product, closure, or governance-hardening branch.

The practical rule is:

- product / closure work should stay focused on the active feature or repo-shape goal
- grouped Dependabot PRs should be reviewed in their own maintenance pass
- security advisories can interrupt that rule when the default branch is actually vulnerable

The repository now groups Dependabot updates by ecosystem so the queue stays reviewable instead of exploding into many unrelated PRs at once.

Use the public docs below when you need the stable contribution-facing contract:

- [`docs/runbooks/store-onboarding-contract.md`](./docs/runbooks/store-onboarding-contract.md)

## Secret Hygiene

Run these checks before opening a pull request:

```bash
gitleaks dir . --no-banner --redact
gitleaks git . --no-banner --redact
trufflehog git --no-update file://"$PWD"
./scripts/run_git_secrets_audit.sh --scan
./scripts/run_git_secrets_audit.sh --scan-history
./scripts/run_fresh_clone_secret_scan.sh
```

Repository note:

- `.gitleaksignore` is intentionally kept to suppress the known `server-main` false positive in `src/dealwatch/server.py`.
- `.gitleaks.toml` now excludes gitignored local-only namespaces such as `.agents/`, `.codex/`, `.claude/`, and `.runtime-cache/` from filesystem-style scans so `gitleaks dir .` stays focused on the public/tracked surface instead of local developer noise.
- Do not add new suppressions unless the finding is reproducibly false and the reason is documented in the pull request.

## DCO

- The pull request tip commit must include a `Signed-off-by:` trailer.
- The repository enforces this through the governance workflow on pull requests.
- Use `git commit -s` on the closure or final integration commit so the trailer is added automatically.

## Dedicated Browser Lane

DealWatch's canonical maintainer browser lane is now a repo-owned Google Chrome instance:

- dedicated root: `~/.cache/dealwatch/browser/chrome-user-data`
- canonical profile: `dealwatch` / `Profile 21`
- canonical CDP lane: `http://127.0.0.1:9333`

Use the launcher first:

```bash
./scripts/launch_dealwatch_chrome.sh
```

That helper launches or reuses one dedicated DealWatch browser lane and ensures:

- a generated local identity tab under `.runtime-cache/browser-identity/index.html`
- canonical account/order tabs for Target / Safeway / Walmart / Weee
- one reusable CDP attach path instead of second-launching the same root

If you only need to re-anchor the current browser lane tabs without relaunching Chrome:

```bash
python3 scripts/open_dealwatch_account_pages.py --env-file .env
```

If you want a lightweight login-state snapshot after attach:

```bash
PYTHONPATH=src .venv/bin/python scripts/report_dealwatch_login_state.py --env-file .env --json
```

Optional human-facing identity overrides:

- `DEALWATCH_BROWSER_IDENTITY_LABEL`
- `DEALWATCH_BROWSER_IDENTITY_ACCENT`

Treat the identity tab as the human-facing anchor for this repo's browser lane:

- keep it open as the left-most anchor when practical
- pin it manually once if you want a stable tab-strip marker
- do not script Chrome private avatar/theme internals or Dock hacks as part of repo bootstrap

## Pull Requests

- Include fresh verification evidence.
- Update `README.md`, `SECURITY.md`, and `SUPPORT.md` when public behavior changes.
- Prefer product-facing improvements that help a first-time visitor understand why DealWatch exists and how to try it.
- Confirm every commit in the pull request includes `Signed-off-by:`.
