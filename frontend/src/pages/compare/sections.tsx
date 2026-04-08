import { formatCurrency, formatDateTime, formatNumber, type AppLocale } from "../../lib/i18n";
import type {
  AIAssistEnvelope,
  CompareRecommendation,
  ComparePreviewComparison,
  ComparePreviewResponse,
  SavedCompareEvidencePackage,
  ThresholdType,
  WatchGroupCandidateInput,
} from "../../types";
import {
  COMPARE_COPY,
  type DraftMessage,
} from "./copy";
import type { CompareDecisionBoard } from "./helpers";
import {
  aiAssistBadgeClass,
  aiAssistLabel,
  compareAIHeadline,
  compareAISummary,
  decisionAlertClass,
  decisionBadgeClass,
  formatCapabilityLabel,
  formatOneDecimal,
  getComparisonLabel,
  getComparisonStatusLabel,
  getComparisonStatusTone,
  getComparisonSummary,
  getSupportActionBuckets,
  getSupportTierLabel,
  resolveUiMessage,
} from "./helpers";

type CompareText = (
  key: string,
  fallback: DraftMessage,
  values?: Record<string, string | number>,
) => string;

export interface CompareGroupFormState {
  title: string;
  zipCode: string;
  cadenceMinutes: number;
  thresholdType: ThresholdType;
  thresholdValue: number;
  cooldownMinutes: number;
  recipientEmail: string;
  notificationsEnabled: boolean;
}

interface CompareDecisionSectionProps {
  compareAIExplain: AIAssistEnvelope | null;
  recommendation: CompareRecommendation | null;
  compareText: CompareText;
  copyCurrentEvidenceSummary: () => void;
  createRuntimeEvidencePackage: () => void;
  createRuntimePending: boolean;
  decisionBoard: CompareDecisionBoard;
  evidenceError: string;
  evidenceNotice: string;
  locale: AppLocale;
  result: ComparePreviewResponse;
  saveEvidencePackage: () => void;
  t: (key: string) => string;
}

export function CompareDecisionSection({
  compareAIExplain,
  recommendation,
  compareText,
  copyCurrentEvidenceSummary,
  createRuntimeEvidencePackage,
  createRuntimePending,
  decisionBoard,
  evidenceError,
  evidenceNotice,
  locale,
  result,
  saveEvidencePackage,
  t,
}: CompareDecisionSectionProps) {
  return (
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
            <div class="mt-2 text-2xl font-semibold text-ink">{formatNumber(locale, result.resolvedCount, "0")}</div>
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

        {recommendation ? (
          <div class="mt-4 rounded-2xl border border-base-300 bg-base-200/30 px-4 py-4">
            <div class="flex items-start justify-between gap-3">
              <div>
                <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                  {compareText("compare.recommendation.eyebrow", COMPARE_COPY.recommendation.eyebrow)}
                </div>
                <h4 class="mt-2 text-lg font-semibold text-ink">{recommendation.headline}</h4>
              </div>
              <span class={`badge ${recommendationBadgeClass(recommendation)}`}>
                {recommendation.abstention.active
                  ? compareText(
                      "compare.recommendation.verdict.insufficient_evidence",
                      COMPARE_COPY.recommendation.verdict.insufficient_evidence,
                    )
                  : recommendation.verdict === "wait"
                    ? compareText("compare.recommendation.verdict.wait", COMPARE_COPY.recommendation.verdict.wait)
                    : compareText(
                        "compare.recommendation.verdict.recheck_later",
                        COMPARE_COPY.recommendation.verdict.recheck_later,
                      )}
              </span>
            </div>
            <p class="mt-2 text-sm leading-6 text-slate-600">{recommendation.summary}</p>
            {recommendation.abstention.active && recommendation.abstention.reason ? (
              <div class="mt-3 rounded-2xl border border-dashed border-base-300 bg-base-100/80 px-4 py-3 text-sm leading-6 text-slate-600">
                <div class="font-semibold">
                  {compareText("compare.recommendation.whyAbstained", COMPARE_COPY.recommendation.whyAbstained)}
                </div>
                <p class="mt-2">{recommendation.abstention.reason}</p>
              </div>
            ) : null}
            <div class="mt-4 grid gap-3 lg:grid-cols-3">
              <div class="rounded-2xl bg-base-100/80 px-4 py-4">
                <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                  {compareText("compare.recommendation.basisTitle", COMPARE_COPY.recommendation.basisTitle)}
                </div>
                <ul class="mt-3 space-y-2 text-sm leading-6 text-slate-600">
                  {recommendation.basis.map((item) => (
                    <li key={item}>- {item}</li>
                  ))}
                </ul>
              </div>
              <div class="rounded-2xl bg-base-100/80 px-4 py-4">
                <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                  {compareText("compare.recommendation.uncertaintyTitle", COMPARE_COPY.recommendation.uncertaintyTitle)}
                </div>
                <ul class="mt-3 space-y-2 text-sm leading-6 text-slate-600">
                  {recommendation.uncertaintyNotes.map((item) => (
                    <li key={item}>- {item}</li>
                  ))}
                </ul>
              </div>
              <div class="rounded-2xl bg-base-100/80 px-4 py-4">
                <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                  {compareText("compare.recommendation.evidenceRefsTitle", COMPARE_COPY.recommendation.evidenceRefsTitle)}
                </div>
                <ul class="mt-3 space-y-2 text-sm leading-6 text-slate-600">
                  {recommendation.evidenceRefs.map((item) => (
                    <li key={`${item.code}-${item.anchor}`}>
                      <span class="font-semibold text-ink">{item.label}</span>
                      <span class="text-slate-500"> · {item.anchor}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
            <p class="mt-3 text-xs leading-5 text-slate-500">{recommendation.deterministicPrimaryNote}</p>
            <p class="mt-1 text-xs leading-5 text-slate-500">{recommendation.feedbackBoundary}</p>
            <p class="mt-1 text-xs leading-5 text-slate-500">{recommendation.overrideBoundary}</p>
          </div>
        ) : null}

        <div class="mt-4 flex flex-wrap gap-3">
          <button class="btn btn-primary" onClick={saveEvidencePackage} type="button">{t("compare.decision.saveReviewPackage")}</button>
          <button
            class="btn btn-outline"
            disabled={createRuntimePending}
            onClick={createRuntimeEvidencePackage}
            type="button"
          >
            {createRuntimePending
              ? t("compare.decision.creatingRuntimePackage")
              : t("compare.decision.createRuntimePackage")}
          </button>
          <button
            class="btn btn-ghost"
            disabled={false}
            onClick={copyCurrentEvidenceSummary}
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
  );
}

function recommendationBadgeClass(recommendation: CompareRecommendation): string {
  if (recommendation.abstention.active) {
    return "badge-outline";
  }
  if (recommendation.verdict === "wait") {
    return "badge-warning";
  }
  return "badge-info";
}

interface SavedEvidenceSectionProps {
  compareText: CompareText;
  copySavedEvidenceSummary: (payload: SavedCompareEvidencePackage | null) => void;
  locale: AppLocale;
  savedPackages: SavedCompareEvidencePackage[];
  selectedPackageId: string | null;
  selectedSavedPackage: SavedCompareEvidencePackage | null;
  selectSavedPackage: (packageId: string) => void;
  t: (key: string) => string;
}

export function SavedEvidenceSection({
  compareText,
  copySavedEvidenceSummary,
  locale,
  savedPackages,
  selectedPackageId,
  selectedSavedPackage,
  selectSavedPackage,
  t,
}: SavedEvidenceSectionProps) {
  return (
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
                  selectedPackageId === item.id
                    ? "border-ember bg-amber-50/70"
                    : "border-base-300 bg-base-100/80 hover:border-ember/50"
                }`}
                key={item.id}
                onClick={() => selectSavedPackage(item.id)}
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
                    onClick={() => copySavedEvidenceSummary(selectedSavedPackage)}
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
  );
}

interface CandidateEvidenceSectionProps {
  compareText: CompareText;
  comparisonByCandidateKey: Map<string, ComparePreviewComparison>;
  groupReadyCandidates: WatchGroupCandidateInput[];
  locale: AppLocale;
  result: ComparePreviewResponse;
  scoreByCandidate: Record<string, number>;
  t: (key: string) => string;
  useComparisonForTask: (
    submittedUrl: string,
    normalizedUrl: string | undefined,
    offerTitle: string,
    storeKey: string | undefined,
    candidateKey: string | undefined,
    brandHint: string | undefined,
    sizeHint: string | undefined,
  ) => void;
}

export function CandidateEvidenceSection({
  compareText,
  comparisonByCandidateKey,
  groupReadyCandidates,
  locale,
  result,
  scoreByCandidate,
  t,
  useComparisonForTask,
}: CandidateEvidenceSectionProps) {
  return (
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
  );
}

interface GroupBuilderSectionProps {
  compareText: CompareText;
  comparisonByCandidateKey: Map<string, ComparePreviewComparison>;
  createGroupPending: boolean;
  groupError: string;
  groupForm: CompareGroupFormState;
  groupReadyCandidates: WatchGroupCandidateInput[];
  locale: AppLocale;
  t: (key: string) => string;
  updateGroupForm: (key: keyof CompareGroupFormState, value: string | number | boolean) => void;
  createGroup: () => void;
}

export function GroupBuilderSection({
  compareText,
  comparisonByCandidateKey,
  createGroup,
  createGroupPending,
  groupError,
  groupForm,
  groupReadyCandidates,
  locale,
  t,
  updateGroupForm,
}: GroupBuilderSectionProps) {
  return (
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
      {createGroupPending ? (
        <div class="alert alert-info mt-5">
          {compareText("compare.groupBuilder.creating", COMPARE_COPY.groupBuilder.creating)}
        </div>
      ) : null}

      <div class="mt-6">
        <button
          class="btn btn-primary"
          disabled={groupReadyCandidates.length < 2 || createGroupPending}
          onClick={createGroup}
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
  );
}

interface PairEvidenceSectionProps {
  compareText: CompareText;
  comparisonByCandidateKey: Map<string, ComparePreviewComparison>;
  locale: AppLocale;
  matches: ComparePreviewResponse["matches"];
  t: (key: string) => string;
}

export function PairEvidenceSection({
  compareText,
  comparisonByCandidateKey,
  locale,
  matches,
  t,
}: PairEvidenceSectionProps) {
  return (
    <aside class="rounded-[1.75rem] border border-base-300 bg-base-100/95 p-6 shadow-card">
      <h3 class="text-lg font-semibold text-ink">
        {t("compare.pairEvidence.title")}
      </h3>
      <p class="mt-2 text-sm leading-6 text-slate-600">
        {t("compare.pairEvidence.summary")}
      </p>
      {matches.length ? (
        <div class="mt-4 space-y-3">
          {matches.map((item) => {
            const left = item.leftCandidateKey ? comparisonByCandidateKey.get(item.leftCandidateKey) : null;
            const right = item.rightCandidateKey ? comparisonByCandidateKey.get(item.rightCandidateKey) : null;
            const confidenceTone =
              item.score >= 85
                ? "badge-success"
                : item.score >= 70
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
                      {item.score >= 85
                        ? compareText("compare.pairEvidence.strong", COMPARE_COPY.pairEvidence.strong)
                        : item.score >= 70
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
  );
}
