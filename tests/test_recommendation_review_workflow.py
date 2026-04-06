from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _script_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return env


def test_recommendation_shadow_review_script_records_review_and_refreshes_summary(tmp_path) -> None:
    workspace = tmp_path / "recommendation-review"
    campaign = subprocess.run(
        [
            sys.executable,
            "scripts/run_recommendation_evaluation_campaign.py",
            "--workspace",
            str(workspace),
            "--seed-fixture-corpus",
        ],
        cwd=ROOT,
        env=_script_env(),
        check=True,
        capture_output=True,
        text=True,
    )
    campaign_payload = json.loads(campaign.stdout)
    pending_before = subprocess.run(
        [
            sys.executable,
            "scripts/review_recommendation_shadow.py",
            "--workspace",
            str(workspace),
            "--list-pending",
        ],
        cwd=ROOT,
        env=_script_env(),
        check=True,
        capture_output=True,
        text=True,
    )
    pending_payload = json.loads(pending_before.stdout)
    assert pending_payload["pending_count"] == 2
    artifact_id = pending_payload["pending_reviews"][0]["artifact_id"]

    pending_text = subprocess.run(
        [
            sys.executable,
            "scripts/review_recommendation_shadow.py",
            "--workspace",
            str(workspace),
            "--list-pending",
            "--format",
            "text",
        ],
        cwd=ROOT,
        env=_script_env(),
        check=True,
        capture_output=True,
        text=True,
    )
    assert "Recommendation review queue" in pending_text.stdout
    assert "Queue snapshot: reviewed=0 | pending=2 | issued=1 | abstained=1" in pending_text.stdout
    assert "Disagreement buckets: none" in pending_text.stdout
    assert f"1. artifact_id={artifact_id}" in pending_text.stdout

    review = subprocess.run(
        [
            sys.executable,
            "scripts/review_recommendation_shadow.py",
            "--workspace",
            str(workspace),
            "--artifact-id",
            artifact_id,
            "--reviewer",
            "maintainer",
            "--decision",
            "overridden",
            "--reason-code",
            "false_positive",
            "--outcome-category",
            "false_positive",
            "--expected-verdict",
            "recheck_later",
            "--actual-verdict",
            "wait",
            "--observed-outcome",
            "Later deterministic evidence favored a more cautious recheck_later call.",
            "--notes",
            "The internal wait verdict overreached.",
            "--follow-up-action",
            "Keep collecting timing evidence.",
            "--evidence-ref",
            "post_review_outcome|Later observed outcome|review.observed_outcome",
        ],
        cwd=ROOT,
        env=_script_env(),
        check=True,
        capture_output=True,
        text=True,
    )
    review_payload = json.loads(review.stdout)

    review_text = subprocess.run(
        [
            sys.executable,
            "scripts/review_recommendation_shadow.py",
            "--workspace",
            str(workspace),
            "--artifact-id",
            pending_payload["pending_reviews"][1]["artifact_id"],
            "--reviewer",
            "maintainer",
            "--decision",
            "confirmed",
            "--reason-code",
            "correct_verdict",
            "--outcome-category",
            "correct_verdict",
            "--observed-outcome",
            "The wait verdict remained the safest internal-only decision after review.",
            "--notes",
            "Keep the current wait posture.",
            "--format",
            "text",
        ],
        cwd=ROOT,
        env=_script_env(),
        check=True,
        capture_output=True,
        text=True,
    )
    assert "Recommendation review recorded" in review_text.stdout
    assert "Agreement bucket: agreement | expected=n/a | actual=wait" in review_text.stdout
    assert "Readiness snapshot: reviewed=2 | pending=0 | confirmed=1 | overridden=1 | rejected=0" in review_text.stdout
    assert "Disagreement buckets: false_positive=1" in review_text.stdout

    assert review_payload["review_record"]["artifact_id"] == artifact_id
    assert review_payload["review_record"]["decision"] == "overridden"
    assert review_payload["review_record"]["agreement_bucket"] == "false_positive"
    assert Path(review_payload["review_log_path"]).exists() is True

    summary_path = Path(review_payload["monitoring_summary_path"])
    replay_manifest_path = Path(review_payload["replay_manifest_path"])
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    replay_manifest = json.loads(replay_manifest_path.read_text(encoding="utf-8"))

    assert summary["review_record_count"] == 2
    assert summary["summary"]["reviewed_count"] == 2
    assert summary["summary"]["review_pending_count"] == 0
    assert summary["summary"]["review_state_buckets"]["confirmed"] == 1
    assert summary["summary"]["review_state_buckets"]["overridden"] == 1
    assert summary["summary"]["disagreement_buckets"]["false_positive"] == 1

    reviewed_entry = next(
        entry for entry in replay_manifest["entries"] if entry.get("artifact_id") == artifact_id
    )
    assert reviewed_entry["review_state"] == "overridden"
    assert reviewed_entry["adjudication"]["expected_verdict"] == "recheck_later"

    pending_after = subprocess.run(
        [
            sys.executable,
            "scripts/review_recommendation_shadow.py",
            "--workspace",
            str(workspace),
            "--list-pending",
        ],
        cwd=ROOT,
        env=_script_env(),
        check=True,
        capture_output=True,
        text=True,
    )
    pending_after_payload = json.loads(pending_after.stdout)
    assert pending_after_payload["pending_count"] == 0
    assert Path(campaign_payload["artifact_paths"]["campaign_report_path"]).exists() is True


def test_recommendation_shadow_review_script_requires_deeper_disagreement_details(tmp_path) -> None:
    workspace = tmp_path / "recommendation-review-validation"
    subprocess.run(
        [
            sys.executable,
            "scripts/run_recommendation_evaluation_campaign.py",
            "--workspace",
            str(workspace),
            "--seed-fixture-corpus",
        ],
        cwd=ROOT,
        env=_script_env(),
        check=True,
        capture_output=True,
        text=True,
    )
    pending_before = subprocess.run(
        [
            sys.executable,
            "scripts/review_recommendation_shadow.py",
            "--workspace",
            str(workspace),
            "--list-pending",
        ],
        cwd=ROOT,
        env=_script_env(),
        check=True,
        capture_output=True,
        text=True,
    )
    artifact_id = json.loads(pending_before.stdout)["pending_reviews"][0]["artifact_id"]

    review = subprocess.run(
        [
            sys.executable,
            "scripts/review_recommendation_shadow.py",
            "--workspace",
            str(workspace),
            "--artifact-id",
            artifact_id,
            "--reviewer",
            "maintainer",
            "--decision",
            "overridden",
            "--reason-code",
            "false_positive",
            "--outcome-category",
            "false_positive",
            "--observed-outcome",
            "The verdict was too eager for the available evidence.",
        ],
        cwd=ROOT,
        env=_script_env(),
        check=False,
        capture_output=True,
        text=True,
    )

    assert review.returncode != 0
    assert "Deeper disagreement review requires --expected-verdict, --actual-verdict" in review.stderr
