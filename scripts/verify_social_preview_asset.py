#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOCIAL_PREVIEW = ROOT / "assets" / "social" / "social-preview-1280x640.png"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_BYTES = 1_000_000
MIN_WIDTH = 1280
MIN_HEIGHT = 640


def read_png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as fh:
        signature = fh.read(8)
        if len(signature) != 8 or signature != PNG_SIGNATURE:
            raise ValueError("not_a_png")
        length_bytes = fh.read(4)
        if len(length_bytes) != 4:
            raise ValueError("truncated_ihdr_length")
        ihdr_length = int.from_bytes(length_bytes, "big")
        if ihdr_length != 13:
            raise ValueError("invalid_ihdr_length")
        chunk_type = fh.read(4)
        if len(chunk_type) != 4 or chunk_type != b"IHDR":
            raise ValueError("missing_ihdr")
        data = fh.read(ihdr_length)
        if len(data) != ihdr_length:
            raise ValueError("truncated_ihdr")
        width = int.from_bytes(data[:4], "big")
        height = int.from_bytes(data[4:8], "big")
        return width, height


def main() -> int:
    findings: list[str] = []
    if not SOCIAL_PREVIEW.exists():
        findings.append(f"Missing social preview asset: {SOCIAL_PREVIEW.relative_to(ROOT)}")
    else:
        size = SOCIAL_PREVIEW.stat().st_size
        if size > MAX_BYTES:
            findings.append(
                f"Social preview asset is too large: {size} bytes (max {MAX_BYTES})"
            )
        try:
            width, height = read_png_dimensions(SOCIAL_PREVIEW)
        except ValueError as exc:
            findings.append(f"Social preview asset is invalid PNG: {exc}")
        else:
            if width < MIN_WIDTH or height < MIN_HEIGHT:
                findings.append(
                    f"Social preview asset is too small: {width}x{height} (min {MIN_WIDTH}x{MIN_HEIGHT})"
                )
            if width * MIN_HEIGHT != height * MIN_WIDTH:
                findings.append(
                    f"Social preview asset must keep a 2:1 ratio, found {width}x{height}"
                )
            print(f"social_preview_dimensions={width}x{height}")
            print(f"social_preview_size_bytes={size}")

    if findings:
        print("Social preview asset verification failed:")
        for finding in findings:
            print(f" - {finding}")
        return 1

    print("Social preview asset verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
