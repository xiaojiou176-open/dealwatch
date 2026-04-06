#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS_DIR = ROOT / ".github" / "workflows"
FORBIDDEN_SNIPPETS = ("self-hosted",)


def main() -> int:
    findings: list[str] = []
    for path in sorted(WORKFLOWS_DIR.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        for snippet in FORBIDDEN_SNIPPETS:
            if snippet in text:
                findings.append(
                    f"{path.relative_to(ROOT)} contains forbidden runner snippet: {snippet}"
                )

    if findings:
        print("CI runner contract verification failed:")
        for finding in findings:
            print(f" - {finding}")
        return 1

    print("CI runner contract verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
