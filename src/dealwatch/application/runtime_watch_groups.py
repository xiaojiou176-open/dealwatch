from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from dealwatch.domain.enums import HealthStatus, TaskRunStatus
from dealwatch.stores.base_adapter import SkipParse
from dealwatch.persistence.models import (
    DeliveryEvent,
    WatchGroup,
    WatchGroupMember,
    WatchGroupRun,
    WatchTarget,
)


async def collect_watch_group_member_results(
    session: AsyncSession,
    *,
    group: WatchGroup,
    members: list[WatchGroupMember],
    fetch_offer: Callable[[str, str, str], Awaitable[Any | None]],
    fetch_cashback_quote_for_target: Callable[[str, str], Awaitable[dict[str, Any] | None]],
    is_store_binding_enabled: Callable[[AsyncSession, str], Awaitable[bool]],
    normalize_runtime_error: Callable[[Exception], tuple[str, str]],
    logger: Any,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for member in members:
        target = await session.get(WatchTarget, member.watch_target_id)
        if target is None:
            results.append(
                {
                    "member_id": member.id,
                    "status": TaskRunStatus.FAILED.value,
                    "error_code": "watch_target_not_found",
                    "error_message": "watch_target_not_found",
                }
            )
            continue
        if not await is_store_binding_enabled(session, target.store_key):
            results.append(
                {
                    "member_id": member.id,
                    "watch_target_id": target.id,
                    "store_key": target.store_key,
                    "title_snapshot": member.title_snapshot,
                    "candidate_key": member.candidate_key,
                    "status": TaskRunStatus.BLOCKED.value,
                    "error_code": "store_disabled",
                    "error_message": "store_disabled",
                }
            )
            continue

        try:
            offer = await fetch_offer(target.product_url, target.store_key, group.zip_code)
            if offer is None:
                raise ValueError("offer_not_parsed")
            cashback_quote = await fetch_cashback_quote_for_target(target.store_key, target.product_url)
            cashback_amount = 0.0
            if cashback_quote is not None:
                if cashback_quote["rate_type"] == "percent":
                    cashback_amount = round(offer.price * float(cashback_quote["rate_value"]) / 100.0, 2)
                else:
                    cashback_amount = float(cashback_quote["rate_value"])
            effective_price = max(offer.price - cashback_amount, 0.0)
            results.append(
                {
                    "member_id": member.id,
                    "watch_target_id": target.id,
                    "store_key": target.store_key,
                    "title_snapshot": offer.title,
                    "candidate_key": member.candidate_key,
                    "listed_price": offer.price,
                    "effective_price": effective_price,
                    "cashback_amount": cashback_amount,
                    "source_url": offer.url,
                    "observed_at": offer.fetch_at.isoformat(),
                    "status": TaskRunStatus.SUCCEEDED.value,
                    "cashback_quote": cashback_quote,
                }
            )
        except SkipParse as exc:
            results.append(
                {
                    "member_id": member.id,
                    "watch_target_id": target.id,
                    "store_key": target.store_key,
                    "title_snapshot": member.title_snapshot,
                    "candidate_key": member.candidate_key,
                    "status": TaskRunStatus.BLOCKED.value,
                    "error_code": exc.reason.value,
                    "error_message": exc.reason.value,
                }
            )
        except Exception as exc:
            logger.exception("Watch group member run failed.")
            error_code, error_message = normalize_runtime_error(exc)
            results.append(
                {
                    "member_id": member.id,
                    "watch_target_id": target.id,
                    "store_key": target.store_key,
                    "title_snapshot": member.title_snapshot,
                    "candidate_key": member.candidate_key,
                    "status": TaskRunStatus.FAILED.value,
                    "error_code": error_code,
                    "error_message": error_message,
                }
            )
    return results


def pick_watch_group_winner(
    results: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any] | None, dict[str, Any] | None]:
    successful = [item for item in results if item["status"] == TaskRunStatus.SUCCEEDED.value]
    if not successful:
        return successful, None, None
    successful.sort(
        key=lambda item: (
            float(item["effective_price"]),
            float(item["listed_price"]),
            str(item["store_key"]),
        )
    )
    winner = successful[0]
    runner_up = successful[1] if len(successful) > 1 else None
    return successful, winner, runner_up


def classify_watch_group_no_success(
    results: list[dict[str, Any]],
) -> tuple[str, str, str]:
    status = (
        TaskRunStatus.BLOCKED.value
        if any(item["status"] == TaskRunStatus.BLOCKED.value for item in results)
        else TaskRunStatus.FAILED.value
    )
    error_code = "watch_group_no_successful_candidates"
    return status, error_code, error_code


def apply_watch_group_success_run(
    run: WatchGroupRun,
    *,
    results: list[dict[str, Any]],
    winner: dict[str, Any],
    runner_up: dict[str, Any] | None,
    decision_reason: str,
    finished_at: datetime,
) -> None:
    run.status = TaskRunStatus.SUCCEEDED.value
    run.finished_at = finished_at
    run.member_results_json = {"results": results}
    run.winner_member_id = str(winner["member_id"])
    run.winner_effective_price = float(winner["effective_price"])
    run.runner_up_member_id = str(runner_up["member_id"]) if runner_up is not None else None
    run.runner_up_effective_price = (
        float(runner_up["effective_price"]) if runner_up is not None else None
    )
    run.price_spread = (
        round(float(runner_up["effective_price"]) - float(winner["effective_price"]), 2)
        if runner_up is not None
        else None
    )
    run.decision_reason = decision_reason


def build_group_decision_reason(
    previous_run: WatchGroupRun | None,
    winner: dict[str, Any],
    runner_up: dict[str, Any] | None,
) -> str:
    if previous_run is not None and previous_run.winner_member_id and previous_run.winner_member_id != winner["member_id"]:
        return "winner_changed_to_lower_effective_price"
    if runner_up is None:
        return "single_successful_candidate"
    if float(winner["effective_price"]) < float(winner["listed_price"]):
        return "lowest_effective_price_with_cashback"
    return "lowest_effective_price"


def build_watch_group_decision_explain(
    *,
    group: WatchGroup,
    latest_run: WatchGroupRun | None,
    latest_results: list[dict[str, Any]],
    member_map: dict[str, WatchGroupMember],
) -> dict[str, Any]:
    def _decision_summary(code: str | None) -> str | None:
        summaries = {
            "winner_changed_to_lower_effective_price": "A different candidate won because it now has the lower effective price.",
            "single_successful_candidate": "Only one candidate finished successfully in the latest run.",
            "lowest_effective_price_with_cashback": "The winner has the lowest effective price after cashback.",
            "lowest_effective_price": "The winner has the lowest effective price among successful candidates.",
        }
        return summaries.get(str(code), code)

    def _member_snapshot(member_id: str | None, result_map: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
        if not member_id:
            return None
        result = result_map.get(member_id)
        member = member_map.get(member_id)
        if member is None:
            return None
        title_snapshot = result.get("title_snapshot") if result else member.title_snapshot
        return {
            "member_id": member.id,
            "title": title_snapshot,
            "title_snapshot": title_snapshot,
            "candidate_key": member.candidate_key,
            "store_key": result.get("store_key") if result else None,
            "listed_price": result.get("listed_price") if result else None,
            "effective_price": result.get("effective_price") if result else None,
            "cashback_amount": result.get("cashback_amount") if result else None,
            "status": result.get("status") if result else None,
        }

    def _build_loss_reasons(winner: dict[str, Any] | None, runner_up: dict[str, Any] | None) -> list[dict[str, Any]]:
        if winner is None or runner_up is None:
            return []
        winner_effective = float(winner.get("effective_price") or 0.0)
        runner_effective = float(runner_up.get("effective_price") or 0.0)
        winner_listed = float(winner.get("listed_price") or 0.0)
        runner_listed = float(runner_up.get("listed_price") or 0.0)
        if runner_effective > winner_effective:
            delta = round(runner_effective - winner_effective, 2)
            return [
                {
                    "field": "effective_price",
                    "winner_value": winner_effective,
                    "runner_up_value": runner_effective,
                    "delta": delta,
                    "summary": f"Runner-up effective price is ${delta:.2f} higher.",
                }
            ]
        if runner_listed > winner_listed:
            delta = round(runner_listed - winner_listed, 2)
            return [
                {
                    "field": "listed_price",
                    "winner_value": winner_listed,
                    "runner_up_value": runner_listed,
                    "delta": delta,
                    "summary": f"Runner-up listed price is ${delta:.2f} higher.",
                }
            ]
        return [
            {
                "field": "store_key",
                "winner_value": str(winner.get("store_key") or ""),
                "runner_up_value": str(runner_up.get("store_key") or ""),
                "delta": None,
                "summary": "Effective and listed prices tied, so the stable store-key tie-breaker kept the winner first.",
            }
        ]

    if latest_run is None:
        return {
            "headline": "No group decision yet.",
            "decision_reason": None,
            "reason": {"code": None, "summary": None},
            "sort_basis": "effective_price_then_listed_price",
            "winner": None,
            "runner_up": None,
            "comparison": None,
            "spread": None,
            "member_outcomes": [],
            "candidate_outcomes": {
                "successful_count": 0,
                "blocked_count": 0,
                "failed_count": 0,
            },
            "reliability": "weak",
            "risk_notes": ["Run the group once before trusting any current winner."],
            "risk_note_items": [
                {
                    "code": "no_latest_run",
                    "message": "Run the group once before trusting any current winner.",
                }
            ],
        }

    result_map = {str(item.get("member_id")): item for item in latest_results}
    successful = [item for item in latest_results if item.get("status") == TaskRunStatus.SUCCEEDED.value]
    blocked = [item for item in latest_results if item.get("status") == TaskRunStatus.BLOCKED.value]
    failed = [item for item in latest_results if item.get("status") == TaskRunStatus.FAILED.value]
    winner = _member_snapshot(latest_run.winner_member_id, result_map)
    runner_up = _member_snapshot(latest_run.runner_up_member_id, result_map)
    comparison = None
    if winner is not None and runner_up is not None:
        comparison = {
            "price_spread": latest_run.price_spread,
            "effective_price_delta": round(
                float(runner_up["effective_price"] or 0.0) - float(winner["effective_price"] or 0.0),
                2,
            ),
            "listed_price_delta": round(
                float(runner_up["listed_price"] or 0.0) - float(winner["listed_price"] or 0.0),
                2,
            ),
            "cashback_delta": round(
                float(winner["cashback_amount"] or 0.0) - float(runner_up["cashback_amount"] or 0.0),
                2,
            ),
        }

    risk_note_items: list[dict[str, Any]] = []
    if latest_run.status != TaskRunStatus.SUCCEEDED.value:
        risk_note_items.append(
            {
                "code": "latest_run_not_successful",
                "message": "The latest group run did not finish successfully.",
            }
        )
    if len(successful) < 2:
        risk_note_items.append(
            {
                "code": "limited_successful_candidates",
                "message": "This decision is based on fewer than two successful candidates.",
            }
        )
    if blocked:
        risk_note_items.append(
            {
                "code": "blocked_candidates_present",
                "message": "At least one candidate was blocked during the latest run.",
            }
        )
    if failed:
        risk_note_items.append(
            {
                "code": "failed_candidates_present",
                "message": "At least one candidate failed during the latest run.",
            }
        )
    if latest_run.price_spread is not None and float(latest_run.price_spread) <= 0.5:
        risk_note_items.append(
            {
                "code": "close_price_spread",
                "message": "The top two candidates are close on effective price, so small changes may flip the winner.",
            }
        )
    if group.manual_intervention_required:
        risk_note_items.append(
            {
                "code": "operator_attention_required",
                "message": "Operator attention is currently required before trusting automation again.",
            }
        )
    risk_notes = [item["message"] for item in risk_note_items]

    if latest_run.status != TaskRunStatus.SUCCEEDED.value or group.manual_intervention_required:
        reliability = "weak"
    elif blocked or failed or len(successful) < 2 or group.health_status != HealthStatus.HEALTHY.value:
        reliability = "caution"
    else:
        reliability = "strong"

    if winner is None:
        headline = "No current winner is available."
    elif runner_up is None:
        headline = f"{winner['title']} is the only successful candidate from the latest run."
    else:
        headline = (
            f"{winner['title']} currently leads {runner_up['title']} by "
            f"${float(latest_run.price_spread or 0.0):.2f} on effective price."
        )

    member_outcomes: list[dict[str, Any]] = []
    seen_member_ids: set[str] = set()
    for result in latest_results:
        member_id = str(result.get("member_id"))
        member = member_map.get(member_id)
        seen_member_ids.add(member_id)
        if member_id == latest_run.winner_member_id:
            outcome = "winner"
        elif member_id == latest_run.runner_up_member_id:
            outcome = "runner_up"
        elif result.get("status") == TaskRunStatus.SUCCEEDED.value:
            outcome = "considered"
        else:
            outcome = str(result.get("status") or "unknown")
        member_outcomes.append(
            {
                "member_id": member_id,
                "title_snapshot": result.get("title_snapshot") or (member.title_snapshot if member is not None else None),
                "candidate_key": member.candidate_key if member is not None else result.get("candidate_key"),
                "store_key": result.get("store_key"),
                "status": result.get("status"),
                "outcome": outcome,
                "listed_price": result.get("listed_price"),
                "effective_price": result.get("effective_price"),
            }
        )
    for member_id, member in member_map.items():
        if member_id in seen_member_ids:
            continue
        member_outcomes.append(
            {
                "member_id": member_id,
                "title_snapshot": member.title_snapshot,
                "candidate_key": member.candidate_key,
                "store_key": None,
                "status": "missing_latest_result",
                "outcome": "missing_latest_result",
                "listed_price": None,
                "effective_price": None,
            }
        )

    return {
        "headline": headline,
        "decision_reason": latest_run.decision_reason,
        "reason": {
            "code": latest_run.decision_reason,
            "summary": _decision_summary(latest_run.decision_reason),
        },
        "sort_basis": "effective_price_then_listed_price",
        "winner": winner,
        "runner_up": (
            {
                **runner_up,
                "loss_reasons": _build_loss_reasons(winner, runner_up),
            }
            if runner_up is not None
            else None
        ),
        "comparison": comparison,
        "spread": (
            {
                "amount": latest_run.price_spread,
                "currency": "USD",
            }
            if latest_run.price_spread is not None
            else None
        ),
        "member_outcomes": member_outcomes,
        "candidate_outcomes": {
            "successful_count": len(successful),
            "blocked_count": len(blocked),
            "failed_count": len(failed),
        },
        "reliability": reliability,
        "risk_notes": risk_notes,
        "risk_note_items": risk_note_items,
    }


async def build_watch_group_ai_decision_explain(
    *,
    ai_service: Any,
    group_explain_enabled: bool,
    group: WatchGroup,
    decision_explain: dict[str, Any],
) -> dict[str, Any]:
    winner = decision_explain.get("winner") or {}
    runner_up = decision_explain.get("runner_up") or {}
    evidence_refs = [
        {
            "code": str((decision_explain.get("reason") or {}).get("code") or "group_decision_reason"),
            "label": "Decision reason",
            "anchor": "decision_explain.reason.code",
        },
        {
            "code": str(winner.get("member_id") or "no_winner"),
            "label": "Winner anchor",
            "anchor": "decision_explain.winner.member_id",
        },
    ]
    if runner_up.get("member_id"):
        evidence_refs.append(
            {
                "code": str(runner_up.get("member_id")),
                "label": "Runner-up anchor",
                "anchor": "decision_explain.runner_up.member_id",
            }
        )
    for item in list(decision_explain.get("risk_note_items", []))[:3]:
        evidence_refs.append(
            {
                "code": str(item.get("code") or "group_risk"),
                "label": "Decision risk note",
                "anchor": "decision_explain.risk_note_items",
            }
        )

    bullets = [
        str(decision_explain.get("headline") or "No group decision is available yet."),
        f"Current reliability is {decision_explain.get('reliability') or 'unknown'}.",
    ]
    if winner.get("title"):
        bullets.append(f"Winner candidate: {winner['title']}.")
    skip_reason = None if winner.get("member_id") else "No latest successful group winner exists yet."
    return await ai_service.build(
        enabled=group_explain_enabled,
        label="AI Watch Group Decision Explainer",
        title=f"Why {group.title} currently prefers this winner",
        summary=str(decision_explain.get("headline") or "No group decision is available yet."),
        bullets=bullets,
        evidence_refs=evidence_refs,
        caution_notes=list(decision_explain.get("risk_notes", [])),
        skip_reason=skip_reason,
    )


async def build_watch_group_detail(
    session: AsyncSession,
    *,
    group: WatchGroup,
    ai_service: Any,
    group_explain_enabled: bool,
) -> dict[str, Any]:
    members = list(
        (
            await session.scalars(
                select(WatchGroupMember)
                .where(WatchGroupMember.watch_group_id == group.id)
                .order_by(desc(WatchGroupMember.created_at))
            )
        ).all()
    )
    runs = list(
        (
            await session.scalars(
                select(WatchGroupRun)
                .where(WatchGroupRun.watch_group_id == group.id)
                .order_by(desc(WatchGroupRun.created_at))
                .limit(20)
            )
        ).all()
    )
    deliveries = list(
        (
            await session.scalars(
                select(DeliveryEvent)
                .where(DeliveryEvent.watch_group_id == group.id)
                .order_by(desc(DeliveryEvent.created_at))
                .limit(20)
            )
        ).all()
    )

    latest_run = runs[0] if runs else None
    latest_results = []
    if latest_run is not None and latest_run.member_results_json:
        latest_results = list(latest_run.member_results_json.get("results", []))
    latest_result_map = {str(item.get("member_id")): item for item in latest_results}
    member_map = {member.id: member for member in members}

    winner_member = None
    if latest_run is not None and latest_run.winner_member_id:
        winner_member = next((item for item in members if item.id == latest_run.winner_member_id), None)
    decision_explain = build_watch_group_decision_explain(
        group=group,
        latest_run=latest_run,
        latest_results=latest_results,
        member_map=member_map,
    )
    ai_decision_explain = await build_watch_group_ai_decision_explain(
        ai_service=ai_service,
        group_explain_enabled=group_explain_enabled,
        group=group,
        decision_explain=decision_explain,
    )

    return {
        "group": {
            "id": group.id,
            "title": group.title,
            "status": group.status,
            "zip_code": group.zip_code,
            "cadence_minutes": group.cadence_minutes,
            "threshold_type": group.threshold_type,
            "threshold_value": group.threshold_value,
            "cooldown_minutes": group.cooldown_minutes,
            "recipient_email": group.recipient_email,
            "notifications_enabled": group.notifications_enabled,
            "next_run_at": group.next_run_at.isoformat() if group.next_run_at else None,
            "last_run_at": group.last_run_at.isoformat() if group.last_run_at else None,
            "last_success_at": group.last_success_at.isoformat() if group.last_success_at else None,
            "last_error_code": group.last_error_code,
            "last_error_message": group.last_error_message,
            "health_status": group.health_status,
            "consecutive_failures": group.consecutive_failures,
            "backoff_until": group.backoff_until.isoformat() if group.backoff_until else None,
            "last_failure_kind": group.last_failure_kind,
            "manual_intervention_required": group.manual_intervention_required,
            "member_count": len(members),
            "current_winner_member_id": latest_run.winner_member_id if latest_run else None,
            "current_winner_title": winner_member.title_snapshot if winner_member is not None else None,
            "current_winner_effective_price": latest_run.winner_effective_price if latest_run else None,
            "price_spread": latest_run.price_spread if latest_run else None,
            "decision_reason": latest_run.decision_reason if latest_run else None,
        },
        "decision_explain": decision_explain,
        "ai_decision_explain": ai_decision_explain,
        "members": [
            {
                "id": member.id,
                "watch_target_id": member.watch_target_id,
                "title_snapshot": member.title_snapshot,
                "candidate_key": member.candidate_key,
                "brand_hint": member.brand_hint,
                "size_hint": member.size_hint,
                "similarity_score": member.similarity_score,
                "is_current_winner": latest_run.winner_member_id == member.id if latest_run else False,
                "latest_result": latest_result_map.get(member.id),
            }
            for member in members
        ],
        "runs": [
            {
                "id": item.id,
                "status": item.status,
                "started_at": item.started_at.isoformat() if item.started_at else None,
                "finished_at": item.finished_at.isoformat() if item.finished_at else None,
                "error_message": item.error_message,
                "winner_member_id": item.winner_member_id,
                "winner_effective_price": item.winner_effective_price,
                "runner_up_member_id": item.runner_up_member_id,
                "runner_up_effective_price": item.runner_up_effective_price,
                "price_spread": item.price_spread,
                "decision_reason": item.decision_reason,
                "member_results": list((item.member_results_json or {}).get("results", [])),
                "artifact_run_dir": item.artifact_run_dir,
            }
            for item in runs
        ],
        "deliveries": [
            {
                "id": item.id,
                "provider": item.provider,
                "recipient": item.recipient,
                "status": item.status,
                "created_at": item.created_at.isoformat(),
                "sent_at": item.sent_at.isoformat() if item.sent_at else None,
                "delivered_at": item.delivered_at.isoformat() if item.delivered_at else None,
                "bounced_at": item.bounced_at.isoformat() if item.bounced_at else None,
            }
            for item in deliveries
        ],
    }
