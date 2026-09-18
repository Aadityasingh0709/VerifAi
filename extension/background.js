/* VerifAI service worker.
 * Bridges the content script + sidebar, talks to the FastAPI backend,
 * and owns the right-click context menu.
 */

const BACKEND = "http://localhost:8000";
let lastCapturedText = null;

// Open the side panel when the action icon is clicked.
chrome.action.onClicked.addListener(async (tab) => {
  try {
    await chrome.sidePanel.open({ tabId: tab.id });
  } catch (e) {
    console.warn("[VerifAI] could not open side panel:", e);
  }
});

// Let the side panel open when the user clicks the toolbar icon.
chrome.sidePanel
  .setPanelBehavior({ openPanelOnActionClick: true })
  .catch((e) => console.warn("[VerifAI] setPanelBehavior failed:", e));

// Register the right-click "Verify with VerifAI" menu on first install.
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "verifai-verify-selection",
    title: "Verify with VerifAI",
    contexts: ["selection"],
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== "verifai-verify-selection" || !info.selectionText)
    return;
  try {
    await chrome.sidePanel.open({ tabId: tab.id });
  } catch (e) {
    /* ignore */
  }
  queueCapture(tab.id, info.selectionText, "selection");
});

// Forward messages between content script and side panel, and proxy backend calls.
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  (async () => {
    try {
      if (msg.type === "VERIFAI_CAPTURE_SCAN_PAGE") {
        const tab = await activeTab();
        if (!tab) return sendResponse({ ok: false, error: "No active browser tab found." });

        if (!tab.url || tab.url.startsWith("chrome://") || tab.url.startsWith("edge://") || tab.url.startsWith("chrome-extension://") || tab.url.startsWith("about:")) {
          return sendResponse({
            ok: false,
            error: "Cannot scan browser internal pages (e.g. chrome://). Please switch to a regular webpage (like Wikipedia, an article, or ChatGPT) and click Scan again.",
          });
        }

        // Force-inject content script first (in case it wasn't loaded)
        try {
          await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            files: ["content.js"],
          });
        } catch (injectErr) {
          console.warn("[VerifAI] inject failed:", injectErr);
        }

        // Small delay to let the script initialize
        await new Promise((r) => setTimeout(r, 400));

        // Now try to extract text
        let text = "";
        const res = await sendToTab(tab.id, { type: "VERIFAI_EXTRACT_PAGE_TEXT" });
        text = res && res.text ? res.text.trim() : "";

        // If content script extraction failed, try executeScript directly
        if (!text) {
          try {
            const results = await chrome.scripting.executeScript({
              target: { tabId: tab.id },
              func: () => {
                const clean = (s) => (s || "").replace(/\u00a0/g, " ").replace(/\n{3,}/g, "\n\n").trim();
                // 1. Selection
                const sel = clean(window.getSelection ? window.getSelection().toString() : "");
                if (sel && sel.length >= 15) return sel;

                // 2. AI chat selectors
                const selectors = [
                  '[data-message-author-role="assistant"]',
                  'article[data-testid^="conversation-turn"]',
                  ".agent-turn .markdown",
                  "model-response",
                  "message-content",
                  ".model-response-text",
                  '[data-testid="chat-message-text"]',
                  '[data-testid="answer"]',
                  "article",
                  "main",
                  "#content",
                ];
                let best = "";
                for (const sel of selectors) {
                  const els = Array.from(document.querySelectorAll(sel));
                  if (els.length > 0) {
                    const last = clean(els[els.length - 1].innerText || "");
                    if (last.length > 25) return last;
                  }
                  for (const el of els) {
                    const t = clean(el.innerText || "");
                    if (t.length > best.length) best = t;
                  }
                  if (best.length > 200) break;
                }

                // 3. Paragraphs
                const ps = Array.from(document.querySelectorAll("p, h1, h2, h3, li"))
                  .map((p) => clean(p.innerText || ""))
                  .filter((t) => t.length > 15);
                if (ps.length > 0) {
                  const joined = ps.join("\n\n");
                  if (joined.length > best.length) best = joined;
                }

                // 4. Body fallback
                if (best.length < 20) best = clean(document.body.innerText || "");
                return best;
              },
            });
            if (results && results[0] && results[0].result) {
              text = results[0].result.trim();
            }
          } catch (directErr) {
            console.warn("[VerifAI] direct extraction failed:", directErr);
          }
        }

        if (!text || text.length < 15) {
          return sendResponse({
            ok: false,
            error: "No readable text found on this page. If this page has AI text, you can highlight it or use 'Paste & Verify'.",
          });
        }
        queueCapture(tab.id, text, "page");
        sendResponse({ ok: true, text });
        return;
      }

      // PDF URL bypass: fetch the raw PDF bytes and send to backend for extraction.
      // This works because the service worker has <all_urls> permission and can fetch
      // the raw file directly, bypassing Chrome's sandboxed PDF viewer entirely.
      if (msg.type === "VERIFAI_SCAN_PDF_URL") {
        const pdfUrl = msg.url;
        const title = msg.title || "PDF document";
        if (!pdfUrl) return sendResponse({ ok: false, error: "No PDF URL provided." });

        let pdfBlob;
        try {
          const r = await fetch(pdfUrl);
          if (!r.ok) throw new Error(`HTTP ${r.status}`);
          pdfBlob = await r.blob();
        } catch (fetchErr) {
          return sendResponse({
            ok: false,
            error: `Could not download the PDF (${fetchErr.message}). The file may require authentication or be restricted.`,
          });
        }

        // Derive a filename from the URL
        const fileName = decodeURIComponent(pdfUrl.split("/").pop().split("?")[0]) || "document.pdf";

        // POST to backend as multipart form upload
        let data;
        try {
          const form = new FormData();
          form.append("file", new File([pdfBlob], fileName, { type: "application/pdf" }));
          const resp = await fetch(`${BACKEND}/api/audit/upload-pdf`, {
            method: "POST",
            body: form,
          });
          data = await resp.json();
          if (!resp.ok) {
            return sendResponse({ ok: false, error: data.detail || "Backend rejected the PDF." });
          }
        } catch (backendErr) {
          return sendResponse({
            ok: false,
            error: "Cannot reach VerifAI backend. Make sure FastAPI is running on http://localhost:8000.",
          });
        }

        sendResponse({
          ok: true,
          auditId: data.audit_id,
          domain: data.domain || null,
          totalClaims: data.total_claims ?? null,
        });
        return;
      }

      if (msg.type === "VERIFAI_NEW_CAPTURE" && msg.text) {
        // Relay auto-scan capture from content script to sidebar
        lastCapturedText = { text: msg.text, source: msg.source || "auto-scan", timestamp: Date.now() };
        // Re-broadcast so the sidebar picks it up
        chrome.runtime.sendMessage({
          type: "VERIFAI_NEW_CAPTURE",
          text: msg.text,
          source: msg.source || "auto-scan",
        }).catch(() => {}); // sidebar may not be open yet
        sendResponse({ ok: true });
        return;
      }

      if (msg.type === "VERIFAI_GET_LAST_CAPTURE") {
        sendResponse({ ok: true, capture: lastCapturedText });
        return;
      }

      if (msg.type === "VERIFAI_START_AUDIT") {
        const r = await fetch(`${BACKEND}/api/audit/start`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            document_text: msg.text,
            document_title: msg.title || "Web page capture",
          }),
        });
        const data = await r.json();
        sendResponse({ ok: r.ok, data });
        return;
      }

      if (msg.type === "VERIFAI_POLL_STATUS") {
        const r = await fetch(`${BACKEND}/api/audit/${msg.auditId}/status`);
        const data = await r.json();
        sendResponse({ ok: r.ok, data });
        return;
      }

      if (msg.type === "VERIFAI_GET_RESULTS") {
        const r = await fetch(`${BACKEND}/api/audit/${msg.auditId}/results`);
        const data = await r.json();
        sendResponse({ ok: r.ok, data });
        return;
      }

      if (msg.type === "VERIFAI_OPEN_PDF") {
        chrome.tabs.create({
          url: `${BACKEND}/api/audit/${msg.auditId}/report.pdf`,
        });
        sendResponse({ ok: true });
        return;
      }

      if (msg.type === "VERIFAI_APPLY_HIGHLIGHTS") {
        const tab = await activeTab();
        if (!tab) return sendResponse({ ok: false });
        chrome.tabs.sendMessage(tab.id, {
          type: "VERIFAI_APPLY_HIGHLIGHTS_TO_PAGE",
          claims: msg.claims,
        });
        sendResponse({ ok: true });
        return;
      }

      if (msg.type === "VERIFAI_LIST_SAMPLES") {
        const r = await fetch(`${BACKEND}/api/audit/samples/list`);
        const data = await r.json();
        sendResponse({ ok: r.ok, data });
        return;
      }

      if (msg.type === "VERIFAI_GET_SAMPLE") {
        const r = await fetch(`${BACKEND}/api/audit/samples/${msg.id}`);
        const data = await r.json();
        sendResponse({ ok: r.ok, data });
        return;
      }
    } catch (e) {
      console.error("[VerifAI] backend error:", e);
      sendResponse({
        ok: false,
        error:
          "Cannot reach VerifAI backend. Make sure the FastAPI server is running on http://localhost:8000.",
      });
    }
  })();
  return true; // keep channel open for async sendResponse
});

function queueCapture(tabId, text, source) {
  lastCapturedText = { text, source, timestamp: Date.now() };
  chrome.storage.local.set({ lastCapture: lastCapturedText });
  // Broadcast to the side panel if it's open.
  chrome.runtime.sendMessage({
    type: "VERIFAI_NEW_CAPTURE",
    text,
    source,
  });
}

async function activeTab() {
  let tabs = await chrome.tabs.query({
    active: true,
    lastFocusedWindow: true,
  });
  if (!tabs || tabs.length === 0) {
    tabs = await chrome.tabs.query({
      active: true,
      currentWindow: true,
    });
  }
  return tabs && tabs[0] ? tabs[0] : null;
}

async function sendToTab(tabId, message) {
  return new Promise((resolve) => {
    chrome.tabs.sendMessage(tabId, message, (response) => {
      if (chrome.runtime.lastError) {
        console.warn("[VerifAI] sendToTab error:", chrome.runtime.lastError.message);
        resolve(null);
      } else {
        resolve(response);
      }
    });
  });
}