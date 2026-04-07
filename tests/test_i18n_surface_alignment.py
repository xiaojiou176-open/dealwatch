import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPARE_PAGE = ROOT / "frontend" / "src" / "pages" / "ComparePage.tsx"
COMPARE_PAGE_COPY = ROOT / "frontend" / "src" / "pages" / "compare" / "copy.ts"
COMPARE_PAGE_HELPERS = ROOT / "frontend" / "src" / "pages" / "compare" / "helpers.ts"
NOTIFICATION_SETTINGS_PAGE = ROOT / "frontend" / "src" / "pages" / "NotificationSettingsPage.tsx"
INDEX_PAGE = ROOT / "site" / "index.html"
BUILDERS_PAGE = ROOT / "site" / "builders.html"
FAQ_PAGE = ROOT / "site" / "faq.html"
COMPARISON_PAGE = ROOT / "site" / "compare-vs-tracker.html"
PROOF_PAGE = ROOT / "site" / "proof.html"
COMPARE_PREVIEW_PAGE = ROOT / "site" / "compare-preview.html"
QUICK_START_PAGE = ROOT / "site" / "quick-start.html"
COMMUNITY_PAGE = ROOT / "site" / "community.html"
NOT_FOUND_PAGE = ROOT / "site" / "404.html"
USE_CASES_PAGE = ROOT / "site" / "use-cases.html"
LLMS_TXT = ROOT / "site" / "llms.txt"
CATALOG_PATHS = {
    "en": ROOT / "site" / "data" / "i18n" / "en.json",
    "zh-CN": ROOT / "site" / "data" / "i18n" / "zh-CN.json",
}
AI_STATUSES = ("ok", "disabled", "error", "skipped", "unavailable")


def _load_catalogs() -> dict[str, dict]:
    return {locale: json.loads(path.read_text(encoding="utf-8")) for locale, path in CATALOG_PATHS.items()}


def _has_key(catalog: dict, key: str) -> bool:
    current = catalog
    for segment in key.split("."):
        if not isinstance(current, dict) or segment not in current:
            return False
        current = current[segment]
    return True


def _get_value(catalog: dict, key: str):
    current = catalog
    for segment in key.split("."):
        current = current[segment]
    return current


def _read_compare_sources() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in (COMPARE_PAGE, COMPARE_PAGE_COPY, COMPARE_PAGE_HELPERS)
    )


def test_compare_page_shared_catalog_keys_exist() -> None:
    page = _read_compare_sources()
    catalogs = _load_catalogs()

    static_keys = set(re.findall(r'"(compare\.[A-Za-z0-9_.]+)"', page))
    dynamic_keys = {
        *[f"compare.decision.ai.badge.{status}" for status in AI_STATUSES],
        *[f"compare.decision.ai.headline.{status}" for status in AI_STATUSES],
        *[f"compare.decision.ai.summary.{status}" for status in AI_STATUSES if status != "ok"],
    }

    for locale, catalog in catalogs.items():
        missing = sorted(key for key in (static_keys | dynamic_keys) if not _has_key(catalog, key))
        assert not missing, f"{locale} missing compare keys: {missing}"


def test_compare_page_no_longer_renders_direct_compare_fallback_copy() -> None:
    page = COMPARE_PAGE.read_text(encoding="utf-8")
    assert 'draft(locale, COMPARE_COPY' not in page


def test_notification_settings_page_shared_catalog_keys_exist() -> None:
    page = NOTIFICATION_SETTINGS_PAGE.read_text(encoding="utf-8")
    catalogs = _load_catalogs()
    keys = set(re.findall(r'"(settings\.[A-Za-z0-9_.]+)"', page))

    for locale, catalog in catalogs.items():
        missing = sorted(key for key in keys if not _has_key(catalog, key))
        assert not missing, f"{locale} missing notification settings keys: {missing}"


def test_notification_settings_page_no_longer_humanizes_limited_support_actions_inline() -> None:
    page = NOTIFICATION_SETTINGS_PAGE.read_text(encoding="utf-8")
    assert 'split("_").join(" ")' not in page


def test_public_comparison_page_shared_catalog_keys_exist() -> None:
    html = COMPARISON_PAGE.read_text(encoding="utf-8")
    catalogs = _load_catalogs()
    keys = set(re.findall(r'data-i18n(?:-key)?="(site\.comparisonPage\.[^"]+)"', html))

    for locale, catalog in catalogs.items():
        missing = sorted(key for key in keys if not _has_key(catalog, key))
        assert not missing, f"{locale} missing comparison page keys: {missing}"


def test_public_comparison_page_metadata_is_bound_to_shared_keys() -> None:
    html = COMPARISON_PAGE.read_text(encoding="utf-8")

    assert 'data-i18n-key="site.comparisonPage.title"' in html
    assert 'data-i18n-key="site.comparisonPage.description"' in html
    assert '<link rel="canonical" href="https://xiaojiou176-open.github.io/dealwatch/compare-vs-tracker.html"' in html
    assert 'property="og:title"' in html and 'data-i18n-key="site.comparisonPage.title"' in html
    assert 'property="og:description"' in html and 'data-i18n-key="site.comparisonPage.description"' in html
    assert 'name="twitter:title"' in html and 'data-i18n-key="site.comparisonPage.title"' in html
    assert 'name="twitter:description"' in html and 'data-i18n-key="site.comparisonPage.description"' in html


def test_home_page_shared_catalog_keys_exist() -> None:
    html = INDEX_PAGE.read_text(encoding="utf-8")
    catalogs = _load_catalogs()
    keys = set(
        re.findall(
            r'data-i18n(?:-(?:key|aria-label))?="(site\.(?:index|common|compareSurface)\.[^"]+)"',
            html,
        )
    )

    for locale, catalog in catalogs.items():
        missing = sorted(key for key in keys if not _has_key(catalog, key))
        assert not missing, f"{locale} missing index page keys: {missing}"


def test_public_builders_page_shared_catalog_keys_exist() -> None:
    html = BUILDERS_PAGE.read_text(encoding="utf-8")
    catalogs = _load_catalogs()
    keys = set(
        re.findall(
            r'data-i18n(?:-(?:key|aria-label))?="(site\.buildersPage\.[^"]+|site\.common\.[^"]+)"',
            html,
        )
    )

    for locale, catalog in catalogs.items():
        missing = sorted(key for key in keys if not _has_key(catalog, key))
        assert not missing, f"{locale} missing builders page keys: {missing}"


def test_public_tail_pages_shared_catalog_keys_exist() -> None:
    catalogs = _load_catalogs()
    page_map = {
        QUICK_START_PAGE: "quickStartPage",
        COMMUNITY_PAGE: "communityPage",
        NOT_FOUND_PAGE: "notFoundPage",
        USE_CASES_PAGE: "useCasesPage",
    }

    for path, prefix in page_map.items():
        html = path.read_text(encoding="utf-8")
        keys = set(
            re.findall(
                rf'data-i18n(?:-(?:key|aria-label))?="(site\.{prefix}\.[^"]+|site\.common\.[^"]+)"',
                html,
            )
        )
        for locale, catalog in catalogs.items():
            missing = sorted(key for key in keys if not _has_key(catalog, key))
            assert not missing, f"{locale} missing {path.name} keys: {missing}"


def test_quick_start_step_bodies_are_bound_to_shared_catalog() -> None:
    html = QUICK_START_PAGE.read_text(encoding="utf-8")

    assert 'data-i18n="site.quickStartPage.step1Body"' in html
    assert 'data-i18n="site.quickStartPage.step4Body"' in html


def test_homepage_start_here_routes_are_bound_and_present() -> None:
    html = INDEX_PAGE.read_text(encoding="utf-8")

    assert 'data-i18n="site.index.heroSecondaryCta"' in html
    assert 'data-i18n="site.index.heroBuilderCta"' in html
    assert 'data-i18n="site.index.microLinkQuickStart"' in html
    assert 'data-i18n="site.index.microLinkBuilders"' in html
    assert 'data-i18n="site.index.valueCardQuickStartTitle"' in html
    assert 'data-i18n="site.index.valueCardBuildersTitle"' in html
    assert 'data-i18n="site.index.valueFollowupProofLink"' in html
    assert 'data-i18n="site.index.valueFollowupComparisonLink"' in html
    assert 'href="./compare-preview.html#sample-compare-demo"' in html
    assert 'href="./quick-start.html"' in html
    assert 'href="./builders.html"' in html
    assert re.search(
        r'<a class="button-secondary" href="./proof\.html" data-i18n="site\.index\.heroSecondaryCta">',
        html,
    )
    assert re.search(
        r'<a class="button-secondary" href="./quick-start\.html" data-i18n="site\.index\.heroBuilderCta">',
        html,
    )


def test_quick_start_page_prioritizes_local_runtime_path() -> None:
    html = QUICK_START_PAGE.read_text(encoding="utf-8")

    assert 'id="local-runtime-path"' in html
    assert re.search(
        r'<a class="button" href="#local-runtime-path" data-i18n="site\.quickStartPage\.heroPrimaryCta">',
        html,
    )
    assert re.search(
        r'<a class="button-secondary" href="./compare-preview\.html#sample-compare-demo" data-i18n="site\.quickStartPage\.heroSecondaryCta">',
        html,
    )


def test_quick_start_page_exposes_first_success_expectation() -> None:
    html = QUICK_START_PAGE.read_text(encoding="utf-8")

    assert 'data-i18n="site.quickStartPage.successTitle"' in html
    assert 'data-i18n="site.quickStartPage.successSummary"' in html
    assert 'data-i18n="site.quickStartPage.successCardRouteTitle"' in html
    assert 'data-i18n="site.quickStartPage.successCardEvidenceTitle"' in html
    assert 'data-i18n="site.quickStartPage.successCardDecisionTitle"' in html


def test_compare_preview_page_exposes_next_step_routes() -> None:
    html = COMPARE_PREVIEW_PAGE.read_text(encoding="utf-8")

    assert 'data-i18n="site.comparePreviewPage.nextStepsTitle"' in html
    assert 'data-i18n="site.comparePreviewPage.nextStepsQuickStartTitle"' in html
    assert 'data-i18n="site.comparePreviewPage.nextStepsProofTitle"' in html
    assert 'data-i18n="site.comparePreviewPage.nextStepsBuildersTitle"' in html
    assert re.search(
        r'<a(?=[^>]*href="./quick-start\.html")(?=[^>]*data-i18n="site\.comparePreviewPage\.nextStepsQuickStartCta")[^>]*>',
        html,
    )
    assert re.search(
        r'<a(?=[^>]*href="./proof\.html")(?=[^>]*data-i18n="site\.comparePreviewPage\.nextStepsProofCta")[^>]*>',
        html,
    )
    assert re.search(
        r'<a(?=[^>]*href="./builders\.html")(?=[^>]*data-i18n="site\.comparePreviewPage\.nextStepsBuildersCta")[^>]*>',
        html,
    )
    assert 'data-i18n="site.comparePreviewPage.footerQuickStartLink"' in html
    assert 'data-i18n="site.comparePreviewPage.footerProofLink"' in html
    assert 'data-i18n="site.comparePreviewPage.footerBuildersLink"' in html
    next_steps = re.search(
        r'<section class="section">\s*<div class="section-head">\s*<h2 data-i18n="site\.comparePreviewPage\.nextStepsTitle">.*?</h2>\s*<p data-i18n="site\.comparePreviewPage\.nextStepsSummary">.*?</p>\s*</div>\s*<div class="card-grid">(.*?)</div>\s*</section>',
        html,
        re.S,
    )
    assert next_steps, "compare preview next-step section missing"
    block = next_steps.group(1)
    proof_pos = block.index('data-i18n="site.comparePreviewPage.nextStepsProofTitle"')
    quick_start_pos = block.index('data-i18n="site.comparePreviewPage.nextStepsQuickStartTitle"')
    builders_pos = block.index('data-i18n="site.comparePreviewPage.nextStepsBuildersTitle"')
    assert proof_pos < quick_start_pos < builders_pos



def test_compare_preview_page_shared_catalog_keys_exist() -> None:
    html = COMPARE_PREVIEW_PAGE.read_text(encoding="utf-8")
    catalogs = _load_catalogs()
    keys = set(
        re.findall(
            r'data-i18n(?:-(?:key|aria-label))?="(site\.comparePreviewPage\.[^"]+|site\.common\.[^"]+|site\.compareSurface\.[^"]+)"',
            html,
        )
    )

    for locale, catalog in catalogs.items():
        missing = sorted(key for key in keys if not _has_key(catalog, key))
        assert not missing, f"{locale} missing compare preview page keys: {missing}"


def test_builder_route_order_matches_machine_reader_contract() -> None:
    builders_html = BUILDERS_PAGE.read_text(encoding="utf-8")
    llms = LLMS_TXT.read_text(encoding="utf-8")
    route_block_match = re.search(
        r'<p class="small-note" data-i18n="site\.buildersPage\.jumpSummary">.*?</p>\s*<div class="micro-links">(.*?)</div>',
        builders_html,
        re.S,
    )
    assert route_block_match, "builders route block missing"
    builders_route = route_block_match.group(1)
    builders_route_start = route_block_match.start(1)

    builders_catalog = builders_route_start + builders_route.index("./data/builder-client-catalog.json")
    builders_starters = builders_route_start + builders_route.index("./data/builder-client-starters.json")
    builders_pack = builders_route_start + builders_route.index("./data/builder-starter-pack.json")
    builders_bundle = builders_route_start + builders_route.index("./data/builder-client-configs.json")
    builders_contract = builders_route_start + builders_route.index("dealwatch-api-mcp-substrate-phase1.md")
    builders_runtime_title = builders_html.index('data-i18n="site.buildersPage.launchContractTitle"')
    assert builders_catalog < builders_starters < builders_pack < builders_bundle < builders_contract < builders_runtime_title

    llms_compare = llms.index("Compare Preview:")
    llms_quick_start = llms.index("Quick Start:")
    llms_builders = llms.index("Builders:")
    assert llms_compare < llms_quick_start < llms_builders

    llms_catalog = llms.index("Static builder client catalog:")
    llms_starters = llms.index("Static client starters mirror:")
    llms_pack = llms.index("Static builder starter pack mirror:")
    llms_bundle = llms.index("Static all-clients config mirror:")
    llms_contract = llms.index("API / MCP substrate contract:")
    llms_runtime = llms.index("Local runtime tool inventory:")
    llms_compare_action = llms.index("Product-safe first action after wiring:")
    assert llms_catalog < llms_starters < llms_pack < llms_bundle < llms_contract < llms_runtime < llms_compare_action


def test_public_pages_json_ld_is_bound_to_shared_catalogs() -> None:
    index_html = INDEX_PAGE.read_text(encoding="utf-8")
    builders_html = BUILDERS_PAGE.read_text(encoding="utf-8")
    faq_html = FAQ_PAGE.read_text(encoding="utf-8")
    compare_preview_html = COMPARE_PREVIEW_PAGE.read_text(encoding="utf-8")
    comparison_html = COMPARISON_PAGE.read_text(encoding="utf-8")
    proof_html = PROOF_PAGE.read_text(encoding="utf-8")
    quick_start_html = QUICK_START_PAGE.read_text(encoding="utf-8")
    community_html = COMMUNITY_PAGE.read_text(encoding="utf-8")
    use_cases_html = USE_CASES_PAGE.read_text(encoding="utf-8")
    catalogs = _load_catalogs()

    assert 'data-i18n-json="site.index.schema"' in index_html
    assert 'data-i18n-json="site.buildersPage.schema"' in builders_html
    assert 'data-i18n-json="site.faqPage.schema"' in faq_html
    assert 'data-i18n-json="site.comparePreviewPage.schema"' in compare_preview_html
    assert 'data-i18n-json="site.comparisonPage.schema"' in comparison_html
    assert 'data-i18n-json="site.proofPage.schema"' in proof_html
    assert 'data-i18n-json="site.quickStartPage.schema"' in quick_start_html
    assert 'data-i18n-json="site.communityPage.schema"' in community_html
    assert 'data-i18n-json="site.useCasesPage.schema"' in use_cases_html
    assert 'data-i18n-json="site.notFoundPage.schema"' in NOT_FOUND_PAGE.read_text(encoding="utf-8")

    for locale, catalog in catalogs.items():
        assert _has_key(catalog, "site.index.schema"), f"{locale} missing site.index.schema"
        assert _has_key(catalog, "site.buildersPage.schema"), f"{locale} missing site.buildersPage.schema"
        assert _has_key(catalog, "site.faqPage.schema"), f"{locale} missing site.faqPage.schema"
        assert _has_key(catalog, "site.comparePreviewPage.schema"), f"{locale} missing site.comparePreviewPage.schema"
        assert _has_key(catalog, "site.comparisonPage.schema"), f"{locale} missing site.comparisonPage.schema"
        assert _has_key(catalog, "site.proofPage.schema"), f"{locale} missing site.proofPage.schema"
        assert _has_key(catalog, "site.quickStartPage.schema"), f"{locale} missing site.quickStartPage.schema"
        assert _has_key(catalog, "site.communityPage.schema"), f"{locale} missing site.communityPage.schema"
        assert _has_key(catalog, "site.useCasesPage.schema"), f"{locale} missing site.useCasesPage.schema"
        assert _has_key(catalog, "site.notFoundPage.schema"), f"{locale} missing site.notFoundPage.schema"


def test_public_pages_default_english_metadata_and_schema_match_catalog() -> None:
    catalogs = _load_catalogs()
    en_catalog = catalogs["en"]["site"]
    pages = [
        (INDEX_PAGE, "index"),
        (BUILDERS_PAGE, "buildersPage"),
        (FAQ_PAGE, "faqPage"),
        (COMPARE_PREVIEW_PAGE, "comparePreviewPage"),
        (COMPARISON_PAGE, "comparisonPage"),
        (PROOF_PAGE, "proofPage"),
        (QUICK_START_PAGE, "quickStartPage"),
        (COMMUNITY_PAGE, "communityPage"),
        (USE_CASES_PAGE, "useCasesPage"),
    ]

    for path, key in pages:
        html = path.read_text(encoding="utf-8")
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.S)
        desc_match = re.search(r'<meta\s+name="description"\s+content="([^"]+)"', html)
        og_desc_match = re.search(r'<meta\s+property="og:description"\s+content="([^"]+)"', html)
        twitter_desc_match = re.search(r'<meta\s+name="twitter:description"\s+content="([^"]+)"', html)
        schema_match = re.search(r'<script type="application/ld\+json"[^>]*data-i18n-json="site\.[^"]+\.schema"[^>]*>(.*?)</script>', html, re.S)

        assert title_match, f"{path.name} missing title"
        assert desc_match, f"{path.name} missing description meta"
        assert og_desc_match, f"{path.name} missing og:description"
        assert twitter_desc_match, f"{path.name} missing twitter:description"
        assert schema_match, f"{path.name} missing JSON-LD content"

        assert title_match.group(1).strip() == en_catalog[key]["title"]
        assert desc_match.group(1).strip() == en_catalog[key]["description"]
        assert og_desc_match.group(1).strip() == en_catalog[key]["description"]
        assert twitter_desc_match.group(1).strip() == en_catalog[key]["description"]
        assert json.loads(schema_match.group(1)) == _get_value(catalogs["en"], f"site.{key}.schema")


def test_not_found_page_default_english_metadata_matches_catalog() -> None:
    catalogs = _load_catalogs()
    en_catalog = catalogs["en"]["site"]["notFoundPage"]
    html = NOT_FOUND_PAGE.read_text(encoding="utf-8")
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.S)
    desc_match = re.search(r'<meta\s+name="description"\s+content="([^"]+)"', html)
    og_title_match = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', html)
    og_desc_match = re.search(r'<meta\s+property="og:description"\s+content="([^"]+)"', html)
    twitter_title_match = re.search(r'<meta\s+name="twitter:title"\s+content="([^"]+)"', html)
    twitter_desc_match = re.search(r'<meta\s+name="twitter:description"\s+content="([^"]+)"', html)
    schema_match = re.search(
        r'<script type="application/ld\+json"[^>]*data-i18n-json="site\.notFoundPage\.schema"[^>]*>(.*?)</script>',
        html,
        re.S,
    )

    assert title_match, "404.html missing title"
    assert desc_match, "404.html missing description meta"
    assert og_title_match, "404.html missing og:title"
    assert og_desc_match, "404.html missing og:description"
    assert twitter_title_match, "404.html missing twitter:title"
    assert twitter_desc_match, "404.html missing twitter:description"
    assert schema_match, "404.html missing JSON-LD content"
    assert title_match.group(1).strip() == en_catalog["title"]
    assert desc_match.group(1).strip() == en_catalog["description"]
    assert og_title_match.group(1).strip() == en_catalog["title"]
    assert og_desc_match.group(1).strip() == en_catalog["description"]
    assert twitter_title_match.group(1).strip() == en_catalog["title"]
    assert twitter_desc_match.group(1).strip() == en_catalog["description"]
    assert json.loads(schema_match.group(1)) == _get_value(catalogs["en"], "site.notFoundPage.schema")
