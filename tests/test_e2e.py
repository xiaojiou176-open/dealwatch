import contextlib
import functools
import http.server
import json
import socketserver
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
import shutil
import tempfile

import pytest

from playwright.async_api import Error as PlaywrightError

from dealwatch.core.ai_analyzer import AIAnalyzer
from dealwatch.core.artifacts import ArtifactManager
from dealwatch.core.models import Offer, PriceContext
from dealwatch.core.pipeline import MonitoringPipeline
from dealwatch.infra.config import Settings
from dealwatch.legacy.db_repo import DatabaseRepository
from dealwatch.infra.mailer import EmailNotifier
from dealwatch.infra.obs.health_check import HealthMonitor
from dealwatch.stores.base_adapter import BaseStoreAdapter
from dealwatch.infra.playwright_client import PlaywrightClient


class _E2EAdapter(BaseStoreAdapter):
    store_id = "e2e"
    base_url = "https://example.com"

    def __init__(self, offer: Offer, settings: Settings) -> None:
        super().__init__(client=object(), settings=settings)
        self._offer = offer

    async def discover_deals(self) -> list[str]:
        return ["https://example.com/p1"]

    async def parse_product(self, url: str) -> Offer | None:
        return self._offer


class _PlaywrightAdapter(BaseStoreAdapter):
    store_id = "e2e_pw"
    base_url = "http://localhost"

    def __init__(
        self,
        client: PlaywrightClient,
        settings: Settings,
        urls: list[str],
    ) -> None:
        super().__init__(client=client, settings=settings)
        self._urls = urls

    async def discover_deals(self) -> list[str]:
        return list(self._urls)

    async def parse_product(self, url: str) -> Offer | None:
        page = await self.client.fetch_page(url, return_page=True)
        try:
            title_node = await page.query_selector("h1")
            price_node = await page.query_selector(".price_current")
            original_node = await page.query_selector(".price_original")

            title = (await title_node.text_content()) if title_node else ""
            price_text = (await price_node.text_content()) if price_node else ""
            original_text = (await original_node.text_content()) if original_node else ""

            title = (title or "").strip()
            price_text = (price_text or "").strip()
            if not title or not price_text:
                await self._capture_failed_page(page, url, "missing_fields")
                return None

            price = float(price_text.replace("$", "").strip())
            original = None
            if (original_text or "").strip():
                original = float(original_text.replace("$", "").strip())

            return Offer(
                store_id=self.store_id,
                product_key="local-1",
                title=title,
                url=url,
                price=price,
                original_price=original,
                fetch_at=datetime.now(timezone.utc),
                context=PriceContext(region="00000"),
                unit_price_info={"raw": "500g"},
            )
        finally:
            await page.close()


def _start_http_server(directory: Path) -> tuple[socketserver.TCPServer, str]:
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler,
        directory=str(directory),
    )
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, f"http://127.0.0.1:{port}"


@functools.lru_cache(maxsize=None)
def _site_catalog(locale: str) -> dict[str, object]:
    root = Path(__file__).resolve().parents[1]
    catalog_path = root / "site" / "data" / "i18n" / f"{locale}.json"
    return json.loads(catalog_path.read_text(encoding="utf-8"))


def _site_text(locale: str, key: str) -> str:
    value: object = _site_catalog(locale)
    for segment in key.split("."):
        if not isinstance(value, dict):
            raise KeyError(key)
        value = value[segment]
    if not isinstance(value, str):
        raise TypeError(f"{key} did not resolve to a string")
    return value


@pytest.mark.asyncio
async def test_e2e_pipeline_artifacts_ai(tmp_path) -> None:
    db_path = tmp_path / "dealwatch.db"
    settings = Settings(
        DB_PATH=db_path,
        USE_LLM=False,
        SMTP_HOST="",
    )

    repo = DatabaseRepository(db_path)
    await repo.initialize()

    context = PriceContext(region="00000")
    old_offer = Offer(
        store_id="e2e",
        product_key="p1",
        title="E2E Product",
        url="https://example.com/p1",
        price=10.00,
        original_price=None,
        fetch_at=datetime.now(timezone.utc) - timedelta(days=1),
        context=context,
        unit_price_info={},
    )
    await repo.insert_price_point(old_offer)

    new_offer = Offer(
        store_id="e2e",
        product_key="p1",
        title="E2E Product",
        url="https://example.com/p1",
        price=8.00,
        original_price=10.00,
        fetch_at=datetime.now(timezone.utc),
        context=context,
        unit_price_info={},
    )

    adapter = _E2EAdapter(new_offer, settings)
    pipeline = MonitoringPipeline(repo=repo, client=object(), settings=settings)
    deals = await pipeline.run_store(adapter)
    assert len(deals) == 1

    artifacts = ArtifactManager(base_dir=tmp_path)
    json_path = artifacts.save_deals(deals, "e2e", total_checked=1)
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["confirmed_count"] == 1

    analyzer = AIAnalyzer(settings)
    html = await analyzer.analyze(json_path)
    assert "<table>" in html

    notifier = EmailNotifier(settings)
    health = HealthMonitor(repo, notifier)
    await health.record_run(pipeline.last_stats)
    issues = await health.evaluate(pipeline.last_stats)
    assert issues == []


@pytest.mark.asyncio
async def test_e2e_playwright_local_site(tmp_path, monkeypatch) -> None:
    site_dir = tmp_path / "site"
    site_dir.mkdir(parents=True, exist_ok=True)

    (site_dir / "product.html").write_text(
        (
            "<html><body>"
            "<h1>Local Noodles 500g</h1>"
            "<div class=\"price_current\">$2.50</div>"
            "<div class=\"price_original\">$3.00</div>"
            "</body></html>"
        ),
        encoding="utf-8",
    )
    (site_dir / "bad.html").write_text(
        "<html><body><h1>Missing Price</h1></body></html>",
        encoding="utf-8",
    )

    server, base_url = _start_http_server(site_dir)
    try:
        db_path = tmp_path / "dealwatch.db"
        settings = Settings(
            DB_PATH=db_path,
            USE_LLM=False,
            SMTP_HOST="",
        )

        repo = DatabaseRepository(db_path)
        await repo.initialize()

        context = PriceContext(region="00000")
        old_offer = Offer(
            store_id="e2e_pw",
            product_key="local-1",
            title="Local Noodles 500g",
            url=f"{base_url}/product.html",
            price=3.50,
            original_price=None,
            fetch_at=datetime.now(timezone.utc) - timedelta(days=1),
            context=context,
            unit_price_info={"raw": "500g"},
        )
        await repo.insert_price_point(old_offer)

        run_dir = tmp_path / ".runtime-cache" / "runs" / "2026-02-03"
        def _fake_run_dir(self) -> Path:
            run_dir.mkdir(parents=True, exist_ok=True)
            return run_dir

        monkeypatch.setattr(ArtifactManager, "get_run_dir", _fake_run_dir)

        async with PlaywrightClient(
            headless=True,
            storage_state_path=tmp_path / "state.json",
        ) as client:
            adapter = _PlaywrightAdapter(
                client=client,
                settings=settings,
                urls=[
                    f"{base_url}/product.html",
                    f"{base_url}/bad.html",
                ],
            )
            pipeline = MonitoringPipeline(repo=repo, client=client, settings=settings)
            deals = await pipeline.run_store(adapter)
            assert len(deals) == 1

        index_path = run_dir / "failures_index.ndjson"
        assert index_path.exists() is True
    except PlaywrightError as exc:
        pytest.skip(f"Playwright unavailable: {exc}")
    finally:
        with contextlib.suppress(Exception):
            server.shutdown()
        with contextlib.suppress(Exception):
            server.server_close()
            server.server_close()


def test_public_comparison_page_switches_locale_and_keeps_assets() -> None:
    from playwright.sync_api import sync_playwright

    root = Path(__file__).resolve().parents[1]
    site_root = root / "site"

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        shutil.copytree(site_root, temp_path, dirs_exist_ok=True)
        server, base_url = _start_http_server(temp_path)
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page(viewport={"width": 1440, "height": 1400})
                page.goto(f"{base_url}/compare-vs-tracker.html", wait_until="networkidle")

                expect_title = "Why DealWatch is not just another generic price tracker"
                expect_builder = "Why builders and AI tool users care"
                expect_description = _site_text("en", "site.comparisonPage.description")
                assert expect_title in page.locator("h1").inner_text()
                assert expect_builder in page.locator("h2").nth(1).inner_text()
                assert page.locator("meta[name='description']").get_attribute("content") == expect_description
                schema = json.loads(page.locator("script[type='application/ld+json']").first.text_content() or "{}")
                assert schema["name"] == _site_text("en", "site.comparisonPage.schema.name")
                assert schema["keywords"] == _site_catalog("en")["site"]["comparisonPage"]["schema"]["keywords"]

                page.locator('[data-locale-option="zh-CN"]').click()
                page.wait_for_function("() => document.documentElement.lang === 'zh-CN'")

                assert _site_text("zh-CN", "site.comparisonPage.heroTitle") in page.locator("h1").inner_text()
                assert _site_text("zh-CN", "site.comparisonPage.builderTitle") in page.locator("h2").nth(1).inner_text()
                assert page.locator("meta[name='description']").get_attribute("content") == _site_text(
                    "zh-CN",
                    "site.comparisonPage.description",
                )
                zh_schema = json.loads(page.locator("script[type='application/ld+json']").first.text_content() or "{}")
                assert zh_schema["name"] == _site_text("zh-CN", "site.comparisonPage.schema.name")
                assert zh_schema["keywords"] == _site_catalog("zh-CN")["site"]["comparisonPage"]["schema"]["keywords"]

                image_state = page.evaluate(
                    """
                    () => Array.from(document.images).map((img) => ({
                      complete: img.complete,
                      width: img.naturalWidth,
                      height: img.naturalHeight,
                    }))
                    """
                )
                assert image_state
                assert all(item["complete"] and item["width"] > 0 and item["height"] > 0 for item in image_state)
                browser.close()
        except PlaywrightError as exc:
            pytest.skip(f"Playwright unavailable: {exc}")
        finally:
            with contextlib.suppress(Exception):
                server.shutdown()
            with contextlib.suppress(Exception):
                server.server_close()


def test_public_index_page_primary_cta_routes_to_compare_preview() -> None:
    from playwright.sync_api import sync_playwright

    root = Path(__file__).resolve().parents[1]
    site_root = root / "site"

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        shutil.copytree(site_root, temp_path, dirs_exist_ok=True)
        server, base_url = _start_http_server(temp_path)
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page(viewport={"width": 1440, "height": 1400})
                page.goto(f"{base_url}/index.html", wait_until="networkidle")

                assert "Compare the aisle before you commit to one cart." in page.locator("h1").inner_text()
                page.get_by_role("link", name="Open the sample compare").first.click()
                page.wait_for_url(f"{base_url}/compare-preview.html#sample-compare-demo")

                assert "Check the product target before you create durable state." in page.locator("h1").inner_text()
                assert page.locator("#sample-compare-demo").is_visible()
                browser.close()
        except PlaywrightError as exc:
            pytest.skip(f"Playwright unavailable: {exc}")
        finally:
            with contextlib.suppress(Exception):
                server.shutdown()
            with contextlib.suppress(Exception):
                server.server_close()


def test_public_builders_page_catalog_cta_routes_to_json_surface() -> None:
    from playwright.sync_api import sync_playwright

    root = Path(__file__).resolve().parents[1]
    site_root = root / "site"

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        shutil.copytree(site_root, temp_path, dirs_exist_ok=True)
        server, base_url = _start_http_server(temp_path)
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page(viewport={"width": 1440, "height": 1400})
                page.goto(f"{base_url}/builders.html", wait_until="networkidle")

                assert "Start with the human path, then let the machine path mirror it." in page.locator("h1").inner_text()
                page.get_by_role("link", name="Open the client catalog").first.click()
                page.wait_for_url(f"{base_url}/data/builder-client-catalog.json")

                body = page.locator("body").inner_text().lower()
                assert "codex" in body
                assert "openhands" in body
                browser.close()
        except PlaywrightError as exc:
            pytest.skip(f"Playwright unavailable: {exc}")
        finally:
            with contextlib.suppress(Exception):
                server.shutdown()
            with contextlib.suppress(Exception):
                server.server_close()


def test_webui_compare_locale_validation_follows_locale_switch() -> None:
    from playwright.sync_api import sync_playwright

    root = Path(__file__).resolve().parents[1]
    frontend_dist = root / "frontend" / "dist"
    if not frontend_dist.exists():
        pytest.skip("frontend/dist missing; run `pnpm -C frontend build` before this E2E check")

    server, base_url = _start_http_server(frontend_dist)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = browser.new_context(locale="en-US", viewport={"width": 1440, "height": 1200})
            page = context.new_page()
            page.goto(f"{base_url}/#compare", wait_until="networkidle")

            page.get_by_role("button", name="English").click()
            page.get_by_role("textbox", name="Product URLs").fill(
                "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869"
            )
            page.get_by_role("button", name="Compare URLs").click()

            assert page.get_by_text("Enter at least two product URLs.").is_visible()

            page.locator('[data-locale-option="zh-CN"]').click()
            page.wait_for_function("() => document.documentElement.lang === 'zh-CN'")

            assert page.get_by_text(_site_text("zh-CN", "compare.form.errors.minUrls")).is_visible()

            context.close()
            browser.close()
    except PlaywrightError as exc:
        pytest.skip(f"Playwright unavailable: {exc}")
    finally:
        with contextlib.suppress(Exception):
            server.shutdown()
        with contextlib.suppress(Exception):
            server.server_close()


def test_public_proof_page_schema_switches_locale() -> None:
    from playwright.sync_api import sync_playwright

    root = Path(__file__).resolve().parents[1]
    site_root = root / "site"

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        shutil.copytree(site_root, temp_path, dirs_exist_ok=True)
        server, base_url = _start_http_server(temp_path)
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page(viewport={"width": 1440, "height": 1400})
                page.goto(f"{base_url}/proof.html", wait_until="networkidle")

                assert "Public claims, AI guidance, and evidence in one place" in page.locator("h1").inner_text()
                schema = json.loads(page.locator("script[type='application/ld+json']").first.text_content() or "{}")
                assert schema["headline"] == "DealWatch Proof | AI Explanation, Recovery Guidance, and Read-Only MCP Evidence"
                assert "Codex" in schema["keywords"]

                page.locator('[data-locale-option="zh-CN"]').click()
                page.wait_for_function("() => document.documentElement.lang === 'zh-CN'")

                assert _site_text("zh-CN", "site.proofPage.heroTitle") in page.locator("h1").inner_text()
                zh_schema = json.loads(page.locator("script[type='application/ld+json']").first.text_content() or "{}")
                assert zh_schema["headline"] == _site_text("zh-CN", "site.proofPage.schema.headline")
                assert "Claude Code" in zh_schema["keywords"]
                browser.close()
        except PlaywrightError as exc:
            pytest.skip(f"Playwright unavailable: {exc}")
        finally:
            with contextlib.suppress(Exception):
                server.shutdown()
            with contextlib.suppress(Exception):
                server.server_close()


def test_public_compare_preview_page_schema_switches_locale() -> None:
    from playwright.sync_api import sync_playwright

    root = Path(__file__).resolve().parents[1]
    site_root = root / "site"

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        shutil.copytree(site_root, temp_path, dirs_exist_ok=True)
        server, base_url = _start_http_server(temp_path)
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page(viewport={"width": 1440, "height": 1400})
                page.goto(f"{base_url}/compare-preview.html", wait_until="networkidle")

                assert "Check the product target before you create durable state." in page.locator("h1").inner_text()
                schema = json.loads(page.locator("script[type='application/ld+json']").first.text_content() or "{}")
                assert schema["name"] == _site_text("en", "site.comparePreviewPage.schema.name")
                assert schema["keywords"] == _site_catalog("en")["site"]["comparePreviewPage"]["schema"]["keywords"]

                page.locator('[data-locale-option="zh-CN"]').click()
                page.wait_for_function("() => document.documentElement.lang === 'zh-CN'")

                assert _site_text("zh-CN", "site.comparePreviewPage.heroTitle") in page.locator("h1").inner_text()
                zh_schema = json.loads(page.locator("script[type='application/ld+json']").first.text_content() or "{}")
                assert zh_schema["name"] == _site_text("zh-CN", "site.comparePreviewPage.schema.name")
                assert zh_schema["keywords"] == _site_catalog("zh-CN")["site"]["comparePreviewPage"]["schema"]["keywords"]
                browser.close()
        except PlaywrightError as exc:
            pytest.skip(f"Playwright unavailable: {exc}")
        finally:
            with contextlib.suppress(Exception):
                server.shutdown()
            with contextlib.suppress(Exception):
                server.server_close()


def test_public_proof_page_schema_switches_locale() -> None:
    from playwright.sync_api import sync_playwright

    root = Path(__file__).resolve().parents[1]
    site_root = root / "site"

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        shutil.copytree(site_root, temp_path, dirs_exist_ok=True)
        server, base_url = _start_http_server(temp_path)
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page(viewport={"width": 1440, "height": 1400})
                page.goto(f"{base_url}/proof.html", wait_until="networkidle")

                assert "Public claims, AI guidance, and evidence in one place" in page.locator("h1").inner_text()
                schema = json.loads(page.locator("script[type='application/ld+json']").first.text_content() or "{}")
                assert schema["headline"] == "DealWatch Proof | AI Explanation, Recovery Guidance, and Read-Only MCP Evidence"
                assert "Codex" in schema["keywords"]

                page.locator('[data-locale-option="zh-CN"]').click()
                page.wait_for_function("() => document.documentElement.lang === 'zh-CN'")

                assert _site_text("zh-CN", "site.proofPage.heroTitle") in page.locator("h1").inner_text()
                zh_schema = json.loads(page.locator("script[type='application/ld+json']").first.text_content() or "{}")
                assert zh_schema["headline"] == _site_text("zh-CN", "site.proofPage.schema.headline")
                assert "Claude Code" in zh_schema["keywords"]
                browser.close()
        except PlaywrightError as exc:
            pytest.skip(f"Playwright unavailable: {exc}")
        finally:
            with contextlib.suppress(Exception):
                server.shutdown()
            with contextlib.suppress(Exception):
                server.server_close()
