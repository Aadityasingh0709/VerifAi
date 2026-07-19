# VerifAI — Real-Time Hallucination Audit Trail

**Hack Helix | Track 5 Problem 1**

VerifAI is a Chrome browser extension that verifies AI-generated text in real time. Highlight any AI output on any webpage (ChatGPT, Perplexity, Gemini, blog posts, anything) → click "Verify with VerifAI" → get a claim-by-claim trust audit with sources, domain detection, and hallucination forensics delivered back to a side panel inside your browser.

Behind the extension is a local FastAPI backend that:

1. **Extracts** atomic factual claims from the text (Claude).
2. **Detects the document's domain** automatically — healthcare, legal, finance, education, news, or general (Claude).
3. **Searches the web** via a three-provider fallback chain: **Tavily → Serper → Brave**.
4. **Evaluates** each claim as VERIFIED / UNVERIFIED / HALLUCINATED with a domain-aware confidence model (Claude).
5. **Runs hallucination forensics** on HALLUCINATED claims (attribute swap / amalgamation / temporal drift / domain confusion / pure confabulation) (Claude).
6. **Produces a trust score** (0–100) and an exportable **PDF audit certificate** (WeasyPrint).

## Project layout

```
verifai/
├── backend/              FastAPI backend (Python)
│   ├── main.py
│   ├── routers/audit.py
│   ├── services/
│   │   ├── claim_extractor.py
│   │   ├── domain_detector.py
│   │   ├── web_verifier.py     (Tavily → Serper → Brave fallback + cache)
│   │   ├── verdict_engine.py   (domain-aware confidence caps)
│   │   ├── genealogy.py        (hallucination forensics)
│   │   ├── report_generator.py (trust score + PDF)
│   │   ├── pipeline.py         (async orchestration)
│   │   └── llm_client.py
│   ├── models/schemas.py
│   ├── db/database.py
│   ├── data/samples.py + mock_fixtures.py
│   └── requirements.txt
└── extension/           Chrome Extension (Manifest V3)
    ├── manifest.json
    ├── background.js    (service worker, backend bridge, context menu)
    ├── content.js       (streaming-safe page capture + highlight painter)
    ├── highlight.css    (injected into pages)
    ├── sidebar.html
    ├── sidebar.css      (dark-theme panel)
    ├── sidebar.js       (SVG gauge, live feed, claim cards)
    └── icons/
```

## Running

### 1. Backend

```bash
cd VerifAi
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
cp .env.example .env      # add real API keys OR leave blank for mock mode
.venv/Scripts/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

The backend exposes:

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/audit/start` | Kick off a new audit (returns audit_id + preview domain/claim count) |
| GET  | `/api/audit/{id}/status` | Poll live stage / progress / partial claims |
| GET  | `/api/audit/{id}/results` | Full result when status = complete |
| GET  | `/api/audit/{id}/report.pdf` | Downloadable PDF certificate |
| GET  | `/api/audit/samples/list` | Three preset demo documents |

**Environment variables** (`backend/.env`):

```
ANTHROPIC_API_KEY=
TAVILY_API_KEY=
SERPER_API_KEY=
BRAVE_API_KEY=
CORS_ORIGINS=*
MOCK_MODE=            # set to 1 to force offline demo with canned results
```

No keys? The backend automatically runs in `MOCK_MODE` and returns pre-written verdicts for the three sample documents (French Revolution, Aspirin, JWST) — useful if the conference Wi-Fi dies.

### 2. Chrome extension

1. Open `chrome://extensions`.
2. Enable **Developer mode**.
3. Click **Load unpacked** and select the `verifai/extension` folder.
4. Pin the VerifAI icon to the toolbar.
5. Click it on any page → the side panel opens.

**Two ways to audit:**

- **Scan the whole visible page**: Click the VerifAI icon → **Scan This Page**. On streaming sites (ChatGPT, Perplexity, Claude, Gemini) the content script waits for the stream to settle before capturing.
- **Verify a selection**: Select text on any page → right-click → **Verify with VerifAI**.
- **Paste any text**: Sidebar → **Paste & Verify** → paste and run.
- **Try the samples**: Three one-click demo documents appear in the sidebar.

## How it scores

A trust score from 0 to 100 is computed per audit:

```
raw     = (Σ weight[verdict] × confidence / 100) / claim_count × 100
final   = max(0, raw − high_stakes_hallucinations × 10 × domain_penalty)
```

`weight[VERIFIED] = 1.0`, `weight[UNVERIFIED] = 0.4`, `weight[HALLUCINATED] = 0.0`.

Domain-penalty multiplier: 2.0 for healthcare/legal, 1.5 for finance, 1.0 everywhere else.

Bands: **85–100** High Trustworthiness (green) · **60–84** Moderate (yellow) · **35–59** Low (orange) · **0–34** Unreliable (red).

Source trust tiers (used to cap confidence):

- **Tier 1 — High Trust**: .gov / .edu / peer-reviewed journals / major wires (Reuters, AP, BBC, NYT, Nature, NASA, WHO, CDC, NEJM, PubMed, Mayo).
- **Tier 2 — Trusted**: Britannica, Wikipedia, WSJ, FT, The Economist, Guardian.
- **Tier 3 — Standard**: general web.
- **Tier 4 — Low Trust**: Medium, Substack, Reddit, Quora, LinkedIn, Blogspot.

## Why this is different

| Tool | Gap VerifAI fills |
|---|---|
| Vectara HHEM | needs original source doc — useless for AI text written from scratch |
| Patronus AI  | developer API only, no UI, no browser integration |
| Galileo / Cleanlab | enterprise ML monitoring, not end-user |
| HaluCheck    | academic demo, not production |

VerifAI is the first tool a regular person can use to verify any AI output on any webpage in one click.

## Architecture notes

- **Anthropic model**: `claude-sonnet-4-20250514` via Anthropic Python SDK for every LLM call (claim extraction, domain detection, search query generation, verdicts, genealogy).
- **Search fallback chain** is attempted in order: Tavily → Serper → Brave. Cache lives in `backend/cache/` and keys on the query hash, so reruns against the same doc don't burn quota.
- **Concurrency**: claims are verified in parallel behind an `asyncio.Semaphore(5)` to respect rate limits.
- **Streaming detection**: content.js uses a MutationObserver stability counter to wait for the page text to stop changing before capturing on ChatGPT/Perplexity-style sites.
- **Privacy**: Everything runs locally. The extension talks to `http://localhost:8000`; the only external calls are the LLM + search APIs, all initiated from your own machine.

## Tech stack

- Chrome Extension Manifest V3 (sidePanel + contextMenus)
- FastAPI, Uvicorn, Pydantic v2
- Anthropic Python SDK (Claude Sonnet 4)
- Tavily / Serper / Brave search APIs
- SQLite + SQLAlchemy
- WeasyPrint with a ReportLab fallback for PDF generation on Windows
- httpx (for Serper & Brave)

## Status

All six pipeline stages implemented and verified end-to-end against three preset documents in mock mode. PDF certificate renders correctly. Extension loads cleanly in Chrome and talks to the local backend.
