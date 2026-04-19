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
  $("btn-error-dismiss").addEventListener("click", () => {
    errorPanel.classList.add("hidden");
    idlePanel.classList.remove("hidden");
  });
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
  const res = await send("VERIFAI_CAPTURE_SCAN_PAGE");
  if (!res || !res.ok)
    return showError(res?.error || "Failed to capture the page.");
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

  renderClaims(data.claims || []);
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

async function highlightOnPage() {
  if (!state.currentResult) return;
  await send("VERIFAI_APPLY_HIGHLIGHTS", {
    claims: state.currentResult.claims || [],
  });
}

function reset() {
  clearPolling();
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
