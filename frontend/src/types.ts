export type TaskStatus = "active" | "paused" | "error";
export type HealthStatus = "healthy" | "degraded" | "blocked" | "needs_attention";
export type RunStatus = "queued" | "running" | "succeeded" | "failed" | "blocked";
export type ThresholdType = "price_below" | "price_drop_percent" | "effective_price_below";
export type DeliveryStatus = "queued" | "sent" | "delivered" | "bounced" | "failed";
export type RuntimeCheckStatus = "ready" | "action_needed" | "warning" | "no_evidence";
export type AIAssistStatus = "ok" | "disabled" | "unavailable" | "error" | "skipped";

export interface AIAssistEnvelope {
  status: AIAssistStatus;
  title: string | null;
  summary: string | null;
  detail: string | null;
  bullets: string[];
  reasonCode: string | null;
  generatedAt: string | null;
}

export interface WatchTaskSummary {
  id: string;
  normalizedUrl: string;
  storeKey: string;
  title: string;
  status: TaskStatus;
  healthStatus: HealthStatus;
  zipCode?: string;
  cadenceMinutes: number;
  nextRunAt: string | null;
  lastListedPrice: number | null;
  lastEffectivePrice: number | null;
  lastRunStatus: RunStatus | null;
  backoffUntil: string | null;
  manualInterventionRequired: boolean;
}

export interface PricePoint {
  observedAt: string;
  listedPrice: number;
  effectivePrice: number | null;
}

export interface TaskRun {
  id: string;
  status: RunStatus;
  triggeredBy: string | null;
  startedAt: string | null;
  finishedAt: string | null;
  errorCode: string | null;
  errorMessage: string | null;
  artifactRunDir: string | null;
  artifactEvidence: {
    summaryPath: string;
    summaryExists: boolean;
    capturedAt: string | null;
    titleSnapshot: string | null;
    listedPrice: number | null;
    effectivePrice: number | null;
    sourceUrl: string | null;
    deliveryCount: number;
    latestDeliveryStatus: string | null;
    hasCashbackQuote: boolean;
  } | null;
}

export interface DeliveryEvent {
  id: string;
  provider: string;
  recipient: string;
  status: DeliveryStatus;
  createdAt: string;
  sentAt: string | null;
  deliveredAt: string | null;
  bouncedAt: string | null;
}

export interface CashbackQuote {
  provider: string;
  rateLabel: string;
  confidence: number;
  collectedAt: string;
}

export interface LatestIntelligenceSignal {
  previousListedPrice: number | null;
  deltaAmount: number | null;
  deltaPct: number | null;
  isNewLow: boolean;
  anomalyReason: string | null;
  decisionReason: string | null;
}

export interface WatchTaskDetail {
  task: WatchTaskSummary & {
    thresholdType: ThresholdType;
    thresholdValue: number;
    recipientEmail: string;
    zipCode: string;
    cooldownMinutes: number;
    lastRunAt: string | null;
    consecutiveFailures: number;
    lastFailureKind: string | null;
  };
  priceHistory: PricePoint[];
  runs: TaskRun[];
  deliveries: DeliveryEvent[];
  cashbackQuote: CashbackQuote | null;
  latestSignal: LatestIntelligenceSignal | null;
  compareContext: {
    candidateKey: string;
    titleSnapshot: string;
    merchantKey: string;
    brandHint: string | null;
    sizeHint: string | null;
    similarityScore: number;
    canonicalProductId: string | null;
    sourceUrl: string;
  } | null;
}

export interface WatchGroupSummary {
  id: string;
  title: string;
  status: TaskStatus;
  healthStatus: HealthStatus;
  zipCode: string;
  cadenceMinutes: number;
  nextRunAt: string | null;
  lastRunAt: string | null;
  lastRunStatus: RunStatus | null;
  memberCount: number;
  winnerTitle: string | null;
  winnerEffectivePrice: number | null;
  priceSpread: number | null;
  backoffUntil: string | null;
  manualInterventionRequired: boolean;
}

export interface WatchGroupCandidateInput {
  submittedUrl: string;
  titleSnapshot: string;
  storeKey: string;
  candidateKey: string;
  brandHint?: string;
  sizeHint?: string;
  similarityScore: number;
}

export interface WatchGroupMemberResult {
  memberId: string;
  watchTargetId?: string;
  storeKey?: string;
  titleSnapshot?: string;
  candidateKey?: string;
  listedPrice?: number;
  effectivePrice?: number;
  cashbackAmount?: number;
  sourceUrl?: string;
  observedAt?: string;
  status: RunStatus;
  errorCode?: string;
  errorMessage?: string;
}

export interface WatchGroupMember {
  id: string;
  watchTargetId: string;
  titleSnapshot: string;
  candidateKey: string;
  brandHint: string | null;
  sizeHint: string | null;
  similarityScore: number;
  isCurrentWinner: boolean;
  latestResult: WatchGroupMemberResult | null;
}

export interface WatchGroupRun {
  id: string;
  status: RunStatus;
  startedAt: string | null;
  finishedAt: string | null;
  errorMessage: string | null;
  winnerMemberId: string | null;
  winnerEffectivePrice: number | null;
  runnerUpMemberId: string | null;
  runnerUpEffectivePrice: number | null;
  priceSpread: number | null;
  decisionReason: string | null;
  memberResults: WatchGroupMemberResult[];
  artifactRunDir: string | null;
}

export interface WatchGroupDecisionExplainMember {
  memberId: string;
  title: string;
  storeKey: string | null;
  listedPrice: number | null;
  effectivePrice: number | null;
  cashbackAmount: number | null;
  status: RunStatus | null;
}

export interface WatchGroupDecisionExplain {
  headline: string;
  decisionReason: string | null;
  sortBasis: string;
  winner: WatchGroupDecisionExplainMember | null;
  runnerUp: WatchGroupDecisionExplainMember | null;
  comparison: {
    priceSpread: number | null;
    effectivePriceDelta: number | null;
    listedPriceDelta: number | null;
    cashbackDelta: number | null;
  } | null;
  candidateOutcomes: {
    successfulCount: number;
    blockedCount: number;
    failedCount: number;
  };
  reliability: "strong" | "caution" | "weak";
  riskNotes: string[];
}

export interface WatchGroupDetail {
  group: WatchGroupSummary & {
    thresholdType: ThresholdType;
    thresholdValue: number;
    cooldownMinutes: number;
    recipientEmail: string;
    notificationsEnabled: boolean;
    lastSuccessAt: string | null;
    lastErrorCode: string | null;
    lastErrorMessage: string | null;
    consecutiveFailures: number;
    lastFailureKind: string | null;
    currentWinnerMemberId: string | null;
    currentWinnerTitle: string | null;
    currentWinnerEffectivePrice: number | null;
    decisionReason: string | null;
  };
  decisionExplain: WatchGroupDecisionExplain;
  aiExplain: AIAssistEnvelope;
  members: WatchGroupMember[];
  runs: WatchGroupRun[];
  deliveries: DeliveryEvent[];
}

export interface NotificationSettings {
  defaultRecipientEmail: string;
  cooldownMinutes: number;
  notificationsEnabled: boolean;
}

export interface RuntimeReadinessCheck {
  key: string;
  label: string;
  status: RuntimeCheckStatus;
  summary: string;
  detail: string | null;
}

export interface RuntimeReadiness {
  overallStatus: RuntimeCheckStatus;
  headline: string;
  generatedAt: string | null;
  checks: RuntimeReadinessCheck[];
}

interface RecoveryInboxItemBase {
  id: string;
  title: string;
  status: TaskStatus;
  healthStatus: HealthStatus;
  nextRunAt: string | null;
  backoffUntil: string | null;
  manualInterventionRequired: boolean;
  consecutiveFailures: number;
  lastFailureKind: string | null;
  lastErrorCode: string | null;
  lastErrorMessage: string | null;
  lastRunAt: string | null;
  reason: string;
  recommendedAction: string;
}

export interface RecoveryTaskItem extends RecoveryInboxItemBase {
  kind: "task";
  normalizedUrl: string;
  storeKey: string;
}

export interface RecoveryGroupItem extends RecoveryInboxItemBase {
  kind: "group";
  zipCode: string;
  memberCount: number;
  winnerTitle: string | null;
  aiCopilot: AIAssistEnvelope;
}

export interface RecoveryInbox {
  tasks: RecoveryTaskItem[];
  groups: RecoveryGroupItem[];
}

export interface NotificationEvent extends DeliveryEvent {
  watchTaskId: string | null;
  watchGroupId: string | null;
  messageId: string | null;
}

export interface StoreBindingSetting {
  storeKey: string;
  enabled: boolean;
  adapterClass: string;
  supportChannel: string;
  supportTier: string;
  supportReasonCodes: string[];
  nextStepCodes: string[];
  contractTestPaths: string[];
  discoveryMode: string;
  parseMode: string;
  regionSensitive: boolean;
  cashbackSupported: boolean;
  supportsCompareIntake: boolean;
  supportsWatchTask: boolean;
  supportsWatchGroup: boolean;
  supportsRecovery: boolean;
}

export interface StoreOnboardingChecklistItem {
  key: string;
  label: string;
  detail: string;
}

export interface StoreOnboardingStoreRow extends StoreBindingSetting {
  supportSummary?: string;
  nextOnboardingStep?: string;
  contractStatus: "ready" | "attention_needed";
  missingCapabilities: string[];
  contractGaps: string[];
  sourceOfTruthFiles: string[];
}

export interface StoreOnboardingRegistryHealth {
  registryStoreCount: number;
  capabilityStoreCount: number;
  bindingStoreCount: number;
  registryParityOk: boolean;
  registryOnlyStoreKeys: string[];
  manifestOnlyStoreKeys: string[];
  bindingOnlyStoreKeys: string[];
}

export interface StoreOnboardingCockpit {
  generatedAt: string;
  summary: {
    supportedStoreCount: number;
    officialFullCount: number;
    officialPartialCount: number;
    officialInProgressCount: number;
    enabledStoreCount: number;
    disabledStoreCount: number;
    compareIntakeSupportedCount: number;
    cashbackSupportedCount: number;
    watchTaskSupportedCount: number;
    watchGroupSupportedCount: number;
    recoverySupportedCount: number;
    regionSensitiveCount: number;
  };
  registryHealth: StoreOnboardingRegistryHealth;
  stores: StoreOnboardingStoreRow[];
  onboardingChecklist: StoreOnboardingChecklistItem[];
  verificationCommands: string[];
  truthSources: string[];
  officialSupportTiers: string[];
  limitedSupportContract: string[];
  limitedSupportLane: {
    supportChannel: string;
    supportTier: string;
    summary: string;
    supportedActions: string[];
    blockedActions: string[];
    contractLines: string[];
    sourceOfTruthFiles: string[];
  };
}

export interface CreateWatchTaskInput {
  submittedUrl: string;
  zipCode: string;
  cadenceMinutes: number;
  thresholdType: ThresholdType;
  thresholdValue: number;
  cooldownMinutes: number;
  recipientEmail: string;
  compareHandoff?: {
    titleSnapshot: string;
    storeKey: string;
    candidateKey: string;
    brandHint?: string;
    sizeHint?: string;
  };
}

export interface CreateWatchGroupInput {
  title?: string;
  zipCode: string;
  cadenceMinutes: number;
  thresholdType: ThresholdType;
  thresholdValue: number;
  cooldownMinutes: number;
  recipientEmail: string;
  notificationsEnabled: boolean;
  candidates: WatchGroupCandidateInput[];
}

export interface UpdateWatchTaskInput {
  status?: TaskStatus;
}

export interface UpdateWatchGroupInput {
  status?: TaskStatus;
}

export interface WatchTaskDraft {
  submittedUrl: string;
  normalizedUrl: string;
  title: string;
  storeKey: string;
  candidateKey: string;
  brandHint?: string;
  sizeHint?: string;
  defaultRecipientEmail: string;
  zipCode: string;
}

export interface ComparePreviewInput {
  submittedUrls: string[];
  zipCode: string;
}

export interface ComparePreviewOffer {
  storeId: string;
  productKey: string;
  dealId: string;
  title: string;
  url: string;
  price: number;
  originalPrice: number | null;
  fetchAt: string;
  context: {
    region: string;
    currency: string;
    isMember: boolean;
  };
  unitPriceInfo: Record<string, string | number | boolean>;
}

export interface ComparePreviewComparison {
  submittedUrl: string;
  supported: boolean;
  storeKey?: string;
  normalizedUrl?: string;
  fetchSucceeded?: boolean;
  errorCode?: string;
  candidateKey?: string;
  brandHint?: string;
  sizeHint?: string;
  offer?: ComparePreviewOffer;
  supportContract?: {
    supportChannel: string;
    storeSupportTier: string;
    supportReasonCodes: string[];
    nextStepCodes: string[];
    intakeStatus: string;
    summary: string;
    nextStep: string;
    canSaveCompareEvidence: boolean;
    canCreateWatchTask: boolean;
    canCreateWatchGroup: boolean;
    cashbackSupported: boolean;
    notificationsSupported: boolean;
    missingCapabilities: string[];
  };
}

export interface ComparePreviewMatch {
  leftStoreKey: string;
  leftProductKey: string;
  rightStoreKey: string;
  rightProductKey: string;
  score: number;
  titleSimilarity?: number;
  brandSignal?: "match" | "mismatch" | "unknown";
  sizeSignal?: "match" | "mismatch" | "unknown";
  productKeySignal?: string;
  leftCandidateKey?: string;
  rightCandidateKey?: string;
  whyLike?: string[];
  whyUnlike?: string[];
}

export type CompareRecommendationVerdict = "wait" | "recheck_later" | "insufficient_evidence";

export interface CompareRecommendationEvidenceRef {
  code: string;
  label: string;
  anchor: string;
}

export interface CompareRecommendation {
  contractVersion: string;
  surface: string;
  scope: string;
  visibility: string;
  status: "issued" | "abstained";
  verdict: CompareRecommendationVerdict;
  verdictVocabulary: string[];
  headline: string;
  summary: string;
  basis: string[];
  uncertaintyNotes: string[];
  abstention: {
    active: boolean;
    code: string | null;
    reason: string | null;
  };
  evidenceRefs: CompareRecommendationEvidenceRef[];
  deterministicPrimaryNote: string;
  feedbackBoundary: string;
  overrideBoundary: string;
  buyNowBlocked: boolean;
}

export interface ComparePreviewResponse {
  submittedCount: number;
  resolvedCount: number;
  comparisons: ComparePreviewComparison[];
  matches: ComparePreviewMatch[];
  recommendation: CompareRecommendation;
  recommendedNextStepHint?: CompareEvidenceNextStepHint;
  riskNotes?: string[];
  riskNoteItems?: { code: string; message: string }[];
  aiExplain: AIAssistEnvelope;
}

export interface CompareEvidenceNextStepHint {
  action: string;
  reasonCode: string;
  summary: string;
  successfulCandidateCount: number;
  strongestMatchScore: number;
}

export interface CompareEvidenceArtifactSummary {
  artifactId: string;
  artifactKind: string;
  storageScope: string;
  createdAt: string;
  savedAt: string;
  headline: string;
  submittedCount: number;
  resolvedCount: number;
  successfulCandidateCount: number;
  strongestMatchScore: number;
  riskNotes: string[];
  recommendedNextStepHint: CompareEvidenceNextStepHint;
  detailUrl: string;
  htmlUrl: string;
}

export interface CompareEvidenceArtifactDetail {
  artifactId: string;
  artifactKind: string;
  storageScope: string;
  savedAt: string;
  artifactPath: string;
  htmlPath: string;
  sourceOfTruthNote: string;
  submittedInputs: {
    submittedUrls: string[];
    zipCode: string;
  };
  submittedCount: number;
  resolvedCount: number;
  comparisons: ComparePreviewComparison[];
  matches: ComparePreviewMatch[];
  recommendation: CompareRecommendation;
  recommendedNextStepHint: CompareEvidenceNextStepHint;
  riskNotes: string[];
  summary: CompareEvidenceArtifactSummary;
}

export interface CompareEvidencePackageArtifact {
  id: string;
  createdAt: string | null;
  htmlUrl: string | null;
  summaryPath: string | null;
}

export interface CreateCompareEvidencePackageInput {
  submittedUrls: string[];
  zipCode: string;
  compareResult: ComparePreviewResponse;
}

export interface SavedCompareEvidencePackage {
  id: string;
  label: string;
  savedAt: string;
  zipCode: string;
  submittedUrls: string[];
  submittedCount: number;
  resolvedCount: number;
  decisionSummary: string;
  riskSummary: string;
  recommendedAction: string;
  compareResult: ComparePreviewResponse;
  runtimeArtifact: CompareEvidencePackageArtifact | null;
}
