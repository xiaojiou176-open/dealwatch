#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGETS: tuple[tuple[str, str], ...] = (
    (".pytest_cache", "pytest cache"),
    (".runtime-cache/operator/temp", "repo-local temporary operator artifacts"),
    (".runtime-cache/operator/smoke", "repo-local smoke logs"),
    ("build", "backend build output"),
    ("frontend/dist", "frontend build output"),
)
HEAVY_TARGETS: tuple[tuple[str, str], ...] = (
    (".venv", "backend virtualenv"),
    ("frontend/node_modules", "frontend dependency install tree"),
    ("frontend/.pnpm-store", "non-canonical frontend-local pnpm store"),
)
PROTECTED_PREFIXES: tuple[str, ...] = (
    ".git",
    ".runtime-cache/browser-identity",
    ".runtime-cache/logs",
    ".runtime-cache/runs",
)
PROTECTED_EXACT: tuple[str, ...] = (
    ".runtime-cache/operator",
    ".pnpm-store",
)


@dataclass(slots=True)
class CleanupTarget:
    path: Path
    label: str
    size_bytes: int

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


def _validate_target(path: Path) -> None:
    rel = path.relative_to(ROOT).as_posix()
    if rel in PROTECTED_EXACT:
        raise ValueError(f"refusing to target protected path: {rel}")
    for prefix in PROTECTED_PREFIXES:
        if rel == prefix or rel.startswith(prefix + "/"):
            raise ValueError(f"refusing to target protected path: {rel}")


def collect_targets(*, include_heavy: bool) -> list[CleanupTarget]:
    selected = list(DEFAULT_TARGETS)
    if include_heavy:
        selected.extend(HEAVY_TARGETS)

    targets: list[CleanupTarget] = []
    for rel_path, label in selected:
        path = ROOT / rel_path
        _validate_target(path)
        if path.exists():
            targets.append(
                CleanupTarget(path=path, label=label, size_bytes=_path_size(path))
            )
    return targets


def render_report(targets: list[CleanupTarget], *, dry_run: bool) -> str:
    total = sum(target.size_bytes for target in targets)
    lines = [
        "DealWatch local rebuildables cleanup",
        f"mode={'dry-run' if dry_run else 'apply'}",
        f"matched={len(targets)}",
        f"estimated_reclaim_bytes={total}",
    ]
    for target in targets:
        lines.append(
            f"- {target.rel_path} | {target.size_bytes} bytes | {target.label}"
        )
    return "\n".join(lines)


def apply_cleanup(targets: list[CleanupTarget]) -> None:
    for target in targets:
        if target.path.is_dir() and not target.path.is_symlink():
            shutil.rmtree(target.path, ignore_errors=False)
        else:
            target.path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Clean repo-local rebuildable DealWatch artifacts."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Show matched local targets without deleting them.")
    mode.add_argument("--apply", action="store_true", help="Delete matched local targets.")
    parser.add_argument(
        "--heavy",
        action="store_true",
        help="Include large rebuildable dependency copies such as .venv and frontend/node_modules.",
    )
    args = parser.parse_args()

    targets = collect_targets(include_heavy=args.heavy)
    print(render_report(targets, dry_run=args.dry_run))
    if args.apply:
        apply_cleanup(targets)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
