/* VerifAI content script — extracts AI text, auto-scans, highlights. */
(function () {
  if (window.__VERIFAI_CONTENT_LOADED__) return;
  window.__VERIFAI_CONTENT_LOADED__ = true;

  const host = location.host;
  const isChatGPT = host.includes("chatgpt.com") || host.includes("chat.openai.com");
  const isGemini = host.includes("gemini.google.com");
  const isClaude = host.includes("claude.ai");
  const isPerplexity = host.includes("perplexity.ai");
  const isAISite = isChatGPT || isGemini || isClaude || isPerplexity;

  /* ---------- message listener ---------- */
  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg.type === "VERIFAI_EXTRACT_PAGE_TEXT") {
      grabText().then((t) => sendResponse({ text: t }));
      return true;
    }
    if (msg.type === "VERIFAI_APPLY_HIGHLIGHTS_TO_PAGE") {
      clearHighlights();
      applyHighlights(msg.claims || []);
      sendResponse({ ok: true });
    }
  });

  /* ---------- text extraction ---------- */
  function grabText() {
    if (!isAISite) return Promise.resolve(bestText());
    // On AI sites, wait for streaming to settle
    return new Promise((resolve) => {
      let last = "";
      let stable = 0;
      let elapsed = 0;
      const iv = setInterval(() => {
        const now = bestText();
        elapsed += 500;
        if (now === last && now.length > 30) {
          stable++;
          if (stable >= 3 || elapsed >= 6000) { clearInterval(iv); resolve(now); }
        } else {
          stable = 0;
          last = now;
        }
        if (elapsed >= 8000) { clearInterval(iv); resolve(now || last); }
      }, 500);
    });
  }

  function bestText() {
    const selectors = [];

    if (isChatGPT) {
      selectors.push(
        '[data-message-author-role="assistant"]',
        ".agent-turn .markdown",
        "main .markdown.prose"
      );
    }
    if (isGemini) {
      selectors.push(
        "model-response",
        "model-response message-content",
        "message-content",
        ".model-response-text",
        ".response-container",
        ".markdown-main-panel"
      );
    }
    if (isClaude) {
      selectors.push('[data-testid="chat-message-text"]', ".prose");
    }
    if (isPerplexity) {
      selectors.push('[data-testid="answer"]', ".prose", ".markdown");
    }
    // Generic fallbacks
    selectors.push("article", "main", '[role="main"]', ".markdown", ".prose");

    // Collect all matching elements, get text from each, pick longest
    let longest = "";
    for (const sel of selectors) {
      try {
        document.querySelectorAll(sel).forEach((el) => {
          const t = clean(el.innerText || el.textContent || "");
          if (t.length > longest.length) longest = t;
        });
      } catch (_) {}
      if (longest.length > 200) break; // good enough
    }

    // Ultimate fallback
    if (longest.length < 50) {
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
          chrome.runtime.sendMessage({ type: "VERIFAI_NEW_CAPTURE", text: t, source: "auto-scan" });
        }
      }, 3500);
    });
    obs.observe(document.body, { childList: true, subtree: true, characterData: true });
  }

  /* ---------- highlight painting ---------- */
  function clearHighlights() {
    document.querySelectorAll("span.verifai-hl").forEach((span) => {
      const p = span.parentNode;
      if (!p) return;
      p.replaceChild(document.createTextNode(span.textContent || ""), span);
      p.normalize();
    });
  }

  function applyHighlights(claims) {
    if (!Array.isArray(claims)) return;
    const sorted = claims
      .filter((c) => c && c.claim && c.claim.source_sentence)
      .sort((a, b) => (b.claim.source_sentence || "").length - (a.claim.source_sentence || "").length);
    for (const c of sorted) {
      const needle = (c.claim.source_sentence || "").trim();
      if (needle.length < 12) continue;
      highlightOne(needle, c);
    }
  }

  function highlightOne(needle, claim) {
    const vClass = claim.verdict === "VERIFIED" ? "verifai-hl-verified"
      : claim.verdict === "HALLUCINATED" ? "verifai-hl-hallucinated"
      : "verifai-hl-unverified";
    const icon = claim.verdict === "HALLUCINATED" ? "\u26a0"
      : claim.verdict === "VERIFIED" ? "\u2713" : "?";

    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
      acceptNode: (n) => {
        if (!n.nodeValue || n.nodeValue.length < needle.length * 0.5) return NodeFilter.FILTER_SKIP;
        const p = n.parentElement;
        if (!p) return NodeFilter.FILTER_REJECT;
        if (["SCRIPT", "STYLE", "NOSCRIPT"].includes(p.tagName)) return NodeFilter.FILTER_REJECT;
        if (p.closest("span.verifai-hl")) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      },
    });

    let node;
    while ((node = walker.nextNode())) {
      const idx = (node.nodeValue || "").indexOf(needle);
      if (idx === -1) continue;
      const before = node.nodeValue.slice(0, idx);
      const match = node.nodeValue.slice(idx, idx + needle.length);
      const after = node.nodeValue.slice(idx + needle.length);
      const frag = document.createDocumentFragment();
      if (before) frag.appendChild(document.createTextNode(before));

      const span = document.createElement("span");
      span.className = `verifai-hl ${vClass}`;
      span.title = `${claim.verdict} (${claim.confidence}%)`;
      const ic = document.createElement("span");
      ic.className = "verifai-hl-icon";
      ic.textContent = icon;
      span.appendChild(ic);
      span.appendChild(document.createTextNode(match));
      span.addEventListener("click", (e) => {
        e.stopPropagation();
        chrome.runtime.sendMessage({ type: "VERIFAI_FOCUS_CLAIM", claimId: claim.claim.id });
      });
      frag.appendChild(span);

      if (after) frag.appendChild(document.createTextNode(after));
      node.parentNode.replaceChild(frag, node);
      break;
    }
  }
})();
