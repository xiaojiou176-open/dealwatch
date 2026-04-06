import { currentTaskId } from "../lib/routes";
import { formatCurrency, formatDateTime, formatNumber, formatPercent, interpolate, type AppLocale, useI18n } from "../lib/i18n";
import { useRunWatchTask, useUpdateWatchTask, useWatchTaskDetail } from "../lib/hooks";
import { Suspense, lazy } from "preact/compat";
import type { DeliveryStatus, HealthStatus, TaskRun } from "../types";

const PriceHistoryChart = lazy(() =>
  import("../components/PriceHistoryChart").then((module) => ({ default: module.PriceHistoryChart })),
);

type DraftMessage = { en: string };

const TASK_DETAIL_COPY = {
  sourceUnavailable: { en: "Source URL unavailable", },
  hero: {
    zip: { en: "ZIP {{value}}", },
    backoffUntil: { en: "Backoff until {{value}}", },
  },
  runStatus: {
    succeeded: { en: "Succeeded", },
    running: { en: "Running", },
    queued: { en: "Queued", },
    blocked: { en: "Blocked", },
    failed: { en: "Failed", },
  },
  artifact: {
    eyebrow: { en: "Run evidence package", },
    summary: {
      en: "This block shows what the latest task run actually captured, so operators can judge whether the proof bundle is complete enough to trust the alert.",
    },
    packageReady: { en: "review package ready", },
    packageMissing: { en: "package still partial", },
    deliveryCount: { en: "{{count}} delivery event{{plural}}", },
    latestDeliveryStatus: { en: "latest delivery: {{value}}", },
    cashbackAttached: { en: "cashback quote attached", },
    capturedAt: { en: "Captured {{value}}", },
    proofPath: { en: "Proof directory", },
    reviewPackagePath: { en: "Review package", },
    notAvailable: { en: "Not available yet", },
    sourceLabel: { en: "Source URL", },
  },
  health: {
    healthy: { en: "Healthy", },
    degraded: { en: "Degraded", },
    blocked: { en: "Blocked", },
    needsAttention: { en: "Needs Attention", },
  },
  badges: {
    operatorAttention: { en: "operator attention", },
    newLow: { en: "new low", },
    anomaly: { en: "anomaly: {{reason}}", },
    tracked: { en: "tracked", },
  },
  compareContext: {
    brand: { en: "brand: {{value}}", },
    size: { en: "size: {{value}}", },
    similarity: { en: "similarity {{value}}", },
    candidateKeyLabel: { en: "Candidate key", },
    titleSnapshotLabel: { en: "Captured compare title", },
  },
  latestSignal: {
    deltaLabel: { en: "Price movement", },
    signalStateLabel: { en: "Signal state", },
    recommendedNextLabel: { en: "Recommended next read", },
    fallbackDecisionReason: {
      en: "No extra decision note was returned, so treat this as the latest visible signal and use the task health panel before rerunning.",
    },
  },
  taskHealth: {
    healthState: { en: "Health state", },
    consecutiveFailures: { en: "Consecutive failures", },
    lastFailureKind: { en: "Last failure kind", },
    lastRun: { en: "Last run", },
    timestampUnavailable: { en: "Timestamp unavailable", },
    summary: {
      en: "Treat this as the task's operating-room view: it tells you whether automation is healthy, drifting, or waiting for a deliberate retry.",
    },
    operatorReviewTitle: { en: "Operator review is still required", },
    operatorReviewDetail: {
      en: "Automation already decided this task should not keep self-retrying. Review the last failure before reopening the lane.",
    },
    backoffTitle: { en: "Automatic retry is waiting", },
    backoffDetail: {
      en: "The runtime will not retry again until {{value}}, which gives the last failure time to clear before another attempt.",
    },
    failuresTitle: { en: "Failure streak changed the risk level", },
    failuresDetail: {
      en: "{{count}} consecutive failure{{plural}} mean the next rerun should be intentional, not just habitual button-mashing.",
    },
    healthyTitle: { en: "No immediate recovery blocker", },
    healthyDetail: {
      en: "Recent task telemetry looks stable enough that the next alert can be interpreted as a fresh signal rather than leftover damage.",
    },
  },
  sections: {
    latestSignalSummary: {
      en: "This is the latest price move that would actually matter to an operator: what changed, by how much, and whether the signal looks like a genuine new low or suspicious drift.",
    },
    compareHandoffSummary: {
      en: "This keeps the link back to the compare intake that created the task, so the operator can recover the original candidate evidence instead of treating the task as an orphan.",
    },
    priceTimelineSummary: {
      en: "The chart is the long-view evidence: use it to decide whether the latest alert is a real pattern change or just one noisy scrape.",
    },
    cashbackSummary: {
      en: "Cashback stays secondary to price, but this panel shows whether the current task is carrying an extra savings layer or still lacks that quote.",
    },
    recentRunsSummary: {
      en: "Read the latest attempts here before rerunning. In plain terms: this is the black box recorder for the task lane.",
    },
  },
  cashback: {
    provider: { en: "Provider", },
    offer: { en: "Offer", },
    confidence: { en: "Confidence", },
    noQuote: { en: "No cashback quote attached yet.", },
  },
  recentRuns: {
    errorCode: { en: "error code: {{value}}", },
  },
  delivery: {
    status: {
      delivered: { en: "Delivered", },
      sent: { en: "Sent", },
      bounced: { en: "Bounced", },
      failed: { en: "Failed", },
      queued: { en: "Queued", },
    },
    delivered: { en: "Delivered {{value}}", },
    bounced: { en: "Bounced {{value}}", },
    sent: { en: "Sent {{value}}", },
    pending: { en: "Pending delivery timestamp", },
    noEvents: { en: "No delivery events yet.", },
  },
  errors: {
    run: { en: "Task run failed. Review the latest task run for details.", },
    update: { en: "Failed to update task status.", },
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

function formatSourceLabel(t: (key: string) => string, sourceUrl: string | null): string {
  if (!sourceUrl) {
    const translated = t("taskDetail.sourceUnavailable");
    return translated === "taskDetail.sourceUnavailable" ? TASK_DETAIL_COPY.sourceUnavailable.en : translated;
  }
  try {
    return new URL(sourceUrl).hostname.replace(/^www\./, "");
  } catch {
    return sourceUrl;
  }
}

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
      return resolvePageCopy(t, locale, "taskDetail.health.healthy", TASK_DETAIL_COPY.health.healthy);
    case "degraded":
      return resolvePageCopy(t, locale, "taskDetail.health.degraded", TASK_DETAIL_COPY.health.degraded);
    case "blocked":
      return resolvePageCopy(t, locale, "taskDetail.health.blocked", TASK_DETAIL_COPY.health.blocked);
    case "needs_attention":
      return resolvePageCopy(t, locale, "taskDetail.health.needsAttention", TASK_DETAIL_COPY.health.needsAttention);
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

function taskRunStatusCopy(t: (key: string) => string, locale: AppLocale, value: TaskRun["status"]): string {
  switch (value) {
    case "succeeded":
      return resolvePageCopy(t, locale, "taskDetail.runStatus.succeeded", TASK_DETAIL_COPY.runStatus.succeeded);
    case "running":
      return resolvePageCopy(t, locale, "taskDetail.runStatus.running", TASK_DETAIL_COPY.runStatus.running);
    case "queued":
      return resolvePageCopy(t, locale, "taskDetail.runStatus.queued", TASK_DETAIL_COPY.runStatus.queued);
    case "blocked":
      return resolvePageCopy(t, locale, "taskDetail.runStatus.blocked", TASK_DETAIL_COPY.runStatus.blocked);
    case "failed":
      return resolvePageCopy(t, locale, "taskDetail.runStatus.failed", TASK_DETAIL_COPY.runStatus.failed);
  }
}

function deliveryStatusCopy(t: (key: string) => string, locale: AppLocale, value: string): string {
  switch (value) {
    case "delivered":
      return resolvePageCopy(t, locale, "taskDetail.delivery.status.delivered", TASK_DETAIL_COPY.delivery.status.delivered);
    case "sent":
      return resolvePageCopy(t, locale, "taskDetail.delivery.status.sent", TASK_DETAIL_COPY.delivery.status.sent);
    case "bounced":
      return resolvePageCopy(t, locale, "taskDetail.delivery.status.bounced", TASK_DETAIL_COPY.delivery.status.bounced);
    case "failed":
      return resolvePageCopy(t, locale, "taskDetail.delivery.status.failed", TASK_DETAIL_COPY.delivery.status.failed);
    case "queued":
      return resolvePageCopy(t, locale, "taskDetail.delivery.status.queued", TASK_DETAIL_COPY.delivery.status.queued);
    default:
      return value;
  }
}

function ArtifactEvidencePanel(props: { run: TaskRun }) {
  const { locale, t } = useI18n();
  const { run } = props;
  const evidence = run.artifactEvidence;
  const artifactText = (
    key: string,
    fallback: DraftMessage,
    values?: Record<string, string | number>,
  ) => resolvePageCopy(t, locale, key, fallback, values);

  if (!run.artifactRunDir && !evidence) {
    return null;
  }

  return (
    <div class="mt-3 rounded-[1.5rem] border border-base-300 bg-base-200/40 p-4">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div class="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
            {artifactText("taskDetail.artifact.eyebrow", TASK_DETAIL_COPY.artifact.eyebrow)}
          </div>
          <p class="mt-2 max-w-xl text-sm leading-6 text-slate-600">
            {artifactText("taskDetail.artifact.summary", TASK_DETAIL_COPY.artifact.summary)}
          </p>
        </div>
        <span class={`badge ${evidence?.summaryExists ? "badge-success" : "badge-outline"}`}>
          {evidence?.summaryExists
            ? artifactText("taskDetail.artifact.packageReady", TASK_DETAIL_COPY.artifact.packageReady)
            : artifactText("taskDetail.artifact.packageMissing", TASK_DETAIL_COPY.artifact.packageMissing)}
        </span>
      </div>

      <div class="mt-3 flex flex-wrap gap-2 text-xs">
        <span class="badge badge-outline">
          {artifactText("taskDetail.artifact.deliveryCount", TASK_DETAIL_COPY.artifact.deliveryCount, {
            count: formatNumber(locale, evidence?.deliveryCount ?? 0, "0"),
            plural: (evidence?.deliveryCount ?? 0) === 1 ? "" : "s",
          })}
        </span>
        {evidence?.latestDeliveryStatus ? (
          <span class="badge badge-outline">
            {artifactText("taskDetail.artifact.latestDeliveryStatus", TASK_DETAIL_COPY.artifact.latestDeliveryStatus, {
              value: deliveryStatusCopy(t, locale, evidence.latestDeliveryStatus),
            })}
          </span>
        ) : null}
        {evidence?.hasCashbackQuote ? (
          <span class="badge badge-outline">
            {artifactText("taskDetail.artifact.cashbackAttached", TASK_DETAIL_COPY.artifact.cashbackAttached)}
          </span>
        ) : null}
        <span class="badge badge-outline">
          {artifactText("taskDetail.artifact.capturedAt", TASK_DETAIL_COPY.artifact.capturedAt, {
            value: formatDateTime(locale, evidence?.capturedAt ?? run.finishedAt, t("settings.runtime.noTimestamp")),
          })}
        </span>
      </div>

      <div class="mt-4 grid gap-3 md:grid-cols-3">
        <div class="rounded-2xl bg-base-100/80 px-4 py-3">
          <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
            {t("chart.listedPrice")}
          </div>
          <div class="mt-2 text-xl font-semibold text-ink">{formatCurrency(locale, evidence?.listedPrice ?? null)}</div>
        </div>
        <div class="rounded-2xl bg-base-100/80 px-4 py-3">
          <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
            {t("chart.effectivePrice")}
          </div>
          <div class="mt-2 text-xl font-semibold text-ember">{formatCurrency(locale, evidence?.effectivePrice ?? null)}</div>
        </div>
        <div class="rounded-2xl bg-base-100/80 px-4 py-3">
          <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
            {artifactText("taskDetail.artifact.sourceLabel", TASK_DETAIL_COPY.artifact.sourceLabel)}
          </div>
          <div class="mt-2 text-sm font-semibold text-ink">{formatSourceLabel(t, evidence?.sourceUrl ?? null)}</div>
        </div>
      </div>

      <details class="mt-4 rounded-2xl border border-base-300 bg-base-100/80 px-4 py-3">
        <summary class="cursor-pointer text-sm font-semibold text-ink">
          {artifactText("taskDetail.artifact.eyebrow", TASK_DETAIL_COPY.artifact.eyebrow)}
        </summary>
        <div class="mt-3 space-y-3 text-xs leading-6 text-slate-600">
          <div>
            <div class="font-semibold uppercase tracking-[0.16em] text-slate-500">
              {artifactText("taskDetail.artifact.proofPath", TASK_DETAIL_COPY.artifact.proofPath)}
            </div>
            <p class="mt-1 break-words font-mono">
              {run.artifactRunDir ?? artifactText("taskDetail.artifact.notAvailable", TASK_DETAIL_COPY.artifact.notAvailable)}
            </p>
          </div>
          {evidence?.summaryPath ? (
            <div>
              <div class="font-semibold uppercase tracking-[0.16em] text-slate-500">
                {artifactText("taskDetail.artifact.reviewPackagePath", TASK_DETAIL_COPY.artifact.reviewPackagePath)}
              </div>
              <p class="mt-1 break-words font-mono">{evidence.summaryPath}</p>
            </div>
          ) : null}
        </div>
      </details>
    </div>
  );
}

export function TaskDetailPage() {
  const { locale, t } = useI18n();
  const query = useWatchTaskDetail(currentTaskId.value);
  const runMutation = useRunWatchTask();
  const updateMutation = useUpdateWatchTask(currentTaskId.value);

  if (query.isLoading) {
    return <div class="alert alert-info">{t("taskDetail.loading")}</div>;
  }

  if (query.isError || !query.data) {
    return <div class="alert alert-error">{t("taskDetail.error")}</div>;
  }

  const { task, runs, deliveries, cashbackQuote, priceHistory, latestSignal } = query.data;
  const nextStatus = task.status === "paused" ? "active" : "paused";
  const taskDetailText = (
    key: string,
    fallback: DraftMessage,
    values?: Record<string, string | number>,
  ) => resolvePageCopy(t, locale, key, fallback, values);
  const taskHealthNotes = [];

  if (task.manualInterventionRequired) {
    taskHealthNotes.push({
      title: taskDetailText("taskDetail.taskHealth.operatorReviewTitle", TASK_DETAIL_COPY.taskHealth.operatorReviewTitle),
      detail: taskDetailText("taskDetail.taskHealth.operatorReviewDetail", TASK_DETAIL_COPY.taskHealth.operatorReviewDetail),
      tone: "alert-error",
    });
  }

  if (task.backoffUntil) {
    taskHealthNotes.push({
      title: taskDetailText("taskDetail.taskHealth.backoffTitle", TASK_DETAIL_COPY.taskHealth.backoffTitle),
      detail: taskDetailText("taskDetail.taskHealth.backoffDetail", TASK_DETAIL_COPY.taskHealth.backoffDetail, {
        value: formatDateTime(locale, task.backoffUntil),
      }),
      tone: "alert-warning",
    });
  }

  if (task.consecutiveFailures > 0) {
    taskHealthNotes.push({
      title: taskDetailText("taskDetail.taskHealth.failuresTitle", TASK_DETAIL_COPY.taskHealth.failuresTitle),
      detail: taskDetailText("taskDetail.taskHealth.failuresDetail", TASK_DETAIL_COPY.taskHealth.failuresDetail, {
        count: formatNumber(locale, task.consecutiveFailures, "0"),
        plural: task.consecutiveFailures === 1 ? "" : "s",
      }),
      tone: "alert-warning",
    });
  }

  if (!taskHealthNotes.length) {
    taskHealthNotes.push({
      title: taskDetailText("taskDetail.taskHealth.healthyTitle", TASK_DETAIL_COPY.taskHealth.healthyTitle),
      detail: taskDetailText("taskDetail.taskHealth.healthyDetail", TASK_DETAIL_COPY.taskHealth.healthyDetail),
      tone: "alert-success",
    });
  }

  return (
    <section class="grid gap-4 xl:grid-cols-[1.3fr,0.95fr]">
      <div class="space-y-4">
        <div class="rounded-[1.75rem] border border-base-300 bg-base-100/95 p-6 shadow-card">
          <p class="text-xs font-semibold uppercase tracking-[0.2em] text-ember">{t("taskDetail.heroEyebrow")}</p>
          <div class="mt-2 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <div>
              <h2 class="text-2xl font-semibold text-ink">{task.title}</h2>
              <p class="text-sm text-slate-500">{task.normalizedUrl}</p>
              <div class="mt-2 flex flex-wrap gap-2 text-xs">
                <span class="badge badge-outline">
                  {taskDetailText("taskDetail.hero.zip", TASK_DETAIL_COPY.hero.zip, {
                    value: task.zipCode,
                  })}
                </span>
                <span class="badge badge-outline">{task.storeKey}</span>
                <span class={`badge ${healthTone(task.healthStatus)}`}>{healthCopy(t, locale, task.healthStatus)}</span>
                {task.manualInterventionRequired ? (
                  <span class="badge badge-error">
                    {taskDetailText("taskDetail.badges.operatorAttention", TASK_DETAIL_COPY.badges.operatorAttention)}
                  </span>
                ) : null}
              </div>
            </div>
            <div class="grid grid-cols-2 gap-2 text-sm">
              <div class="rounded-2xl bg-base-200 px-4 py-3">
                <div class="text-slate-500">{t("chart.listedPrice")}</div>
                <div class="text-xl font-semibold text-ink">{formatCurrency(locale, task.lastListedPrice)}</div>
              </div>
              <div class="rounded-2xl bg-base-200 px-4 py-3">
                <div class="text-slate-500">{t("chart.effectivePrice")}</div>
                <div class="text-xl font-semibold text-ember">{formatCurrency(locale, task.lastEffectivePrice)}</div>
              </div>
            </div>
          </div>

          <div class="mt-4 flex flex-wrap gap-3">
            <button
              class="btn btn-primary"
              disabled={runMutation.isPending}
              onClick={() => runMutation.mutate(task.id)}
              type="button"
            >
              {runMutation.isPending ? t("taskDetail.running") : t("taskDetail.runNow")}
            </button>
            <button
              class="btn btn-outline"
              disabled={updateMutation.isPending}
              onClick={() => updateMutation.mutate({ status: nextStatus })}
              type="button"
            >
              {updateMutation.isPending
                ? t("taskDetail.saving")
                : task.status === "paused"
                  ? t("taskDetail.resume")
                  : t("taskDetail.pause")}
            </button>
            {task.backoffUntil ? (
              <span class="badge badge-warning">
                {taskDetailText("taskDetail.hero.backoffUntil", TASK_DETAIL_COPY.hero.backoffUntil, {
                  value: formatDateTime(locale, task.backoffUntil),
                })}
              </span>
            ) : null}
            {runMutation.isSuccess ? <span class="badge badge-success">{t("taskDetail.refreshed")}</span> : null}
          </div>
          {runMutation.isError ? (
            <div class="alert alert-error mt-4">
              {taskDetailText("taskDetail.errors.run", TASK_DETAIL_COPY.errors.run)}
            </div>
          ) : null}
          {updateMutation.isError ? (
            <div class="alert alert-error mt-4">
              {taskDetailText("taskDetail.errors.update", TASK_DETAIL_COPY.errors.update)}
            </div>
          ) : null}
        </div>

        {latestSignal ? (
          <div class="rounded-[1.75rem] border border-base-300 bg-base-100/95 p-6 shadow-card">
            <h3 class="text-xl font-semibold text-ink">{t("taskDetail.latestSignalTitle")}</h3>
            <p class="mt-2 text-sm leading-6 text-slate-600">
              {taskDetailText("taskDetail.sections.latestSignalSummary", TASK_DETAIL_COPY.sections.latestSignalSummary)}
            </p>
            <div class="mt-4 grid gap-3 md:grid-cols-3">
              <div class="rounded-2xl bg-base-200/60 px-4 py-3">
                <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                  {t("chart.listedPrice")}
                </div>
                <div class="mt-2 text-xl font-semibold text-ink">{formatCurrency(locale, latestSignal.previousListedPrice)}</div>
              </div>
              <div class="rounded-2xl bg-base-200/60 px-4 py-3">
                <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                  {taskDetailText("taskDetail.latestSignal.deltaLabel", TASK_DETAIL_COPY.latestSignal.deltaLabel)}
                </div>
                <div class="mt-2 text-xl font-semibold text-ember">
                  {formatCurrency(locale, latestSignal.deltaAmount)}
                </div>
                <div class="mt-1 text-xs text-slate-500">
                  {formatPercent(locale, latestSignal.deltaPct)}
                </div>
              </div>
              <div class="rounded-2xl bg-base-200/60 px-4 py-3">
                <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                  {taskDetailText("taskDetail.latestSignal.signalStateLabel", TASK_DETAIL_COPY.latestSignal.signalStateLabel)}
                </div>
                <div class="mt-2 flex flex-wrap gap-2">
                  {latestSignal.isNewLow ? (
                    <span class="badge badge-success">
                      {taskDetailText("taskDetail.badges.newLow", TASK_DETAIL_COPY.badges.newLow)}
                    </span>
                  ) : null}
                  {latestSignal.anomalyReason ? (
                    <span class="badge badge-warning">
                      {taskDetailText("taskDetail.badges.anomaly", TASK_DETAIL_COPY.badges.anomaly, {
                        reason: latestSignal.anomalyReason,
                      })}
                    </span>
                  ) : null}
                  {!latestSignal.isNewLow && !latestSignal.anomalyReason ? (
                    <span class="badge badge-outline">
                      {taskDetailText("taskDetail.badges.tracked", TASK_DETAIL_COPY.badges.tracked)}
                    </span>
                  ) : null}
                </div>
              </div>
            </div>
            <div class="mt-4 rounded-2xl bg-base-200/40 px-4 py-4">
              <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                {taskDetailText("taskDetail.latestSignal.recommendedNextLabel", TASK_DETAIL_COPY.latestSignal.recommendedNextLabel)}
              </div>
              <p class="mt-2 text-sm leading-6 text-slate-600">
                {latestSignal.decisionReason
                  ?? taskDetailText(
                    "taskDetail.latestSignal.fallbackDecisionReason",
                    TASK_DETAIL_COPY.latestSignal.fallbackDecisionReason,
                  )}
              </p>
            </div>
          </div>
        ) : null}

        {query.data.compareContext ? (
          <div class="rounded-[1.75rem] border border-base-300 bg-base-100/95 p-6 shadow-card">
            <div class="flex items-center justify-between gap-3">
              <div>
                <h3 class="text-xl font-semibold text-ink">{t("taskDetail.compareHandoffTitle")}</h3>
                <p class="text-sm text-slate-600">
                  {taskDetailText("taskDetail.sections.compareHandoffSummary", TASK_DETAIL_COPY.sections.compareHandoffSummary)}
                </p>
              </div>
              <span class="badge badge-outline">{query.data.compareContext.merchantKey}</span>
            </div>
            <div class="mt-4 grid gap-3 md:grid-cols-2">
              <div class="rounded-2xl bg-base-200/50 px-4 py-3">
                <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                  {taskDetailText("taskDetail.compareContext.candidateKeyLabel", TASK_DETAIL_COPY.compareContext.candidateKeyLabel)}
                </div>
                <p class="mt-2 break-words font-mono text-xs leading-6 text-slate-600">{query.data.compareContext.candidateKey}</p>
              </div>
              <div class="rounded-2xl bg-base-200/50 px-4 py-3">
                <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                  {taskDetailText("taskDetail.compareContext.titleSnapshotLabel", TASK_DETAIL_COPY.compareContext.titleSnapshotLabel)}
                </div>
                <p class="mt-2 text-sm leading-6 text-slate-600">{query.data.compareContext.titleSnapshot}</p>
              </div>
            </div>
            <div class="mt-3 flex flex-wrap gap-2 text-xs">
              {query.data.compareContext.brandHint ? (
                <span class="badge badge-outline">
                  {taskDetailText("taskDetail.compareContext.brand", TASK_DETAIL_COPY.compareContext.brand, {
                    value: query.data.compareContext.brandHint,
                  })}
                </span>
              ) : null}
              {query.data.compareContext.sizeHint ? (
                <span class="badge badge-outline">
                  {taskDetailText("taskDetail.compareContext.size", TASK_DETAIL_COPY.compareContext.size, {
                    value: query.data.compareContext.sizeHint,
                  })}
                </span>
              ) : null}
              <span class="badge badge-outline">
                {taskDetailText("taskDetail.compareContext.similarity", TASK_DETAIL_COPY.compareContext.similarity, {
                  value: formatOneDecimal(locale, query.data.compareContext.similarityScore),
                })}
              </span>
            </div>
          </div>
        ) : null}

        <div class="rounded-[1.75rem] border border-base-300 bg-base-100/95 p-6 shadow-card">
          <div class="flex items-center justify-between">
            <div>
              <h3 class="text-xl font-semibold text-ink">{t("taskDetail.priceTimelineTitle")}</h3>
              <p class="text-sm text-slate-600">
                {taskDetailText("taskDetail.sections.priceTimelineSummary", TASK_DETAIL_COPY.sections.priceTimelineSummary)}
              </p>
            </div>
            <span class="badge badge-outline border-ember text-ember">{task.thresholdType}</span>
          </div>
          <div class="mt-4">
            <Suspense fallback={<div class="alert alert-info">{t("common.loadingRoute")}</div>}>
              <PriceHistoryChart points={priceHistory} />
            </Suspense>
          </div>
        </div>
      </div>

      <div class="space-y-4">
        <div class="rounded-[1.75rem] border border-base-300 bg-base-100/95 p-6 shadow-card">
          <h3 class="text-lg font-semibold text-ink">{t("taskDetail.taskHealthTitle")}</h3>
          <p class="mt-2 text-sm leading-6 text-slate-600">
            {taskDetailText("taskDetail.taskHealth.summary", TASK_DETAIL_COPY.taskHealth.summary)}
          </p>
            <div class="mt-4 space-y-3 text-sm text-slate-600">
              <div class="flex items-center justify-between">
              <span>{taskDetailText("taskDetail.taskHealth.healthState", TASK_DETAIL_COPY.taskHealth.healthState)}</span>
              <span class={`badge ${healthTone(task.healthStatus)}`}>{healthCopy(t, locale, task.healthStatus)}</span>
              </div>
              <div class="flex items-center justify-between">
              <span>{taskDetailText("taskDetail.taskHealth.consecutiveFailures", TASK_DETAIL_COPY.taskHealth.consecutiveFailures)}</span>
              <span class="font-semibold text-ink">{formatNumber(locale, task.consecutiveFailures, "0")}</span>
              </div>
              <div class="flex items-center justify-between">
              <span>{taskDetailText("taskDetail.taskHealth.lastFailureKind", TASK_DETAIL_COPY.taskHealth.lastFailureKind)}</span>
              <span class="font-semibold text-ink">{task.lastFailureKind ?? "--"}</span>
              </div>
              <div class="flex items-center justify-between">
              <span>{taskDetailText("taskDetail.taskHealth.lastRun", TASK_DETAIL_COPY.taskHealth.lastRun)}</span>
              <span class="font-semibold text-ink">
                {formatDateTime(
                  locale,
                  task.lastRunAt,
                  taskDetailText("taskDetail.taskHealth.timestampUnavailable", TASK_DETAIL_COPY.taskHealth.timestampUnavailable),
                )}
              </span>
              </div>
            </div>
            <div class="mt-4 space-y-3">
              {taskHealthNotes.map((note) => (
                <div class={`alert ${note.tone}`} key={`${note.title}-${note.detail}`}>
                  <div>
                    <div class="font-semibold">{note.title}</div>
                    <div class="text-sm leading-6">{note.detail}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

        <div class="rounded-[1.75rem] border border-base-300 bg-base-100/95 p-6 shadow-card">
          <h3 class="text-lg font-semibold text-ink">{t("taskDetail.cashbackTitle")}</h3>
          <p class="mt-2 text-sm leading-6 text-slate-600">
            {taskDetailText("taskDetail.sections.cashbackSummary", TASK_DETAIL_COPY.sections.cashbackSummary)}
          </p>
          {cashbackQuote ? (
            <div class="mt-4 space-y-2 text-sm text-slate-600">
              <div class="flex items-center justify-between">
                <span>{taskDetailText("taskDetail.cashback.provider", TASK_DETAIL_COPY.cashback.provider)}</span>
                <span class="font-semibold text-ink">{cashbackQuote.provider}</span>
              </div>
              <div class="flex items-center justify-between">
                <span>{taskDetailText("taskDetail.cashback.offer", TASK_DETAIL_COPY.cashback.offer)}</span>
                <span class="font-semibold text-ember">{cashbackQuote.rateLabel}</span>
              </div>
              <div class="flex items-center justify-between">
                <span>{taskDetailText("taskDetail.cashback.confidence", TASK_DETAIL_COPY.cashback.confidence)}</span>
                <span class="font-semibold text-ink">{formatPercent(locale, cashbackQuote.confidence * 100)}</span>
              </div>
            </div>
          ) : (
            <p class="mt-4 text-sm text-slate-600">
              {taskDetailText("taskDetail.cashback.noQuote", TASK_DETAIL_COPY.cashback.noQuote)}
            </p>
          )}
        </div>

        <div class="rounded-[1.75rem] border border-base-300 bg-base-100/95 p-6 shadow-card">
          <h3 class="text-lg font-semibold text-ink">{t("taskDetail.recentRunsTitle")}</h3>
          <p class="mt-2 text-sm leading-6 text-slate-600">
            {taskDetailText("taskDetail.sections.recentRunsSummary", TASK_DETAIL_COPY.sections.recentRunsSummary)}
          </p>
          <div class="mt-4 space-y-3">
            {runs.map((run) => (
              <div class="rounded-2xl border border-base-300 px-4 py-3" key={run.id}>
                <div class="flex items-center justify-between gap-3">
                  <span class="font-semibold text-ink">{run.id}</span>
                  <div class="flex flex-wrap gap-2">
                    {run.triggeredBy ? <span class="badge badge-outline">{run.triggeredBy}</span> : null}
                    <span class="badge badge-outline">{taskRunStatusCopy(t, locale, run.status)}</span>
                  </div>
                </div>
                <p class="mt-1 text-xs text-slate-500">
                  {formatDateTime(locale, run.startedAt, t("settings.runtime.noTimestamp"))}
                </p>
                {run.errorCode ? (
                  <p class="mt-2 text-xs text-slate-500">
                    {taskDetailText("taskDetail.recentRuns.errorCode", TASK_DETAIL_COPY.recentRuns.errorCode, {
                      value: run.errorCode,
                    })}
                  </p>
                ) : null}
                <ArtifactEvidencePanel run={run} />
                {run.errorMessage ? <p class="mt-2 text-sm text-error">{run.errorMessage}</p> : null}
              </div>
            ))}
          </div>
        </div>

        <div class="rounded-[1.75rem] border border-base-300 bg-base-100/95 p-6 shadow-card">
          <h3 class="text-lg font-semibold text-ink">{t("taskDetail.deliveryEventsTitle")}</h3>
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
                      ? taskDetailText("taskDetail.delivery.delivered", TASK_DETAIL_COPY.delivery.delivered, {
                        value: formatDateTime(locale, event.deliveredAt),
                      })
                      : event.bouncedAt
                        ? taskDetailText("taskDetail.delivery.bounced", TASK_DETAIL_COPY.delivery.bounced, {
                          value: formatDateTime(locale, event.bouncedAt),
                        })
                        : event.sentAt
                          ? taskDetailText("taskDetail.delivery.sent", TASK_DETAIL_COPY.delivery.sent, {
                            value: formatDateTime(locale, event.sentAt),
                          })
                          : taskDetailText("taskDetail.delivery.pending", TASK_DETAIL_COPY.delivery.pending)}
                  </p>
                </div>
              ))
            ) : (
              <p class="text-sm text-slate-600">
                {taskDetailText("taskDetail.delivery.noEvents", TASK_DETAIL_COPY.delivery.noEvents)}
              </p>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
