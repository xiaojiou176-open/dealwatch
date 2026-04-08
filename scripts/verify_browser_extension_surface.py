#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "browser-extension"
MANIFEST = EXTENSION / "manifest.json"
REQUIRED_FILES = {
    "README.md",
    "chrome-web-store-listing.md",
    "background.js",
    "popup.html",
    "popup.js",
    "popup.css",
    "options.html",
    "options.js",
    "options.css",
}
REQUIRED_ICONS = {"assets/icon-16.png", "assets/icon-32.png", "assets/icon-48.png", "assets/icon-128.png"}
REQUIRED_PERMISSIONS = {"activeTab", "tabs", "storage", "contextMenus"}


def main() -> int:
    findings: list[str] = []
    if not MANIFEST.exists():
        print("Browser extension verification failed: missing browser-extension/manifest.json", file=sys.stderr)
        return 1

    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"Browser extension verification failed: invalid manifest.json ({exc})", file=sys.stderr)
        return 1

    for rel in sorted(REQUIRED_FILES | REQUIRED_ICONS):
        if not (EXTENSION / rel).exists():
            findings.append(f"missing browser-extension/{rel}")

    if manifest.get("manifest_version") != 3:
        findings.append("manifest_version must equal 3")
    if manifest.get("name") != "DealWatch Companion":
        findings.append("manifest name must equal 'DealWatch Companion'")
    if not isinstance(manifest.get("version"), str) or not manifest["version"].strip():
        findings.append("manifest version must be a non-empty string")

    permissions = set(manifest.get("permissions") or [])
    missing_permissions = REQUIRED_PERMISSIONS - permissions
    if missing_permissions:
        findings.append(f"manifest permissions missing: {', '.join(sorted(missing_permissions))}")

    action = manifest.get("action") or {}
    if action.get("default_popup") != "popup.html":
        findings.append("manifest action.default_popup must equal popup.html")

    background = manifest.get("background") or {}
    if background.get("service_worker") != "background.js":
        findings.append("manifest background.service_worker must equal background.js")

    if findings:
        print("Browser extension verification failed.", file=sys.stderr)
        for finding in findings:
            print(f"- {finding}", file=sys.stderr)
        return 1

    print("Browser extension verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
