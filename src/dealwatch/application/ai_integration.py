from __future__ import annotations

import json
from dataclasses import dataclass, field
import logging
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from dealwatch.infra.config import Settings


@dataclass(slots=True, frozen=True)
class AiNarrativeRequest:
    label: str
    title: str
    summary: str
    bullets: list[str]
    evidence_refs: list[dict[str, Any]]
    caution_notes: list[str]


class _AiSectionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=120)
    bullets: list[str] = Field(default_factory=list, max_length=4)


class _AiNarrativeModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=160)
    summary: str = Field(min_length=1, max_length=600)
    bullets: list[str] = Field(default_factory=list, max_length=4)
    sections: list[_AiSectionModel] = Field(default_factory=list, max_length=3)
    uncertainty_notes: list[str] = Field(default_factory=list, max_length=4)


@dataclass(slots=True, frozen=True)
class AiNarrativeDraft:
    title: str
    summary: str
    bullets: list[str] = field(default_factory=list)
    sections: list[dict[str, Any]] = field(default_factory=list)
    uncertainty_notes: list[str] = field(default_factory=list)


class AiNarrativeProvider(Protocol):
    provider_name: str
    model_name: str | None

    async def generate(self, request: AiNarrativeRequest) -> AiNarrativeDraft:
        ...


@dataclass(slots=True)
class FakeAiNarrativeProvider:
    model_name: str
    provider_name: str = "fake"

    async def generate(self, request: AiNarrativeRequest) -> AiNarrativeDraft:
        evidence_lines = [
            f"{item.get('label')}: {item.get('code') or item.get('anchor') or 'anchor'}"
            for item in request.evidence_refs[:4]
        ]
        sections: list[dict[str, Any]] = []
        if evidence_lines:
            sections.append(
                {
                    "title": "Evidence anchors",
                    "bullets": evidence_lines,
                }
            )
        if request.caution_notes:
            sections.append(
                {
                    "title": "Caution notes",
                    "bullets": list(request.caution_notes[:4]),
                }
            )
        return AiNarrativeDraft(
            title=request.title,
            summary=f"{request.summary} This local fake provider mirrors deterministic product truth without changing it.",
            bullets=list(request.bullets[:4]) or [request.summary],
            sections=sections,
            uncertainty_notes=[
                "Local fake provider output is deterministic and intended for contract and test coverage only."
            ],
        )


class AiProviderError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(slots=True)
class SwitchyardServiceNarrativeProvider:
    settings: Settings
    provider_name: str = "switchyard_service"
    model_name: str | None = None

    def __post_init__(self) -> None:
        if self.model_name is None:
            configured = str(self.settings.AI_MODEL or "").strip()
            self.model_name = configured or None

    async def generate(self, request: AiNarrativeRequest) -> AiNarrativeDraft:
        base_url = str(self.settings.AI_BASE_URL or "").strip().rstrip("/")
        if not base_url:
            raise AiProviderError("misconfigured", "AI_BASE_URL is empty.")

        provider_name = str(self.settings.AI_SWITCHYARD_PROVIDER or "").strip()
        if not provider_name:
            raise AiProviderError("misconfigured", "AI_SWITCHYARD_PROVIDER is empty.")

        model_name = str(self.model_name or "").strip()
        if not model_name:
            raise AiProviderError("misconfigured", "AI_MODEL is empty.")

        lane = str(self.settings.AI_SWITCHYARD_LANE or "").strip().lower() or "byok"
        if lane not in {"byok", "web"}:
            raise AiProviderError("misconfigured", "AI_SWITCHYARD_LANE must be either 'byok' or 'web'.")

        payload = {
            "provider": provider_name,
            "model": model_name,
            "input": json.dumps(
                {
                    "label": request.label,
                    "title": request.title,
                    "summary": request.summary,
                    "bullets": request.bullets,
                    "evidence_refs": request.evidence_refs,
                    "caution_notes": request.caution_notes,
                },
                ensure_ascii=False,
            ),
            "system": (
                "You are DealWatch's AI explanation layer.\n"
                "Hard rules:\n"
                "1) Never change deterministic product truth.\n"
                "2) Never invent prices, winners, health states, or missing evidence.\n"
                "3) Treat evidence_refs and caution_notes as the authoritative anchors.\n"
                "4) Use uncertainty_notes when the evidence is incomplete or risky.\n"
                "5) Output JSON only and follow the provided schema exactly.\n"
            ),
            "maxOutputTokens": 800,
            "temperature": 0.2,
        }
        if lane == "web":
            payload["lane"] = "web"
            endpoint = f"{base_url}/v1/runtime/invoke"
        else:
            endpoint = f"{base_url}/v1/runtime/byok/invoke"

        timeout_seconds = max(float(self.settings.AI_TIMEOUT_SECONDS), 1.0)
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.post(endpoint, json=payload)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise AiProviderError("timeout", "The Switchyard service timed out.") from exc
        except httpx.HTTPStatusError as exc:
            try:
                response_payload = exc.response.json()
            except json.JSONDecodeError:
                response_payload = {}
            error_payload = dict(response_payload.get("error") or {})
            error_type = str(error_payload.get("type") or "")
            error_message = str(error_payload.get("message") or "The Switchyard service returned an unexpected error.")
            if exc.response.status_code == 400:
                raise AiProviderError("misconfigured", error_message) from exc
            if exc.response.status_code == 409 and error_type in {
                "missing-credential",
                "session-incomplete",
                "user-action-required",
            }:
                raise AiProviderError("user_action_required", error_message) from exc
            if exc.response.status_code >= 500:
                raise AiProviderError("overloaded", error_message) from exc
            raise AiProviderError("provider_error", error_message) from exc
        except httpx.HTTPError as exc:
            raise AiProviderError("unavailable", "The Switchyard service is currently unreachable.") from exc

        try:
            response_payload = response.json()
        except json.JSONDecodeError as exc:
            raise AiProviderError("invalid_response", "The Switchyard service did not return valid JSON.") from exc

        raw_content = self._extract_content(response_payload)
        if not raw_content:
            raise AiProviderError("invalid_response", "The Switchyard service returned empty content.")

        try:
            narrative = _AiNarrativeModel.model_validate_json(raw_content)
        except ValidationError:
            try:
                parsed = json.loads(raw_content)
            except json.JSONDecodeError as exc:
                raise AiProviderError("invalid_response", "The Switchyard service returned invalid structured content.") from exc
            try:
                narrative = _AiNarrativeModel.model_validate(parsed)
            except ValidationError as exc:
                raise AiProviderError("invalid_response", "The Switchyard service returned schema-invalid content.") from exc

        return AiNarrativeDraft(
            title=narrative.title,
            summary=narrative.summary,
            bullets=list(narrative.bullets),
            sections=[section.model_dump() for section in narrative.sections],
            uncertainty_notes=list(narrative.uncertainty_notes),
        )

    @staticmethod
    def _extract_content(response_payload: dict[str, Any]) -> str:
        text = response_payload.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()
        output = response_payload.get("output")
        if isinstance(output, str) and output.strip():
            return output.strip()
        return ""


@dataclass(slots=True)
class OpenAiCompatibleNarrativeProvider:
    settings: Settings
    provider_name: str = "openai_compatible"
    model_name: str | None = None

    def __post_init__(self) -> None:
        if self.model_name is None:
            configured = str(self.settings.AI_MODEL or "").strip()
            self.model_name = configured or None

    async def generate(self, request: AiNarrativeRequest) -> AiNarrativeDraft:
        api_key = self.settings.LLM_API_KEY.get_secret_value().strip()
        if not api_key:
            raise AiProviderError("misconfigured", "LLM_API_KEY is empty.")

        base_url = str(self.settings.AI_BASE_URL or "").strip().rstrip("/")
        if not base_url:
            raise AiProviderError("misconfigured", "AI_BASE_URL is empty.")

        model_name = str(self.model_name or "").strip()
        if not model_name:
            raise AiProviderError("misconfigured", "AI_MODEL is empty.")

        request_payload = {
            "model": model_name,
            "temperature": 0.2,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are DealWatch's AI explanation layer.\n"
                        "Hard rules:\n"
                        "1) Never change deterministic product truth.\n"
                        "2) Never invent prices, winners, health states, or missing evidence.\n"
                        "3) Treat evidence_refs and caution_notes as the authoritative anchors.\n"
                        "4) Use uncertainty_notes when the evidence is incomplete or risky.\n"
                        "5) Output JSON only and follow the provided schema exactly.\n"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "label": request.label,
                            "title": request.title,
                            "summary": request.summary,
                            "bullets": request.bullets,
                            "evidence_refs": request.evidence_refs,
                            "caution_notes": request.caution_notes,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "dealwatch_ai_narrative",
                    "strict": True,
                    "schema": _AiNarrativeModel.model_json_schema(),
                },
            },
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        timeout_seconds = max(float(self.settings.AI_TIMEOUT_SECONDS), 1.0)
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=request_payload,
                )
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise AiProviderError("timeout", "The AI provider timed out.") from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code in (401, 403):
                raise AiProviderError("misconfigured", "The AI provider rejected the configured credentials.") from exc
            if status_code == 404:
                raise AiProviderError("deprecated_model", "The configured AI model or endpoint is unavailable.") from exc
            if status_code == 429:
                raise AiProviderError("rate_limited", "The AI provider is currently rate limited.") from exc
            if status_code >= 500:
                raise AiProviderError("overloaded", "The AI provider is temporarily overloaded.") from exc
            raise AiProviderError("provider_error", "The AI provider returned an unexpected error.") from exc
        except httpx.HTTPError as exc:
            raise AiProviderError("unavailable", "The AI provider is currently unreachable.") from exc

        try:
            response_payload = response.json()
        except json.JSONDecodeError as exc:
            raise AiProviderError("invalid_response", "The AI provider did not return valid JSON.") from exc

        raw_content = self._extract_content(response_payload)
        if not raw_content:
            raise AiProviderError("invalid_response", "The AI provider returned empty content.")

        try:
            narrative = _AiNarrativeModel.model_validate_json(raw_content)
        except ValidationError:
            try:
                parsed = json.loads(raw_content)
            except json.JSONDecodeError as exc:
                raise AiProviderError("invalid_response", "The AI provider returned invalid structured content.") from exc
            try:
                narrative = _AiNarrativeModel.model_validate(parsed)
            except ValidationError as exc:
                raise AiProviderError("invalid_response", "The AI provider returned schema-invalid content.") from exc

        return AiNarrativeDraft(
            title=narrative.title,
            summary=narrative.summary,
            bullets=list(narrative.bullets),
            sections=[section.model_dump() for section in narrative.sections],
            uncertainty_notes=list(narrative.uncertainty_notes),
        )

    @staticmethod
    def _extract_content(response_payload: dict[str, Any]) -> str:
        choices = response_payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if not isinstance(message, dict):
            return ""
        content = message.get("content")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            chunks: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str) and text.strip():
                        chunks.append(text.strip())
            return "\n".join(chunks).strip()
        return ""


@dataclass(slots=True)
class AiNarrativeService:
    settings: Settings
    provider: AiNarrativeProvider | None = None
    logger: logging.Logger = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.logger = logging.getLogger(__name__)

    async def build(
        self,
        *,
        enabled: bool,
        label: str,
        title: str,
        summary: str,
        bullets: list[str],
        evidence_refs: list[dict[str, Any]],
        caution_notes: list[str],
        skip_reason: str | None = None,
    ) -> dict[str, Any]:
        provider_metadata = self._provider_metadata()
        fallback_bullets = list(bullets[:4]) or [summary]
        if not enabled or not self.settings.USE_LLM:
            return self._build_envelope(
                status="disabled",
                label=label,
                title=title,
                summary=f"{label} is disabled, so the deterministic product truth remains the only guide.",
                bullets=fallback_bullets,
                evidence_refs=evidence_refs,
                caution_notes=caution_notes,
                uncertainty_notes=[],
                provider_metadata=provider_metadata,
            )
        if skip_reason is not None:
            return self._build_envelope(
                status="skipped",
                label=label,
                title=title,
                summary=summary,
                bullets=fallback_bullets,
                evidence_refs=evidence_refs,
                caution_notes=caution_notes,
                uncertainty_notes=[skip_reason],
                provider_metadata=provider_metadata,
            )

        provider = self.provider or self._build_provider()
        if provider is None:
            return self._build_envelope(
                status="unavailable",
                label=label,
                title=title,
                summary=f"{label} is enabled in the contract, but no usable provider is configured for this runtime.",
                bullets=fallback_bullets,
                evidence_refs=evidence_refs,
                caution_notes=caution_notes,
                uncertainty_notes=[
                    "Configure AI_PROVIDER=fake for deterministic local coverage, or wire a real provider later."
                ],
                provider_metadata=provider_metadata,
            )

        request = AiNarrativeRequest(
            label=label,
            title=title,
            summary=summary,
            bullets=fallback_bullets,
            evidence_refs=evidence_refs,
            caution_notes=list(caution_notes[:4]),
        )
        try:
            draft = await provider.generate(request)
        except AiProviderError as exc:
            self.logger.warning("AI narrative generation degraded for %s: %s", label, exc.code)
            return self._build_envelope(
                status="unavailable",
                label=label,
                title=title,
                summary=self._provider_error_summary(label, exc.code),
                bullets=fallback_bullets,
                evidence_refs=evidence_refs,
                caution_notes=caution_notes,
                uncertainty_notes=[exc.message],
                provider_metadata=self._provider_metadata(provider),
            )
        except Exception:
            self.logger.exception("AI narrative generation failed for %s", label)
            return self._build_envelope(
                status="error",
                label=label,
                title=title,
                summary=f"{label} failed, so deterministic product truth remains authoritative.",
                bullets=fallback_bullets,
                evidence_refs=evidence_refs,
                caution_notes=caution_notes,
                uncertainty_notes=["AI generation failed and was downgraded to a non-blocking fallback envelope."],
                provider_metadata=self._provider_metadata(provider),
            )

        return self._build_envelope(
            status="ok",
            label=label,
            title=draft.title,
            summary=draft.summary,
            bullets=draft.bullets or fallback_bullets,
            sections=draft.sections,
            evidence_refs=evidence_refs,
            caution_notes=caution_notes,
            uncertainty_notes=draft.uncertainty_notes,
            provider_metadata=self._provider_metadata(provider),
        )

    def _build_provider(self) -> AiNarrativeProvider | None:
        provider_name = str(self.settings.AI_PROVIDER or "").strip().lower()
        if provider_name in {"", "disabled", "none"}:
            return None
        if provider_name == "fake":
            model_name = str(self.settings.AI_MODEL or "").strip() or "dealwatch-fake-explainer-v1"
            return FakeAiNarrativeProvider(model_name=model_name)
        if provider_name == "switchyard_service":
            model_name = str(self.settings.AI_MODEL or "").strip() or None
            return SwitchyardServiceNarrativeProvider(settings=self.settings, model_name=model_name)
        if provider_name in {"openai", "openai_compatible"}:
            model_name = str(self.settings.AI_MODEL or "").strip() or "gpt-4.1-mini"
            return OpenAiCompatibleNarrativeProvider(
                settings=self.settings,
                provider_name=provider_name,
                model_name=model_name,
            )
        return None

    def _provider_metadata(self, provider: AiNarrativeProvider | None = None) -> dict[str, Any]:
        resolved = provider or self.provider or self._build_provider()
        configured_provider = str(self.settings.AI_PROVIDER or "").strip() or "disabled"
        configured_model = str(self.settings.AI_MODEL or "").strip() or None
        return {
            "provider": getattr(resolved, "provider_name", configured_provider),
            "model": getattr(resolved, "model_name", configured_model),
            "timeout_seconds": float(self.settings.AI_TIMEOUT_SECONDS),
        }

    @staticmethod
    def _provider_error_summary(label: str, code: str) -> str:
        if code == "misconfigured":
            return f"{label} is unavailable because the provider credentials or model configuration are invalid."
        if code == "deprecated_model":
            return f"{label} is unavailable because the configured model or endpoint cannot be found."
        if code == "rate_limited":
            return f"{label} is temporarily rate limited. Deterministic product truth still remains authoritative."
        if code == "overloaded":
            return f"{label} is temporarily overloaded. Deterministic product truth still remains authoritative."
        if code == "user_action_required":
            return f"{label} is blocked until the Switchyard runtime has a usable credential or session for the requested lane."
        if code == "timeout":
            return f"{label} timed out. Deterministic product truth still remains authoritative."
        if code == "unavailable":
            return f"{label} is temporarily unreachable. Deterministic product truth still remains authoritative."
        return f"{label} is unavailable right now, so deterministic product truth remains authoritative."

    @staticmethod
    def _build_envelope(
        *,
        status: str,
        label: str,
        title: str,
        summary: str,
        bullets: list[str],
        evidence_refs: list[dict[str, Any]],
        caution_notes: list[str],
        uncertainty_notes: list[str],
        provider_metadata: dict[str, Any],
        sections: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return {
            "status": status,
            "label": label,
            "title": title,
            "summary": summary,
            "bullets": list(bullets[:4]),
            "sections": list(sections or []),
            "evidence_refs": list(evidence_refs[:6]),
            "caution_notes": list(caution_notes[:4]),
            "uncertainty_notes": list(uncertainty_notes[:4]),
            "provider": provider_metadata,
        }
