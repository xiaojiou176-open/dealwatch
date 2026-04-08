from __future__ import annotations

from dataclasses import replace
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

from dealwatch.application import services as services_module
from dealwatch.application.services import ProductService
from dealwatch.core.models import Offer, PriceContext
from dealwatch.infra.config import Settings, settings
import dealwatch.persistence.store_bindings as store_bindings_module
from dealwatch.persistence.models import (
    CanonicalProduct,
    DeliveryEvent,
    EffectivePriceSnapshot,
    PriceObservation,
    ProductCandidate,
    StoreAdapterBinding,
    TaskRun,
    WatchGroup,
    WatchGroupRun,
    WatchTask,
)
from dealwatch.persistence.session import create_session_factory, get_session_factory, init_product_database
from dealwatch.persistence.store_bindings import sync_store_adapter_bindings
from dealwatch.providers.cashback.base import CashbackQuoteResult
from dealwatch.providers.email.base import EmailDispatchResult


class _FakeCashbackProvider:
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


class _FakeEmailProvider:
    async def send(self, payload):
        return EmailDispatchResult(
            provider="smtp",
            status="sent",
            message_id="msg-1",
            payload={"recipient": payload.recipient},
        )


class _BoomAiProvider:
    provider_name = "boom"
    model_name = "boom-model"

    async def generate(self, _request):
        raise RuntimeError("boom")

@pytest.mark.asyncio
async def test_product_service_create_and_run_watch_task(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'product.db'}"
    await init_product_database(db_url)
    session_factory = get_session_factory(db_url)
    service = ProductService(
        session_factory=session_factory,
        settings=Settings(
            DATABASE_URL=db_url,
            RUNS_DIR=tmp_path / "runs",
            OWNER_EMAIL="owner@example.com",
            SMTP_HOST="",
            ZIP_CODE="98004",
        ),
        cashback_provider=_FakeCashbackProvider(),
        email_provider=_FakeEmailProvider(),
    )

    async with session_factory() as session:
        task = await service.create_watch_task(
            session,
            submitted_url="https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
            zip_code="98004",
            cadence_minutes=60,
            threshold_type="price_below",
            threshold_value=4.5,
            cooldown_minutes=30,
            recipient_email="owner@example.com",
            compare_handoff={
                "title_snapshot": "Asian Honey Pears 3ct",
                "store_key": "weee",
                "candidate_key": "asian honey pears 3ct | golden orchard | 3 ct",
                "brand_hint": "Golden Orchard",
                "size_hint": "3ct",
            },
        )
        await session.commit()

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

    async with session_factory() as session:
        run = await service.run_watch_task(session, task.id, triggered_by="manual")
        await session.commit()
        assert run.status == "succeeded"
        assert run.artifact_run_dir is not None

    artifact_dir = Path(run.artifact_run_dir or "")
    summary_path = artifact_dir / "task_run_summary.json"
    assert artifact_dir.is_dir()
    assert summary_path.is_file()
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert payload["task"]["id"] == task.id
    assert payload["task"]["zip_code"] == "98004"
    assert payload["run"]["id"] == run.id
    assert payload["run"]["artifact_run_dir"] == str(artifact_dir)
    assert payload["delivery_events"][0]["status"] == "sent"
    assert requested_zip_codes == ["98004"]

    async with session_factory() as session:
        observation = await session.scalar(select(PriceObservation).where(PriceObservation.watch_task_id == task.id))
        assert observation is not None
        assert observation.listed_price == 4.2

        effective = await session.scalar(
            select(EffectivePriceSnapshot).where(EffectivePriceSnapshot.watch_task_id == task.id)
        )
        assert effective is not None
        assert effective.effective_price == pytest.approx(3.78, rel=1e-6)

        delivery = await session.scalar(select(DeliveryEvent).where(DeliveryEvent.watch_task_id == task.id))
        assert delivery is not None
        assert delivery.status == "sent"

        candidate = await session.scalar(select(ProductCandidate).where(ProductCandidate.watch_task_id == task.id))
        assert candidate is not None
        assert candidate.merchant_key == "weee"
        assert candidate.title_snapshot == "Asian Honey Pears 3ct"

        canonical = await session.get(CanonicalProduct, candidate.canonical_product_id)
        assert canonical is not None
        assert canonical.brand == "golden orchard"
        assert canonical.size_hint == "3 ct"

        detail = await service.get_watch_task_detail(session, task.id)
        assert detail["compare_context"] is not None
        assert detail["compare_context"]["candidate_key"] == "asian honey pears 3ct | golden orchard | 3 ct"
        assert detail["compare_context"]["merchant_key"] == "weee"
        assert detail["compare_context"]["brand_hint"] == "golden orchard"
        assert detail["compare_context"]["size_hint"] == "3 ct"


@pytest.mark.asyncio
async def test_product_service_lists_watch_tasks(tmp_path) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'product.db'}"
    await init_product_database(db_url)
    session_factory = get_session_factory(db_url)
    service = ProductService(
        session_factory=session_factory,
        settings=Settings(DATABASE_URL=db_url, OWNER_EMAIL="owner@example.com", SMTP_HOST=""),
        cashback_provider=_FakeCashbackProvider(),
        email_provider=_FakeEmailProvider(),
    )

    async with session_factory() as session:
        await service.create_watch_task(
            session,
            submitted_url="https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
            zip_code="98004",
            cadence_minutes=120,
            threshold_type="price_below",
            threshold_value=6.0,
            cooldown_minutes=15,
            recipient_email="owner@example.com",
        )
        await session.commit()

    async with session_factory() as session:
        tasks = await service.list_watch_tasks(session)
        assert len(tasks) == 1
        assert tasks[0]["store_key"] == "weee"
        assert tasks[0]["zip_code"] == "98004"
        assert tasks[0]["title"] == "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869"


@pytest.mark.asyncio
async def test_product_service_runtime_readiness(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'readiness.db'}"
    await init_product_database(db_url)
    session_factory = get_session_factory(db_url)
    smoke_dir = tmp_path / "smoke"
    smoke_dir.mkdir(parents=True, exist_ok=True)
    (smoke_dir / "api-smoke.log").write_text("api ok\n", encoding="utf-8")
    monkeypatch.setattr(services_module, "SMOKE_ARTIFACTS_DIR", smoke_dir)

    app_settings = Settings(
        DATABASE_URL=db_url,
        OWNER_EMAIL="owner@example.com",
        OWNER_BOOTSTRAP_TOKEN="smoke-token",
        APP_BASE_URL="http://127.0.0.1:8000",
        WEBUI_DEV_URL="http://localhost:5173",
        ZIP_CODE="98004",
        ENABLED_STORES=["weee"],
        SMTP_HOST="",
    )
    await sync_store_adapter_bindings(session_factory, app_settings)
    service = ProductService(
        session_factory=session_factory,
        settings=app_settings,
        cashback_provider=_FakeCashbackProvider(),
        email_provider=_FakeEmailProvider(),
    )
    monkeypatch.setattr(service, "_get_smoke_artifact_dir", lambda: smoke_dir)

    async with session_factory() as session:
        readiness = await service.get_runtime_readiness(session)

    assert readiness["status"] == "blocked"
    assert readiness["database"]["status"] == "warning"
    assert readiness["store_bindings"]["metadata"]["enabled_bound_store_keys"] == ["weee"]
    assert readiness["owner_existence"]["status"] == "warning"
    assert readiness["notification_path"]["status"] == "warning"
    assert readiness["startup_preflight"]["status"] == "blocked"
    assert readiness["smoke_evidence"]["status"] == "warning"


@pytest.mark.asyncio
async def test_product_service_process_due_tasks_and_notification_settings(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'worker.db'}"
    await init_product_database(db_url)
    session_factory = get_session_factory(db_url)
    service = ProductService(
        session_factory=session_factory,
        settings=Settings(DATABASE_URL=db_url, OWNER_EMAIL="owner@example.com", SMTP_HOST="", ZIP_CODE="98004"),
        cashback_provider=_FakeCashbackProvider(),
        email_provider=_FakeEmailProvider(),
    )

    async with session_factory() as session:
        task = await service.create_watch_task(
            session,
            submitted_url="https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
            zip_code="98004",
            cadence_minutes=30,
            threshold_type="price_below",
            threshold_value=4.5,
            cooldown_minutes=15,
            recipient_email="owner@example.com",
        )
        task.next_run_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        await session.commit()

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

    runs = await service.process_due_tasks()
    assert len(runs) == 1
    assert runs[0]["status"] == "succeeded"
    assert requested_zip_codes == ["98004"]

    async with session_factory() as session:
        settings_payload = await service.get_notification_settings(session)
        assert settings_payload["default_recipient_email"] == "owner@example.com"

        updated = await service.update_notification_settings(
            session,
            default_recipient_email="alerts@example.com",
            cooldown_minutes=99,
            notifications_enabled=False,
        )
        await session.commit()
        assert updated["default_recipient_email"] == "alerts@example.com"
        assert updated["cooldown_minutes"] == 99
        assert updated["notifications_enabled"] is False
        detail = await service.get_watch_task_detail(session, task.id)
        assert detail["task"]["cooldown_minutes"] == 99
        assert detail["task"]["zip_code"] == "98004"


@pytest.mark.asyncio
async def test_product_service_uses_adapter_cashback_merchant_key_for_ranch99(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'ranch99.db'}"
    await init_product_database(db_url)
    session_factory = get_session_factory(db_url)
    cashback = _FakeCashbackProvider()
    service = ProductService(
        session_factory=session_factory,
        settings=Settings(DATABASE_URL=db_url, OWNER_EMAIL="owner@example.com", SMTP_HOST="", ZIP_CODE="98004"),
        cashback_provider=cashback,
        email_provider=_FakeEmailProvider(),
    )

    async with session_factory() as session:
        task = await service.create_watch_task(
            session,
            submitted_url="https://www.99ranch.com/product-details/1615424/8899/078895126389",
            zip_code="98004",
            cadence_minutes=60,
            threshold_type="price_below",
            threshold_value=4.5,
            cooldown_minutes=30,
            recipient_email="owner@example.com",
        )
        await session.commit()

    async def _fake_fetch_offer(*args, **kwargs):
        return Offer(
            store_id="ranch99",
            product_key="078895126389",
            title="Lkk Premium Dark Soy Sauce",
            url="https://www.99ranch.com/product-details/1615424/8899/078895126389",
            price=4.49,
            original_price=5.29,
            fetch_at=datetime.now(timezone.utc),
            context=PriceContext(region="98004"),
            unit_price_info={"raw": "16.9000 foz/each"},
        )

    monkeypatch.setattr(service, "_fetch_offer", _fake_fetch_offer)

    async with session_factory() as session:
        run = await service.run_watch_task(session, task.id, triggered_by="manual")
        await session.commit()
        assert run.status == "succeeded"

    assert cashback.payloads
    assert cashback.payloads[0].merchant_key == "99-ranch-market"


@pytest.mark.asyncio
async def test_product_service_uses_adapter_cashback_merchant_key_for_safeway(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'safeway-cashback.db'}"
    await init_product_database(db_url)
    session_factory = get_session_factory(db_url)
    cashback = _FakeCashbackProvider()
    service = ProductService(
        session_factory=session_factory,
        settings=Settings(DATABASE_URL=db_url, OWNER_EMAIL="owner@example.com", SMTP_HOST="", ZIP_CODE="98004"),
        cashback_provider=cashback,
        email_provider=_FakeEmailProvider(),
    )

    async with session_factory() as session:
        task = await service.create_watch_task(
            session,
            submitted_url="https://www.safeway.com/shop/product-details.960127167.html",
            zip_code="98004",
            cadence_minutes=60,
            threshold_type="price_below",
            threshold_value=7.0,
            cooldown_minutes=30,
            recipient_email="owner@example.com",
        )
        await session.commit()

    async def _fake_fetch_offer(*args, **kwargs):
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

    async with session_factory() as session:
        run = await service.run_watch_task(session, task.id, triggered_by="manual")
        await session.commit()
        assert run.status == "succeeded"

    assert cashback.payloads
    assert cashback.payloads[0].merchant_key == "safeway"


@pytest.mark.asyncio
async def test_product_service_compare_product_urls(monkeypatch, tmp_path) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'compare.db'}"
    await init_product_database(db_url)
    session_factory = get_session_factory(db_url)
    service = ProductService(
        session_factory=session_factory,
        settings=Settings(DATABASE_URL=db_url, OWNER_EMAIL="owner@example.com", SMTP_HOST="", ZIP_CODE="98004"),
        cashback_provider=_FakeCashbackProvider(),
        email_provider=_FakeEmailProvider(),
    )

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
    result = await service.compare_product_urls(
        submitted_urls=[
            "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
            "https://www.99ranch.com/product-details/1615424/8899/078895126389",
            "https://www.target.com/p/utz-ripples-original-potato-chips-7-75oz/-/A-13202943",
        ],
        zip_code="98004",
    )

    assert result["submitted_count"] == 3
    assert result["resolved_count"] == 3
    assert len(result["matches"]) == 3
    assert result["matches"][0]["score"] > 80
    assert result["matches"][0]["why_like"]
    assert result["matches"][0]["brand_signal"] in {"match", "unknown"}
    assert result["matches"][0]["size_signal"] in {"match", "unknown"}
    assert result["recommended_next_step_hint"]["action"] == "create_watch_group"
    assert result["compare_evidence"]["recommended_next_step_hint"] == result["recommended_next_step_hint"]
    assert result["ai_explain"]["status"] == "disabled"
    assert result["ai_explain"]["label"] == "AI Compare Explainer"


@pytest.mark.asyncio
async def test_product_service_compare_product_urls_supports_safeway(monkeypatch, tmp_path) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'compare-safeway.db'}"
    await init_product_database(db_url)
    session_factory = get_session_factory(db_url)
    service = ProductService(
        session_factory=session_factory,
        settings=Settings(DATABASE_URL=db_url, OWNER_EMAIL="owner@example.com", SMTP_HOST="", ZIP_CODE="98004"),
        cashback_provider=_FakeCashbackProvider(),
        email_provider=_FakeEmailProvider(),
    )

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
            price=7.19,
            original_price=7.49,
            fetch_at=datetime.now(timezone.utc),
            context=PriceContext(region=zip_code),
            unit_price_info={"raw": "52 fl oz", "brand": "fairlife"},
        )

    monkeypatch.setattr(service, "_fetch_offer", _fake_fetch_offer)
    result = await service.compare_product_urls(
        submitted_urls=[
            "https://www.safeway.com/shop/product-details.960127167.html",
            "https://www.target.com/p/-/A-13202943",
        ],
        zip_code="98004",
    )

    assert result["submitted_count"] == 2
    assert result["resolved_count"] == 2
    assert {item["store_key"] for item in result["comparisons"] if item.get("fetch_succeeded")} == {"safeway", "target"}
    assert result["recommended_next_step_hint"]["action"] in {"create_watch_group", "review_compare"}
    safeway_item = next(item for item in result["comparisons"] if item.get("store_key") == "safeway")
    assert safeway_item["support_contract"]["support_channel"] == "official"
    assert safeway_item["support_contract"]["store_support_tier"] == "official_full"
    assert safeway_item["support_contract"]["intake_status"] == "supported"
    assert safeway_item["support_contract"]["can_create_watch_task"] is True
    assert safeway_item["support_contract"]["can_create_watch_group"] is True
    assert safeway_item["support_contract"]["cashback_supported"] is True


@pytest.mark.asyncio
async def test_product_service_create_and_run_safeway_watch_group_with_cashback(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'safeway-group.db'}"
    await init_product_database(db_url)
    session_factory = get_session_factory(db_url)
    cashback = _FakeCashbackProvider()
    service = ProductService(
        session_factory=session_factory,
        settings=Settings(
            DATABASE_URL=db_url,
            RUNS_DIR=tmp_path / "safeway-group-runs",
            OWNER_EMAIL="owner@example.com",
            SMTP_HOST="",
            ZIP_CODE="98004",
            ENABLED_STORES=["safeway"],
        ),
        cashback_provider=cashback,
        email_provider=_FakeEmailProvider(),
    )

    async with session_factory() as session:
        group = await service.create_watch_group(
            session,
            title="Safeway Basket",
            zip_code="98004",
            cadence_minutes=60,
            threshold_type="effective_price_below",
            threshold_value=8.0,
            cooldown_minutes=30,
            recipient_email="owner@example.com",
            notifications_enabled=True,
            candidates=[
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
        )
        await session.commit()
        group_id = group.id

    async def _fake_fetch_offer(product_url: str, store_key: str, *, zip_code: str):
        if product_url.endswith("960127167.html"):
            return Offer(
                store_id="safeway",
                product_key="960127167",
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
            product_key="149030568",
            title="Lucerne Eggs Cage Free Large - 12 Count",
            url=product_url,
            price=5.49,
            original_price=None,
            fetch_at=datetime.now(timezone.utc),
            context=PriceContext(region=zip_code),
            unit_price_info={"raw": "12 count", "brand": "Lucerne"},
        )

    monkeypatch.setattr(service, "_fetch_offer", _fake_fetch_offer)

    async with session_factory() as session:
        run = await service.run_watch_group(session, group_id, triggered_by="manual")
        await session.commit()
        assert run.status == "succeeded"

        detail = await service.get_watch_group_detail(session, group_id)
        assert detail["group"]["member_count"] == 2
        assert detail["group"]["current_winner_effective_price"] == pytest.approx(4.94, rel=1e-6)
        assert detail["decision_explain"]["reason"]["code"] == "lowest_effective_price_with_cashback"
        assert detail["decision_explain"]["winner"]["store_key"] == "safeway"
        assert detail["decision_explain"]["winner"]["cashback_amount"] == pytest.approx(0.55, rel=1e-6)

    assert [payload.merchant_key for payload in cashback.payloads] == ["safeway", "safeway"]


@pytest.mark.asyncio
async def test_product_service_compare_product_urls_prefers_single_task_for_only_resolved_safeway(
    monkeypatch, tmp_path
) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'compare-safeway-single.db'}"
    await init_product_database(db_url)
    session_factory = get_session_factory(db_url)
    service = ProductService(
        session_factory=session_factory,
        settings=Settings(DATABASE_URL=db_url, OWNER_EMAIL="owner@example.com", SMTP_HOST="", ZIP_CODE="98004"),
        cashback_provider=_FakeCashbackProvider(),
        email_provider=_FakeEmailProvider(),
    )

    async def _fake_fetch_offer(product_url: str, store_key: str, *, zip_code: str):
        assert store_key == "safeway"
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

    monkeypatch.setattr(service, "_fetch_offer", _fake_fetch_offer)
    noisy_safeway_url = "https://www.safeway.com/SHOP/PRODUCT-DETAILS.960127167.HTML?storeId=3132#details"
    result = await service.compare_product_urls(
        submitted_urls=[
            noisy_safeway_url,
            "https://example.com/not-supported",
        ],
        zip_code="98004",
    )

    assert result["submitted_count"] == 2
    assert result["resolved_count"] == 1
    assert result["recommended_next_step_hint"]["action"] == "create_watch_task"
    assert result["recommended_next_step_hint"]["reason_code"] == "single_resolved_candidate"
    assert result["compare_evidence"]["successful_candidate_count"] == 1
    assert any(item["code"] == "unsupported_inputs_present" for item in result["risk_note_items"])
    safeway_item = next(item for item in result["comparisons"] if item.get("store_key") == "safeway")
    assert safeway_item["submitted_url"] == noisy_safeway_url
    assert safeway_item["fetch_succeeded"] is True
    assert safeway_item["normalized_url"] == "https://www.safeway.com/shop/product-details.960127167.html"
    assert safeway_item["candidate_key"] == "fairlife milk ultra filtered reduced fat 2 52 fl oz | fairlife | 52 fl oz"
    unsupported_item = next(item for item in result["comparisons"] if item.get("store_key") is None)
    assert unsupported_item["support_contract"]["support_channel"] == "limited"
    assert unsupported_item["support_contract"]["store_support_tier"] == "limited_unofficial"
    assert unsupported_item["support_contract"]["intake_status"] == "unsupported_store_host"
    assert unsupported_item["support_contract"]["can_save_compare_evidence"] is True
    assert unsupported_item["support_contract"]["can_create_watch_task"] is False
    assert "official_store_registry" in unsupported_item["support_contract"]["missing_capabilities"]


@pytest.mark.asyncio
async def test_product_service_compare_product_urls_distinguishes_known_store_path_support(
    monkeypatch, tmp_path
) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'compare-known-host.db'}"
    await init_product_database(db_url)
    session_factory = get_session_factory(db_url)
    service = ProductService(
        session_factory=session_factory,
        settings=Settings(DATABASE_URL=db_url, OWNER_EMAIL="owner@example.com", SMTP_HOST="", ZIP_CODE="98004"),
        cashback_provider=_FakeCashbackProvider(),
        email_provider=_FakeEmailProvider(),
    )

    async def _fake_fetch_offer(product_url: str, store_key: str, *, zip_code: str):
        return Offer(
            store_id="target",
            product_key="13202943",
            title="Fairlife Milk Ultra-Filtered Reduced Fat 2% - 52 Fl. Oz.",
            url=product_url,
            price=7.19,
            original_price=7.49,
            fetch_at=datetime.now(timezone.utc),
            context=PriceContext(region=zip_code),
            unit_price_info={"raw": "52 fl oz", "brand": "fairlife"},
        )

    monkeypatch.setattr(service, "_fetch_offer", _fake_fetch_offer)
    result = await service.compare_product_urls(
        submitted_urls=[
            "https://www.safeway.com/shop/deals.html",
            "https://www.walmart.com/browse/grocery/milk/976759_1071964",
            "https://www.target.com/p/-/A-13202943",
        ],
        zip_code="98004",
    )

    safeway_item = next(item for item in result["comparisons"] if item.get("store_key") == "safeway")
    assert safeway_item["supported"] is False
    assert safeway_item["support_contract"]["support_channel"] == "official"
    assert safeway_item["support_contract"]["store_support_tier"] == "official_full"
    assert safeway_item["support_contract"]["intake_status"] == "unsupported_store_path"
    assert safeway_item["support_contract"]["can_create_watch_task"] is False
    assert safeway_item["support_contract"]["can_save_compare_evidence"] is True
    walmart_item = next(item for item in result["comparisons"] if item.get("store_key") == "walmart")
    assert walmart_item["supported"] is False
    assert walmart_item["support_contract"]["support_channel"] == "official"
    assert walmart_item["support_contract"]["store_support_tier"] == "official_full"
    assert walmart_item["support_contract"]["intake_status"] == "unsupported_store_path"
    assert walmart_item["support_contract"]["can_save_compare_evidence"] is True
    assert walmart_item["support_contract"]["can_create_watch_task"] is False


@pytest.mark.asyncio
async def test_product_service_resolve_or_create_watch_target_supports_safeway(tmp_path) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'safeway-target.db'}"
    await init_product_database(db_url)
    session_factory = get_session_factory(db_url)
    service = ProductService(
        session_factory=session_factory,
        settings=Settings(DATABASE_URL=db_url, OWNER_EMAIL="owner@example.com", SMTP_HOST="", ZIP_CODE="98004"),
        cashback_provider=_FakeCashbackProvider(),
        email_provider=_FakeEmailProvider(),
    )

    async with session_factory() as session:
        owner = await service.bootstrap_owner(session)
        target = await service._resolve_or_create_watch_target(
            session,
            owner.id,
            "https://www.safeway.com/shop/product-details.960127167.html",
        )
        await session.commit()

    assert target.store_key == "safeway"
    assert target.normalized_url == "https://www.safeway.com/shop/product-details.960127167.html"


@pytest.mark.asyncio
async def test_product_service_resolve_or_create_watch_target_supports_walmart(tmp_path) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'walmart-target.db'}"
    await init_product_database(db_url)
    session_factory = get_session_factory(db_url)
    service = ProductService(
        session_factory=session_factory,
        settings=Settings(DATABASE_URL=db_url, OWNER_EMAIL="owner@example.com", SMTP_HOST="", ZIP_CODE="98004"),
        cashback_provider=_FakeCashbackProvider(),
        email_provider=_FakeEmailProvider(),
    )

    noisy_url = "https://www.walmart.com/ip/Great-Value-Whole-Vitamin-D-Milk-1-gal/10450117?athbdg=L1600#details"

    async with session_factory() as session:
        owner = await service.bootstrap_owner(session)
        target = await service._resolve_or_create_watch_target(session, owner.id, noisy_url)
        await session.commit()

    assert target.store_key == "walmart"
    assert target.normalized_url == "https://www.walmart.com/ip/10450117"


@pytest.mark.asyncio
async def test_product_service_create_and_run_walmart_watch_group_with_cashback(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'walmart-group.db'}"
    await init_product_database(db_url)
    session_factory = get_session_factory(db_url)
    cashback = _FakeCashbackProvider()
    service = ProductService(
        session_factory=session_factory,
        settings=Settings(
            DATABASE_URL=db_url,
            RUNS_DIR=tmp_path / "walmart-group-runs",
            OWNER_EMAIL="owner@example.com",
            SMTP_HOST="",
            ZIP_CODE="98004",
            ENABLED_STORES=["walmart"],
        ),
        cashback_provider=cashback,
        email_provider=_FakeEmailProvider(),
    )

    async with session_factory() as session:
        group = await service.create_watch_group(
            session,
            title="Walmart Milk Group",
            zip_code="98004",
            cadence_minutes=60,
            threshold_type="price_below",
            threshold_value=4.5,
            cooldown_minutes=30,
            recipient_email="owner@example.com",
            notifications_enabled=True,
            candidates=[
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
        )
        await session.commit()
        group_id = group.id

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

    async with session_factory() as session:
        run = await service.run_watch_group(session, group_id, triggered_by="manual")
        await session.commit()
        assert run.status == "succeeded"

        detail = await service.get_watch_group_detail(session, group_id)
        assert detail["group"]["member_count"] == 2
        assert detail["decision_explain"]["winner"]["store_key"] == "walmart"
        assert detail["decision_explain"]["winner"]["cashback_amount"] == pytest.approx(0.37, rel=1e-6)
        assert detail["decision_explain"]["reason"]["code"] == "lowest_effective_price_with_cashback"
        assert detail["decision_explain"]["runner_up"]["store_key"] == "walmart"
        assert detail["deliveries"][0]["status"] == "sent"

    assert {payload.merchant_key for payload in cashback.payloads} == {"walmart"}


@pytest.mark.asyncio
async def test_product_service_recovery_inbox_includes_failed_walmart_watch_group(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'walmart-recovery.db'}"
    await init_product_database(db_url)
    session_factory = get_session_factory(db_url)
    service = ProductService(
        session_factory=session_factory,
        settings=Settings(
            DATABASE_URL=db_url,
            OWNER_EMAIL="owner@example.com",
            SMTP_HOST="",
            ZIP_CODE="98004",
            ENABLED_STORES=["walmart"],
        ),
        cashback_provider=_FakeCashbackProvider(),
        email_provider=_FakeEmailProvider(),
    )

    async with session_factory() as session:
        group = await service.create_watch_group(
            session,
            title="Walmart Recovery Group",
            zip_code="98004",
            cadence_minutes=60,
            threshold_type="effective_price_below",
            threshold_value=7.0,
            cooldown_minutes=30,
            recipient_email="owner@example.com",
            notifications_enabled=True,
            candidates=[
                {
                    "submitted_url": "https://www.walmart.com/ip/Great-Value-Whole-Vitamin-D-Milk-1-gal/10450117",
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
        )
        await session.commit()
        group_id = group.id

    async def _fetch_none(*args, **kwargs):
        return None

    monkeypatch.setattr(service, "_fetch_offer", _fetch_none)

    async with session_factory() as session:
        run = await service.run_watch_group(session, group_id, triggered_by="manual")
        await session.commit()
        assert run.status == "failed"
        assert run.error_code == "watch_group_no_successful_candidates"

    async with session_factory() as session:
        payload = await service.get_recovery_inbox(session)

    walmart_group = next(item for item in payload["group_items"] if item["title"] == "Walmart Recovery Group")
    assert walmart_group["last_error_code"] == "watch_group_no_successful_candidates"
    assert walmart_group["recommended_action"] == "Inspect member results, fix the failing candidate path, then rerun the group."


@pytest.mark.asyncio
async def test_product_service_resolve_or_create_watch_target_reuses_noisy_safeway_url(tmp_path) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'safeway-target-dedupe.db'}"
    await init_product_database(db_url)
    session_factory = get_session_factory(db_url)
    service = ProductService(
        session_factory=session_factory,
        settings=Settings(DATABASE_URL=db_url, OWNER_EMAIL="owner@example.com", SMTP_HOST="", ZIP_CODE="98004"),
        cashback_provider=_FakeCashbackProvider(),
        email_provider=_FakeEmailProvider(),
    )

    noisy_url = "https://www.safeway.com/SHOP/PRODUCT-DETAILS.960127167.HTML?storeId=3132#details"
    canonical_url = "https://www.safeway.com/shop/product-details.960127167.html"

    async with session_factory() as session:
        owner = await service.bootstrap_owner(session)
        first_target = await service._resolve_or_create_watch_target(session, owner.id, noisy_url)
        second_target = await service._resolve_or_create_watch_target(session, owner.id, canonical_url)
        await session.commit()

    assert first_target.id == second_target.id
    assert first_target.submitted_url == noisy_url
    assert second_target.normalized_url == canonical_url


@pytest.mark.asyncio
async def test_product_service_compare_ai_failure_does_not_block(monkeypatch, tmp_path) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'compare-ai-error.db'}"
    await init_product_database(db_url)
    session_factory = get_session_factory(db_url)
    service = ProductService(
        session_factory=session_factory,
        settings=Settings(
            DATABASE_URL=db_url,
            OWNER_EMAIL="owner@example.com",
            SMTP_HOST="",
            ZIP_CODE="98004",
            USE_LLM=True,
            AI_PROVIDER="fake",
            AI_MODEL="test-fake-model",
            AI_COMPARE_EXPLAIN_ENABLED=True,
        ),
        cashback_provider=_FakeCashbackProvider(),
        email_provider=_FakeEmailProvider(),
    )
    service.ai_service.provider = _BoomAiProvider()

    async def _fake_fetch_offer(product_url: str, store_key: str, *, zip_code: str):
        return Offer(
            store_id=store_key,
            product_key=f"{store_key}-1",
            title="Asian Honey Pears 3ct",
            url=product_url,
            price=4.2 if store_key == "weee" else 4.49,
            original_price=5.5,
            fetch_at=datetime.now(timezone.utc),
            context=PriceContext(region=zip_code),
            unit_price_info={"raw": "3 ct", "brand": "Golden Orchard"},
        )

    monkeypatch.setattr(service, "_fetch_offer", _fake_fetch_offer)
    result = await service.compare_product_urls(
        submitted_urls=[
            "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
            "https://www.99ranch.com/product-details/1615424/8899/078895126389",
        ],
        zip_code="98004",
    )

    assert result["resolved_count"] == 2
    assert result["recommended_next_step_hint"]["action"] == "create_watch_group"
    assert result["ai_explain"]["status"] == "error"
    assert result["ai_explain"]["provider"]["provider"] == "boom"


@pytest.mark.asyncio
async def test_product_service_create_and_read_compare_evidence_package(monkeypatch, tmp_path) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'compare-evidence.db'}"
    await init_product_database(db_url)
    runs_dir = tmp_path / "runs"
    session_factory = get_session_factory(db_url)
    service = ProductService(
        session_factory=session_factory,
        settings=Settings(DATABASE_URL=db_url, RUNS_DIR=runs_dir, OWNER_EMAIL="owner@example.com", SMTP_HOST=""),
        cashback_provider=_FakeCashbackProvider(),
        email_provider=_FakeEmailProvider(),
    )

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
    compare_result = await service.compare_product_urls(
        submitted_urls=[
            "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
            "https://www.99ranch.com/product-details/1615424/8899/078895126389",
        ],
        zip_code="98004",
    )
    created = await service.create_compare_evidence_package(
        submitted_urls=[
            "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
            "https://www.99ranch.com/product-details/1615424/8899/078895126389",
        ],
        zip_code="98004",
        compare_result=compare_result,
    )
    listed = await service.list_compare_evidence_packages()
    detail = await service.get_compare_evidence_package(created["artifact_id"])
    html_payload = await service.get_compare_evidence_package_html(created["artifact_id"])
    shadow_path = Path(created["artifact_path"]).with_name("recommendation_shadow.json")
    shadow_html_path = Path(created["html_path"]).with_name("recommendation_shadow.html")
    shadow_payload = json.loads(shadow_path.read_text(encoding="utf-8"))

    assert created["artifact_kind"] == "compare_evidence"
    assert created["recommendation"]["contract_version"] == "compare_preview_public_v1"
    assert created["recommendation"]["verdict"] == "wait"
    assert created["recommendation"]["buy_now_blocked"] is True
    assert created["recommended_next_step_hint"]["action"] == "create_watch_group"
    assert "shadow_recommendation" not in created
    assert listed["packages"][0]["artifact_id"] == created["artifact_id"]
    assert listed["packages"][0]["recommendation"]["verdict"] == "wait"
    assert "shadow_recommendation" not in listed["packages"][0]
    assert detail["summary"]["artifact_id"] == created["artifact_id"]
    assert detail["submitted_count"] == 2
    assert detail["recommendation"]["verdict"] == "wait"
    assert "shadow_recommendation" not in detail
    assert "Compare Evidence Artifact" in html_payload
    assert "Keep watching this basket" in html_payload
    assert shadow_path.is_file()
    assert shadow_html_path.is_file()
    assert shadow_payload["artifact_kind"] == "recommendation_shadow"
    assert shadow_payload["shadow_contract_version"] == "v1"
    assert shadow_payload["mode"] == "internal_only_shadow"
    assert shadow_payload["visibility"] == "internal_only"
    assert shadow_payload["surface_anchor"] == "compare_preview"
    assert shadow_payload["status"] == "issued"
    assert shadow_payload["review"]["state"] == "pending_internal_review"
    assert shadow_payload["monitoring"]["future_launch_blocked"] is True
    assert shadow_payload["monitoring"]["review_seed_suggestion"] == "correct_verdict"
    assert shadow_payload["shadow_recommendation"]["verdict"] == "wait"
    assert shadow_payload["shadow_recommendation"]["abstention"]["active"] is False
    assert shadow_payload["shadow_recommendation"]["basis"]
    assert shadow_payload["shadow_recommendation"]["uncertainty_notes"]
    assert shadow_payload["shadow_recommendation"]["evidence_refs"]
    assert shadow_payload["deterministic_truth_anchor"]["artifact_path"] == created["artifact_path"]


@pytest.mark.asyncio
async def test_product_service_compare_evidence_package_writes_abstaining_shadow_artifact(
    monkeypatch, tmp_path
) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'compare-evidence-abstain.db'}"
    await init_product_database(db_url)
    runs_dir = tmp_path / "runs"
    session_factory = get_session_factory(db_url)
    service = ProductService(
        session_factory=session_factory,
        settings=Settings(DATABASE_URL=db_url, RUNS_DIR=runs_dir, OWNER_EMAIL="owner@example.com", SMTP_HOST=""),
        cashback_provider=_FakeCashbackProvider(),
        email_provider=_FakeEmailProvider(),
    )

    async def _fake_fetch_offer(product_url: str, store_key: str, *, zip_code: str):
        assert store_key == "weee"
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

    monkeypatch.setattr(service, "_fetch_offer", _fake_fetch_offer)
    compare_result = await service.compare_product_urls(
        submitted_urls=[
            "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
            "https://example.com/not-supported",
        ],
        zip_code="98004",
    )
    created = await service.create_compare_evidence_package(
        submitted_urls=[
            "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
            "https://example.com/not-supported",
        ],
        zip_code="98004",
        compare_result=compare_result,
    )

    shadow_payload = json.loads(
        Path(created["artifact_path"]).with_name("recommendation_shadow.json").read_text(encoding="utf-8")
    )

    assert created["recommended_next_step_hint"]["reason_code"] == "single_resolved_candidate"
    assert created["recommendation"]["verdict"] == "insufficient_evidence"
    assert created["recommendation"]["abstention"]["active"] is True
    assert shadow_payload["status"] == "abstained"
    assert shadow_payload["monitoring"]["abstention_code"] == "single_resolved_candidate"
    assert shadow_payload["monitoring"]["review_seed_suggestion"] == "correct_abstention"
    assert shadow_payload["shadow_recommendation"]["verdict"] == "insufficient_evidence"
    assert shadow_payload["shadow_recommendation"]["abstention"]["active"] is True
    assert shadow_payload["shadow_recommendation"]["abstention"]["code"] == "single_resolved_candidate"
    assert any(
        item["anchor"] == "compare_evidence.recommended_next_step_hint.reason_code"
        for item in shadow_payload["shadow_recommendation"]["evidence_refs"]
    )
    assert "Cross-store compare context is still incomplete" in shadow_payload["shadow_recommendation"]["basis"][1]


@pytest.mark.asyncio
async def test_product_service_create_compare_evidence_package_ignores_caller_compare_result(
    monkeypatch, tmp_path
) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'compare-evidence-ignores-input.db'}"
    await init_product_database(db_url)
    runs_dir = tmp_path / "runs"
    session_factory = get_session_factory(db_url)
    service = ProductService(
        session_factory=session_factory,
        settings=Settings(DATABASE_URL=db_url, RUNS_DIR=runs_dir, OWNER_EMAIL="owner@example.com", SMTP_HOST=""),
        cashback_provider=_FakeCashbackProvider(),
        email_provider=_FakeEmailProvider(),
    )

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
    created = await service.create_compare_evidence_package(
        submitted_urls=[
            "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
            "https://www.99ranch.com/product-details/1615424/8899/078895126389",
        ],
        zip_code="98004",
        compare_result={
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
    )

    shadow_payload = json.loads(
        Path(created["artifact_path"]).with_name("recommendation_shadow.json").read_text(encoding="utf-8")
    )

    assert created["recommended_next_step_hint"]["action"] == "create_watch_group"
    assert created["recommended_next_step_hint"]["reason_code"] == "multi_candidate_strong_match"
    assert created["recommendation"]["verdict"] == "wait"
    assert shadow_payload["shadow_recommendation"]["verdict"] == "wait"
    assert shadow_payload["shadow_recommendation"]["abstention"]["active"] is False


@pytest.mark.asyncio
async def test_product_service_creates_internal_recommendation_shadow_monitoring_summary(
    monkeypatch, tmp_path
) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'recommendation-shadow-monitoring.db'}"
    await init_product_database(db_url)
    runs_dir = tmp_path / "runs"
    session_factory = get_session_factory(db_url)
    service = ProductService(
        session_factory=session_factory,
        settings=Settings(DATABASE_URL=db_url, RUNS_DIR=runs_dir, OWNER_EMAIL="owner@example.com", SMTP_HOST=""),
        cashback_provider=_FakeCashbackProvider(),
        email_provider=_FakeEmailProvider(),
    )

    async def _fake_fetch_offer(product_url: str, store_key: str, *, zip_code: str):
        if product_url.endswith("/5869"):
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

    issued = await service.create_compare_evidence_package(
        submitted_urls=[
            "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
            "https://www.99ranch.com/product-details/1615424/8899/078895126389",
        ],
        zip_code="98004",
    )
    abstained = await service.create_compare_evidence_package(
        submitted_urls=[
            "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
            "https://example.com/not-supported",
        ],
        zip_code="98004",
    )

    review_record = await service.record_recommendation_shadow_review(
        artifact_id=issued["artifact_id"],
        reviewer="maintainer",
        decision="overridden",
        reason_code="false_positive",
        outcome_category="false_positive",
        observed_outcome="reviewer_disagreed",
        notes="Later evidence showed the internal wait call was too conservative.",
        follow_up_action="Keep collecting compare evidence before any stronger launch discussion.",
        expected_verdict="recheck_later",
    )
    assert review_record["agreement_bucket"] == "false_positive"
    assert review_record["verdict_at_review_time"] == "wait"
    assert Path(service._recommendation_shadow_review_log_path()).is_file()
    reviewed_shadow_payload = json.loads(Path(issued["artifact_path"]).with_name("recommendation_shadow.json").read_text(encoding="utf-8"))
    assert reviewed_shadow_payload["review"]["state"] == "overridden"
    assert reviewed_shadow_payload["review"]["outcome_category"] == "false_positive"
    assert reviewed_shadow_payload["monitoring"]["agreement_bucket"] == "false_positive"

    skipped_dir = runs_dir / "compare-evidence" / "11111111-1111-1111-1111-111111111111"
    skipped_dir.mkdir(parents=True, exist_ok=True)
    (skipped_dir / "compare_evidence.json").write_text(
        json.dumps({"artifact_id": "11111111-1111-1111-1111-111111111111"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    invalid_dir = runs_dir / "compare-evidence" / "22222222-2222-2222-2222-222222222222"
    invalid_dir.mkdir(parents=True, exist_ok=True)
    (invalid_dir / "compare_evidence.json").write_text(
        json.dumps({"artifact_id": "22222222-2222-2222-2222-222222222222"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (invalid_dir / "recommendation_shadow.json").write_text("{not-json", encoding="utf-8")

    summary_payload = await service.create_recommendation_shadow_monitoring_summary()
    replay_manifest = await service.create_recommendation_replay_manifest()

    assert summary_payload["artifact_kind"] == "recommendation_shadow_monitoring"
    assert summary_payload["monitoring_contract_version"] == "v1"
    assert summary_payload["mode"] == "internal_only_monitoring"
    assert summary_payload["visibility"] == "internal_only"
    assert summary_payload["future_launch_blocked"] is True
    assert summary_payload["review_log_path"].endswith("recommendation_shadow_reviews.ndjson")
    assert summary_payload["review_record_count"] == 1
    assert Path(summary_payload["artifact_path"]).is_file()
    assert Path(summary_payload["html_path"]).is_file()
    assert "public API" in Path(summary_payload["html_path"]).read_text(encoding="utf-8")
    assert summary_payload["review_record_count"] == 1
    assert summary_payload["review_log_path"].endswith("recommendation_shadow_reviews.ndjson")

    summary = summary_payload["summary"]
    assert summary["total_artifacts"] == 4
    assert summary["valid_shadow_artifact_count"] == 2
    assert summary["issued_verdict_count"] == 1
    assert summary["abstention_count"] == 1
    assert summary["invalid_artifact_count"] == 1
    assert summary["skipped_artifact_count"] == 1
    assert summary["invalid_or_skipped_count"] == 2
    assert summary["review_pending_count"] == 1
    assert summary["reviewed_count"] == 1
    assert summary["verdict_distribution"] == {
        "insufficient_evidence": 1,
        "wait": 1,
    }
    assert summary["evidence_strength_buckets"] == {
        "insufficient_compare_context": 1,
        "strong_compare_wait": 1,
    }
    assert summary["review_state_buckets"] == {
        "overridden": 1,
        "pending_internal_review": 1,
    }
    assert summary["abstention_code_buckets"] == {
        "single_resolved_candidate": 1,
    }
    assert summary["disagreement_buckets"] == {
        "false_positive": 1,
    }
    assert len(summary_payload["recent_artifacts"]) == 2
    assert {
        item["review_state"] for item in summary_payload["recent_artifacts"]
    } == {"overridden", "pending_internal_review"}

    assert replay_manifest["artifact_kind"] == "recommendation_replay_manifest"
    assert replay_manifest["replay_contract_version"] == "v1"
    assert replay_manifest["mode"] == "internal_only_replay"
    assert replay_manifest["visibility"] == "internal_only"
    assert Path(replay_manifest["artifact_path"]).is_file()
    assert replay_manifest["summary"] == {
        "total_candidates": 4,
        "included_count": 2,
        "skipped_count": 2,
    }
    assert replay_manifest["admission_rules"] == [
        "compare_evidence.json exists",
        "recommendation_shadow.json exists",
        "shadow_contract_version == v1",
        "surface_anchor is an approved internal evaluation anchor",
        "deterministic_truth_anchor.artifact_path matches compare_evidence.json",
    ]
    assert {
        entry["skip_reason"]
        for entry in replay_manifest["entries"]
        if not entry["included"]
    } == {"missing_shadow_artifact", "invalid_shadow_artifact"}

    included_entries = [entry for entry in replay_manifest["entries"] if entry["included"]]
    assert len(included_entries) == 2
    reviewed_entry = next(entry for entry in included_entries if entry["artifact_id"] == issued["artifact_id"])
    assert reviewed_entry["verdict"] == "wait"
    assert reviewed_entry["review_state"] == "overridden"
    assert reviewed_entry["adjudication"]["expected_verdict"] == "recheck_later"
    assert reviewed_entry["adjudication"]["actual_verdict"] == "wait"
    assert reviewed_entry["replay_source"]["surface_anchor"] == "compare_preview"
    assert reviewed_entry["replay_source"]["compare_evidence_path"].endswith("/compare_evidence.json")
    assert reviewed_entry["replay_source"]["shadow_artifact_path"].endswith("/recommendation_shadow.json")
    abstained_entry = next(entry for entry in included_entries if entry["artifact_id"] == abstained["artifact_id"])
    assert abstained_entry["verdict"] == "insufficient_evidence"
    assert abstained_entry["abstention_active"] is True
    assert abstained_entry["abstention_code"] == "single_resolved_candidate"
    assert abstained_entry["replay_source"]["surface_anchor"] == "compare_preview"


@pytest.mark.asyncio
async def test_product_service_records_recommendation_shadow_review(monkeypatch, tmp_path) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'recommendation-shadow-review.db'}"
    await init_product_database(db_url)
    runs_dir = tmp_path / "runs"
    session_factory = get_session_factory(db_url)
    service = ProductService(
        session_factory=session_factory,
        settings=Settings(DATABASE_URL=db_url, RUNS_DIR=runs_dir, OWNER_EMAIL="owner@example.com", SMTP_HOST=""),
        cashback_provider=_FakeCashbackProvider(),
        email_provider=_FakeEmailProvider(),
    )

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

    created = await service.create_compare_evidence_package(
        submitted_urls=[
            "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
            "https://www.99ranch.com/product-details/1615424/8899/078895126389",
        ],
        zip_code="98004",
    )

    review_record = await service.record_recommendation_shadow_review(
        artifact_id=created["artifact_id"],
        reviewer="maintainer",
        decision="overridden",
        reason_code="false_positive",
        outcome_category="false_positive",
        observed_outcome="Later evidence showed the internal wait verdict was too conservative.",
        notes="Human review overruled the shadow call.",
        follow_up_action="Keep collecting stronger timing evidence before any stronger verdict.",
        expected_verdict="recheck_later",
        actual_verdict="wait",
        evidence_refs=[
            {
                "code": "post_review_outcome",
                "label": "Later observed outcome",
                "anchor": "review.observed_outcome",
            }
        ],
    )

    review_log_path = runs_dir / "compare-evidence" / "recommendation_shadow_reviews.ndjson"
    shadow_path = Path(created["artifact_path"]).with_name("recommendation_shadow.json")
    replay_manifest_path = runs_dir / "compare-evidence" / "_shadow-monitoring" / "recommendation_replay_manifest.json"
    summary_path = runs_dir / "compare-evidence" / "_shadow-monitoring" / "recommendation_shadow_summary.json"

    assert review_record["review_contract_version"] == "v1"
    assert review_record["artifact_id"] == created["artifact_id"]
    assert review_record["decision"] == "overridden"
    assert review_record["agreement_bucket"] == "false_positive"
    assert review_record["expected_verdict"] == "recheck_later"
    assert review_record["actual_verdict"] == "wait"
    assert review_log_path.is_file()
    assert replay_manifest_path.is_file()
    assert summary_path.is_file()

    shadow_payload = json.loads(shadow_path.read_text(encoding="utf-8"))
    summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert shadow_payload["review"]["state"] == "overridden"
    assert shadow_payload["review"]["owner"] == "maintainer"
    assert shadow_payload["review"]["reason_code"] == "false_positive"
    assert shadow_payload["monitoring"]["review_state"] == "overridden"
    assert shadow_payload["monitoring"]["agreement_bucket"] == "false_positive"
    assert shadow_payload["review_log_path"] == str(review_log_path)
    assert summary_payload["review_record_count"] == 1


@pytest.mark.asyncio
async def test_product_service_creates_recommendation_replay_manifest(monkeypatch, tmp_path) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'recommendation-replay-manifest.db'}"
    await init_product_database(db_url)
    runs_dir = tmp_path / "runs"
    session_factory = get_session_factory(db_url)
    service = ProductService(
        session_factory=session_factory,
        settings=Settings(DATABASE_URL=db_url, RUNS_DIR=runs_dir, OWNER_EMAIL="owner@example.com", SMTP_HOST=""),
        cashback_provider=_FakeCashbackProvider(),
        email_provider=_FakeEmailProvider(),
    )

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

    issued = await service.create_compare_evidence_package(
        submitted_urls=[
            "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
            "https://www.99ranch.com/product-details/1615424/8899/078895126389",
        ],
        zip_code="98004",
    )
    abstained = await service.create_compare_evidence_package(
        submitted_urls=[
            "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
            "https://example.com/not-supported",
        ],
        zip_code="98004",
    )
    await service.record_recommendation_shadow_review(
        artifact_id=issued["artifact_id"],
        reviewer="maintainer",
        decision="confirmed",
        reason_code="correct_verdict",
        outcome_category="correct_verdict",
        observed_outcome="Later evidence still supported the internal wait verdict.",
        expected_verdict="wait",
        actual_verdict="wait",
    )

    skipped_dir = runs_dir / "compare-evidence" / "33333333-3333-3333-3333-333333333333"
    skipped_dir.mkdir(parents=True, exist_ok=True)
    (skipped_dir / "compare_evidence.json").write_text(
        json.dumps({"artifact_id": "33333333-3333-3333-3333-333333333333"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    manifest_payload = await service.create_recommendation_replay_manifest()

    assert manifest_payload["artifact_kind"] == "recommendation_replay_manifest"
    assert manifest_payload["replay_contract_version"] == "v1"
    assert manifest_payload["mode"] == "internal_only_replay"
    assert manifest_payload["visibility"] == "internal_only"
    assert Path(manifest_payload["artifact_path"]).is_file()
    assert manifest_payload["summary"] == {
        "total_candidates": 3,
        "included_count": 2,
        "skipped_count": 1,
    }

    entries_by_id = {item["artifact_id"]: item for item in manifest_payload["entries"]}
    assert entries_by_id[issued["artifact_id"]]["included"] is True
    assert entries_by_id[issued["artifact_id"]]["status"] == "issued"
    assert entries_by_id[issued["artifact_id"]]["verdict"] == "wait"
    assert entries_by_id[issued["artifact_id"]]["review_state"] == "confirmed"
    assert entries_by_id[issued["artifact_id"]]["adjudication"]["decision"] == "confirmed"
    assert entries_by_id[issued["artifact_id"]]["adjudication"]["expected_verdict"] == "wait"
    assert entries_by_id[abstained["artifact_id"]]["included"] is True
    assert entries_by_id[abstained["artifact_id"]]["status"] == "abstained"
    assert entries_by_id[abstained["artifact_id"]]["verdict"] == "insufficient_evidence"
    assert entries_by_id["33333333-3333-3333-3333-333333333333"]["included"] is False
    assert entries_by_id["33333333-3333-3333-3333-333333333333"]["skip_reason"] == "missing_shadow_artifact"


@pytest.mark.asyncio
async def test_product_service_creates_lists_and_reads_compare_evidence_artifact(monkeypatch, tmp_path) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'compare-evidence.db'}"
    await init_product_database(db_url)
    session_factory = get_session_factory(db_url)
    service = ProductService(
        session_factory=session_factory,
        settings=Settings(
            DATABASE_URL=db_url,
            RUNS_DIR=tmp_path / "compare-evidence-runs",
            OWNER_EMAIL="owner@example.com",
            SMTP_HOST="",
            ZIP_CODE="98004",
        ),
        cashback_provider=_FakeCashbackProvider(),
        email_provider=_FakeEmailProvider(),
    )

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

    async with session_factory() as session:
        created = await service.create_compare_evidence_artifact(
            session,
            submitted_urls=[
                "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
                "https://www.99ranch.com/product-details/1615424/8899/078895126389",
            ],
            zip_code="98004",
        )

    assert created["storage_scope"] == "runtime_local_artifact"
    assert created["artifact_kind"] == "compare_evidence"
    assert created["recommendation"]["verdict"] == "wait"
    assert created["recommended_next_step_hint"]["action"] == "create_watch_group"
    assert created["recommended_next_step_hint"]["reason_code"] == "multi_candidate_strong_match"
    assert "shadow_recommendation" not in created
    artifact_path = Path(created["artifact_path"])
    shadow_path = artifact_path.with_name("recommendation_shadow.json")
    assert artifact_path.is_file()
    assert shadow_path.is_file()

    async with session_factory() as session:
        recent = await service.list_compare_evidence_artifacts(session)
        detail = await service.get_compare_evidence_artifact(session, created["artifact_id"])

    assert recent[0]["artifact_id"] == created["artifact_id"]
    assert recent[0]["resolved_count"] == 2
    assert recent[0]["recommendation"]["verdict"] == "wait"
    assert recent[0]["recommended_next_step_hint"]["action"] == "create_watch_group"
    assert "shadow_recommendation" not in recent[0]
    assert detail["artifact_id"] == created["artifact_id"]
    assert detail["submitted_inputs"] == created["submitted_inputs"]
    assert detail["comparisons"][0]["submitted_url"] == "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869"
    assert detail["matches"][0]["score"] > 80
    assert detail["recommendation"]["verdict"] == "wait"
    assert "shadow_recommendation" not in detail


@pytest.mark.asyncio
async def test_notification_settings_persist_without_watch_tasks(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'notification-settings.db'}"
    monkeypatch.setattr(settings, "DATABASE_URL", db_url)
    monkeypatch.setattr(settings, "OWNER_EMAIL", "owner@example.com")
    session_factory = create_session_factory(db_url)
    await init_product_database(db_url, session_factory)

    service = ProductService(session_factory=session_factory, settings=settings)

    async with session_factory() as session:
        updated = await service.update_notification_settings(
            session,
            default_recipient_email="alerts@example.com",
            cooldown_minutes=55,
            notifications_enabled=False,
        )
        await session.commit()
        assert updated == {
            "default_recipient_email": "alerts@example.com",
            "cooldown_minutes": 55,
            "notifications_enabled": False,
        }

    async with session_factory() as session:
        payload = await service.get_notification_settings(session)
        assert payload == {
            "default_recipient_email": "alerts@example.com",
            "cooldown_minutes": 55,
            "notifications_enabled": False,
        }


@pytest.mark.asyncio
async def test_product_service_normalizes_unexpected_runtime_error(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'unexpected.db'}"
    await init_product_database(db_url)
    session_factory = get_session_factory(db_url)
    service = ProductService(
        session_factory=session_factory,
        settings=Settings(
            DATABASE_URL=db_url,
            OWNER_EMAIL="owner@example.com",
            SMTP_HOST="",
            ZIP_CODE="98004",
        ),
        cashback_provider=_FakeCashbackProvider(),
        email_provider=_FakeEmailProvider(),
    )

    async with session_factory() as session:
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
        await session.commit()

    async def _boom(*args, **kwargs):
        raise RuntimeError("raw driver text should not leak")

    monkeypatch.setattr(service, "_fetch_offer", _boom)

    async with session_factory() as session:
        run = await service.run_watch_task(session, task.id, triggered_by="manual")
        await session.commit()
        assert run.status == "failed"
        assert run.error_code == "unexpected_runtime_error"
        assert run.error_message == "unexpected_runtime_error"

    async with session_factory() as session:
        detail = await service.get_watch_task_detail(session, task.id)
        assert detail["runs"][0]["error_message"] == "unexpected_runtime_error"


@pytest.mark.asyncio
async def test_product_service_create_and_run_watch_group(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'group.db'}"
    await init_product_database(db_url)
    session_factory = get_session_factory(db_url)
    service = ProductService(
        session_factory=session_factory,
        settings=Settings(
            DATABASE_URL=db_url,
            RUNS_DIR=tmp_path / "group-runs",
            OWNER_EMAIL="owner@example.com",
            SMTP_HOST="",
            ZIP_CODE="98004",
        ),
        cashback_provider=_FakeCashbackProvider(),
        email_provider=_FakeEmailProvider(),
    )

    async with session_factory() as session:
        group = await service.create_watch_group(
            session,
            title="Pear Group",
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
        await session.commit()
        group_id = group.id

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

    async with session_factory() as session:
        run = await service.run_watch_group(session, group_id, triggered_by="manual")
        await session.commit()
        assert run.status == "succeeded"
        assert run.winner_effective_price == pytest.approx(3.78, rel=1e-6)

        group = await session.get(WatchGroup, group_id)
        assert group is not None
        assert group.health_status == "healthy"

        delivery = await session.scalar(select(DeliveryEvent).where(DeliveryEvent.watch_group_id == group_id))
        assert delivery is not None
        assert delivery.status == "sent"

        detail = await service.get_watch_group_detail(session, group_id)
        assert detail["group"]["member_count"] == 2
        assert detail["group"]["current_winner_effective_price"] == pytest.approx(3.78, rel=1e-6)
        assert any(member["is_current_winner"] for member in detail["members"])
        assert detail["deliveries"][0]["status"] == "sent"
        assert detail["decision_explain"]["winner"]["store_key"] == "weee"
        assert detail["decision_explain"]["runner_up"]["store_key"] == "ranch99"
        assert detail["decision_explain"]["comparison"]["effective_price_delta"] == pytest.approx(0.26, rel=1e-6)
        assert detail["decision_explain"]["reliability"] == "strong"
        assert detail["decision_explain"]["reason"]["code"] == "lowest_effective_price_with_cashback"
        assert detail["decision_explain"]["winner"]["member_id"] == detail["group"]["current_winner_member_id"]
        assert detail["decision_explain"]["runner_up"]["member_id"] == run.runner_up_member_id
        assert detail["decision_explain"]["runner_up"]["loss_reasons"][0]["field"] == "effective_price"
        assert detail["decision_explain"]["runner_up"]["loss_reasons"][0]["delta"] == pytest.approx(0.26, rel=1e-6)
        assert detail["decision_explain"]["spread"]["amount"] == pytest.approx(0.26, rel=1e-6)
        assert detail["decision_explain"]["member_outcomes"][0]["outcome"] in {"winner", "runner_up"}
        assert detail["decision_explain"]["risk_note_items"][0]["code"] == "close_price_spread"
        assert detail["ai_decision_explain"]["status"] == "disabled"


@pytest.mark.asyncio
async def test_product_service_create_and_run_safeway_watch_group(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'safeway-group.db'}"
    await init_product_database(db_url)
    session_factory = get_session_factory(db_url)
    cashback = _FakeCashbackProvider()
    service = ProductService(
        session_factory=session_factory,
        settings=Settings(
            DATABASE_URL=db_url,
            RUNS_DIR=tmp_path / "safeway-group-runs",
            OWNER_EMAIL="owner@example.com",
            SMTP_HOST="",
            ZIP_CODE="98004",
        ),
        cashback_provider=cashback,
        email_provider=_FakeEmailProvider(),
    )

    async with session_factory() as session:
        group = await service.create_watch_group(
            session,
            title="Milk Group",
            zip_code="98004",
            cadence_minutes=60,
            threshold_type="effective_price_below",
            threshold_value=7.5,
            cooldown_minutes=30,
            recipient_email="owner@example.com",
            notifications_enabled=True,
            candidates=[
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
        )
        await session.commit()
        group_id = group.id

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

    async with session_factory() as session:
        run = await service.run_watch_group(session, group_id, triggered_by="manual")
        await session.commit()
        assert run.status == "succeeded"
        assert run.winner_effective_price == pytest.approx(4.94, rel=1e-6)

        detail = await service.get_watch_group_detail(session, group_id)
        assert detail["group"]["member_count"] == 2
        assert detail["decision_explain"]["winner"]["store_key"] == "safeway"
        assert detail["decision_explain"]["reason"]["code"] == "lowest_effective_price_with_cashback"
        assert detail["decision_explain"]["winner"]["cashback_amount"] == pytest.approx(0.55, rel=1e-6)

    assert cashback.payloads
    assert {payload.merchant_key for payload in cashback.payloads} == {"safeway"}


@pytest.mark.asyncio
async def test_product_service_watch_group_detail_includes_fake_ai_explain(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'group-ai.db'}"
    await init_product_database(db_url)
    session_factory = get_session_factory(db_url)
    service = ProductService(
        session_factory=session_factory,
        settings=Settings(
            DATABASE_URL=db_url,
            RUNS_DIR=tmp_path / "group-ai-runs",
            OWNER_EMAIL="owner@example.com",
            SMTP_HOST="",
            ZIP_CODE="98004",
            USE_LLM=True,
            AI_PROVIDER="fake",
            AI_MODEL="dealwatch-fake-v1",
            AI_GROUP_EXPLAIN_ENABLED=True,
        ),
        cashback_provider=_FakeCashbackProvider(),
        email_provider=_FakeEmailProvider(),
    )

    async with session_factory() as session:
        group = await service.create_watch_group(
            session,
            title="Pear Group",
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
        await session.commit()
        group_id = group.id

    async def _fake_fetch_offer(product_url: str, store_key: str, *, zip_code: str):
        return Offer(
            store_id=store_key,
            product_key=f"{store_key}-1",
            title="Asian Honey Pears 3ct" if store_key == "weee" else "Asian Honey Pears 3 ct",
            url=product_url,
            price=4.2 if store_key == "weee" else 4.49,
            original_price=5.5 if store_key == "weee" else 5.29,
            fetch_at=datetime.now(timezone.utc),
            context=PriceContext(region=zip_code),
            unit_price_info={"raw": "3 ct"},
        )

    monkeypatch.setattr(service, "_fetch_offer", _fake_fetch_offer)

    async with session_factory() as session:
        await service.run_watch_group(session, group_id, triggered_by="manual")
        await session.commit()
        detail = await service.get_watch_group_detail(session, group_id)

    assert detail["decision_explain"]["reason"]["code"] in {
        "lowest_effective_price",
        "lowest_effective_price_with_cashback",
    }
    assert detail["ai_decision_explain"]["status"] == "ok"
    assert detail["ai_decision_explain"]["provider"]["provider"] == "fake"
    assert "deterministic product truth" in detail["ai_decision_explain"]["summary"]


@pytest.mark.asyncio
async def test_product_service_attention_inbox_separates_tasks_and_groups(tmp_path) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'attention.db'}"
    await init_product_database(db_url)
    session_factory = get_session_factory(db_url)
    service = ProductService(
        session_factory=session_factory,
        settings=Settings(DATABASE_URL=db_url, OWNER_EMAIL="owner@example.com", SMTP_HOST=""),
        cashback_provider=_FakeCashbackProvider(),
        email_provider=_FakeEmailProvider(),
    )

    async with session_factory() as session:
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
            title="Pear Group",
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

    async with session_factory() as session:
        inbox = await service.get_attention_inbox(session)

    assert inbox["total_items"] == 2
    assert inbox["task_items"][0]["kind"] == "task"
    assert inbox["group_items"][0]["kind"] == "group"
    assert "re-enable the store runtime switch" in inbox["task_items"][0]["recommended_action"]
    assert "successful candidate" in inbox["group_items"][0]["reason"]


@pytest.mark.asyncio
async def test_product_service_health_and_price_signal(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'health.db'}"
    await init_product_database(db_url)
    session_factory = get_session_factory(db_url)
    service = ProductService(
        session_factory=session_factory,
        settings=Settings(
            DATABASE_URL=db_url,
            RUNS_DIR=tmp_path / "health-runs",
            OWNER_EMAIL="owner@example.com",
            SMTP_HOST="",
            ZIP_CODE="98004",
        ),
        cashback_provider=_FakeCashbackProvider(),
        email_provider=_FakeEmailProvider(),
    )

    async with session_factory() as session:
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
        await session.commit()
        task_id = task.id

    prices = iter([5.5, 4.2])

    async def _fake_success(*args, **kwargs):
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

    monkeypatch.setattr(service, "_fetch_offer", _fake_success)

    async with session_factory() as session:
        await service.run_watch_task(session, task_id, triggered_by="manual")
        await session.commit()

    async with session_factory() as session:
        await service.run_watch_task(session, task_id, triggered_by="manual")
        await session.commit()
        detail = await service.get_watch_task_detail(session, task_id)
        assert detail["latest_signal"]["previous_listed_price"] == 5.5
        assert detail["latest_signal"]["delta_amount"] == 1.3
        assert detail["latest_signal"]["is_new_low"] is True
        assert detail["task"]["health_status"] == "healthy"

    async def _fake_failure(*args, **kwargs):
        raise RuntimeError("network_broken")

    monkeypatch.setattr(service, "_fetch_offer", _fake_failure)
    for _ in range(3):
        async with session_factory() as session:
            await service.run_watch_task(session, task_id, triggered_by="manual")
            await session.commit()

    async with session_factory() as session:
        detail = await service.get_watch_task_detail(session, task_id)
        assert detail["task"]["health_status"] == "needs_attention"
        assert detail["task"]["manual_intervention_required"] is True
        assert detail["task"]["last_failure_kind"] == "unexpected_runtime_error"


@pytest.mark.asyncio
async def test_product_service_respects_disabled_store_binding(tmp_path) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'binding-disabled.db'}"
    await init_product_database(db_url)
    session_factory = get_session_factory(db_url)
    service = ProductService(
        session_factory=session_factory,
        settings=Settings(DATABASE_URL=db_url, OWNER_EMAIL="owner@example.com", SMTP_HOST="", ZIP_CODE="98004"),
        cashback_provider=_FakeCashbackProvider(),
        email_provider=_FakeEmailProvider(),
    )

    async with session_factory() as session:
        owner = await service.bootstrap_owner(session)
        disabled = await session.scalar(
            select(StoreAdapterBinding).where(StoreAdapterBinding.store_key == "weee").limit(1)
        )
        if disabled is None:
            disabled = StoreAdapterBinding(store_key="weee", enabled=False, adapter_class="test")
            session.add(disabled)
            await session.flush()
        else:
            disabled.enabled = False

        with pytest.raises(ValueError, match="store_disabled"):
            await service.create_watch_task(
                session,
                submitted_url="https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
                zip_code="98004",
                cadence_minutes=60,
                threshold_type="price_below",
                threshold_value=4.5,
                cooldown_minutes=30,
                recipient_email="owner@example.com",
            )

        target = await service._resolve_or_create_watch_target(
            session,
            owner.id,
            "https://www.99ranch.com/product-details/1615424/8899/078895126389",
        )
        disabled_ranch = await session.scalar(
            select(StoreAdapterBinding).where(StoreAdapterBinding.store_key == "ranch99").limit(1)
        )
        if disabled_ranch is None:
            disabled_ranch = StoreAdapterBinding(store_key="ranch99", enabled=False, adapter_class="test")
            session.add(disabled_ranch)
        else:
            disabled_ranch.enabled = False

        task = WatchTask(
            user_id=owner.id,
            watch_target_id=target.id,
            zip_code="98004",
            status="active",
            cadence_minutes=60,
            threshold_type="price_below",
            threshold_value=4.5,
            cooldown_minutes=30,
            next_run_at=datetime.now(timezone.utc),
        )
        session.add(task)
        await session.commit()
        task_id = task.id

    async with session_factory() as session:
        run = await service.run_watch_task(session, task_id, triggered_by="manual")
        await session.commit()
        assert run.status == "blocked"
        assert run.error_code == "store_disabled"


@pytest.mark.asyncio
async def test_product_service_update_watch_group_status(tmp_path) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'update-group.db'}"
    await init_product_database(db_url)
    session_factory = get_session_factory(db_url)
    service = ProductService(
        session_factory=session_factory,
        settings=Settings(DATABASE_URL=db_url, OWNER_EMAIL="owner@example.com", SMTP_HOST="", ZIP_CODE="98004"),
        cashback_provider=_FakeCashbackProvider(),
        email_provider=_FakeEmailProvider(),
    )

    async with session_factory() as session:
        group = await service.create_watch_group(
            session,
            title="Pear Group",
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
        await session.commit()
        group_id = group.id

    async with session_factory() as session:
        group = await service.update_watch_group(session, group_id, status="paused")
        await session.commit()
        assert group.status == "paused"


@pytest.mark.asyncio
async def test_product_service_runtime_readiness_reports_real_sources(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'readiness.db'}"
    await init_product_database(db_url)
    session_factory = get_session_factory(db_url)
    smoke_dir = tmp_path / "smoke-artifacts"
    smoke_dir.mkdir()
    (smoke_dir / "api-smoke.log").write_text("API_OK\n", encoding="utf-8")
    (smoke_dir / "worker-smoke.log").write_text("WORKER_OK\n", encoding="utf-8")
    service = ProductService(
        session_factory=session_factory,
        settings=Settings(
            DATABASE_URL=db_url,
            OWNER_EMAIL="owner@example.com",
            OWNER_BOOTSTRAP_TOKEN="real-bootstrap-token",
            APP_BASE_URL="http://127.0.0.1:8000",
            WEBUI_DEV_URL="http://127.0.0.1:5173",
            ZIP_CODE="98004",
            ENABLED_STORES=["weee", "target"],
            SMTP_HOST="",
        ),
        cashback_provider=_FakeCashbackProvider(),
        email_provider=_FakeEmailProvider(),
    )
    monkeypatch.setattr(services_module, "SMOKE_ARTIFACTS_DIR", smoke_dir)

    async with session_factory() as session:
        await service.bootstrap_owner(session)
        session.add_all(
            [
                StoreAdapterBinding(store_key="weee", enabled=True, adapter_class="WeeeAdapter"),
                StoreAdapterBinding(store_key="target", enabled=True, adapter_class="TargetAdapter"),
            ]
        )
        await session.commit()

    async with session_factory() as session:
        payload = await service.get_runtime_readiness(session)

    checks = {item["key"]: item for item in payload["checks"]}
    assert payload["overall_status"] == "blocked"
    assert checks["database"]["status"] == "warning"
    assert checks["database"]["detail"]["database_backend"] == "sqlite+aiosqlite"
    assert checks["owner"]["status"] == "ready"
    assert checks["stores"]["status"] == "ready"
    assert checks["stores"]["detail"]["enabled_store_count"] == 2
    assert checks["notifications"]["status"] == "warning"
    assert checks["startup_preflight"]["status"] == "blocked"
    assert "DATABASE_URL" in checks["startup_preflight"]["detail"]["blocker_keys"]
    assert checks["smoke"]["status"] == "ready"
    assert checks["smoke"]["detail"]["smoke_log_count"] == 2


@pytest.mark.asyncio
async def test_product_service_builder_starter_pack_reports_current_builder_contract(tmp_path) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'builder-starter-pack.db'}"
    await init_product_database(db_url)
    session_factory = get_session_factory(db_url)
    service = ProductService(
        session_factory=session_factory,
        settings=Settings(
            DATABASE_URL=db_url,
            OWNER_EMAIL="owner@example.com",
            OWNER_BOOTSTRAP_TOKEN="real-bootstrap-token",
            APP_BASE_URL="http://127.0.0.1:8000",
            WEBUI_DEV_URL="http://127.0.0.1:5173",
            ZIP_CODE="98004",
            ENABLED_STORES=["weee", "target"],
            SMTP_HOST="",
        ),
        cashback_provider=_FakeCashbackProvider(),
        email_provider=_FakeEmailProvider(),
    )

    payload = await service.get_builder_starter_pack()

    assert payload["surface_version"] == "phase1"
    assert payload["launch_contract"]["mcp_inventory"].endswith("dealwatch.mcp list-tools --json")
    assert payload["launch_contract"]["cli_builder_starter_pack"].endswith("dealwatch builder-starter-pack --json")
    assert payload["launch_contract"]["mcp_client_starters"].endswith("dealwatch.mcp client-starters --json")
    assert payload["client_starters"]["openclaw"] == "docs/integrations/prompts/openclaw-starter.md"
    assert (
        payload["client_skill_cards"]["openclaw"]
        == "docs/integrations/skills/openclaw-readonly-builder-skill.md"
    )
    assert (
        payload["client_adapter_recipes"]["openclaw"]
        == "docs/integrations/recipes/openclaw.md"
    )
    assert payload["client_wrapper_status"]["claude_code"] == "official_wrapper_documented"
    assert payload["client_wrapper_status"]["codex"] == "official_wrapper_documented"
    assert payload["client_wrapper_status"]["openhands"] == "official_wrapper_documented"
    assert payload["client_wrapper_status"]["openclaw"] == "official_wrapper_documented"
    assert payload["client_wrapper_examples"]["codex"] == "docs/integrations/examples/codex-mcp-config.toml"
    assert payload["client_wrapper_examples"]["openhands"] == "docs/integrations/examples/openhands-config.toml"
    assert payload["client_wrapper_examples"]["opencode"] == "docs/integrations/examples/opencode.jsonc"
    assert payload["client_wrapper_examples"]["openclaw"] == "docs/integrations/examples/openclaw-mcp-servers.json"
    assert payload["client_wrapper_sources"]["openclaw"] == "https://docs.openclaw.ai/cli/mcp"
    assert payload["client_wrapper_surfaces"]["openhands"] == "config_toml_mcp_stdio_servers"
    assert payload["launch_contract"]["mcp_streamable_http"].endswith("dealwatch.mcp serve --transport streamable-http")
    assert payload["launch_contract"]["mcp_streamable_http_endpoint"] == "http://127.0.0.1:8000/mcp"
    assert "write-side MCP" in payload["deferred"]
    assert payload["docs"]["config_recipes"] == "docs/integrations/config-recipes.md"
    assert payload["docs"]["skills"] == "docs/integrations/skills/README.md"
    assert payload["public_builder_page"] == "site/builders.html"
    assert payload["skill_pack"]["path"] == "docs/integrations/skills/dealwatch-readonly-builder-skill.md"


@pytest.mark.asyncio
async def test_product_service_builder_client_config_exports_copyable_example(tmp_path) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'builder-client-config.db'}"
    await init_product_database(db_url)
    session_factory = get_session_factory(db_url)
    service = ProductService(
        session_factory=session_factory,
        settings=Settings(
            DATABASE_URL=db_url,
            OWNER_EMAIL="owner@example.com",
            OWNER_BOOTSTRAP_TOKEN="real-bootstrap-token",
            APP_BASE_URL="http://127.0.0.1:8000",
            WEBUI_DEV_URL="http://127.0.0.1:5173",
            ZIP_CODE="98004",
            ENABLED_STORES=["weee", "target"],
            SMTP_HOST="",
        ),
        cashback_provider=_FakeCashbackProvider(),
        email_provider=_FakeEmailProvider(),
    )

    payload = await service.get_builder_client_config("codex")

    assert payload["client"] == "codex"
    assert payload["wrapper_example_path"] == "docs/integrations/examples/codex-mcp-config.toml"
    assert payload["recommended_transport"] == "streamable_http"
    assert payload["recipe_markdown"].startswith("# DealWatch Recipe For Codex")
    assert payload["docs"]["config_recipes"] == "docs/integrations/config-recipes.md"
    assert payload["read_surfaces"]["http"] == "GET /api/runtime/builder-client-config/codex"
    assert "http://127.0.0.1:8000/mcp" in payload["wrapper_example_content"]


@pytest.mark.asyncio
async def test_product_service_builder_client_configs_exports_bundle(tmp_path) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'builder-client-configs.db'}"
    await init_product_database(db_url)
    session_factory = get_session_factory(db_url)
    service = ProductService(
        session_factory=session_factory,
        settings=Settings(
            DATABASE_URL=db_url,
            OWNER_EMAIL="owner@example.com",
            OWNER_BOOTSTRAP_TOKEN="real-bootstrap-token",
            APP_BASE_URL="http://127.0.0.1:8000",
            WEBUI_DEV_URL="http://127.0.0.1:5173",
            ZIP_CODE="98004",
            ENABLED_STORES=["weee", "target"],
            SMTP_HOST="",
        ),
        cashback_provider=_FakeCashbackProvider(),
        email_provider=_FakeEmailProvider(),
    )

    payload = await service.get_builder_client_configs()

    assert payload["export_kind"] == "builder_client_configs"
    assert payload["client_count"] == 5
    assert payload["client_ids"] == ["claude-code", "codex", "openhands", "opencode", "openclaw"]
    assert payload["read_surfaces"]["http"] == "GET /api/runtime/builder-client-configs"
    assert payload["read_surfaces"]["mcp_tool"] == "list_builder_client_configs"
    codex = next(item for item in payload["clients"] if item["client"] == "codex")
    assert codex["wrapper_example_path"] == "docs/integrations/examples/codex-mcp-config.toml"


@pytest.mark.asyncio
async def test_product_service_store_onboarding_cockpit_reports_real_store_truth(tmp_path) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'store-cockpit.db'}"
    await init_product_database(db_url)
    session_factory = get_session_factory(db_url)
    app_settings = Settings(
        DATABASE_URL=db_url,
        OWNER_EMAIL="owner@example.com",
        OWNER_BOOTSTRAP_TOKEN="real-bootstrap-token",
        APP_BASE_URL="http://127.0.0.1:8000",
        WEBUI_DEV_URL="http://127.0.0.1:5173",
        ZIP_CODE="98004",
        ENABLED_STORES=["weee", "target"],
        SMTP_HOST="",
    )
    await sync_store_adapter_bindings(session_factory, app_settings)
    service = ProductService(
        session_factory=session_factory,
        settings=app_settings,
        cashback_provider=_FakeCashbackProvider(),
        email_provider=_FakeEmailProvider(),
    )

    async with session_factory() as session:
        payload = await service.get_store_onboarding_cockpit(session)

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
    assert payload["consistency"]["missing_in_registry"] == []
    assert payload["consistency"]["missing_in_capability_registry"] == []
    assert payload["capability_matrix"][0]["store_key"] == "ranch99"
    assert payload["capability_matrix"][0]["enabled"] is False
    assert payload["capability_matrix"][0]["contract_test_reference_present"] is True
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
    assert safeway["next_step_codes"] == []
    assert safeway["missing_capabilities"] == []
    assert "tests/test_safeway_adapter.py" in safeway["contract_test_paths"]
    assert "tests/test_product_service.py" in safeway["contract_test_paths"]
    assert "tests/test_product_api.py" in safeway["contract_test_paths"]
    assert "docs/roadmaps/dealwatch-safeway-c1.md" in safeway["source_of_truth_files"]
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
    assert payload["limited_support_lane"]["support_channel"] == "limited"
    assert payload["limited_support_lane"]["support_tier"] == "limited_guidance_only"
    assert "save_compare_evidence" in payload["limited_support_lane"]["supported_actions"]
    assert "create_watch_task" in payload["limited_support_lane"]["blocked_actions"]
    assert "docs/runbooks/store-onboarding-contract.md" in payload["limited_support_lane"]["source_of_truth_files"]
    assert "tests/test_product_providers.py" in payload["limited_support_lane"]["source_of_truth_files"]
    assert payload["onboarding_contract"]["source_runbook_path"] == "docs/runbooks/store-onboarding-contract.md"
    assert payload["onboarding_contract"]["runtime_binding_truth"] != []
    assert payload["onboarding_contract"]["limited_support_contract"] != []
    assert "./scripts/test.sh -q tests/test_adapter_contracts.py" in payload["onboarding_contract"]["verification_commands"]
    assert payload["onboarding_contract"]["required_files"][0]["path_template"] == "src/dealwatch/stores/<store>/adapter.py"


@pytest.mark.asyncio
async def test_sync_store_adapter_bindings_uses_manifest_default_enablement_when_allowlist_is_unset(
    tmp_path, monkeypatch
) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'binding-default-enablement.db'}"
    await init_product_database(db_url)
    session_factory = get_session_factory(db_url)
    patched_registry = dict(store_bindings_module.STORE_CAPABILITY_REGISTRY)
    patched_registry["safeway"] = replace(patched_registry["safeway"], default_enabled=False)
    monkeypatch.setattr(store_bindings_module, "STORE_CAPABILITY_REGISTRY", patched_registry)

    await sync_store_adapter_bindings(session_factory, Settings(DATABASE_URL=db_url, ENABLED_STORES=[]))

    async with session_factory() as session:
        rows = list((await session.scalars(select(StoreAdapterBinding))).all())
        enabled_map = {row.store_key: row.enabled for row in rows}

    assert enabled_map["safeway"] is False
    assert enabled_map["weee"] is True
    assert enabled_map["ranch99"] is True
    assert enabled_map["target"] is True


@pytest.mark.asyncio
async def test_sync_store_adapter_bindings_allows_explicit_opt_in_for_default_disabled_store(
    tmp_path, monkeypatch
) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'binding-explicit-opt-in.db'}"
    await init_product_database(db_url)
    session_factory = get_session_factory(db_url)
    patched_registry = dict(store_bindings_module.STORE_CAPABILITY_REGISTRY)
    patched_registry["safeway"] = replace(patched_registry["safeway"], default_enabled=False)
    monkeypatch.setattr(store_bindings_module, "STORE_CAPABILITY_REGISTRY", patched_registry)

    await sync_store_adapter_bindings(session_factory, Settings(DATABASE_URL=db_url, ENABLED_STORES=["safeway"]))

    async with session_factory() as session:
        rows = list((await session.scalars(select(StoreAdapterBinding))).all())
        enabled_map = {row.store_key: row.enabled for row in rows}

    assert enabled_map == {
        "weee": False,
        "ranch99": False,
        "target": False,
        "safeway": True,
        "walmart": False,
    }


@pytest.mark.asyncio
async def test_product_service_recovery_inbox_separates_task_and_group_items(tmp_path) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'recovery.db'}"
    await init_product_database(db_url)
    session_factory = get_session_factory(db_url)
    service = ProductService(
        session_factory=session_factory,
        settings=Settings(
            DATABASE_URL=db_url,
            OWNER_EMAIL="owner@example.com",
            OWNER_BOOTSTRAP_TOKEN="real-bootstrap-token",
            APP_BASE_URL="http://127.0.0.1:8000",
            WEBUI_DEV_URL="http://127.0.0.1:5173",
            ZIP_CODE="98004",
            ENABLED_STORES=["weee", "ranch99"],
            SMTP_HOST="",
        ),
        cashback_provider=_FakeCashbackProvider(),
        email_provider=_FakeEmailProvider(),
    )

    async with session_factory() as session:
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
        task.backoff_until = datetime.now(timezone.utc) + timedelta(minutes=30)
        task.last_failure_kind = "blocked"
        task.last_error_code = "store_disabled"
        task.last_error_message = "store_disabled"
        task.next_run_at = datetime.now(timezone.utc) + timedelta(minutes=45)
        group.health_status = "degraded"
        group.manual_intervention_required = False
        group.backoff_until = datetime.now(timezone.utc) + timedelta(minutes=15)
        group.last_failure_kind = "unexpected_runtime_error"
        group.last_error_code = "unexpected_runtime_error"
        group.last_error_message = "unexpected_runtime_error"
        group.next_run_at = datetime.now(timezone.utc) + timedelta(minutes=20)
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

    async with session_factory() as session:
        payload = await service.get_recovery_inbox(session)

    assert payload["total_items"] == 2
    assert [item["kind"] for item in payload["task_items"]] == ["task"]
    assert [item["kind"] for item in payload["group_items"]] == ["group"]
    assert payload["task_items"][0]["last_run_status"] == "blocked"
    assert (
        payload["task_items"][0]["recommended_action"]
        == "Open Settings, re-enable the store runtime switch, then rerun it manually."
    )
    assert payload["group_items"][0]["last_run_status"] == "failed"
    assert (
        payload["group_items"][0]["recommended_action"]
        == "Inspect the latest run details and artifact evidence before retrying."
    )
    assert payload["ai_copilot"]["status"] == "disabled"


@pytest.mark.asyncio
async def test_product_service_safeway_group_failure_enters_recovery_inbox(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'safeway-recovery.db'}"
    await init_product_database(db_url)
    session_factory = get_session_factory(db_url)
    service = ProductService(
        session_factory=session_factory,
        settings=Settings(
            DATABASE_URL=db_url,
            RUNS_DIR=tmp_path / "safeway-recovery-runs",
            OWNER_EMAIL="owner@example.com",
            APP_BASE_URL="http://127.0.0.1:8000",
            WEBUI_DEV_URL="http://127.0.0.1:5173",
            ZIP_CODE="98004",
            ENABLED_STORES=["safeway"],
            SMTP_HOST="",
        ),
        cashback_provider=_FakeCashbackProvider(),
        email_provider=_FakeEmailProvider(),
    )

    async with session_factory() as session:
        group = await service.create_watch_group(
            session,
            title="Safeway Recovery Group",
            zip_code="98004",
            cadence_minutes=60,
            threshold_type="effective_price_below",
            threshold_value=8.0,
            cooldown_minutes=30,
            recipient_email="owner@example.com",
            notifications_enabled=True,
            candidates=[
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
        )
        await session.commit()
        group_id = group.id

    async def _fake_fetch_offer(*_args, **_kwargs):
        return None

    monkeypatch.setattr(service, "_fetch_offer", _fake_fetch_offer)

    async with session_factory() as session:
        run = await service.run_watch_group(session, group_id, triggered_by="manual")
        await session.commit()
        assert run.error_code == "watch_group_no_successful_candidates"

        payload = await service.get_recovery_inbox(session)

    assert payload["total_items"] == 1
    assert [item["kind"] for item in payload["group_items"]] == ["group"]
    assert payload["group_items"][0]["last_run_status"] == "failed"
    assert payload["group_items"][0]["reason"] == "The latest group run finished without any successful candidate."


@pytest.mark.asyncio
async def test_product_service_recovery_inbox_includes_failed_safeway_watch_group(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'safeway-recovery.db'}"
    await init_product_database(db_url)
    session_factory = get_session_factory(db_url)
    service = ProductService(
        session_factory=session_factory,
        settings=Settings(
            DATABASE_URL=db_url,
            OWNER_EMAIL="owner@example.com",
            SMTP_HOST="",
            ZIP_CODE="98004",
        ),
        cashback_provider=_FakeCashbackProvider(),
        email_provider=_FakeEmailProvider(),
    )

    async with session_factory() as session:
        group = await service.create_watch_group(
            session,
            title="Safeway Recovery Group",
            zip_code="98004",
            cadence_minutes=60,
            threshold_type="effective_price_below",
            threshold_value=7.0,
            cooldown_minutes=30,
            recipient_email="owner@example.com",
            notifications_enabled=True,
            candidates=[
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
        )
        await session.commit()
        group_id = group.id

    async def _fetch_none(*args, **kwargs):
        return None

    monkeypatch.setattr(service, "_fetch_offer", _fetch_none)

    async with session_factory() as session:
        run = await service.run_watch_group(session, group_id, triggered_by="manual")
        await session.commit()
        assert run.status == "failed"
        assert run.error_code == "watch_group_no_successful_candidates"

    async with session_factory() as session:
        payload = await service.get_recovery_inbox(session)

    safeway_group = next(item for item in payload["group_items"] if item["title"] == "Safeway Recovery Group")
    assert payload["task_items"] == []
    assert safeway_group["last_error_code"] == "watch_group_no_successful_candidates"
    assert safeway_group["recommended_action"] == "Inspect member results, fix the failing candidate path, then rerun the group."


@pytest.mark.asyncio
async def test_product_service_recovery_inbox_includes_fake_ai_copilot(tmp_path) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'recovery-ai.db'}"
    await init_product_database(db_url)
    session_factory = get_session_factory(db_url)
    service = ProductService(
        session_factory=session_factory,
        settings=Settings(
            DATABASE_URL=db_url,
            OWNER_EMAIL="owner@example.com",
            SMTP_HOST="",
            ZIP_CODE="98004",
            USE_LLM=True,
            AI_PROVIDER="fake",
            AI_MODEL="dealwatch-fake-v1",
            AI_RECOVERY_COPILOT_ENABLED=True,
        ),
    )

    async with session_factory() as session:
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
            title="Pear Group",
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
        task.last_failure_kind = "blocked"
        task.last_error_code = "store_disabled"
        task.last_error_message = "store_disabled"
        group.health_status = "degraded"
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
        await session.commit()

    async with session_factory() as session:
        payload = await service.get_recovery_inbox(session)

    assert payload["total_items"] == 2
    assert payload["task_items"][0]["recommended_action"] == (
        "Open Settings, re-enable the store runtime switch, then rerun it manually."
    )
    assert payload["ai_copilot"]["status"] == "ok"
    assert payload["ai_copilot"]["provider"]["provider"] == "fake"
