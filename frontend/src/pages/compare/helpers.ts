import { z } from "zod";
import { formatDateTime, formatNumber, interpolate, type AppLocale } from "../../lib/i18n";
import type {
  AIAssistEnvelope,
  CompareEvidencePackageArtifact,
  ComparePreviewComparison,
  ComparePreviewMatch,
  ComparePreviewResponse,
  SavedCompareEvidencePackage,
  ThresholdType,
  WatchGroupCandidateInput,
} from "../../types";
import {
  COMPARE_CAPABILITY_COPY,
  COMPARE_COPY,
  EVIDENCE_STORAGE_KEY,
  type DraftMessage,
  REVIEW_MATCH_SCORE,
  STRONG_MATCH_SCORE,
} from "./copy";

export type DecisionTone = "success" | "warning" | "error" | "info";

export interface CompareDecisionBoard {
  tone: DecisionTone;
  headline: string;
  summary: string;
  recommendedAction: string;
  riskSummary: string;
  risks: string[];
  bestCandidate: ComparePreviewComparison | null;
  bestMatch: ComparePreviewMatch | null;
  bestListedPrice: number | null;
  unsupportedCount: number;
  fetchFailureCount: number;
  weakMatchCount: number;
  groupReadyCount: number;
}

export function draft(locale: AppLocale, message: DraftMessage, values?: Record<string, string | number>) {
  const template = message[locale] ?? message.en;
  return values ? interpolate(template, values) : template;
}

export function resolveCompareCopy(
  t: (key: string) => string,
  locale: AppLocale,
  key: string,
  fallback: DraftMessage,
  values?: Record<string, string | number>,
): string {
  const translated = t(key);
  const template = translated === key ? fallback[locale] ?? fallback.en : translated;
  return values ? interpolate(template, values) : template;
}

export function formatOneDecimal(locale: AppLocale, value: number | null | undefined, fallback = "--"): string {
  return formatNumber(locale, value, fallback, {
    maximumFractionDigits: 1,
    minimumFractionDigits: 1,
  });
}

export function formatCapabilityLabel(locale: AppLocale, t: (key: string) => string, capability: string): string {
  switch (capability) {
    case "official_store_registry":
      return resolveCompareCopy(
        t,
        locale,
        "compare.candidatePanel.capability.officialStoreRegistry",
        COMPARE_CAPABILITY_COPY.officialStoreRegistry,
      );
    case "manifest_entry":
      return resolveCompareCopy(
        t,
        locale,
        "compare.candidatePanel.capability.manifestEntry",
        COMPARE_CAPABILITY_COPY.manifestEntry,
      );
    case "compare_intake":
      return resolveCompareCopy(
        t,
        locale,
        "compare.candidatePanel.capability.compareIntake",
        COMPARE_CAPABILITY_COPY.compareIntake,
      );
    case "watch_task":
      return resolveCompareCopy(
        t,
        locale,
        "compare.candidatePanel.capability.watchTask",
        COMPARE_CAPABILITY_COPY.watchTask,
      );
    case "watch_group":
      return resolveCompareCopy(
        t,
        locale,
        "compare.candidatePanel.capability.watchGroup",
        COMPARE_CAPABILITY_COPY.watchGroup,
      );
    case "recovery":
      return resolveCompareCopy(
        t,
        locale,
        "compare.candidatePanel.capability.recovery",
        COMPARE_CAPABILITY_COPY.recovery,
      );
    case "cashback":
      return resolveCompareCopy(
        t,
        locale,
        "compare.candidatePanel.capability.cashback",
        COMPARE_CAPABILITY_COPY.cashback,
      );
    default:
      return capability.split("_").join(" ");
  }
}

export function resolveUiMessage(message: string, t: (key: string) => string): string {
  const translated = t(message);
  return translated === message ? message : translated;
}

export function normalizeUrls(raw: string): string[] {
  return raw
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function defaultGroupTitle(
  candidates: WatchGroupCandidateInput[],
  locale: AppLocale,
  t: (key: string) => string,
): string {
  if (!candidates.length) {
    return "";
  }
  return `${candidates[0].titleSnapshot} ${resolveCompareCopy(
    t,
    locale,
    "compare.groupBuilder.defaultTitleSuffix",
    COMPARE_COPY.groupBuilder.defaultTitleSuffix,
  )}`;
}

export function buildCandidateScoreIndex(matches: ComparePreviewMatch[]): Record<string, number> {
  const scores: Record<string, number> = {};
  for (const match of matches) {
    if (match.leftCandidateKey) {
      scores[match.leftCandidateKey] = Math.max(scores[match.leftCandidateKey] ?? 0, match.score);
    }
    if (match.rightCandidateKey) {
      scores[match.rightCandidateKey] = Math.max(scores[match.rightCandidateKey] ?? 0, match.score);
    }
  }
  return scores;
}

export function getComparisonLabel(item: ComparePreviewComparison): string {
  return item.offer?.title ?? item.normalizedUrl ?? item.submittedUrl;
}

export function getSupportTierLabel(locale: AppLocale, t: (key: string) => string, item: ComparePreviewComparison): string | null {
  const tier = item.supportContract?.storeSupportTier;
  if (!tier) {
    return null;
  }
  switch (tier) {
    case "official_full":
      return resolveCompareCopy(t, locale, "compare.candidatePanel.tier.officialFull", COMPARE_COPY.candidatePanel.tier.officialFull);
    case "official_partial":
      return resolveCompareCopy(
        t,
        locale,
        "compare.candidatePanel.tier.officialPartial",
        COMPARE_COPY.candidatePanel.tier.officialPartial,
      );
    case "official_in_progress":
      return resolveCompareCopy(
        t,
        locale,
        "compare.candidatePanel.tier.officialInProgress",
        COMPARE_COPY.candidatePanel.tier.officialInProgress,
      );
    default:
      return resolveCompareCopy(
        t,
        locale,
        "compare.candidatePanel.tier.limitedUnofficial",
        COMPARE_COPY.candidatePanel.tier.limitedUnofficial,
      );
  }
}

export function getComparisonStatusLabel(locale: AppLocale, t: (key: string) => string, item: ComparePreviewComparison): string {
  switch (item.supportContract?.intakeStatus) {
    case "store_disabled":
      return resolveCompareCopy(t, locale, "compare.candidatePanel.storeDisabled", COMPARE_COPY.candidatePanel.storeDisabled);
    case "offer_fetch_failed":
      return resolveCompareCopy(t, locale, "compare.candidatePanel.fetchFailed", COMPARE_COPY.candidatePanel.fetchFailed);
    case "unsupported_store_host":
    case "unsupported_store_path":
      return resolveCompareCopy(t, locale, "compare.candidatePanel.unsupported", COMPARE_COPY.candidatePanel.unsupported);
    default:
      return item.fetchSucceeded
        ? resolveCompareCopy(t, locale, "compare.candidatePanel.fetched", COMPARE_COPY.candidatePanel.fetched)
        : item.supported
          ? resolveCompareCopy(t, locale, "compare.candidatePanel.fetchFailed", COMPARE_COPY.candidatePanel.fetchFailed)
          : resolveCompareCopy(t, locale, "compare.candidatePanel.unsupported", COMPARE_COPY.candidatePanel.unsupported);
  }
}

export function getComparisonStatusTone(item: ComparePreviewComparison): string {
  switch (item.supportContract?.intakeStatus) {
    case "supported":
      return item.fetchSucceeded ? "badge-success" : "badge-warning";
    case "store_disabled":
      return "badge-outline";
    case "offer_fetch_failed":
      return "badge-warning";
    default:
      return "badge-error";
  }
}

export function getComparisonSummary(locale: AppLocale, t: (key: string) => string, item: ComparePreviewComparison): string {
  switch (item.supportContract?.intakeStatus) {
    case "supported":
      if (item.supportContract.storeSupportTier === "official_full") {
        return resolveCompareCopy(
          t,
          locale,
          "compare.candidatePanel.officialFullSummary",
          COMPARE_COPY.candidatePanel.officialFullSummary,
        );
      }
      if (item.supportContract.storeSupportTier === "official_partial") {
        return resolveCompareCopy(
          t,
          locale,
          "compare.candidatePanel.officialPartialSummary",
          COMPARE_COPY.candidatePanel.officialPartialSummary,
        );
      }
      return resolveCompareCopy(t, locale, "compare.candidatePanel.fetchedSummary", COMPARE_COPY.candidatePanel.fetchedSummary);
    case "offer_fetch_failed":
      return resolveCompareCopy(t, locale, "compare.candidatePanel.fetchFailedSummary", COMPARE_COPY.candidatePanel.fetchFailedSummary);
    case "store_disabled":
      return resolveCompareCopy(t, locale, "compare.candidatePanel.storeDisabledSummary", COMPARE_COPY.candidatePanel.storeDisabledSummary);
    case "unsupported_store_path":
      return resolveCompareCopy(t, locale, "compare.candidatePanel.unsupportedPathSummary", COMPARE_COPY.candidatePanel.unsupportedPathSummary);
    case "unsupported_store_host":
      return resolveCompareCopy(t, locale, "compare.candidatePanel.unsupportedHostSummary", COMPARE_COPY.candidatePanel.unsupportedHostSummary);
    default:
      return resolveCompareCopy(t, locale, "compare.candidatePanel.unsupportedSummary", COMPARE_COPY.candidatePanel.unsupportedSummary);
  }
}

export function getSupportActionBuckets(
  locale: AppLocale,
  t: (key: string) => string,
  item: ComparePreviewComparison,
): { allowed: string[]; blocked: string[] } {
  const contract = item.supportContract;
  if (!contract) {
    return { allowed: [], blocked: [] };
  }

  const labels = {
    saveCompareEvidence: resolveCompareCopy(
      t,
      locale,
      "compare.candidatePanel.saveCompareEvidence",
      COMPARE_COPY.candidatePanel.saveCompareEvidence,
    ),
    createWatchTask: resolveCompareCopy(
      t,
      locale,
      "compare.candidatePanel.createWatchTaskAction",
      COMPARE_COPY.candidatePanel.createWatchTaskAction,
    ),
    createWatchGroup: resolveCompareCopy(
      t,
      locale,
      "compare.candidatePanel.createWatchGroupAction",
      COMPARE_COPY.candidatePanel.createWatchGroupAction,
    ),
    cashback: resolveCompareCopy(
      t,
      locale,
      "compare.candidatePanel.cashbackAction",
      COMPARE_COPY.candidatePanel.cashbackAction,
    ),
    notifications: resolveCompareCopy(
      t,
      locale,
      "compare.candidatePanel.notificationsAction",
      COMPARE_COPY.candidatePanel.notificationsAction,
    ),
  };

  const allowed: string[] = [];
  const blocked: string[] = [];

  if (contract.canSaveCompareEvidence) {
    allowed.push(labels.saveCompareEvidence);
  } else {
    blocked.push(labels.saveCompareEvidence);
  }
  if (contract.canCreateWatchTask) {
    allowed.push(labels.createWatchTask);
  } else {
    blocked.push(labels.createWatchTask);
  }
  if (contract.canCreateWatchGroup) {
    allowed.push(labels.createWatchGroup);
  } else {
    blocked.push(labels.createWatchGroup);
  }
  if (contract.cashbackSupported) {
    allowed.push(labels.cashback);
  } else {
    blocked.push(labels.cashback);
  }
  if (contract.notificationsSupported) {
    allowed.push(labels.notifications);
  } else {
    blocked.push(labels.notifications);
  }

  return { allowed, blocked };
}

function getBestCandidate(result: ComparePreviewResponse | null): ComparePreviewComparison | null {
  if (!result) {
    return null;
  }
  return (
    [...result.comparisons]
      .filter((item) => item.fetchSucceeded && item.offer)
      .sort((left, right) => (left.offer?.price ?? Number.POSITIVE_INFINITY) - (right.offer?.price ?? Number.POSITIVE_INFINITY))[0] ??
    null
  );
}

function getBestMatch(result: ComparePreviewResponse | null): ComparePreviewMatch | null {
  if (!result?.matches.length) {
    return null;
  }
  return [...result.matches].sort((left, right) => right.score - left.score)[0] ?? null;
}

export function buildDecisionBoard(
  locale: AppLocale,
  t: (key: string) => string,
  result: ComparePreviewResponse,
  successfulCandidates: WatchGroupCandidateInput[],
  groupReadyCandidates: WatchGroupCandidateInput[],
): CompareDecisionBoard {
  const bestCandidate = getBestCandidate(result);
  const bestMatch = getBestMatch(result);
  const unsupportedCount = result.comparisons.filter((item) =>
    ["unsupported_store_host", "unsupported_store_path"].includes(item.supportContract?.intakeStatus ?? ""),
  ).length;
  const disabledCount = result.comparisons.filter((item) => item.supportContract?.intakeStatus === "store_disabled").length;
  const fetchFailureCount = result.comparisons.filter((item) => item.supported && !item.fetchSucceeded).length;
  const weakMatchCount = result.matches.filter((item) => item.score < REVIEW_MATCH_SCORE).length;
  const bestCandidateLabel = bestCandidate
    ? getComparisonLabel(bestCandidate)
    : resolveCompareCopy(t, locale, "compare.decision.noResolvedCandidate", COMPARE_COPY.decision.noResolvedCandidate);
  const bestMatchLabel = bestMatch
    ? `${bestMatch.leftStoreKey} vs ${bestMatch.rightStoreKey}`
    : resolveCompareCopy(t, locale, "compare.decision.noConfidentPair", COMPARE_COPY.decision.noConfidentPair);

  const risks: string[] = [];
  if (unsupportedCount) {
    risks.push(resolveCompareCopy(t, locale, "compare.decision.riskUnsupported", COMPARE_COPY.decision.riskUnsupported, {
      count: unsupportedCount,
      plural: unsupportedCount === 1 ? "" : "s",
      pluralZh: "",
    }));
  }
  if (disabledCount) {
    risks.push(resolveCompareCopy(t, locale, "compare.decision.riskStoreDisabled", COMPARE_COPY.decision.riskStoreDisabled, {
      count: disabledCount,
      plural: disabledCount === 1 ? "" : "s",
      pluralZh: "",
    }));
  }
  if (fetchFailureCount) {
    risks.push(resolveCompareCopy(t, locale, "compare.decision.riskFetchFailed", COMPARE_COPY.decision.riskFetchFailed, {
      count: fetchFailureCount,
      plural: fetchFailureCount === 1 ? "" : "s",
      pluralZh: "",
    }));
  }
  if (!result.matches.length && groupReadyCandidates.length >= 2) {
    risks.push(resolveCompareCopy(t, locale, "compare.decision.riskNoPairScore", COMPARE_COPY.decision.riskNoPairScore));
  }
  if (bestMatch && bestMatch.score < REVIEW_MATCH_SCORE) {
    risks.push(
      resolveCompareCopy(t, locale, "compare.decision.riskWeakStrongest", COMPARE_COPY.decision.riskWeakStrongest, {
        score: formatOneDecimal(locale, bestMatch.score),
      }),
    );
  }
  if (groupReadyCandidates.length < 2) {
    risks.push(resolveCompareCopy(t, locale, "compare.decision.riskNeedTwoCandidates", COMPARE_COPY.decision.riskNeedTwoCandidates));
  }
  if (!risks.length && weakMatchCount) {
    risks.push(resolveCompareCopy(t, locale, "compare.decision.riskLowerConfidence", COMPARE_COPY.decision.riskLowerConfidence, {
      count: weakMatchCount,
      plural: weakMatchCount === 1 ? "" : "s",
      pluralZh: "",
    }));
  }
  if (!risks.length) {
    risks.push(resolveCompareCopy(t, locale, "compare.decision.riskNoBlocker", COMPARE_COPY.decision.riskNoBlocker));
  }

  if (!successfulCandidates.length) {
    return {
      tone: "error",
      headline: resolveCompareCopy(t, locale, "compare.decision.state.noDecisionHeadline", COMPARE_COPY.decision.state.noDecisionHeadline),
      summary: resolveCompareCopy(t, locale, "compare.decision.state.noDecisionSummary", COMPARE_COPY.decision.state.noDecisionSummary),
      recommendedAction: resolveCompareCopy(t, locale, "compare.decision.state.noDecisionAction", COMPARE_COPY.decision.state.noDecisionAction),
      riskSummary: risks[0],
      risks,
      bestCandidate,
      bestMatch,
      bestListedPrice: null,
      unsupportedCount,
      fetchFailureCount,
      weakMatchCount,
      groupReadyCount: groupReadyCandidates.length,
    };
  }

  if (successfulCandidates.length === 1) {
    return {
      tone: "warning",
      headline: resolveCompareCopy(t, locale, "compare.decision.state.oneCandidateHeadline", COMPARE_COPY.decision.state.oneCandidateHeadline),
      summary: resolveCompareCopy(t, locale, "compare.decision.state.oneCandidateSummary", COMPARE_COPY.decision.state.oneCandidateSummary, { bestCandidateLabel }),
      recommendedAction: resolveCompareCopy(t, locale, "compare.decision.state.oneCandidateAction", COMPARE_COPY.decision.state.oneCandidateAction),
      riskSummary: risks[0],
      risks,
      bestCandidate,
      bestMatch,
      bestListedPrice: bestCandidate?.offer?.price ?? null,
      unsupportedCount,
      fetchFailureCount,
      weakMatchCount,
      groupReadyCount: groupReadyCandidates.length,
    };
  }

  if (groupReadyCandidates.length < 2) {
    return {
      tone: "warning",
      headline: resolveCompareCopy(t, locale, "compare.decision.state.reviewHeadline", COMPARE_COPY.decision.state.reviewHeadline),
      summary: resolveCompareCopy(t, locale, "compare.decision.state.reviewSummary", COMPARE_COPY.decision.state.reviewSummary, { bestCandidateLabel, bestMatchLabel }),
      recommendedAction: resolveCompareCopy(t, locale, "compare.decision.state.reviewAction", COMPARE_COPY.decision.state.reviewAction),
      riskSummary: risks[0],
      risks,
      bestCandidate,
      bestMatch,
      bestListedPrice: bestCandidate?.offer?.price ?? null,
      unsupportedCount,
      fetchFailureCount,
      weakMatchCount,
      groupReadyCount: groupReadyCandidates.length,
    };
  }

  if (bestMatch && bestMatch.score >= STRONG_MATCH_SCORE) {
    return {
      tone: "success",
      headline: resolveCompareCopy(t, locale, "compare.decision.state.strongHeadline", COMPARE_COPY.decision.state.strongHeadline),
      summary: resolveCompareCopy(t, locale, "compare.decision.state.strongSummary", COMPARE_COPY.decision.state.strongSummary, { bestCandidateLabel, bestMatchLabel }),
      recommendedAction: resolveCompareCopy(t, locale, "compare.decision.state.strongAction", COMPARE_COPY.decision.state.strongAction),
      riskSummary: risks[0],
      risks,
      bestCandidate,
      bestMatch,
      bestListedPrice: bestCandidate?.offer?.price ?? null,
      unsupportedCount,
      fetchFailureCount,
      weakMatchCount,
      groupReadyCount: groupReadyCandidates.length,
    };
  }

  if (bestMatch && bestMatch.score >= REVIEW_MATCH_SCORE) {
    return {
      tone: "warning",
      headline: resolveCompareCopy(t, locale, "compare.decision.state.reviewHeadline", COMPARE_COPY.decision.state.reviewHeadline),
      summary: resolveCompareCopy(t, locale, "compare.decision.state.reviewSummary", COMPARE_COPY.decision.state.reviewSummary, { bestCandidateLabel, bestMatchLabel }),
      recommendedAction: resolveCompareCopy(t, locale, "compare.decision.state.reviewAction", COMPARE_COPY.decision.state.reviewAction),
      riskSummary: risks[0],
      risks,
      bestCandidate,
      bestMatch,
      bestListedPrice: bestCandidate?.offer?.price ?? null,
      unsupportedCount,
      fetchFailureCount,
      weakMatchCount,
      groupReadyCount: groupReadyCandidates.length,
    };
  }

  return {
    tone: "error",
    headline: resolveCompareCopy(t, locale, "compare.decision.state.mixedHeadline", COMPARE_COPY.decision.state.mixedHeadline),
    summary: resolveCompareCopy(t, locale, "compare.decision.state.mixedSummary", COMPARE_COPY.decision.state.mixedSummary, { bestCandidateLabel }),
    recommendedAction: resolveCompareCopy(t, locale, "compare.decision.state.mixedAction", COMPARE_COPY.decision.state.mixedAction),
    riskSummary: risks[0],
    risks,
    bestCandidate,
    bestMatch,
    bestListedPrice: bestCandidate?.offer?.price ?? null,
    unsupportedCount,
    fetchFailureCount,
    weakMatchCount,
    groupReadyCount: groupReadyCandidates.length,
  };
}

export function decisionBadgeClass(tone: DecisionTone): string {
  switch (tone) {
    case "success":
      return "badge-success";
    case "warning":
      return "badge-warning";
    case "error":
      return "badge-error";
    case "info":
      return "badge-outline";
  }
}

export function decisionAlertClass(tone: DecisionTone): string {
  switch (tone) {
    case "success":
      return "alert-success";
    case "warning":
      return "alert-warning";
    case "error":
      return "alert-error";
    case "info":
      return "alert-info";
  }
}

export function aiAssistBadgeClass(status: AIAssistEnvelope["status"]): string {
  switch (status) {
    case "ok":
      return "badge-success";
    case "disabled":
      return "badge-outline";
    case "error":
      return "badge-error";
    case "skipped":
      return "badge-warning";
    case "unavailable":
      return "badge-outline";
  }
}

export function aiAssistLabel(status: AIAssistEnvelope["status"], locale: AppLocale, t: (key: string) => string): string {
  return resolveCompareCopy(
    t,
    locale,
    `compare.decision.ai.badge.${status}`,
    COMPARE_COPY.decision.ai.badge[status],
  );
}

export function compareAIHeadline(status: AIAssistEnvelope["status"], locale: AppLocale, t: (key: string) => string): string {
  return resolveCompareCopy(
    t,
    locale,
    `compare.decision.ai.headline.${status}`,
    COMPARE_COPY.decision.ai.headline[status],
  );
}

export function compareAISummary(status: AIAssistEnvelope["status"], locale: AppLocale, t: (key: string) => string): string {
  switch (status) {
    case "ok":
      return resolveCompareCopy(t, locale, "compare.decision.stats.aiNote", COMPARE_COPY.decision.stats.aiNote);
    case "disabled":
    case "error":
    case "skipped":
    case "unavailable":
      return resolveCompareCopy(
        t,
        locale,
        `compare.decision.ai.summary.${status}`,
        COMPARE_COPY.decision.ai.summary[status],
      );
  }
}

export function loadSavedEvidencePackages(): SavedCompareEvidencePackage[] {
  if (typeof window === "undefined") {
    return [];
  }
  try {
    const raw = window.localStorage.getItem(EVIDENCE_STORAGE_KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as SavedCompareEvidencePackage[]) : [];
  } catch {
    return [];
  }
}

function buildEvidencePackageLabel(
  result: ComparePreviewResponse,
  zipCode: string,
  locale: AppLocale,
  t: (key: string) => string,
): string {
  const bestCandidate = getBestCandidate(result);
  if (bestCandidate?.offer?.title) {
    return resolveCompareCopy(t, locale, "compare.saved.labelWithTitle", COMPARE_COPY.saved.labelWithTitle, {
      title: bestCandidate.offer.title,
      zipCode,
    });
  }
  return resolveCompareCopy(t, locale, "compare.saved.labelFallback", COMPARE_COPY.saved.labelFallback, { zipCode });
}

export function buildShareSummary(locale: AppLocale, t: (key: string) => string, payload: SavedCompareEvidencePackage): string {
  return [
    resolveCompareCopy(t, locale, "compare.saved.shareTitle", COMPARE_COPY.saved.shareTitle),
    resolveCompareCopy(t, locale, "compare.saved.shareLabel", COMPARE_COPY.saved.shareLabel, { value: payload.label }),
    resolveCompareCopy(t, locale, "compare.saved.shareSavedAt", COMPARE_COPY.saved.shareSavedAt, { value: formatDateTime(locale, payload.savedAt) }),
    resolveCompareCopy(t, locale, "compare.saved.shareZip", COMPARE_COPY.saved.shareZip, { value: payload.zipCode }),
    resolveCompareCopy(t, locale, "compare.saved.shareSubmitted", COMPARE_COPY.saved.shareSubmitted, {
      value: formatNumber(locale, payload.submittedCount, "0"),
    }),
    resolveCompareCopy(t, locale, "compare.saved.shareResolved", COMPARE_COPY.saved.shareResolved, {
      value: formatNumber(locale, payload.resolvedCount, "0"),
    }),
    resolveCompareCopy(t, locale, "compare.saved.shareDecision", COMPARE_COPY.saved.shareDecision, { value: payload.decisionSummary }),
    resolveCompareCopy(t, locale, "compare.saved.shareRisk", COMPARE_COPY.saved.shareRisk, { value: payload.riskSummary }),
    resolveCompareCopy(t, locale, "compare.saved.shareAction", COMPARE_COPY.saved.shareAction, { value: payload.recommendedAction }),
    payload.runtimeArtifact?.htmlUrl
      ? resolveCompareCopy(t, locale, "compare.saved.shareRuntimeReady", COMPARE_COPY.saved.shareRuntimeReady, { value: payload.runtimeArtifact.htmlUrl })
      : resolveCompareCopy(t, locale, "compare.saved.shareRuntimeMissing", COMPARE_COPY.saved.shareRuntimeMissing),
  ].join("\n");
}

export function buildSavedEvidencePackage(input: {
  id: string;
  result: ComparePreviewResponse;
  zipCode: string;
  submittedUrls: string[];
  decisionBoard: CompareDecisionBoard;
  runtimeArtifact: CompareEvidencePackageArtifact | null;
  locale: AppLocale;
  t: (key: string) => string;
}): SavedCompareEvidencePackage {
  return {
    id: input.id,
    label: buildEvidencePackageLabel(input.result, input.zipCode, input.locale, input.t),
    savedAt: new Date().toISOString(),
    zipCode: input.zipCode,
    submittedUrls: input.submittedUrls,
    submittedCount: input.result.submittedCount,
    resolvedCount: input.result.resolvedCount,
    decisionSummary: input.decisionBoard.summary,
    riskSummary: input.decisionBoard.riskSummary,
    recommendedAction: input.decisionBoard.recommendedAction,
    compareResult: input.result,
    runtimeArtifact: input.runtimeArtifact,
  };
}

export function buildCompareSchema() {
  return z.object({
    zipCode: z.string().min(3, "compare.form.errors.zipRequired"),
    submittedUrls: z
      .array(z.string().url("compare.form.errors.invalidProductUrl"))
      .min(2, "compare.form.errors.minUrls")
      .max(10, "compare.form.errors.maxUrls"),
  });
}

export function buildCreateGroupSchema() {
  return z.object({
    title: z
      .string()
      .trim()
      .max(120, "compare.groupBuilder.errors.titleTooLong")
      .optional(),
    zipCode: z.string().min(3, "compare.groupBuilder.errors.zipRequired"),
    cadenceMinutes: z.coerce
      .number()
      .min(5, "compare.groupBuilder.errors.cadenceMin")
      .max(10080, "compare.groupBuilder.errors.cadenceMax"),
    thresholdType: z.enum(["price_below", "price_drop_percent", "effective_price_below"]),
    thresholdValue: z.coerce.number().min(0, "compare.groupBuilder.errors.thresholdValueMin"),
    cooldownMinutes: z.coerce
      .number()
      .min(0, "compare.groupBuilder.errors.cooldownMin")
      .max(10080, "compare.groupBuilder.errors.cooldownMax"),
    recipientEmail: z.string().email("compare.groupBuilder.errors.recipientEmailRequired"),
    notificationsEnabled: z.boolean(),
  });
}

export function buildSavedPackageId(): string {
  return globalThis.crypto?.randomUUID?.() ?? `compare-${Date.now().toString(36)}`;
}
