from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPARE_PAGE = ROOT / "frontend" / "src" / "pages" / "ComparePage.tsx"
COMPARE_SECTIONS = ROOT / "frontend" / "src" / "pages" / "compare" / "sections.tsx"
CREATE_TASK_PAGE = ROOT / "frontend" / "src" / "pages" / "CreateTaskPage.tsx"
APP_SHELL = ROOT / "frontend" / "src" / "components" / "AppShell.tsx"
EN_CATALOG = ROOT / "site" / "data" / "i18n" / "en.json"
ZH_CATALOG = ROOT / "site" / "data" / "i18n" / "zh-CN.json"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _catalog(path: Path) -> dict:
    return json.loads(_read(path))


def _dot_get(payload: dict, key: str):
    current = payload
    for segment in key.split("."):
        current = current[segment]
    return current


def test_compare_frontend_smoke_keeps_second_pass_flow_discoverable() -> None:
    compare_page = _read(COMPARE_PAGE)
    compare_sections = _read(COMPARE_SECTIONS)
    create_task_page = _read(CREATE_TASK_PAGE)
    app_shell = _read(APP_SHELL)

    # compare -> save local proof -> mint runtime proof
    assert "handleSaveEvidencePackage" in compare_page
    assert "handleCreateRuntimeEvidencePackage" in compare_page
    assert 'compare.execution.lane.label' in compare_page
    assert 'compare.execution.proof.label' in compare_page
    assert 'compare.execution.commit.label' in compare_page
    assert 'id="saved-evidence-panel"' in compare_page
    assert 'id="group-builder-panel"' in compare_page
    assert 'href="#group-builder-panel"' in compare_page

    assert 'compare.decision.saveReviewPackage' in compare_sections
    assert 'compare.decision.createRuntimePackage' in compare_sections
    assert 'compare.savedPanel.openRuntimePackageView' in compare_sections
    assert 'compare.groupBuilder.createButton' in compare_sections
    assert 'compare.candidatePanel.createWatchTaskFromRow' in compare_sections

    # watch-new discoverability
    assert 'pendingWatchTaskDraft.value' in create_task_page
    assert 'Compare handoff' in create_task_page
    assert 'navigate("compare")' in create_task_page

    # shell discoverability + locale switch still live
    assert 'buildShellFocus' in app_shell
    assert 'common.languageLabel' in app_shell
    assert 'shell.secondaryHint' in app_shell
    assert 'shell.focus.proofLabel' in app_shell


def test_compare_frontend_smoke_catalogs_cover_route_and_locale_copy() -> None:
    en = _catalog(EN_CATALOG)
    zh = _catalog(ZH_CATALOG)

    keys = [
        "common.languageLabel",
        "common.locale.en",
        "common.locale.zh-CN",
        "shell.nav.watchNew",
        "compare.route.eyebrow",
        "compare.route.title",
        "compare.route.summary",
        "compare.route.stepCompareTitle",
        "compare.route.stepCompareSummary",
        "compare.route.stepDecisionTitle",
        "compare.route.stepDecisionSummary",
        "compare.route.stepCommitTitle",
        "compare.route.stepCommitSummary",
        "compare.decision.saveReviewPackage",
        "compare.decision.createRuntimePackage",
    ]

    for key in keys:
        assert _dot_get(en, key)
        assert _dot_get(zh, key)
