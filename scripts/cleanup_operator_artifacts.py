#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_ROOT = ROOT / ".runtime-cache" / "operator"
GIF_FRAME_DIRS = (
    "gif-frames",
    "gif-frames-final",
    "gif-frames-final2",
    "gif-frames-new",
)
PROTECTED_PREFIXES = (
    "gemini-audit",
)
PROTECTED_SUFFIXES = (
    ".patch",
    ".tgz",
)
PROTECTED_NAME_PARTS = (
    "history",
    "release",
)


@dataclass(slots=True)
class ArtifactDecision:
    action: str
    path: Path
    size_bytes: int
    reason: str

    @property
    def rel_path(self) -> str:
        return str(self.path.relative_to(ROOT))


def _path_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_symlink():
        return path.lstat().st_size
    if path.is_file():
        return path.stat().st_size

    total = 0
    for child in path.rglob("*"):
        try:
            if child.is_symlink():
                total += child.lstat().st_size
            elif child.is_file():
                total += child.stat().st_size
        except OSError:
            continue
    return total


def _candidate_dirs() -> list[Path]:
    return [
        ARTIFACTS_ROOT / name
        for name in GIF_FRAME_DIRS
        if (ARTIFACTS_ROOT / name).is_dir()
    ]


def _latest_candidate(paths: list[Path]) -> Path | None:
    if not paths:
        return None
    return max(paths, key=lambda path: path.stat().st_mtime)


def collect_decisions() -> list[ArtifactDecision]:
    candidates = _candidate_dirs()
    latest = _latest_candidate(candidates)
    decisions: list[ArtifactDecision] = []

    for path in candidates:
        if latest is not None and path == latest:
            decisions.append(
                ArtifactDecision(
                    action="keep",
                    path=path,
                    size_bytes=_path_size(path),
                    reason="latest gif-frames directory by mtime",
                )
            )
        elif len(candidates) <= 1:
            decisions.append(
                ArtifactDecision(
                    action="keep",
                    path=path,
                    size_bytes=_path_size(path),
                    reason="only gif-frames directory present",
                )
            )
        else:
            decisions.append(
                ArtifactDecision(
                    action="delete",
                    path=path,
                    size_bytes=_path_size(path),
                    reason="older duplicate gif-frames directory",
                )
            )
    return decisions


def render_report(decisions: list[ArtifactDecision], *, dry_run: bool) -> str:
    keep_count = sum(1 for item in decisions if item.action == "keep")
    delete_targets = [item for item in decisions if item.action == "delete"]
    total_bytes = sum(item.size_bytes for item in delete_targets)
    lines = [
        "DealWatch operator artifacts cleanup",
        f"mode={'dry-run' if dry_run else 'apply'}",
        f"keep_count={keep_count}",
        f"delete_count={len(delete_targets)}",
        f"estimated_reclaim_bytes={total_bytes}",
    ]
    for item in decisions:
        lines.append(
            f"- {item.action} | {item.rel_path} | {item.size_bytes} bytes | {item.reason}"
        )
    lines.append(
        "- protected | .runtime-cache/operator/gemini-audit | preserved by policy"
    )
    lines.append(
        "- protected | .runtime-cache/operator/*.patch|*.tgz|*history*|*release* | preserved by policy"
    )
    return "\n".join(lines)


def apply_cleanup(decisions: list[ArtifactDecision]) -> None:
    for item in decisions:
        if item.action != "delete":
            continue
        shutil.rmtree(item.path, ignore_errors=False)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Clean duplicate operator evidence frame directories under .runtime-cache/operator."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Show keep/delete decisions without deleting directories.")
    mode.add_argument("--apply", action="store_true", help="Delete duplicate gif-frames directories and keep the latest one.")
    args = parser.parse_args()

    decisions = collect_decisions()
    print(render_report(decisions, dry_run=args.dry_run))
    if args.apply:
        apply_cleanup(decisions)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
