#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.shared.browser_instance_identity import (
    write_browser_identity_page,
)
from scripts.shared.browser_lane_contract import (
    DEFAULT_ENV_FILE,
    BrowserLaneContract,
    load_values,
    resolve_contract,
)
from scripts.shared.browser_lane_targets import (
    BrowserLaneTargetSpec,
    browser_lane_quick_links,
    build_browser_lane_targets,
    target_matches_existing_url,
    target_matches_existing_url_for_mode,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write the DealWatch browser identity tab and ensure canonical account pages exist in the live browser lane."
    )
    parser.add_argument(
        "--env-file",
        default=str(DEFAULT_ENV_FILE),
        help="Path to the repo-local .env file that carries the canonical Chrome contract.",
    )
    parser.add_argument(
        "--repo-root",
        default=str(PROJECT_ROOT),
        help="Override the repo root when writing the local identity page.",
    )
    parser.add_argument(
        "--write-only",
        action="store_true",
        help="Only write the identity page and print its metadata without touching the running browser targets.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of the default text report.",
    )
    return parser.parse_args()


def fetch_json(url: str, *, method: str = "GET") -> Any:
    request = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        raise SystemExit(
            f"DealWatch canonical account opener failed: {method} {url} is not reachable right now ({exc})."
        ) from exc


def list_page_targets(cdp_url: str) -> list[dict[str, Any]]:
    payload = fetch_json(f"{cdp_url}/json/list")
    if not isinstance(payload, list):
        raise SystemExit(f"DealWatch canonical account opener failed: {cdp_url}/json/list did not return a target list.")
    return [item for item in payload if isinstance(item, dict) and item.get("type") == "page"]


def create_target(cdp_url: str, target_url: str) -> dict[str, Any]:
    encoded_url = urllib.parse.quote(target_url, safe="")
    payload = fetch_json(f"{cdp_url}/json/new?{encoded_url}", method="PUT")
    if not isinstance(payload, dict):
        raise SystemExit(f"DealWatch canonical account opener failed: could not create target for {target_url}.")
    return payload


def _page_target_id(payload: dict[str, Any]) -> str | None:
    value = payload.get("id") or payload.get("targetId")
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def wait_for_target(
    *,
    cdp_url: str,
    target: BrowserLaneTargetSpec,
    seen_target_ids: set[str] | None = None,
    attempts: int = 20,
    delay_seconds: float = 0.25,
) -> dict[str, Any] | None:
    for _ in range(attempts):
        page_targets = list_page_targets(cdp_url)
        matching_targets = [
            page_target
            for page_target in page_targets
            if target_matches_existing_url(target, str(page_target.get("url", "")))
        ]
        if seen_target_ids:
            new_matches = [
                page_target
                for page_target in matching_targets
                if (_page_target_id(page_target) not in seen_target_ids)
            ]
            if new_matches:
                return new_matches[-1]
        elif matching_targets:
            return matching_targets[-1]
        time.sleep(delay_seconds)
    return None


def ensure_targets(
    *,
    contract: BrowserLaneContract,
    target_specs: list[BrowserLaneTargetSpec],
) -> list[dict[str, Any]]:
    target_list = list_page_targets(contract.cdp_url)
    results: list[dict[str, Any]] = []
    for target in target_specs:
        preferred_existing = next(
            (
                item
                for item in target_list
                if target_matches_existing_url_for_mode(
                    target,
                    str(item.get("url", "")),
                    allow_reauth=False,
                )
            ),
            None,
        )
        existing = preferred_existing or next(
            (
                item
                for item in target_list
                if target_matches_existing_url_for_mode(
                    target,
                    str(item.get("url", "")),
                    allow_reauth=True,
                )
            ),
            None,
        )
        created = False
        if existing is None:
            seen_target_ids = {
                target_id
                for target_id in (_page_target_id(item) for item in target_list)
                if target_id is not None
            }
            create_target(contract.cdp_url, target.requested_url)
            existing = wait_for_target(
                cdp_url=contract.cdp_url,
                target=target,
                seen_target_ids=seen_target_ids or None,
            )
            created = True
            if existing is None:
                raise SystemExit(
                    f"DealWatch canonical account opener failed: {target.label} did not appear in the CDP target list after createTarget."
                )
            target_list = list_page_targets(contract.cdp_url)
        results.append(
            {
                "label": target.label,
                "slug": target.slug,
                "requested_url": target.requested_url,
                "matched_url": str(existing.get("url", "")),
                "created": created,
                "action": "created" if created else "reused",
            }
        )
    return results


def build_payload(
    *,
    contract: BrowserLaneContract,
    values: dict[str, str],
    write_only: bool,
    repo_root: Path,
) -> dict[str, Any]:
    identity_page = write_browser_identity_page(
        repo_root=repo_root,
        env=values,
        cdp_url=contract.cdp_url,
        cdp_port=contract.remote_debug_port,
        user_data_dir=contract.user_data_dir,
        profile_name=contract.profile_name,
        profile_directory=contract.profile_directory,
        quick_links=browser_lane_quick_links(),
    )
    target_specs = build_browser_lane_targets(identity_page.identity_url)
    targets = [] if write_only else ensure_targets(contract=contract, target_specs=target_specs)
    key_map = {
        "browser-identity": "identity",
        "target-account": "target",
        "safeway-account": "safeway",
        "walmart-account": "walmart",
        "weee-account": "weee",
    }
    return {
        "ok": True,
        "status": "identity_written" if write_only else "targets_ensured",
        "identity_page_path": str(identity_page.identity_path),
        "identity_page_url": identity_page.identity_url,
        "identity_label": identity_page.repo_label,
        "identity_accent": identity_page.accent,
        "identity_title": identity_page.title,
        "cdp_url": contract.cdp_url,
        "browser_user_data_dir": contract.user_data_dir,
        "profile_display_name": contract.profile_name,
        "profile_directory": contract.profile_directory,
        "targets": [
            {
                **target,
                "key": key_map.get(str(target["slug"]), str(target["slug"])),
            }
            for target in targets
        ],
    }


def render_text(payload: dict[str, Any]) -> str:
    lines = [
        "DealWatch canonical browser lane helper",
        f"status={payload['status']}",
        f"identity_page_path={payload['identity_page_path']}",
        f"identity_page_url={payload['identity_page_url']}",
        f"identity_label={payload['identity_label']}",
        f"identity_accent={payload['identity_accent']}",
        f"cdp_url={payload['cdp_url']}",
        f"profile_display_name={payload['profile_display_name']}",
        f"profile_directory={payload['profile_directory']}",
    ]
    targets = payload.get("targets", [])
    if targets:
        lines.append(f"ensured_targets={','.join(target['slug'] for target in targets)}")
        for target in targets:
            lines.append(
                f"- {target['slug']} | action={target['action']} | requested={target['requested_url']} | matched={target['matched_url']}"
            )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    env_file = Path(args.env_file).expanduser()
    repo_root = Path(args.repo_root).expanduser().resolve()
    values = load_values(env_file)
    contract = resolve_contract(
        values,
        env_file=env_file,
        caller_name="DealWatch canonical account opener",
    )
    payload = build_payload(
        contract=contract,
        values=values,
        write_only=args.write_only,
        repo_root=repo_root,
    )
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(render_text(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
