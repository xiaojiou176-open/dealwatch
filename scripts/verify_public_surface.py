#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_FILES = [
    ROOT / "README.md",
    ROOT / "AGENTS.md",
    ROOT / "CHANGELOG.md",
    ROOT / "CONTRIBUTING.md",
    ROOT / "SECURITY.md",
    ROOT / "SUPPORT.md",
]
ALLOWED_TRACKED_MARKDOWN = {
    "AGENTS.md",
    "README.md",
    "CHANGELOG.md",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "SUPPORT.md",
    "THIRD_PARTY.md",
    "CLAUDE.md",
    "docs/integrations/README.md",
    "docs/integrations/config-recipes.md",
    "docs/integrations/examples/README.md",
    "docs/integrations/skills/README.md",
    "docs/integrations/skills/claude-code-readonly-builder-skill.md",
    "docs/integrations/skills/codex-readonly-builder-skill.md",
    "docs/integrations/skills/dealwatch-readonly-builder-skill.md",
    "docs/integrations/skills/openclaw-readonly-builder-skill.md",
    "docs/integrations/skills/opencode-readonly-builder-skill.md",
    "docs/integrations/skills/openhands-readonly-builder-skill.md",
    "docs/integrations/prompt-starters.md",
    "docs/integrations/prompts/claude-code-starter.md",
    "docs/integrations/prompts/codex-starter.md",
    "docs/integrations/prompts/openclaw-starter.md",
    "docs/integrations/prompts/openhands-starter.md",
    "docs/integrations/prompts/opencode-starter.md",
    "docs/integrations/recipes/claude-code.md",
    "docs/integrations/recipes/codex.md",
    "docs/integrations/recipes/openclaw.md",
    "docs/integrations/recipes/opencode.md",
    "docs/integrations/recipes/openhands.md",
    "docs/runbooks/dependency-maintenance-wave.md",
    "docs/runbooks/browser-debug-lane.md",
    "docs/runbooks/runtime-hygiene.md",
    "docs/runbooks/store-onboarding-contract.md",
    "docs/roadmaps/dealwatch-api-mcp-substrate-phase1.md",
    "docs/roadmaps/dealwatch-closeout-overlay-2026-04-06.md",
    "docs/roadmaps/dealwatch-decision-memo.md",
    "docs/roadmaps/dealwatch-i18n-discovery.md",
    "docs/roadmaps/dealwatch-i18n-substrate.md",
    "docs/roadmaps/dealwatch-recommendation-launch-readiness-dossier.md",
    "docs/roadmaps/dealwatch-live-truth-closeout.md",
    "docs/roadmaps/dealwatch-master-delivery-plan.md",
    "docs/roadmaps/dealwatch-next-store-decision-packet.md",
    "docs/roadmaps/dealwatch-post-archive-execution-program.md",
    "docs/roadmaps/dealwatch-recommendation-adjudication-feedback.md",
    "docs/roadmaps/dealwatch-recommendation-readiness-gate.md",
    "docs/roadmaps/dealwatch-recommendation-replay-eval.md",
    "docs/roadmaps/dealwatch-recommendation-shadow-governance.md",
    "docs/roadmaps/dealwatch-recommendation-shadow-monitoring.md",
    "docs/roadmaps/dealwatch-repo-side-closeout.md",
    "docs/roadmaps/dealwatch-safeway-c1.md",
    "docs/roadmaps/dealwatch-switchyard-first-slice.md",
    "docs/roadmaps/dealwatch-walmart-c3.md",
    "docs/runbooks/recommendation-shadow-operations.md",
    "plugins/dealwatch-builder-pack/README.md",
    "plugins/dealwatch-builder-pack/skills/dealwatch-readonly-builder/SKILL.md",
    ".github/ISSUE_TEMPLATE/bug_report.md",
    ".github/ISSUE_TEMPLATE/feature_request.md",
    ".github/ISSUE_TEMPLATE/store_request.md",
    ".github/pull_request_template.md",
}
BANNED_PATTERNS = [
    re.compile(r"\btracker\b"),
    re.compile(r"src/tracker"),
    re.compile(r"python -m tracker"),
    re.compile(r"\bvar/"),
]
ALLOWED_CONTEXT_PHRASES = (
    "Do not reintroduce",
    "Not a",
    "not a",
    "No ",
    "no ",
    "grep gate against",
    "do not",
    "compare-vs-tracker",
)
REQUIRED_PHRASES = {
    ROOT / "README.md": [
        "Product source of truth is PostgreSQL",
        "SQLite remains a one-way import bridge",
        "Current GitHub public entry",
        "Secret scanning is enforced in CI",
        "Choose the first door that matches your real goal",
        "Then read the machine-readable mirrors in the same order",
        "Contributing",
        "Security",
        "Support",
    ],
    ROOT / "AGENTS.md": [
        "Product data: PostgreSQL via `DATABASE_URL`",
        "Legacy import source: `.legacy-runtime/data/dealwatch.db`",
        "Only signal a repo-recorded positive child PID that DealWatch itself spawned.",
        "`scripts/clean.py` is now a forbidden legacy entrypoint.",
        "python3 scripts/verify_host_process_safety.py",
    ],
    ROOT / "CONTRIBUTING.md": [
        "Keep changes surgical",
        "./scripts/test.sh -q",
    ],
    ROOT / "SECURITY.md": [
        "Do not report security vulnerabilities in public issues",
        "GitHub private vulnerability reporting",
    ],
    ROOT / "SUPPORT.md": [
        "Product Support",
        "security issues",
    ],
    ROOT / "CODE_OF_CONDUCT.md": [
        "Expected Behavior",
        "Unacceptable Behavior",
    ],
}
FORBIDDEN_REFERENCES = (
    "QUICKSTART.md",
    "DEPLOYMENT.md",
    "org-migration.md",
    "render-go-live-checklist.md",
)


def get_tracked_markdown() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    tracked = [item for item in result.stdout.decode("utf-8").split("\0") if item]
    return sorted(path for path in tracked if path.endswith(".md") and (ROOT / path).exists())


def main() -> int:
    findings: list[str] = []
    tracked_markdown = get_tracked_markdown()
    unexpected = [path for path in tracked_markdown if path not in ALLOWED_TRACKED_MARKDOWN]
    if unexpected:
        findings.append(f"Tracked markdown surface is not minimal: {', '.join(unexpected)}")

    for path in PUBLIC_FILES:
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for pattern in BANNED_PATTERNS:
                if not pattern.search(line):
                    continue
                if any(phrase in line for phrase in ALLOWED_CONTEXT_PHRASES):
                    continue
                findings.append(
                    f"{path.relative_to(ROOT)}:{lineno} contains banned legacy pattern: {pattern.pattern}"
                )
        for reference in FORBIDDEN_REFERENCES:
            if reference in text:
                findings.append(f"{path.relative_to(ROOT)} still references removed doc: {reference}")

    for path, phrases in REQUIRED_PHRASES.items():
        text = path.read_text(encoding="utf-8")
        for phrase in phrases:
            if phrase not in text:
                findings.append(f"{path.relative_to(ROOT)} missing required phrase: {phrase}")

    if findings:
        print("Public surface verification failed:")
        for finding in findings:
            print(f" - {finding}")
        return 1

    print("Public surface verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
