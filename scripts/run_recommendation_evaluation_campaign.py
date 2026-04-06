#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from dealwatch.jobs.recommendation_evaluation import (
    DEFAULT_RECOMMENDATION_EVAL_WORKSPACE,
    generate_recommendation_replay_campaign,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the internal-only recommendation replay campaign."
    )
    parser.add_argument(
        "--workspace",
        default=str(DEFAULT_RECOMMENDATION_EVAL_WORKSPACE),
        help="Repo-local workspace used for the current internal recommendation evaluation run and replay artifacts.",
    )
    parser.add_argument(
        "--seed-fixture-corpus",
        action="store_true",
        help="Seed the workspace with the repo-owned deterministic compare corpus before generating the campaign report.",
    )
    parser.add_argument(
        "--import-runtime-corpus",
        action="store_true",
        help="Import non-seeded repo-local runtime summaries into the evaluation workspace.",
    )
    parser.add_argument(
        "--harvest-native-compare-origin",
        action="store_true",
        help="Harvest native compare-origin cases from repo-local runtime-discovered URL pairs into the evaluation workspace.",
    )
    parser.add_argument(
        "--ingest-watch-group-runtime",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--runtime-runs-dir",
        default=".runtime-cache/runs",
        help="Runtime runs root used for non-seeded task/group summary import.",
    )
    parser.add_argument(
        "--native-compare-repeat-budget",
        type=int,
        default=0,
        help=(
            "How many repeated native compare-origin cases to keep per pattern after the "
            "breadth-first distinct-pattern pass. Default: 0."
        ),
    )
    parser.add_argument(
        "--reset-workspace",
        action="store_true",
        help="Clear the workspace before rebuilding the evaluation corpus.",
    )
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> int:
    report = await generate_recommendation_replay_campaign(
        Path(args.workspace),
        seed_fixture_corpus=bool(args.seed_fixture_corpus),
        import_runtime_corpus=bool(args.import_runtime_corpus or args.ingest_watch_group_runtime),
        harvest_native_compare_origin=bool(args.harvest_native_compare_origin),
        reset_workspace=bool(args.reset_workspace),
        runtime_runs_dir=Path(args.runtime_runs_dir),
        native_compare_repeat_budget=max(0, int(args.native_compare_repeat_budget)),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    args = _parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
