from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from scripts.shared.browser_lane_targets import CANONICAL_ACCOUNT_TARGETS, classify_target_surface


@dataclass(frozen=True, slots=True)
class LoginObservation:
    current_url: str
    title: str
    body_text: str
    cookie_names: frozenset[str] = frozenset()


_TARGET_BY_KEY: Final[dict[str, object]] = {
    "target": CANONICAL_ACCOUNT_TARGETS[0],
    "safeway": CANONICAL_ACCOUNT_TARGETS[1],
    "walmart": CANONICAL_ACCOUNT_TARGETS[2],
    "weee": CANONICAL_ACCOUNT_TARGETS[3],
}


def classify_site_login_state(site_key: str, observation: LoginObservation) -> str:
    target = _TARGET_BY_KEY[site_key]
    return classify_target_surface(
        target,
        observed_url=observation.current_url,
        title=observation.title,
        body_text=observation.body_text,
    )
