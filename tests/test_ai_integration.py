from __future__ import annotations

import json

import pytest

from dealwatch.application.ai_integration import AiNarrativeService
from dealwatch.infra.config import Settings


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict) -> None:
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import httpx

            request = httpx.Request("POST", "https://switchyard.local")
            response = httpx.Response(self.status_code, request=request, json=self._payload)
            raise httpx.HTTPStatusError("error", request=request, response=response)

    def json(self) -> dict:
        return self._payload


class _FakeAsyncClient:
    def __init__(self, responses: list[_FakeResponse], bucket: dict[str, object], **_kwargs) -> None:
        self._responses = responses
        self._bucket = bucket

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def post(self, url: str, json: dict) -> _FakeResponse:
        self._bucket["url"] = url
        self._bucket["json"] = json
        return self._responses.pop(0)


def _make_settings() -> Settings:
    settings = Settings(_env_file=None)
    settings.USE_LLM = True
    settings.AI_PROVIDER = "switchyard_service"
    settings.AI_BASE_URL = "http://127.0.0.1:4317"
    settings.AI_SWITCHYARD_PROVIDER = "gemini"
    settings.AI_SWITCHYARD_LANE = "byok"
    settings.AI_MODEL = "gemini-2.5-flash"
    return settings


@pytest.mark.asyncio
async def test_switchyard_service_provider_byok_success(monkeypatch) -> None:
    captured: dict[str, object] = {}
    payload = {
        "text": json.dumps(
            {
                "title": "AI summary",
                "summary": "Structured summary",
                "bullets": ["one"],
                "sections": [{"title": "Evidence", "bullets": ["anchor"]}],
                "uncertainty_notes": [],
            }
        )
    }
    monkeypatch.setattr(
        "dealwatch.application.ai_integration.httpx.AsyncClient",
        lambda **kwargs: _FakeAsyncClient([_FakeResponse(200, payload)], captured, **kwargs),
    )
    settings = _make_settings()
    service = AiNarrativeService(settings=settings)

    result = await service.build(
        enabled=True,
        label="AI Compare Explainer",
        title="Should these candidates stay together?",
        summary="Compare summary",
        bullets=["Compare summary"],
        evidence_refs=[{"code": "reason", "label": "Reason", "anchor": "anchor"}],
        caution_notes=["risk"],
    )

    assert result["status"] == "ok"
    assert captured["url"] == "http://127.0.0.1:4317/v1/runtime/byok/invoke"
    assert captured["json"]["provider"] == "gemini"
    assert captured["json"]["model"] == "gemini-2.5-flash"


@pytest.mark.asyncio
async def test_switchyard_service_provider_user_action_required_degrades(monkeypatch) -> None:
    captured: dict[str, object] = {}
    error_payload = {
        "error": {
            "type": "missing-credential",
            "message": "No credential is available for the requested provider.",
        }
    }
    monkeypatch.setattr(
        "dealwatch.application.ai_integration.httpx.AsyncClient",
        lambda **kwargs: _FakeAsyncClient([_FakeResponse(409, error_payload)], captured, **kwargs),
    )
    settings = _make_settings()
    service = AiNarrativeService(settings=settings)

    result = await service.build(
        enabled=True,
        label="AI Compare Explainer",
        title="Should these candidates stay together?",
        summary="Compare summary",
        bullets=["Compare summary"],
        evidence_refs=[{"code": "reason", "label": "Reason", "anchor": "anchor"}],
        caution_notes=["risk"],
    )

    assert result["status"] == "unavailable"
    assert "Switchyard runtime" in result["summary"]

