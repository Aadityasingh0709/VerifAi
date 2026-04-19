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
        if (!tab) return sendResponse({ ok: false, error: "no active tab" });

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
        await new Promise((r) => setTimeout(r, 500));

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
                // Direct DOM extraction as fallback
                const selectors = [
                  '[data-message-author-role="assistant"]',
                  ".agent-turn .markdown",
                  "model-response",
                  "message-content",
                  '[data-testid="chat-message-text"]',
                  ".prose",
                  "article",
                  "main",
                ];
                let best = "";
                for (const sel of selectors) {
                  document.querySelectorAll(sel).forEach((el) => {
                    const t = (el.innerText || "").trim();
                    if (t.length > best.length) best = t;
                  });
                  if (best.length > 100) break;
                }
                if (best.length < 50) best = (document.body.innerText || "").trim();
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

        if (!text) {
          return sendResponse({
            ok: false,
            error: "Could not read page text. Try using Paste & Verify instead.",
          });
        }
        queueCapture(tab.id, text, "page");
        sendResponse({ ok: true });
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
  const tabs = await chrome.tabs.query({
    active: true,
    currentWindow: true,
  });
  return tabs[0] || null;
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