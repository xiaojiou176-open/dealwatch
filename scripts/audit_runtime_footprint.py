#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Final, Literal


ROOT = Path(__file__).resolve().parents[1]
EXTERNAL_CACHE_DIR = Path(
    os.environ.get("EXTERNAL_CACHE_DIR", "~/.cache/dealwatch")
).expanduser()
PERSISTENT_BROWSER_ROOT = EXTERNAL_CACHE_DIR / "browser" / "chrome-user-data"
Classification = Literal[
    "dependency_rebuildable",
    "runtime_evidence",
    "operator_evidence",
    "external_owned_cache",
    "persistent_browser_profile",
    "disposable_generated",
    "legacy_bridge",
]
CleanupLane = Literal[
    "cleanup_local_rebuildables",
    "cleanup_local_rebuildables_heavy",
    "maintenance",
    "keep",
]


@dataclass(frozen=True, slots=True)
class AuditTargetSpec:
    rel_path: str
    classification: Classification
    cleanup_lane: CleanupLane
    notes: str


@dataclass(frozen=True, slots=True)
class AuditEntry:
    path: str
    size_bytes: int
    human_size: str
    mtime: str
    classification: Classification
    cleanup_lane: CleanupLane
    notes: str


@dataclass(frozen=True, slots=True)
class AuditSummary:
    repo_total_bytes: int
    repo_total_human_size: str
    matched_count: int
    missing_count: int
    classification_totals: dict[str, int]
    entries: list[AuditEntry]


AUDIT_TARGETS: Final[tuple[AuditTargetSpec, ...]] = (
    AuditTargetSpec(
        rel_path=".venv",
        classification="dependency_rebuildable",
        cleanup_lane="cleanup_local_rebuildables_heavy",
        notes="Repo-local backend dependency copy. Rebuildable, but heavy cleanup is opt-in.",
    ),
    AuditTargetSpec(
        rel_path=".pnpm-store",
        classification="dependency_rebuildable",
        cleanup_lane="keep",
        notes="Canonical repo-local pnpm store. Keep this namespace inside the repo; do not treat shared-layer reclaim as repo reclaim.",
    ),
    AuditTargetSpec(
        rel_path="frontend/node_modules",
        classification="dependency_rebuildable",
        cleanup_lane="cleanup_local_rebuildables_heavy",
        notes="Repo-local frontend dependency install tree. Heavy cleanup only.",
    ),
    AuditTargetSpec(
        rel_path=".runtime-cache/logs",
        classification="runtime_evidence",
        cleanup_lane="maintenance",
        notes="Product runtime log namespace managed by product maintenance retention.",
    ),
    AuditTargetSpec(
        rel_path=".runtime-cache/runs",
        classification="runtime_evidence",
        cleanup_lane="maintenance",
        notes="Product runtime run artifacts managed by product maintenance retention.",
    ),
    AuditTargetSpec(
        rel_path=".runtime-cache/browser-identity",
        classification="operator_evidence",
        cleanup_lane="keep",
        notes="Repo-owned browser lane identity anchor. Keep this runtime marker instead of treating it as disposable output.",
    ),
    AuditTargetSpec(
        rel_path=".runtime-cache/operator",
        classification="operator_evidence",
        cleanup_lane="keep",
        notes="Repo-local operator evidence root. Duplicate gif-frames cleanup stays in cleanup_operator_artifacts; shared-layer caches remain out of scope.",
    ),
    AuditTargetSpec(
        rel_path="build",
        classification="disposable_generated",
        cleanup_lane="cleanup_local_rebuildables",
        notes="Disposable generated build output. Safe to reclaim through repo-local cleanup.",
    ),
    AuditTargetSpec(
        rel_path="frontend/dist",
        classification="disposable_generated",
        cleanup_lane="cleanup_local_rebuildables",
        notes="Disposable generated frontend bundle. Safe to reclaim through repo-local cleanup.",
    ),
    AuditTargetSpec(
        rel_path=".pytest_cache",
        classification="disposable_generated",
        cleanup_lane="cleanup_local_rebuildables",
        notes="Disposable pytest cache. Safe to reclaim through repo-local cleanup.",
    ),
    AuditTargetSpec(
        rel_path=".legacy-runtime",
        classification="legacy_bridge",
        cleanup_lane="keep",
        notes="Deprecated SQLite bridge namespace. Keep separate from product runtime and shared-layer cleanup.",
    ),
)


def _path_size(path: Path, *, excluded_roots: tuple[Path, ...] = ()) -> int:
    if not path.exists():
        return 0
    try:
        resolved_path = path.resolve()
    except OSError:
        resolved_path = path
    if any(
        resolved_path == excluded_root or excluded_root in resolved_path.parents
        for excluded_root in excluded_roots
    ):
        return 0
    if path.is_symlink():
        return path.lstat().st_size
    if path.is_file():
        return path.stat().st_size

    total = 0
    for child in path.rglob("*"):
        try:
            resolved_child = child.resolve()
        except OSError:
            continue
        if any(
            resolved_child == excluded_root or excluded_root in resolved_child.parents
            for excluded_root in excluded_roots
        ):
            continue
        try:
            if child.is_symlink():
                total += child.lstat().st_size
            elif child.is_file():
                total += child.stat().st_size
        except OSError:
            continue
    return total


def _format_human_size(size_bytes: int) -> str:
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    value = float(size_bytes)
    unit = units[0]
    for unit in units:
        if value < 1024.0 or unit == units[-1]:
            break
        value /= 1024.0
    if unit == "B":
        return f"{int(value)} {unit}"
    return f"{value:.1f} {unit}"


def _format_mtime(path: Path) -> str:
    timestamp = path.stat().st_mtime
    return datetime.fromtimestamp(timestamp).astimezone().isoformat(timespec="seconds")


def collect_entries() -> tuple[list[AuditEntry], int]:
    entries: list[AuditEntry] = []
    missing_count = 0
    for spec in AUDIT_TARGETS:
        path = ROOT / spec.rel_path
        if not path.exists():
            missing_count += 1
            continue
        size_bytes = _path_size(path)
        entries.append(
            AuditEntry(
                path=spec.rel_path,
                size_bytes=size_bytes,
                human_size=_format_human_size(size_bytes),
                mtime=_format_mtime(path),
                classification=spec.classification,
                cleanup_lane=spec.cleanup_lane,
                notes=spec.notes,
            )
        )
    if PERSISTENT_BROWSER_ROOT.exists():
        size_bytes = _path_size(PERSISTENT_BROWSER_ROOT)
        entries.append(
            AuditEntry(
                path=str(PERSISTENT_BROWSER_ROOT),
                size_bytes=size_bytes,
                human_size=_format_human_size(size_bytes),
                mtime=_format_mtime(PERSISTENT_BROWSER_ROOT),
                classification="persistent_browser_profile",
                cleanup_lane="keep",
                notes="Dedicated DealWatch Chrome root. Persistent browser workspace; exclude from TTL, cache budget cleanup, and rebuildable cleanup.",
            )
        )
    if EXTERNAL_CACHE_DIR.exists():
        excluded_roots = (PERSISTENT_BROWSER_ROOT.resolve(),) if PERSISTENT_BROWSER_ROOT.exists() else ()
        size_bytes = _path_size(EXTERNAL_CACHE_DIR, excluded_roots=excluded_roots)
        entries.append(
            AuditEntry(
                path=str(EXTERNAL_CACHE_DIR),
                size_bytes=size_bytes,
                human_size=_format_human_size(size_bytes),
                mtime=_format_mtime(EXTERNAL_CACHE_DIR),
                classification="external_owned_cache",
                cleanup_lane="maintenance",
                notes="Repo-owned external cache root excluding the dedicated persistent browser workspace. Shared-layer caches remain out of scope.",
            )
        )
    return entries, missing_count


def build_summary() -> AuditSummary:
    entries, missing_count = collect_entries()
    classification_totals: dict[str, int] = {
        "dependency_rebuildable": 0,
        "runtime_evidence": 0,
        "operator_evidence": 0,
        "external_owned_cache": 0,
        "persistent_browser_profile": 0,
        "disposable_generated": 0,
        "legacy_bridge": 0,
    }
    for entry in entries:
        classification_totals[entry.classification] += entry.size_bytes

    repo_total_bytes = _path_size(ROOT)
    return AuditSummary(
        repo_total_bytes=repo_total_bytes,
        repo_total_human_size=_format_human_size(repo_total_bytes),
        matched_count=len(entries),
        missing_count=missing_count,
        classification_totals=classification_totals,
        entries=entries,
    )


def render_text(summary: AuditSummary) -> str:
    lines = [
        "DealWatch runtime footprint audit",
        "scope=repo-owned-internal-and-external",
        f"repo_total_bytes={summary.repo_total_bytes}",
        f"repo_total_human_size={summary.repo_total_human_size}",
        f"matched_count={summary.matched_count}",
        f"missing_count={summary.missing_count}",
        "classification_totals:",
    ]
    for classification, total in summary.classification_totals.items():
        lines.append(
            f"- {classification} | {total} bytes | {_format_human_size(total)}"
        )
    lines.append("entries:")
    for entry in summary.entries:
        lines.append(
            f"- {entry.path} | {entry.size_bytes} bytes | {entry.human_size} | "
            f"{entry.mtime} | {entry.classification} | {entry.cleanup_lane} | {entry.notes}"
        )
    return "\n".join(lines)


def render_json(summary: AuditSummary) -> str:
    payload = {
        "scope": "repo-owned-internal-and-external",
        "repo_total_bytes": summary.repo_total_bytes,
        "repo_total_human_size": summary.repo_total_human_size,
        "matched_count": summary.matched_count,
        "missing_count": summary.missing_count,
        "classification_totals": {
            key: {
                "size_bytes": value,
                "human_size": _format_human_size(value),
            }
            for key, value in summary.classification_totals.items()
        },
        "entries": [asdict(entry) for entry in summary.entries],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit DealWatch repo-local runtime and rebuildable footprint."
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    args = parser.parse_args()

    summary = build_summary()
    if args.format == "json":
        print(render_json(summary))
    else:
        print(render_text(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
