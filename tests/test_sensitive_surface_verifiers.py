from __future__ import annotations

from pathlib import Path

from scripts.shared.sensitive_surface_patterns import find_sensitive_text_hits
import scripts.verify_sensitive_surface as verify_sensitive_surface


def _host_path_fragment() -> str:
    return "/" + "/".join(("Users", "tester", "private.txt"))


def _host_project_fragment() -> str:
    return "/" + "/".join(("Users", "tester", "project"))


def _temp_path_fragment() -> str:
    return "/" + "/".join(("private", "var", "folders", "abc"))


def _personal_marker() -> str:
    return ", ".join(("Hi", "Yifeng"))


def test_find_sensitive_text_hits_detects_host_paths_and_personal_markers() -> None:
    hits = find_sensitive_text_hits(
        f"bad {_host_path_fragment()} and {_temp_path_fragment()} plus {_personal_marker()}"
    )
    descriptions = {item[0] for item in hits}
    assert "host-specific /Users path literal" in descriptions
    assert "macOS temp/cache path literal" in descriptions
    assert "personal sample marker from browser fixtures" in descriptions


def test_find_sensitive_text_hits_ignores_placeholder_emails_and_generic_profile_names() -> None:
    hits = find_sensitive_text_hits("owner@example.com Profile 21 dealwatch")
    assert hits == []


def test_scan_path_flags_runtime_artifacts(tmp_path: Path) -> None:
    artifact = tmp_path / ".runtime-cache" / "logs" / "dealwatch.log"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("ok", encoding="utf-8")
    findings = verify_sensitive_surface.scan_path(artifact)
    assert findings


def test_scan_text_flags_sensitive_lines(tmp_path: Path) -> None:
    path = tmp_path / "doc.txt"
    path.write_text(f"see {_host_project_fragment()} and {_personal_marker()}", encoding="utf-8")
    findings = verify_sensitive_surface.scan_text(path)
    assert any(_host_project_fragment() in item for item in findings)
    assert any(_personal_marker() in item for item in findings)
