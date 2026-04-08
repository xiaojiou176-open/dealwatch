from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
import shutil
import time
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from dealwatch.application.services import ProductService
from dealwatch.core.models import Offer, PriceContext
from dealwatch.infra.config import PROJECT_ROOT, Settings
from dealwatch.persistence.session import get_session_factory, init_product_database


DEFAULT_RECOMMENDATION_EVAL_WORKSPACE = (
    PROJECT_ROOT / ".runtime-cache" / "operator" / "recommendation-evaluation-v1"
)
DEFAULT_RUNTIME_RUNS_DIR = PROJECT_ROOT / ".runtime-cache" / "runs"
_SAMPLE_FIXTURE_PATH = PROJECT_ROOT / "site" / "data" / "compare-preview-sample.json"
_CAMPAIGN_REPORT_NAME = "recommendation_replay_campaign_v1.json"
_CAMPAIGN_REPORT_MD_NAME = "recommendation_replay_campaign_v1.md"
_SKIPPED_ARTIFACT_ID = "33333333-3333-3333-3333-333333333333"
_INVALID_ARTIFACT_ID = "44444444-4444-4444-4444-444444444444"
_DEFAULT_WATCH_GROUP_SOURCE_DIR = DEFAULT_RUNTIME_RUNS_DIR / "watch-groups"
_DEFAULT_WATCH_TASK_SOURCE_DIR = DEFAULT_RUNTIME_RUNS_DIR / "watch-tasks"
_DEFAULT_RUNTIME_GROUP_PER_PATTERN_LIMIT = 3
_DEFAULT_NATIVE_COMPARE_ORIGIN_REPEAT_BUDGET = 0
_MIN_NATIVE_COMPARE_ORIGIN_MATCH_SCORE = 20.0


@dataclass(frozen=True)
class SeededReplayCase:
    case_id: str
    label: str
    zip_code: str
    submitted_urls: tuple[str, ...]
    supported_urls: tuple[str, ...]


@dataclass(frozen=True)
class RuntimeReplayCase:
    artifact_id: str
    label: str
    source_anchor: str
    source_summary_path: str
    source_metadata: dict[str, Any]
    compare_evidence: dict[str, Any]


def _case_comparisons(case: RuntimeReplayCase) -> list[dict[str, Any]]:
    return [dict(item) for item in (case.compare_evidence.get("comparisons") or [])]


def _case_source_url_pair(case: RuntimeReplayCase) -> tuple[str, ...]:
    values: list[str] = []
    for comparison in _case_comparisons(case):
        value = str(
            comparison.get("submitted_url")
            or comparison.get("normalized_url")
            or (comparison.get("offer") or {}).get("url")
            or ""
        ).strip()
        if value:
            values.append(value)
    return tuple(sorted(values))


def _case_store_pair(case: RuntimeReplayCase) -> tuple[str, ...]:
    values = [
        str(comparison.get("store_key") or "").strip()
        for comparison in _case_comparisons(case)
        if str(comparison.get("store_key") or "").strip()
    ]
    return tuple(sorted(values))


def _case_candidate_key_family(case: RuntimeReplayCase) -> tuple[str, ...]:
    values = [
        str(comparison.get("candidate_key") or "").strip()
        for comparison in _case_comparisons(case)
        if str(comparison.get("candidate_key") or "").strip()
    ]
    return tuple(sorted(values))


def _case_pattern_key(case: RuntimeReplayCase) -> tuple[tuple[str, ...], tuple[str, ...]]:
    return (_case_source_url_pair(case), _case_candidate_key_family(case))


def _group_cases_by_pattern(
    cases: list[RuntimeReplayCase],
) -> dict[tuple[tuple[str, ...], tuple[str, ...]], list[RuntimeReplayCase]]:
    grouped: dict[tuple[tuple[str, ...], tuple[str, ...]], list[RuntimeReplayCase]] = {}
    for case in cases:
        grouped.setdefault(_case_pattern_key(case), []).append(case)
    for entries in grouped.values():
        entries.sort(
            key=lambda item: str(item.source_metadata.get("saved_at") or ""),
            reverse=True,
        )
    return grouped


def _selection_profile_for_native_compare_origin(
    *,
    available_case_count: int,
    unique_pattern_count: int,
    top_pattern_share: float,
) -> tuple[str, str]:
    if available_case_count <= 1:
        return ("single_case", "low")
    if unique_pattern_count <= 1:
        return ("depth_heavy_single_pattern", "high")
    if top_pattern_share >= 0.75:
        return ("depth_heavy_concentrated", "high")
    if top_pattern_share >= 0.5:
        return ("mixed_but_concentrated", "medium")
    return ("breadth_forward", "low")


def _native_compare_origin_diversity_summary(
    cases: list[RuntimeReplayCase],
    *,
    selection_mode: str,
    repeat_budget_per_pattern: int,
    selected_cases: list[RuntimeReplayCase] | None = None,
) -> dict[str, Any]:
    grouped = _group_cases_by_pattern(cases)
    pattern_counts = Counter({pattern: len(entries) for pattern, entries in grouped.items()})
    source_url_pair_counts = Counter(
        _case_source_url_pair(case) for case in cases if _case_source_url_pair(case)
    )
    store_pair_counts = Counter(
        _case_store_pair(case) for case in cases if _case_store_pair(case)
    )
    available_case_count = len(cases)
    unique_pattern_count = len(pattern_counts)
    unique_source_url_pair_family_count = len(source_url_pair_counts)
    unique_store_pair_count = len(store_pair_counts)
    top_pattern_key: tuple[tuple[str, ...], tuple[str, ...]] | None = None
    top_pattern_count = 0
    if pattern_counts:
        top_pattern_key, top_pattern_count = pattern_counts.most_common(1)[0]
    top_pattern_share = (
        round(top_pattern_count / available_case_count, 4)
        if available_case_count
        else 0.0
    )
    breadth_profile, concentration_risk = _selection_profile_for_native_compare_origin(
        available_case_count=available_case_count,
        unique_pattern_count=unique_pattern_count,
        top_pattern_share=top_pattern_share,
    )

    selected_pattern_count = 0
    selected_repeat_count = 0
    dropped_repeat_count = 0
    if selected_cases is not None:
        selected_grouped = _group_cases_by_pattern(selected_cases)
        selected_pattern_count = len(selected_grouped)
        selected_repeat_count = max(0, len(selected_cases) - selected_pattern_count)
        dropped_repeat_count = max(0, available_case_count - len(selected_cases))

    top_repeated_pattern: dict[str, Any] | None = None
    if top_pattern_key is not None:
        top_repeated_pattern = {
            "source_url_pair_family": list(top_pattern_key[0]),
            "candidate_key_family": list(top_pattern_key[1]),
            "store_pair": list(_case_store_pair(grouped[top_pattern_key][0])),
            "case_count": top_pattern_count,
            "share_of_available_cases": top_pattern_share,
        }

    ceiling_signal = "not_evaluated"
    if available_case_count == 0:
        ceiling_signal = "no_native_compare_origin_cases_available"
    elif unique_pattern_count == 1 and top_pattern_share == 1.0:
        ceiling_signal = "single_pattern_runtime_ceiling"
    elif selected_cases is not None and len(selected_cases) == unique_pattern_count:
        ceiling_signal = "all_detected_patterns_selected"
    return {
        "selection_mode": selection_mode,
        "repeat_budget_per_pattern": repeat_budget_per_pattern,
        "available_case_count": available_case_count,
        "selected_case_count": len(selected_cases) if selected_cases is not None else None,
        "unique_pattern_count": unique_pattern_count,
        "unique_source_url_pair_family_count": unique_source_url_pair_family_count,
        "unique_store_pair_count": unique_store_pair_count,
        "selected_unique_pattern_count": selected_pattern_count if selected_cases is not None else None,
        "selected_repeat_count": selected_repeat_count if selected_cases is not None else None,
        "dropped_repeat_count": dropped_repeat_count if selected_cases is not None else None,
        "breadth_profile": breadth_profile,
        "concentration_risk": concentration_risk,
        "ceiling_signal": ceiling_signal,
        "top_repeated_pattern": top_repeated_pattern,
        "top_repeated_pattern_share": top_pattern_share,
        "available_pattern_counts": [
            {
                "source_url_pair_family": list(pattern_key[0]),
                "candidate_key_family": list(pattern_key[1]),
                "store_pair": list(_case_store_pair(entries[0])),
                "case_count": len(entries),
                "share_of_available_cases": round(len(entries) / available_case_count, 4),
            }
            for pattern_key, entries in sorted(
                grouped.items(),
                key=lambda item: len(item[1]),
                reverse=True,
            )
        ],
    }


def _select_native_compare_origin_cases(
    cases: list[RuntimeReplayCase],
    *,
    repeat_budget_per_pattern: int,
) -> tuple[list[RuntimeReplayCase], dict[str, Any]]:
    grouped = _group_cases_by_pattern(cases)
    ordered_patterns = sorted(
        grouped.items(),
        key=lambda item: str(item[1][0].source_metadata.get("saved_at") or ""),
        reverse=True,
    )
    selected: list[RuntimeReplayCase] = []
    for _, entries in ordered_patterns:
        if entries:
            selected.append(entries[0])
    if repeat_budget_per_pattern > 0:
        for _, entries in ordered_patterns:
            selected.extend(entries[1 : 1 + repeat_budget_per_pattern])
    return selected, _native_compare_origin_diversity_summary(
        cases,
        selection_mode="breadth_first_distinct_patterns",
        repeat_budget_per_pattern=repeat_budget_per_pattern,
        selected_cases=selected,
    )


def workspace_runs_dir(workspace: Path | str) -> Path:
    workspace_path = Path(workspace).expanduser()
    if not workspace_path.is_absolute():
        workspace_path = (PROJECT_ROOT / workspace_path).resolve()
    return workspace_path / "runs"


def workspace_database_url(workspace: Path | str) -> str:
    workspace_path = Path(workspace).expanduser()
    if not workspace_path.is_absolute():
        workspace_path = (PROJECT_ROOT / workspace_path).resolve()
    db_path = workspace_path / "recommendation-evaluation.db"
    return f"sqlite+aiosqlite:///{db_path}"


def build_recommendation_evaluation_settings(workspace: Path | str) -> Settings:
    return Settings(
        DATABASE_URL=workspace_database_url(workspace),
        RUNS_DIR=workspace_runs_dir(workspace),
        OWNER_EMAIL="owner@example.com",
        SMTP_HOST="",
        ZIP_CODE="98004",
    )


def _load_compare_preview_sample_fixture() -> dict[str, Any]:
    return json.loads(_SAMPLE_FIXTURE_PATH.read_text(encoding="utf-8"))


def _sample_offers_by_url() -> dict[str, dict[str, Any]]:
    fixture = _load_compare_preview_sample_fixture()
    offers: dict[str, dict[str, Any]] = {}
    for comparison in fixture.get("comparisons", []):
        offer = comparison.get("offer")
        submitted_url = comparison.get("submitted_url")
        if isinstance(submitted_url, str) and isinstance(offer, dict):
            offers[submitted_url] = offer
    return offers


def seeded_replay_cases() -> list[SeededReplayCase]:
    fixture = _load_compare_preview_sample_fixture()
    submitted_urls = tuple(str(url) for url in fixture.get("submitted_urls", []))
    sample_urls = submitted_urls[:3]
    supported_pair = tuple(url for url in sample_urls[:2])
    return [
        SeededReplayCase(
            case_id="seeded-strong-compare",
            label="Two-store compare preview match with a third distractor still produces an internal wait verdict.",
            zip_code=str(fixture.get("zip_code") or "98004"),
            submitted_urls=sample_urls,
            supported_urls=sample_urls,
        ),
        SeededReplayCase(
            case_id="seeded-abstention",
            label="Single resolved candidate plus unsupported URL should abstain instead of forcing a timing call.",
            zip_code=str(fixture.get("zip_code") or "98004"),
            submitted_urls=(
                supported_pair[0],
                "https://example.com/not-supported",
            ),
            supported_urls=(supported_pair[0],),
        ),
    ]


def _stable_runtime_artifact_id(source_path: Path) -> str:
    return str(uuid5(NAMESPACE_URL, str(source_path.resolve())))


def _normalize_identity_values(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    return tuple(sorted(value for value in (str(item).strip() for item in values) if value))


def _candidate_family_pair(candidate_keys: tuple[str, ...]) -> tuple[str, ...]:
    families: list[str] = []
    for candidate_key in candidate_keys:
        brand_hint, size_hint = _candidate_key_hints(candidate_key)
        family = " | ".join(part for part in (brand_hint, size_hint) if part)
        if family:
            families.append(family)
    return _normalize_identity_values(families)


def _pattern_key(
    source_urls: tuple[str, ...],
    candidate_keys: tuple[str, ...],
) -> str:
    source_key = " || ".join(source_urls) or "no_source_urls"
    candidate_key = " || ".join(candidate_keys) or "no_candidate_keys"
    return f"{source_key} ## {candidate_key}"


def _candidate_key_hints(candidate_key: str) -> tuple[str | None, str | None]:
    parts = [part.strip() for part in str(candidate_key).split("|")]
    brand_hint = parts[1] if len(parts) >= 2 and parts[1] else None
    size_hint = parts[2] if len(parts) >= 3 and parts[2] else None
    return brand_hint, size_hint


def _observation_offer(
    *,
    title: str,
    url: str,
    store_key: str,
    product_key: str,
    listed_price: float | None,
    observed_at: str | None,
    zip_code: str,
    original_price: float | None = None,
    unit_price_raw: str | None = None,
    brand_hint: str | None = None,
) -> dict[str, Any]:
    return {
        "store_id": store_key,
        "product_key": product_key,
        "title": title,
        "url": url,
        "price": listed_price,
        "original_price": original_price,
        "fetch_at": observed_at,
        "context": {
            "region": zip_code,
            "currency": "USD",
            "is_member": False,
        },
        "unit_price_info": {
            "raw": unit_price_raw,
            "brand": brand_hint,
        },
    }


def _build_offer(offer_payload: dict[str, Any], *, zip_code: str) -> Offer:
    context = dict(offer_payload.get("context") or {})
    fetch_at = datetime.fromisoformat(str(offer_payload.get("fetch_at")))
    return Offer(
        store_id=str(offer_payload.get("store_id") or ""),
        product_key=str(offer_payload.get("product_key") or ""),
        title=str(offer_payload.get("title") or ""),
        url=str(offer_payload.get("url") or ""),
        price=float(offer_payload.get("price") or 0.0),
        original_price=(
            float(offer_payload["original_price"])
            if offer_payload.get("original_price") is not None
            else None
        ),
        fetch_at=fetch_at,
        context=PriceContext(
            region=zip_code,
            currency=str(context.get("currency") or "USD"),
            is_member=bool(context.get("is_member", False)),
        ),
        unit_price_info=dict(offer_payload.get("unit_price_info") or {}),
    )


def _fixture_fetcher():
    offer_payloads = _sample_offers_by_url()

    async def _fetch_offer(product_url: str, store_key: str, *, zip_code: str):
        offer_payload = offer_payloads.get(product_url)
        if offer_payload is None:
            return None
        expected_store = str(offer_payload.get("store_id") or "")
        if expected_store and expected_store != store_key:
            return None
        return _build_offer(offer_payload, zip_code=zip_code)

    return _fetch_offer


async def create_recommendation_evaluation_service(workspace: Path | str) -> ProductService:
    workspace_path = Path(workspace)
    workspace_path.mkdir(parents=True, exist_ok=True)
    settings = build_recommendation_evaluation_settings(workspace_path)
    await init_product_database(settings.DATABASE_URL)
    session_factory = get_session_factory(settings.DATABASE_URL)
    service = ProductService(
        session_factory=session_factory,
        settings=settings,
        cashback_provider=None,
        email_provider=None,
    )
    service._fetch_offer = _fixture_fetcher()  # type: ignore[method-assign]
    return service


def _latest_runtime_group_cases(
    runtime_runs_dir: Path,
    *,
    per_pattern_limit: int | None = _DEFAULT_RUNTIME_GROUP_PER_PATTERN_LIMIT,
) -> list[RuntimeReplayCase]:
    rows_by_pattern: dict[tuple[tuple[str, ...], tuple[str, ...]], list[dict[str, Any]]] = {}
    for path in runtime_runs_dir.joinpath("watch-groups").rglob("group_run_summary.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        run = dict(payload.get("run") or {})
        if str(run.get("status") or "") != "succeeded":
            continue
        member_results = [item for item in (payload.get("member_results") or []) if item.get("status") == "succeeded"]
        if len(member_results) < 2:
            continue
        top_members = member_results[:2]
        source_urls = tuple(sorted(str(item.get("source_url") or "") for item in top_members))
        candidate_keys = tuple(sorted(str(item.get("candidate_key") or "") for item in top_members))
        if not all(source_urls) or not all(candidate_keys):
            continue
        similarity_score = SequenceMatcher(None, candidate_keys[0], candidate_keys[1]).ratio()
        if similarity_score < 0.9:
            continue
        store_pair = _normalize_identity_values(
            [str(item.get("store_key") or "") for item in top_members]
        )
        product_family_pair = _candidate_family_pair(candidate_keys)
        pattern_key = (source_urls, candidate_keys)
        saved_at = str(run.get("finished_at") or run.get("started_at") or "")
        rows_by_pattern.setdefault(pattern_key, []).append(
            {
                "saved_at": saved_at,
                "path": path,
                "payload": payload,
                "similarity_score": similarity_score,
                "source_urls": source_urls,
                "store_pair": store_pair,
                "candidate_pair": candidate_keys,
                "product_family_pair": product_family_pair,
            }
        )

    cases: list[RuntimeReplayCase] = []
    selected_pattern_rows: list[dict[str, Any]] = []
    for pattern_key, entries in rows_by_pattern.items():
        entries.sort(key=lambda item: str(item["saved_at"]), reverse=True)
        selected_entries = entries if per_pattern_limit is None else entries[:per_pattern_limit]
        selected_pattern_rows.append(
            {
                "pattern_key": pattern_key,
                "latest_saved_at": str(selected_entries[0]["saved_at"]) if selected_entries else "",
                "rows": selected_entries,
                "total_available": len(entries),
            }
        )

    selected_pattern_rows.sort(key=lambda item: str(item["latest_saved_at"]), reverse=True)
    max_depth = max((len(item["rows"]) for item in selected_pattern_rows), default=0)
    for selection_round in range(max_depth):
        for pattern_row in selected_pattern_rows:
            rows = list(pattern_row["rows"])
            if selection_round >= len(rows):
                continue
            row = rows[selection_round]
            saved_at = str(row["saved_at"])
            path = Path(row["path"])
            payload = dict(row["payload"])
            similarity_score = float(row["similarity_score"])
            group = dict(payload.get("group") or {})
            run = dict(payload.get("run") or {})
            top_members = [item for item in (payload.get("member_results") or []) if item.get("status") == "succeeded"][:2]
            comparisons: list[dict[str, Any]] = []
            for index, member in enumerate(top_members, start=1):
                brand_hint, size_hint = _candidate_key_hints(str(member.get("candidate_key") or ""))
                comparisons.append(
                    {
                        "submitted_url": str(member.get("source_url") or ""),
                        "supported": True,
                        "store_key": str(member.get("store_key") or ""),
                        "normalized_url": str(member.get("source_url") or ""),
                        "fetch_succeeded": True,
                        "error_code": None,
                        "candidate_key": str(member.get("candidate_key") or ""),
                        "brand_hint": brand_hint,
                        "size_hint": size_hint,
                        "offer": _observation_offer(
                            title=str(member.get("title_snapshot") or f"runtime-group-member-{index}"),
                            url=str(member.get("source_url") or ""),
                            store_key=str(member.get("store_key") or ""),
                            product_key=str(member.get("watch_target_id") or f"group-member-{index}"),
                            listed_price=float(member.get("listed_price") or 0.0),
                            observed_at=str(member.get("observed_at") or saved_at),
                            zip_code=str(group.get("zip_code") or "00000"),
                            unit_price_raw=size_hint,
                            brand_hint=brand_hint,
                        ),
                    }
                )
            compare_evidence = {
                "submitted_inputs": [item["submitted_url"] for item in comparisons],
                "zip_code": str(group.get("zip_code") or "00000"),
                "submitted_count": len(comparisons),
                "resolved_count": len(comparisons),
                "comparisons": comparisons,
                "matches": [
                    {
                        "left_store_key": comparisons[0]["store_key"],
                        "right_store_key": comparisons[1]["store_key"],
                        "score": round(similarity_score * 100, 1),
                        "why_like": [
                            "Both rows already survived the same runtime watch-group decision.",
                            "Candidate keys are near-identical across the cross-store pair.",
                        ],
                        "why_unlike": [
                            f"Derived from runtime group evidence triggered by {str(run.get('triggered_by') or 'runtime')}.",
                        ],
                    }
                ],
                "recommended_next_step_hint": {
                    "action": "create_watch_group",
                    "reason_code": "multi_candidate_strong_match",
                    "summary": (
                        "This runtime watch-group case already carries a strong multi-candidate decision path, "
                        "so the internal shadow lane can grade it as a compare-aware wait candidate."
                    ),
                    "successful_candidate_count": len(comparisons),
                    "strongest_match_score": round(similarity_score * 100, 1),
                },
                "risk_notes": [
                    "This case is reconstructed from a runtime watch-group summary for internal evaluation only.",
                    f"Runtime trigger was `{str(run.get('triggered_by') or 'runtime')}` and still needs maintainer adjudication.",
                ],
                "risk_note_items": [
                    {
                        "code": "runtime_group_summary_import",
                        "message": "Derived from a runtime watch-group summary for internal evaluation only.",
                    },
                    {
                        "code": f"runtime_trigger_{str(run.get('triggered_by') or 'runtime')}",
                        "message": f"Runtime trigger was `{str(run.get('triggered_by') or 'runtime')}` and still needs maintainer adjudication.",
                    },
                ],
                "successful_candidate_count": len(comparisons),
                "strongest_match_score": round(similarity_score * 100, 1),
            }
            cases.append(
                RuntimeReplayCase(
                    artifact_id=_stable_runtime_artifact_id(path),
                    label=f"runtime_group:{group.get('title') or 'group'}",
                    source_anchor="watch_group_run_summary",
                    source_summary_path=str(path),
                    source_metadata={
                        "saved_at": saved_at,
                        "triggered_by": str(run.get("triggered_by") or "runtime"),
                        "group_id": str(group.get("id") or ""),
                        "group_title": str(group.get("title") or ""),
                        "decision_reason": str(run.get("decision_reason") or ""),
                        "price_spread": run.get("price_spread"),
                        "non_seeded": True,
                        "pattern_key": _pattern_key(
                            tuple(row["source_urls"]),
                            tuple(row["candidate_pair"]),
                        ),
                        "source_url_pair": list(row["source_urls"]),
                        "store_pair": list(row["store_pair"]),
                        "candidate_pair": list(row["candidate_pair"]),
                        "product_family_pair": list(row["product_family_pair"]),
                        "selection_strategy": "breadth_first_pattern_round_robin",
                        "selection_reason": (
                            "unique_pattern_first"
                            if selection_round == 0
                            else "repeat_depth_after_unique_pattern_pass"
                        ),
                        "selection_round": selection_round + 1,
                        "pattern_entry_index": selection_round + 1,
                        "pattern_total_available": int(pattern_row["total_available"]),
                    },
                    compare_evidence=compare_evidence,
                )
            )
    return cases


def _latest_runtime_compare_evidence_cases(
    runtime_runs_dir: Path,
) -> list[RuntimeReplayCase]:
    base_dir = runtime_runs_dir / "compare-evidence"
    if not base_dir.exists():
        return []

    cases: list[RuntimeReplayCase] = []
    for path in sorted(base_dir.glob("*/compare_evidence.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue

        comparisons = [dict(item) for item in (payload.get("comparisons") or [])]
        successful = [item for item in comparisons if item.get("fetch_succeeded")]
        if len(successful) < 2:
            continue

        candidate_by_key = {
            str(item.get("candidate_key") or ""): item
            for item in successful
            if str(item.get("candidate_key") or "")
        }
        matches = [dict(item) for item in (payload.get("matches") or [])]
        top_match = matches[0] if matches else None
        strongest_match_score = float(
            (payload.get("summary") or {}).get("strongest_match_score")
            or payload.get("strongest_match_score")
            or (top_match.get("score") if top_match else 0.0)
        )
        if strongest_match_score < _MIN_NATIVE_COMPARE_ORIGIN_MATCH_SCORE:
            continue

        top_candidates: list[dict[str, Any]] = []
        if top_match is not None:
            left_key = str(top_match.get("left_candidate_key") or "")
            right_key = str(top_match.get("right_candidate_key") or "")
            if left_key and left_key in candidate_by_key:
                top_candidates.append(candidate_by_key[left_key])
            if right_key and right_key in candidate_by_key and right_key != left_key:
                top_candidates.append(candidate_by_key[right_key])

        if len(top_candidates) < 2:
            top_candidates = successful[:2]

        source_urls = tuple(
            sorted(str(item.get("submitted_url") or item.get("normalized_url") or "") for item in top_candidates)
        )
        candidate_keys = tuple(sorted(str(item.get("candidate_key") or "") for item in top_candidates))
        if not all(source_urls) or not all(candidate_keys):
            continue

        artifact_id = str(payload.get("artifact_id") or path.parent.name)
        saved_at = str(payload.get("saved_at") or ((payload.get("summary") or {}).get("saved_at") or ""))
        store_pair = _normalize_identity_values(
            [str(item.get("store_key") or "") for item in top_candidates]
        )
        product_family_pair = _candidate_family_pair(candidate_keys)
        compare_evidence = {
            "submitted_inputs": list(payload.get("submitted_inputs") or []),
            "zip_code": str(payload.get("zip_code") or "00000"),
            "submitted_count": int(payload.get("submitted_count") or len(payload.get("submitted_inputs") or [])),
            "resolved_count": int(payload.get("resolved_count") or len(successful)),
            "comparisons": comparisons,
            "matches": matches,
            "recommended_next_step_hint": dict(payload.get("recommended_next_step_hint") or {}),
            "risk_notes": list(payload.get("risk_notes") or []),
            "risk_note_items": list(payload.get("risk_note_items") or []),
            "successful_candidate_count": int(
                (payload.get("summary") or {}).get("successful_candidate_count")
                or payload.get("successful_candidate_count")
                or len(successful)
            ),
            "strongest_match_score": strongest_match_score,
        }
        compare_label = str(((payload.get("summary") or {}).get("headline")) or "runtime compare evidence")
        cases.append(
            RuntimeReplayCase(
                artifact_id=artifact_id,
                label=f"runtime_compare:{compare_label}",
                source_anchor="compare_preview",
                source_summary_path=str(path),
                source_metadata={
                    "saved_at": saved_at,
                    "artifact_id": artifact_id,
                    "artifact_kind": str(payload.get("artifact_kind") or "compare_evidence"),
                    "non_seeded": True,
                    "source_kind": "runtime_compare_evidence_package",
                    "pattern_key": _pattern_key(source_urls, candidate_keys),
                    "source_url_pair": list(source_urls),
                    "store_pair": list(store_pair),
                    "candidate_pair": list(candidate_keys),
                    "product_family_pair": list(product_family_pair),
                },
                compare_evidence=compare_evidence,
            )
        )
    return cases


def _latest_runtime_task_cases(runtime_runs_dir: Path) -> list[RuntimeReplayCase]:
    latest_by_pattern: dict[tuple[str, str, str, str | None], tuple[str, Path, dict[str, Any]]] = {}
    pattern_counts: Counter[tuple[str, str, str, str | None]] = Counter()
    for path in runtime_runs_dir.joinpath("watch-tasks").rglob("task_run_summary.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        run = dict(payload.get("run") or {})
        target = dict(payload.get("target") or {})
        pattern = (
            str(target.get("store_key") or ""),
            str(target.get("submitted_url") or ""),
            str(run.get("status") or ""),
            run.get("error_code"),
        )
        if not pattern[0] or not pattern[1]:
            continue
        pattern_counts[pattern] += 1
        saved_at = str(run.get("finished_at") or run.get("started_at") or "")
        current = latest_by_pattern.get(pattern)
        if current is None or saved_at > current[0]:
            latest_by_pattern[pattern] = (saved_at, path, payload)

    cases: list[RuntimeReplayCase] = []
    for (_, path, payload) in sorted(latest_by_pattern.values(), key=lambda item: item[0], reverse=True):
        task = dict(payload.get("task") or {})
        target = dict(payload.get("target") or {})
        run = dict(payload.get("run") or {})
        observation = dict(payload.get("observation") or {})
        store_key = str(target.get("store_key") or "")
        submitted_url = str(target.get("submitted_url") or "")
        run_status = str(run.get("status") or "")
        error_code = str(run.get("error_code") or "")
        observed_at = str((observation.get("observed_at") or run.get("finished_at") or run.get("started_at") or ""))
        action = "create_watch_task"
        reason_code = "single_resolved_candidate"
        summary = "Only one runtime task candidate is available, so recommendation must stay in abstention."
        successful_candidate_count = 1 if observation else 0
        if not observation:
            action = "retry_compare"
            reason_code = "no_successful_candidates"
            summary = "The runtime task does not currently have enough deterministic evidence to support a recommendation call."
        brand_hint = None
        size_hint = str(observation.get("unit_price_raw") or "") or None
        comparisons = [
            {
                "submitted_url": submitted_url,
                "supported": True,
                "store_key": store_key,
                "normalized_url": str(target.get("normalized_url") or submitted_url),
                "fetch_succeeded": bool(observation),
                "error_code": error_code or None,
                "candidate_key": str(target.get("product_url") or submitted_url),
                "brand_hint": brand_hint,
                "size_hint": size_hint,
                "offer": (
                    _observation_offer(
                        title=str(observation.get("title_snapshot") or submitted_url),
                        url=str(observation.get("source_url") or submitted_url),
                        store_key=store_key,
                        product_key=str(run.get("engine_product_key") or submitted_url),
                        listed_price=(float(observation.get("listed_price")) if observation.get("listed_price") is not None else None),
                        observed_at=observed_at,
                        zip_code=str(task.get("zip_code") or "00000"),
                        original_price=(float(observation.get("original_price")) if observation.get("original_price") is not None else None),
                        unit_price_raw=size_hint,
                        brand_hint=brand_hint,
                    )
                    if observation
                    else None
                ),
            }
        ]
        compare_evidence = {
            "submitted_inputs": [submitted_url],
            "zip_code": str(task.get("zip_code") or "00000"),
            "submitted_count": 1,
            "resolved_count": 1 if observation else 0,
            "comparisons": comparisons,
            "matches": [],
            "recommended_next_step_hint": {
                "action": action,
                "reason_code": reason_code,
                "summary": summary,
                "successful_candidate_count": successful_candidate_count,
                "strongest_match_score": 0.0,
            },
            "risk_notes": [
                "This case is reconstructed from a runtime watch-task summary for internal evaluation only.",
                f"Runtime status was `{run_status}` with error `{error_code or 'none'}`.",
            ],
            "risk_note_items": [
                {
                    "code": "runtime_task_summary_import",
                    "message": "Derived from a runtime watch-task summary for internal evaluation only.",
                },
                {
                    "code": f"runtime_status_{run_status}",
                    "message": f"Runtime status was `{run_status}` with error `{error_code or 'none'}`.",
                },
            ],
            "successful_candidate_count": successful_candidate_count,
            "strongest_match_score": 0.0,
        }
        cases.append(
            RuntimeReplayCase(
                artifact_id=_stable_runtime_artifact_id(path),
                label=f"runtime_task:{store_key}:{run_status}",
                source_anchor="watch_task_run_summary",
                source_summary_path=str(path),
                source_metadata={
                    "task_id": str(task.get("id") or ""),
                    "store_key": store_key,
                    "run_status": run_status,
                    "error_code": error_code or None,
                    "pattern_occurrences": pattern_counts[(store_key, submitted_url, run_status, run.get("error_code"))],
                    "delivery_event_count": len(payload.get("delivery_events") or []),
                    "non_seeded": True,
                },
                compare_evidence=compare_evidence,
            )
        )
    return cases


def reset_recommendation_evaluation_workspace(workspace: Path | str) -> None:
    workspace_path = Path(workspace)
    if workspace_path.exists():
        last_error: OSError | None = None
        for _ in range(3):
            try:
                shutil.rmtree(workspace_path)
                last_error = None
                break
            except OSError as exc:
                last_error = exc
                time.sleep(0.2)
        if last_error is not None and workspace_path.exists():
            raise last_error


def _write_replay_artifacts(
    service: ProductService,
    *,
    artifact_id: str,
    label: str,
    compare_evidence: dict[str, Any],
    source_anchor: str,
    source_summary_path: str,
    source_metadata: dict[str, Any],
    corpus_origin: str,
    monitoring_input_profile: str,
    review_seed_suggestion: str,
    deterministic_truth_note: str,
) -> dict[str, Any]:
    compare_payload = service._build_compare_evidence_payload(
        package_id=artifact_id,
        compare_evidence=compare_evidence,
    )
    compare_summary = dict(compare_payload.get("summary") or {})
    source_runtime_context = {
        "surface_anchor": source_anchor,
        "summary_path": source_summary_path,
        **source_metadata,
        "corpus_origin": corpus_origin,
    }
    compare_payload["source_runtime_context"] = source_runtime_context
    compare_summary["source_runtime_context"] = source_runtime_context
    compare_summary["corpus_origin"] = corpus_origin
    compare_payload["summary"] = compare_summary

    shadow_payload = service._build_compare_recommendation_shadow_payload(
        package_id=artifact_id,
        compare_evidence=compare_evidence,
    )
    shadow_payload["surface_anchor"] = source_anchor
    shadow_payload["source_runtime_context"] = source_runtime_context

    monitoring = dict(shadow_payload.get("monitoring") or {})
    monitoring["input_profile"] = monitoring_input_profile
    monitoring["corpus_origin"] = corpus_origin
    monitoring["review_seed_suggestion"] = review_seed_suggestion
    shadow_payload["monitoring"] = monitoring

    deterministic_truth_anchor = dict(shadow_payload.get("deterministic_truth_anchor") or {})
    deterministic_truth_anchor["note"] = deterministic_truth_note
    shadow_payload["deterministic_truth_anchor"] = deterministic_truth_anchor

    recommendation = dict(shadow_payload.get("shadow_recommendation") or {})
    recommendation["uncertainty_notes"] = list(
        dict.fromkeys(
            [
                *list(recommendation.get("uncertainty_notes") or []),
                f"Source runtime summary: {source_summary_path}",
            ]
        )
    )
    shadow_payload["shadow_recommendation"] = recommendation

    artifact_dir = service._prepare_compare_evidence_dir(artifact_id)
    compare_path = artifact_dir / "compare_evidence.json"
    compare_html_path = artifact_dir / "compare_evidence.html"
    shadow_path = artifact_dir / "recommendation_shadow.json"
    shadow_html_path = artifact_dir / "recommendation_shadow.html"

    existing_shadow = service._read_recommendation_shadow_payload(artifact_id)
    if existing_shadow:
        existing_review = dict(existing_shadow.get("review") or {})
        if existing_review:
            shadow_payload["review"] = existing_review
        existing_monitoring = dict(existing_shadow.get("monitoring") or {})
        monitoring = dict(shadow_payload.get("monitoring") or {})
        for key in (
            "review_state",
            "review_reason_code",
            "outcome_category",
            "agreement_bucket",
            "review_recorded_at",
        ):
            if key in existing_monitoring:
                monitoring[key] = existing_monitoring[key]
        shadow_payload["monitoring"] = monitoring
        if existing_shadow.get("review_log_path"):
            shadow_payload["review_log_path"] = existing_shadow.get("review_log_path")
        if existing_shadow.get("public_contract_bridge"):
            shadow_payload["public_contract_bridge"] = existing_shadow.get("public_contract_bridge")

    latest_review_record: dict[str, Any] | None = None
    for record in service._load_recommendation_shadow_review_records():
        if str(record.get("artifact_id") or "") == artifact_id:
            latest_review_record = record
    if latest_review_record is not None:
        shadow_payload["review"] = {
            "state": latest_review_record.get("decision") or "pending_internal_review",
            "owner": latest_review_record.get("reviewer"),
            "reason_code": latest_review_record.get("reason_code"),
            "notes": latest_review_record.get("notes"),
            "observed_outcome": latest_review_record.get("observed_outcome"),
            "recorded_at": latest_review_record.get("recorded_at"),
            "outcome_category": latest_review_record.get("outcome_category"),
            "follow_up_action": latest_review_record.get("follow_up_action"),
        }
        monitoring = dict(shadow_payload.get("monitoring") or {})
        monitoring["review_state"] = latest_review_record.get("decision") or "pending_internal_review"
        monitoring["review_reason_code"] = latest_review_record.get("reason_code")
        monitoring["outcome_category"] = latest_review_record.get("outcome_category")
        monitoring["agreement_bucket"] = latest_review_record.get("agreement_bucket")
        monitoring["review_recorded_at"] = latest_review_record.get("recorded_at")
        shadow_payload["monitoring"] = monitoring
        shadow_payload["review_log_path"] = str(service._recommendation_shadow_review_log_path())

    compare_path.write_text(json.dumps(compare_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    compare_html_path.write_text(service._render_compare_evidence_html(compare_payload), encoding="utf-8")
    shadow_path.write_text(json.dumps(shadow_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    shadow_html_path.write_text(service._render_compare_recommendation_shadow_html(shadow_payload), encoding="utf-8")
    return {
        "artifact_id": artifact_id,
        "label": label,
        "surface_anchor": source_anchor,
        "corpus_origin": corpus_origin,
        "source_summary_path": source_summary_path,
        "review_seed_suggestion": review_seed_suggestion,
        "artifact_path": str(compare_path),
        "shadow_artifact_path": str(shadow_path),
    }


def _write_runtime_case_artifacts(
    service: ProductService,
    *,
    case: RuntimeReplayCase,
) -> dict[str, Any]:
    review_seed_suggestion = "correct_abstention"
    if case.source_anchor == "watch_group_run_summary":
        if str(case.source_metadata.get("triggered_by") or "") == "smoke":
            review_seed_suggestion = "speak_when_should_abstain"
        elif (
            str(
                service._build_compare_recommendation_shadow_payload(
                    package_id=case.artifact_id,
                    compare_evidence=case.compare_evidence,
                ).get("status")
                or ""
            )
            == "issued"
        ):
            review_seed_suggestion = "correct_verdict"
    elif case.source_anchor == "watch_task_run_summary":
        run_status = str(case.source_metadata.get("run_status") or "")
        pattern_occurrences = int(case.source_metadata.get("pattern_occurrences") or 0)
        delivery_event_count = int(case.source_metadata.get("delivery_event_count") or 0)
        if run_status == "succeeded" and pattern_occurrences >= 20 and delivery_event_count >= 1:
            review_seed_suggestion = "abstain_when_should_speak"

    return _write_replay_artifacts(
        service,
        artifact_id=case.artifact_id,
        label=case.label,
        compare_evidence=case.compare_evidence,
        source_anchor=case.source_anchor,
        source_summary_path=case.source_summary_path,
        source_metadata=case.source_metadata,
        corpus_origin="non_seeded_runtime_pattern",
        monitoring_input_profile=case.source_anchor,
        review_seed_suggestion=review_seed_suggestion,
        deterministic_truth_note=(
            "This shadow artifact is advisory-only for internal evaluation and is derived from a repo-local runtime summary. "
            "It remains subordinate to deterministic evidence and must stay out of public surfaces."
        ),
    )


async def seed_fixture_replay_corpus(workspace: Path | str) -> dict[str, Any]:
    service = await create_recommendation_evaluation_service(workspace)
    runs_dir = service.settings.RUNS_DIR
    created_artifacts: list[dict[str, Any]] = []

    for case in seeded_replay_cases():
        artifact = await service.create_compare_evidence_package(
            submitted_urls=list(case.submitted_urls),
            zip_code=case.zip_code,
        )
        created_artifacts.append(
            {
                "case_id": case.case_id,
                "label": case.label,
                "artifact_id": artifact["artifact_id"],
                "artifact_path": artifact["artifact_path"],
                "html_path": artifact["html_path"],
                "recommended_next_step_hint": artifact["recommended_next_step_hint"],
            }
        )

    skipped_dir = runs_dir / "compare-evidence" / _SKIPPED_ARTIFACT_ID
    skipped_dir.mkdir(parents=True, exist_ok=True)
    (skipped_dir / "compare_evidence.json").write_text(
        json.dumps(
            {
                "artifact_id": _SKIPPED_ARTIFACT_ID,
                "summary": {
                    "artifact_id": _SKIPPED_ARTIFACT_ID,
                    "saved_at": datetime.utcnow().isoformat(),
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    invalid_dir = runs_dir / "compare-evidence" / _INVALID_ARTIFACT_ID
    invalid_dir.mkdir(parents=True, exist_ok=True)
    (invalid_dir / "compare_evidence.json").write_text(
        json.dumps(
            {
                "artifact_id": _INVALID_ARTIFACT_ID,
                "summary": {
                    "artifact_id": _INVALID_ARTIFACT_ID,
                    "saved_at": datetime.utcnow().isoformat(),
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (invalid_dir / "recommendation_shadow.json").write_text("{not-json", encoding="utf-8")

    return {
        "seeded_case_count": len(created_artifacts),
        "seeded_cases": created_artifacts,
        "skipped_artifact_id": _SKIPPED_ARTIFACT_ID,
        "invalid_artifact_id": _INVALID_ARTIFACT_ID,
        "runs_dir": str(runs_dir),
    }


async def import_runtime_replay_corpus(
    workspace: Path | str,
    *,
    runtime_runs_dir: Path | str = DEFAULT_RUNTIME_RUNS_DIR,
    service: ProductService | None = None,
) -> dict[str, Any]:
    local_service = service or await create_recommendation_evaluation_service(workspace)
    runtime_dir = Path(runtime_runs_dir)
    group_cases = _latest_runtime_group_cases(runtime_dir)
    task_cases = _latest_runtime_task_cases(runtime_dir)
    imported_cases: list[dict[str, Any]] = []
    for case in [*group_cases, *task_cases]:
        imported_cases.append(_write_runtime_case_artifacts(local_service, case=case))

    return {
        "runtime_runs_dir": str(runtime_dir),
        "non_seeded_case_count": len(imported_cases),
        "group_case_count": len(group_cases),
        "task_case_count": len(task_cases),
        "cases": imported_cases,
    }


async def harvest_native_compare_origin_corpus(
    workspace: Path | str,
    *,
    runtime_runs_dir: Path | str = DEFAULT_RUNTIME_RUNS_DIR,
    service: ProductService | None = None,
    repeat_budget_per_pattern: int = _DEFAULT_NATIVE_COMPARE_ORIGIN_REPEAT_BUDGET,
) -> dict[str, Any]:
    local_service = service or await create_recommendation_evaluation_service(workspace)
    runtime_dir = Path(runtime_runs_dir)
    compare_cases = _latest_runtime_compare_evidence_cases(runtime_dir)
    group_cases = _latest_runtime_group_cases(runtime_dir, per_pattern_limit=None)
    source_cases = compare_cases if compare_cases else group_cases
    selected_cases, diversity = _select_native_compare_origin_cases(
        source_cases,
        repeat_budget_per_pattern=repeat_budget_per_pattern,
    )
    harvested_cases: list[dict[str, Any]] = []

    for case in selected_cases:
        submitted_urls = list(case.compare_evidence.get("submitted_inputs") or [])
        zip_code = str(case.compare_evidence.get("zip_code") or "98004")
        if len(submitted_urls) < 2:
            continue
        compare_result = await local_service.compare_product_urls(
            submitted_urls=submitted_urls,
            zip_code=zip_code,
        )
        compare_evidence = dict(compare_result.get("compare_evidence") or {})
        if not compare_evidence:
            continue
        artifact_id = str(uuid5(NAMESPACE_URL, f"{case.source_summary_path}::native_compare_origin"))
        shadow_status = str(
            local_service._build_compare_recommendation_shadow_payload(
                package_id=artifact_id,
                compare_evidence=compare_evidence,
            ).get("status")
            or ""
        )
        harvested_cases.append(
            _write_replay_artifacts(
                local_service,
                artifact_id=artifact_id,
                label=case.label,
                compare_evidence=compare_evidence,
                source_anchor="compare_preview",
                source_summary_path=case.source_summary_path,
                source_metadata=case.source_metadata,
                corpus_origin="native_compare_origin",
                monitoring_input_profile="compare_preview_only",
                review_seed_suggestion=(
                    "correct_abstention" if shadow_status == "abstained" else "correct_verdict"
                ),
                deterministic_truth_note=(
                    "This shadow artifact was generated through the native compare pipeline from repo-local runtime-discovered URL pairs. "
                    "It is compare-origin evidence for internal evaluation only and must stay out of public surfaces."
                ),
            )
        )

    return {
        "runtime_runs_dir": str(runtime_dir),
        "source_case_kind": "runtime_compare_evidence_package" if compare_cases else "runtime_group_summary_fallback",
        "available_source_case_count": len(source_cases),
        "native_compare_origin_case_count": len(harvested_cases),
        "source_diversity": diversity,
        "cases": harvested_cases,
    }


def _campaign_monitoring_dir(runs_dir: Path) -> Path:
    return runs_dir / "compare-evidence" / "_shadow-monitoring"


def _campaign_report_paths(runs_dir: Path) -> tuple[Path, Path]:
    monitoring_dir = _campaign_monitoring_dir(runs_dir)
    return (
        monitoring_dir / _CAMPAIGN_REPORT_NAME,
        monitoring_dir / _CAMPAIGN_REPORT_MD_NAME,
    )


def _skip_reason_buckets(replay_manifest: dict[str, Any]) -> dict[str, int]:
    buckets: Counter[str] = Counter()
    for entry in replay_manifest.get("entries", []):
        if not entry.get("included") and entry.get("skip_reason"):
            buckets[str(entry["skip_reason"])] += 1
    return dict(sorted(buckets.items()))


def _pending_review_rows(replay_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    pending_rows: list[dict[str, Any]] = []
    for entry in replay_manifest.get("entries", []):
        if not entry.get("included"):
            continue
        if str(entry.get("review_state") or "") != "pending_internal_review":
            continue
        replay_source = dict(entry.get("replay_source") or {})
        monitoring = dict(entry.get("monitoring") or {})
        pending_rows.append(
            {
                "artifact_id": entry.get("artifact_id"),
                "surface_anchor": entry.get("surface_anchor"),
                "verdict": entry.get("verdict"),
                "status": entry.get("status"),
                "review_seed_suggestion": monitoring.get("review_seed_suggestion"),
                "shadow_artifact_path": replay_source.get("shadow_artifact_path"),
                "shadow_html_path": replay_source.get("shadow_html_path"),
            }
        )
    return pending_rows


def _infer_corpus_source_buckets(replay_manifest: dict[str, Any]) -> dict[str, int]:
    buckets: Counter[str] = Counter()
    for entry in replay_manifest.get("entries", []):
        if not entry.get("included"):
            continue
        monitoring = dict(entry.get("monitoring") or {})
        replay_source = dict(entry.get("replay_source") or {})
        corpus_origin = str(monitoring.get("corpus_origin") or "").strip()
        surface_anchor = str(entry.get("surface_anchor") or replay_source.get("surface_anchor") or "").strip()

        bucket: str | None = None
        if corpus_origin == "native_compare_origin":
            bucket = "native_compare_origin"
        elif corpus_origin == "non_seeded_runtime_pattern":
            if surface_anchor == "watch_group_run_summary":
                bucket = "non_seeded_watch_group_runtime"
            elif surface_anchor == "watch_task_run_summary":
                bucket = "non_seeded_watch_task_runtime"

        if bucket is None:
            if surface_anchor == "compare_preview":
                bucket = "seeded_compare_origin"
            elif surface_anchor == "watch_group_run_summary":
                bucket = "non_seeded_watch_group_runtime"
            elif surface_anchor == "watch_task_run_summary":
                bucket = "non_seeded_watch_task_runtime"

        if bucket is not None:
            buckets[bucket] += 1
    return dict(sorted(buckets.items()))


def _load_runtime_replay_case_from_manifest_entry(
    entry: dict[str, Any],
) -> RuntimeReplayCase | None:
    replay_source = dict(entry.get("replay_source") or {})
    compare_evidence_path = str(replay_source.get("compare_evidence_path") or "").strip()
    if not compare_evidence_path:
        return None
    compare_path = Path(compare_evidence_path)
    if not compare_path.is_file():
        return None
    try:
        compare_payload = json.loads(compare_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    source_runtime_context = dict(compare_payload.get("source_runtime_context") or {})
    return RuntimeReplayCase(
        artifact_id=str(entry.get("artifact_id") or ""),
        label=str(entry.get("label") or compare_payload.get("artifact_id") or ""),
        source_anchor=str(entry.get("surface_anchor") or replay_source.get("surface_anchor") or ""),
        source_summary_path=str(source_runtime_context.get("summary_path") or ""),
        source_metadata=source_runtime_context,
        compare_evidence=compare_payload,
    )


def _selected_native_compare_origin_diversity_from_manifest(
    replay_manifest: dict[str, Any],
) -> dict[str, Any] | None:
    selected_cases: list[RuntimeReplayCase] = []
    for entry in replay_manifest.get("entries", []):
        if not entry.get("included"):
            continue
        monitoring = dict(entry.get("monitoring") or {})
        if str(monitoring.get("corpus_origin") or "") != "native_compare_origin":
            continue
        case = _load_runtime_replay_case_from_manifest_entry(dict(entry))
        if case is not None:
            selected_cases.append(case)
    if not selected_cases:
        return None
    return _native_compare_origin_diversity_summary(
        selected_cases,
        selection_mode="selected_campaign_native_compare_origin",
        repeat_budget_per_pattern=_DEFAULT_NATIVE_COMPARE_ORIGIN_REPEAT_BUDGET,
        selected_cases=selected_cases,
    )


def _render_campaign_markdown(report: dict[str, Any]) -> str:
    summary = dict(report.get("summary") or {})
    summary_source_diversity = dict(summary.get("source_diversity") or {})
    first_pass_distribution = dict(summary.get("first_pass_distribution") or {})
    corpus_source_buckets = dict(report.get("corpus_source_buckets") or {})
    source_diversity = dict(report.get("source_diversity") or {})
    native_diversity = dict(source_diversity.get("native_compare_origin") or {})
    native_selected = dict(source_diversity.get("selected_native_compare_origin") or {})
    native_source_case_kind = str(
        summary_source_diversity.get("native_compare_origin_source_case_kind") or ""
    ).strip()
    verdict_lines = "\n".join(
        f"- `{key}`: {value}" for key, value in first_pass_distribution.items()
    ) or "- none"
    source_lines = "\n".join(
        f"- `{key}`: {value}" for key, value in corpus_source_buckets.items()
    ) or "- none"
    diversity_lines = "- none"
    if native_diversity:
        top_pattern = dict(native_diversity.get("top_repeated_pattern") or {})
        top_pair = ", ".join(top_pattern.get("store_pair") or []) or "n/a"
        diversity_lines = "\n".join(
            [
                f"- Available native compare-origin cases: **{native_diversity.get('available_case_count', 0)}**",
                f"- Selected for campaign: **{native_diversity.get('selected_case_count', 0)}**",
                f"- Unique patterns: **{native_diversity.get('unique_pattern_count', 0)}**",
                f"- Unique store pairs: **{native_diversity.get('unique_store_pair_count', 0)}**",
                f"- Unique source-url pair families: **{native_diversity.get('unique_source_url_pair_family_count', 0)}**",
                f"- Breadth profile: `{native_diversity.get('breadth_profile')}`",
                f"- Concentration risk: `{native_diversity.get('concentration_risk')}`",
                f"- Ceiling signal: `{native_diversity.get('ceiling_signal')}`",
                (
                    "- Top repeated pattern: "
                    f"`{top_pair}` · count=**{top_pattern.get('case_count', 0)}** "
                    f"· share=**{top_pattern.get('share_of_available_cases', 0)}**"
                ),
                (
                    "- Selection strategy: "
                    f"`{native_diversity.get('selection_mode')}` "
                    f"(repeat_budget_per_pattern={native_diversity.get('repeat_budget_per_pattern', 0)})"
                ),
            ]
        )
        if native_source_case_kind:
            diversity_lines += (
                "\n"
                f"- Native source case kind: `{native_source_case_kind}`"
            )
        if native_selected and native_selected.get("available_pattern_counts"):
            diversity_lines += "\n- Selected native breadth snapshot:"
            for item in native_selected.get("available_pattern_counts") or []:
                store_pair = ", ".join(item.get("store_pair") or []) or "n/a"
                diversity_lines += (
                    "\n"
                    f"  - `{store_pair}` · count={item.get('case_count', 0)} · "
                    f"share={item.get('share_of_available_cases', 0)}"
                )
    pending_lines = "\n".join(
        f"- `{item['artifact_id']}` · verdict=`{item['verdict']}` · status=`{item['status']}`"
        for item in report.get("pending_review_artifacts", [])
    ) or "- none"
    blocker_lines = "\n".join(
        f"- {item}" for item in report.get("launch_blockers", [])
    ) or "- none"
    evidence_lines = "\n".join(
        f"- {key}: `{value}`" for key, value in report.get("artifact_paths", {}).items()
    )
    return "\n".join(
        [
            "# Recommendation Replay Campaign v1",
            "",
            f"- Generated at: `{report['generated_at']}`",
            f"- Corpus source: `{report['corpus_source']}`",
            f"- Readiness verdict: `{report['readiness_verdict']}`",
            "",
            "## Summary",
            "",
            f"- Total replay items: **{summary.get('total_replay_items', 0)}**",
            f"- Issued verdict count: **{summary.get('issued_verdict_count', 0)}**",
            f"- Abstention count: **{summary.get('abstention_count', 0)}**",
            f"- Invalid / skipped count: **{summary.get('invalid_or_skipped_count', 0)}**",
            "",
            "## First-pass distribution",
            "",
            verdict_lines,
            "",
            "## Corpus source buckets",
            "",
            source_lines,
            "",
            "## Native compare-origin diversity",
            "",
            diversity_lines,
            "",
            "## Pending internal review",
            "",
            pending_lines,
            "",
            "## Why this is still not launch evidence",
            "",
            blocker_lines,
            "",
            "## Artifact paths",
            "",
            evidence_lines,
            "",
            "## Boundary note",
            "",
            report["boundary_note"],
            "",
        ]
    )




async def generate_recommendation_replay_campaign(
    workspace: Path | str,
    *,
    seed_fixture_corpus: bool = False,
    import_runtime_corpus: bool = False,
    harvest_native_compare_origin: bool = False,
    reset_workspace: bool = False,
    runtime_runs_dir: Path | str = DEFAULT_RUNTIME_RUNS_DIR,
    native_compare_repeat_budget: int = _DEFAULT_NATIVE_COMPARE_ORIGIN_REPEAT_BUDGET,
) -> dict[str, Any]:
    if reset_workspace or seed_fixture_corpus:
        reset_recommendation_evaluation_workspace(workspace)
    seed_result: dict[str, Any] | None = None
    non_seeded_ingest_result: dict[str, Any] | None = None
    native_compare_origin_result: dict[str, Any] | None = None
    if seed_fixture_corpus:
        seed_result = await seed_fixture_replay_corpus(workspace)
    service = await create_recommendation_evaluation_service(workspace)
    if import_runtime_corpus:
        non_seeded_ingest_result = await import_runtime_replay_corpus(
            workspace,
            service=service,
            runtime_runs_dir=runtime_runs_dir,
        )
    if harvest_native_compare_origin:
        native_compare_origin_result = await harvest_native_compare_origin_corpus(
            workspace,
            service=service,
            runtime_runs_dir=runtime_runs_dir,
            repeat_budget_per_pattern=native_compare_repeat_budget,
        )
    native_source_case_kind = (
        str(native_compare_origin_result.get("source_case_kind") or "")
        if native_compare_origin_result is not None
        else ""
    )

    replay_manifest = await service.create_recommendation_replay_manifest()
    monitoring_summary = await service.create_recommendation_shadow_monitoring_summary()
    runs_dir = service.settings.RUNS_DIR
    report_json_path, report_md_path = _campaign_report_paths(runs_dir)
    report_json_path.parent.mkdir(parents=True, exist_ok=True)

    monitoring = dict(monitoring_summary.get("summary") or {})
    replay = dict(replay_manifest.get("summary") or {})
    pending_review_artifacts = _pending_review_rows(replay_manifest)
    available_native_compare_cases = _latest_runtime_group_cases(
        Path(runtime_runs_dir),
        per_pattern_limit=None,
    )
    available_native_compare_diversity = _native_compare_origin_diversity_summary(
        available_native_compare_cases,
        selection_mode="breadth_first_distinct_patterns",
        repeat_budget_per_pattern=native_compare_repeat_budget,
        selected_cases=[],
    )
    if native_compare_origin_result is not None and native_compare_origin_result.get("source_diversity"):
        available_native_compare_diversity = dict(
            native_compare_origin_result.get("source_diversity") or {}
        )
    selected_native_compare_diversity = _selected_native_compare_origin_diversity_from_manifest(
        replay_manifest
    )
    if (
        native_compare_origin_result is None
        and selected_native_compare_diversity is not None
    ):
        available_native_compare_diversity["selected_case_count"] = selected_native_compare_diversity.get(
            "available_case_count", 0
        )
        available_native_compare_diversity["selected_unique_pattern_count"] = (
            selected_native_compare_diversity.get("unique_pattern_count", 0)
        )
        available_native_compare_diversity["selected_repeat_count"] = 0
        available_native_compare_diversity["dropped_repeat_count"] = max(
            0,
            int(available_native_compare_diversity.get("available_case_count", 0))
            - int(selected_native_compare_diversity.get("available_case_count", 0)),
        )
    corpus_source_buckets: dict[str, int] = {}
    if seed_result is not None:
        corpus_source_buckets["seeded_compare_origin"] = int(
            seed_result.get("ingested_artifact_count", seed_result.get("seeded_case_count", 0))
        )
    if native_compare_origin_result is not None:
        native_compare_count = int(native_compare_origin_result.get("native_compare_origin_case_count", 0))
        if native_compare_count:
            corpus_source_buckets["native_compare_origin"] = native_compare_count
    if non_seeded_ingest_result is not None:
        group_case_count = int(non_seeded_ingest_result.get("group_case_count", 0))
        task_case_count = int(non_seeded_ingest_result.get("task_case_count", 0))
        if group_case_count:
            corpus_source_buckets["non_seeded_watch_group_runtime"] = group_case_count
        if task_case_count:
            corpus_source_buckets["non_seeded_watch_task_runtime"] = task_case_count
    if not corpus_source_buckets:
        corpus_source_buckets = _infer_corpus_source_buckets(replay_manifest)
    if not corpus_source_buckets:
        corpus_source = "existing_runtime_artifacts"
    elif len(corpus_source_buckets) == 1:
        corpus_source = next(iter(corpus_source_buckets))
    else:
        corpus_source = "mixed_internal_corpus"
    launch_blockers = [
        "Recommendation remains blocked from public launch until deeper replay volume, adjudication history, and launch-readiness review exist together.",
        "Even with non-seeded runtime ingestion, reconstructed internal artifacts are still not the same thing as launch-grade recommendation calibration.",
        "The current evaluation corpus is still repo-local and maintainer-scoped, not a public product trust signal.",
    ]
    if seed_result is not None:
        launch_blockers.insert(
            0,
            "Prompt 7 still contains seeded repo-owned artifacts, which are useful for workflow proof but not sufficient launch evidence on their own.",
        )
    if native_compare_origin_result is not None:
        launch_blockers.insert(
            0,
            "The native compare-origin expansion now measures source diversity directly, but the resulting evidence is still maintainer-scoped and must stay internal-only.",
        )
    if native_source_case_kind == "runtime_group_summary_fallback":
        launch_blockers.insert(
            0,
            "The native compare-origin lane still had to fall back to reconstructed watch-group summaries because no runtime compare-evidence packages were available yet.",
        )
    if available_native_compare_diversity.get("concentration_risk") == "high":
        launch_blockers.insert(
            0,
            "The available native compare-origin runtime pool is still highly concentrated, so deeper history from the same pair cannot be mistaken for broader recommendation coverage.",
        )
    if available_native_compare_diversity.get("ceiling_signal") == "single_pattern_runtime_ceiling":
        launch_blockers.insert(
            0,
            "The current repo-local native compare-origin pool has collapsed to a single repeated pattern, so additional internal harvesting mostly adds depth rather than breadth.",
        )
    if non_seeded_ingest_result is not None:
        launch_blockers.insert(
            0,
            "The non-seeded expansion currently comes from reconstructed runtime task/group summaries, not native compare-preview evidence packages.",
        )
    if replay.get("total_candidates", 0) <= 12:
        launch_blockers.append(
            "The replay batch is still small enough that it only proves workflow continuity, not robust recommendation quality."
        )
    if monitoring.get("reviewed_count", 0) <= 3:
        launch_blockers.append(
            "Maintainer adjudication depth is still thin, so disagreement patterns remain early rather than launch-grade."
        )
    if replay.get("total_candidates", 0) <= 0:
        launch_blockers.insert(
            0,
            "No replayable compare-evidence corpus exists in the selected workspace yet.",
        )
    review_log_path = monitoring_summary.get("review_log_path")
    if review_log_path and not Path(str(review_log_path)).exists():
        review_log_path = None

    report = {
        "artifact_kind": "recommendation_replay_campaign",
        "campaign_contract_version": "v1",
        "mode": "internal_only_evaluation",
        "visibility": "internal_only",
        "generated_at": datetime.utcnow().isoformat(),
        "workspace": str(Path(workspace)),
        "runs_dir": str(runs_dir),
        "corpus_source": corpus_source,
        "corpus_source_buckets": corpus_source_buckets,
        "seed_result": seed_result,
        "native_compare_origin_result": native_compare_origin_result,
        "non_seeded_ingest_result": non_seeded_ingest_result,
        "readiness_verdict": "not_launch_ready",
        "boundary_note": (
            "This campaign proves that DealWatch can seed, harvest native compare-origin evidence, ingest non-seeded runtime evidence, replay, review, and summarize "
            "internal recommendation artifacts without leaking them into public surfaces. It does not prove recommendation is ready for public launch."
        ),
        "summary": {
            "total_replay_items": replay.get("total_candidates", 0),
            "replay_included_count": replay.get("included_count", 0),
            "issued_verdict_count": monitoring.get("issued_verdict_count", 0),
            "abstention_count": monitoring.get("abstention_count", 0),
            "invalid_or_skipped_count": monitoring.get("invalid_or_skipped_count", 0),
            "invalid_artifact_count": monitoring.get("invalid_artifact_count", 0),
            "skipped_artifact_count": monitoring.get("skipped_artifact_count", 0),
            "review_pending_count": monitoring.get("review_pending_count", 0),
            "reviewed_count": monitoring.get("reviewed_count", 0),
            "first_pass_distribution": monitoring.get("verdict_distribution", {}),
            "review_state_buckets": monitoring.get("review_state_buckets", {}),
            "evidence_strength_buckets": monitoring.get("evidence_strength_buckets", {}),
            "disagreement_buckets": monitoring.get("disagreement_buckets", {}),
            "skip_reason_buckets": _skip_reason_buckets(replay_manifest),
            "source_diversity": {
                "native_compare_origin_unique_patterns": available_native_compare_diversity.get(
                    "unique_pattern_count", 0
                ),
                "native_compare_origin_unique_store_pairs": available_native_compare_diversity.get(
                    "unique_store_pair_count", 0
                ),
                "native_compare_origin_unique_source_url_pair_families": available_native_compare_diversity.get(
                    "unique_source_url_pair_family_count", 0
                ),
                "native_compare_origin_top_repeated_pattern_share": available_native_compare_diversity.get(
                    "top_repeated_pattern_share", 0.0
                ),
                "native_compare_origin_breadth_profile": available_native_compare_diversity.get(
                    "breadth_profile"
                ),
                "native_compare_origin_concentration_risk": available_native_compare_diversity.get(
                    "concentration_risk"
                ),
                "native_compare_origin_source_case_kind": native_source_case_kind or None,
            },
        },
        "source_diversity": {
            "native_compare_origin": available_native_compare_diversity,
            "selected_native_compare_origin": selected_native_compare_diversity,
        },
        "pending_review_artifacts": pending_review_artifacts,
        "launch_blockers": launch_blockers,
        "artifact_paths": {
            "replay_manifest_path": replay_manifest.get("artifact_path"),
            "monitoring_summary_path": monitoring_summary.get("artifact_path"),
            "monitoring_summary_html_path": monitoring_summary.get("html_path"),
            "campaign_report_path": str(report_json_path),
            "campaign_report_markdown_path": str(report_md_path),
            "review_log_path": review_log_path,
        },
    }
    report_json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report_md_path.write_text(_render_campaign_markdown(report), encoding="utf-8")
    return report


async def list_pending_recommendation_reviews(workspace: Path | str) -> dict[str, Any]:
    service = await create_recommendation_evaluation_service(workspace)
    replay_manifest = await service.create_recommendation_replay_manifest()
    monitoring_summary = await service.create_recommendation_shadow_monitoring_summary()
    pending = _pending_review_rows(replay_manifest)
    return {
        "artifact_kind": "recommendation_shadow_pending_reviews",
        "workspace": str(Path(workspace)),
        "runs_dir": str(service.settings.RUNS_DIR),
        "pending_count": len(pending),
        "pending_reviews": pending,
        "review_log_path": monitoring_summary.get("review_log_path"),
        "replay_manifest_path": replay_manifest.get("artifact_path"),
        "monitoring_summary_path": monitoring_summary.get("artifact_path"),
    }


def _parse_evidence_ref(spec: str) -> dict[str, str]:
    parts = [part.strip() for part in spec.split("|")]
    if len(parts) != 3 or not all(parts):
        raise ValueError("invalid_evidence_ref")
    return {
        "code": parts[0],
        "label": parts[1],
        "anchor": parts[2],
    }


async def record_recommendation_review(
    workspace: Path | str,
    *,
    artifact_id: str,
    reviewer: str,
    decision: str,
    reason_code: str,
    outcome_category: str,
    observed_outcome: str,
    notes: str | None = None,
    follow_up_action: str | None = None,
    expected_verdict: str | None = None,
    actual_verdict: str | None = None,
    evidence_ref_specs: list[str] | None = None,
) -> dict[str, Any]:
    service = await create_recommendation_evaluation_service(workspace)
    evidence_refs = [_parse_evidence_ref(spec) for spec in (evidence_ref_specs or [])]
    review_record = await service.record_recommendation_shadow_review(
        artifact_id=artifact_id,
        reviewer=reviewer,
        decision=decision,
        reason_code=reason_code,
        outcome_category=outcome_category,
        observed_outcome=observed_outcome,
        notes=notes,
        follow_up_action=follow_up_action,
        expected_verdict=expected_verdict,
        actual_verdict=actual_verdict,
        evidence_refs=evidence_refs,
    )
    replay_manifest = await service.create_recommendation_replay_manifest()
    monitoring_summary = await service.create_recommendation_shadow_monitoring_summary()
    refreshed_campaign = await generate_recommendation_replay_campaign(
        workspace,
        seed_fixture_corpus=False,
    )
    return {
        "review_record": review_record,
        "review_log_path": monitoring_summary.get("review_log_path"),
        "monitoring_summary_path": monitoring_summary.get("artifact_path"),
        "monitoring_summary_html_path": monitoring_summary.get("html_path"),
        "replay_manifest_path": replay_manifest.get("artifact_path"),
        "campaign_report_path": refreshed_campaign.get("artifact_paths", {}).get("campaign_report_path"),
        "campaign_report_markdown_path": refreshed_campaign.get("artifact_paths", {}).get(
            "campaign_report_markdown_path"
        ),
    }
