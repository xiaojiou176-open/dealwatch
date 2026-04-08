const DEFAULT_BASE_URL = "http://127.0.0.1:5173";

function normalizeBaseUrl(raw) {
  const value = String(raw || "").trim();
  return value || DEFAULT_BASE_URL;
}

function buildCompareUrl(baseUrl, submittedUrl) {
  const target = new URL(baseUrl);
  target.hash = "#compare";
  if (submittedUrl) {
    target.searchParams.set("dealwatch_submitted_url", submittedUrl);
  }
  return target.toString();
}

async function getBaseUrl() {
  const payload = await chrome.storage.sync.get({ dealwatchBaseUrl: DEFAULT_BASE_URL });
  return normalizeBaseUrl(payload.dealwatchBaseUrl);
}

async function getCurrentTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab ?? null;
}

function updateStatus(message) {
  document.getElementById("status").textContent = message;
}

function renderTab(tab) {
  const hostNode = document.getElementById("current-tab-host");
  const urlNode = document.getElementById("current-tab-url");
  if (!tab || !tab.url) {
    hostNode.textContent = "No active page";
    urlNode.textContent = "Open a product page before using the companion.";
    return;
  }
  try {
    const current = new URL(tab.url);
    hostNode.textContent = current.host;
    urlNode.textContent = tab.url;
  } catch {
    hostNode.textContent = "Unsupported page";
    urlNode.textContent = tab.url;
  }
}

async function openCompare(prefillUrl) {
  const baseUrl = await getBaseUrl();
  await chrome.tabs.create({ url: buildCompareUrl(baseUrl, prefillUrl) });
  window.close();
}

async function init() {
  const baseUrl = await getBaseUrl();
  document.getElementById("base-url").textContent = baseUrl;
  const tab = await getCurrentTab();
  renderTab(tab);

  document.getElementById("open-current").addEventListener("click", async () => {
    if (!tab?.url || !/^https?:/i.test(tab.url)) {
      updateStatus("The current tab does not expose an http(s) URL.");
      return;
    }
    await openCompare(tab.url);
  });

  document.getElementById("open-blank").addEventListener("click", async () => {
    await openCompare("");
  });

  document.getElementById("open-options").addEventListener("click", async () => {
    await chrome.runtime.openOptionsPage();
  });

  document.getElementById("open-docs").addEventListener("click", async () => {
    await chrome.tabs.create({ url: "https://xiaojiou176-open.github.io/dealwatch/quick-start.html" });
  });
}

init().catch((error) => {
  updateStatus(String(error));
});
