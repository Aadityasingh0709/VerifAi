/* VerifAI sidebar — handles UI state, talks to backend via service worker. */

const BACKEND = "http://localhost:8000";
const POLL_INTERVAL_MS = 1500;

const DOMAIN_LABELS = {
  healthcare: "Healthcare Mode",
  legal: "Legal Mode",
  finance: "Finance Mode",
  education: "Education Mode",
  news: "News Mode",
  general: "General Mode",
};

const DOMAIN_COLORS = {
  healthcare: "#ef4444",
  legal: "#8b5cf6",
  finance: "#22c55e",
  education: "#3b82f6",
  news: "#f59e0b",
  general: "#64748b",
};

const state = {
  auditId: null,
  currentResult: null,
  pollTimer: null,
};

/* ---------------- dom refs ---------------- */
const $ = (id) => document.getElementById(id);
const idlePanel = $("idle-panel");
const progressPanel = $("progress-panel");
const resultsPanel = $("results-panel");
const errorPanel = $("error-panel");
const samplesList = $("samples-list");
const domainPill = $("domain-pill");
const domainPillLabel = $("domain-pill-label");
const gaugeScore = $("gauge-score");
const gaugeBand = $("gauge-band");
const gaugeFg = $("gauge-fg");
const progressStage = $("progress-stage");
const progressFill = $("progress-fill");
const progressMetaLeft = $("progress-meta-left");
const progressMetaRight = $("progress-meta-right");
const liveFeed = $("live-feed");
const claimList = $("claim-list");
const statVerified = $("stat-verified");
const statUnverified = $("stat-unverified");
const statHallucinated = $("stat-hallucinated");
const backendStatus = $("backend-status");
const backendLabel = $("backend-label");

/* ---------------- boot ---------------- */
document.addEventListener("DOMContentLoaded", () => {
  wireUp();
  checkBackend();
  loadSamples();
});

function wireUp() {
  $("btn-scan-page").addEventListener("click", onScanPage);
  $("btn-paste").addEventListener("click", () =>
    $("paste-wrap").classList.toggle("hidden")
  );
  $("btn-run-paste").addEventListener("click", onRunPaste);
  $("btn-reset").addEventListener("click", reset);
  $("btn-download-pdf").addEventListener("click", downloadPdf);
  $("btn-highlight-page").addEventListener("click", highlightOnPage);
  $("btn-open-viewer").addEventListener("click", openViewer);
  $("tab-claims").addEventListener("click", () => switchViewTab("claims"));
  $("tab-doc").addEventListener("click", () => switchViewTab("doc"));
  $("btn-error-dismiss").addEventListener("click", () => {
    errorPanel.classList.add("hidden");
    idlePanel.classList.remove("hidden");
  });

  // PDF drop zone wiring
  const dropZone = $("pdf-drop-zone");
  const fileInput = $("pdf-file-input");
  if (dropZone && fileInput) {
    dropZone.addEventListener("click", (e) => {
      if (!e.target.closest("label")) fileInput.click();
    });
    dropZone.addEventListener("dragover", (e) => {
      e.preventDefault();
      dropZone.classList.add("drag-over");
    });
    dropZone.addEventListener("dragleave", () => dropZone.classList.remove("drag-over"));
    dropZone.addEventListener("drop", (e) => {
      e.preventDefault();
      dropZone.classList.remove("drag-over");
      const file = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
      if (file) uploadPdfFile(file);
    });
    fileInput.addEventListener("change", () => {
      const file = fileInput.files && fileInput.files[0];
      if (file) uploadPdfFile(file);
      fileInput.value = "";
    });
  }
}

async function uploadPdfFile(file) {
  if (!file || !file.name.toLowerCase().endsWith(".pdf")) {
    return showError("Please select a valid PDF file.");
  }
  // Show uploading state
  const dropZone = $("pdf-drop-zone");
  const uploading = $("pdf-uploading");
  const uploadLabel = $("pdf-upload-label");
  if (dropZone) dropZone.classList.add("hidden");
  if (uploading) uploading.classList.remove("hidden");
  if (uploadLabel) uploadLabel.textContent = `Uploading ${file.name}...`;

  try {
    const formData = new FormData();
    formData.append("file", file);
    const r = await fetch(`${BACKEND}/api/audit/upload-pdf`, {
      method: "POST",
      body: formData,
    });
    const data = await r.json();
    if (!r.ok) {
      if (dropZone) dropZone.classList.remove("hidden");
      if (uploading) uploading.classList.add("hidden");
      return showError(data.detail || "Failed to process PDF.");
    }
    // Reset PDF zone visibility
    if (uploading) uploading.classList.add("hidden");
    if (dropZone) dropZone.classList.remove("hidden");
    // Begin audit flow (audit_id already created on backend)
    state.auditId = data.audit_id;
    clearPolling();
    idlePanel.classList.add("hidden");
    errorPanel.classList.add("hidden");
    resultsPanel.classList.add("hidden");
    progressPanel.classList.remove("hidden");
    liveFeed.innerHTML = "";
    claimList.innerHTML = "";
    setGauge(null);
    progressStage.textContent = `PDF loaded: ${file.name}`;
    progressFill.style.width = "5%";
    if (data.domain) setDomain({ domain: data.domain });
    if (data.total_claims != null)
      progressMetaLeft.textContent = `0 / ${data.total_claims} claims`;
    startPolling();
  } catch (err) {
    if (dropZone) dropZone.classList.remove("hidden");
    if (uploading) uploading.classList.add("hidden");
    showError("Could not reach backend. Make sure FastAPI is running on :8000.");
  }
}

chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === "VERIFAI_NEW_CAPTURE" && msg.text) {
    beginAudit(msg.text, `Page capture (${msg.source})`);
  }
  if (msg.type === "VERIFAI_FOCUS_CLAIM" && msg.claimId != null) {
    focusClaim(msg.claimId);
  }
});

/* ---------------- backend helpers ---------------- */
async function checkBackend() {
  try {
    const r = await fetch(`${BACKEND}/healthz`);
    if (r.ok) {
      backendStatus.classList.add("ok");
      backendLabel.textContent = "connected";
    } else throw new Error("bad");
  } catch {
    backendStatus.classList.add("err");
    backendLabel.textContent = "offline — start FastAPI on :8000";
  }
}

function send(type, extra) {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage({ type, ...(extra || {}) }, (r) => resolve(r));
  });
}

/* ---------------- samples ---------------- */
async function loadSamples() {
  try {
    const r = await fetch(`${BACKEND}/api/audit/samples/list`);
    if (!r.ok) return;
    const data = await r.json();
    renderSamples(data.samples || []);
  } catch {
    samplesList.innerHTML =
      '<div class="desc" style="padding:6px 2px">Start the backend to see sample documents.</div>';
  }
}

function renderSamples(samples) {
  samplesList.innerHTML = "";
  for (const s of samples) {
    const row = document.createElement("div");
    row.className = "sample-row";
    row.innerHTML = `
      <div>
        <div class="title">${escapeHtml(s.title)}</div>
        <div class="desc">${escapeHtml(s.description || "")}</div>
      </div>
      <span class="sample-chev">›</span>
    `;
    row.addEventListener("click", () => beginAudit(s.text, s.title));
    samplesList.appendChild(row);
  }
}

/* ---------------- capture flows ---------------- */
async function onScanPage() {
  try {
    // 1. Get the currently active tab in the browser window
    const tabs = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
    const tab = tabs && tabs[0];

    if (!tab || !tab.id) {
      return showError("No active webpage found. Please click into a webpage and try again.");
    }

    const url = tab.url || "";
    if (url.startsWith("chrome://") || url.startsWith("edge://") || url.startsWith("about:") || url.startsWith("chrome-extension://")) {
      return showError("Cannot scan browser settings or internal pages (like chrome://). Please open a regular webpage (like Wikipedia, an article, or ChatGPT) and click Scan again.");
    }

    // Detect PDF — use URL-based fetch bypass instead of DOM extraction
    const isPDF = url.toLowerCase().endsWith(".pdf") ||
      url.toLowerCase().includes(".pdf?") ||
      url.toLowerCase().includes(".pdf#") ||
      (tab.title || "").toLowerCase().endsWith(".pdf");

    if (isPDF) {
      return scanPdfFromUrl(url, tab.title || "PDF document");
    }

    // 2. Direct DOM extraction via executeScript (fastest, most reliable)
    let extractedText = "";
    try {
      const results = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: () => {
          const clean = (s) => (s || "").replace(/\u00a0/g, " ").replace(/\n{3,}/g, "\n\n").trim();

          // Check user selection first
          const sel = clean(window.getSelection ? window.getSelection().toString() : "");
          if (sel && sel.length >= 15) return sel;

          // Check for Chrome PDF viewer elements
          const pdfViewer = document.querySelector("pdf-viewer");
          if (pdfViewer && pdfViewer.shadowRoot) {
            const shadowText = clean(pdfViewer.shadowRoot.innerText || "");
            if (shadowText.length > 25) return shadowText;
          }
          const textLayers = document.querySelectorAll(".textLayer");
          if (textLayers.length > 0) {
            let pdfText = "";
            textLayers.forEach((tl) => { pdfText += " " + (tl.innerText || ""); });
            if (pdfText.trim().length > 25) return clean(pdfText);
          }

          // Check for AI Assistant response containers
          const aiSelectors = [
            '[data-message-author-role="assistant"]',
            'article[data-testid^="conversation-turn"]',
            ".agent-turn .markdown",
            "model-response",
            "message-content",
            ".model-response-text",
            '[data-testid="chat-message-text"]',
            '[data-testid="answer"]',
          ];
          for (const sel of aiSelectors) {
            const els = Array.from(document.querySelectorAll(sel));
            if (els.length > 0) {
              const last = clean(els[els.length - 1].innerText || "");
              if (last.length > 25) return last;
            }
          }

          // Next, check for main article containers
          const container = document.querySelector("article, main, [role='main'], #content, .content, .mw-parser-output, .entry-content, .post-content") || document.body;
          const paragraphs = Array.from(container.querySelectorAll("p, h1, h2, h3, li"))
            .map((el) => clean(el.innerText || ""))
            .filter((t) => t.length > 20);

          if (paragraphs.length > 0) {
            return paragraphs.join("\n\n");
          }

          // Fallback to body text
          return clean(document.body.innerText || "");
        },
      });

      if (results && results[0] && results[0].result) {
        extractedText = results[0].result.trim();
      }
    } catch (scriptErr) {
      console.warn("[VerifAI] direct scripting error, falling back to background:", scriptErr);
    }

    // 3. If direct extraction didn't get enough text, try background message bridge
    if (!extractedText || extractedText.length < 15) {
      const res = await send("VERIFAI_CAPTURE_SCAN_PAGE");
      if (res && res.ok && res.text) {
        extractedText = res.text.trim();
      } else if (!res || !res.ok) {
        if (isPDF) {
          return showError("Chrome's built-in PDF viewer sandboxes PDF files and prevents browser extensions from reading them automatically. Please copy the text from the PDF (Ctrl+C) and click 'Paste & Verify' in the sidebar!");
        }
        return showError(res?.error || "Could not extract text from this page. Try copying and pasting into 'Paste & Verify'.");
      }
    }

    if (!extractedText || extractedText.length < 15) {
      if (isPDF) {
        return showError("Chrome's built-in PDF viewer sandboxes PDF files and prevents browser extensions from reading them automatically. Please copy the text from the PDF (Ctrl+C) and click 'Paste & Verify' in the sidebar!");
      }
      return showError("Page text appears empty or could not be read. Try using 'Paste & Verify' instead.");
    }

    beginAudit(extractedText, tab.title || "Page capture");
  } catch (err) {
    console.error("[VerifAI] scan page error:", err);
    showError("Failed to scan page: " + (err.message || String(err)));
  }
}

/* ---------------- PDF URL scan (bypasses Chrome PDF viewer) ---------------- */
async function scanPdfFromUrl(pdfUrl, title) {
  // Show a progress state while the background fetches and uploads the PDF
  clearPolling();
  idlePanel.classList.add("hidden");
  errorPanel.classList.add("hidden");
  resultsPanel.classList.add("hidden");
  progressPanel.classList.remove("hidden");
  liveFeed.innerHTML = "";
  claimList.innerHTML = "";
  setGauge(null);
  progressStage.textContent = "Fetching PDF from page...";
  progressFill.style.width = "3%";

  const res = await send("VERIFAI_SCAN_PDF_URL", { url: pdfUrl, title });
  if (!res || !res.ok) {
    progressPanel.classList.add("hidden");
    idlePanel.classList.remove("hidden");
    return showError(res?.error || "Could not read PDF. Make sure the backend is running and the PDF is accessible.");
  }

  // Backend already created an audit — set audit_id and start polling
  state.auditId = res.auditId;
  progressStage.textContent = `PDF loaded: ${title}`;
  progressFill.style.width = "8%";
  if (res.domain) setDomain({ domain: res.domain });
  if (res.totalClaims != null)
    progressMetaLeft.textContent = `0 / ${res.totalClaims} claims`;
  startPolling();
}

function onRunPaste() {
  const text = ($("paste-area").value || "").trim();
  if (!text) return;
  beginAudit(text, "Pasted text");
}

/* ---------------- audit lifecycle ---------------- */
async function beginAudit(text, title) {
  clearPolling();
  idlePanel.classList.add("hidden");
  errorPanel.classList.add("hidden");
  resultsPanel.classList.add("hidden");
  progressPanel.classList.remove("hidden");
  liveFeed.innerHTML = "";
  claimList.innerHTML = "";
  setGauge(null);
  progressStage.textContent = "Submitting document...";
  progressFill.style.width = "2%";

  const res = await send("VERIFAI_START_AUDIT", { text, title });
  if (!res.ok)
    return showError(
      res.error || res.data?.detail || "Backend rejected the document."
    );

  state.auditId = res.data.audit_id;
  if (res.data.domain) setDomain(res.data.domain);
  if (res.data.total_claims != null)
    progressMetaLeft.textContent = `0 / ${res.data.total_claims} claims`;
  startPolling();
}

function startPolling() {
  if (!state.auditId) return;
  pollOnce();
  state.pollTimer = setInterval(pollOnce, POLL_INTERVAL_MS);
}

function clearPolling() {
  if (state.pollTimer) {
    clearInterval(state.pollTimer);
    state.pollTimer = null;
  }
}

async function pollOnce() {
  if (!state.auditId) return;
  const res = await send("VERIFAI_POLL_STATUS", { auditId: state.auditId });
  if (!res.ok) return;
  const data = res.data || {};
  applyStatus(data);
  if (data.status === "complete") {
    clearPolling();
    const r = await send("VERIFAI_GET_RESULTS", { auditId: state.auditId });
    if (r.ok) showResults(r.data);
  } else if (data.status === "error") {
    clearPolling();
    showError(data.error_message || "Audit failed on the backend.");
  }
}

function applyStatus(data) {
  progressStage.textContent = data.stage || "Working...";
  progressFill.style.width = `${data.progress_percent || 0}%`;
  progressMetaRight.textContent = `${data.progress_percent || 0}%`;
  progressMetaLeft.textContent = `${data.claims_processed || 0} / ${
    data.total_claims || 0
  } claims`;
  if (data.domain) setDomain(data.domain);
  renderLiveFeed(data.partial_claims || []);
}

function renderLiveFeed(partial) {
  liveFeed.innerHTML = "";
  for (const cv of partial) {
    const row = document.createElement("div");
    row.className = `feed-row verdict-${cv.verdict}`;
    const snip = escapeHtml((cv.claim.claim_text || "").slice(0, 120));
    row.innerHTML = `
      <div class="claim-snip">${snip}</div>
      <span class="mini-badge ${cv.verdict}">${cv.verdict}</span>
    `;
    liveFeed.appendChild(row);
  }
}

/* ---------------- results ---------------- */
function showResults(data) {
  state.currentResult = data;
  progressPanel.classList.add("hidden");
  resultsPanel.classList.remove("hidden");

  const ts = data.trust_score || {};
  setGauge(ts);
  if (data.domain) setDomain(data.domain);

  statVerified.textContent = ts.verified_count ?? 0;
  statUnverified.textContent = ts.unverified_count ?? 0;
  statHallucinated.textContent = ts.hallucinated_count ?? 0;

  // Executive summary
  const summaryEl = $("exec-summary");
  if (summaryEl) {
    const claims = data.claims || [];
    const hall = claims.filter(c => c.verdict === "HALLUCINATED");
    const ver = claims.filter(c => c.verdict === "VERIFIED");
    const unv = claims.filter(c => c.verdict === "UNVERIFIED");
    let summaryText = `Analyzed ${claims.length} factual claim${claims.length !== 1 ? "s" : ""}.`;
    if (hall.length > 0) {
      const worst = hall[0];
      summaryText += ` Found ${hall.length} hallucination${hall.length !== 1 ? "s" : ""}.`;
      summaryText += ` Key issue: "${escapeHtml((worst.claim.claim_text || "").slice(0, 90))}"`;
    } else if (ver.length === claims.length) {
      summaryText += " All claims verified — document appears trustworthy.";
    } else {
      summaryText += ` ${unv.length} claim${unv.length !== 1 ? "s" : ""} could not be fully verified.`;
    }
    summaryEl.innerHTML = summaryText;
    summaryEl.classList.remove("hidden");
  }

  // Show correct information panel if available
  const correctPanel = $("correct-info-panel");
  const correctBody = $("correct-info-body");
  if (correctPanel && correctBody && data.correct_information) {
    correctPanel.classList.remove("hidden");
    correctBody.innerHTML = escapeHtml(data.correct_information).replace(/\n/g, "<br>");
  } else if (correctPanel) {
    correctPanel.classList.add("hidden");
  }

  const claims = data.claims || [];
  const claimsCountEl = $("tab-claims-count");
  if (claimsCountEl) claimsCountEl.textContent = claims.length;

  renderClaims(claims);
  renderDocHighlightView(data.document_text || "", claims);
  switchViewTab("claims");
  highlightOnPage();
}

function renderClaims(claims) {
  claimList.innerHTML = "";
  const ordered = [...claims].sort((a, b) => {
    const order = { HALLUCINATED: 0, UNVERIFIED: 1, VERIFIED: 2 };
    return (
      (order[a.verdict] ?? 3) - (order[b.verdict] ?? 3) ||
      a.claim.id - b.claim.id
    );
  });
  for (const cv of ordered) {
    claimList.appendChild(buildClaimCard(cv));
  }
}

function buildClaimCard(cv) {
  const card = document.createElement("div");
  card.className = `claim-card verdict-${cv.verdict}`;
  if (cv.claim.high_stakes) card.classList.add("high-stakes");
  card.dataset.claimId = cv.claim.id;

  const hsChip = cv.claim.high_stakes
    ? '<span class="hs-chip">⚠ HIGH STAKES</span>'
    : "";

  // Color-coded confidence
  const confColor = cv.confidence >= 80 ? "var(--verified)" : cv.confidence >= 50 ? "var(--unverified)" : "var(--hallucinated)";

  // Source link visible directly on the card
  let sourceLink = "";
  if (cv.best_source_url) {
    const label = escapeHtml(cv.best_source_label || "Source");
    sourceLink = `<a href="${escapeAttr(cv.best_source_url)}" target="_blank" rel="noreferrer" class="claim-source-link" onclick="event.stopPropagation()">🔗 ${label}</a>`;
  } else if (cv.sources && cv.sources.length > 0) {
    const s = cv.sources[0];
    const label = escapeHtml(s.title || "Source");
    sourceLink = `<a href="${escapeAttr(s.url)}" target="_blank" rel="noreferrer" class="claim-source-link" onclick="event.stopPropagation()">🔗 ${label}</a>`;
  }

  // Contradicting snippet shown directly for hallucinated claims
  let contraSnip = "";
  if (cv.verdict === "HALLUCINATED" && cv.contradicting_detail) {
    contraSnip = `<div class="claim-contra">❌ ${escapeHtml(cv.contradicting_detail)}</div>`;
  }

  card.innerHTML = `
    <div class="claim-head">
      <span class="badge ${cv.verdict}">${cv.verdict}</span>
      <span class="conf" style="color:${confColor}">${cv.confidence}%</span>
      ${hsChip}
    </div>
    <div class="claim-body">${escapeHtml(cv.claim.claim_text)}</div>
    ${contraSnip}
    ${sourceLink}
    <div class="claim-details"></div>
  `;

  const details = card.querySelector(".claim-details");
  details.appendChild(buildDetails(cv));

  card.addEventListener("click", () => card.classList.toggle("expanded"));
  return card;
}

function buildDetails(cv) {
  const frag = document.createDocumentFragment();

  frag.appendChild(
    row("Reasoning", escapeHtml(cv.reasoning || "No reasoning returned."))
  );

  if (cv.contradicting_detail) {
    frag.appendChild(
      row(
        "Contradicted by evidence",
        `<span style="color:#fca5a5">${escapeHtml(
          cv.contradicting_detail
        )}</span>`
      )
    );
  }

  if (cv.sources && cv.sources.length) {
    const wrap = document.createElement("div");
    wrap.className = "source-list";
    for (const s of cv.sources.slice(0, 3)) {
      const item = document.createElement("div");
      item.className = `source-item tier-${s.source_tier}`;
      item.innerHTML = `
        <a href="${escapeAttr(s.url)}" target="_blank" rel="noreferrer">${escapeHtml(
        s.title || s.url
      )}</a>
        <div class="snippet">"${escapeHtml((s.snippet || "").slice(0, 200))}"</div>
      `;
      wrap.appendChild(item);
    }
    const r = document.createElement("div");
    r.className = "row";
    const lbl = document.createElement("div");
    lbl.className = "row-label";
    lbl.textContent = "Sources";
    r.appendChild(lbl);
    r.appendChild(wrap);
    frag.appendChild(r);
  }

  if (cv.genealogy) {
    const g = document.createElement("div");
    g.className = "genealogy-block";
    g.innerHTML = `
      <div class="g-type">🧬 Hallucination genealogy — ${escapeHtml(
        cv.genealogy.genealogy_type.replace(/_/g, " ")
      )}</div>
      <div class="g-row"><b>Real fact:</b> ${escapeHtml(
        cv.genealogy.real_fact
      )}</div>
      <div class="g-row"><b>How the AI went wrong:</b> ${escapeHtml(
        cv.genealogy.mutation_explanation
      )}</div>
      <div class="g-row"><b>Analyst confidence:</b> ${
        cv.genealogy.confidence_in_genealogy
      }%</div>
    `;
    frag.appendChild(g);
  }

  return frag;
}

function row(label, htmlContent) {
  const r = document.createElement("div");
  r.className = "row";
  r.innerHTML = `<div class="row-label">${escapeHtml(
    label
  )}</div><div>${htmlContent}</div>`;
  return r;
}

/* ---------------- gauge ---------------- */
const GAUGE_CIRCUMFERENCE = 251.3; // approx of Math.PI * 80 (half circle at r=80)

function setGauge(ts) {
  if (!ts) {
    gaugeScore.textContent = "—";
    gaugeBand.textContent = "Awaiting audit";
    gaugeFg.setAttribute("stroke-dashoffset", GAUGE_CIRCUMFERENCE);
    gaugeFg.setAttribute("stroke", "#3b82f6");
    return;
  }
  const score = Math.max(0, Math.min(100, ts.score || 0));
  const offset = GAUGE_CIRCUMFERENCE * (1 - score / 100);
  gaugeScore.textContent = score.toFixed(0);
  gaugeBand.textContent = ts.band || "—";
  gaugeFg.setAttribute("stroke-dashoffset", offset.toString());
  gaugeFg.setAttribute("stroke", ts.color || "#3b82f6");
}

/* ---------------- domain pill ---------------- */
function setDomain(d) {
  const dom = d.domain || "general";
  const label = DOMAIN_LABELS[dom] || "General Mode";
  domainPill.classList.remove("hidden");
  domainPillLabel.textContent = label;
  domainPill.style.borderColor = hexWithAlpha(DOMAIN_COLORS[dom], 0.4);
  domainPill.style.background = hexWithAlpha(DOMAIN_COLORS[dom], 0.12);
  domainPill.style.color = DOMAIN_COLORS[dom];
  domainPill.querySelector(".dot").style.background = DOMAIN_COLORS[dom];
}

function hexWithAlpha(hex, a) {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
  return `rgba(${r}, ${g}, ${b}, ${a})`;
}

/* ---------------- misc actions ---------------- */
function downloadPdf() {
  if (!state.auditId) return;
  send("VERIFAI_OPEN_PDF", { auditId: state.auditId });
}

function openViewer() {
  if (!state.auditId) return;
  const url = chrome.runtime.getURL(`viewer.html?auditId=${encodeURIComponent(state.auditId)}`);
  chrome.tabs.create({ url });
}

function switchViewTab(tabName) {
  const tabClaims = $("tab-claims");
  const tabDoc = $("tab-doc");
  const claimListEl = $("claim-list");
  const docViewEl = $("doc-highlight-view");

  if (tabName === "doc") {
    tabDoc?.classList.add("active");
    tabClaims?.classList.remove("active");
    claimListEl?.classList.add("hidden");
    docViewEl?.classList.remove("hidden");
  } else {
    tabClaims?.classList.add("active");
    tabDoc?.classList.remove("active");
    claimListEl?.classList.remove("hidden");
    docViewEl?.classList.add("hidden");
  }
}

function renderDocHighlightView(rawText, claims) {
  const docViewEl = $("doc-highlight-view");
  if (!docViewEl) return;

  if (!rawText) {
    docViewEl.innerHTML = '<div style="color:var(--text-dim);text-align:center;padding:20px;">No document text captured.</div>';
    return;
  }

  // Sort claims by sentence length descending
  const sorted = [...claims].sort((a, b) => {
    const lenA = (a.claim?.source_sentence || a.claim?.claim_text || "").length;
    const lenB = (b.claim?.source_sentence || b.claim?.claim_text || "").length;
    return lenB - lenA;
  });

  const matches = [];
  for (const cv of sorted) {
    const needle = (cv.claim?.source_sentence || cv.claim?.claim_text || "").trim();
    if (!needle || needle.length < 8) continue;
    let idx = rawText.indexOf(needle);
    if (idx !== -1) {
      matches.push({ start: idx, end: idx + needle.length, cv });
    }
  }

  matches.sort((a, b) => a.start - b.start);
  const nonOverlapping = [];
  let lastEnd = 0;
  for (const m of matches) {
    if (m.start >= lastEnd) {
      nonOverlapping.push(m);
      lastEnd = m.end;
    }
  }

  let out = "";
  let cursor = 0;
  for (const m of nonOverlapping) {
    if (m.start > cursor) {
      out += escapeHtml(rawText.slice(cursor, m.start));
    }
    const cv = m.cv;
    const v = cv.verdict || "UNVERIFIED";
    const icon = v === "HALLUCINATED" ? "⚠" : v === "VERIFIED" ? "✓" : "?";
    const snip = escapeHtml(rawText.slice(m.start, m.end));
    out += `<span class="doc-hl doc-hl-${v}" data-claim-id="${cv.claim?.id}" title="${v} (${cv.confidence}%)"><span class="doc-hl-badge doc-hl-${v}">${icon} ${v}</span>${snip}</span>`;
    cursor = m.end;
  }
  if (cursor < rawText.length) {
    out += escapeHtml(rawText.slice(cursor));
  }

  docViewEl.innerHTML = out;

  docViewEl.querySelectorAll(".doc-hl").forEach(span => {
    span.addEventListener("click", () => {
      const id = span.getAttribute("data-claim-id");
      switchViewTab("claims");
      focusClaim(id);
    });
  });
}

async function highlightOnPage() {
  if (!state.currentResult) return;
  const btn = $("btn-highlight-page");
  const origText = btn ? btn.textContent : "";
  if (btn) btn.textContent = "Highlighting...";
  const res = await send("VERIFAI_APPLY_HIGHLIGHTS", {
    claims: state.currentResult.claims || [],
  });
  if (btn) {
    btn.textContent = (res && res.count > 0) ? `✓ Highlighted (${res.count})` : "✓ Highlighted";
    setTimeout(() => {
      if (btn) btn.textContent = origText || "Highlight On Page";
    }, 2200);
  }
}

function reset() {
  clearPolling();
  send("VERIFAI_APPLY_HIGHLIGHTS", { claims: [] });
  state.auditId = null;
  state.currentResult = null;
  resultsPanel.classList.add("hidden");
  progressPanel.classList.add("hidden");
  errorPanel.classList.add("hidden");
  idlePanel.classList.remove("hidden");
  setGauge(null);
  domainPill.classList.add("hidden");
  const sum = $("exec-summary");
  if (sum) sum.classList.add("hidden");
}

function focusClaim(claimId) {
  const el = claimList.querySelector(`.claim-card[data-claim-id="${claimId}"]`);
  if (!el) return;
  el.classList.add("expanded");
  el.scrollIntoView({ behavior: "smooth", block: "center" });
  el.animate(
    [
      { boxShadow: "0 0 0 0 rgba(59,130,246,0.7)" },
      { boxShadow: "0 0 0 8px rgba(59,130,246,0)" },
    ],
    { duration: 900, easing: "ease-out" }
  );
}

function showError(message) {
  clearPolling();
  progressPanel.classList.add("hidden");
  resultsPanel.classList.add("hidden");
  idlePanel.classList.add("hidden");
  errorPanel.classList.remove("hidden");
  $("error-body").textContent =
    message || "Unknown error. Check that the backend is running.";
}

/* ---------------- utils ---------------- */
function escapeHtml(s) {
  return (s || "")
    .toString()
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function escapeAttr(s) {
  return escapeHtml(s);
}
