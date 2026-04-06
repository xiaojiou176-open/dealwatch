#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
SOCIAL = ROOT / "assets" / "social"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MIN_WIDTH = 1280
MIN_HEIGHT = 640

EXPECTED = {
    SITE / "index.html": SOCIAL / "og-home.png",
    SITE / "quick-start.html": SOCIAL / "og-quick-start.png",
    SITE / "compare-preview.html": SOCIAL / "og-compare-preview.png",
    SITE / "proof.html": SOCIAL / "og-proof.png",
    SITE / "faq.html": SOCIAL / "og-faq.png",
    SITE / "compare-vs-tracker.html": SOCIAL / "og-comparison.png",
}


def read_png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as fh:
        signature = fh.read(8)
        if signature != PNG_SIGNATURE:
            raise ValueError("not_a_png")
        length_bytes = fh.read(4)
        if len(length_bytes) != 4:
            raise ValueError("truncated_ihdr_length")
        ihdr_length = int.from_bytes(length_bytes, "big")
        if ihdr_length != 13:
            raise ValueError("invalid_ihdr_length")
        chunk_type = fh.read(4)
        if chunk_type != b"IHDR":
            raise ValueError("missing_ihdr")
        data = fh.read(ihdr_length)
        if len(data) != ihdr_length:
            raise ValueError("truncated_ihdr")
        width = int.from_bytes(data[:4], "big")
        height = int.from_bytes(data[4:8], "big")
        return width, height


def main() -> int:
    findings: list[str] = []

    for html_path, image_path in EXPECTED.items():
        if not html_path.exists():
            findings.append(f"Missing site page: {html_path.relative_to(ROOT)}")
            continue
        if not image_path.exists():
            findings.append(f"Missing OG asset: {image_path.relative_to(ROOT)}")
            continue

        text = html_path.read_text(encoding="utf-8")
        expected_relative = image_path.relative_to(ROOT).as_posix()
        if expected_relative not in text:
            findings.append(
                f"{html_path.relative_to(ROOT)} does not reference {expected_relative}"
            )

        try:
            width, height = read_png_dimensions(image_path)
        except ValueError as exc:
            findings.append(f"{image_path.relative_to(ROOT)} invalid PNG: {exc}")
            continue

        if width < MIN_WIDTH or height < MIN_HEIGHT:
            findings.append(
                f"{image_path.relative_to(ROOT)} too small: {width}x{height}"
            )

    if findings:
        print("Social preview matrix verification failed:")
        for finding in findings:
            print(f" - {finding}")
        return 1

    print("Social preview matrix verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
