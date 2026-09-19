/* VerifAI Interactive In-Page PDF Viewer & Direct Highlighter */
(async function () {
  const BACKEND = "http://127.0.0.1:8000";

  // Setup PDF.js worker
  if (window.pdfjsLib) {
    pdfjsLib.GlobalWorkerOptions.workerSrc = chrome.runtime.getURL("pdf.worker.min.js");
  }

  const params = new URLSearchParams(window.location.search);
  const auditId = params.get("auditId") || params.get("id");
  const directPdfUrl = params.get("pdfUrl");

  const docTitleEl = document.getElementById("doc-title");
  const docSubtitleEl = document.getElementById("doc-subtitle");
  const pageNumInput = document.getElementById("page-num");
  const pageCountSpan = document.getElementById("page-count");
  const zoomLevelSpan = document.getElementById("zoom-level");
  const trustPillEl = document.getElementById("trust-pill");
  const trustScoreNumEl = document.getElementById("trust-score-num");
  const trustBandEl = document.getElementById("trust-band");
  const countHallEl = document.getElementById("count-hall");
  const countVerEl = document.getElementById("count-ver");
  const pdfPagesContainer = document.getElementById("pdf-pages");
  const pdfLoadingEl = document.getElementById("pdf-loading");
  const loadingMsgEl = document.getElementById("loading-msg");

  let pdfDoc = null;
  let auditData = null;
  let currentScale = 1.25;
  let activeFilter = "all";

  // Hover tooltip singleton
  let tooltipEl = null;
  let tooltipHideTimer = null;

  initButtons();

  if (!auditId && !directPdfUrl) {
    showError("No PDF or Audit ID provided. Please scan a PDF from the VerifAI extension.");
    return;
  }

  try {
    // 1. Fetch Audit Data if auditId is provided
    if (auditId) {
      const res = await fetch(`${BACKEND}/api/audit/${auditId}/results`);
      if (res.ok) {
        auditData = await res.json();
        updateAuditHeader(auditData);
      }
    }

    // 2. Load PDF Document
    let pdfSource = null;

    // Check if raw bytes were stored in local storage for this audit
    const stored = await chrome.storage.local.get([`pdf_bytes_${auditId}`, "last_pdf_bytes"]);
    const bytesBase64 = stored[`pdf_bytes_${auditId}`] || stored["last_pdf_bytes"];

    if (bytesBase64) {
      const binaryString = atob(bytesBase64);
      const len = binaryString.length;
      const bytes = new Uint8Array(len);
      for (let i = 0; i < len; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }
      pdfSource = { data: bytes };
    } else if (directPdfUrl) {
      pdfSource = { url: directPdfUrl };
    } else if (auditData && auditData.document_title && auditData.document_title.endsWith(".pdf")) {
      // Direct sample / uploaded PDF
      pdfSource = { url: `${BACKEND}/api/audit/samples/${auditId}/pdf` };
    }

    if (!pdfSource) {
      // If we don't have raw PDF binary, render an interactive HTML page layout
      renderHtmlFallback(auditData);
      return;
    }

    loadingMsgEl.textContent = "Parsing PDF pages and extracting text layers...";
    pdfDoc = await pdfjsLib.getDocument(pdfSource).promise;
    pageCountSpan.textContent = pdfDoc.numPages;
    docTitleEl.textContent = auditData?.document_title || "PDF Document";

    await renderAllPages();
    pdfLoadingEl.classList.add("hidden");
  } catch (err) {
    console.warn("[VerifAI PDF Viewer] loading fallback:", err);
    if (auditData) {
      renderHtmlFallback(auditData);
    } else {
      showError("Could not render PDF: " + err.message);
    }
  }

  function updateAuditHeader(data) {
    const ts = data.trust_score || {};
    const claims = data.claims || [];
    docTitleEl.textContent = data.document_title || "Audited PDF Document";
    docSubtitleEl.textContent = `Score: ${ts.score ?? "--"}/100 · ${claims.length} claims audited`;

    if (ts.score !== undefined) {
      trustPillEl.classList.remove("hidden");
      trustScoreNumEl.textContent = ts.score;
      trustBandEl.textContent = ts.band || "Audited";
    }

    const hall = claims.filter(c => c.verdict === "HALLUCINATED");
    const ver = claims.filter(c => c.verdict === "VERIFIED");
    countHallEl.textContent = hall.length;
    countVerEl.textContent = ver.length;
  }

  async function renderAllPages() {
    pdfPagesContainer.innerHTML = "";
    for (let pageNum = 1; pageNum <= pdfDoc.numPages; pageNum++) {
      await renderPage(pageNum);
    }
    applyHighlightsToAllPages();
  }

  async function renderPage(pageNum) {
    const page = await pdfDoc.getPage(pageNum);
    const viewport = page.getViewport({ scale: currentScale });

    const wrapper = document.createElement("div");
    wrapper.className = "pdf-page-wrapper";
    wrapper.id = `pdf-page-${pageNum}`;
    wrapper.style.width = `${viewport.width}px`;
    wrapper.style.height = `${viewport.height}px`;

    // Canvas
    const canvas = document.createElement("canvas");
    canvas.className = "page-canvas";
    canvas.width = viewport.width;
    canvas.height = viewport.height;
    const ctx = canvas.getContext("2d");
    wrapper.appendChild(canvas);

    // TextLayer
    const textLayerDiv = document.createElement("div");
    textLayerDiv.className = "textLayer";
    textLayerDiv.style.width = `${viewport.width}px`;
    textLayerDiv.style.height = `${viewport.height}px`;
    wrapper.appendChild(textLayerDiv);

    pdfPagesContainer.appendChild(wrapper);

    // Render Canvas
    await page.render({ canvasContext: ctx, viewport }).promise;

    // Render Text Layer
    const textContent = await page.getTextContent();
    for (const item of textContent.items) {
      if (!item.str) continue;
      const tx = pdfjsLib.Util.transform(viewport.transform, item.transform);
      const fontHeight = Math.sqrt(tx[2] * tx[2] + tx[3] * tx[3]);

      const span = document.createElement("span");
      span.textContent = item.str;
      span.style.fontSize = `${fontHeight}px`;
      span.style.fontFamily = item.fontName || "sans-serif";
      span.style.left = `${tx[4]}px`;
      span.style.top = `${tx[5] - fontHeight}px`;
      span.style.height = `${fontHeight * 1.15}px`;
      span.style.display = "inline-block";
      span.style.boxSizing = "border-box";
      if (item.width) {
        span.style.width = `${item.width * currentScale}px`;
      }
      textLayerDiv.appendChild(span);
    }
  }

  function applyHighlightsToAllPages() {
    if (!auditData || !auditData.claims) return;
    const claims = auditData.claims;

    // Prioritize hallucinations and longer sentences
    const sorted = [...claims].sort((a, b) => {
      const vScore = { HALLUCINATED: 3, UNVERIFIED: 2, VERIFIED: 1 };
      const diff = (vScore[b.verdict] || 0) - (vScore[a.verdict] || 0);
      if (diff !== 0) return diff;
      const lenA = (a.claim?.source_sentence || a.claim?.claim_text || "").length;
      const lenB = (b.claim?.source_sentence || b.claim?.claim_text || "").length;
      return lenB - lenA;
    });

    const textLayers = document.querySelectorAll(".textLayer");
    for (const layer of textLayers) {
      const spans = Array.from(layer.querySelectorAll("span"));
      if (spans.length === 0) continue;

      let combined = "";
      const map = [];
      for (const span of spans) {
        const start = combined.length;
        combined += span.textContent + " ";
        map.push({ span, start, end: combined.length });
      }

      for (const cv of sorted) {
        const candidates = [];
        const src = (cv.claim?.source_sentence || "").trim();
        const txt = (cv.claim?.claim_text || "").trim();
        if (src && src.length >= 8) candidates.push(src);
        if (txt && txt.length >= 8 && txt !== src) candidates.push(txt);

        if (src && src.length > 35) {
          const words = src.split(/\s+/);
          if (words.length >= 6) {
            candidates.push(words.slice(0, 7).join(" "));
            candidates.push(words.slice(-6).join(" "));
          }
        }

        let claimMatched = false;
        for (const needle of candidates) {
          const normCombined = combined.toLowerCase().replace(/[\u2018\u2019]/g, "'").replace(/[\u201C\u201D]/g, '"').replace(/\s+/g, " ");
          const normNeedle = needle.toLowerCase().replace(/[\u2018\u2019]/g, "'").replace(/[\u201C\u201D]/g, '"').replace(/\s+/g, " ");

          let matchIdx = normCombined.indexOf(normNeedle);
          if (matchIdx !== -1) {
            const matchEnd = matchIdx + normNeedle.length;
            for (const item of map) {
              if (item.end > matchIdx && item.start < matchEnd) {
                const v = cv.verdict || "UNVERIFIED";
                item.span.classList.add("verifai-hl", `verifai-hl-${v.toLowerCase()}`);
                item.span.setAttribute("data-verdict", v);
                item.span.setAttribute("data-claim-id", cv.claim?.id);

                item.span.addEventListener("mouseenter", (e) => showTooltip(e.target, cv));
                item.span.addEventListener("mouseleave", () => hideTooltip());
              }
            }
            claimMatched = true;
            break;
          }
        }
      }
    }
  }

  function showTooltip(target, claim) {
    clearTimeout(tooltipHideTimer);
    if (!tooltipEl) {
      tooltipEl = document.createElement("div");
      tooltipEl.id = "verifai-inpage-tooltip";
      document.body.appendChild(tooltipEl);
    }

    const v = claim.verdict || "UNVERIFIED";
    const icon = v === "HALLUCINATED" ? "⚠" : v === "VERIFIED" ? "✓" : "?";
    let contraHtml = "";
    if (v === "HALLUCINATED" && claim.contradicting_detail) {
      contraHtml = `<div class="verifai-tt-contra"><strong>Contradiction:</strong> ${escapeHtml(claim.contradicting_detail)}</div>`;
    }

    tooltipEl.innerHTML = `
      <div class="verifai-tt-head">
        <span class="verifai-tt-badge ${v}">${icon} ${v}</span>
        <span class="verifai-tt-conf">${claim.confidence}% confidence</span>
      </div>
      <div class="verifai-tt-body"><strong>Claim:</strong> ${escapeHtml(claim.claim?.claim_text || "")}</div>
      ${contraHtml}
      <div class="verifai-tt-body" style="font-size:11px;color:#94a3b8">${escapeHtml((claim.reasoning || "").slice(0, 150))}</div>
    `;

    tooltipEl.classList.add("verifai-tooltip-visible");

    const rect = target.getBoundingClientRect();
    const ttRect = tooltipEl.getBoundingClientRect();
    let top = window.scrollY + rect.top - ttRect.height - 8;
    if (top < window.scrollY + 10) {
      top = window.scrollY + rect.bottom + 8;
    }
    let left = window.scrollX + rect.left + (rect.width / 2) - (ttRect.width / 2);
    if (left < 10) left = 10;
    if (left + ttRect.width > window.innerWidth - 10) {
      left = window.innerWidth - ttRect.width - 10;
    }

    tooltipEl.style.top = `${top}px`;
    tooltipEl.style.left = `${left}px`;
  }

  function hideTooltip() {
    clearTimeout(tooltipHideTimer);
    tooltipHideTimer = setTimeout(() => {
      if (tooltipEl) tooltipEl.classList.remove("verifai-tooltip-visible");
    }, 150);
  }

  function renderHtmlFallback(data) {
    pdfLoadingEl.classList.add("hidden");
    const rawText = data?.document_text || "";
    const claims = data?.claims || [];

    const pageWrapper = document.createElement("div");
    pageWrapper.className = "pdf-page-wrapper";
    pageWrapper.style.padding = "40px 50px";
    pageWrapper.style.width = "820px";
    pageWrapper.style.minHeight = "1050px";
    pageWrapper.style.color = "#0f172a";
    pageWrapper.style.fontSize = "15px";
    pageWrapper.style.lineHeight = "1.8";

    // Build highlighted HTML
    const sorted = [...claims].sort((a, b) => (b.claim?.source_sentence?.length || 0) - (a.claim?.source_sentence?.length || 0));
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
      out += `<span class="verifai-hl verifai-hl-${v.toLowerCase()}" data-verdict="${v}"><span class="verifai-hl-icon">${icon}</span>${snip}</span>`;
      cursor = m.end;
    }
    if (cursor < rawText.length) {
      out += escapeHtml(rawText.slice(cursor));
    }

    pageWrapper.innerHTML = out.replace(/\n\n/g, "<br><br>");
    pdfPagesContainer.appendChild(pageWrapper);

    pageWrapper.querySelectorAll(".verifai-hl").forEach((span) => {
      const verdict = span.getAttribute("data-verdict");
      const matchedClaim = claims.find(c => c.verdict === verdict);
      if (matchedClaim) {
        span.addEventListener("mouseenter", () => showTooltip(span, matchedClaim));
        span.addEventListener("mouseleave", () => hideTooltip());
      }
    });
  }

  function initButtons() {
    document.getElementById("btn-zoom-in").addEventListener("click", () => {
      currentScale = Math.min(2.5, currentScale + 0.2);
      zoomLevelSpan.textContent = `${Math.round(currentScale * 100)}%`;
      if (pdfDoc) renderAllPages();
    });

    document.getElementById("btn-zoom-out").addEventListener("click", () => {
      currentScale = Math.max(0.6, currentScale - 0.2);
      zoomLevelSpan.textContent = `${Math.round(currentScale * 100)}%`;
      if (pdfDoc) renderAllPages();
    });

    document.getElementById("btn-download-pdf").addEventListener("click", () => {
      if (auditId) {
        window.open(`${BACKEND}/api/audit/${auditId}/report.pdf`, "_blank");
      }
    });

    // Filter buttons
    const filterAll = document.getElementById("filter-all");
    const filterHall = document.getElementById("filter-hall");
    const filterVer = document.getElementById("filter-ver");

    filterAll.addEventListener("click", () => {
      setActiveFilter("all", filterAll);
    });
    filterHall.addEventListener("click", () => {
      setActiveFilter("hallucinated", filterHall);
    });
    filterVer.addEventListener("click", () => {
      setActiveFilter("verified", filterVer);
    });
  }

  function setActiveFilter(filterName, activeBtn) {
    document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
    activeBtn.classList.add("active");
    activeFilter = filterName;

    document.querySelectorAll(".verifai-hl").forEach(span => {
      const v = (span.getAttribute("data-verdict") || "").toLowerCase();
      if (filterName === "all" || v === filterName) {
        span.style.opacity = "1";
        span.style.filter = "none";
      } else {
        span.style.opacity = "0.25";
        span.style.filter = "grayscale(1)";
      }
    });
  }

  function showError(msg) {
    pdfLoadingEl.innerHTML = `<div style="color:#ef4444;font-weight:600;">${escapeHtml(msg)}</div>`;
  }

  function escapeHtml(s) {
    return (s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }
})();
