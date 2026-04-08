from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CompareHandoffRequest(BaseModel):
    title_snapshot: str = Field(min_length=1)
    store_key: str = Field(min_length=1, max_length=64)
    candidate_key: str = Field(min_length=1)
    brand_hint: str | None = None
    size_hint: str | None = None


class CreateWatchTaskRequest(BaseModel):
    submitted_url: str
    zip_code: str = Field(default="00000", min_length=3, max_length=32)
    cadence_minutes: int = Field(default=720, ge=5, le=10080)
    threshold_type: str = "price_below"
    threshold_value: float = Field(default=0.0, ge=0.0)
    cooldown_minutes: int = Field(default=240, ge=0, le=10080)
    recipient_email: EmailStr
    compare_handoff: CompareHandoffRequest | None = None


class CreateWatchGroupCandidateRequest(BaseModel):
    submitted_url: str
    title_snapshot: str = Field(min_length=1)
    store_key: str = Field(min_length=1, max_length=64)
    candidate_key: str = Field(min_length=1)
    brand_hint: str | None = None
    size_hint: str | None = None
    similarity_score: float = Field(default=100.0, ge=0.0, le=100.0)


class CreateWatchGroupRequest(BaseModel):
    title: str | None = None
    zip_code: str = Field(default="00000", min_length=3, max_length=32)
    cadence_minutes: int = Field(default=720, ge=5, le=10080)
    threshold_type: str = "effective_price_below"
    threshold_value: float = Field(default=0.0, ge=0.0)
    cooldown_minutes: int = Field(default=240, ge=0, le=10080)
    recipient_email: EmailStr
    notifications_enabled: bool = True
    candidates: list[CreateWatchGroupCandidateRequest] = Field(min_length=2, max_length=10)


class UpdateWatchTaskRequest(BaseModel):
    status: str | None = None
    zip_code: str | None = Field(default=None, min_length=3, max_length=32)
    cadence_minutes: int | None = Field(default=None, ge=5, le=10080)
    threshold_type: str | None = None
    threshold_value: float | None = Field(default=None, ge=0.0)
    cooldown_minutes: int | None = Field(default=None, ge=0, le=10080)
    recipient_email: EmailStr | None = None


class UpdateWatchGroupRequest(BaseModel):
    title: str | None = None
    status: str | None = None
    zip_code: str | None = Field(default=None, min_length=3, max_length=32)
    cadence_minutes: int | None = Field(default=None, ge=5, le=10080)
    threshold_type: str | None = None
    threshold_value: float | None = Field(default=None, ge=0.0)
    cooldown_minutes: int | None = Field(default=None, ge=0, le=10080)
    recipient_email: EmailStr | None = None
    notifications_enabled: bool | None = None


class NotificationSettingsResponse(BaseModel):
    default_recipient_email: EmailStr
    cooldown_minutes: int = Field(ge=0, le=10080)
    notifications_enabled: bool


class UpdateNotificationSettingsRequest(BaseModel):
    default_recipient_email: EmailStr
    cooldown_minutes: int = Field(ge=0, le=10080)
    notifications_enabled: bool = True


class StoreBindingResponse(BaseModel):
    store_key: str
    enabled: bool
    adapter_class: str
    support_channel: str
    support_tier: str
    support_reason_codes: list[str] = Field(default_factory=list)
    next_step_codes: list[str] = Field(default_factory=list)
    contract_test_paths: list[str] = Field(default_factory=list)
    discovery_mode: str
    parse_mode: str
    region_sensitive: bool
    cashback_supported: bool
    supports_compare_intake: bool
    supports_watch_task: bool
    supports_watch_group: bool
    supports_recovery: bool


class UpdateStoreBindingRequest(BaseModel):
    enabled: bool


class StoreOnboardingRequiredFileResponse(BaseModel):
    kind: str
    path: str | None = None
    path_template: str | None = None
    exists: bool | None = None
    exists_for_all_supported_stores: bool | None = None
    missing_store_keys: list[str] = Field(default_factory=list)


class StoreOnboardingStoreResponse(BaseModel):
    store_key: str
    enabled: bool
    binding_present: bool
    registered: bool
    capability_declared: bool
    support_channel: str | None = None
    adapter_class: str | None = None
    adapter_module: str | None = None
    adapter_file_path: str | None = None
    adapter_file_exists: bool
    support_tier: str | None = None
    default_enabled: bool | None = None
    support_reason_codes: list[str] = Field(default_factory=list)
    support_summary: str | None = None
    next_step_codes: list[str] = Field(default_factory=list)
    next_onboarding_step: str | None = None
    runtime_binding_summary: str | None = None
    discovery_mode: str | None = None
    parse_mode: str | None = None
    region_sensitive: bool | None = None
    cashback_supported: bool | None = None
    supports_compare_intake: bool | None = None
    supports_watch_task: bool | None = None
    supports_watch_group: bool | None = None
    supports_recovery: bool | None = None
    contract_test_reference_present: bool
    manifest_store_id_matches: bool
    missing_capabilities: list[str] = Field(default_factory=list)
    contract_gaps: list[str] = Field(default_factory=list)
    contract_test_paths: list[str] = Field(default_factory=list)
    source_of_truth_files: list[str] = Field(default_factory=list)
    required_files: list[StoreOnboardingRequiredFileResponse] = Field(default_factory=list)


class StoreOnboardingSummaryResponse(BaseModel):
    supported_store_count: int = Field(ge=0)
    official_full_count: int = Field(ge=0)
    official_partial_count: int = Field(ge=0)
    official_in_progress_count: int = Field(ge=0)
    default_enabled_store_count: int = Field(ge=0)
    enabled_store_count: int = Field(ge=0)
    disabled_store_count: int = Field(ge=0)
    compare_intake_supported_count: int = Field(ge=0)
    cashback_supported_count: int = Field(ge=0)
    watch_task_supported_count: int = Field(ge=0)
    watch_group_supported_count: int = Field(ge=0)
    recovery_supported_count: int = Field(ge=0)
    region_sensitive_count: int = Field(ge=0)


class StoreOnboardingConsistencyResponse(BaseModel):
    registry_matches_capability_registry: bool
    missing_in_registry: list[str] = Field(default_factory=list)
    missing_in_capability_registry: list[str] = Field(default_factory=list)
    store_id_mismatches: list[str] = Field(default_factory=list)


class StoreOnboardingRegistryHealthResponse(BaseModel):
    registry_store_count: int = Field(ge=0)
    capability_store_count: int = Field(ge=0)
    binding_store_count: int = Field(ge=0)
    registry_parity_ok: bool
    registry_only_store_keys: list[str] = Field(default_factory=list)
    manifest_only_store_keys: list[str] = Field(default_factory=list)
    binding_only_store_keys: list[str] = Field(default_factory=list)


class StoreOnboardingContractResponse(BaseModel):
    source_runbook_path: str
    checklist: list[str] = Field(default_factory=list)
    required_files: list[StoreOnboardingRequiredFileResponse] = Field(default_factory=list)
    verification_commands: list[str] = Field(default_factory=list)
    rollout_rule: list[str] = Field(default_factory=list)
    official_support_tiers: list[str] = Field(default_factory=list)
    runtime_binding_truth: list[str] = Field(default_factory=list)
    limited_support_contract: list[str] = Field(default_factory=list)


class StoreOnboardingChecklistItemResponse(BaseModel):
    key: str
    label: str
    detail: str


class StoreOnboardingLimitedSupportLaneResponse(BaseModel):
    support_channel: str
    support_tier: str
    summary: str
    supported_actions: list[str] = Field(default_factory=list)
    blocked_actions: list[str] = Field(default_factory=list)
    contract_lines: list[str] = Field(default_factory=list)
    source_of_truth_files: list[str] = Field(default_factory=list)


class ComparePreviewOfferContextResponse(BaseModel):
    region: str
    currency: str
    is_member: bool


class ComparePreviewOfferResponse(BaseModel):
    store_id: str
    product_key: str
    deal_id: str
    title: str
    url: str
    price: float
    original_price: float | None = None
    fetch_at: str
    context: ComparePreviewOfferContextResponse
    unit_price_info: dict[str, Any] = Field(default_factory=dict)


class ComparePreviewSupportContractResponse(BaseModel):
    support_channel: str
    store_support_tier: str
    support_reason_codes: list[str] = Field(default_factory=list)
    next_step_codes: list[str] = Field(default_factory=list)
    intake_status: str
    summary: str
    next_step: str
    can_save_compare_evidence: bool
    can_create_watch_task: bool
    can_create_watch_group: bool
    cashback_supported: bool
    notifications_supported: bool
    missing_capabilities: list[str] = Field(default_factory=list)


class ComparePreviewComparisonResponse(BaseModel):
    submitted_url: str
    supported: bool
    store_key: str | None = None
    normalized_url: str | None = None
    fetch_succeeded: bool | None = None
    error_code: str | None = None
    candidate_key: str | None = None
    brand_hint: str | None = None
    size_hint: str | None = None
    offer: ComparePreviewOfferResponse | None = None
    support_contract: ComparePreviewSupportContractResponse


class ComparePreviewMatchResponse(BaseModel):
    left_store_key: str
    left_product_key: str
    right_store_key: str
    right_product_key: str
    score: float
    title_similarity: float | None = None
    brand_signal: str | None = None
    size_signal: str | None = None
    product_key_signal: str | None = None
    left_candidate_key: str | None = None
    right_candidate_key: str | None = None
    why_like: list[str] = Field(default_factory=list)
    why_unlike: list[str] = Field(default_factory=list)


class StoreOnboardingCockpitResponse(BaseModel):
    generated_at: str
    summary: StoreOnboardingSummaryResponse
    consistency: StoreOnboardingConsistencyResponse
    registry_health: StoreOnboardingRegistryHealthResponse
    capability_matrix: list[StoreOnboardingStoreResponse] = Field(default_factory=list)
    stores: list[StoreOnboardingStoreResponse] = Field(default_factory=list)
    onboarding_checklist: list[StoreOnboardingChecklistItemResponse] = Field(default_factory=list)
    verification_commands: list[str] = Field(default_factory=list)
    truth_sources: list[str] = Field(default_factory=list)
    limited_support_lane: StoreOnboardingLimitedSupportLaneResponse
    onboarding_contract: StoreOnboardingContractResponse


class CompareProductsRequest(BaseModel):
    submitted_urls: list[str] = Field(min_length=2, max_length=10)
    zip_code: str = "00000"


class CompareEvidencePackageCreateRequest(BaseModel):
    submitted_urls: list[str] = Field(min_length=2, max_length=10)
    zip_code: str = Field(default="00000", min_length=3, max_length=32)
    compare_result: dict[str, Any] | None = None


class AiNarrativeEvidenceRefResponse(BaseModel):
    code: str
    label: str
    anchor: str


class AiNarrativeSectionResponse(BaseModel):
    title: str
    bullets: list[str] = Field(default_factory=list)


class AiNarrativeProviderResponse(BaseModel):
    provider: str
    model: str | None = None
    timeout_seconds: float = Field(ge=0.0)


class AiNarrativeEnvelopeResponse(BaseModel):
    status: str = Field(pattern="^(ok|disabled|unavailable|error|skipped)$")
    label: str
    title: str
    summary: str
    bullets: list[str] = Field(default_factory=list)
    sections: list[AiNarrativeSectionResponse] = Field(default_factory=list)
    evidence_refs: list[AiNarrativeEvidenceRefResponse] = Field(default_factory=list)
    caution_notes: list[str] = Field(default_factory=list)
    uncertainty_notes: list[str] = Field(default_factory=list)
    provider: AiNarrativeProviderResponse


class CompareRecommendationAbstentionResponse(BaseModel):
    active: bool
    code: str | None = None
    reason: str | None = None


class CompareRecommendationEvidenceRefResponse(BaseModel):
    code: str
    label: str
    anchor: str


class CompareRecommendationResponse(BaseModel):
    contract_version: str
    surface: str
    scope: str
    visibility: str
    status: str = Field(pattern="^(issued|abstained)$")
    verdict: str = Field(pattern="^(wait|recheck_later|insufficient_evidence)$")
    verdict_vocabulary: list[str] = Field(default_factory=list)
    headline: str
    summary: str
    basis: list[str] = Field(default_factory=list)
    uncertainty_notes: list[str] = Field(default_factory=list)
    abstention: CompareRecommendationAbstentionResponse
    evidence_refs: list[CompareRecommendationEvidenceRefResponse] = Field(default_factory=list)
    deterministic_primary_note: str
    feedback_boundary: str
    override_boundary: str
    buy_now_blocked: bool = True


class ComparePreviewResponse(BaseModel):
    submitted_count: int = Field(ge=0)
    resolved_count: int = Field(ge=0)
    comparisons: list[ComparePreviewComparisonResponse] = Field(default_factory=list)
    matches: list[ComparePreviewMatchResponse] = Field(default_factory=list)
    compare_evidence: dict[str, Any]
    recommendation: CompareRecommendationResponse
    recommended_next_step_hint: dict[str, Any]
    risk_notes: list[str] = Field(default_factory=list)
    risk_note_items: list[dict[str, Any]] = Field(default_factory=list)
    ai_explain: AiNarrativeEnvelopeResponse
    model_config = ConfigDict(extra="allow")


class RuntimeReadinessCheckResponse(BaseModel):
    key: str
    label: str
    severity: str
    status: str = Field(pattern="^(ready|warning|blocked)$")
    reason: str
    message: str
    checked_at: str
    detail: dict[str, Any] = Field(default_factory=dict)


class RuntimeReadinessResponse(BaseModel):
    generated_at: str
    overall_status: str
    required_ready_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    blocked_count: int = Field(ge=0)
    checks: list[RuntimeReadinessCheckResponse] = Field(default_factory=list)


class RecoveryInboxItemResponse(BaseModel):
    kind: str = Field(pattern="^(task|group)$")
    id: str
    title: str
    health_status: str
    manual_intervention_required: bool
    backoff_until: str | None = None
    next_run_at: str | None = None
    last_run_status: str | None = None
    last_failure_kind: str | None = None
    last_error_code: str | None = None
    last_error_message: str | None = None
    recommended_action: str


class RecoveryInboxResponse(BaseModel):
    generated_at: str
    total_items: int = Field(ge=0)
    task_items: list[RecoveryInboxItemResponse] = Field(default_factory=list)
    group_items: list[RecoveryInboxItemResponse] = Field(default_factory=list)
    ai_copilot: AiNarrativeEnvelopeResponse


class WatchGroupDetailResponse(BaseModel):
    group: dict[str, Any]
    decision_explain: dict[str, Any]
    ai_decision_explain: AiNarrativeEnvelopeResponse
    members: list[dict[str, Any]] = Field(default_factory=list)
    runs: list[dict[str, Any]] = Field(default_factory=list)
    deliveries: list[dict[str, Any]] = Field(default_factory=list)
    model_config = ConfigDict(extra="allow")


WatchTaskCreateRequest = CreateWatchTaskRequest
WatchTaskUpdateRequest = UpdateWatchTaskRequest
