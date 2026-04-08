from __future__ import annotations

from datetime import datetime, timezone
import html
from pathlib import Path
from typing import Any

from dealwatch.stores import STORE_CAPABILITY_REGISTRY


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def validate_compare_preview_result(compare_result: dict[str, Any]) -> None:
    if not isinstance(compare_result, dict):
        raise ValueError("compare_result_invalid")
    if not isinstance(compare_result.get("comparisons"), list):
        raise ValueError("compare_result_invalid")
    if not isinstance(compare_result.get("matches"), list):
        raise ValueError("compare_result_invalid")
    if "submitted_count" not in compare_result or "resolved_count" not in compare_result:
        raise ValueError("compare_result_invalid")


def build_compare_evidence_truth(
    *,
    submitted_urls: list[str],
    zip_code: str,
    compare_result: dict[str, Any],
) -> dict[str, Any]:
    comparisons = list(compare_result.get("comparisons", []))
    matches = list(compare_result.get("matches", []))
    successful = [item for item in comparisons if item.get("fetch_succeeded")]
    group_ready = [
        item
        for item in successful
        if bool((item.get("support_contract") or {}).get("can_create_watch_group"))
    ]
    unsupported = [item for item in comparisons if not item.get("supported", True)]
    failed_fetch = [
        item
        for item in comparisons
        if item.get("supported", True) and not item.get("fetch_succeeded", False)
    ]
    strongest_match_score = max((float(item.get("score") or 0.0) for item in matches), default=0.0)
    if len(successful) <= 0:
        recommended_next_step_hint = {
            "action": "retry_compare",
            "reason_code": "no_successful_candidates",
            "summary": "No candidate resolved successfully yet, so rerun compare before saving anything durable.",
            "successful_candidate_count": len(successful),
            "strongest_match_score": strongest_match_score,
        }
    elif len(successful) == 1:
        recommended_next_step_hint = {
            "action": "create_watch_task",
            "reason_code": "single_resolved_candidate",
            "summary": "Only one candidate resolved successfully, so a single watch task is the safest next step.",
            "successful_candidate_count": len(successful),
            "strongest_match_score": strongest_match_score,
        }
    elif len(group_ready) == 1:
        recommended_next_step_hint = {
            "action": "create_watch_task",
            "reason_code": "single_group_capable_candidate",
            "summary": (
                "Multiple rows resolved, but only one row is currently eligible for a compare-aware watch group, "
                "so a single watch task is the safest durable next step."
            ),
            "successful_candidate_count": len(successful),
            "strongest_match_score": strongest_match_score,
        }
    elif len(group_ready) >= 2 and strongest_match_score >= 80:
        recommended_next_step_hint = {
            "action": "create_watch_group",
            "reason_code": "multi_candidate_strong_match",
            "summary": "Multiple candidates resolved and the strongest match signal is strong, so keep them together as a watch group.",
            "successful_candidate_count": len(successful),
            "strongest_match_score": strongest_match_score,
        }
    elif len(group_ready) < 2:
        recommended_next_step_hint = {
            "action": "review_before_save",
            "reason_code": "group_capability_gap",
            "summary": (
                "Rows resolved successfully, but the current store-capability contract does not yet support a "
                "compare-aware watch group for enough of them."
            ),
            "successful_candidate_count": len(successful),
            "strongest_match_score": strongest_match_score,
        }
    else:
        recommended_next_step_hint = {
            "action": "review_before_save",
            "reason_code": "multi_candidate_weak_match",
            "summary": "More than one candidate resolved, but the strongest match signal is weak enough that you should review before saving.",
            "successful_candidate_count": len(successful),
            "strongest_match_score": strongest_match_score,
        }

    risk_note_items: list[dict[str, Any]] = []
    if unsupported:
        risk_note_items.append(
            {
                "code": "unsupported_inputs_present",
                "message": f"{len(unsupported)} URL(s) are unsupported.",
            }
        )
    if failed_fetch:
        risk_note_items.append(
            {
                "code": "failed_fetch_candidates_present",
                "message": f"{len(failed_fetch)} candidate(s) failed to fetch.",
            }
        )
    if len(successful) < 2:
        risk_note_items.append(
            {
                "code": "limited_successful_candidates",
                "message": "There are fewer than two successful candidates, so a compare-aware group may not be justified yet.",
            }
        )
    if matches and strongest_match_score < 80:
        risk_note_items.append(
            {
                "code": "match_confidence_not_high",
                "message": "The strongest match score is still below the high-confidence range.",
            }
        )

    return {
        "submitted_inputs": list(submitted_urls),
        "zip_code": zip_code,
        "submitted_count": int(compare_result.get("submitted_count") or len(submitted_urls)),
        "resolved_count": int(compare_result.get("resolved_count") or len(successful)),
        "comparisons": comparisons,
        "matches": matches,
        "recommended_next_step_hint": recommended_next_step_hint,
        "risk_notes": [item["message"] for item in risk_note_items],
        "risk_note_items": risk_note_items,
        "successful_candidate_count": len(successful),
        "strongest_match_score": strongest_match_score,
    }


def build_compare_support_contract(
    *,
    store_key: str | None,
    intake_status: str,
) -> dict[str, Any]:
    capability = STORE_CAPABILITY_REGISTRY.get(store_key) if store_key is not None else None
    support_tier = capability.support_tier if capability is not None else "limited_unofficial"
    support_channel = "official" if capability is not None else "limited"
    missing_capabilities = []
    if capability is not None:
        missing_capabilities = [
            capability_name
            for capability_name, enabled in (
                ("compare_intake", capability.supports_compare_intake),
                ("watch_task", capability.supports_watch_task),
                ("watch_group", capability.supports_watch_group),
                ("recovery", capability.supports_recovery),
                ("cashback", capability.cashback_supported),
            )
            if not enabled
        ]

    summary = (
        "This row is on the full official product path. Compare intake, watch creation, compare-aware groups, "
        "recovery, and cashback-aware review are all available once live offer evidence is present."
    )
    next_step = "Review the compare evidence, then create either a single watch task or a compare-aware watch group."
    can_create_watch_task = capability.supports_watch_task if capability is not None else False
    can_create_watch_group = capability.supports_watch_group if capability is not None else False
    cashback_supported = capability.cashback_supported if capability is not None else False
    notifications_supported = can_create_watch_task or can_create_watch_group

    if intake_status == "unsupported_store_host":
        summary = (
            "This host is not in the official DealWatch store registry yet. "
            "The row can stay in compare review and repo-local evidence, but it cannot become live watch state."
        )
        next_step = "Keep it as compare evidence only, or submit a URL from an officially supported store."
        can_create_watch_task = False
        can_create_watch_group = False
        cashback_supported = False
        notifications_supported = False
        missing_capabilities = ["official_store_registry", "watch_task", "watch_group", "recovery", "cashback"]
    elif intake_status == "unsupported_store_path":
        summary = (
            "The store host is recognized, but this URL shape is not an officially supported product path yet. "
            "DealWatch can keep it in compare review and local evidence, but not as live watch state."
        )
        next_step = "Submit a supported product-detail URL for this store, or keep this row as compare evidence only."
        can_create_watch_task = False
        can_create_watch_group = False
        cashback_supported = False
        notifications_supported = False
    elif intake_status == "store_disabled":
        summary = (
            "This store is part of the official registry, but its runtime binding is currently disabled. "
            "The row can stay in compare review and evidence, but live watch actions are paused."
        )
        next_step = "Re-enable the store binding before creating a watch task or watch group from this row."
        can_create_watch_task = False
        can_create_watch_group = False
        cashback_supported = False
        notifications_supported = False
    elif intake_status == "offer_fetch_failed":
        summary = (
            "The store and URL path are supported, but this compare run did not fetch live offer evidence. "
            "Until fetch succeeds, keep the row as review/evidence instead of durable watch state."
        )
        next_step = "Retry compare or inspect the store/runtime condition before saving live watch state."
        can_create_watch_task = False
        can_create_watch_group = False
        cashback_supported = False
        notifications_supported = False
    elif support_tier == "official_full":
        summary = (
            "This row is on the full official store path. "
            "Compare intake, single-watch, compare-aware watch group, recovery, and cashback all sit inside the current repo-local product path."
        )
        next_step = (
            "If multiple strong rows survive compare, keep them together as a watch group. "
            "If only one row survives cleanly, a single watch task is still the safest durable next step."
        )
    elif support_tier == "official_partial":
        if can_create_watch_group:
            summary = (
                "This row is on an officially supported but still partial store path. "
                "Compare intake, single-watch flow, and compare-aware watch groups are available, "
                "while recovery and cashback closure still remain intentionally limited."
            )
            next_step = (
                "Use the currently supported compare, single-watch, or compare-aware watch-group path, "
                "and keep recovery/cashback claims deferred until those capabilities are truly landed."
            )
        else:
            summary = (
                "This row is on an officially supported but still partial store path. "
                "Compare intake and single-watch flow are available, while broader group/recovery closure is still limited."
            )
            next_step = "Use the currently supported compare or single-watch path, and do not overclaim missing store capabilities."
    elif support_tier == "official_in_progress":
        summary = (
            "This store is in official onboarding progress, so the repo can describe the path but should not market it as full support yet."
        )
        next_step = "Keep the store parked until contract tests, runtime checks, and product-path coverage are ready."

    return {
        "support_channel": support_channel,
        "store_support_tier": support_tier,
        "support_reason_codes": list(capability.support_reason_codes) if capability is not None else [],
        "next_step_codes": list(capability.next_step_codes) if capability is not None else [],
        "intake_status": intake_status,
        "summary": summary,
        "next_step": next_step,
        "can_save_compare_evidence": True,
        "can_create_watch_task": can_create_watch_task and intake_status == "supported",
        "can_create_watch_group": can_create_watch_group and intake_status == "supported",
        "cashback_supported": cashback_supported and intake_status == "supported",
        "notifications_supported": notifications_supported and intake_status == "supported",
        "missing_capabilities": missing_capabilities,
    }


def build_compare_evidence_payload(
    *,
    package_id: str,
    compare_evidence: dict[str, Any],
    runs_dir: Path,
) -> dict[str, Any]:
    comparisons = list(compare_evidence.get("comparisons", []))
    matches = list(compare_evidence.get("matches", []))
    recommended_next_step_hint = dict(compare_evidence.get("recommended_next_step_hint") or {})
    risk_note_items = list(compare_evidence.get("risk_note_items", []))
    risk_notes = list(compare_evidence.get("risk_notes", []))
    recommendation = build_compare_public_recommendation_payload(compare_evidence=compare_evidence)

    headline = str(recommended_next_step_hint.get("summary") or "Compare evidence package")
    saved_at = _utcnow().isoformat()
    artifact_dir = runs_dir / "compare-evidence" / package_id
    summary = {
        "artifact_id": package_id,
        "artifact_kind": "compare_evidence",
        "storage_scope": "runtime_local_artifact",
        "created_at": saved_at,
        "saved_at": saved_at,
        "headline": headline,
        "recommended_next_step_hint": recommended_next_step_hint,
        "submitted_inputs": list(compare_evidence.get("submitted_inputs", [])),
        "submitted_count": int(compare_evidence.get("submitted_count") or 0),
        "resolved_count": int(compare_evidence.get("resolved_count") or 0),
        "successful_candidate_count": int(compare_evidence.get("successful_candidate_count") or 0),
        "strongest_match_score": float(compare_evidence.get("strongest_match_score") or 0.0),
        "risk_notes": risk_notes,
        "risk_note_items": risk_note_items,
        "recommendation": recommendation,
        "artifact_path": str(artifact_dir / "compare_evidence.json"),
        "html_path": str(artifact_dir / "compare_evidence.html"),
        "detail_url": f"/api/compare/evidence/{package_id}",
        "html_url": f"/api/compare/evidence-packages/{package_id}/html",
    }
    return {
        "artifact_id": package_id,
        "artifact_kind": "compare_evidence",
        "storage_scope": "runtime_local_artifact",
        "saved_at": saved_at,
        "artifact_path": summary["artifact_path"],
        "html_path": summary["html_path"],
        "source_of_truth_note": "This evidence pack is a runtime/local artifact and does not become PostgreSQL product source of truth.",
        "submitted_inputs": list(compare_evidence.get("submitted_inputs", [])),
        "zip_code": compare_evidence.get("zip_code"),
        "submitted_count": summary["submitted_count"],
        "resolved_count": summary["resolved_count"],
        "comparisons": comparisons,
        "matches": matches,
        "recommended_next_step_hint": recommended_next_step_hint,
        "risk_notes": risk_notes,
        "risk_note_items": risk_note_items,
        "recommendation": recommendation,
        "summary": summary,
    }


def _build_compare_recommendation_context(compare_evidence: dict[str, Any]) -> dict[str, Any]:
    recommended_next_step_hint = dict(compare_evidence.get("recommended_next_step_hint") or {})
    risk_note_items = list(compare_evidence.get("risk_note_items", []))
    risk_notes = list(compare_evidence.get("risk_notes", []))
    successful_candidate_count = int(compare_evidence.get("successful_candidate_count") or 0)
    strongest_match_score = float(compare_evidence.get("strongest_match_score") or 0.0)
    reason_code = str(recommended_next_step_hint.get("reason_code") or "compare_shadow_unknown")
    action = str(recommended_next_step_hint.get("action") or "review_before_save")

    basis = [
        str(
            recommended_next_step_hint.get("summary")
            or "Deterministic compare evidence remains the primary review surface."
        )
    ]
    uncertainty_notes = [
        "Deterministic compare evidence stays primary, and this recommendation only interprets compare-stage signals."
    ]
    abstention = {
        "active": False,
        "code": None,
        "reason": None,
    }

    evidence_strength = "strong_compare_wait"
    if reason_code in {"no_successful_candidates", "single_resolved_candidate", "single_group_capable_candidate"}:
        verdict = "insufficient_evidence"
        abstention = {
            "active": True,
            "code": reason_code,
            "reason": (
                "This compare run does not yet have enough cross-store evidence for a public recommendation, so stay in evidence review."
            ),
        }
        basis.append(
            "Cross-store compare context is still incomplete, so this recommendation abstains instead of forcing a stronger call."
        )
        evidence_strength = "insufficient_compare_context"
    elif reason_code == "multi_candidate_strong_match":
        verdict = "wait"
        basis.append(
            "Multiple candidates still look plausibly comparable, so keeping the basket under watch is safer than turning compare evidence into a buy-now claim."
        )
    else:
        verdict = "recheck_later"
        basis.append(
            "The compare evidence still needs another review or rerun before a stronger timing call would be honest."
        )
        evidence_strength = "needs_recheck"

    if successful_candidate_count <= 0:
        uncertainty_notes.append("No candidate resolved successfully in this compare run.")
    elif successful_candidate_count < 2:
        uncertainty_notes.append("Fewer than two successful candidates survived compare.")
    if strongest_match_score < 80:
        uncertainty_notes.append(
            f"Strongest match score is only {strongest_match_score:.1f}, which is below the current high-confidence compare range."
        )
    uncertainty_notes.extend(risk_notes)
    uncertainty_notes = list(dict.fromkeys(note for note in uncertainty_notes if note))

    evidence_refs = [
        {
            "code": reason_code,
            "label": "Deterministic next-step reason",
            "anchor": "compare_evidence.recommended_next_step_hint.reason_code",
        },
        {
            "code": action,
            "label": "Deterministic next-step action",
            "anchor": "compare_evidence.recommended_next_step_hint.action",
        },
        {
            "code": f"successful_candidate_count:{successful_candidate_count}",
            "label": "Successful candidate count",
            "anchor": "compare_evidence.successful_candidate_count",
        },
        {
            "code": "strongest_match_score",
            "label": f"Strongest match score {strongest_match_score:.1f}",
            "anchor": "compare_evidence.strongest_match_score",
        },
    ]
    for item in risk_note_items[:3]:
        evidence_refs.append(
            {
                "code": str(item.get("code") or "compare_risk"),
                "label": str(item.get("message") or "Compare risk note"),
                "anchor": "compare_evidence.risk_note_items",
            }
        )

    return {
        "reason_code": reason_code,
        "action": action,
        "verdict": verdict,
        "basis": basis,
        "uncertainty_notes": uncertainty_notes,
        "abstention": abstention,
        "evidence_refs": evidence_refs,
        "evidence_strength": evidence_strength,
    }


def build_compare_public_recommendation_payload(
    *,
    compare_evidence: dict[str, Any],
) -> dict[str, Any]:
    context = _build_compare_recommendation_context(compare_evidence)
    verdict = str(context["verdict"])
    abstention = dict(context["abstention"])
    status = "abstained" if abstention["active"] else "issued"

    if verdict == "wait":
        headline = "Keep watching this basket"
        summary = (
            "The current compare evidence is strong enough to keep these candidates under watch, but it still does not justify a buy-now claim."
        )
    elif verdict == "recheck_later":
        headline = "Re-check later"
        summary = (
            "The compare evidence is still too mixed to support a stronger timing call, so review this basket again after more evidence arrives."
        )
    else:
        headline = "Not enough evidence yet"
        summary = (
            "This compare run does not have enough cross-store evidence for a public recommendation, so stay with evidence review only."
        )

    return {
        "contract_version": "compare_preview_public_v1",
        "surface": "compare_preview",
        "scope": "local_runtime_compare_flow",
        "visibility": "user_visible",
        "status": status,
        "verdict": verdict,
        "verdict_vocabulary": ["wait", "recheck_later", "insufficient_evidence"],
        "headline": headline,
        "summary": summary,
        "basis": list(context["basis"]),
        "uncertainty_notes": list(context["uncertainty_notes"]),
        "abstention": abstention,
        "evidence_refs": list(context["evidence_refs"]),
        "deterministic_primary_note": (
            "Deterministic compare evidence stays primary. AI prose does not decide this recommendation, and compare-only v1 does not issue buy-now."
        ),
        "feedback_boundary": (
            "End-user feedback is not yet a persisted product surface. Maintainers still monitor quality through the internal recommendation review ledger."
        ),
        "override_boundary": (
            "Users still decide whether to save evidence, create a watch task, or create a watch group. Maintainers can keep correcting calibration through the internal review loop."
        ),
        "buy_now_blocked": True,
    }


def build_compare_recommendation_shadow_payload(
    *,
    package_id: str,
    compare_evidence: dict[str, Any],
    runs_dir: Path,
) -> dict[str, Any]:
    public_recommendation = build_compare_public_recommendation_payload(compare_evidence=compare_evidence)
    context = _build_compare_recommendation_context(compare_evidence)
    verdict = str(context["verdict"])
    abstention = dict(context["abstention"])
    basis = list(context["basis"])
    uncertainty_notes = list(context["uncertainty_notes"])
    evidence_refs = list(context["evidence_refs"])
    evidence_strength = str(context["evidence_strength"])

    saved_at = _utcnow().isoformat()
    artifact_dir = runs_dir / "compare-evidence" / package_id
    status = "abstained" if abstention["active"] else "issued"
    review_seed_suggestion = "correct_abstention" if abstention["active"] else "correct_verdict"
    return {
        "artifact_id": package_id,
        "artifact_kind": "recommendation_shadow",
        "shadow_contract_version": "v1",
        "storage_scope": "runtime_local_artifact",
        "mode": "internal_only_shadow",
        "visibility": "internal_only",
        "surface_anchor": "compare_preview",
        "saved_at": saved_at,
        "artifact_path": str(artifact_dir / "recommendation_shadow.json"),
        "html_path": str(artifact_dir / "recommendation_shadow.html"),
        "review_use_cases": ["internal_review", "replay", "compare"],
        "verdict_vocabulary": ["buy_now", "wait", "recheck_later", "insufficient_evidence"],
        "status": status,
        "deterministic_truth_anchor": {
            "artifact_kind": "compare_evidence",
            "artifact_path": str(artifact_dir / "compare_evidence.json"),
            "html_path": str(artifact_dir / "compare_evidence.html"),
            "note": (
                "This shadow artifact is advisory-only for internal review and must stay subordinate to deterministic compare evidence."
            ),
        },
        "review": {
            "state": "pending_internal_review",
            "owner": None,
            "reason_code": None,
            "notes": None,
            "observed_outcome": None,
        },
        "monitoring": {
            "input_profile": "compare_preview_only",
            "evidence_strength": evidence_strength,
            "abstention_code": abstention["code"],
            "review_state": "pending_internal_review",
            "future_launch_blocked": True,
            "review_seed_suggestion": review_seed_suggestion,
        },
        "shadow_recommendation": {
            "verdict": verdict,
            "basis": basis,
            "uncertainty_notes": uncertainty_notes,
            "abstention": abstention,
            "evidence_refs": evidence_refs,
        },
        "public_contract_bridge": {
            "contract_version": public_recommendation["contract_version"],
            "surface": public_recommendation["surface"],
            "public_verdict_vocabulary": list(public_recommendation["verdict_vocabulary"]),
            "buy_now_blocked": public_recommendation["buy_now_blocked"],
        },
    }


async def build_compare_ai_explain(
    *,
    ai_service: Any,
    compare_explain_enabled: bool,
    compare_evidence: dict[str, Any],
) -> dict[str, Any]:
    matches = list(compare_evidence.get("matches", []))
    strongest_match = matches[0] if matches else None
    next_step = dict(compare_evidence.get("recommended_next_step_hint") or {})
    evidence_refs = [
        {
            "code": str(next_step.get("reason_code") or "compare_next_step"),
            "label": "Recommended next-step reason",
            "anchor": "recommended_next_step_hint.reason_code",
        },
        {
            "code": str(next_step.get("action") or "review_compare"),
            "label": "Recommended next-step action",
            "anchor": "recommended_next_step_hint.action",
        },
    ]
    if strongest_match is not None:
        evidence_refs.append(
            {
                "code": "strongest_match_score",
                "label": (
                    f"{strongest_match.get('left_store_key')} vs {strongest_match.get('right_store_key')}"
                ),
                "anchor": "matches[0].score",
            }
        )
    for item in list(compare_evidence.get("risk_note_items", []))[:3]:
        evidence_refs.append(
            {
                "code": str(item.get("code") or "compare_risk"),
                "label": "Compare risk note",
                "anchor": "risk_note_items",
            }
        )

    bullets = [
        (
            f"{int(compare_evidence.get('resolved_count') or 0)} of "
            f"{int(compare_evidence.get('submitted_count') or 0)} candidates resolved successfully."
        ),
        str(next_step.get("summary") or "Review the deterministic compare evidence before deciding."),
    ]
    if strongest_match is not None:
        bullets.append(
            f"Strongest pair score is {float(strongest_match.get('score') or 0.0):.1f}."
        )
    return await ai_service.build(
        enabled=compare_explain_enabled,
        label="AI Compare Explainer",
        title="Should these candidates stay together?",
        summary=str(next_step.get("summary") or "Compare finished without a durable AI explanation."),
        bullets=bullets,
        evidence_refs=evidence_refs,
        caution_notes=list(compare_evidence.get("risk_notes", [])),
    )


def render_compare_evidence_html(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    recommendation = payload.get("recommendation") or {}
    comparisons = payload.get("comparisons", [])
    matches = payload.get("matches", [])
    comparison_rows = "\n".join(
        (
            "<tr>"
            f"<td>{html.escape(str(item.get('store_key') or 'unknown'))}</td>"
            f"<td>{html.escape(str(item.get('submitted_url') or ''))}</td>"
            f"<td>{html.escape(str(item.get('candidate_key') or ''))}</td>"
            f"<td>{'yes' if item.get('fetch_succeeded') else 'no'}</td>"
            f"<td>{html.escape(str((item.get('offer') or {}).get('title') or ''))}</td>"
            f"<td>{html.escape(str(item.get('error_code') or ''))}</td>"
            "</tr>"
        )
        for item in comparisons
    )
    match_rows = "\n".join(
        (
            "<tr>"
            f"<td>{html.escape(str(item.get('left_store_key') or ''))}</td>"
            f"<td>{html.escape(str(item.get('right_store_key') or ''))}</td>"
            f"<td>{float(item.get('score') or 0.0):.1f}</td>"
            f"<td>{html.escape(', '.join(item.get('why_like') or []))}</td>"
            f"<td>{html.escape(', '.join(item.get('why_unlike') or []))}</td>"
            "</tr>"
        )
        for item in matches
    )
    submitted_urls = "".join(
        f"<li>{html.escape(str(item))}</li>"
        for item in payload.get("submitted_inputs", [])
    )
    risk_notes = "".join(
        f"<li>{html.escape(str(item))}</li>"
        for item in summary.get("risk_notes", [])
    )
    recommendation_basis = "".join(
        f"<li>{html.escape(str(item))}</li>"
        for item in recommendation.get("basis", [])
    )
    recommendation_uncertainty = "".join(
        f"<li>{html.escape(str(item))}</li>"
        for item in recommendation.get("uncertainty_notes", [])
    )
    recommendation_refs = "".join(
        (
            "<tr>"
            f"<td>{html.escape(str(item.get('code') or ''))}</td>"
            f"<td>{html.escape(str(item.get('label') or ''))}</td>"
            f"<td>{html.escape(str(item.get('anchor') or ''))}</td>"
            "</tr>"
        )
        for item in recommendation.get("evidence_refs", [])
    )
    abstention = recommendation.get("abstention") or {}
    abstention_text = (
        (
            f"Abstention active: {html.escape(str(abstention.get('code') or 'insufficient_evidence'))} - "
            f"{html.escape(str(abstention.get('reason') or 'No abstention reason provided.'))}"
        )
        if abstention.get("active")
        else "No abstention is active for this compare-preview recommendation."
    )
    return (
        "<html><head><meta charset=\"utf-8\"/>"
        "<style>"
        "body{font-family:Arial,Helvetica,sans-serif;margin:24px;color:#1f2937;}"
        "table{border-collapse:collapse;width:100%;margin-top:16px;}"
        "th,td{border:1px solid #d1d5db;padding:8px;text-align:left;font-size:14px;vertical-align:top;}"
        "th{background:#f3f4f6;}"
        ".summary{background:#f8fafc;border:1px solid #e5e7eb;border-radius:16px;padding:16px;margin-bottom:20px;}"
        ".eyebrow{font-size:12px;text-transform:uppercase;letter-spacing:.12em;color:#b45309;font-weight:700;}"
        "</style></head><body>"
        "<div class=\"summary\">"
        "<div class=\"eyebrow\">Compare Evidence Artifact</div>"
        f"<h1>{html.escape(summary['headline'])}</h1>"
        f"<p>Saved at {html.escape(summary['saved_at'])}. Recommended next step: {html.escape(summary['recommended_next_step_hint']['action'])}.</p>"
        f"<p>Submitted {summary['submitted_count']} URL(s), resolved {summary['resolved_count']} candidate(s), strongest match score {float(summary['strongest_match_score'] or 0.0):.1f}.</p>"
        "</div>"
        "<h2>Input</h2>"
        f"<p>ZIP code: {html.escape(str(payload.get('zip_code') or ''))}</p>"
        f"<ul>{submitted_urls}</ul>"
        "<h2>Risk Notes</h2>"
        f"<ul>{risk_notes or '<li>No additional risk notes.</li>'}</ul>"
        "<h2>Recommendation</h2>"
        "<div class=\"summary\">"
        f"<h3>{html.escape(str(recommendation.get('headline') or 'Recommendation unavailable'))}</h3>"
        f"<p>{html.escape(str(recommendation.get('summary') or 'Recommendation is unavailable for this evidence package.'))}</p>"
        f"<p>{html.escape(str(recommendation.get('deterministic_primary_note') or 'Deterministic compare evidence stays primary.'))}</p>"
        f"<p>{abstention_text}</p>"
        f"<p>{html.escape(str(recommendation.get('feedback_boundary') or ''))}</p>"
        "</div>"
        "<h3>Recommendation Basis</h3>"
        f"<ul>{recommendation_basis or '<li>No recommendation basis recorded.</li>'}</ul>"
        "<h3>Recommendation Uncertainty</h3>"
        f"<ul>{recommendation_uncertainty or '<li>No uncertainty notes recorded.</li>'}</ul>"
        "<h3>Recommendation Evidence References</h3>"
        "<table><tr><th>Code</th><th>Label</th><th>Anchor</th></tr>"
        f"{recommendation_refs}</table>"
        "<h2>Candidate Results</h2>"
        "<table><tr><th>Store</th><th>Submitted URL</th><th>Candidate Key</th><th>Fetched</th><th>Title</th><th>Error</th></tr>"
        f"{comparison_rows}</table>"
        "<h2>Match Signals</h2>"
        "<table><tr><th>Left</th><th>Right</th><th>Score</th><th>Why Like</th><th>Why Unlike</th></tr>"
        f"{match_rows}</table>"
        "</body></html>"
    )


def render_compare_recommendation_shadow_html(payload: dict[str, Any]) -> str:
    recommendation = payload["shadow_recommendation"]
    review = payload.get("review") or {}
    monitoring = payload.get("monitoring") or {}
    evidence_refs = "".join(
        (
            "<tr>"
            f"<td>{html.escape(str(item.get('code') or ''))}</td>"
            f"<td>{html.escape(str(item.get('label') or ''))}</td>"
            f"<td>{html.escape(str(item.get('anchor') or ''))}</td>"
            "</tr>"
        )
        for item in recommendation.get("evidence_refs", [])
    )
    basis_rows = "".join(
        f"<li>{html.escape(str(item))}</li>"
        for item in recommendation.get("basis", [])
    )
    uncertainty_rows = "".join(
        f"<li>{html.escape(str(item))}</li>"
        for item in recommendation.get("uncertainty_notes", [])
    )
    abstention = recommendation.get("abstention") or {}
    abstention_text = (
        (
            f"Abstention active: {html.escape(str(abstention.get('code') or 'shadow_abstention'))} - "
            f"{html.escape(str(abstention.get('reason') or 'No abstention reason provided.'))}"
        )
        if abstention.get("active")
        else "No abstention is active for this internal-only shadow recommendation."
    )
    review_summary = (
        f"Review state: {html.escape(str(review.get('state') or 'pending_internal_review'))}. "
        f"Agreement bucket: {html.escape(str(monitoring.get('agreement_bucket') or 'pending'))}."
    )
    return (
        "<html><head><meta charset=\"utf-8\"/>"
        "<style>"
        "body{font-family:Arial,Helvetica,sans-serif;margin:24px;color:#1f2937;}"
        "table{border-collapse:collapse;width:100%;margin-top:16px;}"
        "th,td{border:1px solid #d1d5db;padding:8px;text-align:left;font-size:14px;vertical-align:top;}"
        "th{background:#f3f4f6;}"
        ".summary{background:#fff7ed;border:1px solid #fdba74;border-radius:16px;padding:16px;margin-bottom:20px;}"
        ".eyebrow{font-size:12px;text-transform:uppercase;letter-spacing:.12em;color:#c2410c;font-weight:700;}"
        "</style></head><body>"
        "<div class=\"summary\">"
        "<div class=\"eyebrow\">Recommendation Shadow Artifact</div>"
        f"<h1>{html.escape(str(recommendation['verdict']))}</h1>"
        f"<p>Saved at {html.escape(str(payload['saved_at']))}. This is internal-only and does not change the public compare contract.</p>"
        f"<p>{html.escape(str(payload['deterministic_truth_anchor']['note']))}</p>"
        f"<p>{abstention_text}</p>"
        f"<p>{review_summary}</p>"
        "</div>"
        "<h2>Basis</h2>"
        f"<ul>{basis_rows}</ul>"
        "<h2>Uncertainty Notes</h2>"
        f"<ul>{uncertainty_rows}</ul>"
        "<h2>Evidence References</h2>"
        "<table><tr><th>Code</th><th>Label</th><th>Anchor</th></tr>"
        f"{evidence_refs}</table>"
        "</body></html>"
    )
