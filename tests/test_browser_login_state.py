from __future__ import annotations

from pathlib import Path

import pytest

from scripts.report_dealwatch_login_state import (
    inspect_target,
    render_text,
    resolve_contract,
    select_context_for_target,
)
from scripts.shared.browser_lane_targets import CANONICAL_ACCOUNT_TARGETS, target_matches_existing_url_for_mode
from scripts.shared.browser_login_state import LoginObservation, classify_site_login_state


def _observation(*, url: str, title: str, body: str, cookies: set[str] | None = None) -> LoginObservation:
    return LoginObservation(
        current_url=url,
        title=title,
        body_text=body,
        cookie_names=frozenset(cookies or set()),
    )


def test_classify_site_login_state_target_homepage_logged_in() -> None:
    status = classify_site_login_state(
        "target",
        _observation(
            url="https://www.target.com/",
            title="Target : Expect More. Pay Less.",
            body="3 Hi, Member Track Orders",
        ),
    )
    assert status == "homepage_logged_in"


def test_classify_site_login_state_target_account_page_logged_in_even_with_sign_in_copy() -> None:
    status = classify_site_login_state(
        "target",
        _observation(
            url="https://www.target.com/account",
            title="Account : Target",
            body="Hi, Member Track Orders Sign in for a faster checkout next time",
        ),
    )
    assert status == "account_page_logged_in"


def test_classify_site_login_state_safeway_account_page_logged_in() -> None:
    status = classify_site_login_state(
        "safeway",
        _observation(
            url="https://www.safeway.com/customer-account/account-dashboard",
            title="Account Dashboard | safeway",
            body="My account Purchases Sign Out",
        ),
    )
    assert status == "account_page_logged_in"


def test_classify_site_login_state_safeway_account_page_logged_in_from_existing_tab_title_and_member_badge() -> None:
    status = classify_site_login_state(
        "safeway",
        _observation(
            url="https://www.safeway.com/customer-account/account-dashboard",
            title="Account Dashboard | safeway",
            body="Skip to main content 1410 E John St Member Fresh Pantry Beverages Frozen Household Recipes Shop more",
        ),
    )
    assert status == "account_page_logged_in"


def test_classify_site_login_state_safeway_account_url_without_logged_in_markers_is_unknown() -> None:
    status = classify_site_login_state(
        "safeway",
        _observation(
            url="https://www.safeway.com/customer-account/account-dashboard",
            title="Safeway",
            body="Weekly ad Grocery delivery rewards",
        ),
    )
    assert status == "unknown"


def test_classify_site_login_state_walmart_requires_reauth() -> None:
    status = classify_site_login_state(
        "walmart",
        _observation(
            url="https://identity.walmart.com/account/verifyitsyou",
            title="Walmart",
            body="Verify it's you to continue",
        ),
    )
    assert status == "reauth_required"


def test_classify_site_login_state_weee_account_page_logged_in() -> None:
    status = classify_site_login_state(
        "weee",
        _observation(
            url="https://www.sayweee.com/zh/account/my_orders",
            title="Weee!",
            body="My Orders Settings Help Center Sign Out Weee! Rewards",
            cookies={"IS_LOGIN"},
        ),
    )
    assert status == "account_page_logged_in"


def test_classify_site_login_state_weee_account_page_logged_in_with_cn_markers() -> None:
    status = classify_site_login_state(
        "weee",
        _observation(
            url="https://www.sayweee.com/zh/account/my_orders",
            title="Weee!",
            body="ID: 12886372 Weee! Rewards coupon gift card",
        ),
    )
    assert status == "account_page_logged_in"


def test_resolve_contract_requires_full_profile_contract(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc_info:
        resolve_contract(
            {
                "CHROME_CDP_URL": "http://127.0.0.1:9333",
                "CHROME_PROFILE_NAME": "dealwatch",
            },
            env_file=tmp_path / ".env",
            caller_name="DealWatch browser login-state report",
        )

    assert "CHROME_USER_DATA_DIR, CHROME_PROFILE_NAME, and CHROME_PROFILE_DIRECTORY" in str(exc_info.value)


def test_resolve_contract_rejects_legacy_shared_root(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc_info:
        resolve_contract(
            {
                "CHROME_USER_DATA_DIR": "<default-macos-chrome-user-data-root>",
                "CHROME_PROFILE_NAME": "dealwatch",
                "CHROME_PROFILE_DIRECTORY": "Profile 21",
            },
            env_file=tmp_path / ".env",
            caller_name="DealWatch browser login-state report",
        )

    assert "must not point at the legacy shared Chrome root" in str(exc_info.value)


def test_render_text_includes_browser_root() -> None:
    text = render_text(
        {
            "cdp_url": "http://127.0.0.1:9333",
            "browser_user_data_dir": "/tmp/dealwatch-chrome",
            "profile_display_name": "dealwatch",
            "profile_directory": "Profile 21",
            "sites": [
                {
                    "store": "Target account",
                    "state": "homepage_logged_in",
                    "source": "temporary_probe",
                    "observed_url": "https://www.target.com/",
                }
            ],
        }
    )

    assert "browser_user_data_dir=/tmp/dealwatch-chrome" in text
    assert "- Target account | state=homepage_logged_in" in text


class _FakeLocator:
    def __init__(self, body: str) -> None:
        self._body = body

    def inner_text(self, timeout: int = 5_000) -> str:
        _ = timeout
        return self._body


class _FakePage:
    def __init__(
        self,
        *,
        url: str = "about:blank",
        title: str = "",
        body: str = "",
        goto_error: Exception | None = None,
        title_error: Exception | None = None,
    ) -> None:
        self.url = url
        self._title = title
        self._body = body
        self._goto_error = goto_error
        self._title_error = title_error
        self.closed = False

    def goto(self, url: str, wait_until: str = "domcontentloaded", timeout: int = 30_000) -> None:
        _ = wait_until
        _ = timeout
        if self._goto_error is not None:
            raise self._goto_error
        self.url = url

    def wait_for_timeout(self, timeout: int) -> None:
        _ = timeout

    def title(self) -> str:
        if self._title_error is not None:
            raise self._title_error
        return self._title

    def locator(self, selector: str) -> _FakeLocator:
        assert selector == "body"
        return _FakeLocator(self._body)

    def close(self) -> None:
        self.closed = True


class _FakeContext:
    def __init__(self, page: _FakePage | None = None) -> None:
        self._page = page or _FakePage()
        self.pages: list[_FakePage] = []

    def new_page(self) -> _FakePage:
        self.pages.append(self._page)
        return self._page


def test_inspect_target_degrades_single_target_probe_error_to_unknown() -> None:
    target = CANONICAL_ACCOUNT_TARGETS[0]
    page = _FakePage(goto_error=RuntimeError("navigation timed out"))
    context = _FakeContext(page)

    observation = inspect_target(context, target, prefer_existing_tabs=False)

    assert observation.state == "unknown"
    assert observation.source == "temporary_probe_error"
    assert observation.error == "navigation timed out"
    assert page.closed is True


def test_inspect_target_reuses_existing_matching_tab_by_default() -> None:
    target = CANONICAL_ACCOUNT_TARGETS[1]
    existing_page = _FakePage(
        url="https://www.safeway.com/customer-account/account-dashboard",
        title="Account Dashboard | safeway",
        body=(
            "Skip to search Skip to main content Skip to cookie settings Skip to chat Grocery Health "
            "Pharmacy For Business 1410 E John St Hours & info Member Fresh Pantry Beverages Frozen "
            "Household Recipes Shop more Easter Weekly Ad Safeway AI Unlimited Free Delivery with "
            "FreshPass Plus score a $5 monthly credit with annual subscription My account "
            "Purchase history Profile & preferences Wallet"
        ),
    )
    context = _FakeContext()
    context.pages.append(existing_page)

    observation = inspect_target(context, target, prefer_existing_tabs=False)

    assert observation.source == "existing_tab"
    assert observation.state == "account_page_logged_in"
    assert existing_page.closed is False


def test_inspect_target_uses_full_body_text_for_state_classification() -> None:
    target = CANONICAL_ACCOUNT_TARGETS[1]
    body = ("filler " * 80) + "Member My account Purchase history Profile & preferences Wallet"
    existing_page = _FakePage(
        url="https://www.safeway.com/customer-account/account-dashboard",
        title="Account Dashboard | safeway",
        body=body,
    )
    context = _FakeContext()
    context.pages.append(existing_page)

    observation = inspect_target(context, target, prefer_existing_tabs=False)

    assert observation.state == "account_page_logged_in"
    assert len(observation.snippet) == 360


def test_inspect_target_prefers_account_tab_over_reauth_tab() -> None:
    target = CANONICAL_ACCOUNT_TARGETS[1]
    context = _FakeContext()
    context.pages.append(
        _FakePage(
            url="https://www.safeway.com/account/sign-in.html",
            title="Sign In | Safeway",
            body="Welcome back Sign in",
        )
    )
    account_page = _FakePage(
        url="https://www.safeway.com/customer-account/account-dashboard",
        title="Account Dashboard | safeway",
        body="Member My account Purchases Profile & preferences Wallet",
    )
    context.pages.append(account_page)

    observation = inspect_target(context, target, prefer_existing_tabs=False)

    assert observation.source == "existing_tab"
    assert observation.state == "account_page_logged_in"
    assert observation.observed_url == "https://www.safeway.com/customer-account/account-dashboard"


def test_select_context_for_target_prefers_context_with_matching_page() -> None:
    target = CANONICAL_ACCOUNT_TARGETS[1]
    first_context = _FakeContext()
    second_context = _FakeContext()
    second_context.pages.append(
        _FakePage(
            url="https://www.safeway.com/customer-account/account-dashboard",
            title="Account Dashboard | safeway",
            body="My account Purchases Profile & preferences",
        )
    )

    selected = select_context_for_target([first_context, second_context], target)

    assert selected is second_context


def test_select_context_for_target_prefers_account_context_over_reauth_context() -> None:
    target = CANONICAL_ACCOUNT_TARGETS[1]
    reauth_context = _FakeContext()
    reauth_context.pages.append(
        _FakePage(
            url="https://www.safeway.com/account/sign-in.html",
            title="Sign In | Safeway",
            body="Welcome back Sign in",
        )
    )
    account_context = _FakeContext()
    account_context.pages.append(
        _FakePage(
            url="https://www.safeway.com/customer-account/account-dashboard",
            title="Account Dashboard | safeway",
            body="Member My account Purchases Profile & preferences Wallet",
        )
    )

    selected = select_context_for_target([reauth_context, account_context], target)

    assert selected is account_context


def test_select_context_for_target_requires_non_empty_contexts() -> None:
    target = CANONICAL_ACCOUNT_TARGETS[1]

    with pytest.raises(ValueError) as exc_info:
        select_context_for_target([], target)

    assert "requires at least one browser context" in str(exc_info.value)


def test_render_text_includes_site_error_when_present() -> None:
    text = render_text(
        {
            "cdp_url": "http://127.0.0.1:9333",
            "browser_user_data_dir": "/tmp/dealwatch-chrome",
            "profile_display_name": "dealwatch",
            "profile_directory": "Profile 21",
            "sites": [
                {
                    "store": "Safeway account",
                    "state": "unknown",
                    "source": "temporary_probe_error",
                    "observed_url": "https://www.safeway.com/account/sign-in.html",
                    "error": "navigation timed out",
                }
            ],
        }
    )

    assert "error=navigation timed out" in text


def test_target_matches_existing_url_for_mode_can_reject_safeway_reauth_tab() -> None:
    target = CANONICAL_ACCOUNT_TARGETS[1]

    assert (
        target_matches_existing_url_for_mode(
            target,
            "https://www.safeway.com/account/sign-in.html",
            allow_reauth=False,
        )
        is False
    )
    assert (
        target_matches_existing_url_for_mode(
            target,
            "https://www.safeway.com/account/sign-in.html",
            allow_reauth=True,
        )
        is True
    )


def test_inspect_target_uses_exception_class_name_when_message_is_empty() -> None:
    target = CANONICAL_ACCOUNT_TARGETS[0]
    page = _FakePage(goto_error=RuntimeError(""))
    context = _FakeContext(page)

    observation = inspect_target(context, target, prefer_existing_tabs=False)

    assert observation.state == "unknown"
    assert observation.error == "RuntimeError"
