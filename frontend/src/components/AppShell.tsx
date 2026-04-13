import type { ComponentChildren } from "preact";
import { useI18n } from "../lib/i18n";
import type { AppRoute } from "../lib/routes";
import { currentGroupId, currentRoute, currentTaskId, navigate } from "../lib/routes";

function navClass(isActive: boolean): string {
  return isActive ? "nav-chip nav-chip-active" : "nav-chip";
}

function contextNavClass(isActive: boolean): string {
  return isActive ? "context-chip context-chip-active" : "context-chip";
}

function routeHref(route: AppRoute): string {
  if (route === "watch-detail" && currentTaskId.value) {
    return `#watch-detail/${currentTaskId.value}`;
  }
  if (route === "watch-group-detail" && currentGroupId.value) {
    return `#watch-group-detail/${currentGroupId.value}`;
  }
  return `#${route}`;
}

function buildShellFocus(route: string, t: (key: string) => string): {
  label: string;
  headline: string;
  summary: string;
  proofPath: string;
} {
  const baseKey =
    route === "watch-new"
      ? "shell.focus.watchNew"
      : route === "watch-list"
        ? "shell.focus.watchList"
        : route === "settings"
          ? "shell.focus.settings"
          : "shell.focus.compare";
  if (route === "watch-new") {
    return {
      label: t(`${baseKey}.label`),
      headline: t(`${baseKey}.headline`),
      summary: t(`${baseKey}.summary`),
      proofPath: t(`${baseKey}.proofPath`),
    };
  }

  if (route === "watch-list") {
    return {
      label: t(`${baseKey}.label`),
      headline: t(`${baseKey}.headline`),
      summary: t(`${baseKey}.summary`),
      proofPath: t(`${baseKey}.proofPath`),
    };
  }

  if (route === "settings") {
    return {
      label: t(`${baseKey}.label`),
      headline: t(`${baseKey}.headline`),
      summary: t(`${baseKey}.summary`),
      proofPath: t(`${baseKey}.proofPath`),
    };
  }

  return {
    label: t(`${baseKey}.label`),
    headline: t(`${baseKey}.headline`),
    summary: t(`${baseKey}.summary`),
    proofPath: t(`${baseKey}.proofPath`),
  };
}

export function AppShell(props: { children: ComponentChildren }) {
  const { locale, setLocale, t } = useI18n();
  const shellFocus = buildShellFocus(currentRoute.value, t);
  const primaryNavItems = [
    { key: "compare", label: t("shell.nav.compare") },
    { key: "watch-list", label: t("shell.nav.watchList") },
    { key: "settings", label: t("shell.nav.settings") },
  ] as const;
  const contextNavItems = [
    currentRoute.value === "watch-new"
      ? { key: "watch-new", label: t("shell.nav.watchNew") }
      : null,
    currentTaskId.value
      ? { key: "watch-detail", label: t("shell.nav.watchDetail") }
      : null,
    currentGroupId.value
      ? { key: "watch-group-detail", label: t("shell.nav.watchGroupDetail") }
      : null,
  ].filter(Boolean) as Array<{ key: AppRoute; label: string }>;
  const flowSteps = [
    t("shell.primaryPathCompare"),
    t("shell.primaryPathDecision"),
    t("shell.primaryPathCommit"),
  ];

  return (
    <div class="shell-root bg-mesh grid-fade" data-theme="dealwatch">
      <a class="skip-link" href="#main-content">
        {t("common.skipToMain")}
      </a>
      <div class="shell-backdrop" />
      <div class="shell-container">
        <header class="shell-header">
          <div class="shell-topline">
            <div class="shell-brand-block">
              <p class="section-kicker">{t("shell.eyebrow")}</p>
              <h1 class="shell-title">{t("shell.title")}</h1>
              <p class="shell-summary">{t("shell.summary")}</p>
            </div>
            <div class="shell-utility-stack">
              <div
                aria-label={t("common.languageLabel")}
                class="shell-locale-card surface-panel surface-panel-muted"
                role="group"
              >
                <div class="shell-shape-label">{t("common.languageLabel")}</div>
                <div class="mt-3 flex flex-wrap gap-2">
                  <button
                    class={locale === "en" ? "nav-chip nav-chip-active" : "nav-chip"}
                    onClick={() => setLocale("en")}
                    type="button"
                  >
                    {t("common.locale.en")}
                  </button>
                  <button
                    class={locale === "zh-CN" ? "nav-chip nav-chip-active" : "nav-chip"}
                    onClick={() => setLocale("zh-CN")}
                    type="button"
                  >
                    {t("common.locale.zh-CN")}
                  </button>
                </div>
              </div>

              <div class="shell-shape-card surface-panel surface-panel-primary">
                <div class="shell-shape-label">{t("shell.productShapeLabel")}</div>
                <div class="shell-shape-value">{t("shell.productShapeValue")}</div>
              </div>
            </div>
          </div>

          <div class="shell-grid">
            <div class="shell-focus-card surface-panel surface-panel-primary">
              <div class="panel-label">{shellFocus.label}</div>
              <div class="panel-title">{shellFocus.headline}</div>
              <p class="panel-copy">{shellFocus.summary}</p>
            </div>

            <div class="shell-proof-card surface-panel surface-panel-proof">
              <div class="panel-label">{t("shell.focus.proofLabel")}</div>
              <div class="panel-title">{shellFocus.proofPath}</div>
              <p class="panel-copy">{t("compare.execution.proof.summary.local")}</p>
            </div>
          </div>

          <div class="shell-nav-card surface-panel">
            <div class="shell-nav-grid">
              <div class="shell-nav-stack">
                <div class="workflow-label">{t("shell.primaryNavLabel")}</div>
                <nav class="shell-nav-row">
                  {primaryNavItems.map((item) => (
                    <a
                      class={navClass(currentRoute.value === item.key)}
                      href={routeHref(item.key)}
                    >
                      {item.label}
                    </a>
                  ))}
                </nav>
              </div>

              <div class="shell-nav-stack">
                <div class="workflow-label">{t("shell.secondaryNavLabel")}</div>
                <div class="shell-nav-row">
                  {contextNavItems.length > 0 ? (
                    contextNavItems.map((item) => (
                      <a
                        class={contextNavClass(currentRoute.value === item.key)}
                        href={routeHref(item.key)}
                      >
                        {item.label}
                      </a>
                    ))
                  ) : (
                    <span class="supporting-copy">{t("shell.secondaryHint")}</span>
                  )}
                </div>
              </div>
            </div>

            <div class="shell-flow-rail">
              <span class="workflow-label">{t("shell.primaryPathLabel")}</span>
              {flowSteps.map((step, index) => (
                <span class="inline-flex items-center gap-2" key={step}>
                  <span class="flow-pill">
                    <span class="flow-pill-number">{index + 1}</span>
                    <span>{step}</span>
                  </span>
                  {index < flowSteps.length - 1 ? <span class="flow-arrow">→</span> : null}
                </span>
              ))}
            </div>
          </div>
        </header>

        <main class="shell-main" id="main-content">{props.children}</main>
      </div>
    </div>
  );
}
