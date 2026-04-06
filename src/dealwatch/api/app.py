from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from hmac import compare_digest
import re
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from dealwatch.api.deps import get_db_session, get_product_service, prepare_product_runtime, shutdown_product_runtime
from dealwatch.api.schemas import (
    ComparePreviewResponse,
    CompareEvidencePackageCreateRequest,
    CompareProductsRequest,
    CreateWatchGroupRequest,
    CreateWatchTaskRequest,
    NotificationSettingsResponse,
    RecoveryInboxResponse,
    StoreBindingResponse,
    StoreOnboardingCockpitResponse,
    UpdateWatchGroupRequest,
    UpdateNotificationSettingsRequest,
    UpdateStoreBindingRequest,
    UpdateWatchTaskRequest,
    WatchGroupDetailResponse,
)
from dealwatch.application import ProductService
from dealwatch.domain.enums import DeliveryStatus
from dealwatch.infra.config import clear_log_context, set_log_context, settings
from dealwatch.persistence.models import DeliveryEvent, TaskRun

_LOOPBACK_HOST_ALIASES = ("127.0.0.1", "localhost")
_CLIENT_ERROR_CODE_RE = re.compile(r"^[a-z0-9_]+$")


def _stable_client_error_detail(exc: ValueError, fallback: str) -> str:
    detail = str(exc).strip()
    return detail if _CLIENT_ERROR_CODE_RE.fullmatch(detail) else fallback


@asynccontextmanager
async def lifespan(_: FastAPI):
    await prepare_product_runtime()
    try:
        yield
    finally:
        await shutdown_product_runtime()


def create_app() -> FastAPI:
    app = FastAPI(title="DealWatch API", version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_build_allowed_origins(settings.WEBUI_DEV_URL, settings.APP_BASE_URL),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        set_log_context(service_name="api", correlation_id=request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        clear_log_context()
        return response

    @app.get("/api/health")
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/runtime/readiness")
    async def get_runtime_readiness(
        session: AsyncSession = Depends(get_db_session),
        service: ProductService = Depends(get_product_service),
    ) -> dict:
        return await service.get_runtime_readiness(session)

    @app.get("/api/runtime/attention")
    async def get_runtime_attention(
        session: AsyncSession = Depends(get_db_session),
        service: ProductService = Depends(get_product_service),
    ) -> dict:
        return await service.get_recovery_inbox(session)

    @app.get("/api/runtime/builder-starter-pack")
    @app.get("/api/settings/builder-starter-pack")
    async def get_builder_starter_pack(
        session: AsyncSession = Depends(get_db_session),
        service: ProductService = Depends(get_product_service),
    ) -> dict:
        return await service.get_builder_starter_pack(session)

    @app.get("/api/runtime/builder-client-config/{client}")
    @app.get("/api/settings/builder-client-config/{client}")
    async def get_builder_client_config(
        client: str,
        session: AsyncSession = Depends(get_db_session),
        service: ProductService = Depends(get_product_service),
    ) -> dict:
        try:
            return await service.get_builder_client_config(client, session)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="unknown_builder_client") from exc

    @app.get("/api/runtime/builder-client-configs")
    @app.get("/api/settings/builder-client-configs")
    async def get_builder_client_configs(
        session: AsyncSession = Depends(get_db_session),
        service: ProductService = Depends(get_product_service),
    ) -> dict:
        return await service.get_builder_client_configs(session)

    @app.post("/api/watch-tasks")
    async def create_watch_task(
        payload: CreateWatchTaskRequest,
        session: AsyncSession = Depends(get_db_session),
        service: ProductService = Depends(get_product_service),
    ) -> dict[str, str]:
        try:
            task = await service.create_watch_task(session, **payload.model_dump())
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=_stable_client_error_detail(exc, "invalid_watch_task_request"),
            ) from exc
        return {"id": task.id}

    @app.get("/api/watch-tasks")
    async def list_watch_tasks(
        session: AsyncSession = Depends(get_db_session),
        service: ProductService = Depends(get_product_service),
    ) -> list[dict]:
        return await service.list_watch_tasks(session)

    @app.post("/api/watch-groups")
    async def create_watch_group(
        payload: CreateWatchGroupRequest,
        session: AsyncSession = Depends(get_db_session),
        service: ProductService = Depends(get_product_service),
    ) -> dict[str, str]:
        try:
            group = await service.create_watch_group(session, **payload.model_dump())
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=_stable_client_error_detail(exc, "invalid_watch_group_request"),
            ) from exc
        return {"id": group.id}

    @app.get("/api/watch-groups")
    async def list_watch_groups(
        session: AsyncSession = Depends(get_db_session),
        service: ProductService = Depends(get_product_service),
    ) -> list[dict]:
        return await service.list_watch_groups(session)

    @app.get("/api/watch-tasks/{task_id}")
    async def get_watch_task(
        task_id: str,
        session: AsyncSession = Depends(get_db_session),
        service: ProductService = Depends(get_product_service),
    ) -> dict:
        try:
            return await service.get_watch_task_detail(session, task_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=404,
                detail=_stable_client_error_detail(exc, "watch_task_not_found"),
            ) from exc

    @app.get("/api/watch-groups/{group_id}", response_model=WatchGroupDetailResponse)
    async def get_watch_group(
        group_id: str,
        session: AsyncSession = Depends(get_db_session),
        service: ProductService = Depends(get_product_service),
    ) -> dict:
        try:
            return await service.get_watch_group_detail(session, group_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=404,
                detail=_stable_client_error_detail(exc, "watch_group_not_found"),
            ) from exc

    @app.patch("/api/watch-tasks/{task_id}")
    async def update_watch_task(
        task_id: str,
        payload: UpdateWatchTaskRequest,
        session: AsyncSession = Depends(get_db_session),
        service: ProductService = Depends(get_product_service),
    ) -> dict[str, str]:
        try:
            task = await service.update_watch_task(session, task_id, **payload.model_dump(exclude_none=True))
        except ValueError as exc:
            raise HTTPException(
                status_code=404,
                detail=_stable_client_error_detail(exc, "watch_task_not_found"),
            ) from exc
        return {"id": task.id}

    @app.patch("/api/watch-groups/{group_id}")
    async def update_watch_group(
        group_id: str,
        payload: UpdateWatchGroupRequest,
        session: AsyncSession = Depends(get_db_session),
        service: ProductService = Depends(get_product_service),
    ) -> dict[str, str]:
        try:
            group = await service.update_watch_group(session, group_id, **payload.model_dump(exclude_none=True))
        except ValueError as exc:
            raise HTTPException(
                status_code=404,
                detail=_stable_client_error_detail(exc, "watch_group_not_found"),
            ) from exc
        return {"id": group.id}

    @app.post("/api/watch-tasks/{task_id}:run-now")
    async def run_now(
        task_id: str,
        session: AsyncSession = Depends(get_db_session),
        service: ProductService = Depends(get_product_service),
    ) -> dict[str, str]:
        try:
            run = await service.run_watch_task(session, task_id, triggered_by="manual")
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=_stable_client_error_detail(exc, "watch_task_run_failed"),
            ) from exc
        return {"id": run.id, "status": run.status}

    @app.post("/api/watch-groups/{group_id}:run-now")
    async def run_watch_group_now(
        group_id: str,
        session: AsyncSession = Depends(get_db_session),
        service: ProductService = Depends(get_product_service),
    ) -> dict[str, str]:
        try:
            run = await service.run_watch_group(session, group_id, triggered_by="manual")
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=_stable_client_error_detail(exc, "watch_group_run_failed"),
            ) from exc
        return {"id": run.id, "status": run.status}

    @app.get("/api/runs/{run_id}")
    async def get_run(run_id: str, session: AsyncSession = Depends(get_db_session)) -> dict:
        run = await session.scalar(select(TaskRun).where(TaskRun.id == run_id))
        if run is None:
            raise HTTPException(status_code=404, detail="run_not_found")
        return {
            "id": run.id,
            "status": run.status,
            "triggered_by": run.triggered_by,
            "error_code": run.error_code,
            "error_message": run.error_message,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "artifact_run_dir": run.artifact_run_dir,
        }

    @app.get("/api/notifications")
    async def list_notifications(
        session: AsyncSession = Depends(get_db_session),
        service: ProductService = Depends(get_product_service),
    ) -> list[dict]:
        return await service.list_notification_events(session)

    @app.get("/api/settings/notifications", response_model=NotificationSettingsResponse)
    async def get_notification_settings(
        session: AsyncSession = Depends(get_db_session),
        service: ProductService = Depends(get_product_service),
    ) -> dict:
        return await service.get_notification_settings(session)

    @app.get("/api/runtime-readiness")
    @app.get("/api/settings/runtime-readiness")
    async def get_runtime_readiness(
        session: AsyncSession = Depends(get_db_session),
        service: ProductService = Depends(get_product_service),
    ) -> dict:
        return await service.get_runtime_readiness(session)

    @app.patch("/api/settings/notifications", response_model=NotificationSettingsResponse)
    async def update_notification_settings(
        payload: UpdateNotificationSettingsRequest,
        session: AsyncSession = Depends(get_db_session),
        service: ProductService = Depends(get_product_service),
    ) -> dict:
        return await service.update_notification_settings(session, **payload.model_dump())

    @app.get("/api/settings/store-bindings", response_model=list[StoreBindingResponse])
    async def list_store_bindings(
        session: AsyncSession = Depends(get_db_session),
        service: ProductService = Depends(get_product_service),
    ) -> list[dict]:
        return await service.list_store_bindings(session)

    @app.get("/api/settings/store-onboarding-cockpit", response_model=StoreOnboardingCockpitResponse)
    @app.get("/api/store-onboarding-cockpit", response_model=StoreOnboardingCockpitResponse)
    async def get_store_onboarding_cockpit(
        session: AsyncSession = Depends(get_db_session),
        service: ProductService = Depends(get_product_service),
    ) -> dict:
        return await service.get_store_onboarding_cockpit(session)

    @app.patch("/api/settings/store-bindings/{store_key}", response_model=StoreBindingResponse)
    async def update_store_binding(
        store_key: str,
        payload: UpdateStoreBindingRequest,
        session: AsyncSession = Depends(get_db_session),
        service: ProductService = Depends(get_product_service),
    ) -> dict:
        try:
            return await service.update_store_binding(session, store_key=store_key, enabled=payload.enabled)
        except ValueError as exc:
            raise HTTPException(
                status_code=404,
                detail=_stable_client_error_detail(exc, "store_binding_not_found"),
            ) from exc

    @app.post("/api/compare/preview", response_model=ComparePreviewResponse)
    async def compare_products(
        payload: CompareProductsRequest,
        session: AsyncSession = Depends(get_db_session),
        service: ProductService = Depends(get_product_service),
    ) -> dict:
        try:
            return await service.compare_product_urls(
                submitted_urls=payload.submitted_urls,
                zip_code=payload.zip_code,
                session=session,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=_stable_client_error_detail(exc, "compare_preview_failed"),
            ) from exc

    @app.post("/api/compare/evidence-packages")
    async def create_compare_evidence_package(
        payload: CompareEvidencePackageCreateRequest,
        service: ProductService = Depends(get_product_service),
        session: AsyncSession = Depends(get_db_session),
    ) -> dict:
        try:
            return await service.create_compare_evidence_package(
                submitted_urls=payload.submitted_urls,
                zip_code=payload.zip_code,
                compare_result=payload.compare_result,
                session=session,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=_stable_client_error_detail(exc, "compare_evidence_package_invalid"),
            ) from exc

    @app.post("/api/compare/evidence")
    async def create_compare_evidence_artifact(
        payload: CompareProductsRequest,
        session: AsyncSession = Depends(get_db_session),
        service: ProductService = Depends(get_product_service),
    ) -> dict:
        try:
            return await service.create_compare_evidence_artifact(
                session,
                submitted_urls=payload.submitted_urls,
                zip_code=payload.zip_code,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=_stable_client_error_detail(exc, "compare_evidence_invalid"),
            ) from exc

    @app.get("/api/compare/evidence-packages")
    async def list_compare_evidence_packages(
        service: ProductService = Depends(get_product_service),
    ) -> dict:
        return await service.list_compare_evidence_packages()

    @app.get("/api/compare/evidence")
    async def list_compare_evidence_artifacts(
        session: AsyncSession = Depends(get_db_session),
        service: ProductService = Depends(get_product_service),
    ) -> list[dict]:
        return await service.list_compare_evidence_artifacts(session)

    @app.get("/api/compare/evidence-packages/{package_id}")
    async def get_compare_evidence_package(
        package_id: str,
        service: ProductService = Depends(get_product_service),
    ) -> dict:
        try:
            return await service.get_compare_evidence_package(package_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=404,
                detail=_stable_client_error_detail(exc, "compare_evidence_package_not_found"),
            ) from exc

    @app.get("/api/compare/evidence/{package_id}")
    async def get_compare_evidence_artifact(
        package_id: str,
        session: AsyncSession = Depends(get_db_session),
        service: ProductService = Depends(get_product_service),
    ) -> dict:
        try:
            return await service.get_compare_evidence_artifact(session, package_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=404,
                detail=_stable_client_error_detail(exc, "compare_evidence_not_found"),
            ) from exc

    @app.get("/api/compare/evidence-packages/{package_id}/html", response_class=HTMLResponse)
    async def get_compare_evidence_package_html(
        package_id: str,
        service: ProductService = Depends(get_product_service),
    ) -> str:
        try:
            return await service.get_compare_evidence_package_html(package_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=404,
                detail=_stable_client_error_detail(exc, "compare_evidence_package_not_found"),
            ) from exc

    @app.get("/api/compare/evidence/{package_id}/html", response_class=HTMLResponse)
    async def get_compare_evidence_artifact_html(
        package_id: str,
        service: ProductService = Depends(get_product_service),
    ) -> str:
        try:
            return await service.get_compare_evidence_package_html(package_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=404,
                detail=_stable_client_error_detail(exc, "compare_evidence_not_found"),
            ) from exc

    @app.get("/api/recovery-inbox", response_model=RecoveryInboxResponse)
    @app.get("/api/recovery/inbox", response_model=RecoveryInboxResponse)
    async def get_recovery_inbox(
        session: AsyncSession = Depends(get_db_session),
        service: ProductService = Depends(get_product_service),
    ) -> dict:
        return await service.get_recovery_inbox(session)

    @app.post("/api/webhooks/postmark")
    async def postmark_webhook(
        request: Request,
        session: AsyncSession = Depends(get_db_session),
    ) -> dict[str, str]:
        configured_token = settings.POSTMARK_WEBHOOK_TOKEN
        if hasattr(configured_token, "get_secret_value"):
            expected_token = configured_token.get_secret_value().strip()
        else:
            expected_token = str(configured_token).strip()
        if not expected_token:
            raise HTTPException(status_code=503, detail="postmark_webhook_not_configured")
        provided_token = request.headers.get("X-DealWatch-Webhook-Token", "").strip()
        if not provided_token or not compare_digest(provided_token, expected_token):
            raise HTTPException(status_code=401, detail="invalid_postmark_webhook_signature")

        payload = await request.json()
        message_id = str(payload.get("MessageID") or "").strip()
        record_type = str(payload.get("RecordType") or "").strip().lower()
        if not message_id or not record_type:
            raise HTTPException(status_code=400, detail="invalid_postmark_webhook")

        event = await session.scalar(
            select(DeliveryEvent)
            .where(DeliveryEvent.provider_message_id == message_id)
            .order_by(desc(DeliveryEvent.created_at))
            .limit(1)
        )
        if event is None:
            raise HTTPException(status_code=404, detail="delivery_event_not_found")

        if record_type == "delivery":
            event.status = DeliveryStatus.DELIVERED.value
            event.delivered_at = datetime.now(timezone.utc)
        elif record_type == "bounce":
            event.status = DeliveryStatus.BOUNCED.value
            event.bounced_at = datetime.now(timezone.utc)
        else:
            raise HTTPException(status_code=400, detail="unsupported_postmark_record_type")
        event.provider_payload_json = payload
        await session.flush()
        return {"status": "ok"}

    return app


def _build_allowed_origins(*origins: str) -> list[str]:
    allowed: set[str] = set()
    for origin in origins:
        normalized = origin.rstrip("/")
        if not normalized:
            continue
        allowed.add(normalized)
        parsed = urlsplit(normalized)
        hostname = parsed.hostname
        if hostname not in _LOOPBACK_HOST_ALIASES:
            continue
        for alias in _LOOPBACK_HOST_ALIASES:
            if alias == hostname:
                continue
            netloc = alias
            if parsed.port is not None:
                netloc = f"{alias}:{parsed.port}"
            allowed.add(urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment)).rstrip("/"))
    return sorted(allowed)
