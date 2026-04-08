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


def test_recommendation_evaluation_campaign_script_seeds_and_reports(tmp_path) -> None:
    workspace = tmp_path / "recommendation-campaign"
    result = subprocess.run(
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

    payload = json.loads(result.stdout)
    summary = payload["summary"]
    assert payload["artifact_kind"] == "recommendation_replay_campaign"
    assert payload["corpus_source"] == "seeded_compare_origin"
    assert payload["readiness_verdict"] == "not_launch_ready"
    assert payload["seed_result"]["seeded_case_count"] == 2
    assert summary["total_replay_items"] == 4
    assert summary["replay_included_count"] == 2
    assert summary["issued_verdict_count"] == 1
    assert summary["abstention_count"] == 1
    assert summary["invalid_or_skipped_count"] == 2
    assert summary["first_pass_distribution"] == {
        "insufficient_evidence": 1,
        "wait": 1,
    }
    assert summary["skip_reason_buckets"] == {
        "invalid_shadow_artifact": 1,
        "missing_shadow_artifact": 1,
    }
    for key, path_value in payload["artifact_paths"].items():
        if not path_value or key == "review_log_path":
            continue
        assert Path(path_value).exists() is True


def test_recommendation_evaluation_campaign_seed_resets_workspace(tmp_path) -> None:
    workspace = tmp_path / "recommendation-campaign-reset"
    command = [
        sys.executable,
        "scripts/run_recommendation_evaluation_campaign.py",
        "--workspace",
        str(workspace),
        "--seed-fixture-corpus",
    ]

    first = subprocess.run(
        command,
        cwd=ROOT,
        env=_script_env(),
        check=True,
        capture_output=True,
        text=True,
    )
    second = subprocess.run(
        command,
        cwd=ROOT,
        env=_script_env(),
        check=True,
        capture_output=True,
        text=True,
    )

    first_payload = json.loads(first.stdout)
    second_payload = json.loads(second.stdout)
    assert first_payload["summary"]["total_replay_items"] == 4
    assert second_payload["summary"]["total_replay_items"] == 4
    assert second_payload["summary"]["review_pending_count"] == 2
    assert second_payload["summary"]["reviewed_count"] == 0


def test_recommendation_evaluation_campaign_ingests_non_seeded_watch_group_runtime(tmp_path) -> None:
    workspace = tmp_path / "recommendation-campaign-runtime"
    runtime_runs_dir = tmp_path / "runtime-runs"
    summary_dir = runtime_runs_dir / "watch-groups" / "group-1" / "run-1"
    summary_dir.mkdir(parents=True, exist_ok=True)
    (summary_dir / "group_run_summary.json").write_text(
        json.dumps(
            {
                "group": {
                    "id": "group-1",
                    "title": "Runtime Pear Group",
                    "zip_code": "98004",
                },
                "run": {
                    "id": "run-1",
                    "status": "succeeded",
                    "started_at": "2026-04-03T00:00:00+00:00",
                    "finished_at": "2026-04-03T00:00:05+00:00",
                    "winner_member_id": "member-a",
                    "runner_up_member_id": "member-b",
                    "winner_effective_price": 3.86,
                    "runner_up_effective_price": 4.13,
                    "price_spread": 0.27,
                    "decision_reason": "lowest_effective_price_with_cashback",
                },
                "member_results": [
                    {
                        "member_id": "member-a",
                        "store_key": "weee",
                        "title_snapshot": "Runtime Pears 3ct",
                        "candidate_key": "runtime pears 3ct | 3 ct",
                        "listed_price": 4.2,
                        "effective_price": 3.86,
                        "source_url": "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
                        "status": "succeeded",
                    },
                    {
                        "member_id": "member-b",
                        "store_key": "ranch99",
                        "title_snapshot": "Runtime Pears 3 ct",
                        "candidate_key": "runtime pears 3 ct | 3 ct",
                        "listed_price": 4.49,
                        "effective_price": 4.13,
                        "source_url": "https://www.99ranch.com/product-details/1615424/8899/078895126389",
                        "status": "succeeded",
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_recommendation_evaluation_campaign.py",
            "--workspace",
            str(workspace),
            "--reset-workspace",
            "--import-runtime-corpus",
            "--runtime-runs-dir",
            str(runtime_runs_dir),
        ],
        cwd=ROOT,
        env=_script_env(),
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    summary = payload["summary"]
    assert payload["corpus_source"] == "non_seeded_watch_group_runtime"
    assert payload["corpus_source_buckets"] == {"non_seeded_watch_group_runtime": 1}
    assert payload["non_seeded_ingest_result"]["non_seeded_case_count"] == 1
    assert summary["total_replay_items"] == 1
    assert summary["replay_included_count"] == 1
    assert summary["issued_verdict_count"] == 1
    assert summary["abstention_count"] == 0
    assert summary["invalid_or_skipped_count"] == 0
    assert summary["first_pass_distribution"] == {"wait": 1}
    assert summary["evidence_strength_buckets"] == {"strong_compare_wait": 1}
    replay_manifest = json.loads(
        Path(payload["artifact_paths"]["replay_manifest_path"]).read_text(encoding="utf-8")
    )
    assert replay_manifest["entries"][0]["surface_anchor"] == "watch_group_run_summary"


def test_recommendation_evaluation_campaign_ingests_non_seeded_watch_task_runtime(tmp_path) -> None:
    workspace = tmp_path / "recommendation-campaign-task-runtime"
    runtime_runs = tmp_path / "runtime-runs"
    summary_dir = runtime_runs / "watch-tasks" / "task-1" / "run-1"
    summary_dir.mkdir(parents=True, exist_ok=True)
    (summary_dir / "task_run_summary.json").write_text(
        json.dumps(
            {
                "task": {
                    "id": "task-1",
                    "status": "active",
                    "zip_code": "98004",
                    "threshold_type": "price_below",
                    "threshold_value": 4.5,
                    "cadence_minutes": 60,
                    "cooldown_minutes": 30,
                },
                "target": {
                    "submitted_url": "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
                    "normalized_url": "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
                    "product_url": "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
                    "store_key": "weee",
                },
                "run": {
                    "id": "run-1",
                    "status": "succeeded",
                    "started_at": "2026-04-03T00:00:00+00:00",
                    "finished_at": "2026-04-03T00:00:04+00:00",
                    "error_code": None,
                    "engine_product_key": "5869",
                },
                "observation": {
                    "title_snapshot": "Asian Honey Pears 3ct",
                    "listed_price": 4.2,
                    "original_price": 5.5,
                    "source_url": "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
                    "observed_at": "2026-04-03T00:00:04+00:00",
                    "unit_price_raw": "3ct",
                },
                "effective_price": 3.78,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_recommendation_evaluation_campaign.py",
            "--workspace",
            str(workspace),
            "--reset-workspace",
            "--import-runtime-corpus",
            "--runtime-runs-dir",
            str(runtime_runs),
        ],
        cwd=ROOT,
        env=_script_env(),
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    summary = payload["summary"]
    assert payload["corpus_source"] == "non_seeded_watch_task_runtime"
    assert payload["corpus_source_buckets"] == {"non_seeded_watch_task_runtime": 1}
    assert payload["non_seeded_ingest_result"]["task_case_count"] == 1
    assert payload["non_seeded_ingest_result"]["group_case_count"] == 0
    assert summary["total_replay_items"] == 1
    assert summary["replay_included_count"] == 1
    assert summary["issued_verdict_count"] == 0
    assert summary["abstention_count"] == 1
    assert summary["invalid_or_skipped_count"] == 0
    assert summary["first_pass_distribution"] == {"insufficient_evidence": 1}
    replay_manifest = json.loads(
        Path(payload["artifact_paths"]["replay_manifest_path"]).read_text(encoding="utf-8")
    )
    assert replay_manifest["entries"][0]["surface_anchor"] == "watch_task_run_summary"


def test_recommendation_evaluation_campaign_marks_repeated_successful_task_as_abstain_when_should_speak(
    tmp_path,
) -> None:
    workspace = tmp_path / "recommendation-campaign-task-signal"
    runtime_runs = tmp_path / "runtime-runs"
    for index in range(25):
        summary_dir = runtime_runs / "watch-tasks" / f"task-1" / f"run-{index}"
        summary_dir.mkdir(parents=True, exist_ok=True)
        (summary_dir / "task_run_summary.json").write_text(
            json.dumps(
                {
                    "task": {
                        "id": "task-1",
                        "status": "active",
                        "zip_code": "98004",
                        "threshold_type": "price_below",
                        "threshold_value": 4.5,
                        "cadence_minutes": 60,
                        "cooldown_minutes": 30,
                    },
                    "target": {
                        "submitted_url": "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
                        "normalized_url": "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
                        "product_url": "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
                        "store_key": "weee",
                    },
                    "run": {
                        "id": f"run-{index}",
                        "status": "succeeded",
                        "started_at": f"2026-04-03T00:00:{index:02d}+00:00",
                        "finished_at": f"2026-04-03T00:01:{index:02d}+00:00",
                        "error_code": None,
                        "engine_product_key": "5869",
                    },
                    "observation": {
                        "title_snapshot": "Asian Honey Pears 3ct",
                        "listed_price": 4.2,
                        "original_price": 5.5,
                        "source_url": "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
                        "observed_at": f"2026-04-03T00:01:{index:02d}+00:00",
                        "unit_price_raw": "3ct",
                    },
                    "effective_price": 3.78,
                    "delivery_events": [
                        {
                            "id": f"delivery-{index}",
                            "provider": "smtp",
                            "recipient": "owner@example.com",
                            "status": "sent",
                            "template_key": "watch-threshold-hit",
                        }
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_recommendation_evaluation_campaign.py",
            "--workspace",
            str(workspace),
            "--reset-workspace",
            "--import-runtime-corpus",
            "--runtime-runs-dir",
            str(runtime_runs),
        ],
        cwd=ROOT,
        env=_script_env(),
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    pending = payload["pending_review_artifacts"]
    assert len(pending) == 1
    assert pending[0]["surface_anchor"] == "watch_task_run_summary"
    assert pending[0]["review_seed_suggestion"] == "abstain_when_should_speak"


def test_recommendation_evaluation_campaign_harvests_native_compare_origin_from_runtime_group(
    tmp_path,
) -> None:
    workspace = tmp_path / "recommendation-campaign-native-compare"
    runtime_runs = tmp_path / "runtime-runs"
    summary_dir = runtime_runs / "watch-groups" / "group-1" / "run-1"
    summary_dir.mkdir(parents=True, exist_ok=True)
    (summary_dir / "group_run_summary.json").write_text(
        json.dumps(
            {
                "group": {
                    "id": "group-1",
                    "title": "Runtime Pear Group",
                    "zip_code": "98004",
                },
                "run": {
                    "id": "run-1",
                    "status": "succeeded",
                    "triggered_by": "manual",
                    "started_at": "2026-04-03T00:00:00+00:00",
                    "finished_at": "2026-04-03T00:00:05+00:00",
                    "winner_member_id": "member-a",
                    "runner_up_member_id": "member-b",
                    "winner_effective_price": 3.86,
                    "runner_up_effective_price": 4.13,
                    "price_spread": 0.27,
                    "decision_reason": "lowest_effective_price_with_cashback",
                },
                "member_results": [
                    {
                        "member_id": "member-a",
                        "store_key": "weee",
                        "title_snapshot": "Asian Honey Pears 3ct",
                        "candidate_key": "asian honey pears 3ct | golden orchard | 3 ct",
                        "listed_price": 4.2,
                        "effective_price": 3.86,
                        "source_url": "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
                        "status": "succeeded",
                    },
                    {
                        "member_id": "member-b",
                        "store_key": "ranch99",
                        "title_snapshot": "Asian Honey Pears 3 ct",
                        "candidate_key": "asian honey pears 3 ct | golden orchard | 3 ct",
                        "listed_price": 4.49,
                        "effective_price": 4.13,
                        "source_url": "https://www.99ranch.com/product-details/1615424/8899/078895126389",
                        "status": "succeeded",
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_recommendation_evaluation_campaign.py",
            "--workspace",
            str(workspace),
            "--reset-workspace",
            "--harvest-native-compare-origin",
            "--runtime-runs-dir",
            str(runtime_runs),
        ],
        cwd=ROOT,
        env=_script_env(),
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload["corpus_source"] == "native_compare_origin"
    assert payload["corpus_source_buckets"] == {"native_compare_origin": 1}
    assert payload["native_compare_origin_result"]["native_compare_origin_case_count"] == 1
    assert payload["native_compare_origin_result"]["source_diversity"]["available_case_count"] == 1
    assert payload["native_compare_origin_result"]["source_diversity"]["selected_case_count"] == 1
    assert payload["native_compare_origin_result"]["source_diversity"]["unique_pattern_count"] == 1
    assert payload["summary"]["total_replay_items"] == 1
    assert payload["summary"]["replay_included_count"] == 1
    replay_manifest = json.loads(
        Path(payload["artifact_paths"]["replay_manifest_path"]).read_text(encoding="utf-8")
    )
    assert replay_manifest["entries"][0]["surface_anchor"] == "compare_preview"


def test_recommendation_evaluation_campaign_harvests_native_compare_origin_from_runtime_compare_evidence(
    tmp_path,
) -> None:
    workspace = tmp_path / "recommendation-campaign-runtime-compare"
    runtime_runs = tmp_path / "runtime-runs"
    artifact_dir = runtime_runs / "compare-evidence" / "artifact-1"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "compare_evidence.json").write_text(
        json.dumps(
            {
                "artifact_id": "artifact-1",
                "artifact_kind": "compare_evidence",
                "saved_at": "2026-04-03T00:00:05+00:00",
                "submitted_inputs": [
                    "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
                    "https://www.99ranch.com/product-details/1615424/8899/078895126389",
                ],
                "zip_code": "98004",
                "submitted_count": 2,
                "resolved_count": 2,
                "comparisons": [
                    {
                        "submitted_url": "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
                        "normalized_url": "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
                        "store_key": "weee",
                        "fetch_succeeded": True,
                        "candidate_key": "asian honey pears 3ct | golden orchard | 3 ct",
                    },
                    {
                        "submitted_url": "https://www.99ranch.com/product-details/1615424/8899/078895126389",
                        "normalized_url": "https://www.99ranch.com/product-details/1615424/8899/078895126389",
                        "store_key": "ranch99",
                        "fetch_succeeded": True,
                        "candidate_key": "asian honey pears 3 ct | golden orchard | 3 ct",
                    },
                ],
                "matches": [
                    {
                        "left_store_key": "weee",
                        "right_store_key": "ranch99",
                        "left_candidate_key": "asian honey pears 3ct | golden orchard | 3 ct",
                        "right_candidate_key": "asian honey pears 3 ct | golden orchard | 3 ct",
                        "score": 100.0,
                    }
                ],
                "recommended_next_step_hint": {
                    "action": "create_watch_group",
                    "reason_code": "multi_candidate_strong_match",
                    "summary": "Multiple candidates resolved and the strongest match signal is strong, so keep them together as a watch group.",
                    "successful_candidate_count": 2,
                    "strongest_match_score": 100.0,
                },
                "risk_notes": [],
                "risk_note_items": [],
                "summary": {
                    "headline": "Runtime compare evidence pears",
                    "saved_at": "2026-04-03T00:00:05+00:00",
                    "successful_candidate_count": 2,
                    "strongest_match_score": 100.0,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_recommendation_evaluation_campaign.py",
            "--workspace",
            str(workspace),
            "--reset-workspace",
            "--harvest-native-compare-origin",
            "--runtime-runs-dir",
            str(runtime_runs),
        ],
        cwd=ROOT,
        env=_script_env(),
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload["corpus_source"] == "native_compare_origin"
    assert payload["native_compare_origin_result"]["source_case_kind"] == "runtime_compare_evidence_package"
    assert payload["native_compare_origin_result"]["available_source_case_count"] == 1
    assert payload["native_compare_origin_result"]["native_compare_origin_case_count"] == 1
    assert payload["summary"]["total_replay_items"] == 1
    assert payload["summary"]["replay_included_count"] == 1
    replay_manifest = json.loads(
        Path(payload["artifact_paths"]["replay_manifest_path"]).read_text(encoding="utf-8")
    )
    assert replay_manifest["entries"][0]["surface_anchor"] == "compare_preview"
    assert replay_manifest["entries"][0]["monitoring"]["corpus_origin"] == "native_compare_origin"


def test_recommendation_evaluation_campaign_prefers_runtime_compare_evidence_over_group_fallback(
    tmp_path,
) -> None:
    workspace = tmp_path / "recommendation-campaign-native-prefer-compare"
    runtime_runs = tmp_path / "runtime-runs"

    compare_artifact_dir = runtime_runs / "compare-evidence" / "artifact-1"
    compare_artifact_dir.mkdir(parents=True, exist_ok=True)
    (compare_artifact_dir / "compare_evidence.json").write_text(
        json.dumps(
            {
                "artifact_id": "artifact-1",
                "artifact_kind": "compare_evidence",
                "saved_at": "2026-04-03T00:00:05+00:00",
                "submitted_inputs": [
                    "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
                    "https://www.99ranch.com/product-details/1615424/8899/078895126389",
                ],
                "zip_code": "98004",
                "submitted_count": 2,
                "resolved_count": 2,
                "comparisons": [
                    {
                        "submitted_url": "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
                        "normalized_url": "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
                        "store_key": "weee",
                        "fetch_succeeded": True,
                        "candidate_key": "asian honey pears 3ct | golden orchard | 3 ct",
                    },
                    {
                        "submitted_url": "https://www.99ranch.com/product-details/1615424/8899/078895126389",
                        "normalized_url": "https://www.99ranch.com/product-details/1615424/8899/078895126389",
                        "store_key": "ranch99",
                        "fetch_succeeded": True,
                        "candidate_key": "asian honey pears 3 ct | golden orchard | 3 ct",
                    },
                ],
                "matches": [
                    {
                        "left_store_key": "weee",
                        "right_store_key": "ranch99",
                        "left_candidate_key": "asian honey pears 3ct | golden orchard | 3 ct",
                        "right_candidate_key": "asian honey pears 3 ct | golden orchard | 3 ct",
                        "score": 100.0,
                    }
                ],
                "recommended_next_step_hint": {
                    "action": "create_watch_group",
                    "reason_code": "multi_candidate_strong_match",
                    "summary": "Multiple candidates resolved and the strongest match signal is strong, so keep them together as a watch group.",
                    "successful_candidate_count": 2,
                    "strongest_match_score": 100.0,
                },
                "risk_notes": [],
                "risk_note_items": [],
                "summary": {
                    "headline": "Runtime compare evidence pears",
                    "saved_at": "2026-04-03T00:00:05+00:00",
                    "successful_candidate_count": 2,
                    "strongest_match_score": 100.0,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    summary_dir = runtime_runs / "watch-groups" / "group-1" / "run-1"
    summary_dir.mkdir(parents=True, exist_ok=True)
    (summary_dir / "group_run_summary.json").write_text(
        json.dumps(
            {
                "group": {"id": "group-1", "title": "Runtime Pear Group", "zip_code": "98004"},
                "run": {
                    "id": "run-1",
                    "status": "succeeded",
                    "triggered_by": "manual",
                    "started_at": "2026-04-03T00:00:00+00:00",
                    "finished_at": "2026-04-03T00:00:05+00:00",
                    "winner_member_id": "member-a",
                    "runner_up_member_id": "member-b",
                    "winner_effective_price": 3.86,
                    "runner_up_effective_price": 4.13,
                    "price_spread": 0.27,
                    "decision_reason": "lowest_effective_price_with_cashback",
                },
                "member_results": [
                    {
                        "member_id": "member-a",
                        "store_key": "weee",
                        "title_snapshot": "Asian Honey Pears 3ct",
                        "candidate_key": "asian honey pears 3ct | golden orchard | 3 ct",
                        "listed_price": 4.2,
                        "effective_price": 3.86,
                        "source_url": "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
                        "status": "succeeded",
                    },
                    {
                        "member_id": "member-b",
                        "store_key": "ranch99",
                        "title_snapshot": "Asian Honey Pears 3 ct",
                        "candidate_key": "asian honey pears 3 ct | golden orchard | 3 ct",
                        "listed_price": 4.49,
                        "effective_price": 4.13,
                        "source_url": "https://www.99ranch.com/product-details/1615424/8899/078895126389",
                        "status": "succeeded",
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_recommendation_evaluation_campaign.py",
            "--workspace",
            str(workspace),
            "--reset-workspace",
            "--harvest-native-compare-origin",
            "--runtime-runs-dir",
            str(runtime_runs),
        ],
        cwd=ROOT,
        env=_script_env(),
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload["native_compare_origin_result"]["source_case_kind"] == "runtime_compare_evidence_package"
    assert payload["native_compare_origin_result"]["available_source_case_count"] == 1


def test_recommendation_evaluation_campaign_harvests_native_compare_origin(tmp_path) -> None:
    workspace = tmp_path / "recommendation-campaign-native-origin"
    runtime_runs_dir = tmp_path / "runtime-runs"
    summary_dir = runtime_runs_dir / "watch-groups" / "group-1" / "run-1"
    summary_dir.mkdir(parents=True, exist_ok=True)
    (summary_dir / "group_run_summary.json").write_text(
        json.dumps(
            {
                "group": {
                    "id": "group-1",
                    "title": "Runtime Pear Group",
                    "zip_code": "98004",
                },
                "run": {
                    "id": "run-1",
                    "status": "succeeded",
                    "started_at": "2026-04-03T00:00:00+00:00",
                    "finished_at": "2026-04-03T00:00:05+00:00",
                    "triggered_by": "manual",
                    "winner_member_id": "member-a",
                    "runner_up_member_id": "member-b",
                    "winner_effective_price": 3.86,
                    "runner_up_effective_price": 4.13,
                    "price_spread": 0.27,
                    "decision_reason": "lowest_effective_price_with_cashback",
                },
                "member_results": [
                    {
                        "member_id": "member-a",
                        "store_key": "weee",
                        "title_snapshot": "Runtime Pears 3ct",
                        "candidate_key": "runtime pears 3ct | 3 ct",
                        "listed_price": 4.2,
                        "effective_price": 3.86,
                        "source_url": "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
                        "status": "succeeded",
                    },
                    {
                        "member_id": "member-b",
                        "store_key": "ranch99",
                        "title_snapshot": "Runtime Pears 3 ct",
                        "candidate_key": "runtime pears 3 ct | 3 ct",
                        "listed_price": 4.49,
                        "effective_price": 4.13,
                        "source_url": "https://www.99ranch.com/product-details/1615424/8899/078895126389",
                        "status": "succeeded",
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_recommendation_evaluation_campaign.py",
            "--workspace",
            str(workspace),
            "--reset-workspace",
            "--harvest-native-compare-origin",
            "--runtime-runs-dir",
            str(runtime_runs_dir),
        ],
        cwd=ROOT,
        env=_script_env(),
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    summary = payload["summary"]
    assert payload["corpus_source"] == "native_compare_origin"
    assert payload["corpus_source_buckets"] == {"native_compare_origin": 1}
    assert payload["native_compare_origin_result"]["source_case_kind"] == "runtime_group_summary_fallback"
    assert payload["native_compare_origin_result"]["native_compare_origin_case_count"] == 1
    assert summary["source_diversity"]["native_compare_origin_source_case_kind"] == (
        "runtime_group_summary_fallback"
    )
    assert any(
        "fall back to reconstructed watch-group summaries" in item
        for item in payload["launch_blockers"]
    )
    assert any(
        "single repeated pattern" in item
        for item in payload["launch_blockers"]
    )
    report_markdown = Path(payload["artifact_paths"]["campaign_report_markdown_path"]).read_text(
        encoding="utf-8"
    )
    assert "Native source case kind: `runtime_group_summary_fallback`" in report_markdown
    assert payload["native_compare_origin_result"]["cases"][0]["label"] == "runtime_group:Runtime Pear Group"
    assert payload["native_compare_origin_result"]["cases"][0]["review_seed_suggestion"] == "correct_verdict"
    assert payload["summary"]["source_diversity"]["native_compare_origin_unique_patterns"] == 1
    assert summary["total_replay_items"] == 1
    assert summary["replay_included_count"] == 1
    assert summary["issued_verdict_count"] == 1


def test_recommendation_evaluation_campaign_prioritizes_distinct_native_compare_origin_patterns(
    tmp_path,
) -> None:
    workspace = tmp_path / "recommendation-campaign-native-origin-depth"
    runtime_runs_dir = tmp_path / "runtime-runs"
    for index in range(12):
        summary_dir = runtime_runs_dir / "watch-groups" / f"group-1" / f"run-{index}"
        summary_dir.mkdir(parents=True, exist_ok=True)
        (summary_dir / "group_run_summary.json").write_text(
            json.dumps(
                {
                    "group": {
                        "id": "group-1",
                        "title": "Runtime Pear Group",
                        "zip_code": "98004",
                    },
                    "run": {
                        "id": f"run-{index}",
                        "status": "succeeded",
                        "started_at": f"2026-04-03T00:00:{index:02d}+00:00",
                        "finished_at": f"2026-04-03T00:01:{index:02d}+00:00",
                        "triggered_by": "manual",
                        "winner_member_id": "member-a",
                        "runner_up_member_id": "member-b",
                        "winner_effective_price": 3.86,
                        "runner_up_effective_price": 4.13,
                        "price_spread": 0.27,
                        "decision_reason": "lowest_effective_price_with_cashback",
                    },
                    "member_results": [
                        {
                            "member_id": "member-a",
                            "store_key": "weee",
                            "title_snapshot": "Asian Honey Pears 3ct",
                            "candidate_key": "asian honey pears 3ct | golden orchard | 3 ct",
                            "listed_price": 4.2,
                            "effective_price": 3.86,
                            "source_url": "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
                            "status": "succeeded",
                        },
                        {
                            "member_id": "member-b",
                            "store_key": "ranch99",
                            "title_snapshot": "Asian Honey Pears 3 ct",
                            "candidate_key": "asian honey pears 3 ct | golden orchard | 3 ct",
                            "listed_price": 4.49,
                            "effective_price": 4.13,
                            "source_url": "https://www.99ranch.com/product-details/1615424/8899/078895126389",
                            "status": "succeeded",
                        },
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_recommendation_evaluation_campaign.py",
            "--workspace",
            str(workspace),
            "--reset-workspace",
            "--harvest-native-compare-origin",
            "--runtime-runs-dir",
            str(runtime_runs_dir),
        ],
        cwd=ROOT,
        env=_script_env(),
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    summary = payload["summary"]
    assert payload["corpus_source"] == "native_compare_origin"
    assert payload["corpus_source_buckets"] == {"native_compare_origin": 1}
    assert payload["native_compare_origin_result"]["native_compare_origin_case_count"] == 1
    assert summary["total_replay_items"] == 1
    assert summary["replay_included_count"] == 1
    assert summary["abstention_count"] == 0
    source_diversity = payload["native_compare_origin_result"]["source_diversity"]
    assert source_diversity["available_case_count"] == 12
    assert source_diversity["selected_case_count"] == 1
    assert source_diversity["unique_pattern_count"] == 1
    assert source_diversity["unique_store_pair_count"] == 1
    assert source_diversity["unique_source_url_pair_family_count"] == 1
    assert source_diversity["breadth_profile"] == "depth_heavy_single_pattern"
    assert source_diversity["concentration_risk"] == "high"
    assert source_diversity["ceiling_signal"] == "single_pattern_runtime_ceiling"
    assert source_diversity["dropped_repeat_count"] == 11
    replay_manifest = json.loads(
        Path(payload["artifact_paths"]["replay_manifest_path"]).read_text(encoding="utf-8")
    )
    assert replay_manifest["entries"][0]["surface_anchor"] == "compare_preview"
    assert replay_manifest["entries"][0]["monitoring"]["corpus_origin"] == "native_compare_origin"
    assert replay_manifest["entries"][0]["monitoring"]["input_profile"] == "compare_preview_only"
    assert summary["source_diversity"]["native_compare_origin_unique_patterns"] == 1
    assert summary["source_diversity"]["native_compare_origin_top_repeated_pattern_share"] == 1.0


def test_recommendation_evaluation_campaign_reports_mixed_seeded_native_and_non_seeded_buckets(
    tmp_path,
) -> None:
    workspace = tmp_path / "recommendation-campaign-mixed-origin"
    runtime_runs_dir = tmp_path / "runtime-runs"
    summary_dir = runtime_runs_dir / "watch-groups" / "group-1" / "run-1"
    summary_dir.mkdir(parents=True, exist_ok=True)
    (summary_dir / "group_run_summary.json").write_text(
        json.dumps(
            {
                "group": {
                    "id": "group-1",
                    "title": "Runtime Pear Group",
                    "zip_code": "98004",
                },
                "run": {
                    "id": "run-1",
                    "status": "succeeded",
                    "started_at": "2026-04-03T00:00:00+00:00",
                    "finished_at": "2026-04-03T00:00:05+00:00",
                    "triggered_by": "manual",
                    "winner_member_id": "member-a",
                    "runner_up_member_id": "member-b",
                    "winner_effective_price": 3.86,
                    "runner_up_effective_price": 4.13,
                    "price_spread": 0.27,
                    "decision_reason": "lowest_effective_price_with_cashback",
                },
                "member_results": [
                    {
                        "member_id": "member-a",
                        "store_key": "weee",
                        "title_snapshot": "Asian Honey Pears 3ct",
                        "candidate_key": "asian honey pears 3ct | golden orchard | 3 ct",
                        "listed_price": 4.2,
                        "effective_price": 3.86,
                        "source_url": "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
                        "status": "succeeded",
                    },
                    {
                        "member_id": "member-b",
                        "store_key": "ranch99",
                        "title_snapshot": "Asian Honey Pears 3 ct",
                        "candidate_key": "asian honey pears 3 ct | golden orchard | 3 ct",
                        "listed_price": 4.49,
                        "effective_price": 4.13,
                        "source_url": "https://www.99ranch.com/product-details/1615424/8899/078895126389",
                        "status": "succeeded",
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_recommendation_evaluation_campaign.py",
            "--workspace",
            str(workspace),
            "--reset-workspace",
            "--seed-fixture-corpus",
            "--import-runtime-corpus",
            "--harvest-native-compare-origin",
            "--runtime-runs-dir",
            str(runtime_runs_dir),
        ],
        cwd=ROOT,
        env=_script_env(),
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    summary = payload["summary"]
    expected_buckets = {
        "seeded_compare_origin": 2,
        "native_compare_origin": 1,
        "non_seeded_watch_group_runtime": 1,
    }
    assert payload["corpus_source"] == "mixed_internal_corpus"
    assert payload["corpus_source_buckets"] == expected_buckets
    assert payload["native_compare_origin_result"]["cases"][0]["review_seed_suggestion"] == "correct_verdict"
    assert summary["total_replay_items"] == 6
    assert summary["replay_included_count"] == 4
    replay_manifest = json.loads(
        Path(payload["artifact_paths"]["replay_manifest_path"]).read_text(encoding="utf-8")
    )
    native_entries = [
        entry
        for entry in replay_manifest["entries"]
        if (entry.get("monitoring") or {}).get("corpus_origin") == "native_compare_origin"
    ]
    assert len(native_entries) == 1
    assert native_entries[0]["surface_anchor"] == "compare_preview"
    assert native_entries[0]["monitoring"]["input_profile"] == "compare_preview_only"

    refreshed = subprocess.run(
        [
            sys.executable,
            "scripts/run_recommendation_evaluation_campaign.py",
            "--workspace",
            str(workspace),
        ],
        cwd=ROOT,
        env=_script_env(),
        check=True,
        capture_output=True,
        text=True,
    )

    refreshed_payload = json.loads(refreshed.stdout)
    assert refreshed_payload["corpus_source"] == "mixed_internal_corpus"
    assert refreshed_payload["corpus_source_buckets"] == expected_buckets
    assert refreshed_payload["summary"]["total_replay_items"] == 6
    assert refreshed_payload["summary"]["replay_included_count"] == 4
