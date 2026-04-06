# Third-Party Transparency

This repository now treats the backend dependency chain as a single audited route instead of a set of hand-maintained requirement files.

## Authoritative Sources

- Python dependency manifest: `pyproject.toml`
- Locked Python dependency graph: `uv.lock`
- Transitional pip exports: `requirements.txt`, `requirements-dev.txt`
- Production-facing container bases:
  - `mcr.microsoft.com/playwright/python:v1.58.0-noble@sha256:678457c4c323b981d8b4befc57b95366bb1bb6aa30057b1269f6b171e8d9975a`
  - `ghcr.io/astral-sh/uv:0.8.15@sha256:a5727064a0de127bdb7c9d3c1383f3a9ac307d9f2d8a391edc7896c54289ced0`

## Update Workflow

1. Edit `pyproject.toml`.
2. Refresh the lockfile with `uv lock --python 3.13`.
3. Regenerate the bridge exports:
   - `uv export --frozen --no-hashes --no-header --no-dev --no-emit-project -o requirements.txt`
   - `uv export --frozen --no-hashes --no-header --only-dev --no-emit-project -o requirements-dev.txt`
4. Re-run the backend verification path:
   - `uv sync --frozen --group dev --python 3.13`
   - `./scripts/test.sh -q`

## Current Scope

This is a minimal transparency scaffold for W4. It documents the active supply-chain route and pinned container/toolchain inputs, but it is not yet a full SBOM.
