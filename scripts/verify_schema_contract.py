#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_DIR = ROOT / "alembic" / "versions"
ROOT_REVISION_RE = re.compile(r"down_revision\s*=\s*None")


def main() -> int:
    root_migrations: list[Path] = []
    for path in sorted(ALEMBIC_DIR.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        if ROOT_REVISION_RE.search(text):
            root_migrations.append(path)

    if len(root_migrations) != 1:
        print("Schema contract verification failed:")
        print(" - Expected exactly one Alembic root migration.")
        for path in root_migrations:
            print(f" - Found root migration: {path.relative_to(ROOT)}")
        return 1

    print(f"Schema contract verification passed. Root migration: {root_migrations[0].relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
