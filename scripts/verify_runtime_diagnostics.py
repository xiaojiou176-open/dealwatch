#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_SNIPPETS = {
    ROOT / "src" / "dealwatch" / "application" / "services.py": [
        "run.error_message = str(exc)",
        "task.last_error_message = str(exc)",
    ],
}

ALLOWED_PRINT_FILES = {
    ROOT / "src" / "dealwatch" / "cli.py",
    ROOT / "src" / "dealwatch" / "mcp" / "server.py",
    ROOT / "src" / "dealwatch" / "runtime_preflight.py",
    ROOT / "src" / "dealwatch" / "stores" / "base_adapter.py",
}


def iter_python_files() -> list[Path]:
    return sorted((ROOT / "src").rglob("*.py"))


def main() -> int:
    findings: list[str] = []

    for path, snippets in FORBIDDEN_SNIPPETS.items():
        text = path.read_text(encoding="utf-8")
        for snippet in snippets:
            if snippet in text:
                findings.append(
                    f"{path.relative_to(ROOT)} still contains forbidden runtime diagnostic snippet: {snippet}"
                )

    for path in iter_python_files():
        text = path.read_text(encoding="utf-8")
        if "print(" in text and path not in ALLOWED_PRINT_FILES:
            findings.append(f"{path.relative_to(ROOT)} contains print() outside the allowlist")

    if findings:
        print("Runtime diagnostics verification failed:")
        for finding in findings:
            print(f" - {finding}")
        return 1

    print("Runtime diagnostics verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
