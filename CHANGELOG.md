# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

- A value-first public path in the README and Pages surface so first contact can start with `Comparison`, `Compare Preview`, and `Proof` instead of immediate stack assembly.
- A new quantified public proof snapshot built around current repository facts such as live stores, runtime surfaces, and public verification guards.
- A dedicated `./scripts/quickstart_stack.sh` entrypoint so the fastest local stack path is executable instead of README-only prose.
- A dedicated social-preview asset verifier and a remote repository settings checklist script so GitHub-side handoff work has concrete repo anchors.
- A static sample compare preview on the public Pages surface so first-time visitors can inspect a real compare result without installing the local stack.
- A page-level social preview matrix for Home, Quick Start, Compare Preview, Proof, FAQ, and Comparison so high-intent shares no longer collapse into one card.
- A dedicated public demo interaction verifier so the sample compare preview can be checked as a real clickable flow, not just a static HTML promise.
- A dedicated host/process safety verifier so dangerous cleanup and desktop-control primitives are blocked in executable repo paths before they land.
- A hard-stop replacement for `scripts/clean.py` plus a browser-instance ceiling in the Chrome launcher so DealWatch can no longer wide-delete protected evidence or keep opening lanes into an already crowded host.

### Changed

- The public quick-start story now leads with a one-command Compose path before the longer manual multi-process setup.
- The public feed now points readers at stable release and proof entrypoints instead of hand-maintained version text scattered across multiple surfaces.
- Public Pages and README now describe proof entrypoints without relying on duplicated snapshot counters or a dedicated story-sync guard.
- Public governance now also guards the repository social preview asset so that remote sharing polish has a concrete repo-side contract.
- Public copy now explains Compare Preview with normalized candidates, score breakdowns, and why-like / why-unlike reasons instead of underselling it as a bare score screen.
- Remote-side checklist copy now separates repo-verified GitHub facts from admin-only manual UI checks, so social preview upload and issue pinning are not overstated as automatic guarantees.
- The public story now reflects three live store adapters: `weee`, `ranch99`, and `target`.
- The proof and community surfaces now treat repository-level AI findings as an explicit admin review step instead of implying automatic repo-side verification.
- Public start-here and roadmap entrypoints now live in tracked README and Pages surfaces instead of depending on open GitHub issues, so repository closure can reach a true zero-open-issue state without losing public onboarding context.
- README now behaves more like a storefront: the heavy governance tail is trimmed back to proof/help links, and the Star reason appears before the final line.
- Quick Start now separates the public sample compare preview from the live local stack so “look first” and “run locally” are no longer mixed into one path.
- Comparison, Proof, Community, FAQ, and Use Cases now expose page-level `h1` titles so the public Pages surface has a complete semantic skeleton.
- Remote GitHub verification now distinguishes unauthenticated blind spots from authenticated checks instead of treating every `403` as configuration failure.
- AGENTS, README, CONTRIBUTING, browser-debug guidance, CI, and pre-commit now treat host-level process control as a first-class DealWatch safety contract instead of an implied convention.

## [v0.1.2] - 2026-03-25

### Added

- A dedicated comparison page that explains how DealWatch differs from a generic single-link price watcher.
- A proof page that ties public claims back to commands, routes, screenshots, and verification gates.
- `llms.txt` and `feed.xml` so the public surface is easier to consume by AI agents and feed readers.
- A dedicated Community page that acts like a front desk for issues, discussions, store requests, and release updates.

### Changed

- Public navigation now includes `Comparison`, `Proof`, and `Community` as first-class routes.
- Site verification now guards comparison/proof/feed/llms routes in addition to the original public pages.
- The public release narrative now treats `v0.1.2` as the latest content-surface expansion release.

## [v0.1.1] - 2026-03-25

### Added

- Custom `404.html`, favicon, and `site.webmanifest` support for the public GitHub Pages surface.
- Stronger social metadata across Home, Quick Start, Compare Preview, Use Cases, and FAQ.
- Extra community and release navigation on the public landing page.

### Changed

- The GitHub Pages deployment workflow now pins `actions/deploy-pages` to a live v4 SHA.
- The public release narrative now treats `v0.1.1` as the latest public-surface polish release.

## [v0.1.0] - 2026-03-25

### Added

- Compare Preview as a first-class API and WebUI route.
- A product-shaped public README built around compare-first intake, effective price, and alert history.
- A GitHub Pages-ready public site for search indexing and first-visit conversion.
- Public marketing assets including a control-cabin hero, walkthrough screenshots, and a Compare Preview GIF.

### Changed

- `dealwatch` is now the only live repository and package name.
- Product runtime surface is fully `.runtime-cache/` + PostgreSQL; `var/` is no longer part of the runtime contract.
- Docker and Compose topology target API + worker + frontend + PostgreSQL.
- Public documentation now leads with product value, screenshots, and release-driven trust signals.
- `python -m dealwatch` requires an explicit product subcommand.
- The repository public story is product-first; SQLite remains import-only.
- The AI analyzer now treats `dspy` as an optional runtime dependency instead of a required base install.
