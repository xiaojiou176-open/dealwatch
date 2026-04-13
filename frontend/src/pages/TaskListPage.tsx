import { navigate } from "../lib/routes";
import { formatCurrency, formatDateTime, formatNumber, interpolate, type AppLocale, useI18n } from "../lib/i18n";
import { useRecoveryInbox, useRunWatchGroup, useRunWatchTask, useWatchGroups, useWatchTasks } from "../lib/hooks";
import type { AIAssistEnvelope, HealthStatus } from "../types";

const statusTone: Record<string, string> = {
  active: "badge-success",
  paused: "badge-warning",
  error: "badge-error",
};

const healthTone: Record<HealthStatus, string> = {
  healthy: "badge-success",
  degraded: "badge-warning",
  blocked: "badge-error",
  needs_attention: "badge-error",
};

type DraftMessage = { en: string; "zh-CN"?: string };

const TASK_LIST_COPY = {
  status: {
    active: { en: "Active", },
    paused: { en: "Paused", },
    error: { en: "Error", },
  },
  health: {
    healthy: { en: "Healthy", },
    degraded: { en: "Degraded", },
    blocked: { en: "Blocked", },
    needsAttention: { en: "Needs Attention", },
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
      ok: { en: "AI recovery copilot", },
      disabled: { en: "AI recovery copilot is disabled", },
      error: { en: "AI recovery copilot hit an error", },
      skipped: { en: "AI recovery copilot was skipped", },
      unavailable: { en: "AI recovery copilot unavailable", },
    },
    panelTitle: { en: "AI recovery read", },
    panelNote: {
      en: "Use this as the readable recovery layer for the current group item. The deterministic reason and recommended action still stay primary.",
    },
    summary: {
      ok: {
        en: "This layer suggests a human-friendly recovery read of the current issue. The deterministic reason and recommended action stay primary.",
      },
      disabled: {
        en: "AI assistance is disabled for this workspace. The deterministic recovery reason and recommended action remain the evidence anchor.",
      },
      error: {
        en: "AI recovery copilot could not be generated for this group item. Use the deterministic reason and recommended action instead.",
      },
      skipped: {
        en: "AI recovery copilot was skipped for this group item. The deterministic reason and recommended action still describe what to do next.",
      },
      unavailable: {
        en: "AI recovery copilot unavailable. Keeping the deterministic recovery reason and recommended action as the evidence anchor.",
      },
    },
  },
  recovery: {
    itemsBadge: { en: "{{count}} items", },
    tasksBadge: { en: "{{count}} tasks", },
    groupsBadge: { en: "{{count}} groups", },
    taskBadge: { en: "task", },
    groupBadge: { en: "group", },
    noNormalizedUrl: { en: "No normalized URL yet", },
    operatorAttention: { en: "operator attention", },
    failures: { en: "{{count}} failure{{plural}}", },
    noSingleTasks: { en: "No single-task recovery items right now.", },
    groupCandidates: { en: "ZIP {{zipCode}} · {{count}} candidate{{plural}}", },
    noGroupItems: {
      en: "No compare-aware group recovery items right now.",
    },
    backoffUntil: { en: "Backoff until {{value}}", },
    nextRun: { en: "Next run {{value}}", },
    lastRun: { en: "Last run {{value}}", },
  },
  board: {
    needsAttention: { en: "needs attention", },
    memberCandidates: { en: "{{count}} member candidates", },
    backoffUntil: { en: "Backoff until {{value}}", },
    zipBadge: { en: "ZIP {{value}}", },
    currentWinner: { en: "Current winner {{value}}", },
    noGroups: {
      en: "No compare-aware groups yet. Build one from a successful Compare Preview result.",
    },
  },
  dashboard: {
    operatorDeskSummary: {
      en: "Keep this page feeling like an operator desk: scan what is live, see what needs intervention, and move back into compare or detail only when the evidence truly requires it.",
    },
    activeTasks: { en: "active tasks", },
    activeTasksNote: {
      en: "The current set of single-target monitoring lanes that are still live.",
    },
    attentionNow: { en: "attention now", },
    attentionNowNote: {
      en: "Rows that already asked for deliberate operator review.",
    },
    compareGroups: { en: "compare groups", },
    compareGroupsNote: {
      en: "Baskets with enough members to behave like a real compare lane.",
    },
    liveWinners: { en: "live winners", },
    liveWinnersNote: {
      en: "Groups that currently expose a winner instead of only awaiting proof.",
    },
    bestNextMove: { en: "best next move", },
    bestNextMoveTitle: { en: "Start in Compare when evidence is still noisy.", },
    bestNextMoveSummary: {
      en: "The dashboard should not invite operators to create watch state too early. Use Compare first whenever the winner is still ambiguous.",
    },
    proofDiscipline: { en: "proof discipline", },
    proofDisciplineTitle: { en: "Keep evidence before commitment.", },
    proofDisciplineSummary: {
      en: "A saved compare package is the safer checkpoint. Long-lived tasks and groups should only happen after the basket reads honestly.",
    },
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
  const template = translated === key ? fallback[locale] ?? fallback.en : translated;
  return values ? interpolate(template, values) : template;
}

function healthCopy(t: (key: string) => string, locale: AppLocale, value: HealthStatus): string {
  switch (value) {
    case "healthy":
      return resolvePageCopy(t, locale, "taskList.health.healthy", TASK_LIST_COPY.health.healthy);
    case "degraded":
      return resolvePageCopy(t, locale, "taskList.health.degraded", TASK_LIST_COPY.health.degraded);
    case "blocked":
      return resolvePageCopy(t, locale, "taskList.health.blocked", TASK_LIST_COPY.health.blocked);
    case "needs_attention":
      return resolvePageCopy(t, locale, "taskList.health.needsAttention", TASK_LIST_COPY.health.needsAttention);
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
      return resolvePageCopy(t, locale, "taskList.ai.label.available", TASK_LIST_COPY.ai.label.available);
    case "disabled":
      return resolvePageCopy(t, locale, "taskList.ai.label.disabled", TASK_LIST_COPY.ai.label.disabled);
    case "error":
      return resolvePageCopy(t, locale, "taskList.ai.label.error", TASK_LIST_COPY.ai.label.error);
    case "skipped":
      return resolvePageCopy(t, locale, "taskList.ai.label.skipped", TASK_LIST_COPY.ai.label.skipped);
    case "unavailable":
      return resolvePageCopy(t, locale, "taskList.ai.label.unavailable", TASK_LIST_COPY.ai.label.unavailable);
  }
}

function recoveryCopilotHeadline(
  t: (key: string) => string,
  locale: AppLocale,
  status: AIAssistEnvelope["status"],
): string {
  switch (status) {
    case "ok":
      return resolvePageCopy(t, locale, "taskList.ai.headline.ok", TASK_LIST_COPY.ai.headline.ok);
    case "disabled":
      return resolvePageCopy(t, locale, "taskList.ai.headline.disabled", TASK_LIST_COPY.ai.headline.disabled);
    case "error":
      return resolvePageCopy(t, locale, "taskList.ai.headline.error", TASK_LIST_COPY.ai.headline.error);
    case "skipped":
      return resolvePageCopy(t, locale, "taskList.ai.headline.skipped", TASK_LIST_COPY.ai.headline.skipped);
    case "unavailable":
      return resolvePageCopy(t, locale, "taskList.ai.headline.unavailable", TASK_LIST_COPY.ai.headline.unavailable);
  }
}

function recoveryCopilotSummary(
  t: (key: string) => string,
  locale: AppLocale,
  status: AIAssistEnvelope["status"],
): string {
  switch (status) {
    case "ok":
      return resolvePageCopy(t, locale, "taskList.ai.summary.ok", TASK_LIST_COPY.ai.summary.ok);
    case "disabled":
      return resolvePageCopy(t, locale, "taskList.ai.summary.disabled", TASK_LIST_COPY.ai.summary.disabled);
    case "error":
      return resolvePageCopy(t, locale, "taskList.ai.summary.error", TASK_LIST_COPY.ai.summary.error);
    case "skipped":
      return resolvePageCopy(t, locale, "taskList.ai.summary.skipped", TASK_LIST_COPY.ai.summary.skipped);
    case "unavailable":
      return resolvePageCopy(t, locale, "taskList.ai.summary.unavailable", TASK_LIST_COPY.ai.summary.unavailable);
  }
}

function RecoveryInboxSection() {
  const { locale, t } = useI18n();
  const query = useRecoveryInbox();
  const runTaskMutation = useRunWatchTask();
  const runGroupMutation = useRunWatchGroup();
  const formatCount = (value: number) => formatNumber(locale, value, "0");
  const taskListText = (
    key: string,
    fallback: DraftMessage,
    values?: Record<string, string | number>,
  ) => resolvePageCopy(t, locale, key, fallback, values);

  return (
    <div class="rounded-[1.75rem] border border-base-300 bg-base-100/95 p-5 shadow-card">
      <div class="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <p class="text-xs font-semibold uppercase tracking-[0.2em] text-ember">
            {t("taskList.recovery.eyebrow")}
          </p>
          <h2 class="mt-2 text-2xl font-semibold text-ink">
            {t("taskList.recovery.title")}
          </h2>
          <p class="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            {t("taskList.recovery.summary")}
          </p>
        </div>
        {query.data ? (
          <div class="flex flex-wrap gap-2 text-xs">
            <span class="badge badge-outline">
              {taskListText("taskList.recovery.itemsBadge", TASK_LIST_COPY.recovery.itemsBadge, {
                count: formatCount(query.data.tasks.length + query.data.groups.length),
              })}
            </span>
            <span class="badge badge-outline">
              {taskListText("taskList.recovery.tasksBadge", TASK_LIST_COPY.recovery.tasksBadge, {
                count: formatCount(query.data.tasks.length),
              })}
            </span>
            <span class="badge badge-outline">
              {taskListText("taskList.recovery.groupsBadge", TASK_LIST_COPY.recovery.groupsBadge, {
                count: formatCount(query.data.groups.length),
              })}
            </span>
          </div>
        ) : null}
      </div>

      {query.isLoading ? (
        <div class="alert alert-info mt-4">{t("taskList.recovery.loading")}</div>
      ) : null}

      {query.isError ? (
        <div class="alert alert-error mt-4">{t("taskList.recovery.error")}</div>
      ) : null}

      {!query.isLoading && !query.isError && query.data ? (
        query.data.tasks.length === 0 && query.data.groups.length === 0 ? (
          <div class="mt-4 rounded-2xl border border-dashed border-base-300 px-5 py-6">
            <h3 class="text-lg font-semibold text-ink">{t("taskList.recovery.emptyTitle")}</h3>
            <p class="mt-2 text-sm leading-6 text-slate-600">
              {t("taskList.recovery.emptySummary")}
            </p>
            <div class="mt-4 flex flex-wrap gap-3">
              <button class="btn btn-primary" onClick={() => navigate("compare")} type="button">{t("taskList.openCompare")}</button>
              <button class="btn btn-outline" onClick={() => navigate("settings")} type="button">{t("taskList.recovery.openNotifications")}</button>
            </div>
          </div>
        ) : (
          <div class="mt-4 grid gap-4 xl:grid-cols-2">
            <div class="space-y-3">
              <div class="flex items-center justify-between">
                <h3 class="text-lg font-semibold text-ink">{t("taskList.recovery.taskItemsTitle")}</h3>
                <span class="badge badge-outline">{formatCount(query.data.tasks.length)}</span>
              </div>
              {query.data.tasks.length ? (
                query.data.tasks.map((task) => (
                  <article
                    class="rounded-2xl border border-base-300 bg-base-100/80 p-4"
                    key={task.id}
                  >
                    <div class="flex items-start justify-between gap-3">
                      <div>
                        <div class="flex flex-wrap gap-2 text-xs">
                          <span class="badge badge-outline">
                            {taskListText("taskList.recovery.taskBadge", TASK_LIST_COPY.recovery.taskBadge)}
                          </span>
                          <span class={`badge ${statusTone[task.status] ?? "badge-neutral"}`}>
                            {taskListText(
                              `taskList.status.${task.status}`,
                              TASK_LIST_COPY.status[task.status as keyof typeof TASK_LIST_COPY.status] ?? {
                                en: task.status,
                              },
                            )}
                          </span>
                        </div>
                        <h4 class="mt-2 text-lg font-semibold text-ink">{task.title}</h4>
                        <p class="mt-1 break-all text-xs text-slate-500">
                          {task.storeKey} · {task.normalizedUrl || taskListText("taskList.recovery.noNormalizedUrl", TASK_LIST_COPY.recovery.noNormalizedUrl)}
                        </p>
                      </div>
                      <span class={`badge ${healthTone[task.healthStatus]}`}>
                        {healthCopy(t, locale, task.healthStatus)}
                      </span>
                    </div>

                    <div class="mt-3 flex flex-wrap gap-2 text-xs">
                      {task.manualInterventionRequired ? (
                        <span class="badge badge-error">
                          {taskListText("taskList.recovery.operatorAttention", TASK_LIST_COPY.recovery.operatorAttention)}
                        </span>
                      ) : null}
                      <span class="badge badge-outline">
                        {taskListText("taskList.recovery.failures", TASK_LIST_COPY.recovery.failures, {
                          count: formatCount(task.consecutiveFailures),
                          plural: task.consecutiveFailures === 1 ? "" : "s",
                        })}
                      </span>
                      {task.lastFailureKind ? (
                        <span class="badge badge-outline">{task.lastFailureKind}</span>
                      ) : null}
                    </div>

                    <p class="mt-3 text-sm leading-6 text-slate-600">{task.reason}</p>
                    <p class="mt-2 text-xs leading-5 text-slate-500">{task.recommendedAction}</p>

                    <div class="mt-3 space-y-1 text-xs text-slate-500">
                      {task.backoffUntil ? (
                        <div>
                          {taskListText("taskList.recovery.backoffUntil", TASK_LIST_COPY.recovery.backoffUntil, {
                            value: formatDateTime(locale, task.backoffUntil),
                          })}
                        </div>
                      ) : null}
                      <div>
                        {taskListText("taskList.recovery.nextRun", TASK_LIST_COPY.recovery.nextRun, {
                          value: formatDateTime(locale, task.nextRunAt),
                        })}
                      </div>
                      <div>
                        {taskListText("taskList.recovery.lastRun", TASK_LIST_COPY.recovery.lastRun, {
                          value: formatDateTime(locale, task.lastRunAt),
                        })}
                      </div>
                    </div>

                    <div class="mt-4 flex flex-wrap gap-3">
                      <button
                        class="btn btn-sm btn-outline"
                        onClick={() => navigate("watch-detail", task.id)}
                        type="button"
                      >
                        {t("shell.nav.watchDetail")}
                      </button>
                      <button
                        class="btn btn-sm btn-primary"
                        disabled={runTaskMutation.isPending}
                        onClick={() => runTaskMutation.mutate(task.id)}
                        type="button"
                      >
                        {runTaskMutation.isPending ? t("taskDetail.running") : t("taskDetail.runNow")}
                      </button>
                    </div>
                  </article>
                ))
              ) : (
                <div class="rounded-2xl border border-dashed border-base-300 px-5 py-6 text-sm text-slate-600">
                  {taskListText("taskList.recovery.noSingleTasks", TASK_LIST_COPY.recovery.noSingleTasks)}
                </div>
              )}
            </div>

            <div class="space-y-3">
              <div class="flex items-center justify-between">
                <h3 class="text-lg font-semibold text-ink">{t("taskList.recovery.groupItemsTitle")}</h3>
                <span class="badge badge-outline">{formatCount(query.data.groups.length)}</span>
              </div>
              {query.data.groups.length ? (
                query.data.groups.map((group) => (
                  <article
                    class="rounded-2xl border border-base-300 bg-base-100/80 p-4"
                    key={group.id}
                  >
                    <div class="flex items-start justify-between gap-3">
                      <div>
                        <div class="flex flex-wrap gap-2 text-xs">
                          <span class="badge badge-outline">
                            {taskListText("taskList.recovery.groupBadge", TASK_LIST_COPY.recovery.groupBadge)}
                          </span>
                          <span class={`badge ${statusTone[group.status] ?? "badge-neutral"}`}>
                            {taskListText(
                              `taskList.status.${group.status}`,
                              TASK_LIST_COPY.status[group.status as keyof typeof TASK_LIST_COPY.status] ?? {
                                en: group.status,
                              },
                            )}
                          </span>
                        </div>
                        <h4 class="mt-2 text-lg font-semibold text-ink">{group.title}</h4>
                        <p class="mt-1 text-xs text-slate-500">
                          {taskListText("taskList.recovery.groupCandidates", TASK_LIST_COPY.recovery.groupCandidates, {
                            zipCode: group.zipCode,
                            count: formatCount(group.memberCount),
                            plural: group.memberCount === 1 ? "" : "s",
                          })}
                        </p>
                      </div>
                      <span class={`badge ${healthTone[group.healthStatus]}`}>
                        {healthCopy(t, locale, group.healthStatus)}
                      </span>
                    </div>

                    <div class="mt-3 flex flex-wrap gap-2 text-xs">
                      {group.manualInterventionRequired ? (
                        <span class="badge badge-error">
                          {taskListText("taskList.recovery.operatorAttention", TASK_LIST_COPY.recovery.operatorAttention)}
                        </span>
                      ) : null}
                      <span class="badge badge-outline">
                        {taskListText("taskList.recovery.failures", TASK_LIST_COPY.recovery.failures, {
                          count: formatCount(group.consecutiveFailures),
                          plural: group.consecutiveFailures === 1 ? "" : "s",
                        })}
                      </span>
                      {group.lastFailureKind ? (
                        <span class="badge badge-outline">{group.lastFailureKind}</span>
                      ) : null}
                    </div>

                    <p class="mt-3 text-sm leading-6 text-slate-600">{group.reason}</p>
                    <p class="mt-2 text-xs leading-5 text-slate-500">{group.recommendedAction}</p>

                    <div class="mt-3 rounded-2xl border border-dashed border-base-300 bg-base-200/30 px-4 py-4">
                      <div class="flex items-start justify-between gap-3">
                        <div>
                          <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                            {taskListText("taskList.ai.panelTitle", TASK_LIST_COPY.ai.panelTitle)}
                          </div>
                          <div class="mt-2 font-semibold text-ink">
                            {group.aiCopilot.title ?? recoveryCopilotHeadline(t, locale, group.aiCopilot.status)}
                          </div>
                        </div>
                        <span class={`badge ${aiAssistBadgeClass(group.aiCopilot.status)}`}>
                          {aiAssistLabel(t, locale, group.aiCopilot.status)}
                        </span>
                      </div>
                      <p class="mt-2 text-sm leading-6 text-slate-600">
                        {group.aiCopilot.summary ?? recoveryCopilotSummary(t, locale, group.aiCopilot.status)}
                      </p>
                      {group.aiCopilot.detail ? (
                        <p class="mt-2 text-sm leading-6 text-slate-500">{group.aiCopilot.detail}</p>
                      ) : null}
                      {group.aiCopilot.bullets.length ? (
                        <ul class="mt-3 space-y-2 text-sm leading-6 text-slate-600">
                          {group.aiCopilot.bullets.map((bullet) => (
                            <li key={bullet}>- {bullet}</li>
                          ))}
                        </ul>
                      ) : null}
                      <p class="mt-3 text-xs leading-5 text-slate-500">
                        {taskListText("taskList.ai.panelNote", TASK_LIST_COPY.ai.panelNote)}
                      </p>
                    </div>

                    <div class="mt-3 space-y-1 text-xs text-slate-500">
                      <div>
                        {taskListText("taskList.board.currentWinner", TASK_LIST_COPY.board.currentWinner, {
                          value: group.winnerTitle ?? t("groupDetail.noRuns"),
                        })}
                      </div>
                      {group.backoffUntil ? (
                        <div>
                          {taskListText("taskList.recovery.backoffUntil", TASK_LIST_COPY.recovery.backoffUntil, {
                            value: formatDateTime(locale, group.backoffUntil),
                          })}
                        </div>
                      ) : null}
                      <div>
                        {taskListText("taskList.recovery.nextRun", TASK_LIST_COPY.recovery.nextRun, {
                          value: formatDateTime(locale, group.nextRunAt),
                        })}
                      </div>
                      <div>
                        {taskListText("taskList.recovery.lastRun", TASK_LIST_COPY.recovery.lastRun, {
                          value: formatDateTime(locale, group.lastRunAt),
                        })}
                      </div>
                    </div>

                    <div class="mt-4 flex flex-wrap gap-3">
                      <button
                        class="btn btn-sm btn-outline"
                        onClick={() => navigate("watch-group-detail", group.id)}
                        type="button"
                      >
                        {t("shell.nav.watchGroupDetail")}
                      </button>
                      <button
                        class="btn btn-sm btn-primary"
                        disabled={runGroupMutation.isPending}
                        onClick={() => runGroupMutation.mutate(group.id)}
                        type="button"
                      >
                        {runGroupMutation.isPending ? t("groupDetail.running") : t("groupDetail.runNow")}
                      </button>
                    </div>
                  </article>
                ))
              ) : (
                <div class="rounded-2xl border border-dashed border-base-300 px-5 py-6 text-sm text-slate-600">
                  {taskListText("taskList.recovery.noGroupItems", TASK_LIST_COPY.recovery.noGroupItems)}
                </div>
              )}
            </div>
          </div>
        )
      ) : null}
    </div>
  );
}

export function TaskListPage() {
  const { locale, t } = useI18n();
  const taskQuery = useWatchTasks();
  const groupQuery = useWatchGroups();
  const formatCount = (value: number) => formatNumber(locale, value, "0");
  const taskListText = (
    key: string,
    fallback: DraftMessage,
    values?: Record<string, string | number>,
  ) => resolvePageCopy(t, locale, key, fallback, values);

  if (taskQuery.isLoading || groupQuery.isLoading) {
    return (
      <section class="space-y-4">
        <RecoveryInboxSection />
        <div class="alert alert-info">{t("taskList.loading")}</div>
      </section>
    );
  }

  if (taskQuery.isError || !taskQuery.data || groupQuery.isError || !groupQuery.data) {
    return (
      <section class="space-y-4">
        <RecoveryInboxSection />
        <div class="alert alert-error">{t("taskList.error")}</div>
      </section>
    );
  }

  const tasks = taskQuery.data;
  const groups = groupQuery.data;
  const activeTasks = tasks.filter((task) => task.status === "active").length;
  const attentionTasks = tasks.filter((task) => task.manualInterventionRequired).length;
  const compareAwareGroups = groups.filter((group) => group.memberCount >= 2).length;
  const liveWinnerGroups = groups.filter((group) => Boolean(group.winnerTitle)).length;

  const boardContent =
    tasks.length === 0 && groups.length === 0 ? (
      <section class="dashboard-dual-grid">
        <div class="surface-panel surface-panel-block surface-panel-primary surface-enter text-center">
          <h2 class="text-2xl font-semibold text-ink">{t("taskList.emptyTitle")}</h2>
          <p class="supporting-copy">
            {t("taskList.emptySummary")}
          </p>
          <div class="dashboard-action-row mt-6 items-center justify-center">
            <button class="btn btn-primary" onClick={() => navigate("compare")} type="button">{t("taskList.openCompare")}</button>
            <button class="btn btn-outline" onClick={() => navigate("watch-new")} type="button">{t("taskList.createSingleTask")}</button>
          </div>
        </div>

        <aside class="surface-panel surface-section-tight surface-enter">
          <p class="eyebrow-label">{t("taskList.newShapeEyebrow")}</p>
          <h3 class="mt-2 text-xl font-semibold text-ink">{t("taskList.newShapeTitle")}</h3>
          <ul class="mt-4 space-y-3 text-sm leading-6 text-slate-600">
            <li>{t("taskList.newShapeBullet1")}</li>
            <li>{t("taskList.newShapeBullet2")}</li>
            <li>{t("taskList.newShapeBullet3")}</li>
          </ul>
        </aside>
      </section>
    ) : (
      <section class="page-stack">
        <div class="surface-panel surface-panel-block surface-panel-primary surface-enter">
          <p class="eyebrow-label">{t("taskList.controlNotesEyebrow")}</p>
          <h2 class="mt-2 text-2xl font-semibold text-ink">{t("taskList.singleWatchTitle")}</h2>
          <p class="supporting-copy">
            {taskListText("taskList.dashboard.operatorDeskSummary", TASK_LIST_COPY.dashboard.operatorDeskSummary)}
          </p>

          <div class="dashboard-kpi-grid mt-6">
            <div class="dashboard-kpi-card">
              <div class="workflow-label">
                {taskListText("taskList.dashboard.activeTasks", TASK_LIST_COPY.dashboard.activeTasks)}
              </div>
              <div class="dashboard-kpi-value">{formatCount(activeTasks)}</div>
              <p class="dashboard-kpi-note">
                {taskListText("taskList.dashboard.activeTasksNote", TASK_LIST_COPY.dashboard.activeTasksNote)}
              </p>
            </div>
            <div class="dashboard-kpi-card">
              <div class="workflow-label">
                {taskListText("taskList.dashboard.attentionNow", TASK_LIST_COPY.dashboard.attentionNow)}
              </div>
              <div class="dashboard-kpi-value">{formatCount(attentionTasks)}</div>
              <p class="dashboard-kpi-note">
                {taskListText("taskList.dashboard.attentionNowNote", TASK_LIST_COPY.dashboard.attentionNowNote)}
              </p>
            </div>
            <div class="dashboard-kpi-card">
              <div class="workflow-label">
                {taskListText("taskList.dashboard.compareGroups", TASK_LIST_COPY.dashboard.compareGroups)}
              </div>
              <div class="dashboard-kpi-value">{formatCount(compareAwareGroups)}</div>
              <p class="dashboard-kpi-note">
                {taskListText("taskList.dashboard.compareGroupsNote", TASK_LIST_COPY.dashboard.compareGroupsNote)}
              </p>
            </div>
            <div class="dashboard-kpi-card">
              <div class="workflow-label">
                {taskListText("taskList.dashboard.liveWinners", TASK_LIST_COPY.dashboard.liveWinners)}
              </div>
              <div class="dashboard-kpi-value">{formatCount(liveWinnerGroups)}</div>
              <p class="dashboard-kpi-note">
                {taskListText("taskList.dashboard.liveWinnersNote", TASK_LIST_COPY.dashboard.liveWinnersNote)}
              </p>
            </div>
          </div>
        </div>

        <div class="dashboard-dual-grid">
          <div class="dashboard-ledger surface-enter">
            <div class="dashboard-ledger-head">
              <div>
                <div class="eyebrow-label">{t("taskList.singleWatchTitle")}</div>
                <h3 class="mt-2 text-xl font-semibold text-ink">{t("taskList.singleWatchTitle")}</h3>
                <p class="supporting-copy">{t("taskList.singleWatchSummary")}</p>
              </div>
              <button class="btn btn-primary" onClick={() => navigate("watch-new")} type="button">{t("taskList.newTask")}</button>
            </div>

            <div class="dashboard-ledger-table mt-4 overflow-x-auto">
              <table class="table">
                <thead>
                  <tr>
                    <th>{t("shell.nav.watchDetail")}</th>
                    <th>{t("taskDetail.taskHealthTitle")}</th>
                    <th>{t("groupDetail.latestRun")}</th>
                    <th>{t("chart.listedPrice")}</th>
                    <th>{t("chart.effectivePrice")}</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {tasks.map((task) => (
                    <tr key={task.id}>
                      <td>
                        <div class="entity-section-title">{task.title}</div>
                        <div class="entity-meta-line">{task.normalizedUrl}</div>
                        <div class="entity-chip-row">
                          <span class={`badge ${statusTone[task.status] ?? "badge-neutral"}`}>
                            {taskListText(
                              `taskList.status.${task.status}`,
                              TASK_LIST_COPY.status[task.status as keyof typeof TASK_LIST_COPY.status] ?? {
                                en: task.status,
                              },
                            )}
                          </span>
                          {task.manualInterventionRequired ? (
                            <span class="badge badge-error">
                              {taskListText("taskList.board.needsAttention", TASK_LIST_COPY.board.needsAttention)}
                            </span>
                          ) : null}
                        </div>
                      </td>
                      <td>
                        <span class={`badge ${healthTone[task.healthStatus]}`}>
                          {healthCopy(t, locale, task.healthStatus)}
                        </span>
                        {task.backoffUntil ? (
                          <div class="entity-meta-line">
                            {taskListText("taskList.board.backoffUntil", TASK_LIST_COPY.board.backoffUntil, {
                              value: formatDateTime(locale, task.backoffUntil),
                            })}
                          </div>
                        ) : null}
                      </td>
                      <td class="text-sm text-slate-600">{formatDateTime(locale, task.nextRunAt)}</td>
                      <td>{formatCurrency(locale, task.lastListedPrice)}</td>
                      <td>{formatCurrency(locale, task.lastEffectivePrice)}</td>
                      <td>
                        <button
                          class="btn btn-sm btn-outline"
                          onClick={() => navigate("watch-detail", task.id)}
                          type="button"
                        >
                          {t("shell.nav.watchDetail")}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <aside class="dashboard-mini-stack surface-enter">
            <div class="surface-panel surface-section-tight">
              <p class="eyebrow-label">{t("taskList.controlNotesEyebrow")}</p>
              <h3 class="mt-2 text-xl font-semibold text-ink">{t("taskList.controlNotesTitle")}</h3>
              <ul class="mt-4 space-y-3 text-sm leading-6 text-slate-600">
                <li>{t("taskList.controlNotesBullet1")}</li>
                <li>{t("taskList.controlNotesBullet2")}</li>
                <li>{t("taskList.controlNotesBullet3")}</li>
                <li>{t("taskList.controlNotesBullet4")}</li>
              </ul>
            </div>

            <div class="dashboard-mini-card">
              <div class="workflow-label">
                {taskListText("taskList.dashboard.bestNextMove", TASK_LIST_COPY.dashboard.bestNextMove)}
              </div>
              <div class="dashboard-mini-title">
                {taskListText("taskList.dashboard.bestNextMoveTitle", TASK_LIST_COPY.dashboard.bestNextMoveTitle)}
              </div>
              <p class="dashboard-mini-copy">
                {taskListText("taskList.dashboard.bestNextMoveSummary", TASK_LIST_COPY.dashboard.bestNextMoveSummary)}
              </p>
            </div>

            <div class="dashboard-mini-card">
              <div class="workflow-label">
                {taskListText("taskList.dashboard.proofDiscipline", TASK_LIST_COPY.dashboard.proofDiscipline)}
              </div>
              <div class="dashboard-mini-title">
                {taskListText("taskList.dashboard.proofDisciplineTitle", TASK_LIST_COPY.dashboard.proofDisciplineTitle)}
              </div>
              <p class="dashboard-mini-copy">
                {taskListText("taskList.dashboard.proofDisciplineSummary", TASK_LIST_COPY.dashboard.proofDisciplineSummary)}
              </p>
            </div>
          </aside>
        </div>

        <div class="dashboard-dual-grid">
          <div class="surface-panel surface-section-tight surface-enter">
            <div class="flex items-center justify-between gap-4">
              <div>
                <p class="eyebrow-label">{t("taskList.groupsTitle")}</p>
                <h3 class="mt-2 text-xl font-semibold text-ink">{t("taskList.groupsTitle")}</h3>
                <p class="supporting-copy">{t("taskList.groupsSummary")}</p>
              </div>
              <button class="btn btn-outline" onClick={() => navigate("compare")} type="button">{t("taskList.buildFromCompare")}</button>
            </div>

            <div class="dashboard-split-grid mt-5">
              {groups.length ? (
                groups.map((group) => (
                  <article
                    class="dashboard-card dashboard-card-strong"
                    key={group.id}
                  >
                    <div class="flex items-start justify-between gap-3">
                      <div>
                        <h3 class="entity-section-title">{group.title}</h3>
                        <p class="entity-meta-line">
                          {taskListText("taskList.board.memberCandidates", TASK_LIST_COPY.board.memberCandidates, {
                            count: formatCount(group.memberCount),
                          })}
                        </p>
                      </div>
                      <span class={`badge ${healthTone[group.healthStatus]}`}>
                        {healthCopy(t, locale, group.healthStatus)}
                      </span>
                    </div>

                    <div class="entity-chip-row">
                      <span class={`badge ${statusTone[group.status] ?? "badge-neutral"}`}>
                        {taskListText(
                          `taskList.status.${group.status}`,
                          TASK_LIST_COPY.status[group.status as keyof typeof TASK_LIST_COPY.status] ?? {
                            en: group.status,
                          },
                        )}
                      </span>
                      <span class="badge badge-outline">
                        {taskListText("taskList.board.zipBadge", TASK_LIST_COPY.board.zipBadge, {
                          value: group.zipCode,
                        })}
                      </span>
                      {group.manualInterventionRequired ? (
                        <span class="badge badge-error">
                          {taskListText("taskList.board.needsAttention", TASK_LIST_COPY.board.needsAttention)}
                        </span>
                      ) : null}
                    </div>

                    <div class="metric-grid mt-4 sm:grid-cols-2">
                      <div class="metric-card">
                        <div class="workflow-label">{t("groupDetail.winnerEffective")}</div>
                        <div class="panel-title">{group.winnerTitle ?? t("groupDetail.noRuns")}</div>
                        <p class="mt-2 text-base font-semibold text-moss">
                          {formatCurrency(locale, group.winnerEffectivePrice)}
                        </p>
                      </div>
                      <div class="metric-card">
                        <div class="workflow-label">{t("groupDetail.spread")} / {t("groupDetail.latestRun")}</div>
                        <div class="panel-title">{formatCurrency(locale, group.priceSpread)}</div>
                        <p class="dashboard-mini-copy">{formatDateTime(locale, group.nextRunAt)}</p>
                      </div>
                    </div>

                    {group.backoffUntil ? (
                      <div class="notice-strip mt-4 text-sm leading-6 text-slate-600">
                        {t("groupDetail.riskTitle")} {formatDateTime(locale, group.backoffUntil)}
                      </div>
                    ) : null}

                    <div class="dashboard-action-row mt-4">
                      <button
                        class="btn btn-sm btn-outline"
                        onClick={() => navigate("watch-group-detail", group.id)}
                        type="button"
                      >
                        {t("shell.nav.watchGroupDetail")}
                      </button>
                    </div>
                  </article>
                ))
              ) : (
                <div class="notice-strip md:col-span-2 text-sm text-slate-600">
                  {taskListText("taskList.board.noGroups", TASK_LIST_COPY.board.noGroups)}
                </div>
              )}
            </div>
          </div>

          <div class="surface-enter">
            <RecoveryInboxSection />
          </div>
        </div>
      </section>
    );

  return (
    <section class="page-stack">
      {boardContent}
    </section>
  );
}
