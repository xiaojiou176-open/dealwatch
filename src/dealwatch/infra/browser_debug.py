from __future__ import annotations

import asyncio
import inspect
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from playwright.async_api import (
    Browser,
    BrowserContext,
    Error as PlaywrightError,
    Page,
    async_playwright,
)

from dealwatch.infra.config import DEFAULT_DEDICATED_CHROME_USER_DATA_DIR, Settings

_ALLOWED_ATTACH_MODES = {"browser", "page", "persistent"}
_LOGIN_KEYWORDS = (
    "login",
    "sign in",
    "sign-in",
    "authenticate",
    "auth",
    "sso",
)
_NO_PAGE_MESSAGE = (
    "No current page is visible in the attached browser context. Open the target site first, "
    "then rerun the browser debug probe."
)
_BOOTSTRAP_EMPTY_PAGE_URLS = {"about:blank", "chrome://newtab/"}
_DEFAULT_SHARED_CHROME_ROOT = str(
    Path("~/Library/Application Support/Google/Chrome").expanduser()
)
_LEGACY_SHARED_CHROME_ROOT_SUFFIX = "/Library/Application Support/Google/Chrome"
_BROWSER_IDENTITY_PAGE_NEEDLE = "/.runtime-cache/browser-identity/index.html"
_CANONICAL_BROWSER_DEBUG_URL_MARKERS = (
    "target.com/account",
    "safeway.com/customer-account/",
    "safeway.com/account/sign-in",
    "walmart.com/account",
    "identity.walmart.com/account/verifyitsyou",
    "sayweee.com/zh/account",
    "sayweee.com/en/account",
    "weee.com/account",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _trim_text(value: str, limit: int = 240) -> str:
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3]}..."


def _normalize_browser_root(value: str | None) -> str | None:
    if not value:
        return None
    return str(Path(value).expanduser())


def _is_legacy_shared_chrome_root(value: str | None) -> bool:
    normalized = _normalize_browser_root(value)
    if not normalized:
        return False
    normalized = normalized.replace("\\", "/")
    return normalized == _DEFAULT_SHARED_CHROME_ROOT or normalized.endswith(_LEGACY_SHARED_CHROME_ROOT_SUFFIX)


@dataclass(slots=True, frozen=True)
class BrowserDebugContract:
    attach_mode: str
    cdp_url: str
    remote_debug_port: int
    user_data_dir: str | None
    profile_name: str | None
    profile_directory: str | None
    start_url: str | None
    observe_ms: int
    storage_state_dir: str
    bundle_dir: str

    @property
    def requested_profile_label(self) -> str | None:
        return self.profile_name

    @property
    def has_profile_contract(self) -> bool:
        return bool(
            self.user_data_dir
            and self.profile_name
            and self.profile_directory
        )

    @property
    def has_any_profile_hint(self) -> bool:
        return bool(
            self.user_data_dir
            or self.profile_name
            or self.profile_directory
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "attach_mode": self.attach_mode,
            "cdp_url": self.cdp_url,
            "remote_debug_port": self.remote_debug_port,
            "user_data_dir": self.user_data_dir,
            "profile_name": self.profile_name,
            "profile_directory": self.profile_directory,
            "requested_profile_label": self.requested_profile_label,
            "has_profile_contract": self.has_profile_contract,
            "start_url": self.start_url,
            "observe_ms": self.observe_ms,
            "storage_state_dir": self.storage_state_dir,
            "bundle_dir": self.bundle_dir,
        }


_AUTHENTICATED_ACCOUNT_SURFACE_RULES: tuple[dict[str, tuple[str, ...]], ...] = (
    {
        "url_markers": ("target.com/account",),
        "title_markers": ("account : target",),
        "body_markers": ("hi,", "track orders", "account since"),
    },
    {
        "url_markers": ("safeway.com/customer-account/", "safeway.com/order-account/", "safeway.com/loyalty/"),
        "title_markers": ("safeway",),
        "body_markers": ("my account", "purchases", "sign out"),
    },
    {
        "url_markers": ("walmart.com/account",),
        "title_markers": ("manage account - home - walmart.com",),
        "body_markers": ("manage account", "hi,", "reorder my items"),
    },
    {
        "url_markers": ("sayweee.com/zh/account", "sayweee.com/en/account", "weee.com/account"),
        "title_markers": ("weee!",),
        "body_markers": ("my orders", "sign out"),
    },
)


def resolve_browser_debug_contract(settings: Settings) -> BrowserDebugContract:
    attach_mode = str(settings.CHROME_ATTACH_MODE or "").strip().lower() or "browser"
    if attach_mode not in _ALLOWED_ATTACH_MODES:
        raise ValueError("browser_debug_attach_mode_invalid")

    remote_debug_port = int(settings.CHROME_REMOTE_DEBUG_PORT or 9222)
    cdp_url = str(settings.CHROME_CDP_URL or "").strip()
    if not cdp_url:
        cdp_url = f"http://127.0.0.1:{remote_debug_port}"

    user_data_dir = _normalize_browser_root(str(settings.CHROME_USER_DATA_DIR or "").strip() or None)
    profile_name = str(settings.CHROME_PROFILE_NAME or "").strip() or None
    profile_directory = str(settings.CHROME_PROFILE_DIRECTORY or "").strip() or None
    start_url = str(settings.CHROME_START_URL or "").strip() or None
    observe_ms = max(int(settings.CHROME_OBSERVE_MS or 0), 0)
    bundle_dir = str(settings.BROWSER_DEBUG_BUNDLE_DIR)
    storage_state_dir = str(settings.STORAGE_STATE_DIR)

    return BrowserDebugContract(
        attach_mode=attach_mode,
        cdp_url=cdp_url.rstrip("/"),
        remote_debug_port=remote_debug_port,
        user_data_dir=user_data_dir,
        profile_name=profile_name,
        profile_directory=profile_directory,
        start_url=start_url,
        observe_ms=observe_ms,
        storage_state_dir=storage_state_dir,
        bundle_dir=bundle_dir,
    )


def classify_browser_debug_state(
    *,
    attached: bool,
    login_required: bool = False,
    requested_profile_label: str | None = None,
    observed_profile_label: str | None = None,
    existing_browser_session: bool = False,
    current_page_url: str | None = None,
) -> str:
    if not attached:
        return "attach_failed"
    if requested_profile_label and observed_profile_label and requested_profile_label != observed_profile_label:
        return "profile_mismatch"
    if login_required:
        return "login_required"
    if existing_browser_session:
        return "existing_browser_session"
    if not current_page_url:
        return "not_open"
    return "public_or_unknown"


def _read_profile_name_map(user_data_dir: str | None) -> dict[str, str]:
    if not user_data_dir:
        return {}
    local_state_path = Path(user_data_dir) / "Local State"
    if not local_state_path.is_file():
        return {}
    try:
        payload = json.loads(local_state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    profile_payload = payload.get("profile")
    if not isinstance(profile_payload, dict):
        return {}
    info_cache = profile_payload.get("info_cache")
    if not isinstance(info_cache, dict):
        return {}
    mapping: dict[str, str] = {}
    for directory, raw_info in info_cache.items():
        if not isinstance(raw_info, dict):
            continue
        name = str(raw_info.get("name") or "").strip()
        if name:
            mapping[str(directory)] = name
    return mapping


def _looks_like_login(*, url: str | None, title: str | None, content_snippet: str | None) -> bool:
    haystack = " ".join(
        part.lower()
        for part in (url or "", title or "", content_snippet or "")
        if isinstance(part, str)
    )
    return any(keyword in haystack for keyword in _LOGIN_KEYWORDS)


def _looks_like_authenticated_account_surface(
    *,
    url: str | None,
    title: str | None,
    content_snippet: str | None,
) -> bool:
    normalized_url = str(url or "").lower()
    normalized_title = str(title or "").lower()
    normalized_body = str(content_snippet or "").lower()
    for rule in _AUTHENTICATED_ACCOUNT_SURFACE_RULES:
        url_markers = rule["url_markers"]
        title_markers = rule["title_markers"]
        body_markers = rule["body_markers"]
        if any(marker in normalized_url for marker in url_markers) and (
            any(marker in normalized_title for marker in title_markers)
            or any(marker in normalized_body for marker in body_markers)
        ):
            return True
    return False


def _browser_debug_page_priority(url: str | None) -> tuple[int, str]:
    normalized_url = str(url or "").strip()
    lowered = normalized_url.lower()
    if not normalized_url:
        return (0, lowered)
    if lowered.startswith("file://") and _BROWSER_IDENTITY_PAGE_NEEDLE in lowered:
        return (10, lowered)
    if any(marker in lowered for marker in _CANONICAL_BROWSER_DEBUG_URL_MARKERS):
        return (100, lowered)
    if lowered in _BOOTSTRAP_EMPTY_PAGE_URLS:
        return (20, lowered)
    return (50, lowered)


def _select_browser_debug_page(pages: list[Page]) -> Page | None:
    if not pages:
        return None
    return max(
        pages,
        key=lambda page: _browser_debug_page_priority(getattr(page, "url", None)),
    )


async def collect_browser_debug_open_pages(pages: list[Page]) -> list[dict[str, Any]]:
    summaries_by_url: dict[str, dict[str, Any]] = {}
    ordered_pages = sorted(
        pages,
        key=lambda page: _browser_debug_page_priority(getattr(page, "url", None)),
        reverse=True,
    )
    for page in ordered_pages:
        url = getattr(page, "url", None) or None
        if not url:
            continue
        try:
            title = await page.title()
        except Exception:
            title = ""
        existing = summaries_by_url.get(url)
        if existing is None or (not existing.get("title") and title):
            summaries_by_url[url] = {
                "url": url,
                "title": title or None,
            }
        if len(summaries_by_url) >= 10 and existing is None:
            break
    return list(summaries_by_url.values())


async def collect_browser_debug_surfaces(
    page: Page,
    *,
    source: str,
    observe_ms: int,
) -> dict[str, Any]:
    console_events: list[dict[str, Any]] = []
    network_events: list[dict[str, Any]] = []
    pending_tasks: list[asyncio.Task[Any]] = []
    collecting = True

    def _on_console(message: Any) -> None:
        if not collecting:
            return
        console_type = getattr(message, "type", None)
        if callable(console_type):
            console_type = console_type()
        console_text = getattr(message, "text", None)
        if callable(console_text):
            console_text = console_text()
        console_events.append(
            {
                "type": str(console_type or "console"),
                "text": _trim_text(str(console_text or "")),
            }
        )

    def _on_page_error(error: Any) -> None:
        if not collecting:
            return
        console_events.append({"type": "pageerror", "text": _trim_text(str(error))})

    async def _append_request_finished(request: Any) -> None:
        try:
            response_getter = getattr(request, "response", None)
            response = response_getter() if callable(response_getter) else None
            if inspect.isawaitable(response):
                response = await response
            status = getattr(response, "status", None)
            if callable(status):
                status = status()
            network_events.append(
                {
                    "event": "finished",
                    "method": getattr(request, "method", None),
                    "url": _trim_text(getattr(request, "url", None) or ""),
                    "status": status,
                }
            )
        except (asyncio.CancelledError, PlaywrightError) as exc:
            if "Target page, context or browser has been closed" in str(exc):
                return
            raise

    def _on_request_finished(request: Any) -> None:
        if not collecting:
            return
        pending_tasks.append(asyncio.create_task(_append_request_finished(request)))

    def _on_request_failed(request: Any) -> None:
        if not collecting:
            return
        failure = getattr(request, "failure", None)
        failure_payload = failure() if callable(failure) else failure
        error_text = ""
        if isinstance(failure_payload, dict):
            error_text = str(failure_payload.get("errorText") or "")
        network_events.append(
            {
                "event": "failed",
                "method": getattr(request, "method", None),
                "url": _trim_text(getattr(request, "url", None) or ""),
                "error_text": _trim_text(error_text),
            }
        )

    page.on("console", _on_console)
    page.on("pageerror", _on_page_error)
    page.on("requestfinished", _on_request_finished)
    page.on("requestfailed", _on_request_failed)

    try:
        if observe_ms > 0:
            await asyncio.sleep(observe_ms / 1000)
        collecting = False
        if pending_tasks:
            await asyncio.gather(*pending_tasks, return_exceptions=True)
    finally:
        collecting = False
        remove_listener = getattr(page, "remove_listener", None)
        if callable(remove_listener):
            for event_name, callback in (
                ("console", _on_console),
                ("pageerror", _on_page_error),
                ("requestfinished", _on_request_finished),
                ("requestfailed", _on_request_failed),
            ):
                try:
                    remove_listener(event_name, callback)
                except Exception:
                    pass

    title = ""
    content_snippet = ""
    try:
        title = await page.title()
    except Exception:
        title = ""
    try:
        content_snippet = _trim_text(await page.content(), limit=600)
    except Exception:
        content_snippet = ""

    current_url = getattr(page, "url", None) or None
    authenticated_like = _looks_like_authenticated_account_surface(
        url=current_url,
        title=title,
        content_snippet=content_snippet,
    )
    return {
        "current_page": {
            "source": source,
            "url": current_url,
            "title": title or None,
        },
        "current_console": console_events[:10],
        "current_network": network_events[:10],
        "login_required": (
            _looks_like_login(url=current_url, title=title, content_snippet=content_snippet)
            and not authenticated_like
        ),
        "authenticated_account_surface": authenticated_like,
    }


async def diagnose_browser_debug(settings: Settings) -> dict[str, Any]:
    contract = resolve_browser_debug_contract(settings)
    diagnosis: dict[str, Any] = {
        "generated_at": _utc_now(),
        "contract": contract.to_dict(),
        "status": "attach_failed",
        "reason": None,
        "profile_truth": {
            "requested_profile_label": contract.requested_profile_label,
            "requested_user_data_dir": contract.user_data_dir,
            "requested_profile_directory": contract.profile_directory,
            "observed_profile_label": None,
            "observed_profile_directory": None,
            "confirmation_status": (
                "no_profile_contract"
                if not contract.has_any_profile_hint
                else "requested_unconfirmed"
                if contract.has_profile_contract
                else "profile_contract_incomplete"
            ),
        },
        "current_page": None,
        "open_pages": [],
        "current_console": [],
        "current_network": [],
        "next_actions": [],
    }

    if contract.has_any_profile_hint and not contract.has_profile_contract:
        diagnosis["reason"] = "profile_contract_incomplete"
        diagnosis["next_actions"] = [
            "Set CHROME_USER_DATA_DIR, CHROME_PROFILE_NAME, and CHROME_PROFILE_DIRECTORY together before using the real profile contract.",
        ]
        return diagnosis
    if (
        contract.has_profile_contract
        and contract.profile_name == "dealwatch"
        and _is_legacy_shared_chrome_root(contract.user_data_dir)
    ):
        diagnosis["reason"] = "legacy_shared_chrome_root"
        diagnosis["profile_truth"]["confirmation_status"] = "legacy_shared_chrome_root"
        diagnosis["next_actions"] = [
            f"Migrate the dealwatch profile into the dedicated Chrome root at {DEFAULT_DEDICATED_CHROME_USER_DATA_DIR}, then launch one dedicated Chrome instance and attach over CDP.",
        ]
        return diagnosis
    if contract.attach_mode == "persistent" and not contract.has_profile_contract:
        diagnosis["reason"] = "profile_contract_incomplete"
        diagnosis["next_actions"] = [
            "CHROME_ATTACH_MODE=persistent now requires CHROME_USER_DATA_DIR, CHROME_PROFILE_NAME, and CHROME_PROFILE_DIRECTORY together.",
        ]
        return diagnosis

    browser: Browser | None = None
    context: BrowserContext | None = None
    playwright = None
    should_close_context = False
    should_close_browser = False
    try:
        playwright = await async_playwright().start()
        existing_browser_session = False
        observed_profile_label: str | None = None
        observed_profile_directory: str | None = None

        if contract.has_profile_contract:
            user_data_dir_path = Path(contract.user_data_dir or "")
            if not user_data_dir_path.is_dir():
                diagnosis["reason"] = "missing_user_data_dir"
                diagnosis["profile_truth"]["confirmation_status"] = "missing_user_data_dir"
                diagnosis["next_actions"] = [
                    f"Create or point CHROME_USER_DATA_DIR at the real Chrome user-data directory for profile '{contract.profile_name}'.",
                ]
                return diagnosis
            profile_dir_path = user_data_dir_path / str(contract.profile_directory)
            if not profile_dir_path.is_dir():
                diagnosis["reason"] = "missing_profile_directory"
                diagnosis["profile_truth"]["confirmation_status"] = "missing_profile_directory"
                diagnosis["next_actions"] = [
                    f"Align CHROME_PROFILE_DIRECTORY with the real Chrome profile directory inside {user_data_dir_path}.",
                ]
                return diagnosis
            profile_name_map = _read_profile_name_map(contract.user_data_dir)
            observed_profile_label = profile_name_map.get(str(contract.profile_directory))
            observed_profile_directory = contract.profile_directory
            diagnosis["profile_truth"]["observed_profile_directory"] = observed_profile_directory
            diagnosis["profile_truth"]["observed_profile_label"] = observed_profile_label
            if observed_profile_label is None:
                diagnosis["reason"] = "missing_profile_metadata"
                diagnosis["profile_truth"]["confirmation_status"] = "missing_profile_metadata"
                diagnosis["next_actions"] = [
                    "Chrome Local State did not expose the configured profile directory; verify the user-data dir and profile directory pair, then rerun diagnose-live.",
                ]
                return diagnosis
            if observed_profile_label != contract.profile_name:
                diagnosis["status"] = "profile_mismatch"
                diagnosis["reason"] = "profile_name_mismatch"
                diagnosis["profile_truth"]["confirmation_status"] = "profile_mismatch"
                diagnosis["next_actions"] = [
                    "Align CHROME_PROFILE_NAME and CHROME_PROFILE_DIRECTORY with the same real Chrome profile, then rerun diagnose-live.",
                ]
                return diagnosis

        if contract.attach_mode == "persistent":
            launch_args = [f"--profile-directory={contract.profile_directory}"]
            context = await playwright.chromium.launch_persistent_context(
                contract.user_data_dir or "",
                headless=settings.PLAYWRIGHT_HEADLESS,
                args=launch_args,
            )
            should_close_context = True
            observed_profile_label = contract.profile_name
            observed_profile_directory = contract.profile_directory
        else:
            browser = await playwright.chromium.connect_over_cdp(contract.cdp_url)
            contexts = list(browser.contexts)
            pages = [page for item in contexts for page in item.pages]
            existing_browser_session = len(pages) > 0
            if contexts:
                context = contexts[0]

        pages = list(context.pages) if context is not None else []
        if context is not None and contract.start_url:
            if not pages:
                bootstrap_page = await context.new_page()
                await bootstrap_page.goto(contract.start_url, wait_until="load", timeout=15_000)
                pages = [bootstrap_page]
            elif all((getattr(page, "url", None) or "") in _BOOTSTRAP_EMPTY_PAGE_URLS for page in pages):
                bootstrap_page = pages[0]
                await bootstrap_page.goto(contract.start_url, wait_until="load", timeout=15_000)
        diagnosis["open_pages"] = await collect_browser_debug_open_pages(pages)
        target_page = _select_browser_debug_page(pages)
        if target_page is None:
            diagnosis["status"] = classify_browser_debug_state(attached=True)
            diagnosis["reason"] = "no_visible_page"
            if contract.start_url:
                diagnosis["next_actions"] = [
                    f"No page was visible after attach or bootstrap to {contract.start_url}. Inspect the browser runtime manually, then rerun diagnose-live.",
                ]
            else:
                diagnosis["next_actions"] = [_NO_PAGE_MESSAGE]
            return diagnosis

        surfaces = await collect_browser_debug_surfaces(
            target_page,
            source=(
                "bootstrapped_page"
                if contract.start_url and not existing_browser_session
                else "persistent_context"
                if contract.attach_mode == "persistent"
                else "existing_browser_session"
            ),
            observe_ms=contract.observe_ms,
        )
        diagnosis["current_page"] = surfaces["current_page"]
        diagnosis["current_console"] = surfaces["current_console"]
        diagnosis["current_network"] = surfaces["current_network"]
        diagnosis["profile_truth"]["observed_profile_label"] = observed_profile_label
        diagnosis["profile_truth"]["observed_profile_directory"] = observed_profile_directory
        if observed_profile_label and observed_profile_directory:
            diagnosis["profile_truth"]["confirmation_status"] = (
                "confirmed"
                if observed_profile_label == contract.profile_name
                and observed_profile_directory == contract.profile_directory
                else "profile_mismatch"
            )
        diagnosis["status"] = classify_browser_debug_state(
            attached=True,
            login_required=bool(surfaces["login_required"]),
            requested_profile_label=contract.profile_name,
            observed_profile_label=observed_profile_label,
            existing_browser_session=existing_browser_session,
            current_page_url=(surfaces["current_page"] or {}).get("url"),
        )
        diagnosis["reason"] = None
        if diagnosis["status"] == "login_required":
            diagnosis["next_actions"] = [
                "The browser attach path is live. Continue the site sign-in flow before treating this as a human-only blocker.",
            ]
        elif diagnosis["status"] == "existing_browser_session":
            diagnosis["next_actions"] = [
                "Reuse the dedicated DealWatch Chrome instance over CDP instead of launching a second browser against the same root.",
            ]
        elif diagnosis["status"] == "profile_mismatch":
            diagnosis["next_actions"] = [
                "Align CHROME_USER_DATA_DIR, CHROME_PROFILE_NAME, and CHROME_PROFILE_DIRECTORY with the dedicated DealWatch Chrome root/profile, then rerun diagnose-live.",
            ]
        else:
            diagnosis["next_actions"] = [
                "Inspect current_page/current_console/current_network before deciding whether the dedicated DealWatch Chrome instance is attached and whether any real external blocker remains.",
            ]
        return diagnosis
    except ValueError as exc:
        diagnosis["reason"] = str(exc)
        diagnosis["next_actions"] = [
            "Fix the browser debug contract inputs, then rerun diagnose-live.",
        ]
        return diagnosis
    except PlaywrightError as exc:
        error_text = str(exc)
        diagnosis["reason"] = error_text
        if "Singleton" in error_text or "ProcessSingleton" in error_text:
            diagnosis["status"] = "existing_browser_session"
            diagnosis["next_actions"] = [
                "The requested Chrome root is already in use. Reuse the dedicated DealWatch Chrome instance over CDP instead of starting a second persistent context.",
            ]
        else:
            diagnosis["status"] = "attach_failed"
            diagnosis["next_actions"] = [
                "Ensure the dedicated DealWatch Chrome instance is running with a reachable CDP listener, then rerun diagnose-live.",
            ]
        return diagnosis
    except Exception as exc:
        diagnosis["reason"] = str(exc)
        diagnosis["next_actions"] = [
            "The browser debug attach failed unexpectedly. Capture a support bundle before retrying.",
        ]
        return diagnosis
    finally:
        if should_close_context and context is not None:
            try:
                await context.close()
            except Exception:
                pass
        if should_close_browser and browser is not None:
            try:
                await browser.close()
            except Exception:
                pass
        if playwright is not None:
            try:
                await playwright.stop()
            except Exception:
                pass


async def probe_browser_debug(settings: Settings) -> dict[str, Any]:
    diagnosis = await diagnose_browser_debug(settings)
    return {
        "generated_at": diagnosis["generated_at"],
        "contract": diagnosis["contract"],
        "status": diagnosis["status"],
        "reason": diagnosis["reason"],
        "current_page": diagnosis["current_page"],
        "next_actions": diagnosis["next_actions"],
    }


def _run_git_command(args: list[str]) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    output = (result.stdout or result.stderr).strip()
    return output or None


def write_browser_support_bundle(settings: Settings, diagnosis: dict[str, Any]) -> dict[str, Any]:
    bundle_dir = settings.BROWSER_DEBUG_BUNDLE_DIR
    bundle_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": _utc_now(),
        "diagnosis": diagnosis,
        "git": {
            "branch": _run_git_command(["branch", "--show-current"]),
            "head": _run_git_command(["rev-parse", "HEAD"]),
            "status_short": _run_git_command(["status", "--short"]),
        },
    }
    output_path = bundle_dir / f"browser-support-bundle-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "status": "ok",
        "output_path": str(output_path),
        "bundle": payload,
    }
