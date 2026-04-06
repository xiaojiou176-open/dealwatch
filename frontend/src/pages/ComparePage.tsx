import { useEffect, useMemo, useState } from "preact/hooks";
import { z } from "zod";
import { ApiError } from "../lib/api";
import { formatCurrency, formatDateTime, formatNumber, interpolate, type AppLocale, useI18n } from "../lib/i18n";
import {
  useComparePreview,
  useCreateCompareEvidencePackage,
  useCreateWatchGroup,
  useNotificationSettings,
} from "../lib/hooks";
import { navigate, setWatchTaskDraft } from "../lib/routes";
import type {
  AIAssistEnvelope,
  CompareEvidencePackageArtifact,
  ComparePreviewComparison,
  ComparePreviewMatch,
  ComparePreviewResponse,
  SavedCompareEvidencePackage,
  ThresholdType,
  WatchGroupCandidateInput,
} from "../types";

const EVIDENCE_STORAGE_KEY = "dealwatch.compare.savedEvidencePackages";
const MAX_SAVED_EVIDENCE_PACKAGES = 12;
const STRONG_MATCH_SCORE = 85;
const REVIEW_MATCH_SCORE = 70;

const defaultUrls = [
  "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
  "https://www.99ranch.com/product-details/1615424/8899/078895126389",
  "https://www.target.com/p/utz-ripples-original-potato-chips-7-75oz/-/A-13202943",
].join("\n");

type DecisionTone = "success" | "warning" | "error" | "info";

interface CompareDecisionBoard {
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

type DraftMessage = { en: string; "zh-CN"?: string };

const COMPARE_COPY = {
  form: {
    errors: {
      zipRequired: { en: "ZIP code is required.", },
      invalidProductUrl: { en: "Each line must be a valid product URL.", },
      minUrls: { en: "Enter at least two product URLs.", },
      maxUrls: { en: "Enter no more than ten product URLs.", },
    },
  },
  decision: {
    noResolvedCandidate: { en: "No resolved candidate", },
    noConfidentPair: { en: "No confident pair yet", },
    riskUnsupported: { en: "{{count}} submitted URL{{plural}} did not map to a supported store path.", },
    riskStoreDisabled: { en: "{{count}} row{{plural}} belongs to a store that is currently disabled in runtime settings.", },
    riskFetchFailed: { en: "{{count}} supported row{{plural}} still failed to fetch live offer evidence.", },
    riskNoPairScore: { en: "Multiple rows resolved, but none of them produced a pairwise compare score yet.", },
    riskWeakStrongest: { en: "The strongest pair is only {{score}}, so the rows may still describe different products.", },
    riskNeedTwoCandidates: { en: "A compare-aware watch group needs at least two group-ready candidates.", },
    riskLowerConfidence: { en: "{{count}} lower-confidence pair{{plural}} still deserve a quick human review before you trust the basket.", },
    riskNoBlocker: { en: "No obvious compare blocker surfaced in this preview, but the final decision still belongs to the operator.", },
    state: {
      noDecisionHeadline: { en: "No durable decision yet", },
      noDecisionSummary: { en: "Nothing resolved into a reusable candidate, so this compare run should stay in review instead of creating watch state.", },
      noDecisionAction: { en: "Fix the unsupported or fetch-failed rows before you create any watch task or watch group.", },
      oneCandidateHeadline: { en: "One candidate is usable, but the compare basket is incomplete", },
      oneCandidateSummary: { en: "{{bestCandidateLabel}} is the only row with durable evidence right now, so there is no honest cross-store winner yet.", },
      oneCandidateAction: { en: "Create a single watch task only if this row already looks correct; otherwise gather more evidence first.", },
      strongHeadline: { en: "This compare run is strong enough for a watch group", },
      strongSummary: { en: "{{bestCandidateLabel}} currently looks like the clearest low-price row, and {{bestMatchLabel}} already forms a strong compare pair.", },
      strongAction: { en: "Save the evidence package, then create a compare-aware watch group so the runtime can keep reranking instead of freezing one URL forever.", },
      reviewHeadline: { en: "The basket is promising, but the decision still needs review", },
      reviewSummary: { en: "{{bestCandidateLabel}} looks usable and {{bestMatchLabel}} is plausible, but the why-like / why-unlike notes still matter before you lock durable group state.", },
      reviewAction: { en: "Review the evidence pair details, then decide whether this should become a watch group or stay as a single-task handoff.", },
      mixedHeadline: { en: "The compare result is mixed and should stay in review", },
      mixedSummary: { en: "{{bestCandidateLabel}} is still the clearest row, but the strongest pair is weak enough that a group could hide real product mismatch risk.", },
      mixedAction: { en: "Keep this as evidence only, or create a single watch task from the clearest row after a manual check.", },
    },
    badge: {
      groupReady: { en: "group-ready", },
      review: { en: "review", },
      hold: { en: "hold", },
      info: { en: "info", },
    },
    stats: {
      resolved: { en: "Resolved", },
      groupReady: { en: "Group-ready", },
      bestListed: { en: "Best listed", },
      strongestPair: { en: "Strongest pair", },
      aiTitle: { en: "AI-assisted explanation", },
      aiNote: { en: "The deterministic decision board stays primary. This card is only the explain layer on top of that evidence.", },
      riskNotes: { en: "{{count}} note{{plural}}", },
      unsupported: { en: "Unsupported", },
      fetchFailures: { en: "Fetch failures", },
    },
    ai: {
      badge: {
        ok: { en: "available", },
        disabled: { en: "disabled", },
        error: { en: "error", },
        skipped: { en: "skipped", },
        unavailable: { en: "unavailable", },
      },
      headline: {
        ok: { en: "AI-assisted explanation", },
        disabled: { en: "AI assistance is disabled", },
        error: { en: "AI-assisted explanation hit an error", },
        skipped: { en: "AI-assisted explanation was skipped", },
        unavailable: { en: "AI-assisted explanation unavailable", },
      },
      summary: {
        disabled: {
          en: "AI assistance is disabled for this workspace. The decision board, risk summary, and pair evidence remain the source of truth.",
        },
        error: {
          en: "AI-assisted explanation could not be generated for this compare run. Review the deterministic summary and pair evidence instead.",
        },
        skipped: {
          en: "AI-assisted explanation was skipped for this compare run. The deterministic summary and pair evidence still tell the full story.",
        },
        unavailable: {
          en: "AI-assisted explanation unavailable. Showing deterministic summary and evidence only.",
        },
      },
    },
  },
  saved: {
    labelWithTitle: { en: "{{title}} · ZIP {{zipCode}}", },
    labelFallback: { en: "Compare evidence · ZIP {{zipCode}}", },
    shareTitle: { en: "DealWatch compare evidence package", },
    shareLabel: { en: "Label: {{value}}", },
    shareSavedAt: { en: "Saved at: {{value}}", },
    shareZip: { en: "ZIP: {{value}}", },
    shareSubmitted: { en: "Submitted URLs: {{value}}", },
    shareResolved: { en: "Resolved candidates: {{value}}", },
    shareDecision: { en: "Decision summary: {{value}}", },
    shareRisk: { en: "Risk summary: {{value}}", },
    shareAction: { en: "Recommended action: {{value}}", },
    shareRuntimeReady: { en: "Runtime review: {{value}}", },
    shareRuntimeMissing: { en: "Runtime review: not created", },
  },
  notices: {
    invalidCompare: { en: "Invalid compare request.", },
    compareFailed: { en: "Failed to compare these product URLs.", },
    saveLocal: { en: "Saved this compare evidence package for local review on this machine.", },
    runtimeCreated: { en: "Runtime evidence package created. This stays local to the runtime and does not create a public link.", },
    runtimeFailed: { en: "Failed to create the runtime evidence package.", },
    copiedSummary: { en: "Copied the compare evidence summary. It describes the evidence package without pretending there is a public share link.", },
    clipboardFailed: { en: "Clipboard access failed. Save the package first and review it locally instead.", },
    invalidGroup: { en: "Invalid watch group configuration.", },
    needTwoCandidates: { en: "At least two successful compare candidates are required to create a watch group.", },
    createGroupFailed: { en: "Failed to create the watch group from compare candidates.", },
  },
  savedPanel: {
    savedPackagesBadge: { en: "{{count}} saved package{{plural}}", },
    runtimeBacked: { en: "runtime-backed", },
    localOnly: { en: "local-only", },
    savedAt: { en: "Saved {{value}}", },
    runtimeReady: { en: "runtime package ready", },
    localReviewOnly: { en: "local review only", },
    detailSummary: {
      en: "Use a saved package when you want the compare conclusion to stay reviewable on this machine before you turn it into longer-lived runtime evidence.",
    },
    zip: { en: "ZIP", },
    submitted: { en: "Submitted", },
    resolved: { en: "Resolved", },
    decisionSummary: { en: "Decision summary", },
    riskSummary: { en: "Risk summary", },
    copySavedSummary: { en: "Copy saved summary", },
    openRuntimePackageView: { en: "Open runtime package view", },
  },
  candidatePanel: {
    submittedBadge: { en: "{{count}} submitted", },
    resolvedBadge: { en: "{{count}} resolved", },
    groupReadyBadge: { en: "{{count}} group-ready candidates", },
    intro: {
      en: "Once a row looks right, you can either carry one candidate into a single watch task, or keep several strong rows together in a compare-aware watch group.",
    },
    fetched: { en: "fetched", },
    fetchFailed: { en: "fetch failed", },
    unsupported: { en: "limited support", },
    storeDisabled: { en: "store disabled", },
    unknownStore: { en: "unknown-store", },
    matchScore: { en: "match score {{value}}", },
    tier: {
      officialFull: { en: "official full", },
      officialPartial: { en: "official partial", },
      officialInProgress: { en: "official in progress", },
      limitedUnofficial: { en: "limited unofficial", },
    },
    fetchedSummary: {
      en: "This row has enough live offer evidence to move into the watch flow.",
    },
    officialFullSummary: {
      en: "This row is on the full official store path. Compare, single-watch, compare-aware watch group, recovery, and cashback all sit inside the current repo-local product flow.",
    },
    officialPartialSummary: {
      en: "This row is on an official partial store path. Compare intake is real, but some broader store capabilities are still intentionally deferred.",
    },
    fetchFailedSummary: {
      en: "The URL is supported, but the fetch still failed, so this row should not drive a durable decision yet.",
    },
    unsupportedSummary: {
      en: "This URL did not resolve into a supported compare target.",
    },
    unsupportedHostSummary: {
      en: "This host is not in the official registry yet. DealWatch can keep it in compare review and repo-local evidence, but not as live watch state.",
    },
    unsupportedPathSummary: {
      en: "The store host is recognized, but this URL shape is not an officially supported product path yet.",
    },
    storeDisabledSummary: {
      en: "The store exists in the official registry, but its runtime binding is disabled, so this row stays evidence-only for now.",
    },
    listed: { en: "Listed", },
    evidenceNotes: { en: "Evidence notes", },
    brand: { en: "Brand {{value}}. ", },
    size: { en: "Size {{value}}. ", },
    originalPrice: { en: "Original {{value}}.", },
    noOriginalPrice: { en: "No original-price evidence returned.", },
    submittedUrl: { en: "Submitted URL", },
    normalizedUrl: { en: "Normalized URL", },
    errorCode: { en: "Error: {{value}}", },
    recommendedCta: { en: "Recommended CTA", },
    recommendedCtaSummary: {
      en: "Use this when you want to turn one confirmed row into a watch task without carrying the whole basket forward.",
    },
    createWatchTaskFromRow: { en: "Create watch task from this row", },
    evidenceFingerprint: { en: "Evidence fingerprint", },
    noDurableCta: {
      en: "No durable CTA yet. This row needs a successful fetch before it can become a watch task or count toward a group.",
    },
    nextStep: { en: "Next step: {{value}}", },
    stillAllowed: { en: "Still allowed", },
    stillBlocked: { en: "Still blocked", },
    saveCompareEvidence: { en: "save compare evidence", },
    createWatchTaskAction: { en: "create watch task", },
    createWatchGroupAction: { en: "create watch group", },
    cashbackAction: { en: "cashback context", },
    notificationsAction: { en: "notifications", },
    missingCapabilities: { en: "Missing capabilities", },
  },
  groupBuilder: {
    eyebrow: { en: "Create watch group", },
    title: { en: "Turn the strongest rows into one decision basket", },
    summary: {
      en: "A watch group is the product answer to \"don't forget the alternatives.\" Instead of freezing one URL forever, the runtime can keep reevaluating the basket each time it runs.",
    },
    groupTitle: { en: "Group title", },
    zipCode: { en: "ZIP Code", },
    cadenceMinutes: { en: "Cadence (minutes)", },
    thresholdType: { en: "Threshold Type", },
    thresholdPriceBelow: { en: "Price below", },
    thresholdDropPercent: { en: "Price drop percent", },
    thresholdEffectiveBelow: { en: "Effective price below", },
    thresholdValue: { en: "Threshold Value", },
    thresholdHelp: {
      en: "Suggested from the best currently fetched candidate so you start from real compare evidence.",
    },
    cooldownMinutes: { en: "Cooldown (minutes)", },
    recipientEmail: { en: "Recipient Email", },
    enableNotifications: { en: "Enable notifications for this group", },
    rowsEnteringBasket: { en: "Rows that will enter the basket", },
    listedAtStore: { en: "{{storeKey}} · listed {{value}}", },
    similarity: { en: "similarity {{value}}", },
    noSuccessfulCandidates: {
      en: "No successful compare candidates are available yet, so group creation stays locked.",
    },
    lockedHint: {
      en: "A compare-aware group stays locked until at least two successful candidates survive the preview. That keeps a thin basket from pretending it is durable compare truth.",
    },
    creating: { en: "Creating watch group from compare candidates...", },
    createButton: { en: "Create watch group from successful candidates", },
    defaultTitleSuffix: { en: "compare group", },
    errors: {
      titleTooLong: { en: "Group title must stay within 120 characters.", },
      zipRequired: { en: "ZIP code is required.", },
      cadenceMin: { en: "Cadence must be at least 5 minutes.", },
      cadenceMax: { en: "Cadence must stay within 10080 minutes.", },
      thresholdValueMin: { en: "Threshold value must be zero or above.", },
      cooldownMin: { en: "Cooldown must be zero or above.", },
      cooldownMax: { en: "Cooldown must stay within 10080 minutes.", },
      recipientEmailRequired: { en: "Recipient email is required.", },
    },
  },
  pairEvidence: {
    title: { en: "Pair evidence", },
    summary: {
      en: "These scores are the pair-by-pair proof. They explain why two rows look close, and why a row might still stay out of the basket.",
    },
    strong: { en: "strong", },
    review: { en: "review", },
    weak: { en: "weak", },
    titleSimilarity: { en: "Title {{value}}", },
    brand: { en: "brand: {{value}}", },
    size: { en: "size: {{value}}", },
    keys: { en: "keys: {{value}}", },
    versus: { en: "vs", },
    unknown: { en: "unknown", },
    whyClose: { en: "Why this looks close", },
    whyDiffer: { en: "Why this may differ", },
    noPairScore: { en: "No successful pair produced a match score.", },
  },
} as const;

const COMPARE_CAPABILITY_COPY = {
  officialStoreRegistry: { en: "official store registry", },
  manifestEntry: { en: "store manifest entry", },
  compareIntake: { en: "compare intake", },
  watchTask: { en: "watch task", },
  watchGroup: { en: "watch group", },
  recovery: { en: "recovery", },
  cashback: { en: "cashback", },
} as const;

function draft(locale: AppLocale, message: DraftMessage, values?: Record<string, string | number>) {
  const template = message[locale] ?? message.en;
  return values ? interpolate(template, values) : template;
}

function resolveCompareCopy(
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

function formatOneDecimal(locale: AppLocale, value: number | null | undefined, fallback = "--"): string {
  return formatNumber(locale, value, fallback, {
    maximumFractionDigits: 1,
    minimumFractionDigits: 1,
  });
}

function formatCapabilityLabel(locale: AppLocale, t: (key: string) => string, capability: string): string {
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

function resolveUiMessage(message: string, t: (key: string) => string): string {
  const translated = t(message);
  return translated === message ? message : translated;
}

function normalizeUrls(raw: string): string[] {
  return raw
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

function defaultGroupTitle(
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

function buildCandidateScoreIndex(matches: ComparePreviewMatch[]): Record<string, number> {
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

function getComparisonLabel(item: ComparePreviewComparison): string {
  return item.offer?.title ?? item.normalizedUrl ?? item.submittedUrl;
}

function getSupportTierLabel(locale: AppLocale, t: (key: string) => string, item: ComparePreviewComparison): string | null {
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

function getComparisonStatusLabel(locale: AppLocale, t: (key: string) => string, item: ComparePreviewComparison): string {
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

function getComparisonStatusTone(item: ComparePreviewComparison): string {
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

function getComparisonSummary(locale: AppLocale, t: (key: string) => string, item: ComparePreviewComparison): string {
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

function getSupportActionBuckets(
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

function buildDecisionBoard(
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

function decisionBadgeClass(tone: DecisionTone): string {
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

function decisionAlertClass(tone: DecisionTone): string {
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

function aiAssistBadgeClass(status: AIAssistEnvelope["status"]): string {
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

function aiAssistLabel(status: AIAssistEnvelope["status"], locale: AppLocale, t: (key: string) => string): string {
  return resolveCompareCopy(
    t,
    locale,
    `compare.decision.ai.badge.${status}`,
    COMPARE_COPY.decision.ai.badge[status],
  );
}

function compareAIHeadline(status: AIAssistEnvelope["status"], locale: AppLocale, t: (key: string) => string): string {
  return resolveCompareCopy(
    t,
    locale,
    `compare.decision.ai.headline.${status}`,
    COMPARE_COPY.decision.ai.headline[status],
  );
}

function compareAISummary(status: AIAssistEnvelope["status"], locale: AppLocale, t: (key: string) => string): string {
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

function loadSavedEvidencePackages(): SavedCompareEvidencePackage[] {
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

function buildShareSummary(locale: AppLocale, t: (key: string) => string, payload: SavedCompareEvidencePackage): string {
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

function buildSavedEvidencePackage(input: {
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

function buildCompareSchema(locale: AppLocale, t: (key: string) => string) {
  return z.object({
    zipCode: z.string().min(3, "compare.form.errors.zipRequired"),
    submittedUrls: z
      .array(z.string().url("compare.form.errors.invalidProductUrl"))
      .min(2, "compare.form.errors.minUrls")
      .max(10, "compare.form.errors.maxUrls"),
  });
}

function buildCreateGroupSchema() {
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

function buildSavedPackageId(): string {
  return globalThis.crypto?.randomUUID?.() ?? `compare-${Date.now().toString(36)}`;
}

export function ComparePage() {
  const { locale, t } = useI18n();
  const compareSchema = useMemo(() => buildCompareSchema(locale, t), [locale, t]);
  const createGroupSchema = useMemo(() => buildCreateGroupSchema(), []);
  const mutation = useComparePreview();
  const settingsQuery = useNotificationSettings();
  const createGroupMutation = useCreateWatchGroup();
  const createEvidencePackageMutation = useCreateCompareEvidencePackage();

  const [zipCode, setZipCode] = useState("98004");
  const [rawUrls, setRawUrls] = useState(defaultUrls);
  const [error, setError] = useState("");
  const [groupError, setGroupError] = useState("");
  const [evidenceError, setEvidenceError] = useState("");
  const [evidenceNotice, setEvidenceNotice] = useState("");
  const [selectedPackageId, setSelectedPackageId] = useState<string | null>(null);
  const [draftPackageId, setDraftPackageId] = useState<string | null>(null);
  const [savedPackages, setSavedPackages] = useState<SavedCompareEvidencePackage[]>(() => loadSavedEvidencePackages());
  const [groupForm, setGroupForm] = useState<{
    title: string;
    zipCode: string;
    cadenceMinutes: number;
    thresholdType: ThresholdType;
    thresholdValue: number;
    cooldownMinutes: number;
    recipientEmail: string;
    notificationsEnabled: boolean;
  }>({
    title: "",
    zipCode: "98004",
    cadenceMinutes: 360,
    thresholdType: "effective_price_below",
    thresholdValue: 0,
    cooldownMinutes: 240,
    recipientEmail: "owner@example.com",
    notificationsEnabled: true,
  });
  const compareText = (
    key: string,
    fallback: DraftMessage,
    values?: Record<string, string | number>,
  ) => resolveCompareCopy(t, locale, key, fallback, values);

  useEffect(() => {
    if (!settingsQuery.data) {
      return;
    }
    setGroupForm((current) => ({
      ...current,
      cooldownMinutes: settingsQuery.data.cooldownMinutes,
      recipientEmail:
        current.recipientEmail === "owner@example.com"
          ? settingsQuery.data.defaultRecipientEmail
          : current.recipientEmail,
      notificationsEnabled: settingsQuery.data.notificationsEnabled,
    }));
  }, [settingsQuery.data]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    try {
      window.localStorage.setItem(EVIDENCE_STORAGE_KEY, JSON.stringify(savedPackages));
    } catch {
      // Ignore local persistence failures and keep the in-memory review surface usable.
    }
  }, [savedPackages]);

  useEffect(() => {
    if (!selectedPackageId && savedPackages[0]) {
      setSelectedPackageId(savedPackages[0].id);
    }
  }, [savedPackages, selectedPackageId]);

  async function onSubmit(event: Event) {
    event.preventDefault();
    const parsed = compareSchema.safeParse({
      zipCode,
      submittedUrls: normalizeUrls(rawUrls),
    });
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? "compare.notices.invalidCompare");
      return;
    }

    setError("");
    setGroupError("");
    setEvidenceError("");
    setEvidenceNotice("");
    setDraftPackageId(null);

    try {
      await mutation.mutateAsync(parsed.data);
      setGroupForm((current) => ({ ...current, zipCode: parsed.data.zipCode }));
    } catch (mutationError) {
      if (mutationError instanceof ApiError) {
        setError(mutationError.message);
        return;
      }
      setError("compare.notices.compareFailed");
    }
  }

  const result = mutation.data;
  const scoreByCandidate = useMemo(
    () => (result ? buildCandidateScoreIndex(result.matches) : {}),
    [result],
  );

  const comparisonByCandidateKey = useMemo(() => {
    const next = new Map<string, ComparePreviewComparison>();
    for (const item of result?.comparisons ?? []) {
      if (item.candidateKey) {
        next.set(item.candidateKey, item);
      }
    }
    return next;
  }, [result]);

  const successfulCandidates = useMemo<WatchGroupCandidateInput[]>(
    () =>
      (result?.comparisons ?? [])
        .filter((item) => item.fetchSucceeded && item.offer && item.storeKey && item.candidateKey)
        .map((item) => ({
          submittedUrl: item.submittedUrl,
          titleSnapshot: item.offer!.title,
          storeKey: item.storeKey!,
          candidateKey: item.candidateKey!,
          brandHint: item.brandHint,
          sizeHint: item.sizeHint,
          similarityScore: scoreByCandidate[item.candidateKey!] ?? 0,
        })),
    [result, scoreByCandidate],
  );
  const groupReadyCandidates = useMemo<WatchGroupCandidateInput[]>(
    () =>
      successfulCandidates.filter((candidate) =>
        comparisonByCandidateKey.get(candidate.candidateKey)?.supportContract?.canCreateWatchGroup,
      ),
    [comparisonByCandidateKey, successfulCandidates],
  );

  const decisionBoard = useMemo(
    () => (result ? buildDecisionBoard(locale, t, result, successfulCandidates, groupReadyCandidates) : null),
    [groupReadyCandidates, locale, result, successfulCandidates, t],
  );
  const compareAIExplain = result?.aiExplain ?? null;

  const selectedSavedPackage = useMemo(
    () => savedPackages.find((item) => item.id === selectedPackageId) ?? savedPackages[0] ?? null,
    [savedPackages, selectedPackageId],
  );

  useEffect(() => {
    if (!groupReadyCandidates.length) {
      return;
    }
    const bestObservedPrice = Math.min(
      ...groupReadyCandidates.map((candidate) => {
        const comparison = result?.comparisons.find((item) => item.candidateKey === candidate.candidateKey);
        return comparison?.offer?.price ?? Number.POSITIVE_INFINITY;
      }),
    );
    const nextTitle = defaultGroupTitle(groupReadyCandidates, locale, t);
    const nextThresholdValue = Number.isFinite(bestObservedPrice)
      ? Number(bestObservedPrice.toFixed(2))
      : undefined;
    setGroupForm((current) => {
      const resolvedTitle = current.title || nextTitle;
      const resolvedThresholdValue = nextThresholdValue ?? current.thresholdValue;
      if (
        current.title === resolvedTitle &&
        current.zipCode === zipCode &&
        current.thresholdValue === resolvedThresholdValue
      ) {
        return current;
      }
      return {
        ...current,
        title: resolvedTitle,
        zipCode,
        thresholdValue: resolvedThresholdValue,
      };
    });
  }, [groupReadyCandidates, locale, result, t, zipCode]);

  function updateGroupForm<K extends keyof typeof groupForm>(key: K, value: (typeof groupForm)[K]) {
    setGroupForm((current) => ({ ...current, [key]: value }));
  }

  function useComparisonForTask(
    submittedUrl: string,
    normalizedUrl: string | undefined,
    offerTitle: string,
    storeKey: string | undefined,
    candidateKey: string | undefined,
    brandHint: string | undefined,
    sizeHint: string | undefined,
  ) {
    setWatchTaskDraft({
      submittedUrl,
      normalizedUrl: normalizedUrl ?? submittedUrl,
      title: offerTitle,
      storeKey: storeKey ?? "unknown",
      candidateKey: candidateKey ?? "unknown",
      brandHint,
      sizeHint,
      defaultRecipientEmail: settingsQuery.data?.defaultRecipientEmail ?? "owner@example.com",
      zipCode,
    });
    navigate("watch-new");
  }

  function upsertCurrentEvidencePackage(runtimeArtifact: CompareEvidencePackageArtifact | null) {
    if (!result || !decisionBoard) {
      return null;
    }

    const nextId = draftPackageId ?? buildSavedPackageId();
    const submittedUrls = normalizeUrls(rawUrls);
    const nextPackage = buildSavedEvidencePackage({
      id: nextId,
      result,
      zipCode,
      submittedUrls,
      decisionBoard,
      runtimeArtifact,
      locale,
      t,
    });

    setSavedPackages((current) => {
      const existing = current.find((item) => item.id === nextId);
      const merged: SavedCompareEvidencePackage = existing
        ? {
            ...existing,
            ...nextPackage,
            runtimeArtifact: runtimeArtifact ?? existing.runtimeArtifact,
          }
        : nextPackage;

      const withoutExisting = current.filter((item) => item.id !== nextId);
      return [merged, ...withoutExisting].slice(0, MAX_SAVED_EVIDENCE_PACKAGES);
    });

    setDraftPackageId(nextId);
    setSelectedPackageId(nextId);
    return nextPackage;
  }

  function handleSaveEvidencePackage() {
    if (!result || !decisionBoard) {
      return;
    }
    upsertCurrentEvidencePackage(null);
    setEvidenceError("");
    setEvidenceNotice("compare.notices.saveLocal");
  }

  async function handleCreateRuntimeEvidencePackage() {
    if (!result || !decisionBoard) {
      return;
    }
    setEvidenceError("");
    setEvidenceNotice("");
    try {
      const runtimeArtifact = await createEvidencePackageMutation.mutateAsync({
        submittedUrls: normalizeUrls(rawUrls),
        zipCode,
        compareResult: result,
      });
      upsertCurrentEvidencePackage(runtimeArtifact);
      setEvidenceNotice("compare.notices.runtimeCreated");
    } catch (mutationError) {
      if (mutationError instanceof ApiError) {
        setEvidenceError(mutationError.message);
        return;
      }
      setEvidenceError("compare.notices.runtimeFailed");
    }
  }

  async function handleCopyEvidenceSummary(payload: SavedCompareEvidencePackage | null) {
    if (!payload) {
      return;
    }
    try {
      await navigator.clipboard.writeText(buildShareSummary(locale, t, payload));
      setEvidenceError("");
      setEvidenceNotice("compare.notices.copiedSummary");
    } catch {
      setEvidenceError("compare.notices.clipboardFailed");
    }
  }

  async function onCreateGroup() {
    const parsed = createGroupSchema.safeParse(groupForm);
    if (!parsed.success) {
      setGroupError(parsed.error.issues[0]?.message ?? "compare.notices.invalidGroup");
      return;
    }
    if (groupReadyCandidates.length < 2) {
      setGroupError("compare.notices.needTwoCandidates");
      return;
    }
    setGroupError("");
    try {
      const group = await createGroupMutation.mutateAsync({
        ...parsed.data,
        title: parsed.data.title?.trim() || undefined,
        candidates: groupReadyCandidates,
      });
      navigate("watch-group-detail", group.id);
    } catch (mutationError) {
      if (mutationError instanceof ApiError) {
        setGroupError(mutationError.message);
        return;
      }
      setGroupError("compare.notices.createGroupFailed");
    }
  }

  return (
    <section class="space-y-4">
      <form
        class="rounded-[1.75rem] border border-base-300 bg-base-100/95 p-6 shadow-card"
        onSubmit={onSubmit}
      >
        <p class="text-xs font-semibold uppercase tracking-[0.2em] text-ember">{t("compare.form.eyebrow")}</p>
        <h2 class="mt-2 text-2xl font-semibold text-ink">
          {t("compare.form.title")}
        </h2>
        <p class="mt-2 text-sm leading-6 text-slate-600">
          {t("compare.form.summary")}
        </p>

        <div class="mt-6 grid gap-4">
          <label class="form-control gap-2">
            <span class="label-text block font-medium">{t("compare.form.zipCode")}</span>
            <input
              class="input input-bordered"
              onInput={(event) => setZipCode((event.currentTarget as HTMLInputElement).value)}
              value={zipCode}
            />
          </label>

          <label class="form-control gap-2">
            <span class="label-text block font-medium">{t("compare.form.productUrls")}</span>
            <textarea
              class="textarea textarea-bordered min-h-48"
              onInput={(event) => setRawUrls((event.currentTarget as HTMLTextAreaElement).value)}
              value={rawUrls}
            />
            <span class="label-text-alt mt-2 text-slate-500">{t("compare.form.productUrlsHelp")}</span>
          </label>
        </div>

        {error ? <div class="alert alert-error mt-5">{resolveUiMessage(error, t)}</div> : null}
        {mutation.isPending ? <div class="alert alert-info mt-5">{t("compare.form.loading")}</div> : null}

        <div class="mt-6">
          <button class="btn btn-primary" type="submit">{t("compare.form.submit")}</button>
        </div>
      </form>

      {decisionBoard ? (
        <div class="grid gap-4 xl:grid-cols-[1.1fr,0.9fr]">
          <section class="rounded-[1.75rem] border border-base-300 bg-base-100/95 p-6 shadow-card">
            <div class="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p class="text-xs font-semibold uppercase tracking-[0.2em] text-ember">{t("compare.decision.eyebrow")}</p>
                <h3 class="mt-2 text-2xl font-semibold text-ink">{decisionBoard.headline}</h3>
                <p class="mt-3 text-sm leading-6 text-slate-600">{decisionBoard.summary}</p>
              </div>
              <span class={`badge ${decisionBadgeClass(decisionBoard.tone)}`}>
                {decisionBoard.tone === "success"
                  ? compareText("compare.decision.badge.groupReady", COMPARE_COPY.decision.badge.groupReady)
                  : decisionBoard.tone === "warning"
                    ? compareText("compare.decision.badge.review", COMPARE_COPY.decision.badge.review)
                    : decisionBoard.tone === "error"
                      ? compareText("compare.decision.badge.hold", COMPARE_COPY.decision.badge.hold)
                      : compareText("compare.decision.badge.info", COMPARE_COPY.decision.badge.info)}
              </span>
            </div>

            <div class="mt-4 grid gap-3 md:grid-cols-4">
              <div class="rounded-2xl bg-base-200/60 px-4 py-3">
                <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                  {compareText("compare.decision.stats.resolved", COMPARE_COPY.decision.stats.resolved)}
                </div>
                <div class="mt-2 text-2xl font-semibold text-ink">{formatNumber(locale, result?.resolvedCount ?? 0, "0")}</div>
              </div>
              <div class="rounded-2xl bg-base-200/60 px-4 py-3">
                <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                  {compareText("compare.decision.stats.groupReady", COMPARE_COPY.decision.stats.groupReady)}
                </div>
                <div class="mt-2 text-2xl font-semibold text-ink">{formatNumber(locale, decisionBoard.groupReadyCount, "0")}</div>
              </div>
              <div class="rounded-2xl bg-base-200/60 px-4 py-3">
                <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                  {compareText("compare.decision.stats.bestListed", COMPARE_COPY.decision.stats.bestListed)}
                </div>
                <div class="mt-2 text-2xl font-semibold text-ember">{formatCurrency(locale, decisionBoard.bestListedPrice)}</div>
              </div>
              <div class="rounded-2xl bg-base-200/60 px-4 py-3">
                <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                  {compareText("compare.decision.stats.strongestPair", COMPARE_COPY.decision.stats.strongestPair)}
                </div>
                <div class="mt-2 text-2xl font-semibold text-ink">
                  {decisionBoard.bestMatch ? formatOneDecimal(locale, decisionBoard.bestMatch.score) : "--"}
                </div>
              </div>
            </div>

            <div class={`alert mt-4 ${decisionAlertClass(decisionBoard.tone)}`}>
              <div>
                <div class="font-semibold">{t("compare.decision.recommendedNextStep")}</div>
                <div class="text-sm leading-6">{decisionBoard.recommendedAction}</div>
              </div>
            </div>

            <div class="mt-4 flex flex-wrap gap-3">
              <button class="btn btn-primary" onClick={handleSaveEvidencePackage} type="button">{t("compare.decision.saveReviewPackage")}</button>
              <button
                class="btn btn-outline"
                disabled={createEvidencePackageMutation.isPending}
                onClick={handleCreateRuntimeEvidencePackage}
                type="button"
              >
                {createEvidencePackageMutation.isPending
                  ? t("compare.decision.creatingRuntimePackage")
                  : t("compare.decision.createRuntimePackage")}
              </button>
              <button
                class="btn btn-ghost"
                disabled={!result}
                onClick={() =>
                  handleCopyEvidenceSummary(
                    result && decisionBoard
                      ? buildSavedEvidencePackage({
                          id: draftPackageId ?? "current-compare-preview",
                          result,
                          zipCode,
                          submittedUrls: normalizeUrls(rawUrls),
                          decisionBoard,
                          runtimeArtifact: null,
                          locale,
                          t,
                        })
                      : null,
                  )
                }
                type="button"
              >
                {t("compare.decision.copyEvidenceSummary")}
              </button>
            </div>
            <p class="mt-3 text-xs leading-5 text-slate-500">
              {t("compare.decision.summaryNote")}
            </p>

            <div class="mt-4 rounded-2xl border border-dashed border-base-300 bg-base-200/30 px-4 py-4">
              <div class="flex items-start justify-between gap-3">
                <div>
                  <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                    {compareText("compare.decision.stats.aiTitle", COMPARE_COPY.decision.stats.aiTitle)}
                  </div>
                  <h4 class="mt-2 text-lg font-semibold text-ink">
                    {compareAIExplain?.title ?? compareAIHeadline(compareAIExplain?.status ?? "unavailable", locale, t)}
                  </h4>
                </div>
                <span class={`badge ${aiAssistBadgeClass(compareAIExplain?.status ?? "unavailable")}`}>
                  {aiAssistLabel(compareAIExplain?.status ?? "unavailable", locale, t)}
                </span>
              </div>
              <p class="mt-2 text-sm leading-6 text-slate-600">
                {compareAIExplain?.summary ?? compareAISummary(compareAIExplain?.status ?? "unavailable", locale, t)}
              </p>
              {compareAIExplain?.detail ? (
                <p class="mt-2 text-sm leading-6 text-slate-500">{compareAIExplain.detail}</p>
              ) : null}
              {compareAIExplain?.bullets.length ? (
                <ul class="mt-3 space-y-2 text-sm leading-6 text-slate-600">
                  {compareAIExplain.bullets.map((bullet) => (
                    <li key={bullet}>- {bullet}</li>
                  ))}
                </ul>
              ) : null}
              <p class="mt-3 text-xs leading-5 text-slate-500">
                {compareText("compare.decision.stats.aiNote", COMPARE_COPY.decision.stats.aiNote)}
              </p>
            </div>
          </section>

          <aside class="rounded-[1.75rem] border border-base-300 bg-base-100/95 p-6 shadow-card">
            <div class="flex items-center justify-between gap-3">
              <div>
                <p class="text-xs font-semibold uppercase tracking-[0.2em] text-ember">{t("compare.decision.riskEyebrow")}</p>
                <h3 class="mt-2 text-xl font-semibold text-ink">{decisionBoard.riskSummary}</h3>
              </div>
              <span class={`badge ${decisionBadgeClass(decisionBoard.tone)}`}>
                {compareText("compare.decision.stats.riskNotes", COMPARE_COPY.decision.stats.riskNotes, {
                  count: formatNumber(locale, decisionBoard.risks.length, "0"),
                  plural: decisionBoard.risks.length === 1 ? "" : "s",
                })}
              </span>
            </div>

            <div class="mt-4 space-y-3">
              {decisionBoard.risks.map((risk) => (
                <div class="rounded-2xl border border-base-300 bg-base-100/80 px-4 py-3 text-sm leading-6 text-slate-600" key={risk}>
                  {risk}
                </div>
              ))}
            </div>

            <div class="mt-4 grid gap-3 md:grid-cols-2">
              <div class="rounded-2xl bg-base-200/60 px-4 py-3">
                <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                  {compareText("compare.decision.stats.unsupported", COMPARE_COPY.decision.stats.unsupported)}
                </div>
                <div class="mt-2 text-xl font-semibold text-ink">{formatNumber(locale, decisionBoard.unsupportedCount, "0")}</div>
              </div>
              <div class="rounded-2xl bg-base-200/60 px-4 py-3">
                <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                  {compareText("compare.decision.stats.fetchFailures", COMPARE_COPY.decision.stats.fetchFailures)}
                </div>
                <div class="mt-2 text-xl font-semibold text-ink">{formatNumber(locale, decisionBoard.fetchFailureCount, "0")}</div>
              </div>
            </div>

            {evidenceNotice ? <div class="alert alert-success mt-4">{resolveUiMessage(evidenceNotice, t)}</div> : null}
            {evidenceError ? <div class="alert alert-error mt-4">{resolveUiMessage(evidenceError, t)}</div> : null}
          </aside>
        </div>
      ) : null}

      <section class="rounded-[1.75rem] border border-base-300 bg-base-100/95 p-6 shadow-card">
        <div class="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div>
            <p class="text-xs font-semibold uppercase tracking-[0.2em] text-ember">{t("compare.decision.savedEyebrow")}</p>
            <h3 class="mt-2 text-xl font-semibold text-ink">{t("compare.decision.savedTitle")}</h3>
            <p class="mt-2 text-sm leading-6 text-slate-600">
              {t("compare.decision.savedSummary")}
            </p>
          </div>
          <span class="badge badge-outline">
            {compareText("compare.savedPanel.savedPackagesBadge", COMPARE_COPY.savedPanel.savedPackagesBadge, {
              count: formatNumber(locale, savedPackages.length, "0"),
              plural: savedPackages.length === 1 ? "" : "s",
            })}
          </span>
        </div>

        {savedPackages.length ? (
          <div class="mt-5 grid gap-4 xl:grid-cols-[0.9fr,1.1fr]">
            <div class="space-y-3">
              {savedPackages.map((item) => (
                <button
                  class={`w-full rounded-2xl border px-4 py-4 text-left transition ${
                    selectedSavedPackage?.id === item.id
                      ? "border-ember bg-amber-50/70"
                      : "border-base-300 bg-base-100/80 hover:border-ember/50"
                  }`}
                  key={item.id}
                  onClick={() => setSelectedPackageId(item.id)}
                  type="button"
                >
                  <div class="flex items-start justify-between gap-3">
                    <div>
                      <div class="font-semibold text-ink">{item.label}</div>
                      <div class="mt-1 text-xs text-slate-500">{formatDateTime(locale, item.savedAt)}</div>
                    </div>
                    <span class={`badge ${item.runtimeArtifact ? "badge-success" : "badge-outline"}`}>
                      {item.runtimeArtifact
                        ? compareText("compare.savedPanel.runtimeBacked", COMPARE_COPY.savedPanel.runtimeBacked)
                        : compareText("compare.savedPanel.localOnly", COMPARE_COPY.savedPanel.localOnly)}
                    </span>
                  </div>
                  <p class="mt-3 text-sm leading-6 text-slate-600">{item.recommendedAction}</p>
                </button>
              ))}
            </div>

            <div class="rounded-2xl border border-base-300 bg-base-100/80 p-5">
              {selectedSavedPackage ? (
                <div class="space-y-4">
                  <div class="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h4 class="text-lg font-semibold text-ink">{selectedSavedPackage.label}</h4>
                      <p class="mt-1 text-sm text-slate-500">
                        {compareText("compare.savedPanel.savedAt", COMPARE_COPY.savedPanel.savedAt, {
                          value: formatDateTime(locale, selectedSavedPackage.savedAt),
                        })}
                      </p>
                      <p class="mt-2 text-sm leading-6 text-slate-600">
                        {compareText("compare.savedPanel.detailSummary", COMPARE_COPY.savedPanel.detailSummary)}
                      </p>
                    </div>
                    {selectedSavedPackage.runtimeArtifact ? (
                      <span class="badge badge-success">
                        {compareText("compare.savedPanel.runtimeReady", COMPARE_COPY.savedPanel.runtimeReady)}
                      </span>
                    ) : (
                      <span class="badge badge-outline">
                        {compareText("compare.savedPanel.localReviewOnly", COMPARE_COPY.savedPanel.localReviewOnly)}
                      </span>
                    )}
                  </div>

                  <div class="grid gap-3 md:grid-cols-3">
                    <div class="rounded-2xl bg-base-200/60 px-4 py-3">
                      <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                        {compareText("compare.savedPanel.zip", COMPARE_COPY.savedPanel.zip)}
                      </div>
                      <div class="mt-2 text-lg font-semibold text-ink">{selectedSavedPackage.zipCode}</div>
                    </div>
                    <div class="rounded-2xl bg-base-200/60 px-4 py-3">
                      <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                        {compareText("compare.savedPanel.submitted", COMPARE_COPY.savedPanel.submitted)}
                      </div>
                      <div class="mt-2 text-lg font-semibold text-ink">{selectedSavedPackage.submittedCount}</div>
                    </div>
                    <div class="rounded-2xl bg-base-200/60 px-4 py-3">
                      <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                        {compareText("compare.savedPanel.resolved", COMPARE_COPY.savedPanel.resolved)}
                      </div>
                      <div class="mt-2 text-lg font-semibold text-ink">{selectedSavedPackage.resolvedCount}</div>
                    </div>
                  </div>

                  <div class="rounded-2xl bg-base-200/40 px-4 py-4">
                    <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                      {compareText("compare.savedPanel.decisionSummary", COMPARE_COPY.savedPanel.decisionSummary)}
                    </div>
                    <p class="mt-2 text-sm leading-6 text-slate-600">{selectedSavedPackage.decisionSummary}</p>
                  </div>

                  <div class="rounded-2xl bg-base-200/40 px-4 py-4">
                    <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                      {compareText("compare.savedPanel.riskSummary", COMPARE_COPY.savedPanel.riskSummary)}
                    </div>
                    <p class="mt-2 text-sm leading-6 text-slate-600">{selectedSavedPackage.riskSummary}</p>
                  </div>

                  <div class="flex flex-wrap gap-3">
                    <button
                      class="btn btn-outline"
                      onClick={() => handleCopyEvidenceSummary(selectedSavedPackage)}
                      type="button"
                    >
                      {compareText("compare.savedPanel.copySavedSummary", COMPARE_COPY.savedPanel.copySavedSummary)}
                    </button>
                    {selectedSavedPackage.runtimeArtifact?.htmlUrl ? (
                      <a
                        class="btn btn-primary"
                        href={selectedSavedPackage.runtimeArtifact.htmlUrl}
                        rel="noreferrer"
                        target="_blank"
                      >
                        {compareText("compare.savedPanel.openRuntimePackageView", COMPARE_COPY.savedPanel.openRuntimePackageView)}
                      </a>
                    ) : null}
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        ) : (
          <div class="alert alert-info mt-5">
            {t("compare.decision.noSavedPackages")}
          </div>
        )}
      </section>

      {result ? (
        <div class="rounded-[1.75rem] border border-base-300 bg-base-100/95 p-6 shadow-card">
          <div class="flex flex-wrap items-center gap-3">
            <h3 class="text-xl font-semibold text-ink">{t("compare.decision.candidateEvidenceTitle")}</h3>
            <span class="badge badge-outline">
              {compareText("compare.candidatePanel.submittedBadge", COMPARE_COPY.candidatePanel.submittedBadge, {
                count: formatNumber(locale, result.submittedCount, "0"),
              })}
            </span>
            <span class="badge badge-outline">
              {compareText("compare.candidatePanel.resolvedBadge", COMPARE_COPY.candidatePanel.resolvedBadge, {
                count: formatNumber(locale, result.resolvedCount, "0"),
              })}
            </span>
            <span class="badge badge-outline">
              {compareText("compare.candidatePanel.groupReadyBadge", COMPARE_COPY.candidatePanel.groupReadyBadge, {
                count: formatNumber(locale, groupReadyCandidates.length, "0"),
              })}
            </span>
          </div>
          <p class="mt-3 text-sm leading-6 text-slate-600">
            {t("compare.candidatePanel.intro")}
          </p>

          <div class="mt-5 grid gap-4">
            {result.comparisons.map((item) => (
              <article class="rounded-2xl border border-base-300 px-4 py-4" key={item.submittedUrl}>
                <div class="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                  <div class="min-w-0 flex-1">
                    <div class="flex flex-wrap items-center gap-2">
                      <span class={`badge ${getComparisonStatusTone(item)}`}>
                        {getComparisonStatusLabel(locale, t, item)}
                      </span>
                      <span class="badge badge-outline">
                        {item.storeKey ?? compareText("compare.candidatePanel.unknownStore", COMPARE_COPY.candidatePanel.unknownStore)}
                      </span>
                      {getSupportTierLabel(locale, t, item) ? (
                        <span class="badge badge-outline">
                          {getSupportTierLabel(locale, t, item)}
                        </span>
                      ) : null}
                      {item.candidateKey && scoreByCandidate[item.candidateKey] !== undefined ? (
                        <span class="badge badge-outline">
                          {compareText("compare.candidatePanel.matchScore", COMPARE_COPY.candidatePanel.matchScore, {
                            value: formatOneDecimal(locale, scoreByCandidate[item.candidateKey]),
                          })}
                        </span>
                      ) : null}
                    </div>

                    <h4 class="mt-3 text-lg font-semibold text-ink">{getComparisonLabel(item)}</h4>
                    <p class="mt-2 text-sm leading-6 text-slate-600">
                      {getComparisonSummary(locale, t, item)}
                    </p>
                    {item.supportContract?.nextStep ? (
                      <p class="mt-2 text-xs leading-5 text-slate-500">
                        {compareText("compare.candidatePanel.nextStep", COMPARE_COPY.candidatePanel.nextStep, {
                          value: item.supportContract.nextStep,
                        })}
                      </p>
                    ) : null}
                    {item.supportContract ? (
                      <div class="mt-4 grid gap-3 md:grid-cols-2">
                        <div class="rounded-2xl bg-base-200/40 px-4 py-3">
                          <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                            {t("compare.candidatePanel.stillAllowed")}
                          </div>
                          <div class="mt-2 flex flex-wrap gap-2">
                            {getSupportActionBuckets(locale, t, item).allowed.map((action) => (
                              <span class="badge badge-success" key={action}>{action}</span>
                            ))}
                          </div>
                        </div>
                        <div class="rounded-2xl bg-base-200/40 px-4 py-3">
                          <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                            {t("compare.candidatePanel.stillBlocked")}
                          </div>
                          <div class="mt-2 flex flex-wrap gap-2">
                            {getSupportActionBuckets(locale, t, item).blocked.map((action) => (
                              <span class="badge badge-outline" key={action}>{action}</span>
                            ))}
                          </div>
                        </div>
                      </div>
                    ) : null}
                    {item.supportContract?.missingCapabilities.length ? (
                      <div class="mt-3">
                        <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                          {t("compare.candidatePanel.missingCapabilities")}
                        </div>
                        <div class="mt-2 flex flex-wrap gap-2">
                          {item.supportContract.missingCapabilities.map((capability) => (
                            <span class="badge badge-outline" key={capability}>
                              {formatCapabilityLabel(locale, t, capability)}
                            </span>
                          ))}
                        </div>
                      </div>
                    ) : null}

                    <div class="mt-4 grid gap-3 md:grid-cols-2">
                      <div class="rounded-2xl bg-base-200/60 px-4 py-3">
                        <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                          {t("compare.candidatePanel.listed")}
                        </div>
                        <div class="mt-2 text-xl font-semibold text-ink">{formatCurrency(locale, item.offer?.price)}</div>
                      </div>
                      <div class="rounded-2xl bg-base-200/60 px-4 py-3">
                        <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                          {t("compare.candidatePanel.evidenceNotes")}
                        </div>
                        <div class="mt-2 text-sm leading-6 text-slate-600">
                          {item.brandHint
                            ? compareText("compare.candidatePanel.brand", COMPARE_COPY.candidatePanel.brand, {
                              value: item.brandHint,
                            })
                            : ""}
                          {item.sizeHint
                            ? compareText("compare.candidatePanel.size", COMPARE_COPY.candidatePanel.size, {
                              value: item.sizeHint,
                            })
                            : ""}
                          {item.offer?.originalPrice !== null && item.offer?.originalPrice !== undefined
                            ? compareText("compare.candidatePanel.originalPrice", COMPARE_COPY.candidatePanel.originalPrice, {
                              value: formatCurrency(locale, item.offer.originalPrice),
                            })
                            : compareText("compare.candidatePanel.noOriginalPrice", COMPARE_COPY.candidatePanel.noOriginalPrice)}
                        </div>
                      </div>
                    </div>

                    <div class="mt-4 space-y-3">
                      <div class="rounded-2xl bg-base-200/50 px-4 py-3">
                        <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                          {compareText("compare.candidatePanel.submittedUrl", COMPARE_COPY.candidatePanel.submittedUrl)}
                        </div>
                        <p class="mt-2 break-words font-mono text-xs leading-6 text-slate-600">{item.submittedUrl}</p>
                      </div>
                      {item.normalizedUrl ? (
                        <div class="rounded-2xl bg-base-200/30 px-4 py-3">
                          <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                            {compareText("compare.candidatePanel.normalizedUrl", COMPARE_COPY.candidatePanel.normalizedUrl)}
                          </div>
                          <p class="mt-2 break-words font-mono text-xs leading-6 text-slate-600">{item.normalizedUrl}</p>
                        </div>
                      ) : null}
                    </div>

                    {item.errorCode ? (
                      <p class="mt-3 text-sm text-error">
                        {compareText("compare.candidatePanel.errorCode", COMPARE_COPY.candidatePanel.errorCode, {
                          value: item.errorCode,
                        })}
                      </p>
                    ) : null}
                  </div>

                  <div class="w-full xl:max-w-sm">
                    {item.offer ? (
                      <div class="rounded-2xl border border-base-300 bg-base-100/80 p-4">
                        <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                          {t("compare.candidatePanel.recommendedCta")}
                        </div>
                        <p class="mt-2 text-sm leading-6 text-slate-600">
                          {t("compare.candidatePanel.recommendedCtaSummary")}
                        </p>
                        <button
                          class="btn btn-primary mt-4"
                          onClick={() =>
                            useComparisonForTask(
                              item.submittedUrl,
                              item.normalizedUrl,
                              item.offer!.title,
                              item.storeKey,
                              item.candidateKey,
                              item.brandHint,
                              item.sizeHint,
                            )
                          }
                          type="button"
                        >
                          {compareText("compare.candidatePanel.createWatchTaskFromRow", COMPARE_COPY.candidatePanel.createWatchTaskFromRow)}
                        </button>

                        {item.candidateKey ? (
                          <div class="mt-4 rounded-2xl bg-base-200/40 px-4 py-3">
                            <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                              {compareText("compare.candidatePanel.evidenceFingerprint", COMPARE_COPY.candidatePanel.evidenceFingerprint)}
                            </div>
                            <p class="mt-2 break-words font-mono text-xs leading-6 text-slate-600">{item.candidateKey}</p>
                          </div>
                        ) : null}
                      </div>
                    ) : (
                      <div class="rounded-2xl border border-base-300 bg-base-100/80 p-4 text-sm leading-6 text-slate-600">
                        {compareText("compare.candidatePanel.noDurableCta", COMPARE_COPY.candidatePanel.noDurableCta)}
                      </div>
                    )}
                  </div>
                </div>
              </article>
            ))}
          </div>
        </div>
      ) : null}

      {result ? (
        <div class="grid gap-4 xl:grid-cols-[1.1fr,0.9fr]">
          <aside class="rounded-[1.75rem] border border-base-300 bg-base-100/95 p-6 shadow-card">
            <p class="text-xs font-semibold uppercase tracking-[0.2em] text-ember">
              {t("compare.groupBuilder.eyebrow")}
            </p>
            <h3 class="mt-2 text-xl font-semibold text-ink">
              {t("compare.groupBuilder.title")}
            </h3>
            <p class="mt-3 text-sm leading-6 text-slate-600">
              {t("compare.groupBuilder.summary")}
            </p>

            <div class="mt-4 grid gap-4 md:grid-cols-2">
              <label class="form-control md:col-span-2">
                <span class="label-text font-medium">
                  {compareText("compare.groupBuilder.groupTitle", COMPARE_COPY.groupBuilder.groupTitle)}
                </span>
                <input
                  class="input input-bordered"
                  onInput={(event) => updateGroupForm("title", (event.currentTarget as HTMLInputElement).value)}
                  value={groupForm.title}
                />
              </label>

              <label class="form-control">
                <span class="label-text font-medium">
                  {compareText("compare.groupBuilder.zipCode", COMPARE_COPY.groupBuilder.zipCode)}
                </span>
                <input
                  class="input input-bordered"
                  onInput={(event) => updateGroupForm("zipCode", (event.currentTarget as HTMLInputElement).value)}
                  value={groupForm.zipCode}
                />
              </label>

              <label class="form-control">
                <span class="label-text font-medium">
                  {compareText("compare.groupBuilder.cadenceMinutes", COMPARE_COPY.groupBuilder.cadenceMinutes)}
                </span>
                <input
                  class="input input-bordered"
                  min="5"
                  onInput={(event) =>
                    updateGroupForm("cadenceMinutes", Number((event.currentTarget as HTMLInputElement).value))
                  }
                  type="number"
                  value={groupForm.cadenceMinutes}
                />
              </label>

              <label class="form-control">
                <span class="label-text font-medium">
                  {compareText("compare.groupBuilder.thresholdType", COMPARE_COPY.groupBuilder.thresholdType)}
                </span>
                <select
                  class="select select-bordered"
                  onInput={(event) =>
                    updateGroupForm(
                      "thresholdType",
                      (event.currentTarget as HTMLSelectElement).value as ThresholdType,
                    )
                  }
                  value={groupForm.thresholdType}
                >
                  <option value="price_below">
                    {compareText("compare.groupBuilder.thresholdPriceBelow", COMPARE_COPY.groupBuilder.thresholdPriceBelow)}
                  </option>
                  <option value="price_drop_percent">
                    {compareText("compare.groupBuilder.thresholdDropPercent", COMPARE_COPY.groupBuilder.thresholdDropPercent)}
                  </option>
                  <option value="effective_price_below">
                    {compareText("compare.groupBuilder.thresholdEffectiveBelow", COMPARE_COPY.groupBuilder.thresholdEffectiveBelow)}
                  </option>
                </select>
              </label>

              <label class="form-control">
                <span class="label-text font-medium">
                  {compareText("compare.groupBuilder.thresholdValue", COMPARE_COPY.groupBuilder.thresholdValue)}
                </span>
                <input
                  class="input input-bordered"
                  min="0"
                  onInput={(event) =>
                    updateGroupForm("thresholdValue", Number((event.currentTarget as HTMLInputElement).value))
                  }
                  step="0.01"
                  type="number"
                  value={groupForm.thresholdValue}
                />
                <span class="label-text-alt mt-2 text-slate-500">
                  {compareText("compare.groupBuilder.thresholdHelp", COMPARE_COPY.groupBuilder.thresholdHelp)}
                </span>
              </label>

              <label class="form-control">
                <span class="label-text font-medium">
                  {compareText("compare.groupBuilder.cooldownMinutes", COMPARE_COPY.groupBuilder.cooldownMinutes)}
                </span>
                <input
                  class="input input-bordered"
                  min="0"
                  onInput={(event) =>
                    updateGroupForm("cooldownMinutes", Number((event.currentTarget as HTMLInputElement).value))
                  }
                  type="number"
                  value={groupForm.cooldownMinutes}
                />
              </label>

              <label class="form-control md:col-span-2">
                <span class="label-text font-medium">
                  {compareText("compare.groupBuilder.recipientEmail", COMPARE_COPY.groupBuilder.recipientEmail)}
                </span>
                <input
                  class="input input-bordered"
                  onInput={(event) =>
                    updateGroupForm("recipientEmail", (event.currentTarget as HTMLInputElement).value)
                  }
                  type="email"
                  value={groupForm.recipientEmail}
                />
              </label>

              <label class="label cursor-pointer justify-start gap-3 md:col-span-2">
                <input
                  checked={groupForm.notificationsEnabled}
                  class="checkbox"
                  onInput={(event) =>
                    updateGroupForm("notificationsEnabled", (event.currentTarget as HTMLInputElement).checked)
                  }
                  type="checkbox"
                />
                <span class="label-text">
                  {compareText("compare.groupBuilder.enableNotifications", COMPARE_COPY.groupBuilder.enableNotifications)}
                </span>
              </label>
            </div>

            <div class="mt-5 rounded-2xl bg-base-200/60 p-4">
              <div class="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                {compareText("compare.groupBuilder.rowsEnteringBasket", COMPARE_COPY.groupBuilder.rowsEnteringBasket)}
              </div>
              <div class="mt-3 space-y-3">
                {groupReadyCandidates.length ? (
                  groupReadyCandidates.map((candidate) => {
                    const comparison = comparisonByCandidateKey.get(candidate.candidateKey);
                    return (
                      <div class="rounded-2xl border border-base-300 bg-base-100/80 px-4 py-3" key={candidate.candidateKey}>
                        <div class="flex items-start justify-between gap-3">
                          <div>
                            <div class="font-semibold text-ink">{candidate.titleSnapshot}</div>
                            <div class="mt-1 text-xs text-slate-500">
                              {compareText("compare.groupBuilder.listedAtStore", COMPARE_COPY.groupBuilder.listedAtStore, {
                                storeKey: candidate.storeKey,
                                value: formatCurrency(locale, comparison?.offer?.price),
                              })}
                            </div>
                          </div>
                          <span class="badge badge-outline">
                            {compareText("compare.groupBuilder.similarity", COMPARE_COPY.groupBuilder.similarity, {
                              value: formatOneDecimal(locale, candidate.similarityScore),
                            })}
                          </span>
                        </div>
                        <p class="mt-2 break-words text-xs leading-6 text-slate-600">{candidate.submittedUrl}</p>
                      </div>
                    );
                  })
                ) : (
                  <p class="text-sm text-slate-600">
                    {compareText("compare.groupBuilder.noSuccessfulCandidates", COMPARE_COPY.groupBuilder.noSuccessfulCandidates)}
                  </p>
                )}
              </div>
            </div>

            {groupError ? <div class="alert alert-error mt-5">{resolveUiMessage(groupError, t)}</div> : null}
            {createGroupMutation.isPending ? (
              <div class="alert alert-info mt-5">
                {compareText("compare.groupBuilder.creating", COMPARE_COPY.groupBuilder.creating)}
              </div>
            ) : null}

            <div class="mt-6">
              <button
                class="btn btn-primary"
                disabled={groupReadyCandidates.length < 2 || createGroupMutation.isPending}
                onClick={onCreateGroup}
                type="button"
              >
                {compareText("compare.groupBuilder.createButton", COMPARE_COPY.groupBuilder.createButton)}
              </button>
              {groupReadyCandidates.length < 2 ? (
                <p class="mt-3 text-xs leading-5 text-slate-500">
                  {compareText("compare.groupBuilder.lockedHint", COMPARE_COPY.groupBuilder.lockedHint)}
                </p>
              ) : null}
            </div>
          </aside>

          <aside class="rounded-[1.75rem] border border-base-300 bg-base-100/95 p-6 shadow-card">
            <h3 class="text-lg font-semibold text-ink">
              {t("compare.pairEvidence.title")}
            </h3>
            <p class="mt-2 text-sm leading-6 text-slate-600">
              {t("compare.pairEvidence.summary")}
            </p>
            {result.matches.length ? (
              <div class="mt-4 space-y-3">
                {result.matches.map((item) => {
                  const left = item.leftCandidateKey ? comparisonByCandidateKey.get(item.leftCandidateKey) : null;
                  const right = item.rightCandidateKey ? comparisonByCandidateKey.get(item.rightCandidateKey) : null;
                  const confidenceTone =
                    item.score >= STRONG_MATCH_SCORE
                      ? "badge-success"
                      : item.score >= REVIEW_MATCH_SCORE
                        ? "badge-warning"
                        : "badge-error";

                  return (
                    <div class="rounded-2xl border border-base-300 px-4 py-3" key={`${item.leftProductKey}-${item.rightProductKey}`}>
                      <div class="flex items-start justify-between gap-4">
                        <div>
                          <div class="font-semibold text-ink">
                            {left ? getComparisonLabel(left) : `${item.leftStoreKey}:${item.leftProductKey}`}
                          </div>
                          <div class="mt-1 text-sm text-slate-600">
                            {compareText("compare.pairEvidence.versus", COMPARE_COPY.pairEvidence.versus)}{" "}
                            {right ? getComparisonLabel(right) : `${item.rightStoreKey}:${item.rightProductKey}`}
                          </div>
                        </div>
                        <div class="text-right">
                          <span class={`badge ${confidenceTone}`}>
                            {item.score >= STRONG_MATCH_SCORE
                              ? compareText("compare.pairEvidence.strong", COMPARE_COPY.pairEvidence.strong)
                              : item.score >= REVIEW_MATCH_SCORE
                                ? compareText("compare.pairEvidence.review", COMPARE_COPY.pairEvidence.review)
                                : compareText("compare.pairEvidence.weak", COMPARE_COPY.pairEvidence.weak)}
                          </span>
                          <div class="mt-2 text-2xl font-semibold text-ember">{formatOneDecimal(locale, item.score)}</div>
                          <div class="mt-1 text-xs text-slate-500">
                            {compareText("compare.pairEvidence.titleSimilarity", COMPARE_COPY.pairEvidence.titleSimilarity, {
                              value: formatOneDecimal(locale, item.titleSimilarity),
                            })}
                          </div>
                        </div>
                      </div>

                      <div class="mt-3 flex flex-wrap gap-2 text-xs">
                        <span class="badge badge-outline">
                          {compareText("compare.pairEvidence.brand", COMPARE_COPY.pairEvidence.brand, {
                            value: item.brandSignal ?? compareText("compare.pairEvidence.unknown", COMPARE_COPY.pairEvidence.unknown),
                          })}
                        </span>
                        <span class="badge badge-outline">
                          {compareText("compare.pairEvidence.size", COMPARE_COPY.pairEvidence.size, {
                            value: item.sizeSignal ?? compareText("compare.pairEvidence.unknown", COMPARE_COPY.pairEvidence.unknown),
                          })}
                        </span>
                        <span class="badge badge-outline">
                          {compareText("compare.pairEvidence.keys", COMPARE_COPY.pairEvidence.keys, {
                            value: item.productKeySignal ?? compareText("compare.pairEvidence.unknown", COMPARE_COPY.pairEvidence.unknown),
                          })}
                        </span>
                      </div>

                      {item.whyLike?.length ? (
                        <div class="mt-3">
                          <div class="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                            {t("compare.pairEvidence.whyClose")}
                          </div>
                          <ul class="mt-2 space-y-1 text-sm text-slate-600">
                            {item.whyLike.map((reason) => (
                              <li key={reason}>- {reason}</li>
                            ))}
                          </ul>
                        </div>
                      ) : null}

                      {item.whyUnlike?.length ? (
                        <div class="mt-3">
                          <div class="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                            {t("compare.pairEvidence.whyDiffer")}
                          </div>
                          <ul class="mt-2 space-y-1 text-sm text-slate-600">
                            {item.whyUnlike.map((reason) => (
                              <li key={reason}>- {reason}</li>
                            ))}
                          </ul>
                        </div>
                      ) : null}

                      <div class="mt-3 rounded-2xl bg-base-200/40 px-3 py-3 text-xs leading-6 text-slate-500">
                        {item.leftCandidateKey ?? "--"}
                        <br />
                        {item.rightCandidateKey ?? "--"}
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p class="mt-4 text-sm text-slate-600">
                {compareText("compare.pairEvidence.noPairScore", COMPARE_COPY.pairEvidence.noPairScore)}
              </p>
            )}
          </aside>
        </div>
      ) : null}
    </section>
  );
}
