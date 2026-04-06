#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from dealwatch.jobs.recommendation_evaluation import (
    DEFAULT_RECOMMENDATION_EVAL_WORKSPACE,
    list_pending_recommendation_reviews,
    record_recommendation_review,
)

DISAGREEMENT_OUTCOME_CATEGORIES = {
    "false_positive",
    "false_negative",
    "abstain_when_should_speak",
    "speak_when_should_abstain",
}


def _load_json_artifact(path_value: str | None) -> dict[str, Any]:
    if not path_value:
        return {}
    artifact_path = Path(path_value)
    if not artifact_path.is_file():
        return {}
    return json.loads(artifact_path.read_text(encoding="utf-8"))


def _render_bucket_summary(buckets: dict[str, Any]) -> str:
    if not buckets:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(buckets.items()))


def _format_pending_text(payload: dict[str, Any]) -> str:
    monitoring_summary = _load_json_artifact(payload.get("monitoring_summary_path"))
    summary = dict(monitoring_summary.get("summary") or {})
    lines = [
        "Recommendation review queue",
        f"Workspace: {payload['workspace']}",
        (
            "Queue snapshot: "
            f"reviewed={summary.get('reviewed_count', 0)} | "
            f"pending={payload.get('pending_count', 0)} | "
            f"issued={summary.get('issued_verdict_count', 0)} | "
            f"abstained={summary.get('abstention_count', 0)}"
        ),
        f"Review state buckets: {_render_bucket_summary(summary.get('review_state_buckets') or {})}",
        f"Disagreement buckets: {_render_bucket_summary(summary.get('disagreement_buckets') or {})}",
        "Pending cases:",
    ]
    pending_reviews = list(payload.get("pending_reviews") or [])
    if not pending_reviews:
        lines.append("- none")
        return "\n".join(lines)

    for index, entry in enumerate(pending_reviews, start=1):
        seed = entry.get("review_seed_suggestion") or "no_seed_suggestion"
        lines.extend(
            [
                (
                    f"{index}. artifact_id={entry.get('artifact_id')} | "
                    f"surface_anchor={entry.get('surface_anchor')} | "
                    f"status={entry.get('status')} | "
                    f"verdict={entry.get('verdict')}"
                ),
                f"   suggested_bucket={seed}",
                f"   shadow_json={entry.get('shadow_artifact_path')}",
                f"   shadow_html={entry.get('shadow_html_path')}",
            ]
        )
    return "\n".join(lines)


def _format_review_text(payload: dict[str, Any]) -> str:
    review_record = dict(payload.get("review_record") or {})
    monitoring_summary = _load_json_artifact(payload.get("monitoring_summary_path"))
    summary = dict(monitoring_summary.get("summary") or {})
    lines = [
        "Recommendation review recorded",
        (
            f"Artifact: {review_record.get('artifact_id')} | "
            f"surface_anchor={review_record.get('surface_anchor')} | "
            f"decision={review_record.get('decision')}"
        ),
        (
            f"Agreement bucket: {review_record.get('agreement_bucket')} | "
            f"expected={review_record.get('expected_verdict') or 'n/a'} | "
            f"actual={review_record.get('actual_verdict') or 'n/a'}"
        ),
        f"Observed outcome: {review_record.get('observed_outcome')}",
        f"Follow-up action: {review_record.get('follow_up_action') or 'none'}",
        (
            "Readiness snapshot: "
            f"reviewed={summary.get('reviewed_count', 0)} | "
            f"pending={summary.get('review_pending_count', 0)} | "
            f"confirmed={summary.get('review_state_buckets', {}).get('confirmed', 0)} | "
            f"overridden={summary.get('review_state_buckets', {}).get('overridden', 0)} | "
            f"rejected={summary.get('review_state_buckets', {}).get('rejected', 0)}"
        ),
        f"Disagreement buckets: {_render_bucket_summary(summary.get('disagreement_buckets') or {})}",
        f"Review log: {payload.get('review_log_path')}",
        f"Monitoring summary: {payload.get('monitoring_summary_path')}",
        f"Replay manifest: {payload.get('replay_manifest_path')}",
    ]
    return "\n".join(lines)


def _emit_payload(payload: dict[str, Any], output_format: str, *, list_pending: bool) -> None:
    if output_format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    rendered = _format_pending_text(payload) if list_pending else _format_review_text(payload)
    print(rendered)


def _validate_review_args(args: argparse.Namespace) -> None:
    if args.list_pending:
        return
    if not args.artifact_id.strip() or not args.reason_code.strip() or not args.observed_outcome.strip():
        raise SystemExit(
            "artifact-id, reason-code, and observed-outcome are required unless --list-pending is used."
        )
    if args.outcome_category not in DISAGREEMENT_OUTCOME_CATEGORIES:
        return

    missing: list[str] = []
    if not str(args.expected_verdict or "").strip():
        missing.append("--expected-verdict")
    if not str(args.actual_verdict or "").strip():
        missing.append("--actual-verdict")
    if not (
        str(args.notes or "").strip()
        or str(args.follow_up_action or "").strip()
        or [spec for spec in args.evidence_ref if str(spec).strip()]
    ):
        missing.append("one of --notes/--follow-up-action/--evidence-ref")
    if missing:
        raise SystemExit(
            "Deeper disagreement review requires "
            + ", ".join(missing)
            + " so the internal-only adjudication record is specific enough to reuse later."
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="List or record an internal-only review for recommendation shadow artifacts."
    )
    parser.add_argument(
        "--workspace",
        default=str(DEFAULT_RECOMMENDATION_EVAL_WORKSPACE),
        help="Repo-local workspace used for the current internal recommendation evaluation run and replay artifacts.",
    )
    parser.add_argument(
        "--list-pending",
        action="store_true",
        help="List replayable recommendation shadow artifacts that still need internal review.",
    )
    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
        help="Output json for automation or text for a maintainer-readable queue/readiness summary.",
    )
    parser.add_argument("--artifact-id", default="", help="Recommendation shadow artifact id to review.")
    parser.add_argument("--reviewer", default="maintainer", help="Maintainer or internal operator recording the review.")
    parser.add_argument(
        "--decision",
        choices=["confirmed", "overridden", "rejected"],
        default="confirmed",
        help="Review decision recorded against the shadow artifact.",
    )
    parser.add_argument("--reason-code", default="", help="Short machine-readable review reason.")
    parser.add_argument(
        "--outcome-category",
        default="correct_verdict",
        choices=[
            "correct_verdict",
            "correct_abstention",
            "false_positive",
            "false_negative",
            "abstain_when_should_speak",
            "speak_when_should_abstain",
        ],
        help="Canonical disagreement/agreement bucket for monitoring and replay.",
    )
    parser.add_argument("--observed-outcome", default="", help="Plain-language later deterministic outcome.")
    parser.add_argument(
        "--expected-verdict",
        default=None,
        help="What the reviewer believes the verdict should have been. Required for disagreement buckets.",
    )
    parser.add_argument(
        "--actual-verdict",
        default=None,
        help="The actual recorded verdict after review. Required for disagreement buckets.",
    )
    parser.add_argument(
        "--notes",
        default=None,
        help="Optional review note. One of notes/follow-up-action/evidence-ref is required for disagreement buckets.",
    )
    parser.add_argument(
        "--follow-up-action",
        default=None,
        help="Optional maintainer follow-up action. One of notes/follow-up-action/evidence-ref is required for disagreement buckets.",
    )
    parser.add_argument(
        "--evidence-ref",
        action="append",
        default=[],
        help="Optional evidence ref in the form code|label|anchor. Repeatable. One evidence anchor is required when recording a disagreement without notes/follow-up.",
    )
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace)
    _validate_review_args(args)
    if args.list_pending:
        payload = await list_pending_recommendation_reviews(workspace)
        _emit_payload(payload, args.format, list_pending=True)
        return 0

    payload = await record_recommendation_review(
        workspace,
        artifact_id=args.artifact_id.strip(),
        reviewer=args.reviewer.strip(),
        decision=args.decision,
        reason_code=args.reason_code.strip(),
        outcome_category=args.outcome_category,
        observed_outcome=args.observed_outcome.strip(),
        notes=args.notes,
        follow_up_action=args.follow_up_action,
        expected_verdict=args.expected_verdict,
        actual_verdict=args.actual_verdict,
        evidence_ref_specs=list(args.evidence_ref),
    )
    _emit_payload(payload, args.format, list_pending=False)
    return 0


def main() -> int:
    return asyncio.run(_run(_parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
