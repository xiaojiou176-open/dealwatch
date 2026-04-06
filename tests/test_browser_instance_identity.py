from __future__ import annotations

from pathlib import Path

from scripts.shared.browser_instance_identity import (
    BROWSER_IDENTITY_RUNTIME_DIRNAME,
    build_browser_identity_page_html,
    write_browser_identity_page,
)


def test_build_browser_identity_page_html_contains_required_fields() -> None:
    html = build_browser_identity_page_html(
        repo_label="dealwatch",
        repo_root="/tmp/dealwatch",
        cdp_url="http://127.0.0.1:9333",
        cdp_port=9333,
        user_data_dir="/tmp/chrome-user-data",
        profile_name="dealwatch",
        profile_directory="Profile 21",
        accent="#0f766e",
        monogram="DW",
        quick_links=[("Target account", "https://www.target.com/account")],
    )

    assert "dealwatch · 9333 · browser lane" in html
    assert "http://127.0.0.1:9333" in html
    assert "/tmp/dealwatch" in html
    assert "/tmp/chrome-user-data" in html
    assert "Profile 21" in html
    assert "Target account" in html
    assert "Keep it as the left-most anchor" in html


def test_write_browser_identity_page_writes_under_runtime_cache(tmp_path: Path) -> None:
    result = write_browser_identity_page(
        repo_root=tmp_path,
        env={
            "DEALWATCH_BROWSER_IDENTITY_LABEL": "DealWatch Lane",
            "DEALWATCH_BROWSER_IDENTITY_ACCENT": "#2563eb",
        },
        cdp_url="http://127.0.0.1:9333",
        cdp_port=9333,
        user_data_dir="/tmp/chrome-user-data",
        profile_name="dealwatch",
        profile_directory="Profile 21",
        quick_links=[("Walmart account", "https://www.walmart.com/account")],
    )

    assert result.identity_path == tmp_path / ".runtime-cache" / BROWSER_IDENTITY_RUNTIME_DIRNAME / "index.html"
    assert result.identity_path.exists()
    assert result.identity_url.startswith("file://")

    payload = result.identity_path.read_text(encoding="utf-8")
    assert "DealWatch Lane" in payload
    assert "#2563eb" in payload
    assert "/tmp/chrome-user-data" in payload
