from __future__ import annotations

from pathlib import Path

import scripts.verify_release_surface_sync as verify_script


def test_extract_latest_release_tag_ignores_unreleased() -> None:
    changelog = """## [Unreleased]

### Added

- something

## [v0.1.2] - 2026-03-25

### Added

- shipped
"""

    assert verify_script.extract_latest_release_tag(changelog) == "v0.1.2"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_release_surface_sync_main_passes_for_aligned_surfaces(monkeypatch, tmp_path: Path, capsys) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    readme = tmp_path / "README.md"
    site_index = tmp_path / "site" / "index.html"
    site_proof = tmp_path / "site" / "proof.html"
    site_feed = tmp_path / "site" / "feed.xml"

    _write(
        changelog,
        """## [Unreleased]

## [v0.1.2] - 2026-03-25
""",
    )
    _write(
        readme,
        (
            f"See {verify_script.LATEST_RELEASE_URL} and {verify_script.RELEASE_HISTORY_URL} "
            "for release history."
        ),
    )
    _write(
        site_index,
        (
            f"GitHub Releases live here: {verify_script.LATEST_RELEASE_URL}"
        ),
    )
    _write(site_proof, verify_script.LATEST_RELEASE_URL)
    _write(
        site_feed,
        (
            f"{verify_script.LATEST_RELEASE_URL}\n"
            f"{verify_script.CHANGELOG_URL}\n"
            "Latest tagged release: v0.1.2\n"
        ),
    )

    monkeypatch.setattr(verify_script, "CHANGELOG", changelog)
    monkeypatch.setattr(verify_script, "README", readme)
    monkeypatch.setattr(verify_script, "SITE_INDEX", site_index)
    monkeypatch.setattr(verify_script, "SITE_PROOF", site_proof)
    monkeypatch.setattr(verify_script, "SITE_FEED", site_feed)

    assert verify_script.main() == 0
    captured = capsys.readouterr()
    assert "Release surface sync verification passed." in captured.out


def test_release_surface_sync_main_fails_when_feed_omits_latest_tag(monkeypatch, tmp_path: Path, capsys) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    readme = tmp_path / "README.md"
    site_index = tmp_path / "site" / "index.html"
    site_proof = tmp_path / "site" / "proof.html"
    site_feed = tmp_path / "site" / "feed.xml"

    _write(
        changelog,
        """## [Unreleased]

## [v0.1.2] - 2026-03-25
""",
    )
    _write(readme, f"{verify_script.LATEST_RELEASE_URL}\n{verify_script.RELEASE_HISTORY_URL}\n")
    _write(site_index, f"GitHub Releases {verify_script.LATEST_RELEASE_URL}\n")
    _write(site_proof, verify_script.LATEST_RELEASE_URL)
    _write(
        site_feed,
        (
            f"{verify_script.LATEST_RELEASE_URL}\n"
            f"{verify_script.CHANGELOG_URL}\n"
        ),
    )

    monkeypatch.setattr(verify_script, "CHANGELOG", changelog)
    monkeypatch.setattr(verify_script, "README", readme)
    monkeypatch.setattr(verify_script, "SITE_INDEX", site_index)
    monkeypatch.setattr(verify_script, "SITE_PROOF", site_proof)
    monkeypatch.setattr(verify_script, "SITE_FEED", site_feed)

    assert verify_script.main() == 1
    captured = capsys.readouterr()
    assert "site/feed.xml should name the latest tagged release in the summary entry" in captured.out
