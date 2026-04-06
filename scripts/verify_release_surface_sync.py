#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHANGELOG = ROOT / "CHANGELOG.md"
README = ROOT / "README.md"
SITE_INDEX = ROOT / "site" / "index.html"
SITE_BUILDERS = ROOT / "site" / "builders.html"
SITE_LLMS = ROOT / "site" / "llms.txt"
SITE_PROOF = ROOT / "site" / "proof.html"
SITE_FEED = ROOT / "site" / "feed.xml"
LATEST_RELEASE_URL = "https://github.com/xiaojiou176/dealwatch/releases/latest"
RELEASE_HISTORY_URL = "https://github.com/xiaojiou176/dealwatch/releases"
CHANGELOG_URL = "https://github.com/xiaojiou176/dealwatch/blob/main/CHANGELOG.md"


def extract_latest_release_tag(changelog: str) -> str | None:
    matches = re.findall(r"^## \[(v\d+\.\d+\.\d+)\] - ", changelog, flags=re.MULTILINE)
    return matches[0] if matches else None


def main() -> int:
    changelog = CHANGELOG.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")
    site_index = SITE_INDEX.read_text(encoding="utf-8")
    site_builders = SITE_BUILDERS.read_text(encoding="utf-8")
    site_llms = SITE_LLMS.read_text(encoding="utf-8")
    site_proof = SITE_PROOF.read_text(encoding="utf-8")
    site_feed = SITE_FEED.read_text(encoding="utf-8")

    latest = extract_latest_release_tag(changelog)
    findings: list[str] = []

    if latest is None:
        findings.append("CHANGELOG.md does not expose a tagged latest release heading")
    if "## [Unreleased]" not in changelog:
        findings.append("CHANGELOG.md should keep an Unreleased section above the latest tagged release")

    if LATEST_RELEASE_URL not in readme:
        findings.append("README.md should point readers to the stable releases/latest URL")
    if RELEASE_HISTORY_URL not in readme:
        findings.append("README.md should keep a release history link")

    if LATEST_RELEASE_URL not in site_index:
        findings.append("site/index.html should point to the stable releases/latest URL")
    if "GitHub Releases" not in site_index:
        findings.append("site/index.html should describe the release surface as GitHub Releases")

    if LATEST_RELEASE_URL not in site_proof:
        findings.append("site/proof.html should point to the stable releases/latest URL")

    if LATEST_RELEASE_URL not in site_llms:
        findings.append("site/llms.txt should point to the stable releases/latest URL")
    if "Builder Starter Pack" not in site_llms:
        findings.append("site/llms.txt should keep the builder trust-surface link set")

    if "docs/integrations" not in site_builders:
        findings.append("site/builders.html should keep the builder pack frontdoor link")

    if LATEST_RELEASE_URL not in site_feed:
        findings.append("site/feed.xml latest release entry is not aligned with the stable releases/latest URL")
    if CHANGELOG_URL not in site_feed:
        findings.append("site/feed.xml should keep the CHANGELOG history entry")
    if latest is not None and f"Latest tagged release: {latest}" not in site_feed:
        findings.append("site/feed.xml should name the latest tagged release in the summary entry")

    if findings:
        print("Release surface sync verification failed:")
        for finding in findings:
            print(f" - {finding}")
        return 1

    print("Release surface sync verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
