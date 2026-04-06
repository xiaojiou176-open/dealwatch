#!/usr/bin/env python3
from __future__ import annotations

import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"

REQUIRED_URLS = {
    "Homepage",
    "Repository",
    "Documentation",
    "Issues",
    "Discussions",
    "Changelog",
}

REQUIRED_SCRIPTS = {
    "dealwatch": "dealwatch.cli:main",
    "dealwatch-mcp": "dealwatch.mcp.server:main",
}


def main() -> int:
    try:
        data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        print(
            f"Package publish surface verification failed: could not read {PYPROJECT.name} ({exc}).",
            file=sys.stderr,
        )
        return 1

    project = data.get("project")
    if not isinstance(project, dict):
        print("Package publish surface verification failed: missing [project] table.", file=sys.stderr)
        return 1

    findings: list[str] = []

    if project.get("readme") != "README.md":
        findings.append("project.readme must point at README.md")
    if project.get("license") != "MIT":
        findings.append("project.license must use the SPDX string MIT")

    urls = project.get("urls")
    if not isinstance(urls, dict):
        findings.append("project.urls must exist")
    else:
        missing_urls = sorted(REQUIRED_URLS - set(urls))
        if missing_urls:
            findings.append(f"project.urls missing keys: {', '.join(missing_urls)}")

    scripts = project.get("scripts")
    if not isinstance(scripts, dict):
        findings.append("project.scripts must exist")
    else:
        for key, expected in REQUIRED_SCRIPTS.items():
            actual = scripts.get(key)
            if actual != expected:
                findings.append(
                    f"project.scripts.{key} must equal {expected!r}; found {actual!r}"
                )

    classifiers = project.get("classifiers")
    if not isinstance(classifiers, list) or not classifiers:
        findings.append("project.classifiers must contain publish-oriented metadata")

    keywords = project.get("keywords")
    if not isinstance(keywords, list) or not keywords:
        findings.append("project.keywords must exist")

    if findings:
        print("Package publish surface verification failed.", file=sys.stderr)
        for finding in findings:
            print(f"- {finding}", file=sys.stderr)
        return 1

    print("Package publish surface verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
