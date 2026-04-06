const SAMPLE_FIXTURE_PATH = "./data/compare-preview-sample.json";

function siteT(key, fallback) {
  return window.dealwatchSiteI18n?.t?.(key, fallback) ?? fallback;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function money(value) {
  return typeof value === "number" ? `$${value.toFixed(2)}` : siteT("site.comparePreviewPage.demoNotAvailable", "n/a");
}

function renderComparison(item) {
  const offer = item.offer || {};
  const unitInfo = offer.unit_price_info || {};
  return `
    <li class="demo-item">
      <div class="demo-item-head">
        <strong>${escapeHtml(offer.title || item.submitted_url)}</strong>
        <span>${escapeHtml(item.store_key || siteT("site.comparePreviewPage.demoUnknownStore", "unknown store"))}</span>
      </div>
      <p class="demo-item-copy">
        ${escapeHtml(siteT("site.comparePreviewPage.demoCandidateKey", "Candidate key"))}: <code>${escapeHtml(item.candidate_key || siteT("site.comparePreviewPage.demoNotAvailable", "n/a"))}</code><br />
        ${escapeHtml(siteT("site.comparePreviewPage.demoNormalizedUrl", "Normalized URL"))}: <code>${escapeHtml(item.normalized_url || item.submitted_url)}</code>
      </p>
      <ul>
        <li>${escapeHtml(siteT("site.comparePreviewPage.demoListedPrice", "Listed price"))}: ${money(offer.price)} (${escapeHtml(siteT("site.comparePreviewPage.demoOriginalPrefix", "original"))} ${money(offer.original_price)})</li>
        <li>${escapeHtml(siteT("site.comparePreviewPage.demoBrandHint", "Brand hint"))}: ${escapeHtml(item.brand_hint || unitInfo.brand || siteT("site.comparePreviewPage.demoUnknown", "unknown"))}</li>
        <li>${escapeHtml(siteT("site.comparePreviewPage.demoSizeHint", "Size hint"))}: ${escapeHtml(item.size_hint || unitInfo.raw || siteT("site.comparePreviewPage.demoUnknown", "unknown"))}</li>
      </ul>
    </li>
  `;
}

function renderMatch(item) {
  const whyLike = Array.isArray(item.why_like) && item.why_like.length
    ? `<ul>${item.why_like.map((entry) => `<li>${escapeHtml(entry)}</li>`).join("")}</ul>`
    : `<p class="demo-item-copy">${escapeHtml(siteT("site.comparePreviewPage.demoNoPositiveSignals", "No positive signals recorded in this sample."))}</p>`;
  const whyUnlike = Array.isArray(item.why_unlike) && item.why_unlike.length
    ? `<ul>${item.why_unlike.map((entry) => `<li>${escapeHtml(entry)}</li>`).join("")}</ul>`
    : `<p class="demo-item-copy">${escapeHtml(siteT("site.comparePreviewPage.demoNoNegativeSignals", "No negative signals recorded in this sample."))}</p>`;

  return `
    <li class="demo-item">
      <div class="demo-item-head">
        <strong>${escapeHtml(item.left_store_key)} vs ${escapeHtml(item.right_store_key)}</strong>
        <span>${escapeHtml(siteT("site.comparePreviewPage.demoScorePrefix", "Score"))} ${escapeHtml(item.score)}</span>
      </div>
      <p class="demo-item-copy">
        ${escapeHtml(siteT("site.comparePreviewPage.demoTitleSimilarity", "Title similarity"))}: ${escapeHtml(item.title_similarity)} ·
        ${escapeHtml(siteT("site.comparePreviewPage.demoBrand", "Brand"))}: ${escapeHtml(item.brand_signal)} ·
        ${escapeHtml(siteT("site.comparePreviewPage.demoSize", "Size"))}: ${escapeHtml(item.size_signal)}
      </p>
      <div class="demo-grid">
        <div class="demo-panel">
          <h3>${escapeHtml(siteT("site.comparePreviewPage.demoWhyClose", "Why it looks close"))}</h3>
          ${whyLike}
        </div>
        <div class="demo-panel">
          <h3>${escapeHtml(siteT("site.comparePreviewPage.demoWhyDifferent", "Why it looks different"))}</h3>
          ${whyUnlike}
        </div>
      </div>
    </li>
  `;
}

function renderSampleResults(fixture) {
  return `
    <div class="demo-summary">
      <div class="status-pill">
        <strong>${escapeHtml(fixture.submitted_count)}</strong>
        <span class="small-note">${escapeHtml(siteT("site.comparePreviewPage.demoSubmittedUrls", "submitted URLs in this public fixture"))}</span>
      </div>
      <div class="status-pill">
        <strong>${escapeHtml(fixture.resolved_count)}</strong>
        <span class="small-note">${escapeHtml(siteT("site.comparePreviewPage.demoResolvedOffers", "resolved candidate offers"))}</span>
      </div>
      <div class="status-pill">
        <strong>${escapeHtml(fixture.matches[0]?.score ?? "n/a")}</strong>
        <span class="small-note">${escapeHtml(siteT("site.comparePreviewPage.demoTopMatchScore", "top match score for the two-store pear pair"))}</span>
      </div>
      <div class="status-pill">
        <strong>${escapeHtml(fixture.zip_code)}</strong>
        <span class="small-note">${escapeHtml(siteT("site.comparePreviewPage.demoSampleZip", "sample ZIP code used for the compare story"))}</span>
      </div>
    </div>
    <div class="demo-grid">
      <div class="demo-panel">
        <h3>${escapeHtml(siteT("site.comparePreviewPage.demoSampleUrlsTitle", "Sample URLs"))}</h3>
        <pre>${fixture.submitted_urls.map((url) => escapeHtml(url)).join("\n")}</pre>
      </div>
      <div class="demo-panel">
        <h3>${escapeHtml(siteT("site.comparePreviewPage.demoSampleProofTitle", "What this sample proves"))}</h3>
        <ul>
          <li>${escapeHtml(siteT("site.comparePreviewPage.demoSampleProofBullet1", "Compare Preview can surface a strong cross-store match before any task is created."))}</li>
          <li>${escapeHtml(siteT("site.comparePreviewPage.demoSampleProofBullet2", "The same sample also shows an obvious distractor, so “different” is visible too."))}</li>
          <li>${escapeHtml(siteT("site.comparePreviewPage.demoSampleProofBullet3", "This page loads a fixed public fixture only. It does not save anything or call a live write path."))}</li>
        </ul>
      </div>
    </div>
    <div class="demo-panel">
      <h3>${escapeHtml(siteT("site.comparePreviewPage.demoResolvedComparisonsTitle", "Resolved comparisons"))}</h3>
      <ol class="demo-list">
        ${fixture.comparisons.map(renderComparison).join("")}
      </ol>
    </div>
    <div class="demo-panel">
      <h3>${escapeHtml(siteT("site.comparePreviewPage.demoMatchReasoningTitle", "Match reasoning"))}</h3>
      <ol class="demo-list">
        ${fixture.matches.map(renderMatch).join("")}
      </ol>
    </div>
  `;
}

document.addEventListener("DOMContentLoaded", () => {
  const loadButton = document.querySelector("#load-sample-compare");
  const resetButton = document.querySelector("#reset-sample-compare");
  const status = document.querySelector("#sample-status");
  const results = document.querySelector("#sample-results");

  if (!(loadButton instanceof HTMLButtonElement) || !(resetButton instanceof HTMLButtonElement)) {
    return;
  }
  if (!(status instanceof HTMLElement) || !(results instanceof HTMLElement)) {
    return;
  }

  let fixtureCache = null;

  async function loadFixture() {
    if (fixtureCache) {
      return fixtureCache;
    }
    const response = await fetch(SAMPLE_FIXTURE_PATH);
    if (!response.ok) {
      throw new Error(`sample_fixture_${response.status}`);
    }
    fixtureCache = await response.json();
    return fixtureCache;
  }

  loadButton.addEventListener("click", async () => {
    loadButton.disabled = true;
    status.textContent = siteT(
      "site.comparePreviewPage.sampleStatusLoading",
      "Loading the static sample compare fixture...",
    );
    try {
      const fixture = await loadFixture();
      results.innerHTML = renderSampleResults(fixture);
      results.classList.remove("is-hidden");
      status.textContent = fixture.sample_note;
    } catch (error) {
      status.textContent = siteT(
        "site.comparePreviewPage.sampleStatusError",
        "The sample compare fixture could not be loaded. Use the local stack if you want to test your own URLs.",
      );
      results.classList.add("is-hidden");
      results.innerHTML = "";
      console.error(error);
    } finally {
      loadButton.disabled = false;
    }
  });

  resetButton.addEventListener("click", () => {
    results.classList.add("is-hidden");
    results.innerHTML = "";
    status.textContent = siteT(
      "site.comparePreviewPage.sampleStatusIdle",
      "Load the sample compare to inspect a fixed public fixture. Read-only. No data is saved.",
    );
  });

  document.addEventListener("dealwatch:localechange", () => {
    if (results.classList.contains("is-hidden")) {
      status.textContent = siteT(
        "site.comparePreviewPage.sampleStatusIdle",
        "Load the sample compare to inspect a fixed public fixture. Read-only. No data is saved.",
      );
    }
  });
});
