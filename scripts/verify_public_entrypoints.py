#!/usr/bin/env python3
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse


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
        "https://xiaojiou176-open.github.io/dealwatch/compare-preview.html#sample-compare-demo",
        "https://xiaojiou176-open.github.io/dealwatch/quick-start.html",
        "https://xiaojiou176-open.github.io/dealwatch/builders.html",
        "Specialist route: [Builder Route](https://xiaojiou176-open.github.io/dealwatch/builders.html)",
        "https://xiaojiou176-open.github.io/dealwatch/compare-preview.html",
        "https://xiaojiou176-open.github.io/dealwatch/proof.html",
        "./site/builders.html",
        "./site/llms.txt",
        "./site/data/builder-client-catalog.json",
        "./site/data/builder-client-starters.json",
        "./site/data/builder-starter-pack.json",
        "./site/data/builder-client-configs.json",
        "https://github.com/xiaojiou176-open/dealwatch/releases/latest",
    ],
    SITE_INDEX: [
        "./compare-preview.html#sample-compare-demo",
        "./quick-start.html",
        "./builders.html",
        "./proof.html",
        "https://github.com/xiaojiou176-open/dealwatch/releases/latest",
        "https://github.com/xiaojiou176-open/dealwatch/discussions",
    ],
    SITE_PROOF: [
        "python3 scripts/verify_docs_contract.py",
        "python3 scripts/verify_public_surface.py",
        "python3 scripts/verify_site_surface.py",
        "python3 scripts/verify_remote_github_state.py",
        "python3 scripts/print_remote_repo_settings_checklist.py",
        "https://github.com/xiaojiou176-open/dealwatch/releases/latest",
    ],
    ROOT / "site" / "compare-preview.html": [
        "1 local-runtime API route",
    ],
    SITE_BUILDERS: [
        "https://github.com/xiaojiou176-open/dealwatch/blob/main/docs/roadmaps/dealwatch-api-mcp-substrate-phase1.md",
        "./data/builder-client-catalog.json",
        "./data/builder-client-starters.json",
        "./data/builder-starter-pack.json",
        "./data/builder-client-configs.json",
        "https://github.com/xiaojiou176-open/dealwatch/tree/main/docs/integrations",
    ],
    SITE_COMMUNITY: [
        "https://github.com/xiaojiou176-open/dealwatch#start-here",
        "https://github.com/xiaojiou176-open/dealwatch#roadmap",
    ],
    SITE_LLMS: [
        "https://xiaojiou176-open.github.io/dealwatch/builders.html",
        "https://xiaojiou176-open.github.io/dealwatch/data/builder-client-catalog.json",
        "https://xiaojiou176-open.github.io/dealwatch/data/builder-client-starters.json",
        "https://xiaojiou176-open.github.io/dealwatch/data/builder-starter-pack.json",
        "https://xiaojiou176-open.github.io/dealwatch/data/builder-client-configs.json",
        "https://github.com/xiaojiou176-open/dealwatch/releases/latest",
        "https://github.com/xiaojiou176-open/dealwatch#start-here",
        "https://github.com/xiaojiou176-open/dealwatch#roadmap",
    ],
    SITE_FEED: [
        "https://github.com/xiaojiou176-open/dealwatch/releases/latest",
        "https://github.com/xiaojiou176-open/dealwatch/releases",
        "https://github.com/xiaojiou176-open/dealwatch/blob/main/CHANGELOG.md",
    ],
}

FORBIDDEN_RELEASE_TAG_PATTERNS = (
    "https://github.com/xiaojiou176-open/dealwatch/releases/tag/v",
    "/releases/tag/v",
)

FORBIDDEN_LOCAL_FIRST_HOP_SUFFIXES = {".md", ".yaml", ".yml"}
FIRST_HOP_PAGES = (SITE_INDEX, SITE_BUILDERS)

REQUIRED_FIRST_HOP_LINKS = {
    SITE_INDEX: (
        "./compare-preview.html#sample-compare-demo",
        "./proof.html",
        "./quick-start.html",
        "./builders.html",
    ),
    SITE_BUILDERS: (
        "./data/builder-client-catalog.json",
        "./data/builder-client-starters.json",
        "./data/builder-starter-pack.json",
        "./data/builder-client-configs.json",
    ),
}


class _HrefCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attr_map = dict(attrs)
        href = attr_map.get("href")
        if href:
            self.hrefs.append(href)


def _collect_hrefs(path: Path) -> list[str]:
    collector = _HrefCollector()
    collector.feed(path.read_text(encoding="utf-8"))
    return collector.hrefs


def _resolve_local_href(page_path: Path, href: str) -> Path | None:
    parsed = urlparse(href)
    if parsed.scheme or parsed.netloc or not parsed.path or parsed.path.startswith("#"):
        return None
    return (page_path.parent / parsed.path).resolve()


def _assert_first_hop_targets(path: Path, findings: list[str]) -> None:
    hrefs = _collect_hrefs(path)
    href_set = set(hrefs)
    site_root = (ROOT / "site").resolve()

    for expected in REQUIRED_FIRST_HOP_LINKS[path]:
        if expected not in href_set:
            findings.append(f"{path.relative_to(ROOT)} missing first-hop link: {expected}")

    for href in hrefs:
        target = _resolve_local_href(path, href)
        if target is None:
            continue
        try:
            target.relative_to(site_root)
        except ValueError:
            findings.append(
                f"{path.relative_to(ROOT)} points outside site root with local href: {href}"
            )
            continue
        if target.suffix in FORBIDDEN_LOCAL_FIRST_HOP_SUFFIXES:
            findings.append(
                f"{path.relative_to(ROOT)} local first-hop should not target source docs: {href}"
            )
        if not target.exists():
            findings.append(
                f"{path.relative_to(ROOT)} local first-hop target is missing: {href}"
            )


def _assert_readme_start_here_order(text: str, findings: list[str]) -> None:
    try:
        start_here = text.index("## Start Here")
        compare_preview = text.index("https://xiaojiou176-open.github.io/dealwatch/compare-preview.html#sample-compare-demo", start_here)
        quick_start = text.index("https://xiaojiou176-open.github.io/dealwatch/quick-start.html", start_here)
        builders = text.index("https://xiaojiou176-open.github.io/dealwatch/builders.html", start_here)
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

    for path in FIRST_HOP_PAGES:
        _assert_first_hop_targets(path, findings)

    if findings:
        print("Public entrypoint verification failed:")
        for finding in findings:
            print(f" - {finding}")
        return 1

    print("Public entrypoint verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
