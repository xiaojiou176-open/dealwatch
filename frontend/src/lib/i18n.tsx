import { createContext, type ComponentChildren } from "preact";
import { useContext, useEffect, useState } from "preact/hooks";
import enCatalog from "@shared-locales/en.json";
import zhCatalog from "@shared-locales/zh-CN.json";

export type AppLocale = "en" | "zh-CN";
type Catalog = typeof enCatalog;

const DEFAULT_LOCALE: AppLocale = "en";
const LOCALE_STORAGE_KEY = "dealwatch.locale";

const catalogs: Record<AppLocale, Catalog> = {
  en: enCatalog,
  "zh-CN": zhCatalog as Catalog,
};

interface I18nContextValue {
  locale: AppLocale;
  setLocale: (locale: AppLocale) => void;
  t: (key: string) => string;
}

const I18nContext = createContext<I18nContextValue | null>(null);

function isLocale(value: string): value is AppLocale {
  return value === "en" || value === "zh-CN";
}

function detectBrowserLocale(): AppLocale {
  if (typeof navigator === "undefined") {
    return DEFAULT_LOCALE;
  }

  const languages = [...(navigator.languages ?? []), navigator.language].filter(Boolean);
  return languages.some((language) => language.toLowerCase().startsWith("zh")) ? "zh-CN" : "en";
}

function loadInitialLocale(): AppLocale {
  if (typeof window === "undefined") {
    return DEFAULT_LOCALE;
  }

  try {
    const stored = window.localStorage.getItem(LOCALE_STORAGE_KEY);
    if (stored && isLocale(stored)) {
      return stored;
    }
  } catch {
    // Keep rendering even if localStorage is unavailable.
  }

  return detectBrowserLocale();
}

function lookupMessage(catalog: Catalog, key: string): string | null {
  const value = key.split(".").reduce<unknown>((current, segment) => {
    if (!current || typeof current !== "object") {
      return null;
    }
    return (current as Record<string, unknown>)[segment] ?? null;
  }, catalog);

  return typeof value === "string" ? value : null;
}

export function formatCurrency(locale: AppLocale, value: number | null | undefined, fallback = "--"): string {
  if (typeof value !== "number") {
    return fallback;
  }

  return new Intl.NumberFormat(locale, {
    currency: "USD",
    style: "currency",
  }).format(value);
}

export function formatNumber(
  locale: AppLocale,
  value: number | null | undefined,
  fallback = "--",
  options?: Intl.NumberFormatOptions,
): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return fallback;
  }

  return new Intl.NumberFormat(locale, options).format(value);
}

export function formatDateTime(locale: AppLocale, value: string | null | undefined, fallback = "--"): string {
  if (!value) {
    return fallback;
  }

  return new Date(value).toLocaleString(locale);
}

export function formatShortDate(locale: AppLocale, value: string, fallback = "--"): string {
  if (!value) {
    return fallback;
  }

  return new Date(value).toLocaleDateString(locale, {
    day: "numeric",
    month: "short",
  });
}

export function formatPercent(locale: AppLocale, value: number | null | undefined, fallback = "--"): string {
  if (typeof value !== "number") {
    return fallback;
  }

  return new Intl.NumberFormat(locale, {
    maximumFractionDigits: 2,
    minimumFractionDigits: 2,
    style: "percent",
  }).format(value / 100);
}

export function interpolate(template: string, values: Record<string, string | number>): string {
  return Object.entries(values).reduce((current, [key, value]) => {
    return current.split(`{{${key}}}`).join(String(value));
  }, template);
}

export function I18nProvider(props: { children: ComponentChildren }) {
  const [locale, setLocale] = useState<AppLocale>(loadInitialLocale);

  useEffect(() => {
    document.documentElement.dataset.locale = locale;
    document.documentElement.lang = locale;

    if (typeof window === "undefined") {
      return;
    }

    try {
      window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
    } catch {
      // Keep the runtime usable even if persistence fails.
    }
  }, [locale]);

  return (
    <I18nContext.Provider
      value={{
        locale,
        setLocale,
        t: (key: string) => lookupMessage(catalogs[locale], key) ?? key,
      }}
    >
      {props.children}
    </I18nContext.Provider>
  );
}

export function useI18n(): I18nContextValue {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error("useI18n must be used within I18nProvider");
  }
  return context;
}
