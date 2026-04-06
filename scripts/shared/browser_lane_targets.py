from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class BrowserLaneTargetSpec:
    slug: str
    label: str
    requested_url: str
    host_needles: tuple[str, ...]
    account_url_markers: tuple[str, ...] = ()
    reauth_url_markers: tuple[str, ...] = ()
    logged_in_markers: tuple[str, ...] = ()
    reauth_text_markers: tuple[str, ...] = ()
    quick_link_label: str | None = None


CANONICAL_ACCOUNT_TARGETS: Final[tuple[BrowserLaneTargetSpec, ...]] = (
    BrowserLaneTargetSpec(
        slug="target-account",
        label="Target account",
        requested_url="https://www.target.com/account",
        host_needles=("target.com",),
        account_url_markers=("target.com/account",),
        reauth_url_markers=("target.com/login",),
        logged_in_markers=("hi,", "track orders", "account : target"),
        reauth_text_markers=("sign in", "sign-in"),
        quick_link_label="Target account",
    ),
    BrowserLaneTargetSpec(
        slug="safeway-account",
        label="Safeway account",
        requested_url="https://www.safeway.com/customer-account/account-dashboard",
        host_needles=("safeway.com",),
        account_url_markers=("safeway.com/customer-account/", "safeway.com/order-account/", "safeway.com/loyalty/"),
        reauth_url_markers=("safeway.com/account/sign-in",),
        logged_in_markers=(
            "account dashboard | safeway",
            "member",
            "my account",
            "purchases",
            "purchase history",
            "profile & preferences",
            "wallet",
            "sign out",
        ),
        reauth_text_markers=("sign in", "create account"),
        quick_link_label="Safeway account",
    ),
    BrowserLaneTargetSpec(
        slug="walmart-account",
        label="Walmart account",
        requested_url="https://www.walmart.com/account",
        host_needles=("walmart.com",),
        account_url_markers=("walmart.com/account",),
        reauth_url_markers=("identity.walmart.com/account/verifyitsyou", "walmart.com/?action=signin"),
        logged_in_markers=("manage account", "reorder my items", "hi,", "account - home - walmart.com"),
        reauth_text_markers=("verify it's you", "verify it’s you", "sign in"),
        quick_link_label="Walmart account",
    ),
    BrowserLaneTargetSpec(
        slug="weee-account",
        label="Weee account",
        requested_url="https://www.sayweee.com/zh/account",
        host_needles=("sayweee.com", "weee.com"),
        account_url_markers=("sayweee.com/zh/account", "sayweee.com/en/account", "weee.com/account"),
        reauth_url_markers=("sayweee.com/en/account/login", "sayweee.com/zh/account/login", "weee.com/account/login"),
        logged_in_markers=("my orders", "sign out", "weee! rewards"),
        reauth_text_markers=("sign in",),
        quick_link_label="Weee account",
    ),
)


def build_browser_lane_targets(identity_url: str | None = None) -> list[BrowserLaneTargetSpec]:
    targets: list[BrowserLaneTargetSpec] = []
    if identity_url:
        targets.append(
            BrowserLaneTargetSpec(
                slug="browser-identity",
                label="Browser identity",
                requested_url=identity_url,
                host_needles=(),
                account_url_markers=(identity_url.lower(),),
            )
        )
    targets.extend(CANONICAL_ACCOUNT_TARGETS)
    return targets


def browser_lane_quick_links() -> list[tuple[str, str]]:
    return [
        (target.quick_link_label or target.label, target.requested_url)
        for target in CANONICAL_ACCOUNT_TARGETS
        if target.quick_link_label
    ]


def target_matches_existing_url(target: BrowserLaneTargetSpec, existing_url: str) -> bool:
    return target_matches_existing_url_for_mode(target, existing_url, allow_reauth=True)


def target_matches_existing_url_for_mode(
    target: BrowserLaneTargetSpec,
    existing_url: str,
    *,
    allow_reauth: bool,
) -> bool:
    normalized_url = str(existing_url or "").strip()
    normalized_lower = normalized_url.lower()
    if target.slug == "browser-identity":
        return normalized_url == target.requested_url
    if not any(needle in normalized_lower for needle in target.host_needles):
        return False
    requested_lower = target.requested_url.lower()
    if normalized_lower.startswith(requested_lower):
        return True
    if any(marker in normalized_lower for marker in target.account_url_markers):
        return True
    if allow_reauth and any(marker in normalized_lower for marker in target.reauth_url_markers):
        return True
    return False


def classify_target_surface(
    target: BrowserLaneTargetSpec,
    *,
    observed_url: str,
    title: str,
    body_text: str,
) -> str:
    normalized_url = str(observed_url or "").lower()
    haystack = " ".join(part.lower() for part in (observed_url, title, body_text) if part)
    if any(marker in normalized_url for marker in target.reauth_url_markers):
        return "reauth_required"
    if any(marker in normalized_url for marker in target.account_url_markers) and any(
        marker in haystack for marker in target.logged_in_markers
    ):
        return "account_page_logged_in"
    if any(marker in haystack for marker in target.logged_in_markers):
        return "homepage_logged_in"
    if any(marker in haystack for marker in target.reauth_text_markers):
        return "reauth_required"
    return "unknown"
