#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SVG = ROOT / "site" / "favicon.svg"
ASSET_DIR = ROOT / "browser-extension" / "assets"
SIZES = (16, 32, 48, 128)


def run_sips(size: int, output: Path) -> None:
    subprocess.run(
        [
            "sips",
            "-s",
            "format",
            "png",
            "--resampleWidth",
            str(size),
            str(SOURCE_SVG),
            "--out",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def main() -> int:
    if not SOURCE_SVG.exists():
        print(f"Missing source asset: {SOURCE_SVG}", file=sys.stderr)
        return 1
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    for size in SIZES:
        output = ASSET_DIR / f"icon-{size}.png"
        run_sips(size, output)
        print(f"generated={output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
