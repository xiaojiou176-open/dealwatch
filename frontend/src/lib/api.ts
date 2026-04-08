import type {
  AIAssistEnvelope,
  AIAssistStatus,
  CompareRecommendation,
  CompareEvidencePackageArtifact,
  CreateCompareEvidencePackageInput,
  ComparePreviewInput,
  ComparePreviewResponse,
  CreateWatchGroupInput,
  CreateWatchTaskInput,
  DeliveryEvent,
  NotificationEvent,
  NotificationSettings,
  PricePoint,
  RecoveryGroupItem,
  RecoveryInbox,
  RecoveryTaskItem,
  RunStatus,
  RuntimeReadiness,
  RuntimeReadinessCheck,
  StoreBindingSetting,
  StoreOnboardingCockpit,
  TaskRun,
  UpdateWatchGroupInput,
  UpdateWatchTaskInput,
  WatchGroupDetail,
  WatchGroupMemberResult,
  WatchGroupRun,
  WatchGroupSummary,
  WatchTaskDetail,
  WatchTaskSummary,
} from "../types";

type ApiAIAssistEnvelope = Record<string, unknown> | string;

type ApiTaskSummary = {
  id: string;
  title: string | null;
  normalized_url: string | null;
  store_key: string | null;
  status: WatchTaskSummary["status"];
  health_status: WatchTaskSummary["healthStatus"];
  zip_code?: string | null;
  cadence_minutes: number;
  next_run_at: string | null;
  last_listed_price: number | null;
  last_effective_price: number | null;
  last_run_status: WatchTaskSummary["lastRunStatus"] | null;
  backoff_until: string | null;
  manual_intervention_required: boolean;
};

type ApiTaskDetail = {
  task: {
    id: string;
    title: string;
    status: WatchTaskSummary["status"];
    normalized_url: string | null;
    submitted_url: string | null;
    store_key: string | null;
    threshold_type: WatchTaskDetail["task"]["thresholdType"];
    threshold_value: number;
    zip_code: string;
    cadence_minutes: number;
    cooldown_minutes: number;
    next_run_at: string | null;
    last_run_at: string | null;
    last_listed_price: number | null;
    last_effective_price: number | null;
    last_run_status: WatchTaskSummary["lastRunStatus"] | null;
    recipient_email: string;
    health_status: WatchTaskSummary["healthStatus"];
    consecutive_failures: number;
    backoff_until: string | null;
    last_failure_kind: string | null;
    manual_intervention_required: boolean;
  };
  compare_context: {
    candidate_key: string;
    title_snapshot: string;
    merchant_key: string;
    brand_hint: string | null;
    size_hint: string | null;
    similarity_score: number;
    canonical_product_id: string | null;
    source_url: string;
  } | null;
  observations: Array<{
    observed_at: string;
    listed_price: number;
    title_snapshot: string;
  }>;
  runs: Array<{
    id: string;
    status: TaskRun["status"];
    triggered_by: string | null;
    started_at: string | null;
    finished_at: string | null;
    error_code: string | null;
    error_message: string | null;
    artifact_run_dir: string | null;
    artifact_evidence: {
      summary_path: string;
      summary_exists: boolean;
      captured_at: string | null;
      title_snapshot: string | null;
      listed_price: number | null;
      effective_price: number | null;
      source_url: string | null;
      delivery_count: number;
      latest_delivery_status: string | null;
      has_cashback_quote: boolean;
    } | null;
  }>;
  delivery_events: Array<{
    id: string;
    provider: string;
    recipient: string;
    status: DeliveryEvent["status"];
    sent_at: string | null;
    created_at: string;
    delivered_at: string | null;
    bounced_at: string | null;
  }>;
  cashback_quotes: Array<{
    provider: string;
    rate_type: "percent" | "flat";
    rate_value: number;
    confidence: number;
    collected_at: string;
  }>;
  effective_prices: Array<{
    effective_price: number;
    computed_at: string;
  }>;
  latest_signal: {
    previous_listed_price: number | null;
    delta_amount: number | null;
    delta_pct: number | null;
    is_new_low: boolean;
    anomaly_reason: string | null;
    decision_reason: string | null;
  } | null;
};

type ApiWatchGroupSummary = {
  id: string;
  title: string;
  status: WatchGroupSummary["status"];
  health_status: WatchGroupSummary["healthStatus"];
  zip_code: string;
  cadence_minutes: number;
  next_run_at: string | null;
  last_run_at: string | null;
  last_run_status: WatchGroupSummary["lastRunStatus"] | null;
  member_count: number;
  winner_title: string | null;
  winner_effective_price: number | null;
  price_spread: number | null;
  backoff_until: string | null;
  manual_intervention_required: boolean;
};

type ApiWatchGroupDetail = {
  group: {
    id: string;
    title: string;
    status: WatchGroupSummary["status"];
    zip_code: string;
    cadence_minutes: number;
    threshold_type: WatchGroupDetail["group"]["thresholdType"];
    threshold_value: number;
    cooldown_minutes: number;
    recipient_email: string;
    notifications_enabled: boolean;
    next_run_at: string | null;
    last_run_at: string | null;
    last_success_at: string | null;
    last_error_code: string | null;
    last_error_message: string | null;
    health_status: WatchGroupSummary["healthStatus"];
    consecutive_failures: number;
    backoff_until: string | null;
    last_failure_kind: string | null;
    manual_intervention_required: boolean;
    member_count: number;
    current_winner_member_id: string | null;
    current_winner_title: string | null;
    current_winner_effective_price: number | null;
    price_spread: number | null;
    decision_reason: string | null;
  };
  decision_explain: {
    headline: string;
    decision_reason: string | null;
    sort_basis: string;
    winner: {
      member_id: string;
      title: string;
      store_key: string | null;
      listed_price: number | null;
      effective_price: number | null;
      cashback_amount: number | null;
      status: RunStatus | null;
    } | null;
    runner_up: {
      member_id: string;
      title: string;
      store_key: string | null;
      listed_price: number | null;
      effective_price: number | null;
      cashback_amount: number | null;
      status: RunStatus | null;
    } | null;
    comparison: {
      price_spread: number | null;
      effective_price_delta: number | null;
      listed_price_delta: number | null;
      cashback_delta: number | null;
    } | null;
    candidate_outcomes: {
      successful_count: number;
      blocked_count: number;
      failed_count: number;
    };
    reliability: WatchGroupDetail["decisionExplain"]["reliability"];
    risk_notes: string[];
  };
  ai_explain?: ApiAIAssistEnvelope | null;
  aiExplain?: ApiAIAssistEnvelope | null;
  ai_decision_explain?: ApiAIAssistEnvelope | null;
  aiDecisionExplain?: ApiAIAssistEnvelope | null;
  members: Array<{
    id: string;
    watch_target_id: string;
    title_snapshot: string;
    candidate_key: string;
    brand_hint: string | null;
    size_hint: string | null;
    similarity_score: number;
    is_current_winner: boolean;
    latest_result: ApiWatchGroupMemberResult | null;
  }>;
  runs: ApiWatchGroupRun[];
  deliveries: ApiDeliveryEvent[];
};

type ApiWatchGroupMemberResult = {
  member_id: string;
  watch_target_id?: string;
  store_key?: string;
  title_snapshot?: string;
  candidate_key?: string;
  listed_price?: number;
  effective_price?: number;
  cashback_amount?: number;
  source_url?: string;
  observed_at?: string;
  status: WatchGroupMemberResult["status"];
  error_code?: string;
  error_message?: string;
};

type ApiWatchGroupRun = {
  id: string;
  status: WatchGroupRun["status"];
  started_at: string | null;
  finished_at: string | null;
  error_message: string | null;
  winner_member_id: string | null;
  winner_effective_price: number | null;
  runner_up_member_id: string | null;
  runner_up_effective_price: number | null;
  price_spread: number | null;
  decision_reason: string | null;
  member_results: ApiWatchGroupMemberResult[];
  artifact_run_dir: string | null;
};

type ApiNotificationSettings = {
  default_recipient_email: string;
  cooldown_minutes: number;
  notifications_enabled: boolean;
};

type ApiRuntimeReadinessCheck = {
  key: string;
  label?: string | null;
  status: string;
  summary?: string | null;
  detail?: string | Record<string, unknown> | null;
  metadata?: Record<string, unknown> | null;
};

type ApiRuntimeReadiness = {
  overall_status?: string | null;
  headline?: string | null;
  generated_at?: string | null;
  checks: ApiRuntimeReadinessCheck[];
};

type ApiRecoveryTaskItem = {
  id: string;
  title: string;
  status: RecoveryTaskItem["status"];
  health_status: RecoveryTaskItem["healthStatus"];
  normalized_url: string | null;
  store_key: string | null;
  next_run_at: string | null;
  backoff_until: string | null;
  manual_intervention_required: boolean;
  consecutive_failures: number;
  last_failure_kind: string | null;
  last_error_code: string | null;
  last_error_message: string | null;
  last_run_at: string | null;
  reason: string;
  recommended_action: string;
};

type ApiRecoveryGroupItem = {
  id: string;
  title: string;
  status: RecoveryGroupItem["status"];
  health_status: RecoveryGroupItem["healthStatus"];
  zip_code: string | null;
  member_count: number;
  winner_title: string | null;
  next_run_at: string | null;
  backoff_until: string | null;
  manual_intervention_required: boolean;
  consecutive_failures: number;
  last_failure_kind: string | null;
  last_error_code: string | null;
  last_error_message: string | null;
  last_run_at: string | null;
  reason: string;
  recommended_action: string;
  ai_recovery_copilot?: ApiAIAssistEnvelope | null;
  aiRecoveryCopilot?: ApiAIAssistEnvelope | null;
  recovery_ai_copilot?: ApiAIAssistEnvelope | null;
  recoveryAiCopilot?: ApiAIAssistEnvelope | null;
  ai_copilot?: ApiAIAssistEnvelope | null;
  aiCopilot?: ApiAIAssistEnvelope | null;
};

type ApiRecoveryInbox = {
  tasks?: ApiRecoveryTaskItem[];
  groups?: ApiRecoveryGroupItem[];
  task_items?: ApiRecoveryTaskItem[];
  group_items?: ApiRecoveryGroupItem[];
};

type ApiNotificationEvent = {
  id: string;
  watch_task_id: string | null;
  watch_group_id: string | null;
  provider: string;
  status: NotificationEvent["status"];
  recipient: string;
  message_id: string | null;
  created_at: string;
  sent_at: string | null;
  delivered_at: string | null;
  bounced_at: string | null;
};

type ApiStoreBindingSetting = {
  store_key: string;
  enabled: boolean;
  adapter_class: string;
  support_channel: string;
  support_tier: string;
  support_reason_codes?: string[];
  next_step_codes?: string[];
  contract_test_paths?: string[];
  discovery_mode: string;
  parse_mode: string;
  region_sensitive: boolean;
  cashback_supported: boolean;
  supports_compare_intake: boolean;
  supports_watch_task: boolean;
  supports_watch_group: boolean;
  supports_recovery: boolean;
};

type ApiStoreOnboardingChecklistItem = {
  key: string;
  label: string;
  detail: string;
};

type ApiStoreOnboardingStoreRow = ApiStoreBindingSetting & {
  support_summary?: string;
  next_onboarding_step?: string;
  contract_status: "ready" | "attention_needed";
  missing_capabilities?: string[];
  contract_gaps: string[];
  source_of_truth_files?: string[];
};

type ApiStoreOnboardingCockpit = {
  generated_at: string;
  summary: {
    supported_store_count: number;
    official_full_count: number;
    official_partial_count: number;
    official_in_progress_count: number;
    enabled_store_count: number;
    disabled_store_count: number;
    compare_intake_supported_count: number;
    cashback_supported_count: number;
    watch_task_supported_count: number;
    watch_group_supported_count: number;
    recovery_supported_count: number;
    region_sensitive_count: number;
  };
  registry_health: {
    registry_store_count: number;
    capability_store_count: number;
    binding_store_count: number;
    registry_parity_ok: boolean;
    registry_only_store_keys: string[];
    manifest_only_store_keys: string[];
    binding_only_store_keys: string[];
  };
  stores: ApiStoreOnboardingStoreRow[];
  onboarding_checklist: ApiStoreOnboardingChecklistItem[];
  verification_commands: string[];
  truth_sources: string[];
  onboarding_contract?: {
    official_support_tiers?: string[];
    limited_support_contract?: string[];
  };
  limited_support_lane?: {
    support_channel: string;
    support_tier: string;
    summary: string;
    supported_actions?: string[];
    blocked_actions?: string[];
    contract_lines?: string[];
    source_of_truth_files?: string[];
  };
};

type ApiComparePreviewOffer = {
  store_id: string;
  product_key: string;
  deal_id: string;
  title: string;
  url: string;
  price: number;
  original_price: number | null;
  fetch_at: string;
  context: {
    region: string;
    currency: string;
    is_member: boolean;
  };
  unit_price_info: Record<string, string | number | boolean>;
};

type ApiComparePreviewComparison = {
  submitted_url: string;
  supported: boolean;
  store_key?: string;
  normalized_url?: string;
  fetch_succeeded?: boolean;
  error_code?: string;
  candidate_key?: string;
  brand_hint?: string;
  size_hint?: string;
  offer?: ApiComparePreviewOffer;
  support_contract?: {
    support_channel: string;
    store_support_tier: string;
    support_reason_codes?: string[];
    next_step_codes?: string[];
    intake_status: string;
    summary: string;
    next_step: string;
    can_save_compare_evidence: boolean;
    can_create_watch_task: boolean;
    can_create_watch_group: boolean;
    cashback_supported: boolean;
    notifications_supported: boolean;
    missing_capabilities?: string[];
  };
};

type ApiComparePreviewMatch = {
  left_store_key: string;
  left_product_key: string;
  right_store_key: string;
  right_product_key: string;
  score: number;
  title_similarity?: number;
  brand_signal?: "match" | "mismatch" | "unknown";
  size_signal?: "match" | "mismatch" | "unknown";
  product_key_signal?: string;
  left_candidate_key?: string;
  right_candidate_key?: string;
  why_like?: string[];
  why_unlike?: string[];
};

type ApiComparePreviewResponse = {
  submitted_count: number;
  resolved_count: number;
  comparisons: ApiComparePreviewComparison[];
  matches: ApiComparePreviewMatch[];
  recommendation?: {
    contract_version: string;
    surface: string;
    scope: string;
    visibility: string;
    status: "issued" | "abstained";
    verdict: "wait" | "recheck_later" | "insufficient_evidence";
    verdict_vocabulary?: string[];
    headline: string;
    summary: string;
    basis?: string[];
    uncertainty_notes?: string[];
    abstention?: {
      active: boolean;
      code?: string | null;
      reason?: string | null;
    };
    evidence_refs?: Array<{
      code: string;
      label: string;
      anchor: string;
    }>;
    deterministic_primary_note: string;
    feedback_boundary: string;
    override_boundary: string;
    buy_now_blocked: boolean;
  };
  recommended_next_step_hint?: {
    action: string;
    reason_code: string;
    summary: string;
    successful_candidate_count: number;
    strongest_match_score: number;
  };
  risk_notes?: string[];
  risk_note_items?: { code: string; message: string }[];
  ai_explain?: ApiAIAssistEnvelope | null;
  aiExplain?: ApiAIAssistEnvelope | null;
  ai_assisted_explanation?: ApiAIAssistEnvelope | null;
  aiAssistedExplanation?: ApiAIAssistEnvelope | null;
};

type ApiCompareEvidencePackageArtifact = Record<string, unknown>;

type ApiDeliveryEvent = {
  id: string;
  provider: string;
  recipient: string;
  status: DeliveryEvent["status"];
  created_at: string;
  sent_at: string | null;
  delivered_at: string | null;
  bounced_at: string | null;
};

type ApiErrorPayload = {
  detail?: string;
};

class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function getApiBaseUrl() {
  const configured = import.meta.env.VITE_API_BASE_URL as string | undefined;
  if (configured && configured.trim()) {
    return configured.replace(/\/$/, "");
  }
  if (import.meta.env.DEV) {
    if (typeof window !== "undefined") {
      const apiUrl = new URL(window.location.origin);
      apiUrl.port = "8000";
      return apiUrl.origin;
    }
    return "http://127.0.0.1:8000";
  }
  return "";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    let payload: ApiErrorPayload | null = null;
    try {
      payload = (await response.json()) as ApiErrorPayload;
    } catch {
      payload = null;
    }
    throw new ApiError(response.status, payload?.detail ?? `Request failed with status ${response.status}`);
  }

  return (await response.json()) as T;
}

function mapTaskSummary(payload: ApiTaskSummary): WatchTaskSummary {
  return {
    id: payload.id,
    title: payload.title ?? "Pending first fetch",
    normalizedUrl: payload.normalized_url ?? "",
    storeKey: payload.store_key ?? "unknown",
    status: payload.status,
    healthStatus: payload.health_status,
    zipCode: payload.zip_code ?? undefined,
    cadenceMinutes: payload.cadence_minutes,
    nextRunAt: payload.next_run_at,
    lastListedPrice: payload.last_listed_price,
    lastEffectivePrice: payload.last_effective_price,
    lastRunStatus: payload.last_run_status,
    backoffUntil: payload.backoff_until,
    manualInterventionRequired: payload.manual_intervention_required,
  };
}

function mapNotificationSettings(payload: ApiNotificationSettings): NotificationSettings {
  return {
    defaultRecipientEmail: payload.default_recipient_email,
    cooldownMinutes: payload.cooldown_minutes,
    notificationsEnabled: payload.notifications_enabled,
  };
}

function normalizeRuntimeStatus(
  rawStatus: string | null | undefined,
  key?: string,
): RuntimeReadiness["overallStatus"] {
  if (rawStatus === "blocked" || rawStatus === "action_needed") {
    return "action_needed";
  }
  if (rawStatus === "degraded" || rawStatus === "warning") {
    if (key === "smoke") {
      return "no_evidence";
    }
    return "warning";
  }
  if (rawStatus === "no_evidence") {
    return "no_evidence";
  }
  return "ready";
}

function deriveRuntimeOverallStatus(checks: ApiRuntimeReadinessCheck[]): RuntimeReadiness["overallStatus"] {
  if (checks.some((item) => normalizeRuntimeStatus(item.status, item.key) === "action_needed")) {
    return "action_needed";
  }
  if (checks.some((item) => normalizeRuntimeStatus(item.status, item.key) === "warning")) {
    return "warning";
  }
  if (checks.some((item) => normalizeRuntimeStatus(item.status, item.key) === "no_evidence")) {
    return "no_evidence";
  }
  return "ready";
}

function formatFallbackLabel(key: string): string {
  return key
    .split(/[_-]+/)
    .filter(Boolean)
    .map((part) => part.slice(0, 1).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatRuntimeCheckDetail(payload: ApiRuntimeReadinessCheck): string | null {
  if (typeof payload.detail === "string") {
    return payload.detail;
  }
  const meta = payload.metadata ?? (typeof payload.detail === "object" && payload.detail ? payload.detail : null);
  if (!meta) {
    return null;
  }
  if (payload.key === "database" && typeof meta.database_backend === "string") {
    return `Backend: ${meta.database_backend}`;
  }
  if (payload.key === "owner" && typeof meta.owner_email === "string" && meta.owner_email) {
    return `Owner: ${meta.owner_email}`;
  }
  if (payload.key === "stores") {
    const enabled = Array.isArray(meta.enabled_store_keys) ? meta.enabled_store_keys.join(", ") : "";
    return enabled ? `Enabled stores: ${enabled}` : null;
  }
  if (payload.key === "notifications" && typeof meta.provider_mode === "string") {
    return `Provider: ${meta.provider_mode}`;
  }
  if (payload.key === "startup_preflight") {
    const blockers = Array.isArray(meta.blocker_keys) ? meta.blocker_keys.join(", ") : "";
    const warnings = Array.isArray(meta.warning_keys) ? meta.warning_keys.join(", ") : "";
    if (blockers) {
      return `Blockers: ${blockers}`;
    }
    if (warnings) {
      return `Warnings: ${warnings}`;
    }
  }
  if (payload.key === "smoke" && typeof meta.latest_log_at === "string" && meta.latest_log_at) {
    return `Latest local evidence: ${new Date(meta.latest_log_at).toLocaleString()}`;
  }
  return null;
}

function mapRuntimeReadiness(payload: ApiRuntimeReadiness): RuntimeReadiness {
  return {
    overallStatus:
      normalizeRuntimeStatus(payload.overall_status ?? undefined) ??
      deriveRuntimeOverallStatus(payload.checks),
    headline: payload.headline ?? "Check the runtime contract before you trust the next run.",
    generatedAt: payload.generated_at ?? null,
    checks: payload.checks.map((item) => ({
      key: item.key,
      label: item.label ?? formatFallbackLabel(item.key),
      status: normalizeRuntimeStatus(item.status, item.key),
      summary: item.summary ?? "No detail returned yet.",
      detail: formatRuntimeCheckDetail(item),
    })),
  };
}

function mapNotificationEvent(payload: ApiNotificationEvent): NotificationEvent {
  return {
    id: payload.id,
    watchTaskId: payload.watch_task_id,
    watchGroupId: payload.watch_group_id,
    provider: payload.provider,
    status: payload.status,
    recipient: payload.recipient,
    messageId: payload.message_id,
    createdAt: payload.created_at,
    sentAt: payload.sent_at,
    deliveredAt: payload.delivered_at,
    bouncedAt: payload.bounced_at,
  };
}

function mapStoreBindingSetting(payload: ApiStoreBindingSetting): StoreBindingSetting {
  return {
    storeKey: payload.store_key,
    enabled: payload.enabled,
    adapterClass: payload.adapter_class,
    supportChannel: payload.support_channel,
    supportTier: payload.support_tier,
    supportReasonCodes: payload.support_reason_codes ?? [],
    nextStepCodes: payload.next_step_codes ?? [],
    contractTestPaths: payload.contract_test_paths ?? [],
    discoveryMode: payload.discovery_mode,
    parseMode: payload.parse_mode,
    regionSensitive: payload.region_sensitive,
    cashbackSupported: payload.cashback_supported,
    supportsCompareIntake: payload.supports_compare_intake,
    supportsWatchTask: payload.supports_watch_task,
    supportsWatchGroup: payload.supports_watch_group,
    supportsRecovery: payload.supports_recovery,
  };
}

function mapStoreOnboardingCockpit(payload: ApiStoreOnboardingCockpit): StoreOnboardingCockpit {
  return {
    generatedAt: payload.generated_at,
    summary: {
      supportedStoreCount: payload.summary.supported_store_count,
      officialFullCount: payload.summary.official_full_count,
      officialPartialCount: payload.summary.official_partial_count,
      officialInProgressCount: payload.summary.official_in_progress_count,
      enabledStoreCount: payload.summary.enabled_store_count,
      disabledStoreCount: payload.summary.disabled_store_count,
      compareIntakeSupportedCount: payload.summary.compare_intake_supported_count,
      cashbackSupportedCount: payload.summary.cashback_supported_count,
      watchTaskSupportedCount: payload.summary.watch_task_supported_count,
      watchGroupSupportedCount: payload.summary.watch_group_supported_count,
      recoverySupportedCount: payload.summary.recovery_supported_count,
      regionSensitiveCount: payload.summary.region_sensitive_count,
    },
    registryHealth: {
      registryStoreCount: payload.registry_health.registry_store_count,
      capabilityStoreCount: payload.registry_health.capability_store_count,
      bindingStoreCount: payload.registry_health.binding_store_count,
      registryParityOk: payload.registry_health.registry_parity_ok,
      registryOnlyStoreKeys: payload.registry_health.registry_only_store_keys,
      manifestOnlyStoreKeys: payload.registry_health.manifest_only_store_keys,
      bindingOnlyStoreKeys: payload.registry_health.binding_only_store_keys,
    },
    stores: payload.stores.map((item) => ({
      ...mapStoreBindingSetting(item),
      supportSummary: item.support_summary,
      nextOnboardingStep: item.next_onboarding_step,
      contractStatus: item.contract_status,
      missingCapabilities: item.missing_capabilities ?? [],
      contractGaps: item.contract_gaps ?? [],
      sourceOfTruthFiles: item.source_of_truth_files ?? [],
    })),
    onboardingChecklist: payload.onboarding_checklist.map((item) => ({
      key: item.key,
      label: item.label,
      detail: item.detail,
    })),
    verificationCommands: payload.verification_commands ?? [],
    truthSources: payload.truth_sources ?? [],
    officialSupportTiers: payload.onboarding_contract?.official_support_tiers ?? [],
    limitedSupportContract: payload.onboarding_contract?.limited_support_contract ?? [],
    limitedSupportLane: {
      supportChannel: payload.limited_support_lane?.support_channel ?? "limited",
      supportTier: payload.limited_support_lane?.support_tier ?? "limited_guidance_only",
      summary: payload.limited_support_lane?.summary ?? "",
      supportedActions: payload.limited_support_lane?.supported_actions ?? [],
      blockedActions: payload.limited_support_lane?.blocked_actions ?? [],
      contractLines: payload.limited_support_lane?.contract_lines ?? [],
      sourceOfTruthFiles: payload.limited_support_lane?.source_of_truth_files ?? [],
    },
  };
}

function mapComparePreview(payload: ApiComparePreviewResponse): ComparePreviewResponse {
  return {
    submittedCount: payload.submitted_count,
    resolvedCount: payload.resolved_count,
    comparisons: payload.comparisons.map((item) => ({
      submittedUrl: item.submitted_url,
      supported: item.supported,
      storeKey: item.store_key,
      normalizedUrl: item.normalized_url,
      fetchSucceeded: item.fetch_succeeded,
      errorCode: item.error_code,
      candidateKey: item.candidate_key,
      brandHint: item.brand_hint,
      sizeHint: item.size_hint,
      supportContract: item.support_contract
        ? {
            supportChannel: item.support_contract.support_channel,
            storeSupportTier: item.support_contract.store_support_tier,
            supportReasonCodes: item.support_contract.support_reason_codes ?? [],
            nextStepCodes: item.support_contract.next_step_codes ?? [],
            intakeStatus: item.support_contract.intake_status,
            summary: item.support_contract.summary,
            nextStep: item.support_contract.next_step,
            canSaveCompareEvidence: item.support_contract.can_save_compare_evidence,
            canCreateWatchTask: item.support_contract.can_create_watch_task,
            canCreateWatchGroup: item.support_contract.can_create_watch_group,
            cashbackSupported: item.support_contract.cashback_supported,
            notificationsSupported: item.support_contract.notifications_supported,
            missingCapabilities: item.support_contract.missing_capabilities ?? [],
          }
        : undefined,
      offer: item.offer
        ? {
            storeId: item.offer.store_id,
            productKey: item.offer.product_key,
            dealId: item.offer.deal_id,
            title: item.offer.title,
            url: item.offer.url,
            price: item.offer.price,
            originalPrice: item.offer.original_price,
            fetchAt: item.offer.fetch_at,
            context: {
              region: item.offer.context.region,
              currency: item.offer.context.currency,
              isMember: item.offer.context.is_member,
            },
            unitPriceInfo: item.offer.unit_price_info,
          }
        : undefined,
    })),
    matches: payload.matches.map((item) => ({
      leftStoreKey: item.left_store_key,
      leftProductKey: item.left_product_key,
      rightStoreKey: item.right_store_key,
      rightProductKey: item.right_product_key,
      score: item.score,
      titleSimilarity: item.title_similarity,
      brandSignal: item.brand_signal,
      sizeSignal: item.size_signal,
      productKeySignal: item.product_key_signal,
      leftCandidateKey: item.left_candidate_key,
      rightCandidateKey: item.right_candidate_key,
      whyLike: item.why_like ?? [],
      whyUnlike: item.why_unlike ?? [],
    })),
    recommendation: mapCompareRecommendation(
      (payload.recommendation as Record<string, unknown> | undefined) ?? {},
    ),
    recommendedNextStepHint: payload.recommended_next_step_hint
      ? {
          action: payload.recommended_next_step_hint.action,
          reasonCode: payload.recommended_next_step_hint.reason_code,
          summary: payload.recommended_next_step_hint.summary,
          successfulCandidateCount: payload.recommended_next_step_hint.successful_candidate_count,
          strongestMatchScore: payload.recommended_next_step_hint.strongest_match_score,
        }
      : undefined,
    riskNotes: payload.risk_notes ?? [],
    riskNoteItems: payload.risk_note_items ?? [],
    aiExplain: readNamedAIAssistEnvelope(payload as Record<string, unknown>, [
      "ai_explain",
      "aiExplain",
      "ai_assisted_explanation",
      "aiAssistedExplanation",
      "compare_ai_explain",
      "compareAiExplain",
    ]),
  };
}

function mapCompareRecommendation(payload: Record<string, unknown>): CompareRecommendation {
  const abstention = (payload.abstention as Record<string, unknown> | undefined) ?? {};
  const evidenceRefs = Array.isArray(payload.evidence_refs) ? payload.evidence_refs : [];
  const verdict =
    readStringField(payload, ["verdict"]) ?? "insufficient_evidence";
  return {
    contractVersion: readStringField(payload, ["contract_version"]) ?? "compare_preview_public_v1",
    surface: readStringField(payload, ["surface"]) ?? "compare_preview",
    scope: readStringField(payload, ["scope"]) ?? "local_runtime_compare_flow",
    visibility: readStringField(payload, ["visibility"]) ?? "user_visible",
    status: (readStringField(payload, ["status"]) as CompareRecommendation["status"] | null) ?? "abstained",
    verdict: verdict as CompareRecommendation["verdict"],
    verdictVocabulary: Array.isArray(payload.verdict_vocabulary)
      ? payload.verdict_vocabulary.filter((item): item is string => typeof item === "string")
      : ["wait", "recheck_later", "insufficient_evidence"],
    headline: readStringField(payload, ["headline"]) ?? "Not enough evidence yet",
    summary: readStringField(payload, ["summary"]) ?? "Recommendation unavailable.",
    basis: Array.isArray(payload.basis) ? payload.basis.filter((item): item is string => typeof item === "string") : [],
    uncertaintyNotes: Array.isArray(payload.uncertainty_notes)
      ? payload.uncertainty_notes.filter((item): item is string => typeof item === "string")
      : [],
    abstention: {
      active: Boolean(abstention.active),
      code: readStringField(abstention, ["code"]),
      reason: readStringField(abstention, ["reason"]),
    },
    evidenceRefs: evidenceRefs
      .filter((item): item is Record<string, unknown> => !!item && typeof item === "object")
      .map((item) => ({
        code: readStringField(item, ["code"]) ?? "compare_signal",
        label: readStringField(item, ["label"]) ?? "Compare signal",
        anchor: readStringField(item, ["anchor"]) ?? "compare_evidence",
      })),
    deterministicPrimaryNote:
      readStringField(payload, ["deterministic_primary_note"]) ??
      "Deterministic compare evidence stays primary.",
    feedbackBoundary:
      readStringField(payload, ["feedback_boundary"]) ??
      "End-user feedback is not yet a persisted product surface.",
    overrideBoundary:
      readStringField(payload, ["override_boundary"]) ??
      "Users keep the final action choice.",
    buyNowBlocked: readBooleanField(payload, ["buy_now_blocked"]) ?? true,
  };
}

function serializeComparePreview(response: ComparePreviewResponse): ApiComparePreviewResponse {
  return {
    submitted_count: response.submittedCount,
    resolved_count: response.resolvedCount,
    comparisons: response.comparisons.map((item) => ({
      submitted_url: item.submittedUrl,
      supported: item.supported,
      store_key: item.storeKey,
      normalized_url: item.normalizedUrl,
      fetch_succeeded: item.fetchSucceeded,
      error_code: item.errorCode,
      candidate_key: item.candidateKey,
      brand_hint: item.brandHint,
      size_hint: item.sizeHint,
      support_contract: item.supportContract
        ? {
            support_channel: item.supportContract.supportChannel,
            store_support_tier: item.supportContract.storeSupportTier,
            support_reason_codes: item.supportContract.supportReasonCodes,
            next_step_codes: item.supportContract.nextStepCodes,
            intake_status: item.supportContract.intakeStatus,
            summary: item.supportContract.summary,
            next_step: item.supportContract.nextStep,
            can_save_compare_evidence: item.supportContract.canSaveCompareEvidence,
            can_create_watch_task: item.supportContract.canCreateWatchTask,
            can_create_watch_group: item.supportContract.canCreateWatchGroup,
            cashback_supported: item.supportContract.cashbackSupported,
            notifications_supported: item.supportContract.notificationsSupported,
            missing_capabilities: item.supportContract.missingCapabilities,
          }
        : undefined,
      offer: item.offer
        ? {
            store_id: item.offer.storeId,
            product_key: item.offer.productKey,
            deal_id: item.offer.dealId,
            title: item.offer.title,
            url: item.offer.url,
            price: item.offer.price,
            original_price: item.offer.originalPrice,
            fetch_at: item.offer.fetchAt,
            context: {
              region: item.offer.context.region,
              currency: item.offer.context.currency,
              is_member: item.offer.context.isMember,
            },
            unit_price_info: item.offer.unitPriceInfo,
          }
        : undefined,
    })),
    matches: response.matches.map((item) => ({
      left_store_key: item.leftStoreKey,
      left_product_key: item.leftProductKey,
      right_store_key: item.rightStoreKey,
      right_product_key: item.rightProductKey,
      score: item.score,
      title_similarity: item.titleSimilarity,
      brand_signal: item.brandSignal,
      size_signal: item.sizeSignal,
      product_key_signal: item.productKeySignal,
      left_candidate_key: item.leftCandidateKey,
      right_candidate_key: item.rightCandidateKey,
      why_like: item.whyLike,
      why_unlike: item.whyUnlike,
    })),
    recommended_next_step_hint: response.recommendedNextStepHint
      ? {
          action: response.recommendedNextStepHint.action,
          reason_code: response.recommendedNextStepHint.reasonCode,
          summary: response.recommendedNextStepHint.summary,
          successful_candidate_count: response.recommendedNextStepHint.successfulCandidateCount,
          strongest_match_score: response.recommendedNextStepHint.strongestMatchScore,
        }
      : undefined,
    risk_notes: response.riskNotes ?? [],
    risk_note_items: response.riskNoteItems ?? [],
  };
}

function readStringField(payload: Record<string, unknown>, keys: string[]): string | null {
  for (const key of keys) {
    const value = payload[key];
    if (typeof value === "string" && value.trim()) {
      return value;
    }
  }
  return null;
}

function readBooleanField(payload: Record<string, unknown>, keys: string[]): boolean | null {
  for (const key of keys) {
    const value = payload[key];
    if (typeof value === "boolean") {
      return value;
    }
  }
  return null;
}

function readObjectField(payload: Record<string, unknown>, keys: string[]): Record<string, unknown> | null {
  for (const key of keys) {
    const value = payload[key];
    if (value && typeof value === "object" && !Array.isArray(value)) {
      return value as Record<string, unknown>;
    }
  }
  return null;
}

function readStringArrayField(payload: Record<string, unknown>, keys: string[]): string[] {
  for (const key of keys) {
    const value = payload[key];
    if (!Array.isArray(value)) {
      continue;
    }
    const normalized = value
      .map((item) => {
        if (typeof item === "string") {
          return item.trim();
        }
        if (item && typeof item === "object") {
          return readStringField(item as Record<string, unknown>, ["message", "summary", "detail", "title", "text"]) ?? "";
        }
        return "";
      })
      .filter(Boolean);
    if (normalized.length) {
      return normalized;
    }
  }
  return [];
}

function createAIAssistEnvelope(
  status: AIAssistStatus,
  overrides: Partial<Omit<AIAssistEnvelope, "status">> = {},
): AIAssistEnvelope {
  return {
    status,
    title: overrides.title ?? null,
    summary: overrides.summary ?? null,
    detail: overrides.detail ?? null,
    bullets: overrides.bullets ?? [],
    reasonCode: overrides.reasonCode ?? null,
    generatedAt: overrides.generatedAt ?? null,
  };
}

function normalizeAIAssistStatus(value: string | null): AIAssistStatus | null {
  switch (value?.trim().toLowerCase()) {
    case "ok":
    case "ready":
      return "ok";
    case "disabled":
      return "disabled";
    case "unavailable":
    case "no_evidence":
      return "unavailable";
    case "error":
    case "failed":
      return "error";
    case "skipped":
      return "skipped";
    default:
      return null;
  }
}

function mapAIAssistEnvelope(payload: ApiAIAssistEnvelope | null | undefined): AIAssistEnvelope {
  if (typeof payload === "string") {
    return createAIAssistEnvelope("ok", { summary: payload.trim() || null });
  }
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return createAIAssistEnvelope("unavailable");
  }

  const record = payload as Record<string, unknown>;
  const title = readStringField(record, ["title", "headline", "label"]);
  const summary = readStringField(record, ["summary", "message", "overview"]);
  const detail = readStringField(record, ["detail", "body", "text", "explanation"]);
  const bullets = readStringArrayField(record, [
    "bullets",
    "points",
    "supporting_points",
    "supportingPoints",
    "notes",
    "reasons",
    "next_steps",
    "nextSteps",
  ]);
  const explicitStatus = normalizeAIAssistStatus(readStringField(record, ["status", "state"]));
  const hasContent = Boolean(title || summary || detail || bullets.length);

  return createAIAssistEnvelope(explicitStatus ?? (hasContent ? "ok" : "unavailable"), {
    title,
    summary,
    detail,
    bullets,
    reasonCode: readStringField(record, ["reason_code", "reasonCode", "code", "error_code", "errorCode"]),
    generatedAt: readStringField(record, ["generated_at", "generatedAt", "created_at", "createdAt"]),
  });
}

function readNamedAIAssistEnvelope(payload: Record<string, unknown>, keys: string[]): AIAssistEnvelope {
  const rawObject = readObjectField(payload, keys);
  if (rawObject) {
    return mapAIAssistEnvelope(rawObject);
  }
  for (const key of keys) {
    const value = payload[key];
    if (typeof value === "string") {
      return mapAIAssistEnvelope(value);
    }
  }
  return createAIAssistEnvelope("unavailable");
}

function mapCompareEvidencePackageArtifact(
  payload: ApiCompareEvidencePackageArtifact,
): CompareEvidencePackageArtifact {
  const normalized = payload as Record<string, unknown>;
  const id =
    readStringField(normalized, ["id", "package_id"]) ??
    `runtime-${globalThis.crypto?.randomUUID?.() ?? Date.now().toString()}`;
  const htmlUrl =
    readStringField(normalized, ["html_url", "htmlUrl"]) ??
    `${getApiBaseUrl()}/api/compare/evidence-packages/${id}/html`;

  return {
    id,
    createdAt: readStringField(normalized, ["created_at", "generated_at", "saved_at"]),
    htmlUrl,
    summaryPath: readStringField(normalized, ["summary_path", "artifact_path", "package_path"]),
  };
}

function mapPriceHistory(detail: ApiTaskDetail): PricePoint[] {
  return detail.observations.map((item, index) => ({
    observedAt: item.observed_at,
    listedPrice: item.listed_price,
    effectivePrice: detail.effective_prices[index]?.effective_price ?? null,
  }));
}

function mapDeliveryEvent(payload: ApiDeliveryEvent): DeliveryEvent {
  return {
    id: payload.id,
    provider: payload.provider,
    recipient: payload.recipient,
    status: payload.status,
    createdAt: payload.created_at,
    sentAt: payload.sent_at,
    deliveredAt: payload.delivered_at,
    bouncedAt: payload.bounced_at,
  };
}

function mapRecoveryTaskItem(payload: ApiRecoveryTaskItem): RecoveryTaskItem {
  return {
    kind: "task",
    id: payload.id,
    title: payload.title,
    status: payload.status,
    healthStatus: payload.health_status,
    normalizedUrl: payload.normalized_url ?? "",
    storeKey: payload.store_key ?? "unknown",
    nextRunAt: payload.next_run_at,
    backoffUntil: payload.backoff_until,
    manualInterventionRequired: payload.manual_intervention_required,
    consecutiveFailures: payload.consecutive_failures,
    lastFailureKind: payload.last_failure_kind,
    lastErrorCode: payload.last_error_code,
    lastErrorMessage: payload.last_error_message,
    lastRunAt: payload.last_run_at,
    reason: payload.reason,
    recommendedAction: payload.recommended_action,
  };
}

function mapRecoveryGroupItem(payload: ApiRecoveryGroupItem): RecoveryGroupItem {
  return {
    kind: "group",
    id: payload.id,
    title: payload.title,
    status: payload.status,
    healthStatus: payload.health_status,
    zipCode: payload.zip_code ?? "--",
    memberCount: payload.member_count,
    winnerTitle: payload.winner_title,
    nextRunAt: payload.next_run_at,
    backoffUntil: payload.backoff_until,
    manualInterventionRequired: payload.manual_intervention_required,
    consecutiveFailures: payload.consecutive_failures,
    lastFailureKind: payload.last_failure_kind,
    lastErrorCode: payload.last_error_code,
    lastErrorMessage: payload.last_error_message,
    lastRunAt: payload.last_run_at,
    reason: payload.reason,
    recommendedAction: payload.recommended_action,
    aiCopilot: readNamedAIAssistEnvelope(payload as Record<string, unknown>, [
      "ai_recovery_copilot",
      "aiRecoveryCopilot",
      "recovery_ai_copilot",
      "recoveryAiCopilot",
      "ai_copilot",
      "aiCopilot",
    ]),
  };
}

function mapRecoveryInbox(payload: ApiRecoveryInbox): RecoveryInbox {
  return {
    tasks: (payload.tasks ?? payload.task_items ?? []).map(mapRecoveryTaskItem),
    groups: (payload.groups ?? payload.group_items ?? []).map(mapRecoveryGroupItem),
  };
}

function mapWatchGroupMemberResult(payload: ApiWatchGroupMemberResult): WatchGroupMemberResult {
  return {
    memberId: payload.member_id,
    watchTargetId: payload.watch_target_id,
    storeKey: payload.store_key,
    titleSnapshot: payload.title_snapshot,
    candidateKey: payload.candidate_key,
    listedPrice: payload.listed_price,
    effectivePrice: payload.effective_price,
    cashbackAmount: payload.cashback_amount,
    sourceUrl: payload.source_url,
    observedAt: payload.observed_at,
    status: payload.status,
    errorCode: payload.error_code,
    errorMessage: payload.error_message,
  };
}

function mapWatchGroupSummary(payload: ApiWatchGroupSummary): WatchGroupSummary {
  return {
    id: payload.id,
    title: payload.title,
    status: payload.status,
    healthStatus: payload.health_status,
    zipCode: payload.zip_code,
    cadenceMinutes: payload.cadence_minutes,
    nextRunAt: payload.next_run_at,
    lastRunAt: payload.last_run_at,
    lastRunStatus: payload.last_run_status,
    memberCount: payload.member_count,
    winnerTitle: payload.winner_title,
    winnerEffectivePrice: payload.winner_effective_price,
    priceSpread: payload.price_spread,
    backoffUntil: payload.backoff_until,
    manualInterventionRequired: payload.manual_intervention_required,
  };
}

function mapWatchGroupRun(payload: ApiWatchGroupRun): WatchGroupRun {
  return {
    id: payload.id,
    status: payload.status,
    startedAt: payload.started_at,
    finishedAt: payload.finished_at,
    errorMessage: payload.error_message,
    winnerMemberId: payload.winner_member_id,
    winnerEffectivePrice: payload.winner_effective_price,
    runnerUpMemberId: payload.runner_up_member_id,
    runnerUpEffectivePrice: payload.runner_up_effective_price,
    priceSpread: payload.price_spread,
    decisionReason: payload.decision_reason,
    memberResults: payload.member_results.map(mapWatchGroupMemberResult),
    artifactRunDir: payload.artifact_run_dir,
  };
}

function mapTaskDetail(payload: ApiTaskDetail): WatchTaskDetail {
  return {
    task: {
      id: payload.task.id,
      title: payload.task.title,
      normalizedUrl: payload.task.normalized_url ?? "",
      storeKey: payload.task.store_key ?? "unknown",
      status: payload.task.status,
      healthStatus: payload.task.health_status,
      zipCode: payload.task.zip_code,
      cadenceMinutes: payload.task.cadence_minutes,
      nextRunAt: payload.task.next_run_at,
      lastListedPrice: payload.task.last_listed_price,
      lastEffectivePrice: payload.task.last_effective_price,
      lastRunStatus: payload.task.last_run_status,
      backoffUntil: payload.task.backoff_until,
      manualInterventionRequired: payload.task.manual_intervention_required,
      thresholdType: payload.task.threshold_type,
      thresholdValue: payload.task.threshold_value,
      recipientEmail: payload.task.recipient_email,
      cooldownMinutes: payload.task.cooldown_minutes,
      lastRunAt: payload.task.last_run_at,
      consecutiveFailures: payload.task.consecutive_failures,
      lastFailureKind: payload.task.last_failure_kind,
    },
    priceHistory: mapPriceHistory(payload),
    runs: payload.runs.map((item) => ({
      id: item.id,
      status: item.status,
      triggeredBy: item.triggered_by,
      startedAt: item.started_at,
      finishedAt: item.finished_at,
      errorCode: item.error_code,
      errorMessage: item.error_message,
      artifactRunDir: item.artifact_run_dir,
      artifactEvidence: item.artifact_evidence
        ? {
            summaryPath: item.artifact_evidence.summary_path,
            summaryExists: item.artifact_evidence.summary_exists,
            capturedAt: item.artifact_evidence.captured_at,
            titleSnapshot: item.artifact_evidence.title_snapshot,
            listedPrice: item.artifact_evidence.listed_price,
            effectivePrice: item.artifact_evidence.effective_price,
            sourceUrl: item.artifact_evidence.source_url,
            deliveryCount: item.artifact_evidence.delivery_count,
            latestDeliveryStatus: item.artifact_evidence.latest_delivery_status,
            hasCashbackQuote: item.artifact_evidence.has_cashback_quote,
          }
        : null,
    })),
    deliveries: payload.delivery_events.map(mapDeliveryEvent),
    cashbackQuote: payload.cashback_quotes[0]
      ? {
          provider: payload.cashback_quotes[0].provider,
          rateLabel:
            payload.cashback_quotes[0].rate_type === "percent"
              ? `${payload.cashback_quotes[0].rate_value}% back`
              : `$${payload.cashback_quotes[0].rate_value.toFixed(2)} back`,
          confidence: payload.cashback_quotes[0].confidence,
          collectedAt: payload.cashback_quotes[0].collected_at,
        }
      : null,
    latestSignal: payload.latest_signal
      ? {
          previousListedPrice: payload.latest_signal.previous_listed_price,
          deltaAmount: payload.latest_signal.delta_amount,
          deltaPct: payload.latest_signal.delta_pct,
          isNewLow: payload.latest_signal.is_new_low,
          anomalyReason: payload.latest_signal.anomaly_reason,
          decisionReason: payload.latest_signal.decision_reason,
        }
      : null,
    compareContext: payload.compare_context
      ? {
          candidateKey: payload.compare_context.candidate_key,
          titleSnapshot: payload.compare_context.title_snapshot,
          merchantKey: payload.compare_context.merchant_key,
          brandHint: payload.compare_context.brand_hint,
          sizeHint: payload.compare_context.size_hint,
          similarityScore: payload.compare_context.similarity_score,
          canonicalProductId: payload.compare_context.canonical_product_id,
          sourceUrl: payload.compare_context.source_url,
        }
      : null,
  };
}

function mapWatchGroupDetail(payload: ApiWatchGroupDetail): WatchGroupDetail {
  return {
    group: {
      id: payload.group.id,
      title: payload.group.title,
      status: payload.group.status,
      healthStatus: payload.group.health_status,
      zipCode: payload.group.zip_code,
      cadenceMinutes: payload.group.cadence_minutes,
      nextRunAt: payload.group.next_run_at,
      lastRunAt: payload.group.last_run_at,
      lastRunStatus: null,
      memberCount: payload.group.member_count,
      winnerTitle: payload.group.current_winner_title,
      winnerEffectivePrice: payload.group.current_winner_effective_price,
      priceSpread: payload.group.price_spread,
      backoffUntil: payload.group.backoff_until,
      manualInterventionRequired: payload.group.manual_intervention_required,
      thresholdType: payload.group.threshold_type,
      thresholdValue: payload.group.threshold_value,
      cooldownMinutes: payload.group.cooldown_minutes,
      recipientEmail: payload.group.recipient_email,
      notificationsEnabled: payload.group.notifications_enabled,
      lastSuccessAt: payload.group.last_success_at,
      lastErrorCode: payload.group.last_error_code,
      lastErrorMessage: payload.group.last_error_message,
      consecutiveFailures: payload.group.consecutive_failures,
      lastFailureKind: payload.group.last_failure_kind,
      currentWinnerMemberId: payload.group.current_winner_member_id,
      currentWinnerTitle: payload.group.current_winner_title,
      currentWinnerEffectivePrice: payload.group.current_winner_effective_price,
      decisionReason: payload.group.decision_reason,
    },
    decisionExplain: {
      headline: payload.decision_explain.headline,
      decisionReason: payload.decision_explain.decision_reason,
      sortBasis: payload.decision_explain.sort_basis,
      winner: payload.decision_explain.winner
        ? {
            memberId: payload.decision_explain.winner.member_id,
            title: payload.decision_explain.winner.title,
            storeKey: payload.decision_explain.winner.store_key,
            listedPrice: payload.decision_explain.winner.listed_price,
            effectivePrice: payload.decision_explain.winner.effective_price,
            cashbackAmount: payload.decision_explain.winner.cashback_amount,
            status: payload.decision_explain.winner.status,
          }
        : null,
      runnerUp: payload.decision_explain.runner_up
        ? {
            memberId: payload.decision_explain.runner_up.member_id,
            title: payload.decision_explain.runner_up.title,
            storeKey: payload.decision_explain.runner_up.store_key,
            listedPrice: payload.decision_explain.runner_up.listed_price,
            effectivePrice: payload.decision_explain.runner_up.effective_price,
            cashbackAmount: payload.decision_explain.runner_up.cashback_amount,
            status: payload.decision_explain.runner_up.status,
          }
        : null,
      comparison: payload.decision_explain.comparison
        ? {
            priceSpread: payload.decision_explain.comparison.price_spread,
            effectivePriceDelta: payload.decision_explain.comparison.effective_price_delta,
            listedPriceDelta: payload.decision_explain.comparison.listed_price_delta,
            cashbackDelta: payload.decision_explain.comparison.cashback_delta,
          }
        : null,
      candidateOutcomes: {
        successfulCount: payload.decision_explain.candidate_outcomes.successful_count,
        blockedCount: payload.decision_explain.candidate_outcomes.blocked_count,
        failedCount: payload.decision_explain.candidate_outcomes.failed_count,
      },
      reliability: payload.decision_explain.reliability,
      riskNotes: payload.decision_explain.risk_notes,
    },
    aiExplain: readNamedAIAssistEnvelope(payload as Record<string, unknown>, [
      "ai_explain",
      "aiExplain",
      "ai_decision_explain",
      "aiDecisionExplain",
      "decision_ai_explain",
      "decisionAiExplain",
    ]),
    members: payload.members.map((member) => ({
      id: member.id,
      watchTargetId: member.watch_target_id,
      titleSnapshot: member.title_snapshot,
      candidateKey: member.candidate_key,
      brandHint: member.brand_hint,
      sizeHint: member.size_hint,
      similarityScore: member.similarity_score,
      isCurrentWinner: member.is_current_winner,
      latestResult: member.latest_result ? mapWatchGroupMemberResult(member.latest_result) : null,
    })),
    runs: payload.runs.map(mapWatchGroupRun),
    deliveries: payload.deliveries.map(mapDeliveryEvent),
  };
}

export const apiClient = {
  async listWatchTasks(): Promise<WatchTaskSummary[]> {
    const payload = await request<ApiTaskSummary[]>("/api/watch-tasks");
    return payload.map(mapTaskSummary);
  },

  async getWatchTaskDetail(taskId: string): Promise<WatchTaskDetail> {
    const payload = await request<ApiTaskDetail>(`/api/watch-tasks/${taskId}`);
    return mapTaskDetail(payload);
  },

  async createWatchTask(input: CreateWatchTaskInput): Promise<{ id: string }> {
    return request<{ id: string }>("/api/watch-tasks", {
      method: "POST",
      body: JSON.stringify({
        submitted_url: input.submittedUrl,
        zip_code: input.zipCode,
        cadence_minutes: input.cadenceMinutes,
        threshold_type: input.thresholdType,
        threshold_value: input.thresholdValue,
        cooldown_minutes: input.cooldownMinutes,
        recipient_email: input.recipientEmail,
        compare_handoff: input.compareHandoff
          ? {
              title_snapshot: input.compareHandoff.titleSnapshot,
              store_key: input.compareHandoff.storeKey,
              candidate_key: input.compareHandoff.candidateKey,
              brand_hint: input.compareHandoff.brandHint,
              size_hint: input.compareHandoff.sizeHint,
            }
          : undefined,
      }),
    });
  },

  async updateWatchTask(taskId: string, input: UpdateWatchTaskInput): Promise<{ id: string }> {
    return request<{ id: string }>(`/api/watch-tasks/${taskId}`, {
      method: "PATCH",
      body: JSON.stringify({
        status: input.status,
      }),
    });
  },

  async runWatchTask(taskId: string): Promise<{ id: string; status: string }> {
    return request<{ id: string; status: string }>(`/api/watch-tasks/${taskId}:run-now`, {
      method: "POST",
    });
  },

  async listWatchGroups(): Promise<WatchGroupSummary[]> {
    const payload = await request<ApiWatchGroupSummary[]>("/api/watch-groups");
    return payload.map(mapWatchGroupSummary);
  },

  async getWatchGroupDetail(groupId: string): Promise<WatchGroupDetail> {
    const payload = await request<ApiWatchGroupDetail>(`/api/watch-groups/${groupId}`);
    return mapWatchGroupDetail(payload);
  },

  async createWatchGroup(input: CreateWatchGroupInput): Promise<{ id: string }> {
    return request<{ id: string }>("/api/watch-groups", {
      method: "POST",
      body: JSON.stringify({
        title: input.title,
        zip_code: input.zipCode,
        cadence_minutes: input.cadenceMinutes,
        threshold_type: input.thresholdType,
        threshold_value: input.thresholdValue,
        cooldown_minutes: input.cooldownMinutes,
        recipient_email: input.recipientEmail,
        notifications_enabled: input.notificationsEnabled,
        candidates: input.candidates.map((candidate) => ({
          submitted_url: candidate.submittedUrl,
          title_snapshot: candidate.titleSnapshot,
          store_key: candidate.storeKey,
          candidate_key: candidate.candidateKey,
          brand_hint: candidate.brandHint,
          size_hint: candidate.sizeHint,
          similarity_score: candidate.similarityScore,
        })),
      }),
    });
  },

  async updateWatchGroup(groupId: string, input: UpdateWatchGroupInput): Promise<{ id: string }> {
    return request<{ id: string }>(`/api/watch-groups/${groupId}`, {
      method: "PATCH",
      body: JSON.stringify({
        status: input.status,
      }),
    });
  },

  async runWatchGroup(groupId: string): Promise<{ id: string; status: string }> {
    return request<{ id: string; status: string }>(`/api/watch-groups/${groupId}:run-now`, {
      method: "POST",
    });
  },

  async getNotificationSettings(): Promise<NotificationSettings> {
    const payload = await request<ApiNotificationSettings>("/api/settings/notifications");
    return mapNotificationSettings(payload);
  },

  async getRuntimeReadiness(): Promise<RuntimeReadiness> {
    const payload = await request<ApiRuntimeReadiness>("/api/runtime-readiness");
    return mapRuntimeReadiness(payload);
  },

  async updateNotificationSettings(payload: NotificationSettings): Promise<NotificationSettings> {
    const response = await request<ApiNotificationSettings>("/api/settings/notifications", {
      method: "PATCH",
      body: JSON.stringify({
        default_recipient_email: payload.defaultRecipientEmail,
        cooldown_minutes: payload.cooldownMinutes,
        notifications_enabled: payload.notificationsEnabled,
      }),
    });
    return mapNotificationSettings(response);
  },

  async listNotificationEvents(): Promise<NotificationEvent[]> {
    const payload = await request<ApiNotificationEvent[]>("/api/notifications");
    return payload.map(mapNotificationEvent);
  },

  async getRecoveryInbox(): Promise<RecoveryInbox> {
    const payload = await request<ApiRecoveryInbox>("/api/recovery-inbox");
    return mapRecoveryInbox(payload);
  },

  async listStoreBindings(): Promise<StoreBindingSetting[]> {
    const payload = await request<ApiStoreBindingSetting[]>("/api/settings/store-bindings");
    return payload.map(mapStoreBindingSetting);
  },

  async getStoreOnboardingCockpit(): Promise<StoreOnboardingCockpit> {
    const payload = await request<ApiStoreOnboardingCockpit>("/api/settings/store-onboarding-cockpit");
    return mapStoreOnboardingCockpit(payload);
  },

  async updateStoreBinding(storeKey: string, enabled: boolean): Promise<StoreBindingSetting> {
    const payload = await request<ApiStoreBindingSetting>(`/api/settings/store-bindings/${storeKey}`, {
      method: "PATCH",
      body: JSON.stringify({ enabled }),
    });
    return mapStoreBindingSetting(payload);
  },

  async comparePreview(input: ComparePreviewInput): Promise<ComparePreviewResponse> {
    const payload = await request<ApiComparePreviewResponse>("/api/compare/preview", {
      method: "POST",
      body: JSON.stringify({
        submitted_urls: input.submittedUrls,
        zip_code: input.zipCode,
      }),
    });
    return mapComparePreview(payload);
  },

  async createCompareEvidencePackage(
    input: CreateCompareEvidencePackageInput,
  ): Promise<CompareEvidencePackageArtifact> {
    const payload = await request<ApiCompareEvidencePackageArtifact>("/api/compare/evidence-packages", {
      method: "POST",
      body: JSON.stringify({
        submitted_urls: input.submittedUrls,
        zip_code: input.zipCode,
        compare_result: serializeComparePreview(input.compareResult),
      }),
    });
    return mapCompareEvidencePackageArtifact(payload);
  },
};

export { ApiError };
