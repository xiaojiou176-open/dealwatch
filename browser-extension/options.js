const DEFAULT_BASE_URL = "http://127.0.0.1:5173";

function normalizeBaseUrl(raw) {
  const value = String(raw || "").trim();
  return value || DEFAULT_BASE_URL;
}

async function init() {
  const input = document.getElementById("base-url");
  const status = document.getElementById("status");
  const payload = await chrome.storage.sync.get({ dealwatchBaseUrl: DEFAULT_BASE_URL });
  input.value = normalizeBaseUrl(payload.dealwatchBaseUrl);

  document.getElementById("save").addEventListener("click", async () => {
    await chrome.storage.sync.set({ dealwatchBaseUrl: normalizeBaseUrl(input.value) });
    status.textContent = "Saved.";
  });

  document.getElementById("reset").addEventListener("click", async () => {
    input.value = DEFAULT_BASE_URL;
    await chrome.storage.sync.set({ dealwatchBaseUrl: DEFAULT_BASE_URL });
    status.textContent = "Reset to the default local runtime URL.";
  });
}

init().catch((error) => {
  document.getElementById("status").textContent = String(error);
});
