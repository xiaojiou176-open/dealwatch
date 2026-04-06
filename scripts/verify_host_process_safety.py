#!/usr/bin/env python3
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCAN_ROOTS = ("scripts", "src", "tests", "frontend", ".github")
SCANNED_SUFFIXES = {
    ".bash",
    ".cjs",
    ".js",
    ".jsx",
    ".mjs",
    ".py",
    ".sh",
    ".ts",
    ".tsx",
    ".yaml",
    ".yml",
    ".zsh",
}
ROOT_SCANNED_FILES = {
    ".pre-commit-config.yaml",
    "docker-compose.yml",
    "render.yaml",
    "setup.sh",
}
IGNORED_DIR_NAMES = {
    ".cache",
    ".git",
    ".pytest_cache",
    ".runtime-cache",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
}
SELF_EXEMPT_FILES = {
    Path("scripts/verify_host_process_safety.py"),
    Path("tests/test_host_process_safety_contract.py"),
}


@dataclass(frozen=True, slots=True)
class SafetyRule:
    name: str
    pattern: re.Pattern[str]
    message: str


SAFETY_RULES = (
    SafetyRule(
        name="killall",
        pattern=re.compile(r"\bkillall\b"),
        message="broad host matching via `killall` is forbidden; keep cleanup on repo-owned recorded resources.",
    ),
    SafetyRule(
        name="pkill",
        pattern=re.compile(r"\bpkill\b"),
        message="pattern-based process killing via `pkill` is forbidden; use repo-owned recorded resources instead.",
    ),
    SafetyRule(
        name="kill_minus_nine",
        pattern=re.compile(r"(^|[^\w-])kill\s+-9\b"),
        message="broad-force shell killing via `kill -9` is forbidden in repo code, tests, and CI.",
    ),
    SafetyRule(
        name="process_kill",
        pattern=re.compile(r"\bprocess\.kill\s*\("),
        message="direct `process.kill(...)` is forbidden; DealWatch must not emit raw host signals from repo code.",
    ),
    SafetyRule(
        name="os_kill",
        pattern=re.compile(r"\bos\.kill\s*\("),
        message="direct `os.kill(...)` is forbidden; DealWatch must not emit raw host signals from repo code.",
    ),
    SafetyRule(
        name="osascript",
        pattern=re.compile(r"\bosascript\b"),
        message="`osascript` is forbidden in executable DealWatch paths; browser control must stay on repo-owned contracts.",
    ),
    SafetyRule(
        name="system_events",
        pattern=re.compile(r"System Events"),
        message="desktop-wide `System Events` automation is forbidden in DealWatch worker/test/runtime paths.",
    ),
    SafetyRule(
        name="loginwindow_force_quit",
        pattern=re.compile(r"\bloginwindow\b|showForceQuitPanel|kAEShowApplicationWindow|aevt,apwn|CGSession"),
        message="system-level force-quit or loginwindow automation is forbidden.",
    ),
    SafetyRule(
        name="appleevent",
        pattern=re.compile(r"\bAppleEvent\b|NSAppleEventManager"),
        message="AppleEvent-driven app/session control is forbidden in DealWatch executable paths.",
    ),
)


def _should_scan(path: Path, *, root: Path) -> bool:
    rel_path = path.relative_to(root)
    if rel_path in SELF_EXEMPT_FILES:
        return False
    if any(part in IGNORED_DIR_NAMES for part in rel_path.parts[:-1]):
        return False
    if path.suffix in SCANNED_SUFFIXES:
        return True
    return rel_path.as_posix() in ROOT_SCANNED_FILES


def iter_scan_files(root: Path = ROOT) -> list[Path]:
    files: list[Path] = []
    seen: set[Path] = set()

    for root_name in SCAN_ROOTS:
        base = root / root_name
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or not _should_scan(path, root=root):
                continue
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            files.append(path)

    for path in sorted(root.iterdir()):
        if not path.is_file() or not _should_scan(path, root=root):
            continue
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        files.append(path)

    return files


def scan_repository(root: Path = ROOT) -> list[str]:
    findings: list[str] = []
    for path in iter_scan_files(root):
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for rule in SAFETY_RULES:
                if rule.pattern.search(line):
                    findings.append(
                        f"{path.relative_to(root)}:{lineno} violates `{rule.name}`: {rule.message}"
                    )
    return findings


def main() -> int:
    findings = scan_repository()
    if findings:
        print("Host/process safety verification failed:")
        for finding in findings:
            print(f" - {finding}")
        return 1

    print("Host/process safety verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
