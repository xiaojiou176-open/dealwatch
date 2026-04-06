#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
SITE_INDEX = ROOT / "site" / "index.html"
SITE_BUILDERS = ROOT / "site" / "builders.html"
SITE_COMMUNITY = ROOT / "site" / "community.html"
SITE_PROOF = ROOT / "site" / "proof.html"
SITE_FEED = ROOT / "site" / "feed.xml"
SITE_LLMS = ROOT / "site" / "llms.txt"

REQUIRED_SNIPPETS = {
    README: [
        "## Start Here",
        "https://xiaojiou176.github.io/dealwatch/compare-preview.html#sample-compare-demo",
        "https://xiaojiou176.github.io/dealwatch/quick-start.html",
        "https://xiaojiou176.github.io/dealwatch/builders.html",
        "https://xiaojiou176.github.io/dealwatch/compare-preview.html",
        "https://xiaojiou176.github.io/dealwatch/proof.html",
        "./site/builders.html",
        "./site/llms.txt",
        "./site/data/builder-client-catalog.json",
        "./site/data/builder-client-starters.json",
        "./site/data/builder-starter-pack.json",
        "./site/data/builder-client-configs.json",
        "https://github.com/xiaojiou176/dealwatch/releases/latest",
    ],
    SITE_INDEX: [
        "./compare-preview.html#sample-compare-demo",
        "./quick-start.html",
        "./builders.html",
        "./proof.html",
        "https://github.com/xiaojiou176/dealwatch/releases/latest",
        "https://github.com/xiaojiou176/dealwatch/discussions/5",
    ],
    SITE_PROOF: [
        "python3 scripts/verify_docs_contract.py",
        "python3 scripts/verify_public_surface.py",
        "python3 scripts/verify_site_surface.py",
        "python3 scripts/verify_remote_github_state.py",
        "python3 scripts/print_remote_repo_settings_checklist.py",
        "https://github.com/xiaojiou176/dealwatch/releases/latest",
    ],
    SITE_BUILDERS: [
        "https://github.com/xiaojiou176/dealwatch/blob/main/docs/roadmaps/dealwatch-api-mcp-substrate-phase1.md",
        "./data/builder-client-catalog.json",
        "./data/builder-client-starters.json",
        "./data/builder-starter-pack.json",
        "./data/builder-client-configs.json",
        "https://github.com/xiaojiou176/dealwatch/tree/main/docs/integrations",
    ],
    SITE_COMMUNITY: [
        "https://github.com/xiaojiou176/dealwatch#start-here",
        "https://github.com/xiaojiou176/dealwatch#roadmap",
    ],
    SITE_LLMS: [
        "https://xiaojiou176.github.io/dealwatch/builders.html",
        "https://xiaojiou176.github.io/dealwatch/data/builder-client-catalog.json",
        "https://xiaojiou176.github.io/dealwatch/data/builder-client-starters.json",
        "https://xiaojiou176.github.io/dealwatch/data/builder-starter-pack.json",
        "https://xiaojiou176.github.io/dealwatch/data/builder-client-configs.json",
        "https://github.com/xiaojiou176/dealwatch/releases/latest",
        "https://github.com/xiaojiou176/dealwatch#start-here",
        "https://github.com/xiaojiou176/dealwatch#roadmap",
    ],
    SITE_FEED: [
        "https://github.com/xiaojiou176/dealwatch/releases/latest",
        "https://github.com/xiaojiou176/dealwatch/releases",
        "https://github.com/xiaojiou176/dealwatch/blob/main/CHANGELOG.md",
    ],
}

FORBIDDEN_RELEASE_TAG_PATTERNS = (
    "https://github.com/xiaojiou176/dealwatch/releases/tag/v",
    "/releases/tag/v",
)


def _assert_readme_start_here_order(text: str, findings: list[str]) -> None:
    try:
        start_here = text.index("## Start Here")
        compare_preview = text.index("https://xiaojiou176.github.io/dealwatch/compare-preview.html#sample-compare-demo", start_here)
        quick_start = text.index("https://xiaojiou176.github.io/dealwatch/quick-start.html", start_here)
        builders = text.index("https://xiaojiou176.github.io/dealwatch/builders.html", start_here)
    except ValueError as exc:
        findings.append(f"README.md missing ordered Start Here route evidence: {exc}")
        return

    if not compare_preview < quick_start < builders:
        findings.append(
            "README.md Start Here order drifted; expected Compare Preview -> Quick Start -> Builders"
        )


def main() -> int:
    findings: list[str] = []

    for path, snippets in REQUIRED_SNIPPETS.items():
        text = path.read_text(encoding="utf-8")
        for snippet in snippets:
            if snippet not in text:
                findings.append(f"{path.relative_to(ROOT)} missing entrypoint: {snippet}")

        for forbidden in FORBIDDEN_RELEASE_TAG_PATTERNS:
            if forbidden in text:
                findings.append(
                    f"{path.relative_to(ROOT)} should not hard-code release tag URLs: {forbidden}"
                )
        if path == README:
            _assert_readme_start_here_order(text, findings)

    if findings:
        print("Public entrypoint verification failed:")
        for finding in findings:
            print(f" - {finding}")
        return 1

    print("Public entrypoint verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
