#!/usr/bin/env python3
from __future__ import annotations

import sys


def main() -> int:
    print(
        "scripts/clean.py refused: this legacy wide-delete entrypoint is no longer allowed because it can wipe protected DealWatch evidence and browser identity anchors. Use `PYTHONPATH=src uv run python -m dealwatch maintenance --dry-run|--apply`, `python3 scripts/cleanup_local_rebuildables.py --dry-run|--apply [--heavy]`, or `python3 scripts/cleanup_operator_artifacts.py --dry-run|--apply` instead.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
