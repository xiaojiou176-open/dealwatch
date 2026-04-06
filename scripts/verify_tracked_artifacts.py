#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALLOWED_TRACKED_FILES = {
    ".agents/plugins/marketplace.json",
}
FORBIDDEN_PREFIXES = (
    ".agents/",
    ".agent/",
    ".cache/",
    ".codex/",
    ".claude/",
    ".pytest_cache/",
    ".ruff_cache/",
    ".runtime-cache/",
    ".legacy-runtime/",
    ".pnpm-store/",
    ".venv/",
    "artifacts/",
    "build/",
    "coverage/",
    "data/",
    "dist/",
    "frontend/.pnpm-store/",
    "frontend/dist/",
    "frontend/node_modules/",
    "logs/",
    "out/",
    "playwright-report/",
    "site-dist/",
    "test-results/",
    "tmp/",
)


def get_tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [
        item
        for item in result.stdout.decode("utf-8").split("\0")
        if item and (ROOT / item).exists()
    ]


def is_forbidden(path: str) -> bool:
    if path in ALLOWED_TRACKED_FILES:
        return False
    return (
        path.endswith(".log")
        or path.endswith(".db")
        or path.endswith(".sqlite")
        or path.startswith(FORBIDDEN_PREFIXES)
        or ".egg-info/" in path
        or path.endswith(".egg-info")
        or "storage_state_" in path
        or "browser-support-bundle-" in path
        or "browser-identity/" in path
    )


def main() -> int:
    findings = sorted(path for path in get_tracked_files() if is_forbidden(path))
    if findings:
        print("Tracked artifact verification failed:")
        for finding in findings:
            print(f" - {finding}")
        return 1

    print("Tracked artifact verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
