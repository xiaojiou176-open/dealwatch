from __future__ import annotations

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
TARGETS = [
    ROOT / "src/dealwatch/api",
    ROOT / "src/dealwatch/application",
    ROOT / "src/dealwatch/worker",
    ROOT / "src/dealwatch/persistence",
    ROOT / "scripts/product_smoke.py",
    ROOT / "scripts/smoke_product.sh",
]
PATTERNS = [
    re.compile(r"\bfrom\s+dealwatch\.legacy\.db_repo\s+import\b"),
    re.compile(r"\bDatabaseRepository\b"),
    re.compile(r"\blegacy-import\b"),
    re.compile(r"\blegacy-maintenance\b"),
]


def iter_files(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    return sorted(path for path in target.rglob("*") if path.is_file() and path.suffix in {".py", ".sh"})


def main() -> int:
    failures: list[str] = []
    for target in TARGETS:
        for path in iter_files(target):
            text = path.read_text(encoding="utf-8")
            for lineno, line in enumerate(text.splitlines(), start=1):
                for pattern in PATTERNS:
                    if pattern.search(line):
                        rel = path.relative_to(ROOT)
                        failures.append(f"{rel}:{lineno}: live runtime path references legacy bridge: {line.strip()}")

    if failures:
        print("live runtime legacy bridge references are forbidden:", file=sys.stderr)
        for item in failures:
            print(item, file=sys.stderr)
        return 1

    print("no live runtime legacy bridge references found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
