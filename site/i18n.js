const LOCALE_STORAGE_KEY = "dealwatch.locale";
const DEFAULT_LOCALE = "en";
const SUPPORTED_LOCALES = new Set(["en", "zh-CN"]);

let currentLocale = DEFAULT_LOCALE;
let currentCatalog = null;

function isLocale(value) {
  return SUPPORTED_LOCALES.has(value);
}

function detectBrowserLocale() {
  const languages = [navigator.language, ...(navigator.languages || [])].filter(Boolean);
  return languages.some((language) => String(language).toLowerCase().startsWith("zh"))
    ? "zh-CN"
    : DEFAULT_LOCALE;
}

function loadInitialLocale() {
  try {
    const stored = window.localStorage.getItem(LOCALE_STORAGE_KEY);
    if (stored && isLocale(stored)) {
      return stored;
    }
  } catch {
    // Fail open when storage is unavailable.
  }
  return detectBrowserLocale();
}

function lookupMessage(catalog, key) {
  return key.split(".").reduce((current, segment) => {
    if (!current || typeof current !== "object") {
      return null;
    }
    return current[segment] ?? null;
  }, catalog);
}

function setAttributeIfPresent(element, attribute, value) {
  if (typeof value === "string") {
    element.setAttribute(attribute, value);
  }
}

function applyCatalog() {
  if (!currentCatalog) {
    return;
  }

  document.documentElement.lang = currentLocale;

  document.querySelectorAll("[data-i18n]").forEach((element) => {
    const key = element.getAttribute("data-i18n");
    if (!key) {
      return;
    }
    const value = lookupMessage(currentCatalog, key);
    if (typeof value === "string") {
      element.textContent = value;
    }
  });

  document.querySelectorAll("[data-i18n-key][data-i18n-attr]").forEach((element) => {
    const key = element.getAttribute("data-i18n-key");
    const attribute = element.getAttribute("data-i18n-attr");
    if (!key || !attribute) {
      return;
    }
    const value = lookupMessage(currentCatalog, key);
    if (typeof value !== "string") {
      return;
    }
    if (attribute === "text") {
      element.textContent = value;
    } else {
      element.setAttribute(attribute, value);
    }
  });

  document.querySelectorAll("[data-i18n-content]").forEach((element) => {
    const key = element.getAttribute("data-i18n-content");
    if (!key) {
      return;
    }
    setAttributeIfPresent(element, "content", lookupMessage(currentCatalog, key));
  });

  document.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
    const key = element.getAttribute("data-i18n-placeholder");
    if (!key) {
      return;
    }
    setAttributeIfPresent(element, "placeholder", lookupMessage(currentCatalog, key));
  });

  document.querySelectorAll("[data-i18n-aria-label]").forEach((element) => {
    const key = element.getAttribute("data-i18n-aria-label");
    if (!key) {
      return;
    }
    setAttributeIfPresent(element, "aria-label", lookupMessage(currentCatalog, key));
  });

  document.querySelectorAll("[data-i18n-json]").forEach((element) => {
    const key = element.getAttribute("data-i18n-json");
    if (!key) {
      return;
    }
    const value = lookupMessage(currentCatalog, key);
    if (value && typeof value === "object") {
      element.textContent = JSON.stringify(value);
    }
  });

  const titleElement = document.querySelector("title[data-i18n]");
  if (titleElement) {
    const key = titleElement.getAttribute("data-i18n");
    const value = key ? lookupMessage(currentCatalog, key) : null;
    if (typeof value === "string") {
      titleElement.textContent = value;
      document.title = value;
    }
  }

  document.querySelectorAll("[data-locale-option]").forEach((button) => {
    const locale = button.getAttribute("data-locale-option");
    const isActive = locale === currentLocale;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-pressed", isActive ? "true" : "false");
    const label = locale ? lookupMessage(currentCatalog, `common.locale.${locale}`) : null;
    if (typeof label === "string") {
      button.textContent = label;
    }
  });

  document.dispatchEvent(
    new CustomEvent("dealwatch:localechange", {
      detail: {
        catalog: currentCatalog,
        locale: currentLocale,
      },
    }),
  );
}

async function loadCatalog(locale) {
  const response = await fetch(`./data/i18n/${locale}.json`);
  if (!response.ok) {
    throw new Error(`site_i18n_${response.status}`);
  }
  return response.json();
}

async function setLocale(locale) {
  if (!isLocale(locale)) {
    return;
  }

  currentCatalog = await loadCatalog(locale);
  currentLocale = locale;

  try {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
  } catch {
    // Fail open when storage is unavailable.
  }

  applyCatalog();
}

function t(key, fallback = key) {
  return lookupMessage(currentCatalog, key) || fallback;
}

window.dealwatchSiteI18n = {
  get locale() {
    return currentLocale;
  },
  setLocale,
  t,
};

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-locale-option]").forEach((button) => {
    button.addEventListener("click", async () => {
      const locale = button.getAttribute("data-locale-option");
      if (!locale) {
        return;
      }
      try {
        await setLocale(locale);
      } catch (error) {
        console.error(error);
      }
    });
  });

  setLocale(loadInitialLocale()).catch((error) => {
    console.error(error);
  });
});
