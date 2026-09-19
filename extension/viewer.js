/* VerifAI Full Highlighted Document Reader */
(async function () {
  const BACKEND = "http://127.0.0.1:8000";
  const params = new URLSearchParams(window.location.search);
  const auditId = params.get("auditId") || params.get("id");

  const docTitleEl = document.getElementById("doc-title");
  const docContentEl = document.getElementById("doc-content");
  const gaugeScoreEl = document.getElementById("gauge-score");
  const gaugeBandEl = document.getElementById("gauge-band");
  const gaugeStatsEl = document.getElementById("gauge-stats");
  const execSummaryEl = document.getElementById("exec-summary");
  const inspectorClaimsEl = document.getElementById("inspector-claims");
  const domainPillEl = document.getElementById("domain-pill");
  const domainLabelEl = document.getElementById("domain-label");
  const btnDownloadPdf = document.getElementById("btn-download-pdf");

  if (!auditId) {
    docContentEl.innerHTML = '<div class="loading-state">No audit ID provided. Please run an audit from the VerifAI extension.</div>';
    return;
  }

  btnDownloadPdf.addEventListener("click", () => {
    window.open(`${BACKEND}/api/audit/${auditId}/report.pdf`, "_blank");
  });

  try {
    const res = await fetch(`${BACKEND}/api/audit/${auditId}/results`);
    if (!res.ok) throw new Error("Could not fetch audit results from backend.");
    const data = await res.json();
    renderDocument(data);
  } catch (err) {
    docContentEl.innerHTML = `<div class="loading-state" style="color:#ef4444">Error loading audit: ${escapeHtml(err.message)}</div>`;
  }

  function renderDocument(data) {
    const docText = data.document_text || "";
    const claims = data.claims || [];
    const ts = data.trust_score || {};
    const domain = data.domain || {};

    docTitleEl.textContent = data.document_title || "Audited Document";
    if (domain.domain) {
      domainPillEl.classList.remove("hidden");
      domainLabelEl.textContent = domain.domain.toUpperCase();
    }

    gaugeScoreEl.textContent = ts.score !== undefined ? `${ts.score}` : "--";
    gaugeScoreEl.style.color = ts.color || "#3b82f6";
    gaugeBandEl.textContent = ts.band || "Unknown";
    gaugeStatsEl.textContent = `${ts.verified_count || 0} verified · ${ts.unverified_count || 0} unverified · ${ts.hallucinated_count || 0} hallucinated`;

    // Executive summary
    const hall = claims.filter(c => c.verdict === "HALLUCINATED");
    let summaryText = `Analyzed ${claims.length} claim${claims.length !== 1 ? "s" : ""}.`;
    if (hall.length > 0) {
      summaryText += ` Identified ${hall.length} hallucination${hall.length !== 1 ? "s" : ""}.`;
    } else {
      summaryText += " All claims verified accurately.";
    }
    execSummaryEl.textContent = summaryText;

    // Render Highlighted Text
    renderHighlightedContent(docText, claims);

    // Render Inspector Cards
    renderInspectorCards(claims);
  }

  function renderHighlightedContent(rawText, claims) {
    if (!rawText) {
      docContentEl.innerHTML = '<div class="loading-state">No text found for this document.</div>';
      return;
    }

    // Sort claims by sentence length descending so longer sentences match first
    const sorted = [...claims].sort((a, b) => {
      const lenA = (a.claim?.source_sentence || a.claim?.claim_text || "").length;
      const lenB = (b.claim?.source_sentence || b.claim?.claim_text || "").length;
      return lenB - lenA;
    });

    // Build segment matches
    const matches = [];
    for (const cv of sorted) {
      const needle = (cv.claim?.source_sentence || cv.claim?.claim_text || "").trim();
      if (!needle || needle.length < 8) continue;

      let idx = rawText.indexOf(needle);
      if (idx !== -1) {
        matches.push({
          start: idx,
          end: idx + needle.length,
          cv,
        });
      }
    }

    // Sort matches by start position
    matches.sort((a, b) => a.start - b.start);

    // Filter overlapping matches
    const nonOverlapping = [];
    let lastEnd = 0;
    for (const m of matches) {
      if (m.start >= lastEnd) {
        nonOverlapping.push(m);
        lastEnd = m.end;
      }
    }

    // Build HTML with highlight spans
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
      out += `<span class="doc-hl doc-hl-${v}" data-claim-id="${cv.claim?.id}" title="${v} (${cv.confidence}%)"><span class="doc-hl-icon">${icon}</span>${snip}</span>`;
      cursor = m.end;
    }
    if (cursor < rawText.length) {
      out += escapeHtml(rawText.slice(cursor));
    }

    docContentEl.innerHTML = out;

    // Attach click listeners to highlights to focus inspector card
    docContentEl.querySelectorAll(".doc-hl").forEach(span => {
      span.addEventListener("click", () => {
        const id = span.getAttribute("data-claim-id");
        focusClaim(id);
      });
    });
  }

  function renderInspectorCards(claims) {
    inspectorClaimsEl.innerHTML = "";
    const ordered = [...claims].sort((a, b) => {
      const order = { HALLUCINATED: 0, UNVERIFIED: 1, VERIFIED: 2 };
      return (order[a.verdict] ?? 3) - (order[b.verdict] ?? 3) || (a.claim?.id - b.claim?.id);
    });

    for (const cv of ordered) {
      const card = document.createElement("div");
      card.className = "inspector-card";
      card.setAttribute("data-claim-id", cv.claim?.id);

      let contraHtml = "";
      if (cv.verdict === "HALLUCINATED" && cv.contradicting_detail) {
        contraHtml = `<div class="card-contra">❌ <strong>Contradiction:</strong> ${escapeHtml(cv.contradicting_detail)}</div>`;
      }

      let sourceHtml = "";
      if (cv.best_source_url) {
        sourceHtml = `<a href="${escapeAttr(cv.best_source_url)}" target="_blank" rel="noreferrer" class="card-source">🔗 ${escapeHtml(cv.best_source_label || "Source Evidence")}</a>`;
      }

      card.innerHTML = `
        <div class="card-head">
          <span class="verdict-badge ${cv.verdict}">${cv.verdict}</span>
          <span class="card-conf">${cv.confidence}% confidence</span>
        </div>
        <div class="card-claim-text">${escapeHtml(cv.claim?.claim_text || "")}</div>
        ${contraHtml}
        <div class="card-reasoning">${escapeHtml(cv.reasoning || "")}</div>
        ${sourceHtml}
      `;

      card.addEventListener("click", () => {
        focusClaim(cv.claim?.id);
      });

      inspectorClaimsEl.appendChild(card);
    }
  }

  function focusClaim(claimId) {
    if (!claimId) return;

    // Highlight in inspector list
    inspectorClaimsEl.querySelectorAll(".inspector-card").forEach(c => {
      c.classList.toggle("active-card", c.getAttribute("data-claim-id") === String(claimId));
    });
    const targetCard = inspectorClaimsEl.querySelector(`.inspector-card[data-claim-id="${claimId}"]`);
    if (targetCard) {
      targetCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    // Highlight in document pane
    docContentEl.querySelectorAll(".doc-hl").forEach(s => {
      const isMatch = s.getAttribute("data-claim-id") === String(claimId);
      s.classList.toggle("active-focus", isMatch);
      if (isMatch) {
        s.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    });
  }

  function escapeHtml(s) {
    return (s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function escapeAttr(s) {
    return escapeHtml(s).replace(/"/g, "&quot;");
  }
})();
