#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"

REQUIRED_FILES = {
    SITE / "index.html",
    SITE / "builders.html",
    SITE / "quick-start.html",
    SITE / "compare-preview.html",
    SITE / "compare-vs-tracker.html",
    SITE / "proof.html",
    SITE / "use-cases.html",
    SITE / "community.html",
    SITE / "faq.html",
    SITE / "404.html",
    SITE / "styles.css",
    SITE / "robots.txt",
    SITE / "sitemap.xml",
    SITE / "feed.xml",
    SITE / "llms.txt",
    SITE / "data" / "builder-client-catalog.json",
    SITE / "data" / "builder-client-starters.json",
    SITE / "data" / "builder-starter-pack.json",
    SITE / "data" / "builder-client-configs.json",
    SITE / "favicon.svg",
    SITE / "site.webmanifest",
}

PAGE_REQUIREMENTS = {
    SITE / "index.html": [
        '<link rel="icon" href="./favicon.svg" type="image/svg+xml" />',
        '<link rel="manifest" href="./site.webmanifest" />',
        'meta name="twitter:card" content="summary_large_image"',
        'meta property="og:site_name" content="DealWatch"',
        "Latest release",
        'data-i18n="site.index.valueCardQuickStartTitle"',
        'data-i18n="site.index.valueCardBuildersTitle"',
    ],
    SITE / "builders.html": [
        '<link rel="icon" href="./favicon.svg" type="image/svg+xml" />',
        '<link rel="manifest" href="./site.webmanifest" />',
        'meta name="twitter:card" content="summary_large_image"',
        "Human path first: builder pack, contract, then runtime.",
        "Follow the builder route in order",
        "builder-client-catalog.json",
        "builder-client-starters.json",
        "builder-starter-pack.json",
        "builder-client-configs.json",
        '"@type":"TechArticle"',
    ],
    SITE / "quick-start.html": [
        '<link rel="icon" href="./favicon.svg" type="image/svg+xml" />',
        '<link rel="manifest" href="./site.webmanifest" />',
        'meta name="twitter:card" content="summary_large_image"',
        'data-i18n-json="site.quickStartPage.schema"',
    ],
    SITE / "compare-preview.html": [
        '<link rel="icon" href="./favicon.svg" type="image/svg+xml" />',
        '<link rel="manifest" href="./site.webmanifest" />',
        'meta name="twitter:card" content="summary_large_image"',
        'id="sample-compare-demo"',
        'Load sample compare',
        'No data is saved',
        'data-i18n="site.comparePreviewPage.nextStepsTitle"',
        'data-i18n="site.comparePreviewPage.footerBuildersLink"',
    ],
    SITE / "compare-vs-tracker.html": [
        "DealWatch is not just another single-link tracker.",
        '<link rel="icon" href="./favicon.svg" type="image/svg+xml" />',
        '<link rel="manifest" href="./site.webmanifest" />',
        'meta name="twitter:card" content="summary_large_image"',
    ],
    SITE / "proof.html": [
        "Claims mean more when they point back to evidence.",
        '<link rel="icon" href="./favicon.svg" type="image/svg+xml" />',
        '<link rel="manifest" href="./site.webmanifest" />',
        'meta name="twitter:card" content="summary_large_image"',
    ],
    SITE / "use-cases.html": [
        '<link rel="icon" href="./favicon.svg" type="image/svg+xml" />',
        '<link rel="manifest" href="./site.webmanifest" />',
        'meta name="twitter:card" content="summary_large_image"',
        'data-i18n-json="site.useCasesPage.schema"',
    ],
    SITE / "community.html": [
        "The public front desk for DealWatch.",
        '<link rel="icon" href="./favicon.svg" type="image/svg+xml" />',
        '<link rel="manifest" href="./site.webmanifest" />',
        'meta name="twitter:card" content="summary_large_image"',
        'data-i18n-json="site.communityPage.schema"',
    ],
    SITE / "faq.html": [
        '<link rel="icon" href="./favicon.svg" type="image/svg+xml" />',
        '<link rel="manifest" href="./site.webmanifest" />',
        '"@type":"FAQPage"',
        'meta name="twitter:card" content="summary_large_image"',
    ],
    SITE / "404.html": [
        "Wrong link. Right next step.",
        '<link rel="icon" href="./favicon.svg" type="image/svg+xml" />',
        '<link rel="manifest" href="./site.webmanifest" />',
    ],
}

EXPECTED_OG_IMAGES = {
    SITE / "index.html": "assets/social/og-home.png",
    SITE / "quick-start.html": "assets/social/og-quick-start.png",
    SITE / "compare-preview.html": "assets/social/og-compare-preview.png",
    SITE / "proof.html": "assets/social/og-proof.png",
}


def main() -> int:
    findings: list[str] = []

    for path in sorted(REQUIRED_FILES):
        if not path.exists():
            findings.append(f"Missing required site file: {path.relative_to(ROOT)}")

    for path, snippets in PAGE_REQUIREMENTS.items():
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for snippet in snippets:
            if snippet not in text:
                findings.append(f"{path.relative_to(ROOT)} missing snippet: {snippet}")
        if "<h1" not in text:
            findings.append(f"{path.relative_to(ROOT)} missing page-level h1")

    for path, asset in EXPECTED_OG_IMAGES.items():
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if asset not in text:
            findings.append(f"{path.relative_to(ROOT)} missing expected OG image: {asset}")

    robots = (SITE / "robots.txt").read_text(encoding="utf-8") if (SITE / "robots.txt").exists() else ""
    if "Sitemap: https://xiaojiou176.github.io/dealwatch/sitemap.xml" not in robots:
        findings.append("site/robots.txt missing canonical sitemap URL")

    sitemap = (SITE / "sitemap.xml").read_text(encoding="utf-8") if (SITE / "sitemap.xml").exists() else ""
    for required_url in (
        "https://xiaojiou176.github.io/dealwatch/",
        "https://xiaojiou176.github.io/dealwatch/builders.html",
        "https://xiaojiou176.github.io/dealwatch/quick-start.html",
        "https://xiaojiou176.github.io/dealwatch/compare-preview.html",
        "https://xiaojiou176.github.io/dealwatch/compare-vs-tracker.html",
        "https://xiaojiou176.github.io/dealwatch/proof.html",
        "https://xiaojiou176.github.io/dealwatch/use-cases.html",
        "https://xiaojiou176.github.io/dealwatch/community.html",
        "https://xiaojiou176.github.io/dealwatch/faq.html",
        "https://xiaojiou176.github.io/dealwatch/feed.xml",
        "https://xiaojiou176.github.io/dealwatch/llms.txt",
    ):
        if required_url not in sitemap:
            findings.append(f"site/sitemap.xml missing URL: {required_url}")

    if findings:
        print("Site surface verification failed:")
        for finding in findings:
            print(f" - {finding}")
        return 1

    print("Site surface verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
