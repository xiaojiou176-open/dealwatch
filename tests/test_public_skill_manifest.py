from __future__ import annotations

from pathlib import Path


def test_public_skill_manifest_has_single_version_key() -> None:
    manifest = (
        Path(__file__).resolve().parents[1]
        / "public-skills"
        / "dealwatch-readonly-builder"
        / "manifest.yaml"
    )
    lines = manifest.read_text(encoding="utf-8").splitlines()
    version_lines = [line for line in lines if line.startswith("version:")]
    assert version_lines == ["version: 1.1.0"]
