/* VerifAI content script — extracts AI text, auto-scans, robust in-page highlights. */
(function () {
  if (window.__VERIFAI_CONTENT_LOADED__) return;
  window.__VERIFAI_CONTENT_LOADED__ = true;

  const host = location.host;
  const isChatGPT = host.includes("chatgpt.com") || host.includes("chat.openai.com");
  const isGemini = host.includes("gemini.google.com");
  const isClaude = host.includes("claude.ai");
  const isPerplexity = host.includes("perplexity.ai");
  const isAISite = isChatGPT || isGemini || isClaude || isPerplexity;

  let inpageTooltipEl = null;
  let tooltipHideTimer = null;

  /* ---------- message listener ---------- */
  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg.type === "VERIFAI_EXTRACT_PAGE_TEXT") {
      grabText().then((t) => sendResponse({ text: t }));
      return true;
    }
    if (msg.type === "VERIFAI_APPLY_HIGHLIGHTS_TO_PAGE") {
      clearHighlights();
      const count = applyHighlights(msg.claims || []);
      sendResponse({ ok: true, count });
      return true;
    }
    if (msg.type === "VERIFAI_CLEAR_HIGHLIGHTS") {
      clearHighlights();
      sendResponse({ ok: true });
      return true;
    }
  });

  /* ---------- text extraction ---------- */
  function grabText() {
    // 1. Check user selection first
    const selection = clean(window.getSelection ? window.getSelection().toString() : "");
    if (selection && selection.length >= 15) {
      return Promise.resolve(selection);
    }

    // 2. Check current page text immediately
    const current = bestText();
    if (current && current.length >= 25) {
      // If not actively streaming (no stop button / streaming indicator), return immediately
      const isStreaming = document.querySelector('button[aria-label="Stop generating"], .result-streaming, [data-testid="stop-button"]');
      if (!isStreaming || !isAISite) {
        return Promise.resolve(current);
      }
    }

    // 3. If streaming on AI site, wait briefly for it to settle
    if (!isAISite) return Promise.resolve(current || clean(document.body.innerText || ""));

    return new Promise((resolve) => {
      let last = current;
      let stable = 0;
      let elapsed = 0;
      const iv = setInterval(() => {
        const now = bestText();
        elapsed += 400;
        if (now === last && now.length > 20) {
          stable++;
          if (stable >= 2 || elapsed >= 3000) {
            clearInterval(iv);
            resolve(now);
          }
        } else {
          stable = 0;
          last = now;
        }
        if (elapsed >= 4000) {
          clearInterval(iv);
          resolve(now || last || clean(document.body.innerText || ""));
        }
      }, 400);
    });
  }

  function bestText() {
    // 1. Check user selection
    const sel = clean(window.getSelection ? window.getSelection().toString() : "");
    if (sel && sel.length >= 20) return sel;

    const selectors = [];

    if (isChatGPT) {
      selectors.push(
        '[data-message-author-role="assistant"]',
        'article[data-testid^="conversation-turn"]',
        ".agent-turn .markdown",
        "main .markdown.prose",
        "[data-message-id]"
      );
    }
    if (isGemini) {
      selectors.push(
        "model-response",
        "message-content",
        ".model-response-text",
        ".response-container",
        ".markdown-main-panel",
        '[data-test-id="model-response"]'
      );
    }
    if (isClaude) {
      selectors.push('[data-testid="chat-message-text"]', ".font-claude-message", ".prose");
    }
    if (isPerplexity) {
      selectors.push('[data-testid="answer"]', ".prose", ".markdown");
    }
    // Generic fallbacks
    selectors.push("article", "main", '[role="main"]', ".markdown", ".prose");

    // Collect all matching elements, pick last assistant turn or longest
    let longest = "";
    for (const s of selectors) {
      try {
        const els = Array.from(document.querySelectorAll(s));
        if (els.length > 0) {
          // If on AI site, prefer the latest response
          if (isAISite) {
            const last = clean(els[els.length - 1].innerText || els[els.length - 1].textContent || "");
            if (last.length > 25) return last;
          }
          for (const el of els) {
            const t = clean(el.innerText || el.textContent || "");
            if (t.length > longest.length) longest = t;
          }
        }
      } catch (_) {}
      if (longest.length > 300) break;
    }

    // On standard webpages, aggregate paragraphs from main article container
    if (!isAISite) {
      const container = document.querySelector("article, main, [role='main'], #content, .content, .mw-parser-output, .entry-content, .post-content") || document.body;
      const paragraphs = Array.from(container.querySelectorAll("p, h1, h2, h3, li"))
        .map(el => clean(el.innerText || el.textContent || ""))
        .filter(t => t.length > 20);
      if (paragraphs.length > 0) {
        const aggregated = paragraphs.join("\n\n");
        if (aggregated.length > longest.length) longest = aggregated;
      }
    }

    // Ultimate fallback
    if (longest.length < 25) {
      longest = clean(document.body.innerText || "");
    }
    return longest;
  }

  function clean(s) {
    return (s || "").replace(/\u00a0/g, " ").replace(/\n{3,}/g, "\n\n").trim();
  }

  /* ---------- auto-scan ---------- */
  let lastAutoText = "";
  let debounce = null;

  if (isAISite) {
    const obs = new MutationObserver(() => {
      clearTimeout(debounce);
      debounce = setTimeout(() => {
        const t = bestText();
        if (t.length > 50 && t !== lastAutoText && Math.abs(t.length - lastAutoText.length) > 30) {
          lastAutoText = t;
          chrome.runtime.sendMessage(
            { type: "VERIFAI_NEW_CAPTURE", text: t, source: "auto-scan" },
            () => {
              if (chrome.runtime.lastError) {
                /* background waking up or unavailable, ignore */
              }
            }
          );
        }
      }, 3500);
    });
    obs.observe(document.body, { childList: true, subtree: true, characterData: true });
  }

  /* ---------- in-page tooltip singleton ---------- */
  function getInpageTooltip() {
    if (!inpageTooltipEl) {
      inpageTooltipEl = document.createElement("div");
      inpageTooltipEl.id = "verifai-inpage-tooltip";
      document.body.appendChild(inpageTooltipEl);
      inpageTooltipEl.addEventListener("mouseenter", () => clearTimeout(tooltipHideTimer));
      inpageTooltipEl.addEventListener("mouseleave", () => hideTooltip());
    }
    return inpageTooltipEl;
  }

  function showTooltip(targetSpan, claim) {
    clearTimeout(tooltipHideTimer);
    const tt = getInpageTooltip();
    const verdict = claim.verdict || "UNVERIFIED";
    const conf = claim.confidence ?? 0;
    const icon = verdict === "HALLUCINATED" ? "\u26a0" : verdict === "VERIFIED" ? "\u2713" : "?";

    let contraHtml = "";
    if (verdict === "HALLUCINATED" && claim.contradicting_detail) {
      contraHtml = `<div class="verifai-tt-contra"><strong>Contradiction:</strong> ${escapeHtml(claim.contradicting_detail)}</div>`;
    } else if (claim.reasoning) {
      contraHtml = `<div class="verifai-tt-body" style="font-size:11px;color:#94a3b8">${escapeHtml(claim.reasoning.slice(0, 160))}</div>`;
    }

    tt.innerHTML = `
      <div class="verifai-tt-head">
        <span class="verifai-tt-badge ${verdict}">${icon} ${verdict}</span>
        <span class="verifai-tt-conf">${conf}% confidence</span>
      </div>
      <div class="verifai-tt-body"><strong>Claim:</strong> ${escapeHtml(claim.claim?.claim_text || "")}</div>
      ${contraHtml}
      <div class="verifai-tt-hint">Click highlight to open in VerifAI sidebar</div>
    `;

    tt.classList.add("verifai-tooltip-visible");

    // Position above target if room, else below
    const rect = targetSpan.getBoundingClientRect();
    const ttRect = tt.getBoundingClientRect();
    let top = window.scrollY + rect.top - ttRect.height - 8;
    if (top < window.scrollY + 10) {
      top = window.scrollY + rect.bottom + 8;
    }
    let left = window.scrollX + rect.left + (rect.width / 2) - (ttRect.width / 2);
    if (left < 10) left = 10;
    if (left + ttRect.width > window.innerWidth - 10) {
      left = window.innerWidth - ttRect.width - 10;
    }

    tt.style.top = `${top}px`;
    tt.style.left = `${left}px`;
  }

  function hideTooltip() {
    clearTimeout(tooltipHideTimer);
    tooltipHideTimer = setTimeout(() => {
      if (inpageTooltipEl) {
        inpageTooltipEl.classList.remove("verifai-tooltip-visible");
      }
    }, 150);
  }

  function escapeHtml(s) {
    return (s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  /* ---------- text normalization for matching ---------- */
  function normalizeText(s) {
    return (s || "")
      .replace(/[\u2018\u2019]/g, "'")
      .replace(/[\u201C\u201D]/g, '"')
      .replace(/[\u2013\u2014]/g, "-")
      .replace(/\s+/g, " ")
      .trim();
  }

  /* ---------- highlight painting ---------- */
  function clearHighlights() {
    hideTooltip();
    document.querySelectorAll("span.verifai-hl").forEach((span) => {
      const p = span.parentNode;
      if (!p) return;
      const text = document.createTextNode(span.textContent || "");
      p.replaceChild(text, span);
      p.normalize();
    });
  }

  function applyHighlights(claims) {
    if (!Array.isArray(claims) || claims.length === 0) return 0;

    // Prioritize hallucinations first, then longer claims
    const sorted = [...claims].sort((a, b) => {
      const vScore = { HALLUCINATED: 3, UNVERIFIED: 2, VERIFIED: 1 };
      const diff = (vScore[b.verdict] || 0) - (vScore[a.verdict] || 0);
      if (diff !== 0) return diff;
      const lenA = (a.claim?.source_sentence || a.claim?.claim_text || "").length;
      const lenB = (b.claim?.source_sentence || b.claim?.claim_text || "").length;
      return lenB - lenA;
    });

    let highlightCount = 0;

    for (const c of sorted) {
      if (!c || !c.claim) continue;
      const candidates = [];
      
      const src = (c.claim.source_sentence || "").trim();
      const txt = (c.claim.claim_text || "").trim();

      if (src && src.length >= 8) candidates.push(src);
      if (txt && txt.length >= 8 && txt !== src) candidates.push(txt);

      // Add phrase chunks if sentence is long (e.g. first 60 chars or words)
      if (src && src.length > 40) {
        const words = src.split(/\s+/);
        if (words.length >= 6) {
          candidates.push(words.slice(0, 8).join(" "));
          candidates.push(words.slice(-7).join(" "));
        }
      }

      let matched = false;
      for (const needle of candidates) {
        if (highlightInDOM(needle, c)) {
          matched = true;
          highlightCount++;
          break;
        }
      }
    }

    return highlightCount;
  }

  /**
   * Searches the DOM for `needle` across all block elements and text nodes,
   * handling nested tags, whitespace variations, and multi-node spans.
   */
  function highlightInDOM(needle, claim) {
    const normNeedle = normalizeText(needle);
    if (!normNeedle || normNeedle.length < 6) return false;

    // Potential container elements to search
    const containers = Array.from(
      document.querySelectorAll(
        "article, main, [role='main'], [data-message-id], model-response, message-content, .markdown, .prose, .font-claude-message, p, li, blockquote, div, section"
      )
    );

    // Also include document.body as fallback container
    if (!containers.includes(document.body)) containers.push(document.body);

    for (const container of containers) {
      if (container.closest("span.verifai-hl")) continue;
      if (["SCRIPT", "STYLE", "NOSCRIPT", "TEXTAREA", "INPUT"].includes(container.tagName)) continue;

      // Collect all valid text nodes under this container
      const textNodes = [];
      const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, {
        acceptNode: (n) => {
          if (!n.nodeValue) return NodeFilter.FILTER_REJECT;
          const p = n.parentElement;
          if (!p) return NodeFilter.FILTER_REJECT;
          if (["SCRIPT", "STYLE", "NOSCRIPT"].includes(p.tagName)) return NodeFilter.FILTER_REJECT;
          if (p.closest("span.verifai-hl")) return NodeFilter.FILTER_REJECT;
          return NodeFilter.FILTER_ACCEPT;
        },
      });

      let n;
      while ((n = walker.nextNode())) {
        textNodes.push(n);
      }

      if (textNodes.length === 0) continue;

      // Build combined text and index mapping
      let combined = "";
      const map = []; // each entry: { node, startInCombined, endInCombined }
      for (const node of textNodes) {
        const start = combined.length;
        combined += node.nodeValue;
        map.push({ node, start, end: combined.length });
      }

      // Check for exact substring match first
      let matchStart = combined.indexOf(needle);
      let matchLen = needle.length;

      // If exact fails, try normalized search
      if (matchStart === -1) {
        const normCombined = normalizeText(combined);
        const normIndex = normCombined.toLowerCase().indexOf(normNeedle.toLowerCase());
        if (normIndex !== -1) {
          // Approximate position in raw combined
          matchStart = findRawIndex(combined, normCombined, normIndex);
          matchLen = findRawLength(combined, matchStart, normNeedle.length);
        }
      }

      if (matchStart !== -1 && matchLen > 0) {
        const matchEnd = matchStart + matchLen;
        const success = wrapRangeInSpan(map, matchStart, matchEnd, claim);
        if (success) return true;
      }
    }

    return false;
  }

  function findRawIndex(raw, norm, normTargetIndex) {
    let nIdx = 0;
    for (let rIdx = 0; rIdx < raw.length; rIdx++) {
      if (nIdx >= normTargetIndex) return rIdx;
      if (normalizeChar(raw[rIdx]) === norm[nIdx]) {
        nIdx++;
      }
    }
    return 0;
  }

  function findRawLength(raw, rawStart, normLen) {
    let nMatched = 0;
    for (let i = rawStart; i < raw.length; i++) {
      nMatched++;
      if (nMatched >= normLen) return (i - rawStart + 1);
    }
    return Math.min(normLen, raw.length - rawStart);
  }

  function normalizeChar(ch) {
    if (ch === "\u2018" || ch === "\u2019") return "'";
    if (ch === "\u201C" || ch === "\u201D") return '"';
    if (ch === "\u2013" || ch === "\u2014") return '-';
    if (/\s/.test(ch)) return " ";
    return ch;
  }

  /**
   * Wraps the text slices between matchStart and matchEnd across the text nodes in `map`.
   */
  function wrapRangeInSpan(map, matchStart, matchEnd, claim) {
    try {
      const vClass = claim.verdict === "VERIFIED" ? "verifai-hl-verified"
        : claim.verdict === "HALLUCINATED" ? "verifai-hl-hallucinated"
        : "verifai-hl-unverified";
      const icon = claim.verdict === "HALLUCINATED" ? "\u26a0"
        : claim.verdict === "VERIFIED" ? "\u2713" : "?";

      // Identify affected text nodes
      const affected = map.filter((entry) => entry.end > matchStart && entry.start < matchEnd);
      if (affected.length === 0) return false;

      let isFirst = true;

      for (const entry of affected) {
        const node = entry.node;
        if (!node.parentNode) continue;

        const sliceStart = Math.max(0, matchStart - entry.start);
        const sliceEnd = Math.min(node.nodeValue.length, matchEnd - entry.start);
        if (sliceStart >= sliceEnd) continue;

        const textVal = node.nodeValue;
        const beforeText = textVal.slice(0, sliceStart);
        const matchText = textVal.slice(sliceStart, sliceEnd);
        const afterText = textVal.slice(sliceEnd);

        const frag = document.createDocumentFragment();
        if (beforeText) frag.appendChild(document.createTextNode(beforeText));

        const span = document.createElement("span");
        span.className = `verifai-hl ${vClass}`;
        span.dataset.claimId = String(claim.claim?.id ?? "");
        span.dataset.verdict = claim.verdict;

        if (isFirst) {
          const ic = document.createElement("span");
          ic.className = "verifai-hl-icon";
          ic.textContent = icon;
          span.appendChild(ic);
          isFirst = false;
        }

        span.appendChild(document.createTextNode(matchText));

        // Tooltip listeners
        span.addEventListener("mouseenter", () => showTooltip(span, claim));
        span.addEventListener("mouseleave", () => hideTooltip());

        // Click listener to focus claim in sidebar
        span.addEventListener("click", (e) => {
          e.stopPropagation();
          span.classList.add("verifai-hl-pulse");
          setTimeout(() => span.classList.remove("verifai-hl-pulse"), 1200);
          chrome.runtime.sendMessage(
            {
              type: "VERIFAI_FOCUS_CLAIM",
              claimId: claim.claim?.id,
            },
            () => {
              if (chrome.runtime.lastError) {
                /* sidebar not open, ignore */
              }
            }
          );
        });

        frag.appendChild(span);
        if (afterText) frag.appendChild(document.createTextNode(afterText));

        node.parentNode.replaceChild(frag, node);
      }

      return true;
    } catch (e) {
      console.warn("[VerifAI] highlight wrapping failed:", e);
      return false;
    }
  }
})();
