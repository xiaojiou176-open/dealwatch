import { currentGroupId } from "../lib/routes";
import { formatCurrency, formatDateTime, formatNumber, interpolate, type AppLocale, useI18n } from "../lib/i18n";
import { useRunWatchGroup, useUpdateWatchGroup, useWatchGroupDetail } from "../lib/hooks";
import type {
  AIAssistEnvelope,
  DeliveryStatus,
  HealthStatus,
  RunStatus,
  WatchGroupDetail,
  WatchGroupMember,
  WatchGroupRun,
} from "../types";

function healthTone(value: HealthStatus): string {
  switch (value) {
    case "healthy":
      return "badge-success";
    case "degraded":
      return "badge-warning";
    case "blocked":
      return "badge-error";
    case "needs_attention":
      return "badge-error";
  }
}

function healthCopy(t: (key: string) => string, locale: AppLocale, value: HealthStatus): string {
  switch (value) {
    case "healthy":
      return resolvePageCopy(t, locale, "groupDetail.health.healthy", GROUP_DETAIL_COPY.health.healthy);
    case "degraded":
      return resolvePageCopy(t, locale, "groupDetail.health.degraded", GROUP_DETAIL_COPY.health.degraded);
    case "blocked":
      return resolvePageCopy(t, locale, "groupDetail.health.blocked", GROUP_DETAIL_COPY.health.blocked);
    case "needs_attention":
      return resolvePageCopy(t, locale, "groupDetail.health.needsAttention", GROUP_DETAIL_COPY.health.needsAttention);
  }
}

function runTone(value: RunStatus): string {
  switch (value) {
    case "succeeded":
      return "badge-success";
    case "running":
      return "badge-warning";
    case "queued":
      return "badge-outline";
    case "blocked":
      return "badge-error";
    case "failed":
      return "badge-error";
  }
}

function deliveryTone(value: DeliveryStatus): string {
  switch (value) {
    case "delivered":
      return "badge-success";
    case "sent":
      return "badge-outline";
    case "bounced":
      return "badge-error";
    case "failed":
      return "badge-error";
    case "queued":
      return "badge-warning";
  }
}

type NoteTone = "success" | "warning" | "error" | "info";

interface ReliabilityNote {
  tone: NoteTone;
  title: string;
  detail: string;
}

type DraftMessage = { en: string };

const GROUP_DETAIL_COPY = {
  hero: {
    operationalSummary: {
      en: "This is the long-lived compare basket view: one place to judge the winner, the runner-up, and whether the basket still deserves operator trust.",
    },
    zip: { en: "ZIP {{value}}", },
    backoffUntil: { en: "Backoff until {{value}}", },
  },
  groupStatus: {
    active: { en: "Active", },
    paused: { en: "Paused", },
  },
  health: {
    healthy: { en: "Healthy", },
    degraded: { en: "Degraded", },
    blocked: { en: "Blocked", },
    needsAttention: { en: "Needs Attention", },
  },
  runStatus: {
    succeeded: { en: "Succeeded", },
    running: { en: "Running", },
    queued: { en: "Queued", },
    blocked: { en: "Blocked", },
    failed: { en: "Failed", },
  },
  reliability: {
    strong: { en: "Strong", },
    caution: { en: "Caution", },
    weak: { en: "Weak", },
  },
  ai: {
    label: {
      available: { en: "available", },
      disabled: { en: "disabled", },
      error: { en: "error", },
      skipped: { en: "skipped", },
      unavailable: { en: "unavailable", },
    },
    headline: {
      ok: { en: "AI decision explanation", },
      disabled: { en: "AI assistance is disabled", },
      error: { en: "AI decision explanation hit an error", },
      skipped: { en: "AI decision explanation was skipped", },
      unavailable: { en: "AI decision explanation unavailable", },
    },
    summary: {
      ok: {
        en: "This layer explains the current winner in plain language. The deterministic decision, runner-up comparison, and risk notes still lead the page.",
      },
      disabled: {
        en: "AI assistance is disabled for this workspace. Current decision, winner vs runner-up, and deterministic risk notes remain the source of truth.",
      },
      error: {
        en: "AI decision explanation could not be generated for this group. Review the deterministic decision and risk notes instead.",
      },
      skipped: {
        en: "AI decision explanation was skipped for this group. The deterministic decision and risk notes still describe the basket state.",
      },
      unavailable: {
        en: "AI decision explanation unavailable. Showing deterministic winner, runner-up, and risk notes only.",
      },
    },
  },
  badges: {
    operatorAttention: { en: "operator attention", },
    currentWinner: { en: "current winner", },
    runnerUp: { en: "runner-up", },
    noResult: { en: "no result yet", },
  },
  candidate: {
    unknownStore: { en: "unknown store", },
    brand: { en: "Brand: {{value}}", },
    size: { en: "Size: {{value}}", },
    similarity: { en: "Similarity {{value}}", },
    lastObserved: { en: "Last observed {{value}}", },
    noObservation: { en: "No observation timestamp yet", },
    candidateKey: { en: "Candidate key", },
  },
  comparison: {
    winnerEyebrow: { en: "Winner", },
    runnerUpEyebrow: { en: "Runner-up", },
    noWinner: { en: "No current winner has been established yet.", },
    noRunnerUp: { en: "No runner-up is available yet, so the basket still lacks a clear second-place comparison.", },
  },
  notes: {
    operatorReviewRequiredTitle: { en: "Operator review is required", },
    operatorReviewRequiredDetail: { en: "Automation is paused until someone inspects the latest failure and decides whether to rerun.", },
    noRunTitle: { en: "No run evidence yet", },
    noRunDetail: { en: "The group exists, but there is no run record yet, so there is still no current winner or reliability baseline.", },
    latestRunDirtyTitle: { en: "The latest run did not finish cleanly", },
    latestRunDirtyDetail: { en: "Latest run status is {{status}}, so the current decision should be treated as incomplete evidence.", },
    backoffTitle: { en: "Backoff is active", },
    backoffDetail: { en: "The runtime is waiting until {{value}} before it will retry automatically.", },
    failuresTitle: { en: "Recent failures reduced confidence", },
    failuresDetail: { en: "{{count}} consecutive failure{{plural}} mean the next rerun should happen with intent, not by habit.", },
    failedMembersTitle: { en: "Some candidate rows failed inside the latest basket run", },
    failedMembersDetail: { en: "{{count}} member{{plural}} did not return clean evidence, so the winner may be correct but not fully contested.", },
    thinLeadTitle: { en: "The winner lead is thin", },
    thinLeadDetail: { en: "A spread of {{value}} means the winner could flip on the next run with only a small price change.", },
    noRunnerUpTitle: { en: "No runner-up is established yet", },
    noRunnerUpDetail: { en: "The current winner has evidence, but the basket still lacks a clean second-place row for direct comparison.", },
    stableTitle: { en: "The current basket looks operationally stable", },
    stableDetailWithTime: { en: "Latest success was captured at {{value}} and no obvious reliability blocker is active.", },
    stableDetailWithoutTime: { en: "No obvious blocker is active right now.", },
    noWinnerHeadline: { en: "No current winner yet", },
    winnerLeadHeadline: { en: "{{title}} leads by {{value}}", },
    winnerCurrentHeadline: { en: "{{title}} is the current winner", },
    cadenceMinutes: { en: "{{count}} min", },
    lastSuccess: { en: "Last success", },
    lastFailureKind: { en: "Last failure kind", },
    finished: { en: "Finished {{value}}", },
    pendingDelivery: { en: "Pending delivery timestamp", },
    delivered: { en: "Delivered {{value}}", },
    bounced: { en: "Bounced {{value}}", },
    sent: { en: "Sent {{value}}", },
    runId: { en: "Run id: {{value}}", },
    decisionReasonFallback: {
      en: "No deterministic decision reason returned yet, so treat this group as waiting for stronger evidence.",
    },
  },
  aiPanel: {
    title: { en: "AI decision read", },
    note: {
      en: "Use this as the readable explanation layer for the current basket. Deterministic winner, runner-up, and risk notes still stay primary.",
    },
  },
  recentRuns: {
    summary: {
      en: "This is the basket flight recorder: each run shows whether the current winner was earned cleanly or still needs another deliberate look.",
    },
  },
  deliveryStatus: {
    delivered: { en: "Delivered", },
    sent: { en: "Sent", },
    bounced: { en: "Bounced", },
    failed: { en: "Failed", },
    queued: { en: "Queued", },
  },
} as const;

function resolvePageCopy(
  t: (key: string) => string,
  locale: AppLocale,
  key: string,
  fallback: DraftMessage,
  values?: Record<string, string | number>,
): string {
  const translated = t(key);
  const template = translated === key ? fallback.en : translated;
  return values ? interpolate(template, values) : template;
}

function formatOneDecimal(locale: AppLocale, value: number | null | undefined, fallback = "--"): string {
  return formatNumber(locale, value, fallback, {
    maximumFractionDigits: 1,
    minimumFractionDigits: 1,
  });
}

function groupStatusCopy(t: (key: string) => string, locale: AppLocale, value: WatchGroupDetail["group"]["status"]): string {
  switch (value) {
    case "active":
      return resolvePageCopy(t, locale, "groupDetail.groupStatus.active", GROUP_DETAIL_COPY.groupStatus.active);
    case "paused":
      return resolvePageCopy(t, locale, "groupDetail.groupStatus.paused", GROUP_DETAIL_COPY.groupStatus.paused);
    default:
      return value;
  }
}

function runStatusCopy(t: (key: string) => string, locale: AppLocale, value: RunStatus): string {
  switch (value) {
    case "succeeded":
      return resolvePageCopy(t, locale, "groupDetail.runStatus.succeeded", GROUP_DETAIL_COPY.runStatus.succeeded);
    case "running":
      return resolvePageCopy(t, locale, "groupDetail.runStatus.running", GROUP_DETAIL_COPY.runStatus.running);
    case "queued":
      return resolvePageCopy(t, locale, "groupDetail.runStatus.queued", GROUP_DETAIL_COPY.runStatus.queued);
    case "blocked":
      return resolvePageCopy(t, locale, "groupDetail.runStatus.blocked", GROUP_DETAIL_COPY.runStatus.blocked);
    case "failed":
      return resolvePageCopy(t, locale, "groupDetail.runStatus.failed", GROUP_DETAIL_COPY.runStatus.failed);
    default:
      return value;
  }
}

function reliabilityCopy(t: (key: string) => string, locale: AppLocale, value: string): string {
  switch (value) {
    case "strong":
      return resolvePageCopy(t, locale, "groupDetail.reliability.strong", GROUP_DETAIL_COPY.reliability.strong);
    case "caution":
      return resolvePageCopy(t, locale, "groupDetail.reliability.caution", GROUP_DETAIL_COPY.reliability.caution);
    case "weak":
      return resolvePageCopy(t, locale, "groupDetail.reliability.weak", GROUP_DETAIL_COPY.reliability.weak);
    default:
      return value;
  }
}

function deliveryStatusCopy(t: (key: string) => string, locale: AppLocale, value: DeliveryStatus): string {
  switch (value) {
    case "delivered":
      return resolvePageCopy(t, locale, "groupDetail.deliveryStatus.delivered", GROUP_DETAIL_COPY.deliveryStatus.delivered);
    case "sent":
      return resolvePageCopy(t, locale, "groupDetail.deliveryStatus.sent", GROUP_DETAIL_COPY.deliveryStatus.sent);
    case "bounced":
      return resolvePageCopy(t, locale, "groupDetail.deliveryStatus.bounced", GROUP_DETAIL_COPY.deliveryStatus.bounced);
    case "failed":
      return resolvePageCopy(t, locale, "groupDetail.deliveryStatus.failed", GROUP_DETAIL_COPY.deliveryStatus.failed);
    case "queued":
      return resolvePageCopy(t, locale, "groupDetail.deliveryStatus.queued", GROUP_DETAIL_COPY.deliveryStatus.queued);
  }
}

function noteToneClass(tone: NoteTone): string {
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

function aiAssistLabel(t: (key: string) => string, locale: AppLocale, status: AIAssistEnvelope["status"]): string {
  switch (status) {
    case "ok":
      return resolvePageCopy(t, locale, "groupDetail.ai.label.available", GROUP_DETAIL_COPY.ai.label.available);
    case "disabled":
      return resolvePageCopy(t, locale, "groupDetail.ai.label.disabled", GROUP_DETAIL_COPY.ai.label.disabled);
    case "error":
      return resolvePageCopy(t, locale, "groupDetail.ai.label.error", GROUP_DETAIL_COPY.ai.label.error);
    case "skipped":
      return resolvePageCopy(t, locale, "groupDetail.ai.label.skipped", GROUP_DETAIL_COPY.ai.label.skipped);
    case "unavailable":
      return resolvePageCopy(t, locale, "groupDetail.ai.label.unavailable", GROUP_DETAIL_COPY.ai.label.unavailable);
  }
}

function groupAIHeadline(t: (key: string) => string, locale: AppLocale, status: AIAssistEnvelope["status"]): string {
  switch (status) {
    case "ok":
      return resolvePageCopy(t, locale, "groupDetail.ai.headline.ok", GROUP_DETAIL_COPY.ai.headline.ok);
    case "disabled":
      return resolvePageCopy(t, locale, "groupDetail.ai.headline.disabled", GROUP_DETAIL_COPY.ai.headline.disabled);
    case "error":
      return resolvePageCopy(t, locale, "groupDetail.ai.headline.error", GROUP_DETAIL_COPY.ai.headline.error);
    case "skipped":
      return resolvePageCopy(t, locale, "groupDetail.ai.headline.skipped", GROUP_DETAIL_COPY.ai.headline.skipped);
    case "unavailable":
      return resolvePageCopy(t, locale, "groupDetail.ai.headline.unavailable", GROUP_DETAIL_COPY.ai.headline.unavailable);
  }
}

function groupAISummary(t: (key: string) => string, locale: AppLocale, status: AIAssistEnvelope["status"]): string {
  switch (status) {
    case "ok":
      return resolvePageCopy(t, locale, "groupDetail.ai.summary.ok", GROUP_DETAIL_COPY.ai.summary.ok);
    case "disabled":
      return resolvePageCopy(t, locale, "groupDetail.ai.summary.disabled", GROUP_DETAIL_COPY.ai.summary.disabled);
    case "error":
      return resolvePageCopy(t, locale, "groupDetail.ai.summary.error", GROUP_DETAIL_COPY.ai.summary.error);
    case "skipped":
      return resolvePageCopy(t, locale, "groupDetail.ai.summary.skipped", GROUP_DETAIL_COPY.ai.summary.skipped);
    case "unavailable":
      return resolvePageCopy(t, locale, "groupDetail.ai.summary.unavailable", GROUP_DETAIL_COPY.ai.summary.unavailable);
  }
}

function buildReliabilityNotes(
  t: (key: string) => string,
  locale: AppLocale,
  payload: WatchGroupDetail,
  latestRun: WatchGroupRun | null,
  runnerUpMember: WatchGroupMember | null,
): ReliabilityNote[] {
  const { group, members } = payload;
  const notes: ReliabilityNote[] = [];

  if (group.manualInterventionRequired) {
    notes.push({
      tone: "error",
      title: resolvePageCopy(t, locale, "groupDetail.notes.operatorReviewRequiredTitle", GROUP_DETAIL_COPY.notes.operatorReviewRequiredTitle),
      detail: resolvePageCopy(t, locale, "groupDetail.notes.operatorReviewRequiredDetail", GROUP_DETAIL_COPY.notes.operatorReviewRequiredDetail),
    });
  }

  if (!latestRun) {
    notes.push({
      tone: "info",
      title: resolvePageCopy(t, locale, "groupDetail.notes.noRunTitle", GROUP_DETAIL_COPY.notes.noRunTitle),
      detail: resolvePageCopy(t, locale, "groupDetail.notes.noRunDetail", GROUP_DETAIL_COPY.notes.noRunDetail),
    });
  } else if (latestRun.status !== "succeeded") {
    notes.push({
      tone: "error",
      title: resolvePageCopy(t, locale, "groupDetail.notes.latestRunDirtyTitle", GROUP_DETAIL_COPY.notes.latestRunDirtyTitle),
      detail:
        latestRun.errorMessage ??
        resolvePageCopy(t, locale, "groupDetail.notes.latestRunDirtyDetail", GROUP_DETAIL_COPY.notes.latestRunDirtyDetail, {
          status: latestRun.status,
        }),
    });
  }

  if (group.backoffUntil) {
    notes.push({
      tone: "warning",
      title: resolvePageCopy(t, locale, "groupDetail.notes.backoffTitle", GROUP_DETAIL_COPY.notes.backoffTitle),
      detail: resolvePageCopy(t, locale, "groupDetail.notes.backoffDetail", GROUP_DETAIL_COPY.notes.backoffDetail, {
        value: formatDateTime(locale, group.backoffUntil),
      }),
    });
  }

  if (group.consecutiveFailures > 0) {
    notes.push({
      tone: "warning",
      title: resolvePageCopy(t, locale, "groupDetail.notes.failuresTitle", GROUP_DETAIL_COPY.notes.failuresTitle),
      detail: resolvePageCopy(t, locale, "groupDetail.notes.failuresDetail", GROUP_DETAIL_COPY.notes.failuresDetail, {
        count: group.consecutiveFailures,
        plural: group.consecutiveFailures === 1 ? "" : "s",
      }),
    });
  }

  if (latestRun) {
    const failedMembers = latestRun.memberResults.filter((item) => item.status !== "succeeded").length;
    if (failedMembers > 0) {
      notes.push({
        tone: "warning",
        title: resolvePageCopy(t, locale, "groupDetail.notes.failedMembersTitle", GROUP_DETAIL_COPY.notes.failedMembersTitle),
        detail: resolvePageCopy(t, locale, "groupDetail.notes.failedMembersDetail", GROUP_DETAIL_COPY.notes.failedMembersDetail, {
          count: failedMembers,
          plural: failedMembers === 1 ? "" : "s",
        }),
      });
    }
    if (latestRun.priceSpread !== null && latestRun.priceSpread <= 1) {
      notes.push({
        tone: "warning",
        title: resolvePageCopy(t, locale, "groupDetail.notes.thinLeadTitle", GROUP_DETAIL_COPY.notes.thinLeadTitle),
        detail: resolvePageCopy(t, locale, "groupDetail.notes.thinLeadDetail", GROUP_DETAIL_COPY.notes.thinLeadDetail, {
          value: formatCurrency(locale, latestRun.priceSpread),
        }),
      });
    }
  }

  if (!runnerUpMember && latestRun?.status === "succeeded") {
    notes.push({
      tone: "info",
      title: resolvePageCopy(t, locale, "groupDetail.notes.noRunnerUpTitle", GROUP_DETAIL_COPY.notes.noRunnerUpTitle),
      detail: resolvePageCopy(t, locale, "groupDetail.notes.noRunnerUpDetail", GROUP_DETAIL_COPY.notes.noRunnerUpDetail),
    });
  }

  if (!notes.length) {
    notes.push({
      tone: "success",
      title: resolvePageCopy(t, locale, "groupDetail.notes.stableTitle", GROUP_DETAIL_COPY.notes.stableTitle),
      detail:
        group.lastSuccessAt
          ? resolvePageCopy(t, locale, "groupDetail.notes.stableDetailWithTime", GROUP_DETAIL_COPY.notes.stableDetailWithTime, {
            value: formatDateTime(locale, group.lastSuccessAt),
          })
          : resolvePageCopy(t, locale, "groupDetail.notes.stableDetailWithoutTime", GROUP_DETAIL_COPY.notes.stableDetailWithoutTime),
    });
  }

  return notes;
}

function buildDecisionHeadline(
  t: (key: string) => string,
  locale: AppLocale,
  group: WatchGroupDetail["group"],
  winnerMember: WatchGroupMember | null,
  runnerUpMember: WatchGroupMember | null,
  latestRun: WatchGroupRun | null,
): string {
  if (!winnerMember) {
    return resolvePageCopy(t, locale, "groupDetail.notes.noWinnerHeadline", GROUP_DETAIL_COPY.notes.noWinnerHeadline);
  }
  if (runnerUpMember && latestRun && latestRun.priceSpread !== null) {
    return resolvePageCopy(t, locale, "groupDetail.notes.winnerLeadHeadline", GROUP_DETAIL_COPY.notes.winnerLeadHeadline, {
      title: winnerMember.titleSnapshot,
      value: formatCurrency(locale, latestRun.priceSpread),
    });
  }
  return resolvePageCopy(t, locale, "groupDetail.notes.winnerCurrentHeadline", GROUP_DETAIL_COPY.notes.winnerCurrentHeadline, {
    title: winnerMember.titleSnapshot,
  });
}

function sortMembers(members: WatchGroupMember[]): WatchGroupMember[] {
  return [...members].sort((left, right) => {
    if (left.isCurrentWinner !== right.isCurrentWinner) {
      return left.isCurrentWinner ? -1 : 1;
    }
    const leftPrice = left.latestResult?.effectivePrice ?? Number.POSITIVE_INFINITY;
    const rightPrice = right.latestResult?.effectivePrice ?? Number.POSITIVE_INFINITY;
    return leftPrice - rightPrice;
  });
}

function CandidateComparisonCard(props: {
  eyebrow: string;
  badgeClass: string;
  badgeLabel: string;
  member: WatchGroupMember | null;
  emptyCopy: string;
  locale: AppLocale;
}) {
  const { t } = useI18n();

  if (!props.member) {
    return (
      <div class="rounded-2xl border border-dashed border-base-300 bg-base-100/80 p-4">
        <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">{props.eyebrow}</div>
        <p class="mt-3 text-sm leading-6 text-slate-600">{props.emptyCopy}</p>
      </div>
    );
  }

  const latestResult = props.member.latestResult;

  return (
    <div class="rounded-2xl border border-base-300 bg-base-100/80 p-4">
      <div class="flex items-start justify-between gap-3">
        <div>
          <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">{props.eyebrow}</div>
          <h4 class="mt-2 font-semibold text-ink">{props.member.titleSnapshot}</h4>
          <p class="mt-1 text-xs text-slate-500">
            {latestResult?.storeKey
              ?? resolvePageCopy(t, props.locale, "groupDetail.candidate.unknownStore", GROUP_DETAIL_COPY.candidate.unknownStore)}
          </p>
        </div>
        <span class={`badge ${props.badgeClass}`}>{props.badgeLabel}</span>
      </div>

      <div class="mt-4 grid gap-3 sm:grid-cols-2">
        <div class="rounded-2xl bg-base-200/60 px-4 py-3">
          <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
            {t("chart.listedPrice")}
          </div>
          <div class="mt-2 font-semibold text-ink">{formatCurrency(props.locale, latestResult?.listedPrice ?? null)}</div>
        </div>
        <div class="rounded-2xl bg-base-200/60 px-4 py-3">
          <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
            {t("chart.effectivePrice")}
          </div>
          <div class="mt-2 font-semibold text-ember">{formatCurrency(props.locale, latestResult?.effectivePrice ?? null)}</div>
        </div>
      </div>

      <div class="mt-3 flex flex-wrap gap-2 text-xs">
        {props.member.brandHint ? (
          <span class="badge badge-outline">
            {resolvePageCopy(t, props.locale, "groupDetail.candidate.brand", GROUP_DETAIL_COPY.candidate.brand, {
              value: props.member.brandHint,
            })}
          </span>
        ) : null}
        {props.member.sizeHint ? (
          <span class="badge badge-outline">
            {resolvePageCopy(t, props.locale, "groupDetail.candidate.size", GROUP_DETAIL_COPY.candidate.size, {
              value: props.member.sizeHint,
            })}
          </span>
        ) : null}
        <span class="badge badge-outline">
          {resolvePageCopy(t, props.locale, "groupDetail.candidate.similarity", GROUP_DETAIL_COPY.candidate.similarity, {
            value: formatOneDecimal(props.locale, props.member.similarityScore),
          })}
        </span>
      </div>

      {latestResult?.observedAt ? (
        <p class="mt-3 text-sm text-slate-600">
          {resolvePageCopy(t, props.locale, "groupDetail.candidate.lastObserved", GROUP_DETAIL_COPY.candidate.lastObserved, {
            value: formatDateTime(props.locale, latestResult.observedAt),
          })}
        </p>
      ) : (
        <p class="mt-3 text-sm text-slate-600">
          {resolvePageCopy(t, props.locale, "groupDetail.candidate.noObservation", GROUP_DETAIL_COPY.candidate.noObservation)}
        </p>
      )}

      {latestResult?.errorMessage ? <p class="mt-2 text-sm text-error">{latestResult.errorMessage}</p> : null}

      <div class="mt-3 rounded-2xl bg-base-200/40 px-4 py-3">
        <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
          {resolvePageCopy(t, props.locale, "groupDetail.candidate.candidateKey", GROUP_DETAIL_COPY.candidate.candidateKey)}
        </div>
        <p class="mt-2 break-words font-mono text-xs leading-6 text-slate-600">{props.member.candidateKey}</p>
      </div>
    </div>
  );
}

export function WatchGroupDetailPage() {
  const { locale, t } = useI18n();
  const query = useWatchGroupDetail(currentGroupId.value);
  const runMutation = useRunWatchGroup();
  const updateMutation = useUpdateWatchGroup(currentGroupId.value);

  if (query.isLoading) {
    return <div class="alert alert-info">{t("groupDetail.loading")}</div>;
  }

  if (query.isError || !query.data) {
    return <div class="alert alert-error">{t("groupDetail.error")}</div>;
  }

  const { group, members, runs, deliveries } = query.data;
  const nextStatus = group.status === "paused" ? "active" : "paused";
  const latestRun = runs[0] ?? null;
  const decisionExplain = query.data.decisionExplain;
  const groupAIExplain = query.data.aiExplain;
  const winnerMember =
    members.find((item) => item.id === (group.currentWinnerMemberId ?? latestRun?.winnerMemberId ?? "")) ?? null;
  const runnerUpMember =
    members.find((item) => item.id === (latestRun?.runnerUpMemberId ?? "")) ?? null;
  const rankedMembers = sortMembers(members);
  const reliabilityNotes = buildReliabilityNotes(t, locale, query.data, latestRun, runnerUpMember);
  const decisionReason =
    decisionExplain.decisionReason ??
    group.decisionReason ??
    latestRun?.decisionReason ??
    resolvePageCopy(t, locale, "groupDetail.notes.decisionReasonFallback", GROUP_DETAIL_COPY.notes.decisionReasonFallback);
  const decisionHeadline =
    decisionExplain.headline || buildDecisionHeadline(t, locale, group, winnerMember, runnerUpMember, latestRun);
  const memberSummary = interpolate(t("groupDetail.summaryTemplate"), {
    count: formatNumber(locale, group.memberCount, "0"),
    plural: group.memberCount === 1 ? "" : "s",
  });

  return (
    <section class="grid gap-4 xl:grid-cols-[1.2fr,0.95fr]">
      <div class="space-y-4">
        <div class="rounded-[1.75rem] border border-base-300 bg-base-100/95 p-6 shadow-card">
          <p class="text-xs font-semibold uppercase tracking-[0.2em] text-ember">{t("groupDetail.heroEyebrow")}</p>
          <div class="mt-2 flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
            <div>
              <h2 class="text-2xl font-semibold text-ink">{group.title}</h2>
              <p class="mt-2 text-sm leading-6 text-slate-600">{memberSummary}</p>
              <p class="mt-2 text-sm leading-6 text-slate-500">
                {resolvePageCopy(t, locale, "groupDetail.hero.operationalSummary", GROUP_DETAIL_COPY.hero.operationalSummary)}
              </p>
              <div class="mt-3 flex flex-wrap gap-2 text-xs">
                <span class="badge badge-outline">
                  {resolvePageCopy(t, locale, "groupDetail.hero.zip", GROUP_DETAIL_COPY.hero.zip, {
                    value: group.zipCode,
                  })}
                </span>
                <span class="badge badge-outline">{groupStatusCopy(t, locale, group.status)}</span>
                <span class={`badge ${healthTone(group.healthStatus)}`}>{healthCopy(t, locale, group.healthStatus)}</span>
                {group.manualInterventionRequired ? (
                  <span class="badge badge-error">
                    {resolvePageCopy(t, locale, "groupDetail.badges.operatorAttention", GROUP_DETAIL_COPY.badges.operatorAttention)}
                  </span>
                ) : null}
              </div>
            </div>

            <div class="grid grid-cols-2 gap-2 text-sm md:min-w-[20rem]">
              <div class="rounded-2xl bg-base-200 px-4 py-3">
                <div class="text-slate-500">{t("groupDetail.winnerEffective")}</div>
                <div class="text-xl font-semibold text-ember">{formatCurrency(locale, group.currentWinnerEffectivePrice)}</div>
              </div>
              <div class="rounded-2xl bg-base-200 px-4 py-3">
                <div class="text-slate-500">{t("groupDetail.spread")}</div>
                <div class="text-xl font-semibold text-ink">{formatCurrency(locale, group.priceSpread)}</div>
              </div>
              <div class="rounded-2xl bg-base-200 px-4 py-3">
                <div class="text-slate-500">{t("groupDetail.cadence")}</div>
                <div class="text-base font-semibold text-ink">
                  {resolvePageCopy(t, locale, "groupDetail.notes.cadenceMinutes", GROUP_DETAIL_COPY.notes.cadenceMinutes, {
                    count: formatNumber(locale, group.cadenceMinutes, "0"),
                  })}
                </div>
              </div>
              <div class="rounded-2xl bg-base-200 px-4 py-3">
                <div class="text-slate-500">{t("groupDetail.latestRun")}</div>
                <div class="mt-2">
                  <span class={`badge ${runTone(latestRun?.status ?? "queued")}`}>
                    {latestRun ? runStatusCopy(t, locale, latestRun.status) : t("groupDetail.noRuns")}
                  </span>
                </div>
              </div>
              <div class="rounded-2xl bg-base-200 px-4 py-3">
                <div class="text-slate-500">{t("groupDetail.reliabilityTitle")}</div>
                <div class="mt-2">
                  <span
                    class={`badge ${
                      decisionExplain.reliability === "strong"
                        ? "badge-success"
                        : decisionExplain.reliability === "caution"
                          ? "badge-warning"
                          : "badge-error"
                    }`}
                  >
                    {reliabilityCopy(t, locale, decisionExplain.reliability)}
                  </span>
                </div>
              </div>
              <div class="rounded-2xl bg-base-200 px-4 py-3">
                <div class="text-slate-500">{t("groupDetail.successfulRows")}</div>
                <div class="text-base font-semibold text-ink">{formatNumber(locale, decisionExplain.candidateOutcomes.successfulCount, "0")}</div>
              </div>
            </div>
          </div>

          <div class={`alert mt-4 ${latestRun?.status === "succeeded" ? "alert-success" : "alert-info"}`}>
            <div>
              <div class="font-semibold">{decisionHeadline}</div>
              <div class="text-sm leading-6">{decisionReason}</div>
            </div>
          </div>

          <div class="mt-4 flex flex-wrap gap-3">
            <button
              class="btn btn-primary"
              disabled={runMutation.isPending}
              onClick={() => runMutation.mutate(group.id)}
              type="button"
            >
              {runMutation.isPending ? t("groupDetail.running") : t("groupDetail.runNow")}
            </button>
            <button
              class="btn btn-outline"
              disabled={updateMutation.isPending}
              onClick={() => updateMutation.mutate({ status: nextStatus })}
              type="button"
            >
              {updateMutation.isPending
                ? t("groupDetail.saving")
                : group.status === "paused"
                  ? t("groupDetail.resume")
                  : t("groupDetail.pause")}
            </button>
            {group.backoffUntil ? (
              <span class="badge badge-warning">
                {resolvePageCopy(t, locale, "groupDetail.hero.backoffUntil", GROUP_DETAIL_COPY.hero.backoffUntil, {
                  value: formatDateTime(locale, group.backoffUntil),
                })}
              </span>
            ) : null}
            {runMutation.isSuccess ? <span class="badge badge-success">{t("groupDetail.refreshed")}</span> : null}
          </div>

          {runMutation.isError ? (
            <div class="alert alert-error mt-4">{t("groupDetail.runError")}</div>
          ) : null}
          {updateMutation.isError ? <div class="alert alert-error mt-4">{t("groupDetail.saveError")}</div> : null}
        </div>

        <div class="rounded-[1.75rem] border border-base-300 bg-base-100/95 p-6 shadow-card">
          <div class="flex items-center justify-between gap-3">
            <div>
              <h3 class="text-xl font-semibold text-ink">{t("groupDetail.winnerVsRunnerUpTitle")}</h3>
              <p class="mt-2 text-sm leading-6 text-slate-600">{t("groupDetail.winnerVsRunnerUpSummary")}</p>
            </div>
            {latestRun?.priceSpread !== null ? (
              <span class="badge badge-outline border-ember text-ember">
                {t("groupDetail.spread")} {formatCurrency(locale, latestRun.priceSpread)}
              </span>
            ) : null}
          </div>

          <div class="mt-4 grid gap-4 md:grid-cols-2">
            <CandidateComparisonCard
              badgeClass="badge-success"
              badgeLabel={resolvePageCopy(t, locale, "groupDetail.badges.currentWinner", GROUP_DETAIL_COPY.badges.currentWinner)}
              emptyCopy={resolvePageCopy(t, locale, "groupDetail.comparison.noWinner", GROUP_DETAIL_COPY.comparison.noWinner)}
              eyebrow={resolvePageCopy(t, locale, "groupDetail.comparison.winnerEyebrow", GROUP_DETAIL_COPY.comparison.winnerEyebrow)}
              locale={locale}
              member={winnerMember}
            />
            <CandidateComparisonCard
              badgeClass="badge-outline"
              badgeLabel={resolvePageCopy(t, locale, "groupDetail.badges.runnerUp", GROUP_DETAIL_COPY.badges.runnerUp)}
              emptyCopy={resolvePageCopy(t, locale, "groupDetail.comparison.noRunnerUp", GROUP_DETAIL_COPY.comparison.noRunnerUp)}
              eyebrow={resolvePageCopy(t, locale, "groupDetail.comparison.runnerUpEyebrow", GROUP_DETAIL_COPY.comparison.runnerUpEyebrow)}
              locale={locale}
              member={runnerUpMember}
            />
          </div>
        </div>

        <div class="rounded-[1.75rem] border border-base-300 bg-base-100/95 p-6 shadow-card">
          <div class="flex items-center justify-between">
            <div>
              <h3 class="text-xl font-semibold text-ink">{t("groupDetail.candidateBasketTitle")}</h3>
              <p class="text-sm text-slate-600">{t("groupDetail.candidateBasketSummary")}</p>
            </div>
            <span class="badge badge-outline">{memberSummary}</span>
          </div>

          <div class="mt-4 grid gap-4 md:grid-cols-2">
            {rankedMembers.map((member) => (
              <article class="rounded-2xl border border-base-300 bg-base-100/80 p-4" key={member.id}>
                <div class="flex items-start justify-between gap-3">
                  <div>
                    <h4 class="font-semibold text-ink">{member.titleSnapshot}</h4>
                    <p class="mt-1 text-xs text-slate-500">
                      {member.latestResult?.storeKey
                        ?? resolvePageCopy(t, locale, "groupDetail.candidate.unknownStore", GROUP_DETAIL_COPY.candidate.unknownStore)}
                    </p>
                  </div>
                  <div class="flex flex-wrap gap-2">
                    {member.isCurrentWinner ? (
                      <span class="badge badge-success">
                        {resolvePageCopy(t, locale, "groupDetail.badges.currentWinner", GROUP_DETAIL_COPY.badges.currentWinner)}
                      </span>
                    ) : null}
                    {member.latestResult ? (
                      <span class={`badge ${runTone(member.latestResult.status)}`}>
                        {runStatusCopy(t, locale, member.latestResult.status)}
                      </span>
                    ) : (
                      <span class="badge badge-outline">
                        {resolvePageCopy(t, locale, "groupDetail.badges.noResult", GROUP_DETAIL_COPY.badges.noResult)}
                      </span>
                    )}
                  </div>
                </div>

                <div class="mt-4 grid gap-3 sm:grid-cols-2">
                  <div class="rounded-2xl bg-base-200/60 px-4 py-3">
                    <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                      {t("chart.listedPrice")}
                    </div>
                    <div class="mt-2 font-semibold text-ink">{formatCurrency(locale, member.latestResult?.listedPrice ?? null)}</div>
                  </div>
                  <div class="rounded-2xl bg-base-200/60 px-4 py-3">
                    <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                      {t("chart.effectivePrice")}
                    </div>
                    <div class="mt-2 font-semibold text-ember">{formatCurrency(locale, member.latestResult?.effectivePrice ?? null)}</div>
                  </div>
                </div>

                <div class="mt-3 flex flex-wrap gap-2 text-xs">
                  {member.brandHint ? (
                    <span class="badge badge-outline">
                      {resolvePageCopy(t, locale, "groupDetail.candidate.brand", GROUP_DETAIL_COPY.candidate.brand, {
                        value: member.brandHint,
                      })}
                    </span>
                  ) : null}
                  {member.sizeHint ? (
                    <span class="badge badge-outline">
                      {resolvePageCopy(t, locale, "groupDetail.candidate.size", GROUP_DETAIL_COPY.candidate.size, {
                        value: member.sizeHint,
                      })}
                    </span>
                  ) : null}
                  <span class="badge badge-outline">
                    {resolvePageCopy(t, locale, "groupDetail.candidate.similarity", GROUP_DETAIL_COPY.candidate.similarity, {
                      value: formatOneDecimal(locale, member.similarityScore),
                    })}
                  </span>
                </div>

                <p class="mt-3 text-sm text-slate-600">
                  {member.latestResult?.observedAt
                    ? resolvePageCopy(t, locale, "groupDetail.candidate.lastObserved", GROUP_DETAIL_COPY.candidate.lastObserved, {
                      value: formatDateTime(locale, member.latestResult.observedAt),
                    })
                    : resolvePageCopy(t, locale, "groupDetail.candidate.noObservation", GROUP_DETAIL_COPY.candidate.noObservation)}
                </p>
                {member.latestResult?.errorMessage ? <p class="mt-2 text-sm text-error">{member.latestResult.errorMessage}</p> : null}

                <div class="mt-3 rounded-2xl bg-base-200/40 px-4 py-3">
                  <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                    {resolvePageCopy(t, locale, "groupDetail.candidate.candidateKey", GROUP_DETAIL_COPY.candidate.candidateKey)}
                  </div>
                  <p class="mt-2 break-words font-mono text-xs leading-6 text-slate-600">{member.candidateKey}</p>
                </div>
              </article>
            ))}
          </div>
        </div>
      </div>

      <div class="space-y-4">
        <div class="rounded-[1.75rem] border border-base-300 bg-base-100/95 p-6 shadow-card">
          <div class="flex items-start justify-between gap-3">
            <div>
              <h3 class="text-lg font-semibold text-ink">{t("groupDetail.riskTitle")}</h3>
              <p class="mt-2 text-sm leading-6 text-slate-600">{t("groupDetail.riskSummary")}</p>
            </div>
            <span class={`badge ${healthTone(group.healthStatus)}`}>{healthCopy(t, locale, group.healthStatus)}</span>
          </div>

          <div class="mt-4 space-y-3">
            {decisionExplain.riskNotes.map((note) => (
              <div class="alert alert-info" key={note}>
                <div>
                  <div class="font-semibold">{t("groupDetail.riskTitle")}</div>
                  <div class="text-sm leading-6">{note}</div>
                </div>
              </div>
            ))}
            {reliabilityNotes.map((note) => (
              <div class={`alert ${noteToneClass(note.tone)}`} key={`${note.title}-${note.detail}`}>
                <div>
                  <div class="font-semibold">{note.title}</div>
                  <div class="text-sm leading-6">{note.detail}</div>
                </div>
              </div>
            ))}
          </div>

          <div class="mt-4 grid gap-3 sm:grid-cols-2">
            <div class="rounded-2xl bg-base-200/60 px-4 py-3 text-sm text-slate-600">
              <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                {resolvePageCopy(t, locale, "groupDetail.notes.lastSuccess", GROUP_DETAIL_COPY.notes.lastSuccess)}
              </div>
              <div class="mt-2 font-semibold text-ink">{formatDateTime(locale, group.lastSuccessAt)}</div>
            </div>
            <div class="rounded-2xl bg-base-200/60 px-4 py-3 text-sm text-slate-600">
              <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                {resolvePageCopy(t, locale, "groupDetail.notes.lastFailureKind", GROUP_DETAIL_COPY.notes.lastFailureKind)}
              </div>
              <div class="mt-2 font-semibold text-ink">{group.lastFailureKind ?? "--"}</div>
            </div>
          </div>

          <div class="mt-4 rounded-2xl border border-dashed border-base-300 bg-base-200/30 px-4 py-4">
            <div class="flex items-start justify-between gap-3">
              <div>
                <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                  {resolvePageCopy(t, locale, "groupDetail.aiPanel.title", GROUP_DETAIL_COPY.aiPanel.title)}
                </div>
                <h4 class="mt-2 text-lg font-semibold text-ink">
                  {groupAIExplain.title ?? groupAIHeadline(t, locale, groupAIExplain.status)}
                </h4>
              </div>
              <span class={`badge ${aiAssistBadgeClass(groupAIExplain.status)}`}>
                {aiAssistLabel(t, locale, groupAIExplain.status)}
              </span>
            </div>
            <p class="mt-2 text-sm leading-6 text-slate-600">
              {groupAIExplain.summary ?? groupAISummary(t, locale, groupAIExplain.status)}
            </p>
            {groupAIExplain.detail ? (
              <p class="mt-2 text-sm leading-6 text-slate-500">{groupAIExplain.detail}</p>
            ) : null}
            {groupAIExplain.bullets.length ? (
              <ul class="mt-3 space-y-2 text-sm leading-6 text-slate-600">
                {groupAIExplain.bullets.map((bullet) => (
                  <li key={bullet}>- {bullet}</li>
                ))}
              </ul>
            ) : null}
            <p class="mt-3 text-xs leading-5 text-slate-500">
              {resolvePageCopy(t, locale, "groupDetail.aiPanel.note", GROUP_DETAIL_COPY.aiPanel.note)}
            </p>
          </div>
        </div>

        <div class="rounded-[1.75rem] border border-base-300 bg-base-100/95 p-6 shadow-card">
          <h3 class="text-lg font-semibold text-ink">{t("groupDetail.recentRunsTitle")}</h3>
          <p class="mt-2 text-sm leading-6 text-slate-600">
            {resolvePageCopy(t, locale, "groupDetail.recentRuns.summary", GROUP_DETAIL_COPY.recentRuns.summary)}
          </p>
          <div class="mt-4 space-y-3">
            {runs.length ? (
              runs.map((run) => (
                <div class="rounded-2xl border border-base-300 px-4 py-3" key={run.id}>
                  <div class="flex items-start justify-between gap-3">
                    <div>
                      <div class="font-semibold text-ink">{formatDateTime(locale, run.startedAt)}</div>
                      <p class="mt-1 text-xs text-slate-500">
                        {resolvePageCopy(t, locale, "groupDetail.notes.finished", GROUP_DETAIL_COPY.notes.finished, {
                          value: formatDateTime(locale, run.finishedAt),
                        })}
                      </p>
                    </div>
                    <span class={`badge ${runTone(run.status)}`}>{runStatusCopy(t, locale, run.status)}</span>
                  </div>

                  <div class="mt-3 flex flex-wrap gap-2 text-xs">
                    {run.winnerEffectivePrice !== null ? (
                      <span class="badge badge-outline">
                        {t("groupDetail.winnerEffective")} {formatCurrency(locale, run.winnerEffectivePrice)}
                      </span>
                    ) : null}
                    {run.runnerUpEffectivePrice !== null ? (
                      <span class="badge badge-outline">
                        {t("groupDetail.winnerVsRunnerUpTitle")} {formatCurrency(locale, run.runnerUpEffectivePrice)}
                      </span>
                    ) : null}
                    {run.priceSpread !== null ? (
                      <span class="badge badge-outline">{t("groupDetail.spread")} {formatCurrency(locale, run.priceSpread)}</span>
                    ) : null}
                  </div>

                  <p class="mt-3 text-sm text-slate-600">{run.decisionReason ?? t("groupDetail.riskSummary")}</p>
                  {run.errorMessage ? <p class="mt-2 text-sm text-error">{run.errorMessage}</p> : null}
                  <p class="mt-2 text-xs text-slate-500">
                    {resolvePageCopy(t, locale, "groupDetail.notes.runId", GROUP_DETAIL_COPY.notes.runId, {
                      value: run.id,
                    })}
                  </p>
                </div>
              ))
            ) : (
              <p class="text-sm text-slate-600">{t("groupDetail.noRuns")}</p>
            )}
          </div>
        </div>

        <div class="rounded-[1.75rem] border border-base-300 bg-base-100/95 p-6 shadow-card">
          <h3 class="text-lg font-semibold text-ink">{t("groupDetail.deliveryEventsTitle")}</h3>
          <p class="mt-2 text-sm leading-6 text-slate-600">{t("settings.page.deliveryEventsSummary")}</p>
          <div class="mt-4 space-y-3">
            {deliveries.length ? (
              deliveries.map((event) => (
                <div class="rounded-2xl border border-base-300 px-4 py-3" key={event.id}>
                  <div class="flex items-center justify-between">
                    <span class="font-semibold text-ink">{event.provider}</span>
                    <span class={`badge ${deliveryTone(event.status)}`}>{deliveryStatusCopy(t, locale, event.status)}</span>
                  </div>
                  <p class="mt-1 text-sm text-slate-600">{event.recipient}</p>
                  <p class="text-xs text-slate-500">
                    {event.deliveredAt
                      ? resolvePageCopy(t, locale, "groupDetail.notes.delivered", GROUP_DETAIL_COPY.notes.delivered, {
                        value: formatDateTime(locale, event.deliveredAt),
                      })
                      : event.bouncedAt
                        ? resolvePageCopy(t, locale, "groupDetail.notes.bounced", GROUP_DETAIL_COPY.notes.bounced, {
                          value: formatDateTime(locale, event.bouncedAt),
                        })
                        : event.sentAt
                          ? resolvePageCopy(t, locale, "groupDetail.notes.sent", GROUP_DETAIL_COPY.notes.sent, {
                            value: formatDateTime(locale, event.sentAt),
                          })
                          : resolvePageCopy(t, locale, "groupDetail.notes.pendingDelivery", GROUP_DETAIL_COPY.notes.pendingDelivery)}
                  </p>
                </div>
              ))
            ) : (
              <p class="text-sm text-slate-600">{t("groupDetail.noDeliveries")}</p>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
