#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALLOWED_TRACKED_DOCS = {"README.md", "CHANGELOG.md", "AGENTS.md", "CLAUDE.md"}
EXTRA_TRACKED_TEXT = {"crontab.example", "setup.sh", "bootstrap.sh"}
ALLOWED_SUFFIXES = {".md", ".py", ".sh", ".ts", ".tsx", ".html", ".yml", ".yaml"}
HAN_RE = re.compile(r"[\u3400-\u9fff]")


def iter_tracked_text_boundary() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    tracked = [item for item in result.stdout.decode("utf-8").split("\0") if item]
    docs: list[Path] = []
    for rel_path in tracked:
        path = Path(rel_path)
        if path.suffix not in ALLOWED_SUFFIXES and path.name not in ALLOWED_TRACKED_DOCS and path.name not in EXTRA_TRACKED_TEXT:
            continue
        if path.parts and path.parts[0] in {".agents", ".runtime-cache", "frontend"} and "node_modules" in path.parts:
            continue
        if path.parts and path.parts[0] in {".agents", ".runtime-cache"}:
            continue
        docs.append(ROOT / path)
    return docs


def main() -> int:
    findings: list[str] = []

    for path in iter_tracked_text_boundary():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if HAN_RE.search(line):
                rel = path.relative_to(ROOT)
                findings.append(f"{rel}:{lineno}: {line.strip()}")

    if findings:
        print("Tracked English verification failed. Han characters were found in tracked text surfaces:")
        for finding in findings:
            print(f" - {finding}")
        return 1

    print("Tracked English verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
