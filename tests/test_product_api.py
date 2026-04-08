from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from dealwatch.application import services as services_module
from dealwatch.api import deps
from dealwatch.api.app import create_app
from dealwatch.core.models import Offer, PriceContext
from dealwatch.infra.config import settings
from dealwatch.persistence.models import StoreAdapterBinding, TaskRun, WatchGroup, WatchGroupRun, WatchTask
from dealwatch.providers.cashback.base import CashbackQuoteResult


class _ApiFakeEmailProvider:
    async def send(self, payload):
        return SimpleNamespace(
            provider="smtp",
            status="sent",
            message_id="api-msg-1",
            payload={"recipient": payload.recipient},
        )


class _ApiFakeCashbackProvider:
    def __init__(self) -> None:
        self.payloads = []

    async def fetch_quote(self, payload):
        self.payloads.append(payload)
        return CashbackQuoteResult(
            provider="cashbackmonitor",
            merchant_key=payload.merchant_key,
            rate_type="percent",
            rate_value=10.0,
            conditions_text="fake",
            source_url="https://example.com/cashback",
            confidence=0.8,
        )


@pytest.fixture(autouse=True)
def _reset_product_api_runtime(monkeypatch):
    monkeypatch.setattr(settings, "PRODUCT_AUTO_CREATE_SCHEMA", True)
    monkeypatch.setattr(settings, "POSTMARK_WEBHOOK_TOKEN", "test-webhook-token")
    monkeypatch.setattr(deps, "ensure_runtime_contract_from_settings", lambda *_args, **_kwargs: None)
    deps._SERVICE = None
    deps._RUNTIME_FACTORY = None
    yield
    deps._SERVICE = None
    deps._RUNTIME_FACTORY = None

@pytest.mark.asyncio
async def test_product_api_create_list_and_run(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'api.db'}"
    monkeypatch.setattr(settings, "DATABASE_URL", db_url)
    monkeypatch.setattr(settings, "RUNS_DIR", tmp_path / "api-runs")
    monkeypatch.setattr(settings, "OWNER_EMAIL", "owner@example.com")
    monkeypatch.setattr(settings, "ZIP_CODE", "98101")
    monkeypatch.setattr(settings, "SMTP_HOST", "")

    app = create_app()
    service = deps.get_product_service()

    requested_zip_codes: list[str] = []

    async def _fake_fetch_offer(*args, **kwargs):
        requested_zip_codes.append(kwargs["zip_code"])
        return Offer(
            store_id="weee",
            product_key="5869",
            title="Asian Honey Pears 3ct",
            url="https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
            price=4.2,
            original_price=5.5,
            fetch_at=datetime.now(timezone.utc),
            context=PriceContext(region="98004"),
            unit_price_info={"raw": "3ct"},
        )

    monkeypatch.setattr(service, "_fetch_offer", _fake_fetch_offer)
    monkeypatch.setattr(service, "cashback_provider", None)
    monkeypatch.setattr(service, "email_provider", _ApiFakeEmailProvider())

    with TestClient(app) as client:
        create_response = client.post(
            "/api/watch-tasks",
            json={
                "submitted_url": "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
                "zip_code": "98004",
                "cadence_minutes": 60,
                "threshold_type": "price_below",
                "threshold_value": 5.0,
                "cooldown_minutes": 30,
                "recipient_email": "owner@example.com",
                "compare_handoff": {
                    "title_snapshot": "Asian Honey Pears 3ct",
                    "store_key": "weee",
                    "candidate_key": "asian honey pears 3ct | golden orchard | 3 ct",
                    "brand_hint": "Golden Orchard",
                    "size_hint": "3ct",
                },
            },
        )
        assert create_response.status_code == 200
        task_id = create_response.json()["id"]
        assert isinstance(task_id, str)

        list_response = client.get("/api/watch-tasks")
        assert list_response.status_code == 200
        assert len(list_response.json()) == 1

        run_response = client.post(f"/api/watch-tasks/{task_id}:run-now")
        assert run_response.status_code == 200
        assert run_response.json()["status"] == "succeeded"

        detail_response = client.get(f"/api/watch-tasks/{task_id}")
        assert detail_response.status_code == 200
        payload = detail_response.json()
        assert payload["task"]["store_key"] == "weee"
        assert payload["task"]["title"] == "Asian Honey Pears 3ct"
        assert payload["task"]["zip_code"] == "98004"
        assert payload["compare_context"]["candidate_key"] == "asian honey pears 3ct | golden orchard | 3 ct"
        assert payload["compare_context"]["merchant_key"] == "weee"
        assert payload["compare_context"]["brand_hint"] == "golden orchard"
        assert payload["compare_context"]["size_hint"] == "3 ct"
        assert payload["observations"][0]["listed_price"] == 4.2
        artifact_run_dir = payload["runs"][0]["artifact_run_dir"]
        assert artifact_run_dir
        artifact_dir = Path(artifact_run_dir)
        assert artifact_dir.is_dir()
        summary_path = artifact_dir / "task_run_summary.json"
        assert summary_path.is_file()
        evidence = payload["runs"][0]["artifact_evidence"]
        assert evidence["summary_exists"] is True
        assert evidence["summary_path"] == str(summary_path)
        assert evidence["delivery_count"] == 1
        assert evidence["latest_delivery_status"] == payload["delivery_events"][0]["status"]
        assert evidence["source_url"] == "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        assert summary["run"]["status"] == "succeeded"
        assert summary["task"]["zip_code"] == "98004"
        assert summary["delivery_events"][0]["recipient"] == "owner@example.com"
        assert requested_zip_codes == ["98004"]

        settings_response = client.get("/api/settings/notifications")
        assert settings_response.status_code == 200
        assert settings_response.json()["default_recipient_email"] == "owner@example.com"

        patch_settings = client.patch(
            "/api/settings/notifications",
            json={
                "default_recipient_email": "alerts@example.com",
                "cooldown_minutes": 45,
                "notifications_enabled": False,
            },
        )
        assert patch_settings.status_code == 200
        assert patch_settings.json()["default_recipient_email"] == "alerts@example.com"
        assert patch_settings.json()["notifications_enabled"] is False


@pytest.mark.asyncio
async def test_product_api_create_and_run_safeway_watch_task(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'api-safeway.db'}"
    monkeypatch.setattr(settings, "DATABASE_URL", db_url)
    monkeypatch.setattr(settings, "RUNS_DIR", tmp_path / "api-safeway-runs")
    monkeypatch.setattr(settings, "OWNER_EMAIL", "owner@example.com")
    monkeypatch.setattr(settings, "ZIP_CODE", "98004")
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    monkeypatch.setattr(settings, "ENABLED_STORES", ["safeway"])

    app = create_app()
    service = deps.get_product_service()

    requested_zip_codes: list[str] = []
    requested_product_urls: list[str] = []
    noisy_safeway_url = "https://www.safeway.com/SHOP/PRODUCT-DETAILS.960127167.HTML?storeId=3132#details"

    async def _fake_fetch_offer(*args, **kwargs):
        requested_product_urls.append(args[0])
        requested_zip_codes.append(kwargs["zip_code"])
        return Offer(
            store_id="safeway",
            product_key="0000001234567",
            title="Fairlife Milk Ultra-Filtered Reduced Fat 2% - 52 Fl. Oz.",
            url="https://www.safeway.com/shop/product-details.960127167.html",
            price=6.99,
            original_price=None,
            fetch_at=datetime.now(timezone.utc),
            context=PriceContext(region="98004"),
            unit_price_info={"raw": "52 fl oz", "brand": "fairlife"},
        )

    monkeypatch.setattr(service, "_fetch_offer", _fake_fetch_offer)
    monkeypatch.setattr(service, "cashback_provider", None)
    monkeypatch.setattr(service, "email_provider", _ApiFakeEmailProvider())

    with TestClient(app) as client:
        create_response = client.post(
            "/api/watch-tasks",
            json={
                "submitted_url": noisy_safeway_url,
                "zip_code": "98004",
                "cadence_minutes": 60,
                "threshold_type": "price_below",
                "threshold_value": 7.0,
                "cooldown_minutes": 30,
                "recipient_email": "owner@example.com",
                "compare_handoff": {
                    "title_snapshot": "Fairlife Milk Ultra-Filtered Reduced Fat 2% - 52 Fl. Oz.",
                    "store_key": "safeway",
                    "candidate_key": "fairlife milk ultra filtered reduced fat 2 52 fl oz | fairlife | 52 fl oz",
                    "brand_hint": "fairlife",
                    "size_hint": "52 fl oz",
                },
            },
        )
        assert create_response.status_code == 200
        task_id = create_response.json()["id"]

        run_response = client.post(f"/api/watch-tasks/{task_id}:run-now")
        assert run_response.status_code == 200
        assert run_response.json()["status"] == "succeeded"

        detail_response = client.get(f"/api/watch-tasks/{task_id}")
        assert detail_response.status_code == 200
        payload = detail_response.json()
        assert payload["task"]["store_key"] == "safeway"
        assert payload["task"]["submitted_url"] == noisy_safeway_url
        assert payload["task"]["title"] == "Fairlife Milk Ultra-Filtered Reduced Fat 2% - 52 Fl. Oz."
        assert payload["compare_context"]["candidate_key"] == "fairlife milk ultra filtered reduced fat 2 52 fl oz | fairlife | 52 fl oz"
        assert payload["compare_context"]["merchant_key"] == "safeway"
        assert payload["compare_context"]["brand_hint"] == "fairlife"
        assert payload["compare_context"]["size_hint"] == "52 fl oz"
        assert payload["observations"][0]["listed_price"] == 6.99
        summary_path = Path(payload["runs"][0]["artifact_run_dir"]) / "task_run_summary.json"
        assert summary_path.is_file()
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        assert summary["run"]["status"] == "succeeded"
        assert summary["task"]["zip_code"] == "98004"
        assert requested_product_urls == ["https://www.safeway.com/shop/product-details.960127167.html"]
        assert requested_zip_codes == ["98004"]


@pytest.mark.asyncio
async def test_product_api_create_and_run_safeway_watch_group(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'api-safeway-group.db'}"
    monkeypatch.setattr(settings, "DATABASE_URL", db_url)
    monkeypatch.setattr(settings, "RUNS_DIR", tmp_path / "api-safeway-group-runs")
    monkeypatch.setattr(settings, "OWNER_EMAIL", "owner@example.com")
    monkeypatch.setattr(settings, "ZIP_CODE", "98004")
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    monkeypatch.setattr(settings, "ENABLED_STORES", ["safeway"])

    app = create_app()
    service = deps.get_product_service()
    cashback = _ApiFakeCashbackProvider()

    async def _fake_fetch_offer(product_url: str, store_key: str, *, zip_code: str):
        if product_url.endswith("960127167.html"):
            return Offer(
                store_id="safeway",
                product_key="0000001234567",
                title="Fairlife Milk Ultra-Filtered Reduced Fat 2% - 52 Fl. Oz.",
                url=product_url,
                price=6.99,
                original_price=None,
                fetch_at=datetime.now(timezone.utc),
                context=PriceContext(region=zip_code),
                unit_price_info={"raw": "52 fl oz", "brand": "fairlife"},
            )
        return Offer(
            store_id="safeway",
            product_key="0000007654321",
            title="Lucerne Eggs Cage Free Large - 12 Count",
            url=product_url,
            price=5.49,
            original_price=None,
            fetch_at=datetime.now(timezone.utc),
            context=PriceContext(region=zip_code),
            unit_price_info={"raw": "12 count", "brand": "Lucerne"},
        )

    monkeypatch.setattr(service, "_fetch_offer", _fake_fetch_offer)
    monkeypatch.setattr(service, "cashback_provider", cashback)
    monkeypatch.setattr(service, "email_provider", _ApiFakeEmailProvider())

    with TestClient(app) as client:
        create_response = client.post(
            "/api/watch-groups",
            json={
                "title": "Safeway Milk Group",
                "zip_code": "98004",
                "cadence_minutes": 60,
                "threshold_type": "effective_price_below",
                "threshold_value": 7.5,
                "cooldown_minutes": 30,
                "recipient_email": "owner@example.com",
                "notifications_enabled": True,
                "candidates": [
                    {
                        "submitted_url": "https://www.safeway.com/shop/product-details.960127167.html",
                        "title_snapshot": "Fairlife Milk Ultra-Filtered Reduced Fat 2% - 52 Fl. Oz.",
                        "store_key": "safeway",
                        "candidate_key": "fairlife milk ultra filtered reduced fat 2 52 fl oz | fairlife | 52 fl oz",
                    },
                    {
                        "submitted_url": "https://www.safeway.com/shop/product-details.149030568.html",
                        "title_snapshot": "Lucerne Eggs Cage Free Large - 12 Count",
                        "store_key": "safeway",
                        "candidate_key": "lucerne eggs cage free large 12 count | lucerne | 12 count",
                    },
                ],
            },
        )
        assert create_response.status_code == 200
        group_id = create_response.json()["id"]

        run_response = client.post(f"/api/watch-groups/{group_id}:run-now")
        assert run_response.status_code == 200
        assert run_response.json()["status"] == "succeeded"

        detail_response = client.get(f"/api/watch-groups/{group_id}")
        assert detail_response.status_code == 200
        payload = detail_response.json()
        assert payload["group"]["member_count"] == 2
        assert payload["decision_explain"]["winner"]["store_key"] == "safeway"
        assert payload["decision_explain"]["reason"]["code"] == "lowest_effective_price_with_cashback"
        assert payload["decision_explain"]["winner"]["cashback_amount"] == pytest.approx(0.55, rel=1e-6)

    assert cashback.payloads
    assert {payload.merchant_key for payload in cashback.payloads} == {"safeway"}


def test_product_api_rejects_unsupported_url(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'unsupported.db'}"
    monkeypatch.setattr(settings, "DATABASE_URL", db_url)
    monkeypatch.setattr(settings, "OWNER_EMAIL", "owner@example.com")
    app = create_app()
    with TestClient(app) as client:
        response = client.post(
            "/api/watch-tasks",
            json={
                "submitted_url": "https://example.com/not-supported",
                "zip_code": "98004",
                "cadence_minutes": 60,
                "threshold_type": "price_below",
                "threshold_value": 10.0,
                "cooldown_minutes": 10,
                "recipient_email": "owner@example.com",
            },
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "unsupported_store_host"


def test_product_api_compare_preview_returns_limited_support_guidance(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'limited-support.db'}"
    monkeypatch.setattr(settings, "DATABASE_URL", db_url)
    monkeypatch.setattr(settings, "OWNER_EMAIL", "owner@example.com")
    monkeypatch.setattr(settings, "ZIP_CODE", "98004")
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    app = create_app()

    with TestClient(app) as client:
        response = client.post(
            "/api/compare/preview",
            json={
                "submitted_urls": [
                    "https://example.com/not-supported",
                    "https://www.target.com/c/grocery/-/N-5xt1a",
                ],
                "zip_code": "98004",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    host_row = next(item for item in payload["comparisons"] if item.get("error_code") == "unsupported_store_host")
    path_row = next(item for item in payload["comparisons"] if item.get("error_code") == "unsupported_store_path")
    assert host_row["support_contract"]["store_support_tier"] == "limited_unofficial"
    assert host_row["support_contract"]["can_create_watch_task"] is False
    assert path_row["store_key"] == "target"
    assert path_row["support_contract"]["store_support_tier"] == "official_full"
    assert path_row["support_contract"]["intake_status"] == "unsupported_store_path"
    assert path_row["support_contract"]["can_save_compare_evidence"] is True


def test_product_api_sets_request_id_header(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'request-id.db'}"
    monkeypatch.setattr(settings, "DATABASE_URL", db_url)
    monkeypatch.setattr(settings, "OWNER_EMAIL", "owner@example.com")
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/api/health", headers={"X-Request-ID": "req-123"})
        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == "req-123"


def test_product_api_runtime_readiness_and_attention(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'runtime-api.db'}"
    smoke_dir = tmp_path / "smoke"
    smoke_dir.mkdir(parents=True, exist_ok=True)
    (smoke_dir / "api-smoke.log").write_text("api ok\n", encoding="utf-8")
    monkeypatch.setattr(services_module.ProductService, "_get_smoke_artifact_dir", lambda self: smoke_dir)
    monkeypatch.setattr(settings, "DATABASE_URL", db_url)
    monkeypatch.setattr(settings, "OWNER_EMAIL", "owner@example.com")
    monkeypatch.setattr(settings, "OWNER_BOOTSTRAP_TOKEN", "smoke-token")
    monkeypatch.setattr(settings, "APP_BASE_URL", "http://127.0.0.1:8000")
    monkeypatch.setattr(settings, "WEBUI_DEV_URL", "http://localhost:5173")
    monkeypatch.setattr(settings, "ZIP_CODE", "98004")
    monkeypatch.setattr(settings, "ENABLED_STORES", ["weee", "ranch99"])
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    app = create_app()

    with TestClient(app) as client:
        readiness = client.get("/api/runtime/readiness")
        assert readiness.status_code == 200
        readiness_payload = readiness.json()
        assert readiness_payload["database"]["status"] == "warning"
        assert readiness_payload["store_bindings"]["metadata"]["enabled_bound_store_keys"] == ["ranch99", "weee"]
        assert readiness_payload["owner_existence"]["status"] == "warning"
        assert readiness_payload["smoke_evidence"]["status"] == "warning"

        create_task = client.post(
            "/api/watch-tasks",
            json={
                "submitted_url": "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
                "zip_code": "98004",
                "cadence_minutes": 60,
                "threshold_type": "price_below",
                "threshold_value": 4.5,
                "cooldown_minutes": 30,
                "recipient_email": "owner@example.com",
            },
        )
        assert create_task.status_code == 200
        task_id = create_task.json()["id"]

        create_group = client.post(
            "/api/watch-groups",
            json={
                "title": "Pear Group",
                "zip_code": "98004",
                "cadence_minutes": 60,
                "threshold_type": "effective_price_below",
                "threshold_value": 4.5,
                "cooldown_minutes": 30,
                "recipient_email": "owner@example.com",
                "notifications_enabled": True,
                "candidates": [
                    {
                        "submitted_url": "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
                        "title_snapshot": "Asian Honey Pears 3ct",
                        "store_key": "weee",
                        "candidate_key": "asian honey pears 3ct | 3 ct",
                    },
                    {
                        "submitted_url": "https://www.99ranch.com/product-details/1615424/8899/078895126389",
                        "title_snapshot": "Asian Honey Pears 3 ct",
                        "store_key": "ranch99",
                        "candidate_key": "asian honey pears 3 ct | 3 ct",
                    },
                ],
            },
        )
        assert create_group.status_code == 200
        group_id = create_group.json()["id"]

        service = deps.get_product_service()
        import asyncio

        async def _apply_states() -> None:
            async with service.session_factory() as session:
                task = await session.get(WatchTask, task_id)
                group = await session.get(WatchGroup, group_id)
                assert task is not None
                assert group is not None
                task.health_status = "blocked"
                task.manual_intervention_required = True
                task.status = "error"
                task.consecutive_failures = 1
                task.last_failure_kind = "blocked"
                task.last_error_code = "store_disabled"
                task.last_error_message = "store_disabled"
                group.health_status = "needs_attention"
                group.manual_intervention_required = True
                group.status = "error"
                group.consecutive_failures = 3
                group.last_failure_kind = "fetch_failed"
                group.last_error_code = "watch_group_no_successful_candidates"
                group.last_error_message = "watch_group_no_successful_candidates"
                await session.commit()

        asyncio.run(_apply_states())

        attention = client.get("/api/runtime/attention")
        assert attention.status_code == 200
        attention_payload = attention.json()
        assert attention_payload["total_items"] == 2
        assert attention_payload["task_items"][0]["kind"] == "task"
        assert attention_payload["group_items"][0]["kind"] == "group"
        assert "re-enable the store runtime switch" in attention_payload["task_items"][0]["recommended_action"]
        assert "successful candidate" in attention_payload["group_items"][0]["reason"]


def test_product_api_store_onboarding_cockpit_endpoint(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'store-cockpit-api.db'}"
    monkeypatch.setattr(settings, "DATABASE_URL", db_url)
    monkeypatch.setattr(settings, "OWNER_EMAIL", "owner@example.com")
    monkeypatch.setattr(settings, "OWNER_BOOTSTRAP_TOKEN", "real-bootstrap-token")
    monkeypatch.setattr(settings, "ZIP_CODE", "98004")
    monkeypatch.setattr(settings, "ENABLED_STORES", ["weee", "target"])
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    app = create_app()

    with TestClient(app) as client:
        response = client.get("/api/settings/store-onboarding-cockpit")

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["supported_store_count"] == 5
    assert payload["summary"]["official_full_count"] == 5
    assert payload["summary"]["official_partial_count"] == 0
    assert payload["summary"]["official_in_progress_count"] == 0
    assert payload["summary"]["default_enabled_store_count"] == 4
    assert payload["summary"]["enabled_store_count"] == 2
    assert payload["summary"]["disabled_store_count"] == 3
    assert payload["summary"]["compare_intake_supported_count"] == 5
    assert payload["summary"]["cashback_supported_count"] == 5
    assert payload["summary"]["watch_task_supported_count"] == 5
    assert payload["summary"]["watch_group_supported_count"] == 5
    assert payload["summary"]["recovery_supported_count"] == 5
    assert payload["consistency"]["registry_matches_capability_registry"] is True
    assert len(payload["capability_matrix"]) == 5
    assert payload["capability_matrix"][0]["store_key"] == "ranch99"
    assert "ENABLED_STORES" in payload["capability_matrix"][0]["support_summary"]
    assert (
        payload["capability_matrix"][0]["next_onboarding_step"]
        == "The store is runtime-ready; update the active ENABLED_STORES allowlist if you want this environment to turn it on."
    )
    safeway = next(item for item in payload["capability_matrix"] if item["store_key"] == "safeway")
    assert safeway["support_channel"] == "official"
    assert safeway["support_tier"] == "official_full"
    assert safeway["default_enabled"] is True
    assert "enabled by default when ENABLED_STORES is unset" in safeway["runtime_binding_summary"]
    assert safeway["support_reason_codes"] == []
    assert safeway["missing_capabilities"] == []
    assert "tests/test_safeway_adapter.py" in safeway["contract_test_paths"]
    assert "tests/test_product_service.py" in safeway["contract_test_paths"]
    assert "tests/test_product_api.py" in safeway["contract_test_paths"]
    walmart = next(item for item in payload["capability_matrix"] if item["store_key"] == "walmart")
    assert walmart["support_channel"] == "official"
    assert walmart["support_tier"] == "official_full"
    assert walmart["default_enabled"] is False
    assert "disabled by default" in walmart["runtime_binding_summary"]
    assert walmart["support_reason_codes"] == []
    assert walmart["next_step_codes"] == []
    assert walmart["missing_capabilities"] == []
    assert "tests/test_walmart_adapter.py" in walmart["contract_test_paths"]
    assert "docs/roadmaps/dealwatch-next-store-decision-packet.md" in walmart["source_of_truth_files"]
    assert payload["onboarding_contract"]["source_runbook_path"] == "docs/runbooks/store-onboarding-contract.md"
    assert payload["capability_matrix"][1]["support_tier"] == "official_full"
    assert payload["onboarding_contract"]["runtime_binding_truth"] != []
    assert payload["onboarding_contract"]["limited_support_contract"] != []
    assert payload["limited_support_lane"]["support_tier"] == "limited_guidance_only"
    assert "docs/runbooks/store-onboarding-contract.md" in payload["limited_support_lane"]["source_of_truth_files"]
    assert "tests/test_product_providers.py" in payload["limited_support_lane"]["source_of_truth_files"]
    assert "./scripts/smoke_product_hermetic.sh" in payload["onboarding_contract"]["verification_commands"]


def test_product_api_persists_notification_settings_without_tasks(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'settings-only.db'}"
    monkeypatch.setattr(settings, "DATABASE_URL", db_url)
    monkeypatch.setattr(settings, "OWNER_EMAIL", "owner@example.com")
    app = create_app()

    with TestClient(app) as client:
        patch_response = client.patch(
            "/api/settings/notifications",
            json={
                "default_recipient_email": "alerts@example.com",
                "cooldown_minutes": 45,
                "notifications_enabled": False,
            },
        )
        assert patch_response.status_code == 200
        assert patch_response.json() == {
            "default_recipient_email": "alerts@example.com",
            "cooldown_minutes": 45,
            "notifications_enabled": False,
        }

        get_response = client.get("/api/settings/notifications")
        assert get_response.status_code == 200
        assert get_response.json() == {
            "default_recipient_email": "alerts@example.com",
            "cooldown_minutes": 45,
            "notifications_enabled": False,
        }


def test_product_api_compare_preview(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'compare-api.db'}"
    monkeypatch.setattr(settings, "DATABASE_URL", db_url)
    monkeypatch.setattr(settings, "OWNER_EMAIL", "owner@example.com")
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    monkeypatch.setattr(settings, "ENABLED_STORES", ["weee", "ranch99", "target"])
    app = create_app()
    service = deps.get_product_service()

    async def _fake_fetch_offer(product_url: str, store_key: str, *, zip_code: str):
        if store_key == "weee":
            return Offer(
                store_id="weee",
                product_key="5869",
                title="Asian Honey Pears 3ct",
                url=product_url,
                price=4.2,
                original_price=5.5,
                fetch_at=datetime.now(timezone.utc),
                context=PriceContext(region=zip_code),
                unit_price_info={"raw": "3ct", "brand": "Golden Orchard"},
            )
        if store_key == "ranch99":
            return Offer(
                store_id="ranch99",
                product_key="078895126389",
                title="Asian Honey Pears 3 ct",
                url=product_url,
                price=4.49,
                original_price=5.29,
                fetch_at=datetime.now(timezone.utc),
                context=PriceContext(region=zip_code),
                unit_price_info={"raw": "3 ct", "brand": "Golden Orchard"},
            )
        return Offer(
            store_id="target",
            product_key="13202943",
            title="Asian Honey Pears 3ct",
            url=product_url,
            price=4.39,
            original_price=4.99,
            fetch_at=datetime.now(timezone.utc),
            context=PriceContext(region=zip_code),
            unit_price_info={"raw": "3 ct", "brand": "Golden Orchard"},
        )

    monkeypatch.setattr(service, "_fetch_offer", _fake_fetch_offer)
    monkeypatch.setattr(service, "cashback_provider", None)
    monkeypatch.setattr(service, "email_provider", _ApiFakeEmailProvider())

    with TestClient(app) as client:
        response = client.post(
            "/api/compare/preview",
            json={
                "submitted_urls": [
                    "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
                    "https://www.99ranch.com/product-details/1615424/8899/078895126389",
                    "https://www.target.com/p/utz-ripples-original-potato-chips-7-75oz/-/A-13202943",
                ],
                "zip_code": "98004",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["submitted_count"] == 3
        assert payload["resolved_count"] == 3
        assert payload["matches"][0]["score"] > 80
        assert payload["matches"][0]["why_like"]
        assert payload["matches"][0]["left_candidate_key"]
        assert payload["recommendation"]["contract_version"] == "compare_preview_public_v1"
        assert payload["recommendation"]["verdict"] == "wait"
        assert payload["recommendation"]["buy_now_blocked"] is True
        assert payload["recommended_next_step_hint"]["action"] == "create_watch_group"
        assert payload["compare_evidence"]["recommended_next_step_hint"] == payload["recommended_next_step_hint"]
        assert payload["ai_explain"]["status"] == "disabled"
        assert "shadow_recommendation" not in payload
        assert "recommendation_shadow" not in payload


def test_product_api_compare_evidence_artifact_routes(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'compare-evidence-api.db'}"
    monkeypatch.setattr(settings, "DATABASE_URL", db_url)
    monkeypatch.setattr(settings, "RUNS_DIR", tmp_path / "compare-evidence-runs")
    monkeypatch.setattr(settings, "OWNER_EMAIL", "owner@example.com")
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    monkeypatch.setattr(settings, "ENABLED_STORES", ["weee", "ranch99"])
    app = create_app()
    service = deps.get_product_service()

    async def _fake_fetch_offer(product_url: str, store_key: str, *, zip_code: str):
        if store_key == "weee":
            return Offer(
                store_id="weee",
                product_key="5869",
                title="Asian Honey Pears 3ct",
                url=product_url,
                price=4.2,
                original_price=5.5,
                fetch_at=datetime.now(timezone.utc),
                context=PriceContext(region=zip_code),
                unit_price_info={"raw": "3ct", "brand": "Golden Orchard"},
            )
        return Offer(
            store_id="ranch99",
            product_key="078895126389",
            title="Asian Honey Pears 3 ct",
            url=product_url,
            price=4.49,
            original_price=5.29,
            fetch_at=datetime.now(timezone.utc),
            context=PriceContext(region=zip_code),
            unit_price_info={"raw": "3 ct", "brand": "Golden Orchard"},
        )

    monkeypatch.setattr(service, "_fetch_offer", _fake_fetch_offer)
    cashback = _ApiFakeCashbackProvider()
    monkeypatch.setattr(service, "cashback_provider", cashback)
    monkeypatch.setattr(service, "email_provider", _ApiFakeEmailProvider())

    with TestClient(app) as client:
        create_response = client.post(
            "/api/compare/evidence",
            json={
                "submitted_urls": [
                    "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
                    "https://www.99ranch.com/product-details/1615424/8899/078895126389",
                ],
                "zip_code": "98004",
            },
        )
        assert create_response.status_code == 200
        created = create_response.json()
        assert created["artifact_kind"] == "compare_evidence"
        assert created["storage_scope"] == "runtime_local_artifact"
        assert created["recommendation"]["contract_version"] == "compare_preview_public_v1"
        assert created["recommendation"]["verdict"] == "wait"
        assert created["recommended_next_step_hint"]["action"] == "create_watch_group"
        assert "shadow_recommendation" not in created
        assert "recommendation_shadow" not in created
        shadow_path = Path(created["artifact_path"]).with_name("recommendation_shadow.json")
        assert shadow_path.is_file()

        list_response = client.get("/api/compare/evidence")
        assert list_response.status_code == 200
        listed = list_response.json()
        assert listed[0]["artifact_id"] == created["artifact_id"]
        assert listed[0]["strongest_match_score"] > 80
        assert listed[0]["recommendation"]["verdict"] == "wait"
        assert "shadow_recommendation" not in listed[0]
        assert "recommendation_shadow" not in listed[0]

        detail_response = client.get(f"/api/compare/evidence/{created['artifact_id']}")
        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert detail["artifact_id"] == created["artifact_id"]
        assert detail["submitted_inputs"] == created["submitted_inputs"]
        assert detail["matches"][0]["score"] > 80
        assert detail["recommendation"]["verdict"] == "wait"
        assert Path(detail["artifact_path"]).is_file()
        assert "shadow_recommendation" not in detail
        assert "recommendation_shadow" not in detail


def test_product_api_compare_evidence_package_route_ignores_client_compare_result(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'compare-evidence-package-api.db'}"
    monkeypatch.setattr(settings, "DATABASE_URL", db_url)
    monkeypatch.setattr(settings, "RUNS_DIR", tmp_path / "compare-evidence-runs")
    monkeypatch.setattr(settings, "OWNER_EMAIL", "owner@example.com")
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    monkeypatch.setattr(settings, "ENABLED_STORES", ["weee", "ranch99"])
    app = create_app()
    service = deps.get_product_service()

    async def _fake_fetch_offer(product_url: str, store_key: str, *, zip_code: str):
        if store_key == "weee":
            return Offer(
                store_id="weee",
                product_key="5869",
                title="Asian Honey Pears 3ct",
                url=product_url,
                price=4.2,
                original_price=5.5,
                fetch_at=datetime.now(timezone.utc),
                context=PriceContext(region=zip_code),
                unit_price_info={"raw": "3ct", "brand": "Golden Orchard"},
            )
        return Offer(
            store_id="ranch99",
            product_key="078895126389",
            title="Asian Honey Pears 3 ct",
            url=product_url,
            price=4.49,
            original_price=5.29,
            fetch_at=datetime.now(timezone.utc),
            context=PriceContext(region=zip_code),
            unit_price_info={"raw": "3 ct", "brand": "Golden Orchard"},
        )

    monkeypatch.setattr(service, "_fetch_offer", _fake_fetch_offer)
    cashback = _ApiFakeCashbackProvider()
    monkeypatch.setattr(service, "cashback_provider", cashback)
    monkeypatch.setattr(service, "email_provider", _ApiFakeEmailProvider())

    with TestClient(app) as client:
        response = client.post(
            "/api/compare/evidence-packages",
            json={
                "submitted_urls": [
                    "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
                    "https://www.99ranch.com/product-details/1615424/8899/078895126389",
                ],
                "zip_code": "98004",
                "compare_result": {
                    "submitted_count": 2,
                    "resolved_count": 0,
                    "comparisons": [],
                    "matches": [],
                    "compare_evidence": {
                        "submitted_inputs": [],
                        "zip_code": "98004",
                        "submitted_count": 2,
                        "resolved_count": 0,
                        "comparisons": [],
                        "matches": [],
                        "recommended_next_step_hint": {
                            "action": "retry_compare",
                            "reason_code": "forged_compare_result",
                            "summary": "forged",
                        },
                        "risk_notes": [],
                        "risk_note_items": [],
                        "successful_candidate_count": 0,
                        "strongest_match_score": 0.0,
                    },
                },
            },
        )

        assert response.status_code == 200
        created = response.json()
        shadow_payload = json.loads(
            Path(created["artifact_path"]).with_name("recommendation_shadow.json").read_text(encoding="utf-8")
        )

        assert created["recommended_next_step_hint"]["action"] == "create_watch_group"
        assert created["recommended_next_step_hint"]["reason_code"] == "multi_candidate_strong_match"
        assert created["recommendation"]["verdict"] == "wait"
        assert "shadow_recommendation" not in created
        assert shadow_payload["shadow_recommendation"]["verdict"] == "wait"
        assert shadow_payload["shadow_recommendation"]["abstention"]["active"] is False


def test_product_api_sanitizes_non_slug_runtime_detail(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'compare-runtime-detail.db'}"
    monkeypatch.setattr(settings, "DATABASE_URL", db_url)
    monkeypatch.setattr(settings, "OWNER_EMAIL", "owner@example.com")
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    app = create_app()
    service = deps.get_product_service()

    async def _boom(*args, **kwargs):
        raise ValueError("human readable sentence should not leak")

    monkeypatch.setattr(service, "compare_product_urls", _boom)

    with TestClient(app) as client:
        response = client.post(
            "/api/compare/preview",
            json={
                "submitted_urls": [
                    "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
                    "https://www.99ranch.com/product-details/1615424/8899/078895126389",
                ],
                "zip_code": "98004",
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "compare_preview_failed"


def test_product_api_create_and_run_watch_group_and_webhook(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'group-api.db'}"
    monkeypatch.setattr(settings, "DATABASE_URL", db_url)
    monkeypatch.setattr(settings, "RUNS_DIR", tmp_path / "group-runs")
    monkeypatch.setattr(settings, "OWNER_EMAIL", "owner@example.com")
    monkeypatch.setattr(settings, "ZIP_CODE", "98004")
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    monkeypatch.setattr(settings, "ENABLED_STORES", ["weee", "ranch99"])
    app = create_app()
    service = deps.get_product_service()

    async def _fake_fetch_offer(product_url: str, store_key: str, *, zip_code: str):
        if store_key == "weee":
            return Offer(
                store_id="weee",
                product_key="5869",
                title="Asian Honey Pears 3ct",
                url=product_url,
                price=4.2,
                original_price=5.5,
                fetch_at=datetime.now(timezone.utc),
                context=PriceContext(region=zip_code),
                unit_price_info={"raw": "3ct"},
            )
        return Offer(
            store_id="ranch99",
            product_key="078895126389",
            title="Asian Honey Pears 3 ct",
            url=product_url,
            price=4.49,
            original_price=5.29,
            fetch_at=datetime.now(timezone.utc),
            context=PriceContext(region=zip_code),
            unit_price_info={"raw": "3 ct"},
        )

    monkeypatch.setattr(service, "_fetch_offer", _fake_fetch_offer)
    monkeypatch.setattr(service, "cashback_provider", None)
    monkeypatch.setattr(service, "email_provider", _ApiFakeEmailProvider())

    with TestClient(app) as client:
        create_response = client.post(
            "/api/watch-groups",
            json={
                "title": "Pear Group",
                "zip_code": "98004",
                "cadence_minutes": 60,
                "threshold_type": "effective_price_below",
                "threshold_value": 4.5,
                "cooldown_minutes": 30,
                "recipient_email": "owner@example.com",
                "notifications_enabled": True,
                "candidates": [
                    {
                        "submitted_url": "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
                        "title_snapshot": "Asian Honey Pears 3ct",
                        "store_key": "weee",
                        "candidate_key": "asian honey pears 3ct | 3 ct",
                    },
                    {
                        "submitted_url": "https://www.99ranch.com/product-details/1615424/8899/078895126389",
                        "title_snapshot": "Asian Honey Pears 3 ct",
                        "store_key": "ranch99",
                        "candidate_key": "asian honey pears 3 ct | 3 ct",
                    },
                ],
            },
        )
        assert create_response.status_code == 200
        group_id = create_response.json()["id"]

        run_response = client.post(f"/api/watch-groups/{group_id}:run-now")
        assert run_response.status_code == 200
        assert run_response.json()["status"] == "succeeded"

        detail_response = client.get(f"/api/watch-groups/{group_id}")
        assert detail_response.status_code == 200
        payload = detail_response.json()
        assert payload["group"]["title"] == "Pear Group"
        assert payload["group"]["member_count"] == 2
        assert payload["group"]["current_winner_effective_price"] == 4.2
        assert len(payload["members"]) == 2
        assert any(member["is_current_winner"] for member in payload["members"])
        assert payload["decision_explain"]["reason"]["code"] == "lowest_effective_price"
        assert payload["decision_explain"]["winner"]["member_id"] == payload["group"]["current_winner_member_id"]
        assert payload["decision_explain"]["runner_up"]["loss_reasons"][0]["field"] == "effective_price"
        assert payload["decision_explain"]["spread"]["amount"] == pytest.approx(0.29, rel=1e-6)
        assert payload["ai_decision_explain"]["status"] == "disabled"

        notifications = client.get("/api/notifications")
        assert notifications.status_code == 200
        group_delivery = next(item for item in notifications.json() if item["watch_group_id"] == group_id)
        assert group_delivery["status"] == "sent"
        assert group_delivery["watch_task_id"] is None
        assert group_delivery["watch_group_id"] == group_id
        webhook_response = client.post(
            "/api/webhooks/postmark",
            headers={"X-DealWatch-Webhook-Token": "test-webhook-token"},
            json={"RecordType": "Delivery", "MessageID": group_delivery["message_id"]},
        )
        assert webhook_response.status_code == 200

        detail_after_webhook = client.get(f"/api/watch-groups/{group_id}")
        assert detail_after_webhook.status_code == 200
        delivered = detail_after_webhook.json()["deliveries"][0]
        assert delivered["status"] == "delivered"
        assert delivered["delivered_at"] is not None


def test_product_api_task_health_controls_and_signal(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'health-api.db'}"
    monkeypatch.setattr(settings, "DATABASE_URL", db_url)
    monkeypatch.setattr(settings, "RUNS_DIR", tmp_path / "health-runs")
    monkeypatch.setattr(settings, "OWNER_EMAIL", "owner@example.com")
    monkeypatch.setattr(settings, "ZIP_CODE", "98004")
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    app = create_app()
    service = deps.get_product_service()
    prices = iter([5.5, 4.2])

    async def _fake_fetch_offer(*args, **kwargs):
        price = next(prices)
        return Offer(
            store_id="weee",
            product_key="5869",
            title="Asian Honey Pears 3ct",
            url="https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
            price=price,
            original_price=6.0,
            fetch_at=datetime.now(timezone.utc),
            context=PriceContext(region="98004"),
            unit_price_info={"raw": "3ct"},
        )

    monkeypatch.setattr(service, "_fetch_offer", _fake_fetch_offer)
    monkeypatch.setattr(service, "cashback_provider", None)
    monkeypatch.setattr(service, "email_provider", _ApiFakeEmailProvider())

    with TestClient(app) as client:
        create_response = client.post(
            "/api/watch-tasks",
            json={
                "submitted_url": "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
                "zip_code": "98004",
                "cadence_minutes": 60,
                "threshold_type": "price_below",
                "threshold_value": 4.5,
                "cooldown_minutes": 30,
                "recipient_email": "owner@example.com",
            },
        )
        assert create_response.status_code == 200
        task_id = create_response.json()["id"]

        assert client.post(f"/api/watch-tasks/{task_id}:run-now").status_code == 200
        assert client.post(f"/api/watch-tasks/{task_id}:run-now").status_code == 200

        detail = client.get(f"/api/watch-tasks/{task_id}")
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["task"]["health_status"] == "healthy"
        assert payload["latest_signal"]["previous_listed_price"] == 5.5
        assert payload["latest_signal"]["delta_amount"] == 1.3
        assert payload["latest_signal"]["is_new_low"] is True

        pause = client.patch(f"/api/watch-tasks/{task_id}", json={"status": "paused"})
        assert pause.status_code == 200
        assert client.get(f"/api/watch-tasks/{task_id}").json()["task"]["status"] == "paused"

        resume = client.patch(f"/api/watch-tasks/{task_id}", json={"status": "active"})
        assert resume.status_code == 200
        resumed = client.get(f"/api/watch-tasks/{task_id}")
        assert resumed.json()["task"]["status"] == "active"


@pytest.mark.asyncio
async def test_product_api_rejects_disabled_store_targets(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'disabled-store.db'}"
    monkeypatch.setattr(settings, "DATABASE_URL", db_url)
    monkeypatch.setattr(settings, "OWNER_EMAIL", "owner@example.com")
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    app = create_app()

    with TestClient(app) as client:
        service = deps.get_product_service()
        async with service.session_factory() as session:
            binding = await session.scalar(
                select(StoreAdapterBinding).where(StoreAdapterBinding.store_key == "weee").limit(1)
            )
            if binding is None:
                binding = StoreAdapterBinding(store_key="weee", enabled=False, adapter_class="test")
                session.add(binding)
            else:
                binding.enabled = False
            await session.commit()

        compare_response = client.post(
            "/api/compare/preview",
            json={
                "submitted_urls": [
                    "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
                    "https://www.99ranch.com/product-details/1615424/8899/078895126389",
                ],
                "zip_code": "98004",
            },
        )
        assert compare_response.status_code == 200
        compare_payload = compare_response.json()
        weee_comparison = next(item for item in compare_payload["comparisons"] if item.get("store_key") == "weee")
        assert weee_comparison["error_code"] == "store_disabled"
        assert weee_comparison["support_contract"]["intake_status"] == "store_disabled"
        assert weee_comparison["support_contract"]["can_create_watch_task"] is False

        create_response = client.post(
            "/api/watch-tasks",
            json={
                "submitted_url": "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
                "zip_code": "98004",
                "cadence_minutes": 60,
                "threshold_type": "price_below",
                "threshold_value": 4.5,
                "cooldown_minutes": 30,
                "recipient_email": "owner@example.com",
            },
        )
        assert create_response.status_code == 400
        assert create_response.json()["detail"] == "store_disabled"


@pytest.mark.asyncio
async def test_product_api_compare_preview_distinguishes_known_store_path_support(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'known-store-path.db'}"
    monkeypatch.setattr(settings, "DATABASE_URL", db_url)
    monkeypatch.setattr(settings, "OWNER_EMAIL", "owner@example.com")
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    app = create_app()

    with TestClient(app) as client:
        compare_response = client.post(
            "/api/compare/preview",
            json={
                "submitted_urls": [
                    "https://www.safeway.com/shop/deals.html",
                    "https://www.walmart.com/browse/grocery/milk/976759_1071964",
                    "https://www.target.com/p/utz-ripples-original-potato-chips-7-75oz/-/A-13202943",
                ],
                "zip_code": "98004",
            },
        )

    assert compare_response.status_code == 200
    payload = compare_response.json()
    safeway_item = next(item for item in payload["comparisons"] if item.get("store_key") == "safeway")
    assert safeway_item["supported"] is False
    assert safeway_item["support_contract"]["support_channel"] == "official"
    assert safeway_item["support_contract"]["store_support_tier"] == "official_full"
    assert safeway_item["support_contract"]["intake_status"] == "unsupported_store_path"
    assert safeway_item["support_contract"]["can_save_compare_evidence"] is True
    assert safeway_item["support_contract"]["can_create_watch_task"] is False
    walmart_item = next(item for item in payload["comparisons"] if item.get("store_key") == "walmart")
    assert walmart_item["supported"] is False
    assert walmart_item["support_contract"]["support_channel"] == "official"
    assert walmart_item["support_contract"]["store_support_tier"] == "official_full"
    assert walmart_item["support_contract"]["intake_status"] == "unsupported_store_path"
    assert walmart_item["support_contract"]["can_save_compare_evidence"] is True
    assert walmart_item["support_contract"]["can_create_watch_task"] is False


@pytest.mark.asyncio
async def test_product_api_create_and_run_walmart_watch_task(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'api-walmart.db'}"
    monkeypatch.setattr(settings, "DATABASE_URL", db_url)
    monkeypatch.setattr(settings, "RUNS_DIR", tmp_path / "api-walmart-runs")
    monkeypatch.setattr(settings, "OWNER_EMAIL", "owner@example.com")
    monkeypatch.setattr(settings, "ZIP_CODE", "98004")
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    monkeypatch.setattr(settings, "ENABLED_STORES", ["walmart"])

    app = create_app()
    service = deps.get_product_service()

    requested_zip_codes: list[str] = []
    requested_product_urls: list[str] = []
    noisy_walmart_url = "https://www.walmart.com/ip/Great-Value-Whole-Vitamin-D-Milk-1-gal/10450117?athbdg=L1600#details"

    async def _fake_fetch_offer(*args, **kwargs):
        requested_product_urls.append(args[0])
        requested_zip_codes.append(kwargs["zip_code"])
        return Offer(
            store_id="walmart",
            product_key="10450117",
            title="Great Value Whole Vitamin D Milk, 1 gal",
            url="https://www.walmart.com/ip/10450117",
            price=3.74,
            original_price=None,
            fetch_at=datetime.now(timezone.utc),
            context=PriceContext(region="98004"),
            unit_price_info={"raw": "1 gal", "brand": "Great Value"},
        )

    monkeypatch.setattr(service, "_fetch_offer", _fake_fetch_offer)
    monkeypatch.setattr(service, "cashback_provider", None)
    monkeypatch.setattr(service, "email_provider", _ApiFakeEmailProvider())

    with TestClient(app) as client:
        create_response = client.post(
            "/api/watch-tasks",
            json={
                "submitted_url": noisy_walmart_url,
                "zip_code": "98004",
                "cadence_minutes": 60,
                "threshold_type": "price_below",
                "threshold_value": 4.0,
                "cooldown_minutes": 30,
                "recipient_email": "owner@example.com",
                "compare_handoff": {
                    "title_snapshot": "Great Value Whole Vitamin D Milk, 1 gal",
                    "store_key": "walmart",
                    "candidate_key": "great value whole vitamin d milk 1 gal | great value | 1 gal",
                    "brand_hint": "Great Value",
                    "size_hint": "1 gal",
                },
            },
        )
        assert create_response.status_code == 200
        task_id = create_response.json()["id"]

        run_response = client.post(f"/api/watch-tasks/{task_id}:run-now")
        assert run_response.status_code == 200
        assert run_response.json()["status"] == "succeeded"

        detail_response = client.get(f"/api/watch-tasks/{task_id}")
        assert detail_response.status_code == 200
        payload = detail_response.json()
        assert payload["task"]["store_key"] == "walmart"
        assert payload["task"]["submitted_url"] == noisy_walmart_url
        assert payload["task"]["title"] == "Great Value Whole Vitamin D Milk, 1 gal"
        assert payload["compare_context"]["merchant_key"] == "walmart"
        assert payload["compare_context"]["brand_hint"] == "great value"
        assert payload["compare_context"]["size_hint"] == "1 gal"
        assert payload["observations"][0]["listed_price"] == 3.74

    assert requested_zip_codes == ["98004"]
    assert requested_product_urls == ["https://www.walmart.com/ip/10450117"]


@pytest.mark.asyncio
async def test_product_api_create_and_run_walmart_watch_group_with_cashback(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'api-walmart-group.db'}"
    monkeypatch.setattr(settings, "DATABASE_URL", db_url)
    monkeypatch.setattr(settings, "RUNS_DIR", tmp_path / "api-walmart-group-runs")
    monkeypatch.setattr(settings, "OWNER_EMAIL", "owner@example.com")
    monkeypatch.setattr(settings, "ZIP_CODE", "98004")
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    monkeypatch.setattr(settings, "ENABLED_STORES", ["walmart"])

    app = create_app()
    service = deps.get_product_service()

    async def _fake_fetch_offer(product_url: str, store_key: str, *, zip_code: str):
        if product_url.endswith("/10450117"):
            return Offer(
                store_id="walmart",
                product_key="10450117",
                title="Great Value Whole Vitamin D Milk, 1 gal",
                url="https://www.walmart.com/ip/10450117",
                price=3.74,
                original_price=None,
                fetch_at=datetime.now(timezone.utc),
                context=PriceContext(region=zip_code),
                unit_price_info={"raw": "1 gal", "brand": "Great Value"},
            )
        return Offer(
            store_id="walmart",
            product_key="20450117",
            title="Great Value 2% Milk, 1 gal",
            url="https://www.walmart.com/ip/20450117",
            price=4.29,
            original_price=None,
            fetch_at=datetime.now(timezone.utc),
            context=PriceContext(region=zip_code),
            unit_price_info={"raw": "1 gal", "brand": "Great Value"},
        )

    monkeypatch.setattr(service, "_fetch_offer", _fake_fetch_offer)
    cashback = _ApiFakeCashbackProvider()
    monkeypatch.setattr(service, "cashback_provider", cashback)
    monkeypatch.setattr(service, "email_provider", _ApiFakeEmailProvider())

    with TestClient(app) as client:
        create_response = client.post(
            "/api/watch-groups",
            json={
                "title": "Walmart Milk Group",
                "zip_code": "98004",
                "cadence_minutes": 60,
                "threshold_type": "price_below",
                "threshold_value": 4.5,
                "cooldown_minutes": 30,
                "recipient_email": "owner@example.com",
                "notifications_enabled": True,
                "candidates": [
                    {
                        "submitted_url": "https://www.walmart.com/ip/Great-Value-Whole-Vitamin-D-Milk-1-gal/10450117?athbdg=L1600#details",
                        "title_snapshot": "Great Value Whole Vitamin D Milk, 1 gal",
                        "store_key": "walmart",
                        "candidate_key": "great value whole vitamin d milk 1 gal | great value | 1 gal",
                    },
                    {
                        "submitted_url": "https://www.walmart.com/ip/Great-Value-2-Milk-1-gal/20450117",
                        "title_snapshot": "Great Value 2% Milk, 1 gal",
                        "store_key": "walmart",
                        "candidate_key": "great value 2 milk 1 gal | great value | 1 gal",
                    },
                ],
            },
        )
        assert create_response.status_code == 200
        group_id = create_response.json()["id"]

        run_response = client.post(f"/api/watch-groups/{group_id}:run-now")
        assert run_response.status_code == 200
        assert run_response.json()["status"] == "succeeded"

        detail_response = client.get(f"/api/watch-groups/{group_id}")
        assert detail_response.status_code == 200
        payload = detail_response.json()
        assert payload["group"]["member_count"] == 2
        assert payload["decision_explain"]["winner"]["store_key"] == "walmart"
        assert payload["decision_explain"]["winner"]["cashback_amount"] == pytest.approx(0.37, rel=1e-6)
        assert payload["decision_explain"]["reason"]["code"] == "lowest_effective_price_with_cashback"

    assert {payload.merchant_key for payload in cashback.payloads} == {"walmart"}



@pytest.mark.asyncio
async def test_product_api_create_and_run_safeway_watch_group_with_cashback(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'safeway-group-api.db'}"
    monkeypatch.setattr(settings, "DATABASE_URL", db_url)
    monkeypatch.setattr(settings, "RUNS_DIR", tmp_path / "safeway-group-runs")
    monkeypatch.setattr(settings, "OWNER_EMAIL", "owner@example.com")
    monkeypatch.setattr(settings, "ZIP_CODE", "98004")
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    monkeypatch.setattr(settings, "ENABLED_STORES", ["safeway", "target"])
    app = create_app()
    service = deps.get_product_service()

    async def _fake_fetch_offer(product_url: str, store_key: str, *, zip_code: str):
        if store_key == "safeway":
            return Offer(
                store_id="safeway",
                product_key="0000001234567",
                title="Fairlife Milk Ultra-Filtered Reduced Fat 2% - 52 Fl. Oz.",
                url=product_url,
                price=6.99,
                original_price=None,
                fetch_at=datetime.now(timezone.utc),
                context=PriceContext(region=zip_code),
                unit_price_info={"raw": "52 fl oz", "brand": "fairlife"},
            )
        return Offer(
            store_id="target",
            product_key="13202943",
            title="Fairlife Milk Ultra-Filtered Reduced Fat 2% - 52 Fl. Oz.",
            url=product_url,
            price=7.49,
            original_price=7.99,
            fetch_at=datetime.now(timezone.utc),
            context=PriceContext(region=zip_code),
            unit_price_info={"raw": "52 fl oz", "brand": "fairlife"},
        )

    monkeypatch.setattr(service, "_fetch_offer", _fake_fetch_offer)
    monkeypatch.setattr(service, "cashback_provider", _ApiFakeCashbackProvider())
    monkeypatch.setattr(service, "email_provider", _ApiFakeEmailProvider())

    with TestClient(app) as client:
        create_response = client.post(
            "/api/watch-groups",
            json={
                "title": "Safeway Fairlife Group",
                "zip_code": "98004",
                "cadence_minutes": 60,
                "threshold_type": "effective_price_below",
                "threshold_value": 7.0,
                "cooldown_minutes": 30,
                "recipient_email": "owner@example.com",
                "notifications_enabled": True,
                "candidates": [
                    {
                        "submitted_url": "https://www.safeway.com/SHOP/PRODUCT-DETAILS.960127167.HTML?storeId=3132#details",
                        "title_snapshot": "Fairlife Milk Ultra-Filtered Reduced Fat 2% - 52 Fl. Oz.",
                        "store_key": "safeway",
                        "candidate_key": "fairlife milk ultra filtered reduced fat 2 52 fl oz | fairlife | 52 fl oz",
                        "brand_hint": "fairlife",
                        "size_hint": "52 fl oz",
                        "similarity_score": 96.0,
                    },
                    {
                        "submitted_url": "https://www.target.com/p/-/A-13202943",
                        "title_snapshot": "Fairlife Milk Ultra-Filtered Reduced Fat 2% - 52 Fl. Oz.",
                        "store_key": "target",
                        "candidate_key": "fairlife milk ultra filtered reduced fat 2 52 fl oz | fairlife | 52 fl oz",
                        "brand_hint": "fairlife",
                        "size_hint": "52 fl oz",
                        "similarity_score": 94.0,
                    },
                ],
            },
        )
        assert create_response.status_code == 200
        group_id = create_response.json()["id"]

        run_response = client.post(f"/api/watch-groups/{group_id}:run-now")
        assert run_response.status_code == 200
        assert run_response.json()["status"] == "succeeded"

        detail_response = client.get(f"/api/watch-groups/{group_id}")
        assert detail_response.status_code == 200
        payload = detail_response.json()
        assert payload["group"]["current_winner_effective_price"] == pytest.approx(6.29, rel=1e-6)
        assert payload["decision_explain"]["winner"]["store_key"] == "safeway"
        safeway_member = next(item for item in payload["runs"][0]["member_results"] if item["store_key"] == "safeway")
        assert safeway_member["cashback_amount"] == pytest.approx(0.7, rel=1e-6)
        assert safeway_member["cashback_quote"]["merchant_key"] == "safeway"


def test_product_api_updates_watch_group_status(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'update-group.db'}"
    monkeypatch.setattr(settings, "DATABASE_URL", db_url)
    monkeypatch.setattr(settings, "OWNER_EMAIL", "owner@example.com")
    monkeypatch.setattr(settings, "ZIP_CODE", "98004")
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    monkeypatch.setattr(settings, "ENABLED_STORES", ["weee", "ranch99"])
    app = create_app()

    with TestClient(app) as client:
        create_response = client.post(
            "/api/watch-groups",
            json={
                "title": "Pear Group",
                "zip_code": "98004",
                "cadence_minutes": 60,
                "threshold_type": "effective_price_below",
                "threshold_value": 4.5,
                "cooldown_minutes": 30,
                "recipient_email": "owner@example.com",
                "notifications_enabled": True,
                "candidates": [
                    {
                        "submitted_url": "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
                        "title_snapshot": "Asian Honey Pears 3ct",
                        "store_key": "weee",
                        "candidate_key": "asian honey pears 3ct | 3 ct",
                    },
                    {
                        "submitted_url": "https://www.99ranch.com/product-details/1615424/8899/078895126389",
                        "title_snapshot": "Asian Honey Pears 3 ct",
                        "store_key": "ranch99",
                        "candidate_key": "asian honey pears 3 ct | 3 ct",
                    },
                ],
            },
        )
        assert create_response.status_code == 200
        group_id = create_response.json()["id"]

        pause_response = client.patch(f"/api/watch-groups/{group_id}", json={"status": "paused"})
        assert pause_response.status_code == 200
        detail = client.get(f"/api/watch-groups/{group_id}")
        assert detail.status_code == 200
        assert detail.json()["group"]["status"] == "paused"


def test_product_api_runtime_readiness_endpoint(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'readiness-api.db'}"
    smoke_dir = tmp_path / "smoke-artifacts"
    smoke_dir.mkdir()
    (smoke_dir / "api-smoke.log").write_text("API_OK\n", encoding="utf-8")
    (smoke_dir / "worker-smoke.log").write_text("WORKER_OK\n", encoding="utf-8")
    monkeypatch.setattr(settings, "DATABASE_URL", db_url)
    monkeypatch.setattr(settings, "OWNER_EMAIL", "owner@example.com")
    monkeypatch.setattr(settings, "OWNER_BOOTSTRAP_TOKEN", "real-bootstrap-token")
    monkeypatch.setattr(settings, "ZIP_CODE", "98004")
    monkeypatch.setattr(settings, "ENABLED_STORES", ["weee", "target"])
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    monkeypatch.setattr(services_module, "SMOKE_ARTIFACTS_DIR", smoke_dir)
    app = create_app()
    service = deps.get_product_service()

    with TestClient(app) as client:
        async def _seed() -> None:
            async with service.session_factory() as session:
                await service.bootstrap_owner(session)
                for store_key, adapter_class in (("weee", "WeeeAdapter"), ("target", "TargetAdapter")):
                    binding = await session.scalar(
                        select(StoreAdapterBinding).where(StoreAdapterBinding.store_key == store_key).limit(1)
                    )
                    if binding is None:
                        session.add(StoreAdapterBinding(store_key=store_key, enabled=True, adapter_class=adapter_class))
                    else:
                        binding.enabled = True
                        binding.adapter_class = adapter_class
                await session.commit()

        import asyncio

        asyncio.run(_seed())
        response = client.get("/api/settings/runtime-readiness")

    assert response.status_code == 200
    payload = response.json()
    checks = {item["key"]: item for item in payload["checks"]}
    assert checks["database"]["detail"]["database_backend"] == "sqlite+aiosqlite"
    assert checks["owner"]["status"] == "ready"
    assert checks["stores"]["status"] == "ready"
    assert checks["smoke"]["status"] == "ready"
    assert checks["notifications"]["status"] == "warning"


def test_product_api_builder_starter_pack_endpoint(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'builder-starter-pack.db'}"
    monkeypatch.setattr(settings, "DATABASE_URL", db_url)
    monkeypatch.setattr(settings, "OWNER_EMAIL", "owner@example.com")
    monkeypatch.setattr(settings, "OWNER_BOOTSTRAP_TOKEN", "real-bootstrap-token")
    monkeypatch.setattr(settings, "ZIP_CODE", "98004")
    monkeypatch.setattr(settings, "ENABLED_STORES", ["weee", "target"])
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    app = create_app()

    with TestClient(app) as client:
        response = client.get("/api/runtime/builder-starter-pack")

    assert response.status_code == 200
    payload = response.json()
    assert payload["surface_version"] == "phase1"
    assert payload["client_starters"]["openclaw"] == "docs/integrations/prompts/openclaw-starter.md"
    assert payload["launch_contract"]["cli_builder_starter_pack"].endswith("dealwatch builder-starter-pack --json")
    assert (
        payload["client_skill_cards"]["openclaw"]
        == "docs/integrations/skills/openclaw-readonly-builder-skill.md"
    )
    assert payload["client_adapter_recipes"]["codex"] == "docs/integrations/recipes/codex.md"
    assert payload["client_wrapper_status"]["claude_code"] == "official_wrapper_documented"
    assert payload["client_wrapper_status"]["codex"] == "official_wrapper_documented"
    assert payload["client_wrapper_status"]["opencode"] == "official_wrapper_documented"
    assert payload["client_wrapper_status"]["openclaw"] == "official_wrapper_documented"
    assert payload["client_wrapper_examples"]["claude_code"] == "docs/integrations/examples/claude-code.mcp.json"
    assert payload["client_wrapper_examples"]["openhands"] == "docs/integrations/examples/openhands-config.toml"
    assert payload["client_wrapper_examples"]["openclaw"] == "docs/integrations/examples/openclaw-mcp-servers.json"
    assert payload["client_wrapper_sources"]["codex"] == "https://developers.openai.com/codex/mcp/"
    assert payload["client_wrapper_surfaces"]["openhands"] == "config_toml_mcp_stdio_servers"
    assert payload["launch_contract"]["mcp_streamable_http"].endswith("dealwatch.mcp serve --transport streamable-http")
    assert payload["launch_contract"]["mcp_streamable_http_endpoint"] == "http://127.0.0.1:8000/mcp"
    assert payload["launch_contract"]["mcp_client_starters"].endswith("dealwatch.mcp client-starters --json")
    assert payload["docs"]["config_recipes"] == "docs/integrations/config-recipes.md"
    assert payload["docs"]["skills"] == "docs/integrations/skills/README.md"
    assert payload["public_builder_page"] == "site/builders.html"
    assert payload["skill_pack"]["path"] == "docs/integrations/skills/dealwatch-readonly-builder-skill.md"
    assert "get_builder_starter_pack" in payload["safe_first_loops"]["mcp"]


def test_product_api_builder_client_config_endpoint(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'builder-client-config.db'}"
    monkeypatch.setattr(settings, "DATABASE_URL", db_url)
    monkeypatch.setattr(settings, "OWNER_EMAIL", "owner@example.com")
    monkeypatch.setattr(settings, "OWNER_BOOTSTRAP_TOKEN", "real-bootstrap-token")
    monkeypatch.setattr(settings, "ZIP_CODE", "98004")
    monkeypatch.setattr(settings, "ENABLED_STORES", ["weee", "target"])
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    app = create_app()

    with TestClient(app) as client:
        response = client.get("/api/runtime/builder-client-config/codex")

    assert response.status_code == 200
    payload = response.json()
    assert payload["client"] == "codex"
    assert payload["recommended_transport"] == "streamable_http"
    assert payload["wrapper_example_path"] == "docs/integrations/examples/codex-mcp-config.toml"
    assert payload["recipe_markdown"].startswith("# DealWatch Recipe For Codex")
    assert payload["docs"]["config_recipes"] == "docs/integrations/config-recipes.md"
    assert payload["read_surfaces"]["cli"].endswith("dealwatch builder-client-config codex --json")
    assert payload["read_surfaces"]["http"] == "GET /api/runtime/builder-client-config/codex"
    assert "http://127.0.0.1:8000/mcp" in payload["wrapper_example_content"]


def test_product_api_builder_client_configs_endpoint(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'builder-client-configs.db'}"
    monkeypatch.setattr(settings, "DATABASE_URL", db_url)
    monkeypatch.setattr(settings, "OWNER_EMAIL", "owner@example.com")
    monkeypatch.setattr(settings, "OWNER_BOOTSTRAP_TOKEN", "real-bootstrap-token")
    monkeypatch.setattr(settings, "ZIP_CODE", "98004")
    monkeypatch.setattr(settings, "ENABLED_STORES", ["weee", "target"])
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    app = create_app()

    with TestClient(app) as client:
        response = client.get("/api/runtime/builder-client-configs")

    assert response.status_code == 200
    payload = response.json()
    assert payload["export_kind"] == "builder_client_configs"
    assert payload["client_count"] == 5
    assert payload["read_surfaces"]["http"] == "GET /api/runtime/builder-client-configs"
    assert payload["read_surfaces"]["mcp_tool"] == "list_builder_client_configs"
    assert any(item["client"] == "openclaw" for item in payload["clients"])


def test_product_api_recovery_inbox_endpoint(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'recovery-api.db'}"
    monkeypatch.setattr(settings, "DATABASE_URL", db_url)
    monkeypatch.setattr(settings, "OWNER_EMAIL", "owner@example.com")
    monkeypatch.setattr(settings, "OWNER_BOOTSTRAP_TOKEN", "real-bootstrap-token")
    monkeypatch.setattr(settings, "ZIP_CODE", "98004")
    monkeypatch.setattr(settings, "ENABLED_STORES", ["weee", "ranch99"])
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    monkeypatch.setattr(settings, "USE_LLM", True)
    monkeypatch.setattr(settings, "AI_PROVIDER", "fake")
    monkeypatch.setattr(settings, "AI_MODEL", "dealwatch-fake-v1")
    monkeypatch.setattr(settings, "AI_RECOVERY_COPILOT_ENABLED", True)
    app = create_app()
    service = deps.get_product_service()

    with TestClient(app) as client:
        async def _seed() -> None:
            async with service.session_factory() as session:
                task = await service.create_watch_task(
                    session,
                    submitted_url="https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
                    zip_code="98004",
                    cadence_minutes=60,
                    threshold_type="price_below",
                    threshold_value=4.5,
                    cooldown_minutes=30,
                    recipient_email="owner@example.com",
                )
                group = await service.create_watch_group(
                    session,
                    title="Pear Recovery Group",
                    zip_code="98004",
                    cadence_minutes=60,
                    threshold_type="effective_price_below",
                    threshold_value=4.5,
                    cooldown_minutes=30,
                    recipient_email="owner@example.com",
                    notifications_enabled=True,
                    candidates=[
                        {
                            "submitted_url": "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
                            "title_snapshot": "Asian Honey Pears 3ct",
                            "store_key": "weee",
                            "candidate_key": "asian honey pears 3ct | 3 ct",
                        },
                        {
                            "submitted_url": "https://www.99ranch.com/product-details/1615424/8899/078895126389",
                            "title_snapshot": "Asian Honey Pears 3 ct",
                            "store_key": "ranch99",
                            "candidate_key": "asian honey pears 3 ct | 3 ct",
                        },
                    ],
                )
                task.health_status = "needs_attention"
                task.manual_intervention_required = True
                task.backoff_until = datetime.now(timezone.utc)
                task.last_failure_kind = "blocked"
                task.last_error_code = "store_disabled"
                task.last_error_message = "store_disabled"
                group.health_status = "degraded"
                group.manual_intervention_required = False
                group.backoff_until = datetime.now(timezone.utc)
                group.last_failure_kind = "unexpected_runtime_error"
                group.last_error_code = "unexpected_runtime_error"
                group.last_error_message = "unexpected_runtime_error"
                session.add(
                    TaskRun(
                        watch_task_id=task.id,
                        triggered_by="manual",
                        status="blocked",
                        error_code="store_disabled",
                        error_message="store_disabled",
                    )
                )
                session.add(
                    WatchGroupRun(
                        watch_group_id=group.id,
                        triggered_by="manual",
                        status="failed",
                        error_code="unexpected_runtime_error",
                        error_message="unexpected_runtime_error",
                    )
                )
                await session.commit()

        import asyncio

        asyncio.run(_seed())
        response = client.get("/api/recovery/inbox")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_items"] == 2
    assert [item["kind"] for item in payload["task_items"]] == ["task"]
    assert [item["kind"] for item in payload["group_items"]] == ["group"]
    assert (
        payload["task_items"][0]["recommended_action"]
        == "Open Settings, re-enable the store runtime switch, then rerun it manually."
    )
    assert (
        payload["group_items"][0]["recommended_action"]
        == "Inspect the latest run details and artifact evidence before retrying."
    )
    assert payload["ai_copilot"]["status"] == "ok"
    assert payload["ai_copilot"]["provider"]["provider"] == "fake"
