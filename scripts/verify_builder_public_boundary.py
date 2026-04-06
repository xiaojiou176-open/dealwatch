#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

TARGET_GLOBS = (
    "README.md",
    "docs/integrations/README.md",
    "docs/integrations/config-recipes.md",
    "docs/integrations/prompt-starters.md",
    "docs/integrations/examples/README.md",
    "docs/integrations/prompts/*.md",
    "docs/integrations/recipes/*.md",
    "docs/integrations/skills/*.md",
    "site/builders.html",
    "site/llms.txt",
    "site/data/builder-*.json",
)

REQUIRED_PHRASES = {
    "README.md": (
        "not a hosted multi-tenant builder platform",
        "does **not** ship a formal SDK",
    ),
    "docs/integrations/README.md": (
        "not a hosted multi-tenant control plane guide",
        "not a write-side automation guide",
    ),
    "site/builders.html": (
        "official listing",
        "No hosted control plane",
        "No write-side MCP promise",
    ),
    "site/llms.txt": (
        "Not a hosted SaaS.",
        "Not a hosted plugin runtime",
    ),
}

OVERCLAIM_PATTERNS = (
    re.compile(r"\bofficial plugin\b", re.I),
    re.compile(r"\bmarketplace integration\b", re.I),
    re.compile(r"\bhosted (?:saas|platform|control plane|runtime|auth)\b", re.I),
    re.compile(r"\bmulti-tenant\b", re.I),
    re.compile(r"\bwrite-side mcp\b", re.I),
    re.compile(r"\bwrite[- ]capable mcp\b", re.I),
    re.compile(r"\bformal sdk\b", re.I),
    re.compile(r"\bpackaged sdk\b", re.I),
    re.compile(r"\bofficial sdk\b", re.I),
    re.compile(r"\bofficially listed\b", re.I),
    re.compile(r"\bofficial marketplace listing\b", re.I),
    re.compile(r"\bofficial registry listing\b", re.I),
    re.compile(r"\bruntime[- ]base\b", re.I),
    re.compile(r"\bdealwatch runs on (?:codex|claude code|openhands|opencode|openclaw)\b", re.I),
    re.compile(r"\bbuilt on (?:codex|claude code|openhands|opencode|openclaw)\b", re.I),
)

DISALLOWED_EXACT_PHRASES_BY_GLOB = {
    "docs/integrations/examples/*.response.json": (
        "Official repo-owned plugin-ready pack.",
    ),
    "site/data/builder-*.json": (
        "Official repo-owned plugin-ready pack.",
    ),
}

ALLOWED_CONTEXT_MARKERS = (
    "do not",
    "does not",
    "does not promise",
    "should not",
    "is not",
    "neither one is",
    "not a",
    "not an",
    "not the",
    "no official",
    "no hosted",
    "no write-side",
    "what stays out",
    "unsafe assumptions",
    "do not translate",
    "deferred",
    "without pretending",
    "outside the current",
    "still does not mean",
    "not prove",
    "not officially listed",
    "public proof asset",
    "public proof assets",
    "public proof surface",
)


def iter_target_files() -> list[Path]:
    results: list[Path] = []
    for pattern in TARGET_GLOBS:
        results.extend(sorted(ROOT.glob(pattern)))
    return results


def _normalize_text(text: str) -> str:
    normalized = re.sub(r"[*_`]+", "", text)
    normalized = re.sub(r"<[^>]+>", " ", normalized)
    normalized = re.sub(r"[.,!?;:(){}\[\]\"'“”‘’/\\-]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.lower().strip()


def _context_window(lines: list[str], lineno: int) -> str:
    start = max(0, lineno - 10)
    return _normalize_text("\n".join(lines[start:lineno]))


def collect_findings() -> list[str]:
    findings: list[str] = []
    for path in iter_target_files():
        relative = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines() or [text]
        for lineno, line in enumerate(lines, start=1):
            for pattern in OVERCLAIM_PATTERNS:
                if not pattern.search(line):
                    continue
                context = _context_window(lines, lineno)
                if any(marker in context for marker in ALLOWED_CONTEXT_MARKERS):
                    continue
                findings.append(
                    f"{relative}:{lineno} contains builder public overclaim pattern: {pattern.pattern}"
                )

        required = REQUIRED_PHRASES.get(relative)
        if required:
            lowered = _normalize_text(text)
            for phrase in required:
                if _normalize_text(phrase) not in lowered:
                    findings.append(f"{relative} missing required boundary phrase: {phrase}")

        for pattern, disallowed_phrases in DISALLOWED_EXACT_PHRASES_BY_GLOB.items():
            if not path.match(pattern):
                continue
            for phrase in disallowed_phrases:
                if phrase in text:
                    findings.append(f"{relative} contains store-like builder phrase: {phrase}")
    return findings


def main() -> int:
    findings = collect_findings()
    if findings:
        print("Builder public boundary verification failed:")
        for finding in findings:
            print(f" - {finding}")
        return 1

    print("Builder public boundary verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
