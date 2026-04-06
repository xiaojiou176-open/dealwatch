#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.shared.sensitive_surface_patterns import find_sensitive_text_hits

FORBIDDEN_TRACKED_PATH_MARKERS = (
    ".runtime-cache/",
    ".legacy-runtime/",
    "logs/",
    "log/",
    "storage_state_",
    "browser-support-bundle-",
    "browser-identity/",
)
FORBIDDEN_TRACKED_SUFFIXES = (".log", ".db", ".sqlite")
ALLOWED_TEXT_PATTERN_FILES = {
    "scripts/shared/sensitive_surface_patterns.py",
}


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=False,
    )
    paths: list[Path] = []
    for item in result.stdout.decode("utf-8").split("\0"):
        if item:
            paths.append(ROOT / item)
    return paths


def display_path(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def is_binary(path: Path) -> bool:
    try:
        sample = path.read_bytes()[:2048]
    except OSError:
        return True
    return b"\0" in sample


def scan_path(path: Path) -> list[str]:
    rel_path = display_path(path)
    parts = Path(rel_path).parts
    findings: list[str] = []
    if (
        ".runtime-cache" in parts
        or ".legacy-runtime" in parts
        or "logs" in parts
        or "log" in parts
        or "browser-identity" in parts
        or "storage_state_" in rel_path
        or "browser-support-bundle-" in rel_path
    ):
        findings.append(f"{rel_path}: tracked runtime/log artifact marker")
    if rel_path.endswith(FORBIDDEN_TRACKED_SUFFIXES):
        findings.append(f"{rel_path}: tracked runtime/log database artifact")
    return findings


def scan_text(path: Path) -> list[str]:
    if is_binary(path):
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    except OSError:
        return []
    rel_path = display_path(path)
    if rel_path in ALLOWED_TEXT_PATTERN_FILES:
        return []
    findings: list[str] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for description, sample in find_sensitive_text_hits(line):
            findings.append(f"{rel_path}:{line_no}: {description} -> {sample}")
    return findings


def main() -> int:
    findings: list[str] = []
    for path in tracked_files():
        findings.extend(scan_path(path))
        findings.extend(scan_text(path))
    if findings:
        print("Sensitive surface verification failed:")
        for item in findings:
            print(f" - {item}")
        return 1
    print("Sensitive surface verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
