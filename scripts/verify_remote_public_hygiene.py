#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.shared.sensitive_surface_patterns import find_sensitive_text_hits


BASE = "https://api.github.com/repos/xiaojiou176/dealwatch"
TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
GH = shutil.which("gh")


def build_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "dealwatch-remote-public-hygiene",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    return headers


def fetch_json(url: str) -> tuple[int, object]:
    request = Request(url, headers=build_headers())
    last_error: object = {"error": "unknown"}
    for attempt in range(3):
        try:
            with urlopen(request, timeout=20) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8")
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                payload = {"raw": body}
            # Retry transient rate/availability edges once or twice before failing hard.
            if exc.code in {403, 429, 500, 502, 503, 504} and attempt < 2:
                time.sleep(1 + attempt)
                last_error = payload
                continue
            return exc.code, payload
        except URLError as exc:
            last_error = {"error": str(exc)}
            if attempt < 2:
                time.sleep(1 + attempt)
                continue
            return 0, last_error
    if GH:
        relative = url.replace("https://api.github.com/", "", 1)
        result = subprocess.run(
            [GH, "api", relative],
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
        if result.returncode == 0:
            try:
                return 200, json.loads(result.stdout)
            except json.JSONDecodeError:
                return 0, {"error": "gh api returned non-json output"}
    return 0, last_error


def fetch_paginated_list(url: str) -> tuple[list[dict[str, Any]], str | None]:
    items: list[dict[str, Any]] = []
    for page in range(1, 11):
        separator = "&" if "?" in url else "?"
        status, payload = fetch_json(f"{url}{separator}page={page}")
        if status != 200 or not isinstance(payload, list):
            return [], f"endpoint returned {status}: {url}"
        typed_items = [item for item in payload if isinstance(item, dict)]
        items.extend(typed_items)
        if page == 10 and len(typed_items) == 100:
            return items, f"pagination truncated at 1000 items: {url}"
        if len(typed_items) < 100:
            break
    return items, None


def iter_text_surfaces() -> tuple[list[tuple[str, str]], list[str]]:
    surfaces: list[tuple[str, str]] = []
    warnings: list[str] = []
    endpoints = {
        "pull_body": f"{BASE}/pulls?state=all&per_page=100",
        "issue_body": f"{BASE}/issues?state=all&per_page=100",
        "issue_comment": f"{BASE}/issues/comments?per_page=100",
        "review_comment": f"{BASE}/pulls/comments?per_page=100",
        "release_body": f"{BASE}/releases?per_page=100",
    }
    for surface_name, endpoint in endpoints.items():
        items, warning = fetch_paginated_list(endpoint)
        if warning:
            warnings.append(f"{surface_name}: {warning}")
            continue
        for item in items:
            if surface_name == "issue_body" and item.get("pull_request"):
                continue
            text = str(item.get("body") or "")
            if not text.strip():
                continue
            url = str(item.get("html_url") or item.get("url") or endpoint)
            surfaces.append((url, text))
    return surfaces, warnings


def main() -> int:
    findings: list[str] = []
    surfaces, warnings = iter_text_surfaces()
    for url, text in surfaces:
        for description, sample in find_sensitive_text_hits(text):
            findings.append(f"{url}: {description} -> {sample}")
    if findings:
        print("Remote public hygiene verification failed:")
        for item in findings:
            print(f" - {item}")
        return 1
    if warnings:
        print("Remote public hygiene verification degraded:")
        for item in warnings:
            print(f" - {item}")
        print("Manual public-surface verification is still required for the unavailable endpoints.")
        return 0
    print("Remote public hygiene verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
