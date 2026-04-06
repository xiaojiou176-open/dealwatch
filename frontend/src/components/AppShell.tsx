import type { ComponentChildren } from "preact";
import { useI18n } from "../lib/i18n";
import { currentGroupId, currentRoute, currentTaskId, navigate } from "../lib/routes";

function navClass(isActive: boolean): string {
  return isActive
    ? "btn btn-sm bg-ink text-base-100 border-ink"
    : "btn btn-sm btn-ghost text-ink";
}

export function AppShell(props: { children: ComponentChildren }) {
  const { locale, setLocale, t } = useI18n();

  return (
    <div class="min-h-screen bg-mesh grid-fade text-ink">
      <div class="mx-auto flex min-h-screen w-full max-w-7xl flex-col px-4 py-6 md:px-6">
        <header class="mb-6 rounded-[2rem] border border-base-300/70 bg-base-100/90 p-5 shadow-card backdrop-blur">
          <div class="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
            <div>
              <p class="text-xs font-semibold uppercase tracking-[0.24em] text-ember">
                {t("shell.eyebrow")}
              </p>
              <h1 class="mt-2 font-serif text-4xl font-semibold text-ink">
                {t("shell.title")}
              </h1>
              <p class="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
                {t("shell.summary")}
              </p>
            </div>
            <div class="flex flex-col gap-3 md:items-end">
              <div class="rounded-2xl border border-base-300 bg-base-200/80 px-4 py-3 text-sm text-slate-600">
                <div class="font-semibold text-ink">{t("shell.productShapeLabel")}</div>
                <div>{t("shell.productShapeValue")}</div>
              </div>
              <div
                aria-label={t("common.languageLabel")}
                class="inline-flex items-center gap-2 rounded-2xl border border-base-300 bg-base-100/90 px-3 py-2 text-xs text-slate-600"
                role="group"
              >
                <span class="font-semibold text-ink">{t("common.languageLabel")}</span>
                <button
                  class={locale === "en" ? "btn btn-xs border-ink bg-ink text-base-100" : "btn btn-xs btn-ghost text-ink"}
                  onClick={() => setLocale("en")}
                  type="button"
                >
                  {t("common.locale.en")}
                </button>
                <button
                  class={locale === "zh-CN" ? "btn btn-xs border-ink bg-ink text-base-100" : "btn btn-xs btn-ghost text-ink"}
                  onClick={() => setLocale("zh-CN")}
                  type="button"
                >
                  {t("common.locale.zh-CN")}
                </button>
              </div>
            </div>
          </div>

          <nav class="mt-5 flex flex-wrap gap-2">
            <button
              class={navClass(currentRoute.value === "compare")}
              onClick={() => navigate("compare")}
              type="button"
            >
              {t("shell.nav.compare")}
            </button>
            <button
              class={navClass(currentRoute.value === "watch-list")}
              onClick={() => navigate("watch-list")}
              type="button"
            >
              {t("shell.nav.watchList")}
            </button>
            <button
              class={navClass(currentRoute.value === "watch-new")}
              onClick={() => navigate("watch-new")}
              type="button"
            >
              {t("shell.nav.watchNew")}
            </button>
            <button
              class={navClass(currentRoute.value === "watch-detail")}
              disabled={!currentTaskId.value}
              onClick={() => navigate("watch-detail")}
              type="button"
            >
              {t("shell.nav.watchDetail")}
            </button>
            <button
              class={navClass(currentRoute.value === "watch-group-detail")}
              disabled={!currentGroupId.value}
              onClick={() => navigate("watch-group-detail")}
              type="button"
            >
              {t("shell.nav.watchGroupDetail")}
            </button>
            <button
              class={navClass(currentRoute.value === "settings")}
              onClick={() => navigate("settings")}
              type="button"
            >
              {t("shell.nav.settings")}
            </button>
          </nav>
        </header>

        <main class="flex-1">{props.children}</main>
      </div>
    </div>
  );
}
