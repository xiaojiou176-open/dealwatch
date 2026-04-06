#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALLOWED_RUNTIME_SUBDIRS = {
    "browser-identity",
    "cache",
    "logs",
    "operator",
    "runs",
}
ALLOWED_RUNTIME_FILES = {
    "maintenance.lock",
}
ALLOWED_ROOT_ENTRIES = {
    ".claude-plugin",
    ".dockerignore",
    ".env.example",
    ".env.production.example",
    ".git",
    ".gitallowed",
    ".github",
    ".gitignore",
    ".gitleaksignore",
    ".nvmrc",
    ".npmrc",
    ".pre-commit-config.yaml",
    "pyproject.toml",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "plugins",
    "THIRD_PARTY.md",
    "CLAUDE.md",
    "AGENTS.md",
    "alembic",
    "alembic.ini",
    "CHANGELOG.md",
    "CODEOWNERS",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "crontab.example",
    "docker-compose.yml",
    "Dockerfile",
    "docs",
    "frontend",
    "LICENSE",
    "pytest.ini",
    "README.md",
    "render.yaml",
    "requirements-dev.txt",
    "requirements.txt",
    "scripts",
    "SECURITY.md",
    "setup.sh",
    "site",
    "src",
    "SUPPORT.md",
    "tests",
    "uv.lock",
    "assets",
}
LOCAL_ONLY_PREFIXES = {
    ".agents",
    ".agent",
    ".codex",
    ".claude",
    ".serena",
    ".runtime-cache",
    ".legacy-runtime",
    ".pnpm-store",
    ".cache",
    "artifacts",
    "build",
    "coverage",
    "data",
    "dist",
    "log",
    "logs",
    "out",
    "playwright-report",
    "site-dist",
    "test-results",
    "tmp",
    "node_modules",
}
LOCAL_ONLY_EXACT = {
    ".env",
}
BANNED_ROOT_ENTRIES = {
    ".DS_Store",
    ".coverage",
    "notes.md",
    "draft.md",
    "todo.md",
    "plan.md",
    "final.md",
}


def _is_tracked(path: Path) -> bool:
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", path.name],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _tracked_under(prefix: str) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z", prefix],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=False,
    )
    return [item for item in result.stdout.decode("utf-8").split("\0") if item]


def _is_ignored(path: Path) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "-q", path.name],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _verify_runtime_namespace(findings: list[str]) -> None:
    runtime_dir = ROOT / ".runtime-cache"
    if not runtime_dir.exists():
        return

    for child in sorted(runtime_dir.iterdir(), key=lambda path: path.name):
        if child.name == ".gitkeep":
            continue
        if child.is_file() and child.name in ALLOWED_RUNTIME_FILES:
            continue
        if child.name not in ALLOWED_RUNTIME_SUBDIRS:
            findings.append(
                "Runtime namespace contains non-product entry: "
                f".runtime-cache/{child.name}"
            )


def _verify_frontend_store(findings: list[str]) -> None:
    frontend_store = ROOT / "frontend" / ".pnpm-store"
    if frontend_store.exists():
        findings.append("frontend/.pnpm-store must not exist; use the canonical root .pnpm-store directory.")


def main() -> int:
    root_entries = {path.name for path in ROOT.iterdir()}
    findings: list[str] = []

    for name in sorted(root_entries):
        path = ROOT / name
        if name in BANNED_ROOT_ENTRIES:
            findings.append(f"Banned root entry present: {name}")
            continue
        if name == ".agents":
            tracked = _tracked_under(".agents")
            disallowed = [path for path in tracked if path != ".agents/plugins/marketplace.json"]
            if disallowed:
                findings.append(
                    "Local-only root entry is tracked outside the allowed Codex marketplace file: "
                    + ", ".join(disallowed)
                )
            elif not path.exists():
                findings.append("Allowed .agents root entry is missing")
            continue
        if name == ".claude-plugin":
            tracked = _tracked_under(".claude-plugin")
            if not tracked:
                findings.append("Allowed .claude-plugin root entry has no tracked marketplace artifacts")
            continue
        if name in LOCAL_ONLY_EXACT or any(name.startswith(prefix) for prefix in LOCAL_ONLY_PREFIXES) or name.endswith(".log"):
            if _is_tracked(path):
                findings.append(f"Local-only root entry is tracked: {name}")
            elif not _is_ignored(path):
                findings.append(f"Local-only root entry is not ignored: {name}")
            continue
        if name not in ALLOWED_ROOT_ENTRIES:
            findings.append(f"Unexpected root entry present: {name}")

    _verify_runtime_namespace(findings)
    _verify_frontend_store(findings)

    if findings:
        print("Root allowlist verification failed:")
        for finding in findings:
            print(f" - {finding}")
        return 1

    print("Root allowlist verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
