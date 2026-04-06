#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_SNIPPETS = {
    ROOT / "README.md": [
        "./scripts/test.sh -q",
        "./scripts/smoke_product_hermetic.sh",
        "python3 scripts/verify_host_process_safety.py",
        "English is the canonical collaboration language",
        "Security",
        "Contributing",
        "Support",
        "Current GitHub public entry",
        "Compare Preview",
        "compare-aware watch group",
        "python -m dealwatch server",
        "python -m dealwatch worker",
        "python -m dealwatch bootstrap-owner",
    ],
    ROOT / "CONTRIBUTING.md": [
        "Keep changes surgical",
        "nvm use",
        "Signed-off-by:",
        "Required Development",
        "pre-commit run --all-files",
        "python3 scripts/verify_host_process_safety.py",
        "python3 scripts/verify_sensitive_surface.py",
        "./scripts/run_git_secrets_audit.sh --scan-history",
        "python3 scripts/verify_remote_public_hygiene.py",
        "store-onboarding-contract.md",
    ],
    ROOT / "SECURITY.md": [
        "GitHub private vulnerability reporting",
        "OWNER_BOOTSTRAP_TOKEN",
    ],
    ROOT / "SUPPORT.md": [
        "product usage questions",
        "security issues",
    ],
}

FORBIDDEN_SNIPPETS = {
    ROOT / "README.md": [
        "Target / Safeway / Walmart / Weee all stayed signed in across a controlled dedicated-instance relaunch",
    ],
}


def main() -> int:
    missing: list[str] = []
    for path, snippets in REQUIRED_SNIPPETS.items():
        text = path.read_text(encoding="utf-8")
        for snippet in snippets:
            if snippet not in text:
                missing.append(f"{path.relative_to(ROOT)} missing snippet: {snippet}")
    for path, snippets in FORBIDDEN_SNIPPETS.items():
        text = path.read_text(encoding="utf-8")
        for snippet in snippets:
            if snippet in text:
                missing.append(f"{path.relative_to(ROOT)} contains stale snippet: {snippet}")

    if missing:
        print("Docs contract verification failed:")
        for item in missing:
            print(f" - {item}")
        return 1

    print("Docs contract verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
