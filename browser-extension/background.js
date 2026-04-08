const CONTEXT_MENU_ID = "dealwatch-open-compare";
const DEFAULT_BASE_URL = "http://127.0.0.1:5173";

function normalizeBaseUrl(raw) {
  const value = String(raw || "").trim();
  return value || DEFAULT_BASE_URL;
}

async function getBaseUrl() {
  const payload = await chrome.storage.sync.get({ dealwatchBaseUrl: DEFAULT_BASE_URL });
  return normalizeBaseUrl(payload.dealwatchBaseUrl);
}

function buildCompareUrl(baseUrl, submittedUrl) {
  const target = new URL(baseUrl);
  target.hash = "#compare";
  if (submittedUrl) {
    target.searchParams.set("dealwatch_submitted_url", submittedUrl);
  }
  return target.toString();
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: CONTEXT_MENU_ID,
    title: "Open in DealWatch Compare",
    contexts: ["page", "link"],
  });
});

chrome.contextMenus.onClicked.addListener(async (info) => {
  if (info.menuItemId !== CONTEXT_MENU_ID) {
    return;
  }

  const baseUrl = await getBaseUrl();
  const sourceUrl = info.linkUrl || info.pageUrl || "";
  await chrome.tabs.create({ url: buildCompareUrl(baseUrl, sourceUrl) });
});
