#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from playwright.sync_api import sync_playwright

from scripts.shared.browser_lane_contract import (
    DEFAULT_ENV_FILE,
    load_values,
    resolve_contract,
)
from scripts.shared.browser_login_state import LoginObservation, classify_site_login_state
from scripts.shared.browser_lane_targets import (
    CANONICAL_ACCOUNT_TARGETS,
    BrowserLaneTargetSpec,
    target_matches_existing_url_for_mode,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Report whether each DealWatch browser lane target currently looks like homepage-logged-in, account-page-logged-in, or reauth-required."
    )
    parser.add_argument(
        "--env-file",
        default=str(DEFAULT_ENV_FILE),
        help="Path to the repo-local .env file that carries the canonical Chrome contract.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of the default text report.",
    )
    parser.add_argument(
        "--prefer-existing-tabs",
        action="store_true",
        help="Backward-compatible alias. The reporter already reuses matching existing tabs first and only opens a temporary canonical probe when no matching tab exists.",
    )
    parser.add_argument(
        "--open-missing",
        action="store_true",
        help="Backward-compatible alias. Temporary canonical probes are already the default; this flag is accepted so callers do not fail on the old phrasing.",
    )
    return parser.parse_args()


@dataclass(frozen=True, slots=True)
class BrowserLoginObservation:
    store: str
    requested_url: str
    observed_url: str
    title: str
    state: str
    source: str
    snippet: str
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "store": self.store,
            "requested_url": self.requested_url,
            "observed_url": self.observed_url,
            "title": self.title,
            "state": self.state,
            "source": self.source,
            "snippet": self.snippet,
        }
        if self.error is not None:
            payload["error"] = self.error
        return payload


def _normalize_error(value: Exception) -> str:
    normalized = " ".join(str(value).split())
    if not normalized:
        normalized = value.__class__.__name__
    return normalized[:240]


def _unknown_observation(
    target: BrowserLaneTargetSpec,
    *,
    source: str,
    observed_url: str = "",
    title: str = "",
    snippet: str = "",
    error: str | None = None,
) -> BrowserLoginObservation:
    return BrowserLoginObservation(
        store=target.label,
        requested_url=target.requested_url,
        observed_url=observed_url,
        title=title,
        state="unknown",
        source=source,
        snippet=snippet,
        error=error,
    )


def _body_text(page: Any) -> str:
    try:
        text = page.locator("body").inner_text(timeout=5_000)
    except Exception:
        return ""
    return " ".join(text.split())


def _body_snippet(body_text: str) -> str:
    return body_text[:360]


def _find_existing_page(context: Any, target: BrowserLaneTargetSpec) -> Any | None:
    # Prefer the strongest account tab before falling back to a reauth page.
    pages = getattr(context, "pages", [])
    preferred_existing = next(
        (
            page
            for page in pages
            if target_matches_existing_url_for_mode(target, page.url, allow_reauth=False)
        ),
        None,
    )
    if preferred_existing is not None:
        return preferred_existing
    return next(
        (
            page
            for page in pages
            if target_matches_existing_url_for_mode(target, page.url, allow_reauth=True)
        ),
        None,
    )


def inspect_target(
    context: Any,
    target: BrowserLaneTargetSpec,
    *,
    prefer_existing_tabs: bool,
) -> BrowserLoginObservation:
    # Backward-compatible alias: matching existing tabs are always preferred now.
    _ = prefer_existing_tabs
    existing_page = _find_existing_page(context, target)
    source = "existing_tab" if existing_page is not None else "temporary_probe"
    created_page = None
    page = existing_page
    try:
        if page is None:
            created_page = context.new_page()
            page = created_page
            page.goto(target.requested_url, wait_until="domcontentloaded", timeout=30_000)
            page.wait_for_timeout(1500)
        if page is None:
            return _unknown_observation(target, source="missing_tab")
        observed_url = page.url
        title = page.title()
        body_text = _body_text(page)
        snippet = _body_snippet(body_text)
        site_key = target.slug.replace("-account", "")
        state = classify_site_login_state(
            site_key,
            LoginObservation(
                current_url=observed_url,
                title=title,
                body_text=body_text,
            ),
        )
        return BrowserLoginObservation(
            store=target.label,
            requested_url=target.requested_url,
            observed_url=observed_url,
            title=title,
            state=state,
            source=source,
            snippet=snippet,
        )
    except Exception as exc:
        observed_url = getattr(page, "url", "") or ""
        title = ""
        body_text = ""
        try:
            title = page.title()
        except Exception:
            title = ""
        try:
            body_text = _body_text(page)
        except Exception:
            body_text = ""
        return _unknown_observation(
            target,
            source=f"{source}_error",
            observed_url=observed_url,
            title=title,
            snippet=_body_snippet(body_text),
            error=_normalize_error(exc),
        )
    finally:
        if created_page is not None:
            created_page.close()


def select_context_for_target(contexts: list[Any], target: BrowserLaneTargetSpec) -> Any:
    if not contexts:
        raise ValueError("DealWatch browser login-state report requires at least one browser context.")
    for context in contexts:
        pages = getattr(context, "pages", [])
        if any(
            target_matches_existing_url_for_mode(target, page.url, allow_reauth=False)
            for page in pages
        ):
            return context
    for context in contexts:
        if _find_existing_page(context, target) is not None:
            return context
    return contexts[0]


def render_text(payload: dict[str, Any]) -> str:
    lines = [
        "DealWatch browser login-state report",
        f"cdp_url={payload['cdp_url']}",
        f"browser_user_data_dir={payload['browser_user_data_dir']}",
        f"profile_display_name={payload['profile_display_name']}",
        f"profile_directory={payload['profile_directory']}",
    ]
    for entry in payload["sites"]:
        line = f"- {entry['store']} | state={entry['state']} | source={entry['source']} | observed_url={entry['observed_url']}"
        if entry.get("error"):
            line += f" | error={entry['error']}"
        lines.append(line)
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    env_file = Path(args.env_file).expanduser()
    values = load_values(env_file)
    contract = resolve_contract(
        values,
        env_file=env_file,
        caller_name="DealWatch browser login-state report",
    )
    payload: dict[str, Any] = {
        "cdp_url": contract.cdp_url,
        "browser_user_data_dir": contract.user_data_dir,
        "profile_display_name": contract.profile_name,
        "profile_directory": contract.profile_directory,
        "sites": [],
    }
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.connect_over_cdp(contract.cdp_url)
            contexts = list(browser.contexts)
            if not contexts:
                contexts = [browser.new_context()]
            observations = [
                inspect_target(
                    select_context_for_target(contexts, target),
                    target,
                    prefer_existing_tabs=args.prefer_existing_tabs,
                )
                for target in CANONICAL_ACCOUNT_TARGETS
            ]
            payload["sites"] = [observation.to_dict() for observation in observations]
    except Exception as exc:
        raise SystemExit(
            f"DealWatch browser login-state report failed: could not attach to {contract.cdp_url} ({exc}). Launch or reuse the dedicated browser lane first."
        ) from exc

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(render_text(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
