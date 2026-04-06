#!/usr/bin/env python3
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / "site" / "feed.xml"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
CANONICAL_SITE_URL = "https://xiaojiou176.github.io/dealwatch/"
CANONICAL_FEED_URL = f"{CANONICAL_SITE_URL}feed.xml"
REQUIRED_ENTRIES = {
    "Latest release notes": "https://github.com/xiaojiou176/dealwatch/releases/latest",
    "Release history": "https://github.com/xiaojiou176/dealwatch/releases",
    "Changelog": "https://github.com/xiaojiou176/dealwatch/blob/main/CHANGELOG.md",
}


def get_text(element: ET.Element | None) -> str:
    if element is None or element.text is None:
        return ""
    return element.text.strip()


def main() -> int:
    findings: list[str] = []

    if not FEED.exists():
        print(f"Feed surface verification failed:\n - Missing feed file: {FEED.relative_to(ROOT)}")
        return 1

    try:
        root = ET.parse(FEED).getroot()
    except ET.ParseError as exc:
        print(f"Feed surface verification failed:\n - Invalid XML in {FEED.relative_to(ROOT)}: {exc}")
        return 1

    if root.tag != "{http://www.w3.org/2005/Atom}feed":
        findings.append("site/feed.xml root element must be Atom <feed>")

    feed_title = get_text(root.find("atom:title", ATOM_NS))
    if feed_title != "DealWatch Updates":
        findings.append("site/feed.xml missing canonical feed title: DealWatch Updates")

    feed_id = get_text(root.find("atom:id", ATOM_NS))
    if feed_id != CANONICAL_FEED_URL:
        findings.append(f"site/feed.xml feed id must stay stable: {CANONICAL_FEED_URL}")

    if not get_text(root.find("atom:updated", ATOM_NS)):
        findings.append("site/feed.xml missing feed-level updated timestamp")

    self_links = [
        link.get("href", "").strip()
        for link in root.findall("atom:link", ATOM_NS)
        if link.get("rel", "").strip() == "self"
    ]
    if self_links != [CANONICAL_FEED_URL]:
        findings.append(f"site/feed.xml must expose one canonical self link: {CANONICAL_FEED_URL}")

    home_links = [
        link.get("href", "").strip()
        for link in root.findall("atom:link", ATOM_NS)
        if link.get("rel") in (None, "")
    ]
    if CANONICAL_SITE_URL not in home_links:
        findings.append(f"site/feed.xml missing canonical home link: {CANONICAL_SITE_URL}")

    entries = root.findall("atom:entry", ATOM_NS)
    if len(entries) < len(REQUIRED_ENTRIES):
        findings.append(
            f"site/feed.xml should contain at least {len(REQUIRED_ENTRIES)} public entrypoints; found {len(entries)}"
        )

    entry_by_title: dict[str, ET.Element] = {}
    seen_titles: set[str] = set()
    seen_links: set[str] = set()
    duplicate_titles: set[str] = set()
    duplicate_links: set[str] = set()

    for entry in entries:
        title = get_text(entry.find("atom:title", ATOM_NS))
        href = entry.find("atom:link", ATOM_NS).get("href", "").strip() if entry.find("atom:link", ATOM_NS) is not None else ""
        entry_id = get_text(entry.find("atom:id", ATOM_NS))
        updated = get_text(entry.find("atom:updated", ATOM_NS))
        summary = get_text(entry.find("atom:summary", ATOM_NS))

        if not title:
            findings.append("site/feed.xml has an entry without a title")
            continue
        if not href:
            findings.append(f"site/feed.xml entry '{title}' missing link href")
            continue

        if title in seen_titles:
            duplicate_titles.add(title)
        seen_titles.add(title)

        if href in seen_links:
            duplicate_links.add(href)
        seen_links.add(href)

        entry_by_title[title] = entry

        if entry_id != href:
            findings.append(f"site/feed.xml entry '{title}' must use the link as its stable id")
        if not updated:
            findings.append(f"site/feed.xml entry '{title}' missing updated timestamp")
        if not summary:
            findings.append(f"site/feed.xml entry '{title}' missing summary")

    for title in sorted(duplicate_titles):
        findings.append(f"site/feed.xml duplicate entry title: {title}")

    for href in sorted(duplicate_links):
        findings.append(f"site/feed.xml duplicate entry link: {href}")

    for title, expected_href in REQUIRED_ENTRIES.items():
        entry = entry_by_title.get(title)
        if entry is None:
            findings.append(f"site/feed.xml missing required entry title: {title}")
            continue

        link = entry.find("atom:link", ATOM_NS)
        href = link.get("href", "").strip() if link is not None else ""
        if href != expected_href:
            findings.append(f"site/feed.xml entry '{title}' must point to stable URL: {expected_href}")

    if findings:
        print("Feed surface verification failed:")
        for finding in findings:
            print(f" - {finding}")
        return 1

    print("Feed surface verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
