from __future__ import annotations

from pathlib import Path

from dealwatch.application.store_onboarding import (
    _LIMITED_SUPPORT_TRUTH_SOURCES,
    _build_store_truth_sources,
)
from dealwatch.infra.config import PROJECT_ROOT


def test_store_onboarding_truth_sources_point_to_existing_files() -> None:
    paths = _build_store_truth_sources(
        store_key="walmart",
        adapter_file_path=None,
        contract_test_paths=[],
    )
    paths.extend(_LIMITED_SUPPORT_TRUTH_SOURCES)

    missing = [relative for relative in paths if not (PROJECT_ROOT / relative).exists()]
    assert missing == []


def test_contributing_runbook_links_point_to_existing_files() -> None:
    readme = PROJECT_ROOT / "CONTRIBUTING.md"
    links = [
        "docs/runbooks/store-onboarding-contract.md",
    ]

    text = readme.read_text(encoding="utf-8")
    missing = [relative for relative in links if relative in text and not (PROJECT_ROOT / relative).exists()]
    assert missing == []
    assert ".agents/Docs/" not in text
