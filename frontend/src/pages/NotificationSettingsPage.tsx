import { useEffect, useState } from "preact/hooks";
import { formatDateTime, formatNumber, interpolate, type AppLocale, useI18n } from "../lib/i18n";
import { navigate } from "../lib/routes";
import {
  useNotificationEvents,
  useNotificationSettings,
  useStoreOnboardingCockpit,
  useStoreBindings,
  useRuntimeReadiness,
  useUpdateNotificationSettings,
  useUpdateStoreBinding,
} from "../lib/hooks";
import type { DeliveryStatus, RuntimeCheckStatus, StoreBindingSetting } from "../types";

type DraftMessage = { en: string };

const LIMITED_SUPPORT_ACTION_KEYS = {
  accept_url_into_compare_preview: "settings.page.limitedSupportActions.acceptUrlIntoComparePreview",
  show_compare_guidance: "settings.page.limitedSupportActions.showCompareGuidance",
  save_compare_evidence: "settings.page.limitedSupportActions.saveCompareEvidence",
  create_watch_task: "settings.page.limitedSupportActions.createWatchTask",
  create_watch_group: "settings.page.limitedSupportActions.createWatchGroup",
  cashback_tracking: "settings.page.limitedSupportActions.cashbackTracking",
  notification_delivery: "settings.page.limitedSupportActions.notificationDelivery",
} as const;

const LIMITED_SUPPORT_ACTION_FALLBACKS = {
  accept_url_into_compare_preview: "accept URL into compare preview",
  show_compare_guidance: "show compare guidance",
  save_compare_evidence: "save compare evidence",
  create_watch_task: "create watch task",
  create_watch_group: "create watch group",
  cashback_tracking: "cashback tracking",
  notification_delivery: "notification delivery",
} as const;

const SETTINGS_COPY = {
  page: {
    notificationsSummary: {
      en: "Set the default recipient lane here, then use the event feed below to confirm what actually left the runtime.",
    },
    whyMcpBoundarySummary: {
      en: "This cockpit is where builder-safe read surfaces and maintainer reality meet. It explains what the runtime can expose safely today without pretending write-side automation is part of the public promise.",
    },
    registryHealthySummary: {
      en: "Registry and cockpit signals line up right now, so the store matrix reads like one truthful control surface instead of two competing ledgers.",
    },
    registryWarningSummary: {
      en: "Some store registry truth still needs review. Treat the cockpit as the lead view, then inspect the linked source refs before you widen store claims.",
    },
    cockpitBridgeSummary: {
      en: "The cockpit keeps capability truth, runtime enablement, and onboarding proof in one place so a store can earn product-path status instead of only looking supported on paper.",
    },
    limitedSupportTitle: { en: "Limited-support compare intake", },
    limitedSupportSummary: {
      en: "Unsupported hosts or unsupported product paths can still stay inside compare review and repo-local evidence, but they must not pretend to be live watch state.",
    },
    limitedSupportAllowedTitle: { en: "Still allowed", },
    limitedSupportBlockedTitle: { en: "Still blocked", },
    limitedSupportSourceRefsTitle: { en: "Limited-support truth refs", },
    compareCapableCardTitle: { en: "Compare-capable stores", },
    compareCapableCardSummary: {
      en: "These are the stores already shaped for compare-first intake instead of only single-link monitoring.",
    },
    cashbackCardTitle: { en: "Cashback-capable stores", },
    cashbackCardSummary: {
      en: "This count shows where effective-price context can join the same operator loop instead of living in a side spreadsheet.",
    },
    disciplineCardTitle: { en: "Execution discipline", },
    disciplineCardSummary: {
      en: "The current rule is still prove the product path first, then widen store exposure. This keeps new store growth from outrunning evidence.",
    },
  },
  readiness: {
    ready: { en: "Ready", },
    actionNeeded: { en: "Action Needed", },
    warning: { en: "Warning", },
    noEvidence: { en: "No Local Evidence Yet", },
  },
  binding: {
    fullLive: { en: "Live on the full official product path", },
    partialLive: { en: "Live on the current partial official path", },
    inProgressLive: { en: "Enabled for onboarding validation, not ready for broad store claims", },
    partialDisabled: { en: "Officially modeled, currently parked until more product-path proof lands", },
    disabledUntilReady: { en: "Disabled until the product path is ready", },
  },
  cockpit: {
    officialStores: { en: "{{count}} official stores", },
    enabled: { en: "{{count}} enabled", },
    disabled: { en: "{{count}} disabled", },
    officialFull: { en: "{{count}} official full", },
    officialPartial: { en: "{{count}} official partial", },
    officialInProgress: { en: "{{count}} official in progress", },
    compareCapable: { en: "{{count}} compare-capable", },
    cashbackCapable: { en: "{{count}} cashback-capable", },
    taskCapable: { en: "{{count}} task-capable", },
    groupCapable: { en: "{{count}} group-capable", },
    recoveryCapable: { en: "{{count}} recovery-capable", },
    liveForCompare: { en: "{{count}} live for compare", },
    liveNowParked: { en: "{{enabled}} live now, {{disabled}} intentionally parked", },
    disableFirstProveSecond: { en: "Disable first, prove second", },
    compareCapableStores: { en: "{{count}} stores", },
    cashbackCapableStores: { en: "{{count}} stores", },
    table: {
      store: { en: "Store", },
      tier: { en: "Official tier", },
      binding: { en: "Binding", },
      compare: { en: "Compare" },
      task: { en: "Task", },
      group: { en: "Group", },
      recovery: { en: "Recovery", },
      cashback: { en: "Cashback", },
      region: { en: "Region", },
      discovery: { en: "Discovery", },
      parse: { en: "Parse", },
      contractAttention: { en: "contract attention", },
      contractReady: { en: "contract ready", },
      enabled: { en: "Enabled", },
      disabled: { en: "Disabled", },
      supported: { en: "Supported", },
      notYet: { en: "Not yet", },
      none: { en: "None", },
      officialFull: { en: "Official full", },
      officialPartial: { en: "Official partial", },
      officialInProgress: { en: "Official in progress", },
      regionAware: { en: "Region-aware", },
      regionStatic: { en: "Region-static", },
      toggleBinding: { en: "Toggle {{storeKey}} runtime binding", },
    },
    updateError: { en: "Failed to update store runtime switch.", },
    onboardingChecklist: { en: "Onboarding checklist", },
    verificationCommands: { en: "Verification commands", },
    contractTests: { en: "Contract tests", },
    sourceRefs: { en: "Source-of-truth refs", },
    verificationCommandsDetail: {
      en: "These are the prove-it commands from the onboarding contract. In everyday terms: this is the exam sheet a new store has to pass before it earns shelf space.",
    },
    sourceRefsDetail: {
      en: "No second store truth is hidden in this page. These refs are the files and endpoint that define what the matrix means.",
    },
  },
  deliveryEvents: {
    taskRef: { en: "task {{value}}", },
    groupRef: { en: "group {{value}}", },
    messageRef: { en: "message {{value}}", },
    status: {
      delivered: { en: "Delivered", },
      sent: { en: "Sent", },
      bounced: { en: "Bounced", },
      failed: { en: "Failed", },
      queued: { en: "Queued", },
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
  const template = translated === key ? fallback.en : translated;
  return values ? interpolate(template, values) : template;
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

function deliveryStatusCopy(t: (key: string) => string, locale: AppLocale, value: DeliveryStatus): string {
  switch (value) {
    case "delivered":
      return resolvePageCopy(t, locale, "settings.deliveryEvents.status.delivered", SETTINGS_COPY.deliveryEvents.status.delivered);
    case "sent":
      return resolvePageCopy(t, locale, "settings.deliveryEvents.status.sent", SETTINGS_COPY.deliveryEvents.status.sent);
    case "bounced":
      return resolvePageCopy(t, locale, "settings.deliveryEvents.status.bounced", SETTINGS_COPY.deliveryEvents.status.bounced);
    case "failed":
      return resolvePageCopy(t, locale, "settings.deliveryEvents.status.failed", SETTINGS_COPY.deliveryEvents.status.failed);
    case "queued":
      return resolvePageCopy(t, locale, "settings.deliveryEvents.status.queued", SETTINGS_COPY.deliveryEvents.status.queued);
  }
}

function readinessTone(value: RuntimeCheckStatus): string {
  switch (value) {
    case "ready":
      return "badge-success";
    case "action_needed":
      return "badge-error";
    case "warning":
      return "badge-warning";
    case "no_evidence":
      return "badge-outline";
  }
}

function readinessCopy(t: (key: string) => string, locale: AppLocale, value: RuntimeCheckStatus): string {
  switch (value) {
    case "ready":
      return resolvePageCopy(t, locale, "settings.runtime.badge.ready", SETTINGS_COPY.readiness.ready);
    case "action_needed":
      return resolvePageCopy(t, locale, "settings.runtime.badge.actionNeeded", SETTINGS_COPY.readiness.actionNeeded);
    case "warning":
      return resolvePageCopy(t, locale, "settings.runtime.badge.warning", SETTINGS_COPY.readiness.warning);
    case "no_evidence":
      return resolvePageCopy(t, locale, "settings.runtime.badge.noEvidence", SETTINGS_COPY.readiness.noEvidence);
  }
}

function bindingStatusCopy(binding: StoreBindingSetting, t: (key: string) => string, locale: AppLocale): string {
  if (binding.enabled && binding.supportTier === "official_full") {
    return resolvePageCopy(t, locale, "settings.cockpit.binding.fullLive", SETTINGS_COPY.binding.fullLive);
  }
  if (binding.enabled && binding.supportTier === "official_partial") {
    return resolvePageCopy(t, locale, "settings.cockpit.binding.partialLive", SETTINGS_COPY.binding.partialLive);
  }
  if (binding.enabled) {
    return resolvePageCopy(t, locale, "settings.cockpit.binding.inProgressLive", SETTINGS_COPY.binding.inProgressLive);
  }
  if (binding.supportsCompareIntake || binding.supportTier !== "official_in_progress") {
    return resolvePageCopy(t, locale, "settings.cockpit.binding.partialDisabled", SETTINGS_COPY.binding.partialDisabled);
  }
  return resolvePageCopy(t, locale, "settings.cockpit.binding.disabledUntilReady", SETTINGS_COPY.binding.disabledUntilReady);
}

function limitedSupportActionCopy(
  t: (key: string) => string,
  locale: AppLocale,
  action: string,
): string {
  const key = LIMITED_SUPPORT_ACTION_KEYS[action as keyof typeof LIMITED_SUPPORT_ACTION_KEYS];
  const fallback =
    LIMITED_SUPPORT_ACTION_FALLBACKS[action as keyof typeof LIMITED_SUPPORT_ACTION_FALLBACKS] ?? action;
  if (!key) {
    return fallback;
  }
  return resolvePageCopy(t, locale, key, { en: fallback });
}

function supportTierBadgeClass(tier: string): string {
  switch (tier) {
    case "official_full":
      return "badge-success";
    case "official_partial":
      return "badge-warning";
    default:
      return "badge-outline";
  }
}

function supportTierCopy(binding: StoreBindingSetting, t: (key: string) => string, locale: AppLocale): string {
  switch (binding.supportTier) {
    case "official_full":
      return resolvePageCopy(t, locale, "settings.cockpit.table.officialFull", SETTINGS_COPY.cockpit.table.officialFull);
    case "official_partial":
      return resolvePageCopy(t, locale, "settings.cockpit.table.officialPartial", SETTINGS_COPY.cockpit.table.officialPartial);
    default:
      return resolvePageCopy(t, locale, "settings.cockpit.table.officialInProgress", SETTINGS_COPY.cockpit.table.officialInProgress);
  }
}

function RuntimeReadinessSection() {
  const { locale, t } = useI18n();
  const query = useRuntimeReadiness();
  const formatCount = (value: number) => formatNumber(locale, value, "0");

  const readyCount = query.data?.checks.filter((item) => item.status === "ready").length ?? 0;
  const actionCount =
    query.data?.checks.filter((item) => item.status === "action_needed").length ?? 0;
  const cautionCount =
    query.data?.checks.filter((item) => item.status === "warning" || item.status === "no_evidence")
      .length ?? 0;

  return (
    <div class="rounded-[1.75rem] border border-base-300 bg-base-100/95 p-6 shadow-card">
      <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p class="text-xs font-semibold uppercase tracking-[0.2em] text-ember">
            {t("settings.runtime.eyebrow")}
          </p>
          <div class="mt-2 flex flex-wrap items-center gap-3">
            <h2 class="text-2xl font-semibold text-ink">{t("settings.runtime.title")}</h2>
            {query.data ? (
              <span class={`badge ${readinessTone(query.data.overallStatus)}`}>
                {readinessCopy(t, locale, query.data.overallStatus)}
              </span>
            ) : null}
          </div>
          <p class="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            {t("settings.runtime.summary")}
          </p>
          <p class="mt-2 max-w-3xl text-sm leading-6 text-slate-500">
            {t("settings.page.notificationsSummary")}
          </p>
        </div>
        {query.data ? (
          <div class="flex flex-wrap gap-2 text-xs">
            <span class="badge badge-outline">{formatCount(readyCount)} {t("settings.runtime.readyCount")}</span>
            <span class="badge badge-outline">{formatCount(actionCount)} {t("settings.runtime.actionNeededCount")}</span>
            <span class="badge badge-outline">{formatCount(cautionCount)} {t("settings.runtime.warningCount")}</span>
          </div>
        ) : null}
      </div>

      {query.isLoading ? (
        <div class="alert alert-info mt-4">{t("settings.runtime.loading")}</div>
      ) : null}

      {query.isError ? (
        <div class="alert alert-error mt-4">{t("settings.runtime.error")}</div>
      ) : null}

      {!query.isLoading && !query.isError && query.data ? (
        query.data.checks.length ? (
          <>
            <div class="mt-4 rounded-2xl bg-base-200/50 px-4 py-4 text-sm leading-6 text-slate-600">
              <div class="font-semibold text-ink">{query.data.headline}</div>
              <div class="mt-1 text-xs text-slate-500">
                {t("settings.runtime.lastUpdatedPrefix")} {formatDateTime(locale, query.data.generatedAt, t("settings.runtime.noTimestamp"))}
              </div>
            </div>

            <div class="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {query.data.checks.map((check) => (
                <article class="rounded-2xl border border-base-300 bg-base-100/80 p-4" key={check.key}>
                  <div class="flex items-start justify-between gap-3">
                    <div>
                      <p class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                        {check.key}
                      </p>
                      <h3 class="mt-2 text-lg font-semibold text-ink">{check.label}</h3>
                    </div>
                    <span class={`badge ${readinessTone(check.status)}`}>
                      {readinessCopy(t, locale, check.status)}
                    </span>
                  </div>
                  <p class="mt-3 text-sm leading-6 text-slate-600">{check.summary}</p>
                  {check.detail && check.detail !== check.summary ? (
                    <p class="mt-2 text-xs leading-5 text-slate-500">{check.detail}</p>
                  ) : null}
                </article>
              ))}
            </div>

            <div class="mt-4 flex flex-wrap gap-3">
              <button class="btn btn-outline" onClick={() => navigate("settings")} type="button">
                {t("settings.runtime.stayInSettings")}
              </button>
              <button class="btn btn-outline" onClick={() => navigate("watch-list")} type="button">
                {t("settings.runtime.openTaskBoard")}
              </button>
              <button class="btn btn-primary" onClick={() => navigate("compare")} type="button">
                {t("settings.runtime.openCompare")}
              </button>
            </div>
          </>
        ) : (
          <div class="mt-4 rounded-2xl border border-dashed border-base-300 px-5 py-6">
            <h3 class="text-lg font-semibold text-ink">{t("settings.runtime.emptyTitle")}</h3>
            <p class="mt-2 text-sm leading-6 text-slate-600">
              {t("settings.runtime.emptySummary")}
            </p>
            <div class="mt-4 flex flex-wrap gap-3">
              <button class="btn btn-outline" onClick={() => navigate("settings")} type="button">
                {t("settings.runtime.stayInSettings")}
              </button>
              <button class="btn btn-primary" onClick={() => navigate("compare")} type="button">
                {t("settings.runtime.openCompare")}
              </button>
            </div>
          </div>
        )
      ) : null}
    </div>
  );
}

export function NotificationSettingsPage() {
  const { locale, t } = useI18n();
  const query = useNotificationSettings();
  const eventsQuery = useNotificationEvents();
  const cockpitQuery = useStoreOnboardingCockpit();
  const storeBindingsQuery = useStoreBindings();
  const mutation = useUpdateNotificationSettings();
  const storeMutation = useUpdateStoreBinding();
  const [localState, setLocalState] = useState({
    defaultRecipientEmail: "",
    cooldownMinutes: 240,
    notificationsEnabled: true,
  });

  useEffect(() => {
    if (query.data) {
      setLocalState(query.data);
    }
  }, [query.data]);

  if (query.isLoading || eventsQuery.isLoading || cockpitQuery.isLoading || storeBindingsQuery.isLoading) {
    return (
      <section class="space-y-4">
        <RuntimeReadinessSection />
        <div class="alert alert-info">{t("settings.page.loading")}</div>
      </section>
    );
  }

  if (query.isError || !query.data || eventsQuery.isError || !eventsQuery.data || cockpitQuery.isError || !cockpitQuery.data || storeBindingsQuery.isError || !storeBindingsQuery.data) {
    return (
      <section class="space-y-4">
        <RuntimeReadinessSection />
        <div class="alert alert-error">{t("settings.page.error")}</div>
      </section>
    );
  }

  const state = localState.defaultRecipientEmail ? localState : query.data;
  const events = eventsQuery.data;
  const cockpit = cockpitQuery.data;
  const limitedSupportLane = cockpit.limitedSupportLane;
  const storeBindings = storeBindingsQuery.data;
  const officialFullCount = cockpit.summary.officialFullCount;
  const officialPartialCount = cockpit.summary.officialPartialCount;
  const officialInProgressCount = cockpit.summary.officialInProgressCount;
  const enabledCount = cockpit.summary.enabledStoreCount;
  const disabledCount = cockpit.summary.disabledStoreCount;
  const compareCapableCount = cockpit.summary.compareIntakeSupportedCount;
  const cashbackCapableCount = cockpit.summary.cashbackSupportedCount;
  const taskCapableCount = cockpit.summary.watchTaskSupportedCount;
  const groupCapableCount = cockpit.summary.watchGroupSupportedCount;
  const recoveryCapableCount = cockpit.summary.recoverySupportedCount;
  const compareReadyCount = storeBindings.filter(
    (binding) => binding.enabled && binding.supportsCompareIntake,
  ).length;
  const formatCount = (value: number) => formatNumber(locale, value, "0");
  const settingsText = (
    key: string,
    fallback: DraftMessage,
    values?: Record<string, string | number>,
  ) => resolvePageCopy(t, locale, key, fallback, values);

  function onToggleStore(binding: StoreBindingSetting) {
    storeMutation.mutate({ storeKey: binding.storeKey, enabled: !binding.enabled });
  }

  return (
    <section class="space-y-4">
      <RuntimeReadinessSection />

      <section class="grid gap-4 xl:grid-cols-[1.08fr,0.92fr]">
        <div class="space-y-4">
          <div class="rounded-[1.75rem] border border-base-300 bg-base-100/95 p-6 shadow-card">
            <p class="text-xs font-semibold uppercase tracking-[0.2em] text-ember">{t("settings.page.notificationsEyebrow")}</p>
            <h2 class="mt-2 text-2xl font-semibold text-ink">{t("settings.page.notificationsTitle")}</h2>
            <p class="mt-2 text-sm leading-6 text-slate-600">
              {t("settings.page.notificationsSummary")}
            </p>
            <div class="mt-6 space-y-5">
              <label class="form-control gap-2 rounded-2xl border border-base-300/80 bg-base-200/40 px-4 py-4">
                <span class="label-text block font-medium text-ink">{t("settings.notifications.recipientEmail")}</span>
                <span class="text-xs leading-5 text-slate-500">{t("settings.notifications.recipientHelp")}</span>
                <input
                  class="input input-bordered"
                  onInput={(event) =>
                    setLocalState((current) => ({
                      ...current,
                      defaultRecipientEmail: (event.currentTarget as HTMLInputElement).value,
                    }))
                  }
                  type="email"
                  value={state.defaultRecipientEmail}
                />
              </label>

              <label class="form-control gap-2 rounded-2xl border border-base-300/80 bg-base-200/40 px-4 py-4">
                <span class="label-text block font-medium text-ink">{t("settings.notifications.cooldown")}</span>
                <span class="text-xs leading-5 text-slate-500">{t("settings.notifications.cooldownHelp")}</span>
                <input
                  class="input input-bordered"
                  min="0"
                  onInput={(event) =>
                    setLocalState((current) => ({
                      ...current,
                      cooldownMinutes: Number((event.currentTarget as HTMLInputElement).value),
                    }))
                  }
                  type="number"
                  value={state.cooldownMinutes}
                />
              </label>

              <label class="label cursor-pointer rounded-2xl border border-base-300/80 bg-base-200/40 px-4 py-4">
                <span>
                  <span class="label-text block font-medium text-ink">{t("settings.notifications.enabled")}</span>
                  <span class="mt-1 block text-xs leading-5 text-slate-500">{t("settings.notifications.enabledHelp")}</span>
                </span>
                <input
                  checked={state.notificationsEnabled}
                  class="toggle toggle-primary"
                  onInput={(event) =>
                    setLocalState((current) => ({
                      ...current,
                      notificationsEnabled: (event.currentTarget as HTMLInputElement).checked,
                    }))
                  }
                  type="checkbox"
                />
              </label>

              <button
                class="btn btn-primary"
                onClick={() => mutation.mutate(state)}
                type="button"
              >
                {mutation.isPending ? t("settings.notifications.saving") : t("settings.notifications.save")}
              </button>

              {mutation.isSuccess ? <div class="alert alert-success">{t("settings.notifications.saved")}</div> : null}
              {mutation.isError ? <div class="alert alert-error">{t("settings.notifications.saveError")}</div> : null}
            </div>
          </div>

          <div class="rounded-[1.75rem] border border-base-300 bg-base-100/95 p-6 shadow-card">
            <h3 class="text-lg font-semibold text-ink">{t("settings.page.deliveryEventsTitle")}</h3>
            <p class="mt-2 text-sm leading-6 text-slate-600">
              {t("settings.page.deliveryEventsSummary")}
            </p>
            <div class="mt-4 space-y-3">
              {events.length ? (
                events.map((event) => (
                  <div class="rounded-2xl border border-base-300 px-4 py-3" key={event.id}>
                    <div class="flex items-center justify-between gap-3">
                      <div>
                        <div class="font-semibold text-ink">{event.provider}</div>
                        <div class="text-xs text-slate-500">{event.recipient}</div>
                      </div>
                      <span class={`badge ${deliveryTone(event.status)}`}>{deliveryStatusCopy(t, locale, event.status)}</span>
                    </div>
                    <div class="mt-3 flex flex-wrap gap-2 text-xs">
                      {event.watchTaskId ? (
                        <span class="badge badge-outline">
                          {settingsText("settings.deliveryEvents.taskRef", SETTINGS_COPY.deliveryEvents.taskRef, {
                            value: event.watchTaskId,
                          })}
                        </span>
                      ) : null}
                      {event.watchGroupId ? (
                        <span class="badge badge-outline">
                          {settingsText("settings.deliveryEvents.groupRef", SETTINGS_COPY.deliveryEvents.groupRef, {
                            value: event.watchGroupId,
                          })}
                        </span>
                      ) : null}
                      {event.messageId ? (
                        <span class="badge badge-outline">
                          {settingsText("settings.deliveryEvents.messageRef", SETTINGS_COPY.deliveryEvents.messageRef, {
                            value: event.messageId,
                          })}
                        </span>
                      ) : null}
                    </div>
                    <p class="mt-3 text-xs text-slate-500">
                      {formatDateTime(locale, event.deliveredAt ?? event.bouncedAt ?? event.sentAt ?? event.createdAt)}
                    </p>
                  </div>
                ))
              ) : (
                <p class="text-sm text-slate-600">{t("settings.notifications.noEvents")}</p>
              )}
            </div>
          </div>
        </div>

        <aside class="rounded-[1.75rem] border border-base-300 bg-base-100/95 p-6 shadow-card">
          <h3 class="text-lg font-semibold text-ink">{t("settings.page.whyTitle")}</h3>
          <div class="mt-4 space-y-3 text-sm leading-6 text-slate-600">
            <p>{t("settings.page.deliveryEventsSummary")}</p>
            <p>{t("settings.page.whyMcpBoundarySummary")}</p>
            <p>{t("settings.page.cockpitSummary")}</p>
            {cockpit.registryHealth.registryParityOk ? (
              <div class="rounded-2xl bg-base-200/60 px-4 py-3 text-xs leading-5 text-slate-600">
                {t("settings.page.registryHealthySummary")}
              </div>
            ) : (
              <div class="rounded-2xl bg-amber-50 px-4 py-3 text-xs leading-5 text-amber-900">
                {t("settings.page.registryWarningSummary")}
              </div>
            )}
          </div>
        </aside>
      </section>

      <section class="rounded-[1.75rem] border border-base-300 bg-base-100/95 p-6 shadow-card">
        <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p class="text-xs font-semibold uppercase tracking-[0.2em] text-ember">
              {t("settings.page.cockpitEyebrow")}
            </p>
            <div class="mt-2 flex flex-wrap items-center gap-3">
              <h2 class="text-2xl font-semibold text-ink">{t("settings.page.cockpitTitle")}</h2>
              <span class="badge badge-outline">
                {settingsText("settings.cockpit.officialStores", SETTINGS_COPY.cockpit.officialStores, {
                  count: formatCount(cockpit.summary.supportedStoreCount),
                })}
              </span>
            </div>
            <p class="mt-2 max-w-4xl text-sm leading-6 text-slate-600">
              {t("settings.page.cockpitSummary")}
            </p>
            <p class="mt-2 max-w-4xl text-sm leading-6 text-slate-500">
              {t("settings.page.cockpitBridgeSummary")}
            </p>
          </div>
          <div class="flex flex-wrap gap-2 text-xs">
            <span class="badge badge-outline">
              {settingsText("settings.cockpit.officialFullCount", SETTINGS_COPY.cockpit.officialFull, {
                count: formatCount(officialFullCount),
              })}
            </span>
            <span class="badge badge-outline">
              {settingsText("settings.cockpit.officialPartialCount", SETTINGS_COPY.cockpit.officialPartial, {
                count: formatCount(officialPartialCount),
              })}
            </span>
            <span class="badge badge-outline">
              {settingsText("settings.cockpit.officialInProgressCount", SETTINGS_COPY.cockpit.officialInProgress, {
                count: formatCount(officialInProgressCount),
              })}
            </span>
            <span class="badge badge-outline">
              {settingsText("settings.cockpit.enabledCount", SETTINGS_COPY.cockpit.enabled, { count: formatCount(enabledCount) })}
            </span>
            <span class="badge badge-outline">
              {settingsText("settings.cockpit.disabledCount", SETTINGS_COPY.cockpit.disabled, { count: formatCount(disabledCount) })}
            </span>
            <span class="badge badge-outline">
              {settingsText("settings.cockpit.compareCapableCount", SETTINGS_COPY.cockpit.compareCapable, {
                count: formatCount(compareCapableCount),
              })}
            </span>
            <span class="badge badge-outline">
              {settingsText("settings.cockpit.cashbackCapableCount", SETTINGS_COPY.cockpit.cashbackCapable, {
                count: formatCount(cashbackCapableCount),
              })}
            </span>
            <span class="badge badge-outline">
              {settingsText("settings.cockpit.taskCapableCount", SETTINGS_COPY.cockpit.taskCapable, {
                count: formatCount(taskCapableCount),
              })}
            </span>
            <span class="badge badge-outline">
              {settingsText("settings.cockpit.groupCapableCount", SETTINGS_COPY.cockpit.groupCapable, {
                count: formatCount(groupCapableCount),
              })}
            </span>
            <span class="badge badge-outline">
              {settingsText("settings.cockpit.recoveryCapableCount", SETTINGS_COPY.cockpit.recoveryCapable, {
                count: formatCount(recoveryCapableCount),
              })}
            </span>
            <span class="badge badge-outline">
              {settingsText("settings.cockpit.liveForCompareCount", SETTINGS_COPY.cockpit.liveForCompare, {
                count: formatCount(compareReadyCount),
              })}
            </span>
          </div>
        </div>

        <div class="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          <article class="rounded-2xl border border-base-300 bg-base-200/50 px-4 py-4 xl:col-span-2">
            <p class="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              {t("settings.page.cockpitTitle")}
            </p>
            <h3 class="mt-2 text-lg font-semibold text-ink">
              {settingsText("settings.cockpit.liveNowParked", SETTINGS_COPY.cockpit.liveNowParked, {
                enabled: formatCount(enabledCount),
                disabled: formatCount(disabledCount),
              })}
            </h3>
            <p class="mt-2 text-sm leading-6 text-slate-600">
              {t("settings.page.cockpitSummary")}
            </p>
          </article>

          <article class="rounded-2xl border border-base-300 bg-base-200/50 px-4 py-4">
            <p class="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              {t("settings.page.compareCapableCardTitle")}
            </p>
            <h3 class="mt-2 text-lg font-semibold text-ink">
              {settingsText("settings.cockpit.compareCapableStores", SETTINGS_COPY.cockpit.compareCapableStores, {
                count: formatCount(compareCapableCount),
              })}
            </h3>
            <p class="mt-2 text-sm leading-6 text-slate-600">
              {t("settings.page.compareCapableCardSummary")}
            </p>
          </article>

          <article class="rounded-2xl border border-base-300 bg-base-200/50 px-4 py-4">
            <p class="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              {t("settings.page.cashbackCardTitle")}
            </p>
            <h3 class="mt-2 text-lg font-semibold text-ink">
              {settingsText("settings.cockpit.cashbackCapableStores", SETTINGS_COPY.cockpit.cashbackCapableStores, {
                count: formatCount(cashbackCapableCount),
              })}
            </h3>
            <p class="mt-2 text-sm leading-6 text-slate-600">
              {t("settings.page.cashbackCardSummary")}
            </p>
          </article>

          <article class="rounded-2xl border border-base-300 bg-base-200/50 px-4 py-4">
            <p class="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              {t("settings.page.disciplineCardTitle")}
            </p>
            <h3 class="mt-2 text-lg font-semibold text-ink">
              {settingsText("settings.cockpit.disableFirstProveSecond", SETTINGS_COPY.cockpit.disableFirstProveSecond)}
            </h3>
            <p class="mt-2 text-sm leading-6 text-slate-600">
              {t("settings.page.disciplineCardSummary")}
            </p>
          </article>
        </div>

        <div class="mt-6 overflow-x-auto rounded-2xl border border-base-300">
          <table class="min-w-full border-collapse bg-base-100 text-sm">
            <thead class="bg-base-200/70 text-left text-xs uppercase tracking-[0.16em] text-slate-500">
              <tr>
                <th class="px-4 py-3 font-semibold">{settingsText("settings.cockpit.table.store", SETTINGS_COPY.cockpit.table.store)}</th>
                <th class="px-4 py-3 font-semibold">{settingsText("settings.cockpit.table.tier", SETTINGS_COPY.cockpit.table.tier)}</th>
                <th class="px-4 py-3 font-semibold">{settingsText("settings.cockpit.table.binding", SETTINGS_COPY.cockpit.table.binding)}</th>
                <th class="px-4 py-3 font-semibold">{settingsText("settings.cockpit.table.compare", SETTINGS_COPY.cockpit.table.compare)}</th>
                <th class="px-4 py-3 font-semibold">{settingsText("settings.cockpit.table.task", SETTINGS_COPY.cockpit.table.task)}</th>
                <th class="px-4 py-3 font-semibold">{settingsText("settings.cockpit.table.group", SETTINGS_COPY.cockpit.table.group)}</th>
                <th class="px-4 py-3 font-semibold">{settingsText("settings.cockpit.table.recovery", SETTINGS_COPY.cockpit.table.recovery)}</th>
                <th class="px-4 py-3 font-semibold">{settingsText("settings.cockpit.table.cashback", SETTINGS_COPY.cockpit.table.cashback)}</th>
                <th class="px-4 py-3 font-semibold">{settingsText("settings.cockpit.table.region", SETTINGS_COPY.cockpit.table.region)}</th>
                <th class="px-4 py-3 font-semibold">{settingsText("settings.cockpit.table.discovery", SETTINGS_COPY.cockpit.table.discovery)}</th>
                <th class="px-4 py-3 font-semibold">{settingsText("settings.cockpit.table.parse", SETTINGS_COPY.cockpit.table.parse)}</th>
              </tr>
            </thead>
            <tbody>
              {storeBindings.map((binding) => {
                const storeRow = cockpit.stores.find((item) => item.storeKey === binding.storeKey);
                return (
                  <tr class="border-t border-base-300 align-top" key={binding.storeKey}>
                    <td class="px-4 py-4">
                      <div class="font-semibold text-ink">{binding.storeKey}</div>
                      <div class="mt-1 text-xs leading-5 text-slate-500">{binding.adapterClass}</div>
                      {storeRow?.contractStatus === "attention_needed" ? (
                        <span class="badge badge-warning mt-2">
                          {settingsText("settings.cockpit.table.contractAttention", SETTINGS_COPY.cockpit.table.contractAttention)}
                        </span>
                      ) : (
                        <span class="badge badge-success mt-2">
                          {settingsText("settings.cockpit.table.contractReady", SETTINGS_COPY.cockpit.table.contractReady)}
                        </span>
                      )}
                    </td>
                    <td class="px-4 py-4">
                      <span class={`badge ${supportTierBadgeClass(binding.supportTier)}`}>
                        {supportTierCopy(binding, t, locale)}
                      </span>
                      {storeRow?.supportSummary ? (
                        <p class="mt-2 max-w-xs text-xs leading-5 text-slate-500">{storeRow.supportSummary}</p>
                      ) : null}
                      {storeRow?.nextOnboardingStep ? (
                        <p class="mt-2 max-w-xs text-[11px] leading-5 text-slate-400">{storeRow.nextOnboardingStep}</p>
                      ) : null}
                      {storeRow?.contractTestPaths.length ? (
                        <div class="mt-3">
                          <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                            {settingsText("settings.cockpit.contractTests", SETTINGS_COPY.cockpit.contractTests)}
                          </div>
                          <div class="mt-2 flex flex-wrap gap-2">
                            {storeRow.contractTestPaths.map((path) => (
                              <span class="badge badge-outline" key={path}>{path.replace(/^tests\//, "")}</span>
                            ))}
                          </div>
                        </div>
                      ) : null}
                    </td>
                    <td class="px-4 py-4">
                      <div class="flex items-start justify-between gap-3">
                        <div>
                          <span class={`badge ${binding.enabled ? "badge-success" : "badge-outline"}`}>
                            {binding.enabled
                              ? settingsText("settings.cockpit.table.enabled", SETTINGS_COPY.cockpit.table.enabled)
                              : settingsText("settings.cockpit.table.disabled", SETTINGS_COPY.cockpit.table.disabled)}
                          </span>
                          <p class="mt-2 max-w-xs text-xs leading-5 text-slate-500">
                            {bindingStatusCopy(binding, t, locale)}
                          </p>
                        </div>
                        <label class="label cursor-pointer gap-3 py-0">
                          <span class="sr-only">
                            {settingsText("settings.cockpit.table.toggleBinding", SETTINGS_COPY.cockpit.table.toggleBinding, {
                              storeKey: binding.storeKey,
                            })}
                          </span>
                          <input
                            checked={binding.enabled}
                            class="toggle toggle-primary"
                            disabled={storeMutation.isPending}
                            onInput={() => onToggleStore(binding)}
                            type="checkbox"
                          />
                        </label>
                      </div>
                    </td>
                    <td class="px-4 py-4">
                      <span class={`badge ${binding.supportsCompareIntake ? "badge-success" : "badge-outline"}`}>
                        {binding.supportsCompareIntake
                          ? settingsText("settings.cockpit.table.supported", SETTINGS_COPY.cockpit.table.supported)
                          : settingsText("settings.cockpit.table.notYet", SETTINGS_COPY.cockpit.table.notYet)}
                      </span>
                    </td>
                    <td class="px-4 py-4">
                      <span class={`badge ${binding.supportsWatchTask ? "badge-success" : "badge-outline"}`}>
                        {binding.supportsWatchTask
                          ? settingsText("settings.cockpit.table.supported", SETTINGS_COPY.cockpit.table.supported)
                          : settingsText("settings.cockpit.table.notYet", SETTINGS_COPY.cockpit.table.notYet)}
                      </span>
                    </td>
                    <td class="px-4 py-4">
                      <span class={`badge ${binding.supportsWatchGroup ? "badge-success" : "badge-outline"}`}>
                        {binding.supportsWatchGroup
                          ? settingsText("settings.cockpit.table.supported", SETTINGS_COPY.cockpit.table.supported)
                          : settingsText("settings.cockpit.table.notYet", SETTINGS_COPY.cockpit.table.notYet)}
                      </span>
                    </td>
                    <td class="px-4 py-4">
                      <span class={`badge ${binding.supportsRecovery ? "badge-success" : "badge-outline"}`}>
                        {binding.supportsRecovery
                          ? settingsText("settings.cockpit.table.supported", SETTINGS_COPY.cockpit.table.supported)
                          : settingsText("settings.cockpit.table.notYet", SETTINGS_COPY.cockpit.table.notYet)}
                      </span>
                    </td>
                    <td class="px-4 py-4">
                      <span class={`badge ${binding.cashbackSupported ? "badge-success" : "badge-outline"}`}>
                        {binding.cashbackSupported
                          ? settingsText("settings.cockpit.table.supported", SETTINGS_COPY.cockpit.table.supported)
                          : settingsText("settings.cockpit.table.none", SETTINGS_COPY.cockpit.table.none)}
                      </span>
                    </td>
                    <td class="px-4 py-4">
                      <span class="badge badge-outline">
                        {binding.regionSensitive
                          ? settingsText("settings.cockpit.table.regionAware", SETTINGS_COPY.cockpit.table.regionAware)
                          : settingsText("settings.cockpit.table.regionStatic", SETTINGS_COPY.cockpit.table.regionStatic)}
                      </span>
                    </td>
                    <td class="px-4 py-4 text-slate-600">{binding.discoveryMode}</td>
                    <td class="px-4 py-4 text-slate-600">{binding.parseMode}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {storeMutation.isError ? (
          <div class="alert alert-error mt-4">
            {settingsText("settings.cockpit.updateError", SETTINGS_COPY.cockpit.updateError)}
          </div>
        ) : null}

        <div class="mt-6 grid gap-4 xl:grid-cols-[1.15fr,0.85fr,1fr]">
          <article class="rounded-2xl border border-base-300 px-5 py-5">
            <p class="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              {settingsText("settings.cockpit.onboardingChecklist", SETTINGS_COPY.cockpit.onboardingChecklist)}
            </p>
            <div class="mt-4 space-y-4">
              {cockpit.onboardingChecklist.map((item, index) => (
                <div class="flex gap-3" key={item.key}>
                  <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-base-200 text-sm font-semibold text-ink">
                    {index + 1}
                  </div>
                  <div>
                    <h3 class="font-semibold text-ink">{item.label}</h3>
                    <p class="mt-1 text-sm leading-6 text-slate-600">{item.detail}</p>
                  </div>
                </div>
              ))}
            </div>
          </article>

          <article class="rounded-2xl border border-base-300 px-5 py-5">
            <p class="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              {settingsText("settings.cockpit.verificationCommands", SETTINGS_COPY.cockpit.verificationCommands)}
            </p>
            <p class="mt-3 text-sm leading-6 text-slate-600">
              {settingsText("settings.cockpit.verificationCommandsDetail", SETTINGS_COPY.cockpit.verificationCommandsDetail)}
            </p>
            <pre class="mt-4 overflow-x-auto rounded-2xl bg-base-200/70 px-4 py-4 text-xs leading-6 text-slate-700">
              {cockpit.verificationCommands.join("\n")}
            </pre>
          </article>

          <article class="rounded-2xl border border-base-300 px-5 py-5">
            <p class="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              {settingsText("settings.cockpit.sourceRefs", SETTINGS_COPY.cockpit.sourceRefs)}
            </p>
            <p class="mt-3 text-sm leading-6 text-slate-600">
              {settingsText("settings.cockpit.sourceRefsDetail", SETTINGS_COPY.cockpit.sourceRefsDetail)}
            </p>
            <div class="mt-4 space-y-3 text-sm leading-6 text-slate-600">
              {cockpit.truthSources.map((item) => (
                <div class="rounded-2xl bg-base-200/50 px-4 py-3" key={item}>
                  <code class="text-xs leading-5 text-slate-700">{item}</code>
                </div>
              ))}
            </div>
          </article>

          <article class="rounded-2xl border border-base-300 px-5 py-5 xl:col-span-3">
            <p class="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              {t("settings.page.limitedSupportTitle")}
            </p>
            <p class="mt-3 text-sm leading-6 text-slate-600">
              {t("settings.page.limitedSupportSummary")}
            </p>
            <div class="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-[1fr,1fr,1.1fr]">
              {cockpit.limitedSupportContract.map((item) => (
                <div class="rounded-2xl bg-base-200/50 px-4 py-3 text-sm leading-6 text-slate-600" key={item}>
                  {item}
                </div>
              ))}
              <div class="rounded-2xl bg-base-200/50 px-4 py-3">
                <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                  {t("settings.page.limitedSupportAllowedTitle")}
                </div>
                <div class="mt-3 flex flex-wrap gap-2">
                  {limitedSupportLane.supportedActions.map((item) => (
                    <span class="badge badge-success" key={item}>{limitedSupportActionCopy(t, locale, item)}</span>
                  ))}
                </div>
              </div>
              <div class="rounded-2xl bg-base-200/50 px-4 py-3">
                <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                  {t("settings.page.limitedSupportBlockedTitle")}
                </div>
                <div class="mt-3 flex flex-wrap gap-2">
                  {limitedSupportLane.blockedActions.map((item) => (
                    <span class="badge badge-outline" key={item}>{limitedSupportActionCopy(t, locale, item)}</span>
                  ))}
                </div>
              </div>
              <div class="rounded-2xl bg-base-200/50 px-4 py-3 md:col-span-2 xl:col-span-1">
                <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                  {t("settings.page.limitedSupportSourceRefsTitle")}
                </div>
                <div class="mt-3 space-y-2 text-xs leading-5 text-slate-600">
                  {limitedSupportLane.sourceOfTruthFiles.map((item) => (
                    <div class="rounded-xl bg-base-100/80 px-3 py-2" key={item}>
                      <code>{item}</code>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </article>
        </div>
      </section>
    </section>
  );
}
